#!/usr/bin/env python3
"""
session_registry.py — Session configuration and state tracking for MT-30 Session Daemon.

Manages the registry of intended sessions (what SHOULD be running), their configs,
and runtime state (PIDs, restart counts, current status).

The registry is a JSON config file that defines sessions. Runtime state is tracked
in-memory with periodic persistence to a state file.

Usage:
    from session_registry import SessionRegistry
    registry = SessionRegistry("/path/to/config.json")
    for session in registry.get_runnable():
        print(session.id, session.command)

CLI:
    python3 session_registry.py status              # Show all sessions
    python3 session_registry.py validate config.json # Validate a config file

Stdlib only. No external dependencies.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SessionStatus(Enum):
    """Runtime status of a managed session."""
    PENDING = "pending"           # Configured but not yet started
    RUNNING = "running"           # Process is alive
    STOPPED = "stopped"           # Cleanly wrapped / user-paused
    CRASHED = "crashed"           # Died unexpectedly
    FAILED = "failed"             # Exceeded max restart count
    PAUSED = "paused"             # Auto-restart disabled by user
    DEPRIORITIZED = "deprioritized"  # Paused due to peak hours


@dataclass
class SessionConfig:
    """Configuration for a single managed session."""
    id: str
    type: str                        # "cca" or "kalshi"
    role: str                        # "desktop", "main", "research", "cli1", "cli2"
    command: str                     # Shell command to launch
    auto_restart: bool = True
    restart_delay_seconds: int = 30
    env: dict = field(default_factory=dict)
    cwd: Optional[str] = None
    priority: int = 99              # Lower = higher priority


@dataclass
class SessionState:
    """Runtime state for a single managed session."""
    config: SessionConfig
    status: SessionStatus = SessionStatus.PENDING
    pid: Optional[int] = None
    tmux_window: Optional[str] = None
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    restart_count: int = 0
    restart_timestamps: list = field(default_factory=list)
    last_error: Optional[str] = None

    def uptime_seconds(self) -> Optional[float]:
        """Return uptime in seconds if running."""
        if self.started_at and self.status == SessionStatus.RUNNING:
            return time.time() - self.started_at
        return None

    def can_restart(self, max_restarts_per_hour: int = 5) -> bool:
        """Check if restart is allowed (not exceeded hourly limit)."""
        if not self.config.auto_restart:
            return False
        if self.status in (SessionStatus.FAILED, SessionStatus.PAUSED):
            return False
        now = time.time()
        hour_ago = now - 3600
        recent = [t for t in self.restart_timestamps if t > hour_ago]
        return len(recent) < max_restarts_per_hour

    def record_restart(self):
        """Record a restart event."""
        self.restart_count += 1
        self.restart_timestamps.append(time.time())

    def mark_running(self, pid: int, tmux_window: str):
        """Transition to RUNNING state."""
        self.status = SessionStatus.RUNNING
        self.pid = pid
        self.tmux_window = tmux_window
        self.started_at = time.time()
        self.stopped_at = None
        self.last_error = None

    def mark_stopped(self, reason: str = "clean_wrap"):
        """Transition to STOPPED state."""
        self.status = SessionStatus.STOPPED
        self.stopped_at = time.time()
        self.pid = None
        self.last_error = reason

    def mark_crashed(self, error: str = "process_died"):
        """Transition to CRASHED state."""
        self.status = SessionStatus.CRASHED
        self.stopped_at = time.time()
        self.pid = None
        self.last_error = error

    def mark_failed(self, reason: str = "max_restarts_exceeded"):
        """Transition to FAILED state (no more auto-restarts)."""
        self.status = SessionStatus.FAILED
        self.stopped_at = time.time()
        self.pid = None
        self.last_error = reason

    def mark_paused(self):
        """User-initiated pause of auto-restart."""
        self.status = SessionStatus.PAUSED
        self.stopped_at = time.time()

    def mark_deprioritized(self):
        """Peak-hours deprioritization."""
        self.status = SessionStatus.DEPRIORITIZED
        self.stopped_at = time.time()

    def to_dict(self) -> dict:
        """Serialize state for persistence."""
        return {
            "session_id": self.config.id,
            "status": self.status.value,
            "pid": self.pid,
            "tmux_window": self.tmux_window,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "restart_count": self.restart_count,
            "restart_timestamps": self.restart_timestamps,
            "last_error": self.last_error,
        }


class RegistryError(Exception):
    """Raised for registry configuration errors."""
    pass


class SessionRegistry:
    """Manages session configuration and runtime state."""

    DEFAULT_CONFIG = {
        "version": 1,
        "max_total_chats": 3,
        "max_restarts_per_hour": 5,
        "check_interval_seconds": 60,
        "sessions": [],
        "peak_hours": {
            "max_chats": 2,
            "deprioritize": []
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """Load registry from config file or use defaults."""
        self._config_path = config_path
        self._raw_config = dict(self.DEFAULT_CONFIG)
        self._sessions: dict[str, SessionState] = {}
        self._state_path: Optional[str] = None

        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
        elif config_path:
            raise RegistryError(f"Config file not found: {config_path}")

    def _load_config(self, path: str):
        """Load and validate config from JSON file."""
        try:
            with open(path, 'r') as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise RegistryError(f"Invalid JSON in config: {e}")

        errors = self.validate_config(raw)
        if errors:
            raise RegistryError(f"Config validation failed: {'; '.join(errors)}")

        self._raw_config.update(raw)

        # Build session configs
        for s in raw.get("sessions", []):
            config = SessionConfig(
                id=s["id"],
                type=s.get("type", "cca"),
                role=s.get("role", "default"),
                command=s["command"],
                auto_restart=s.get("auto_restart", True),
                restart_delay_seconds=s.get("restart_delay_seconds", 30),
                env=s.get("env", {}),
                cwd=s.get("cwd"),
                priority=s.get("priority", 99),
            )
            self._sessions[config.id] = SessionState(config=config)

    @staticmethod
    def validate_config(raw: dict) -> list[str]:
        """Validate a config dict, returning a list of error strings."""
        errors = []

        if not isinstance(raw, dict):
            return ["Config must be a JSON object"]

        if "version" not in raw:
            errors.append("Missing 'version' field")
        elif raw["version"] != 1:
            errors.append(f"Unsupported version: {raw['version']} (expected 1)")

        max_chats = raw.get("max_total_chats", 3)
        if not isinstance(max_chats, int) or max_chats < 1:
            errors.append(f"max_total_chats must be a positive integer, got {max_chats}")
        if isinstance(max_chats, int) and max_chats > 5:
            errors.append(f"max_total_chats={max_chats} exceeds safety limit of 5")

        sessions = raw.get("sessions", [])
        if not isinstance(sessions, list):
            errors.append("'sessions' must be an array")
            return errors

        seen_ids = set()
        seen_priorities = set()
        for i, s in enumerate(sessions):
            if not isinstance(s, dict):
                errors.append(f"Session {i} must be an object")
                continue

            if "id" not in s:
                errors.append(f"Session {i} missing 'id'")
            elif s["id"] in seen_ids:
                errors.append(f"Duplicate session id: '{s['id']}'")
            else:
                seen_ids.add(s["id"])

            if "command" not in s:
                errors.append(f"Session {i} missing 'command'")

            priority = s.get("priority", 99)
            if priority in seen_priorities:
                errors.append(f"Duplicate priority {priority} in session '{s.get('id', i)}'")
            seen_priorities.add(priority)

            delay = s.get("restart_delay_seconds", 30)
            if not isinstance(delay, (int, float)) or delay < 0:
                errors.append(f"Session '{s.get('id', i)}' has invalid restart_delay_seconds: {delay}")
            if isinstance(delay, (int, float)) and delay < 10:
                errors.append(f"Session '{s.get('id', i)}' restart_delay_seconds={delay} too low (min 10)")

            if "env" in s and not isinstance(s["env"], dict):
                errors.append(f"Session '{s.get('id', i)}' env must be an object")

        if len(sessions) > max_chats:
            errors.append(f"{len(sessions)} sessions configured but max_total_chats={max_chats}")

        peak = raw.get("peak_hours", {})
        if isinstance(peak, dict):
            peak_max = peak.get("max_chats", 2)
            if isinstance(peak_max, int) and isinstance(max_chats, int) and peak_max > max_chats:
                errors.append(f"peak_hours.max_chats={peak_max} exceeds max_total_chats={max_chats}")

            depri = peak.get("deprioritize", [])
            if isinstance(depri, list):
                for d in depri:
                    if d not in seen_ids:
                        errors.append(f"peak_hours.deprioritize references unknown session: '{d}'")

        return errors

    @property
    def max_total_chats(self) -> int:
        return self._raw_config.get("max_total_chats", 3)

    @property
    def max_restarts_per_hour(self) -> int:
        return self._raw_config.get("max_restarts_per_hour", 5)

    @property
    def check_interval_seconds(self) -> int:
        return self._raw_config.get("check_interval_seconds", 60)

    @property
    def peak_max_chats(self) -> int:
        return self._raw_config.get("peak_hours", {}).get("max_chats", 2)

    @property
    def peak_deprioritize(self) -> list[str]:
        return self._raw_config.get("peak_hours", {}).get("deprioritize", [])

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session state by ID."""
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[SessionState]:
        """Get all sessions sorted by priority."""
        return sorted(self._sessions.values(), key=lambda s: s.config.priority)

    def get_running_sessions(self) -> list[SessionState]:
        """Get currently running sessions."""
        return [s for s in self._sessions.values() if s.status == SessionStatus.RUNNING]

    def get_runnable_sessions(self, is_peak: bool = False) -> list[SessionState]:
        """Get sessions that should be started, respecting limits."""
        max_chats = self.peak_max_chats if is_peak else self.max_total_chats
        running_count = len(self.get_running_sessions())
        available_slots = max_chats - running_count

        if available_slots <= 0:
            return []

        # Sessions that need to be started
        candidates = []
        for s in self.get_all_sessions():
            if s.status in (SessionStatus.PENDING, SessionStatus.CRASHED, SessionStatus.STOPPED):
                if s.config.auto_restart or s.status == SessionStatus.PENDING:
                    if is_peak and s.config.id in self.peak_deprioritize:
                        continue
                    if s.can_restart(self.max_restarts_per_hour):
                        candidates.append(s)

        return candidates[:available_slots]

    def get_deprioritizable(self, is_peak: bool = False) -> list[SessionState]:
        """Get running sessions that should be stopped during peak hours."""
        if not is_peak:
            return []
        running = self.get_running_sessions()
        return [s for s in running if s.config.id in self.peak_deprioritize]

    def add_session(self, config: SessionConfig) -> SessionState:
        """Add a session config dynamically."""
        if config.id in self._sessions:
            raise RegistryError(f"Session '{config.id}' already exists")
        state = SessionState(config=config)
        self._sessions[config.id] = state
        return state

    def remove_session(self, session_id: str) -> bool:
        """Remove a session (only if not running)."""
        state = self._sessions.get(session_id)
        if not state:
            return False
        if state.status == SessionStatus.RUNNING:
            raise RegistryError(f"Cannot remove running session '{session_id}'")
        del self._sessions[session_id]
        return True

    def save_state(self, path: Optional[str] = None) -> str:
        """Persist runtime state to JSON file. Returns path written."""
        path = path or self._state_path or os.path.expanduser("~/.cca-session-registry-state.json")
        self._state_path = path

        state = {
            "saved_at": time.time(),
            "sessions": {sid: s.to_dict() for sid, s in self._sessions.items()}
        }

        # Atomic write
        tmp_path = path + ".tmp"
        with open(tmp_path, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, path)

        return path

    def load_state(self, path: Optional[str] = None) -> bool:
        """Restore runtime state from file. Returns True if loaded."""
        path = path or self._state_path or os.path.expanduser("~/.cca-session-registry-state.json")

        if not os.path.exists(path):
            return False

        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        for sid, sdata in data.get("sessions", {}).items():
            if sid in self._sessions:
                state = self._sessions[sid]
                state.status = SessionStatus(sdata.get("status", "pending"))
                state.pid = sdata.get("pid")
                state.tmux_window = sdata.get("tmux_window")
                state.started_at = sdata.get("started_at")
                state.stopped_at = sdata.get("stopped_at")
                state.restart_count = sdata.get("restart_count", 0)
                state.restart_timestamps = sdata.get("restart_timestamps", [])
                state.last_error = sdata.get("last_error")

        self._state_path = path
        return True

    def summary(self) -> str:
        """Human-readable summary of all sessions."""
        lines = [f"Session Registry ({len(self._sessions)} sessions, max {self.max_total_chats})"]
        lines.append("-" * 60)

        for s in self.get_all_sessions():
            status_str = s.status.value.upper()
            uptime = s.uptime_seconds()
            uptime_str = ""
            if uptime is not None:
                mins = int(uptime // 60)
                uptime_str = f" ({mins}m uptime)"

            pid_str = f" PID={s.pid}" if s.pid else ""
            restart_str = f" restarts={s.restart_count}" if s.restart_count > 0 else ""
            error_str = f" [{s.last_error}]" if s.last_error else ""

            lines.append(f"  {s.config.id:<20} {status_str:<15}{pid_str}{uptime_str}{restart_str}{error_str}")

        running = len(self.get_running_sessions())
        lines.append(f"\nRunning: {running}/{self.max_total_chats}")
        return "\n".join(lines)


def main():
    args = sys.argv[1:]

    if not args or args[0] == "help":
        print("Usage:")
        print("  python3 session_registry.py status [config.json]")
        print("  python3 session_registry.py validate config.json")
        return

    cmd = args[0]

    if cmd == "validate":
        if len(args) < 2:
            print("ERROR: validate requires a config path", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args[1]) as f:
                raw = json.load(f)
            errors = SessionRegistry.validate_config(raw)
            if errors:
                print(f"INVALID ({len(errors)} errors):")
                for e in errors:
                    print(f"  - {e}")
                sys.exit(1)
            else:
                print(f"VALID: {len(raw.get('sessions', []))} sessions configured")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif cmd == "status":
        config_path = args[1] if len(args) > 1 else None
        try:
            registry = SessionRegistry(config_path)
            registry.load_state()
            print(registry.summary())
        except RegistryError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
