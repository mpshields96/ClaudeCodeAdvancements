#!/usr/bin/env python3
"""
tmux_manager.py — Tmux session and window management for MT-30 Session Daemon.

Creates, monitors, and controls tmux windows for managed Claude Code sessions.
Each managed session runs in a named window within a single tmux session.

Usage:
    from tmux_manager import TmuxManager
    mgr = TmuxManager("cca-workspace")
    mgr.create_window("cca-desktop", "claude /cca-init", env={"CCA_CHAT_ID": "desktop"})
    print(mgr.is_alive("cca-desktop"))
    mgr.kill_window("cca-desktop")

CLI:
    python3 tmux_manager.py status                    # Show workspace status
    python3 tmux_manager.py create <name> <command>   # Create a window
    python3 tmux_manager.py kill <name>               # Kill a window
    python3 tmux_manager.py capture <name> [lines]    # Capture pane output

Stdlib only. No external dependencies.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


class TmuxError(Exception):
    """Raised for tmux operation failures."""
    pass


@dataclass
class WindowInfo:
    """Information about a tmux window/pane."""
    name: str
    pane_pid: Optional[int]
    pane_dead: bool
    window_index: int
    active: bool


class TmuxManager:
    """Manages a tmux session with named windows for Claude Code sessions."""

    def __init__(self, session_name: str = "cca-workspace"):
        self.session_name = session_name
        self._tmux_path = shutil.which("tmux")

    def is_tmux_available(self) -> bool:
        """Check if tmux is installed and accessible."""
        return self._tmux_path is not None

    def _run_tmux(self, args: list[str], check: bool = True,
                  capture: bool = True) -> subprocess.CompletedProcess:
        """Run a tmux command and return the result."""
        if not self.is_tmux_available():
            raise TmuxError("tmux is not installed or not in PATH")

        cmd = ["tmux"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=10,
            )
            if check and result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else ""
                raise TmuxError(f"tmux {' '.join(args)} failed: {stderr}")
            return result
        except subprocess.TimeoutExpired:
            raise TmuxError(f"tmux {' '.join(args)} timed out")
        except FileNotFoundError:
            raise TmuxError("tmux binary not found")

    def session_exists(self) -> bool:
        """Check if the managed tmux session exists."""
        result = self._run_tmux(
            ["has-session", "-t", self.session_name],
            check=False
        )
        return result.returncode == 0

    def create_session(self) -> bool:
        """Create the managed tmux session if it doesn't exist.

        Creates with a 'daemon' window as the initial window.
        Returns True if created, False if already existed.
        """
        if self.session_exists():
            return False

        self._run_tmux([
            "new-session", "-d",
            "-s", self.session_name,
            "-n", "daemon",
        ])
        return True

    def destroy_session(self, force: bool = False) -> bool:
        """Destroy the entire tmux session.

        Args:
            force: If True, kill even if windows are still running.
                   If False, only kill if no managed windows remain.

        Returns True if destroyed, False if not.
        """
        if not self.session_exists():
            return False

        if not force:
            windows = self.list_windows()
            # Don't destroy if non-daemon windows exist
            active = [w for w in windows if w.name != "daemon"]
            if active:
                raise TmuxError(
                    f"Cannot destroy session with {len(active)} active windows. "
                    "Use force=True to override."
                )

        self._run_tmux(["kill-session", "-t", self.session_name])
        return True

    def window_exists(self, window_name: str) -> bool:
        """Check if a named window exists in the session."""
        if not self.session_exists():
            return False

        result = self._run_tmux(
            ["list-windows", "-t", self.session_name, "-F", "#{window_name}"],
            check=False
        )
        if result.returncode != 0:
            return False

        names = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return window_name in names

    def create_window(self, window_name: str, command: str,
                      env: Optional[dict] = None,
                      cwd: Optional[str] = None) -> int:
        """Create a new tmux window and run a command in it.

        Args:
            window_name: Name for the tmux window.
            command: Shell command to execute.
            env: Environment variables to set.
            cwd: Working directory for the command.

        Returns:
            PID of the pane process.

        Raises:
            TmuxError if window already exists or creation fails.
        """
        if not self.session_exists():
            self.create_session()

        if self.window_exists(window_name):
            raise TmuxError(f"Window '{window_name}' already exists")

        # Build the command with env vars and ANTHROPIC_API_KEY unset
        # SAFETY: Always unset ANTHROPIC_API_KEY to use Max subscription
        parts = ["unset ANTHROPIC_API_KEY"]

        if env:
            for k, v in env.items():
                # Sanitize: only allow alphanumeric + underscore in names
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
                    raise TmuxError(f"Invalid env var name: {k}")
                # Escape single quotes in values
                safe_v = str(v).replace("'", "'\\''")
                parts.append(f"export {k}='{safe_v}'")

        if cwd:
            safe_cwd = cwd.replace("'", "'\\''")
            parts.append(f"cd '{safe_cwd}'")

        parts.append(command)
        full_command = " && ".join(parts)

        # Create the window
        create_args = [
            "new-window",
            "-t", self.session_name,
            "-n", window_name,
        ]
        # Note: tmux new-window doesn't support -c with shell command well,
        # so we handle cwd in the command itself
        create_args.append(full_command)

        self._run_tmux(create_args)

        # Get the PID of the new pane
        pid = self.get_pane_pid(window_name)
        return pid if pid else 0

    def get_pane_pid(self, window_name: str) -> Optional[int]:
        """Get the PID of the process running in a window's pane."""
        if not self.window_exists(window_name):
            return None

        target = f"{self.session_name}:{window_name}"
        result = self._run_tmux(
            ["list-panes", "-t", target, "-F", "#{pane_pid}"],
            check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            return int(result.stdout.strip().split("\n")[0])
        except (ValueError, IndexError):
            return None

    def is_alive(self, window_name: str) -> bool:
        """Check if the process in a window is still running."""
        if not self.window_exists(window_name):
            return False

        target = f"{self.session_name}:{window_name}"
        result = self._run_tmux(
            ["list-panes", "-t", target, "-F", "#{pane_dead}"],
            check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False

        dead_flag = result.stdout.strip().split("\n")[0]
        return dead_flag == "0"

    def kill_window(self, window_name: str, graceful: bool = True) -> bool:
        """Kill a tmux window.

        Args:
            window_name: Name of the window to kill.
            graceful: If True, send SIGTERM first, then SIGKILL after timeout.
                      If False, send SIGKILL immediately.

        Returns True if killed, False if window didn't exist.
        """
        if not self.window_exists(window_name):
            return False

        target = f"{self.session_name}:{window_name}"

        if graceful:
            # Send Ctrl-C first (SIGINT)
            self._run_tmux(
                ["send-keys", "-t", target, "C-c", ""],
                check=False
            )
            # Give it a moment, then check if still alive
            # (In production, the daemon loop handles the wait)

        # Kill the window
        self._run_tmux(["kill-window", "-t", target], check=False)
        return True

    def capture_pane(self, window_name: str, lines: int = 20) -> Optional[str]:
        """Capture recent output from a window's pane.

        Args:
            window_name: Name of the window.
            lines: Number of lines to capture from the end.

        Returns:
            Captured text, or None if window doesn't exist.
        """
        if not self.window_exists(window_name):
            return None

        target = f"{self.session_name}:{window_name}"
        start_line = -lines

        result = self._run_tmux(
            ["capture-pane", "-t", target, "-p", "-S", str(start_line)],
            check=False
        )
        if result.returncode != 0:
            return None

        return result.stdout

    def list_windows(self) -> list[WindowInfo]:
        """List all windows in the managed session."""
        if not self.session_exists():
            return []

        result = self._run_tmux(
            ["list-windows", "-t", self.session_name,
             "-F", "#{window_name}\t#{pane_pid}\t#{pane_dead}\t#{window_index}\t#{window_active}"],
            check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        windows = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            try:
                windows.append(WindowInfo(
                    name=parts[0],
                    pane_pid=int(parts[1]) if parts[1] else None,
                    pane_dead=parts[2] == "1",
                    window_index=int(parts[3]),
                    active=parts[4] == "1",
                ))
            except (ValueError, IndexError):
                continue

        return windows

    def send_keys(self, window_name: str, keys: str) -> bool:
        """Send keystrokes to a window's pane.

        Args:
            window_name: Target window.
            keys: Keys to send (tmux key syntax).

        Returns True if sent, False if window doesn't exist.
        """
        if not self.window_exists(window_name):
            return False

        target = f"{self.session_name}:{window_name}"
        self._run_tmux(["send-keys", "-t", target, keys, "Enter"], check=False)
        return True

    def has_wrap_marker(self, window_name: str, marker: str = "SESSION_WRAPPED") -> bool:
        """Check if recent pane output contains a wrap marker.

        Used to detect clean session wraps vs crashes.
        """
        output = self.capture_pane(window_name, lines=30)
        if output is None:
            return False
        return marker in output

    def get_exit_code(self, window_name: str) -> Optional[int]:
        """Get the exit code of the process in a dead pane.

        Only meaningful when is_alive() returns False.
        Returns None if window doesn't exist or pane is still alive.
        """
        if not self.window_exists(window_name):
            return None

        if self.is_alive(window_name):
            return None

        # tmux stores exit status
        target = f"{self.session_name}:{window_name}"
        result = self._run_tmux(
            ["list-panes", "-t", target, "-F", "#{pane_dead_status}"],
            check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            return int(result.stdout.strip().split("\n")[0])
        except (ValueError, IndexError):
            return None

    def summary(self) -> str:
        """Human-readable summary of the workspace."""
        if not self.session_exists():
            return f"Tmux session '{self.session_name}' does not exist"

        windows = self.list_windows()
        lines = [f"Tmux Workspace: {self.session_name} ({len(windows)} windows)"]
        lines.append("-" * 50)

        for w in windows:
            alive = "ALIVE" if not w.pane_dead else "DEAD"
            pid_str = f"PID={w.pane_pid}" if w.pane_pid else "no-pid"
            active = " *" if w.active else ""
            lines.append(f"  [{w.window_index}] {w.name:<20} {alive:<6} {pid_str}{active}")

        return "\n".join(lines)


def main():
    args = sys.argv[1:]

    if not args or args[0] == "help":
        print("Usage:")
        print("  python3 tmux_manager.py status [session-name]")
        print("  python3 tmux_manager.py create <window-name> <command>")
        print("  python3 tmux_manager.py kill <window-name>")
        print("  python3 tmux_manager.py capture <window-name> [lines]")
        return

    session_name = "cca-workspace"
    cmd = args[0]

    mgr = TmuxManager(session_name)

    if not mgr.is_tmux_available():
        print("ERROR: tmux is not installed", file=sys.stderr)
        sys.exit(1)

    if cmd == "status":
        if len(args) > 1:
            mgr = TmuxManager(args[1])
        print(mgr.summary())

    elif cmd == "create":
        if len(args) < 3:
            print("ERROR: create requires <window-name> <command>", file=sys.stderr)
            sys.exit(1)
        try:
            pid = mgr.create_window(args[1], " ".join(args[2:]))
            print(f"Created window '{args[1]}' with PID {pid}")
        except TmuxError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif cmd == "kill":
        if len(args) < 2:
            print("ERROR: kill requires <window-name>", file=sys.stderr)
            sys.exit(1)
        if mgr.kill_window(args[1]):
            print(f"Killed window '{args[1]}'")
        else:
            print(f"Window '{args[1]}' not found")

    elif cmd == "capture":
        if len(args) < 2:
            print("ERROR: capture requires <window-name>", file=sys.stderr)
            sys.exit(1)
        lines = int(args[2]) if len(args) > 2 else 20
        output = mgr.capture_pane(args[1], lines)
        if output is not None:
            print(output)
        else:
            print(f"Window '{args[1]}' not found")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
