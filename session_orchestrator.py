#!/usr/bin/env python3
"""
session_orchestrator.py — 3-chat auto-launch decision logic.

Detects which CCA sessions are running (desktop, worker, Kalshi) and decides
what needs to be launched to reach the target session mode.

Usage:
    python3 session_orchestrator.py status              # Show running sessions
    python3 session_orchestrator.py plan [--mode 3chat]  # Show what would be launched
    python3 session_orchestrator.py launch [--mode 3chat] [--task "worker task"]  # Execute launches
    python3 session_orchestrator.py set-mode 3chat      # Save default target mode

Designed for /cca-auto-desktop coordination round integration.
Stdlib only. No external dependencies.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

CCA_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
PREF_FILE = os.path.join(CCA_DIR, ".session_preference.json")


class SessionMode(Enum):
    SOLO = "solo"
    TWO_CHAT = "2chat"
    THREE_CHAT = "3chat"


@dataclass
class SessionState:
    """Current state of running sessions."""
    desktop_running: bool = False
    worker_running: bool = False
    kalshi_running: bool = False

    @property
    def mode(self) -> SessionMode:
        if self.worker_running and self.kalshi_running:
            return SessionMode.THREE_CHAT
        if self.worker_running:
            return SessionMode.TWO_CHAT
        return SessionMode.SOLO


@dataclass
class LaunchDecision:
    """What to launch and whether it's blocked."""
    target: str  # "worker" or "kalshi"
    blocked: bool = False
    reason: str = ""


def detect_running_sessions(processes: list) -> SessionState:
    """Determine which sessions are running from a process list.

    Args:
        processes: List of dicts with keys: pid, chat_id, command.
                   Optional key: project (for Kalshi detection).

    Returns:
        SessionState with flags for each running session type.
    """
    state = SessionState()

    for proc in processes:
        chat_id = proc.get("chat_id")
        project = proc.get("project", "")

        if chat_id == "desktop":
            state.desktop_running = True
        elif chat_id in ("cli1", "cli2"):
            state.worker_running = True
        elif project and "polymarket-bot" in project:
            state.kalshi_running = True

    return state


def decide_launches(
    state: SessionState,
    target: SessionMode,
    is_peak: bool = False,
) -> List[LaunchDecision]:
    """Decide what sessions need launching to reach target mode.

    Args:
        state: Current running sessions.
        target: Desired session mode.
        is_peak: Whether we're in peak hours (blocks launches).

    Returns:
        List of LaunchDecision objects.
    """
    if not state.desktop_running:
        return []  # Can't launch helpers without desktop

    decisions = []

    # Worker needed for 2chat and 3chat
    if target in (SessionMode.TWO_CHAT, SessionMode.THREE_CHAT):
        if not state.worker_running:
            d = LaunchDecision(target="worker")
            if is_peak:
                d.blocked = True
                d.reason = "Peak hours — standard rate limits. Defer worker launch."
            decisions.append(d)

    # Kalshi needed for 3chat
    if target == SessionMode.THREE_CHAT:
        if not state.kalshi_running:
            d = LaunchDecision(target="kalshi")
            if is_peak:
                d.blocked = True
                d.reason = "Peak hours — standard rate limits. Defer Kalshi launch."
            decisions.append(d)

    return decisions


def build_launch_commands(
    decisions: List[LaunchDecision],
    worker_task: str = "",
) -> List[str]:
    """Convert launch decisions into shell commands.

    Args:
        decisions: List of non-blocked launch decisions.
        worker_task: Optional task to assign to worker at launch.

    Returns:
        List of shell command strings to execute.
    """
    commands = []

    for d in decisions:
        if d.blocked:
            continue

        if d.target == "worker":
            cmd = f"bash {CCA_DIR}/launch_worker.sh"
            if worker_task:
                cmd += f' "{worker_task}"'
            commands.append(cmd)
        elif d.target == "kalshi":
            commands.append(f"bash {CCA_DIR}/launch_kalshi.sh main")

    return commands


def save_session_preference(mode: SessionMode, path: str = PREF_FILE) -> None:
    """Persist target session mode."""
    with open(path, "w") as f:
        json.dump({"target_mode": mode.value}, f)


def load_session_preference(path: str = PREF_FILE) -> SessionMode:
    """Load saved target mode, defaulting to SOLO."""
    try:
        with open(path) as f:
            data = json.load(f)
        return SessionMode(data.get("target_mode", "solo"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return SessionMode.SOLO


def _get_live_state() -> SessionState:
    """Detect running sessions from live processes."""
    try:
        result = subprocess.run(
            ["ps", "axo", "pid,command"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return SessionState()

    processes = []
    for line in lines:
        line = line.strip()
        if "claude" not in line.lower():
            continue
        # Extract PID
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        cmd = parts[1]

        # Detect CCA chat ID from environment
        chat_id = None
        if "CCA_CHAT_ID=desktop" in cmd or "cca-auto-desktop" in cmd:
            chat_id = "desktop"
        elif "CCA_CHAT_ID=cli1" in cmd:
            chat_id = "cli1"
        elif "CCA_CHAT_ID=cli2" in cmd:
            chat_id = "cli2"
        elif "ClaudeCodeAdvancements" in cmd:
            chat_id = "desktop"  # Default CCA to desktop

        project = ""
        if "polymarket-bot" in cmd:
            project = "polymarket-bot"

        if chat_id or project:
            processes.append({
                "pid": pid,
                "chat_id": chat_id,
                "command": cmd,
                "project": project,
            })

    return detect_running_sessions(processes)


def _check_peak() -> bool:
    """Check if we're in peak hours."""
    try:
        result = subprocess.run(
            ["python3", os.path.join(CCA_DIR, "peak_hours.py"), "--check"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode != 0  # Non-zero = peak
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False  # Fail open


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print("session_orchestrator.py — 3-chat auto-launch decision logic")
        print()
        print("Commands:")
        print("  status                    Show running sessions")
        print("  plan [--mode MODE]        Show what would be launched")
        print("  launch [--mode MODE]      Execute launches")
        print("  set-mode MODE             Save default target mode (solo/2chat/3chat)")
        return

    cmd = args[0]

    if cmd == "status":
        state = _get_live_state()
        print(f"Desktop: {'RUNNING' if state.desktop_running else 'not running'}")
        print(f"Worker:  {'RUNNING' if state.worker_running else 'not running'}")
        print(f"Kalshi:  {'RUNNING' if state.kalshi_running else 'not running'}")
        print(f"Mode:    {state.mode.value}")

    elif cmd == "plan":
        mode_str = args[args.index("--mode") + 1] if "--mode" in args else None
        target = SessionMode(mode_str) if mode_str else load_session_preference()
        state = _get_live_state()
        is_peak = _check_peak()
        decisions = decide_launches(state, target, is_peak)

        print(f"Current: {state.mode.value} | Target: {target.value} | Peak: {is_peak}")
        if not decisions:
            print("No launches needed.")
        for d in decisions:
            status = "BLOCKED" if d.blocked else "READY"
            print(f"  {status}: Launch {d.target}" + (f" ({d.reason})" if d.reason else ""))

    elif cmd == "launch":
        mode_str = args[args.index("--mode") + 1] if "--mode" in args else None
        task = args[args.index("--task") + 1] if "--task" in args else ""
        target = SessionMode(mode_str) if mode_str else load_session_preference()
        state = _get_live_state()
        is_peak = _check_peak()
        decisions = decide_launches(state, target, is_peak)
        commands = build_launch_commands(decisions, worker_task=task)

        if not commands:
            blocked = [d for d in decisions if d.blocked]
            if blocked:
                print("Launches blocked:")
                for d in blocked:
                    print(f"  {d.target}: {d.reason}")
            else:
                print("All sessions already running. Nothing to launch.")
            return

        for c in commands:
            print(f"Executing: {c}")
            subprocess.run(c, shell=True, cwd=CCA_DIR)

    elif cmd == "set-mode":
        if len(args) < 2:
            print("Usage: set-mode solo|2chat|3chat")
            return
        mode = SessionMode(args[1])
        save_session_preference(mode)
        print(f"Default mode set to: {mode.value}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
