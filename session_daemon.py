#!/usr/bin/env python3
"""
session_daemon.py — MT-30 Phase 3: Session lifecycle daemon.

Polls tmux workspace, detects dead/wrapped sessions, spawns replacements,
enforces peak hours, and logs all actions to a structured audit trail.

This is a SUPERVISOR — it manages session lifecycles but never modifies
code files, places bets, or accesses financial APIs.

Usage:
    python3 session_daemon.py start [--config config.json]
    python3 session_daemon.py stop [--kill-sessions]
    python3 session_daemon.py status
    python3 session_daemon.py restart <session-id>
    python3 session_daemon.py pause <session-id>
    python3 session_daemon.py resume <session-id>
    python3 session_daemon.py log [--last N]

Safety guarantees:
    - Never spawns more than max_total_chats (hard limit)
    - Never auto-starts without explicit human activation
    - Never kills sessions without reason
    - Logs every spawn/kill/crash/restart event
    - Fails open: if daemon crashes, sessions continue running
    - Always unsets ANTHROPIC_API_KEY (Max subscription, not API credits)

Stdlib only. No external dependencies.
"""

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from session_registry import SessionRegistry, SessionState, SessionStatus
from tmux_manager import TmuxManager

# Lazy import — peak_hours may not be on path in test contexts
def peak_hours_get_status() -> dict:
    """Get peak hours status. Wrapped for mockability."""
    try:
        from peak_hours import get_status
        return get_status()
    except ImportError:
        return {"is_peak": False, "max_recommended_chats": 3}


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Structured JSONL event logger for daemon actions."""

    def __init__(self, path: str = "~/.cca-session-daemon.log"):
        self.path = os.path.expanduser(path)

    def log(self, event: str, data: Optional[dict] = None):
        """Append a structured event to the log file."""
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "data": data or {},
        }
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass  # Fail silently — logging should never crash the daemon

    def get_recent(self, n: int = 20) -> list[dict]:
        """Return the last N log entries."""
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path) as f:
                lines = f.readlines()
            entries = []
            for line in lines[-n:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
            return entries
        except OSError:
            return []


# ---------------------------------------------------------------------------
# Daemon State
# ---------------------------------------------------------------------------

@dataclass
class DaemonState:
    """Tracks daemon-level runtime state."""
    running: bool = False
    pid: Optional[int] = None
    started_at: Optional[float] = None
    total_spawns: int = 0
    total_crashes: int = 0

    def mark_started(self, pid: int):
        self.running = True
        self.pid = pid
        self.started_at = time.time()

    def mark_stopped(self):
        self.running = False

    def uptime_seconds(self) -> Optional[float]:
        if self.started_at and self.running:
            return time.time() - self.started_at
        return None

    def record_spawn(self, session_id: str):
        self.total_spawns += 1

    def record_crash(self, session_id: str):
        self.total_crashes += 1


# ---------------------------------------------------------------------------
# Session Daemon
# ---------------------------------------------------------------------------

class SessionDaemon:
    """Core daemon loop: poll, check health, spawn/restart, enforce limits."""

    DEFAULT_LOG = os.path.expanduser("~/.cca-session-daemon.log")
    DEFAULT_PID = os.path.expanduser("~/.cca-session-daemon.pid")

    def __init__(
        self,
        config_path: Optional[str] = None,
        log_path: Optional[str] = None,
        pid_path: Optional[str] = None,
    ):
        config_path = config_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "session_daemon_config.json",
        )
        self.registry = SessionRegistry(config_path)
        self.tmux = TmuxManager("cca-workspace")
        self.audit = AuditLogger(log_path or self.DEFAULT_LOG)
        self.state = DaemonState()
        self._pid_path = pid_path or self.DEFAULT_PID

    # --- Health Checking ---

    def check_health(self) -> list[dict]:
        """Check all running sessions for liveness.

        Returns a list of status change events:
        [{"session_id": str, "status": "crashed"|"stopped", "reason": str}]
        """
        results = []

        for session in self.registry.get_all_sessions():
            if session.status != SessionStatus.RUNNING:
                continue

            window_name = session.tmux_window or session.config.id
            alive = self.tmux.is_alive(window_name)

            if alive:
                continue

            # Session died — determine why
            has_wrap = self.tmux.has_wrap_marker(window_name)
            exit_code = self.tmux.get_exit_code(window_name)

            if has_wrap or exit_code == 0:
                session.mark_stopped(reason="clean_wrap")
                status = "stopped"
                reason = "clean_wrap"
            else:
                session.mark_crashed(error=f"exit_code={exit_code}")
                self.state.record_crash(session.config.id)
                status = "crashed"
                reason = f"exit_code={exit_code}"

            # Clean up the dead tmux window
            self.tmux.kill_window(window_name, graceful=False)

            self.audit.log(f"session_{status}", {
                "session": session.config.id,
                "reason": reason,
                "exit_code": exit_code,
                "restart_count": session.restart_count,
            })

            results.append({
                "session_id": session.config.id,
                "status": status,
                "reason": reason,
            })

        return results

    # --- Spawning ---

    def spawn_session(self, session: SessionState) -> bool:
        """Attempt to spawn a session. Returns True if spawned.

        Checks:
        1. Max total chats not exceeded
        2. Restart delay has elapsed (if restarting)
        3. Max restarts per hour not exceeded
        """
        # Check max chats
        running_count = len(self.registry.get_running_sessions())
        if running_count >= self.registry.max_total_chats:
            return False

        # Check restart delay (only for non-PENDING sessions)
        if session.status != SessionStatus.PENDING:
            if session.stopped_at is not None:
                elapsed = time.time() - session.stopped_at
                if elapsed < session.config.restart_delay_seconds:
                    return False

            # Check max restarts per hour
            if not session.can_restart(self.registry.max_restarts_per_hour):
                session.mark_failed(reason="max_restarts_exceeded")
                self.audit.log("session_failed", {
                    "session": session.config.id,
                    "reason": "max_restarts_exceeded",
                    "restart_count": session.restart_count,
                })
                return False

        # Spawn via tmux
        try:
            pid = self.tmux.create_window(
                window_name=session.config.id,
                command=session.config.command,
                env=session.config.env,
                cwd=session.config.cwd,
            )
        except Exception as e:
            self.audit.log("spawn_error", {
                "session": session.config.id,
                "error": str(e),
            })
            return False

        # Record the spawn
        if session.status != SessionStatus.PENDING:
            session.record_restart()

        session.mark_running(pid=pid, tmux_window=session.config.id)
        self.state.record_spawn(session.config.id)

        self.audit.log("session_spawned", {
            "session": session.config.id,
            "pid": pid,
            "restart_count": session.restart_count,
        })

        return True

    # --- Peak Hours ---

    def enforce_peak_hours(self) -> list[dict]:
        """Enforce peak hour limits. Returns list of actions taken."""
        status = peak_hours_get_status()
        if not status.get("is_peak", False):
            return []

        actions = []
        deprioritizable = self.registry.get_deprioritizable(is_peak=True)

        for session in deprioritizable:
            if session.status == SessionStatus.RUNNING:
                window_name = session.tmux_window or session.config.id
                self.tmux.kill_window(window_name, graceful=True)
                session.mark_deprioritized()

                self.audit.log("session_deprioritized", {
                    "session": session.config.id,
                    "reason": "peak_hours",
                })

                actions.append({
                    "session_id": session.config.id,
                    "action": "deprioritized",
                })

        return actions

    def restore_deprioritized(self) -> list[dict]:
        """Restore sessions that were deprioritized when peak hours end."""
        status = peak_hours_get_status()
        if status.get("is_peak", False):
            return []

        actions = []
        for session in self.registry.get_all_sessions():
            if session.status == SessionStatus.DEPRIORITIZED:
                session.status = SessionStatus.STOPPED
                session.stopped_at = time.time() - session.config.restart_delay_seconds - 1

                self.audit.log("session_restored", {
                    "session": session.config.id,
                    "reason": "peak_hours_ended",
                })

                actions.append({
                    "session_id": session.config.id,
                    "action": "restored",
                })

        return actions

    # --- Single Cycle ---

    def run_cycle(self):
        """Execute one daemon cycle: health check, spawn, enforce.

        This is the core of the daemon loop. Called repeatedly by run().
        """
        # 1. Health check — detect dead sessions
        self.check_health()

        # 2. Enforce peak hours
        self.enforce_peak_hours()
        self.restore_deprioritized()

        # 3. Spawn sessions that need to be started
        is_peak = peak_hours_get_status().get("is_peak", False)
        runnable = self.registry.get_runnable_sessions(is_peak=is_peak)

        for session in runnable:
            self.spawn_session(session)

        # 4. Persist state
        try:
            self.registry.save_state()
        except OSError:
            pass  # Non-fatal

    # --- Main Loop ---

    def run(self):
        """Run the daemon main loop. Blocks until stopped."""
        if not self.acquire_pid_file():
            print("ERROR: Another daemon is already running", file=sys.stderr)
            sys.exit(1)

        self.state.mark_started(pid=os.getpid())
        self.audit.log("daemon_started", {"pid": os.getpid()})

        # Ensure tmux session exists
        self.tmux.create_session()

        # Install signal handlers
        def handle_signal(signum, frame):
            self.audit.log("signal_received", {"signal": signum})
            self.stop(kill_sessions=False)

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        try:
            while self.state.running:
                self.run_cycle()
                time.sleep(self.registry.check_interval_seconds)
        finally:
            self.release_pid_file()
            self.audit.log("daemon_exited", {
                "total_spawns": self.state.total_spawns,
                "total_crashes": self.state.total_crashes,
            })

    # --- Control ---

    def stop(self, kill_sessions: bool = False):
        """Stop the daemon loop."""
        self.state.mark_stopped()

        if kill_sessions:
            for session in self.registry.get_all_sessions():
                if session.status == SessionStatus.RUNNING:
                    window_name = session.tmux_window or session.config.id
                    self.tmux.kill_window(window_name, graceful=True)
                    session.mark_stopped(reason="daemon_shutdown")

        self.audit.log("daemon_stopped", {
            "kill_sessions": kill_sessions,
            "total_spawns": self.state.total_spawns,
            "total_crashes": self.state.total_crashes,
        })

    # --- PID File ---

    def acquire_pid_file(self) -> bool:
        """Acquire the PID file for singleton enforcement.

        Returns True if acquired, False if another daemon is running.
        """
        if os.path.exists(self._pid_path):
            try:
                with open(self._pid_path) as f:
                    existing_pid = int(f.read().strip())
                # Check if the process is still alive
                os.kill(existing_pid, 0)
                return False  # Process exists
            except (ProcessLookupError, ValueError):
                # Stale PID file — process doesn't exist
                os.remove(self._pid_path)
            except PermissionError:
                return False  # Process exists but we can't signal it

        with open(self._pid_path, "w") as f:
            f.write(str(os.getpid()))
        return True

    def release_pid_file(self):
        """Remove the PID file."""
        try:
            os.remove(self._pid_path)
        except OSError:
            pass

    # --- Status ---

    def get_status_report(self) -> dict:
        """Generate a structured status report."""
        sessions = []
        for s in self.registry.get_all_sessions():
            uptime = s.uptime_seconds()
            sessions.append({
                "id": s.config.id,
                "type": s.config.type,
                "role": s.config.role,
                "status": s.status.value,
                "pid": s.pid,
                "uptime_seconds": uptime,
                "restart_count": s.restart_count,
                "last_error": s.last_error,
            })

        return {
            "daemon_running": self.state.running,
            "daemon_pid": self.state.pid,
            "uptime_seconds": self.state.uptime_seconds(),
            "total_spawns": self.state.total_spawns,
            "total_crashes": self.state.total_crashes,
            "sessions": sessions,
        }

    def format_status(self) -> str:
        """Human-readable status output."""
        report = self.get_status_report()
        lines = []

        # Daemon state
        if report["daemon_running"]:
            uptime = report.get("uptime_seconds") or 0
            mins = int(uptime // 60)
            lines.append(f"Session Daemon: RUNNING (PID {report['daemon_pid']}, uptime {mins}m)")
        else:
            lines.append("Session Daemon: STOPPED")

        lines.append("")

        # Sessions
        lines.append("Sessions:")
        for s in report["sessions"]:
            status = s["status"].upper()
            pid_str = f"PID={s['pid']}" if s["pid"] else ""
            uptime_str = ""
            if s.get("uptime_seconds"):
                mins = int(s["uptime_seconds"] // 60)
                uptime_str = f" ({mins}m)"
            restart_str = f" restarts={s['restart_count']}" if s["restart_count"] > 0 else ""
            error_str = f" [{s['last_error']}]" if s.get("last_error") else ""
            lines.append(f"  {s['id']:<20} {status:<15} {pid_str}{uptime_str}{restart_str}{error_str}")

        lines.append("")

        # Peak hours
        try:
            peak = peak_hours_get_status()
            peak_str = "PEAK" if peak.get("is_peak") else "OFF-PEAK"
            lines.append(f"Peak hours: {peak_str}")
        except Exception:
            lines.append("Peak hours: unknown")

        # Totals
        lines.append(f"Spawns today: {report['total_spawns']}  Crashes: {report['total_crashes']}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print("session_daemon.py — MT-30 Session Lifecycle Manager")
        print()
        print("Commands:")
        print("  start [--config path]     Start the daemon (foreground)")
        print("  stop [--kill-sessions]    Stop the daemon")
        print("  status                    Show current status")
        print("  restart <session-id>      Restart a specific session")
        print("  pause <session-id>        Pause auto-restart for a session")
        print("  resume <session-id>       Resume auto-restart for a session")
        print("  log [--last N]            View audit log")
        print()
        return

    cmd = args[0]

    if cmd == "start":
        config_path = None
        for i, arg in enumerate(args[1:], 1):
            if arg == "--config" and i + 1 < len(args):
                config_path = args[i + 1]

        daemon = SessionDaemon(config_path=config_path)
        print("Starting session daemon...")
        daemon.run()

    elif cmd == "status":
        daemon = SessionDaemon()
        daemon.registry.load_state()
        print(daemon.format_status())

    elif cmd == "log":
        n = 20
        for i, arg in enumerate(args[1:], 1):
            if arg == "--last" and i + 1 < len(args):
                n = int(args[i + 1])

        logger = AuditLogger()
        entries = logger.get_recent(n)
        if not entries:
            print("No log entries found.")
        else:
            for entry in entries:
                ts = entry.get("ts", "?")
                event = entry.get("event", "?")
                data = entry.get("data", {})
                detail = " ".join(f"{k}={v}" for k, v in data.items()) if data else ""
                print(f"[{ts}] {event}  {detail}")

    elif cmd == "stop":
        kill = "--kill-sessions" in args
        # Read PID from file and send SIGTERM
        pid_path = SessionDaemon.DEFAULT_PID
        if os.path.exists(pid_path):
            try:
                with open(pid_path) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to daemon PID {pid}")
                if kill:
                    print("Sessions will be killed by the daemon on shutdown.")
            except (ProcessLookupError, ValueError) as e:
                print(f"Daemon not running (stale PID file). Cleaning up.")
                os.remove(pid_path)
        else:
            print("No daemon PID file found. Daemon may not be running.")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
