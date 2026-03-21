#!/usr/bin/env python3
"""
session_notifier.py — ntfy.sh push notifications for CCA session events.

Sends a notification to Matthew's iPhone when:
  - An autonomous session completes (wrap)
  - A critical error occurs mid-session

Reuses MOBILE_APPROVER_TOPIC from agent-guard's mobile_approver.py.
Fail-open: if ntfy.sh is unreachable or no topic is configured,
the notification silently fails — never blocks work.

Setup:
  export MOBILE_APPROVER_TOPIC=cc-yourname   (same topic as mobile_approver)

Usage as library:
    from session_notifier import notify_session_end, notify_session_error
    notify_session_end(tasks_completed=3, elapsed_minutes=47, session_id="S95")
    notify_session_error(error="Tests failing", task_name="MT-20")

Usage as CLI:
    python3 session_notifier.py wrap --tasks 3 --elapsed 47 --session S95
    python3 session_notifier.py wrap --auto [--pacer-state PATH]
    python3 session_notifier.py error --message "Tests failing" --task "MT-20"

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

NTFY_BASE = "https://ntfy.sh"


# ── Message formatting ───────────────────────────────────────────────────────


def format_wrap_message(
    tasks_completed: int,
    elapsed_minutes: float,
    session_id: str = None,
    grade: str = None,
) -> dict:
    """Format a session-complete notification message."""
    title = f"CCA {session_id} Complete" if session_id else "CCA Session Complete"

    parts = [f"{tasks_completed} tasks in {elapsed_minutes:.0f}m"]
    if grade:
        parts.append(f"Grade: {grade}")

    return {"title": title, "body": " | ".join(parts)}


def format_error_message(
    error: str,
    task_name: str = None,
) -> dict:
    """Format a critical error notification message."""
    title = "CCA Error"

    parts = []
    if task_name:
        parts.append(f"Task: {task_name}")
    # Truncate long errors
    truncated = error[:280] if len(error) > 280 else error
    parts.append(truncated)

    return {"title": title, "body": " | ".join(parts)}


# ── ntfy.sh sender ───────────────────────────────────────────────────────────


def send_notification(
    title: str,
    body: str,
    priority: str = "default",
) -> bool:
    """
    Send a one-way push notification via ntfy.sh.

    Returns True on success, False on any failure (fail-open).
    Reads topic from MOBILE_APPROVER_TOPIC env var.
    """
    topic = os.environ.get("MOBILE_APPROVER_TOPIC", "").strip()
    if not topic:
        return False

    url = f"{NTFY_BASE}/{quote(topic)}"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": "claude,checkered_flag",
        "Content-Type": "text/plain",
    }

    req = Request(url, data=body.encode(), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (URLError, HTTPError, OSError):
        return False


# ── High-level API ───────────────────────────────────────────────────────────


def notify_session_end(
    tasks_completed: int,
    elapsed_minutes: float,
    session_id: str = None,
    grade: str = None,
) -> bool:
    """Send session-complete notification. Returns True if sent."""
    msg = format_wrap_message(tasks_completed, elapsed_minutes, session_id, grade)
    return send_notification(msg["title"], msg["body"], priority="default")


def notify_session_error(
    error: str,
    task_name: str = None,
) -> bool:
    """Send critical error notification. Returns True if sent."""
    msg = format_error_message(error, task_name)
    return send_notification(msg["title"], msg["body"], priority="high")


# ── CLI ──────────────────────────────────────────────────────────────────────


def _read_pacer_state(path: str) -> dict:
    """Read session pacer state file and extract summary."""
    default_path = os.path.expanduser("~/.cca-session-pace.json")
    state_path = path or default_path

    if not os.path.exists(state_path):
        return {"tasks_completed": 0, "elapsed_minutes": 0}

    try:
        with open(state_path) as f:
            data = json.load(f)

        tasks = data.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("completed_at") is not None)

        started_at = data.get("started_at", "")
        if started_at:
            start = datetime.fromisoformat(started_at)
            now = datetime.now(timezone.utc)
            elapsed = (now - start).total_seconds() / 60.0
        else:
            elapsed = 0.0

        return {"tasks_completed": completed, "elapsed_minutes": elapsed}
    except (json.JSONDecodeError, OSError, ValueError):
        return {"tasks_completed": 0, "elapsed_minutes": 0}


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print(
            "Usage: python3 session_notifier.py <command> [options]\n"
            "\n"
            "Commands:\n"
            "  wrap    Send session-complete notification\n"
            "  error   Send critical error notification\n"
            "\n"
            "wrap options:\n"
            "  --tasks N          Tasks completed\n"
            "  --elapsed M        Elapsed minutes\n"
            "  --session ID       Session identifier (e.g. S95)\n"
            "  --grade G          Session grade (e.g. B+)\n"
            "  --auto             Read from session pacer state file\n"
            "  --pacer-state P    Path to pacer state file (with --auto)\n"
            "\n"
            "error options:\n"
            "  --message MSG      Error description\n"
            "  --task NAME        Task that failed"
        )
        return

    cmd = args[0]

    # Parse flags
    tasks = 0
    elapsed = 0.0
    session_id = None
    grade = None
    auto = False
    pacer_state = None
    message = None
    task_name = None

    i = 1
    while i < len(args):
        if args[i] == "--tasks" and i + 1 < len(args):
            tasks = int(args[i + 1])
            i += 2
        elif args[i] == "--elapsed" and i + 1 < len(args):
            elapsed = float(args[i + 1])
            i += 2
        elif args[i] == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        elif args[i] == "--grade" and i + 1 < len(args):
            grade = args[i + 1]
            i += 2
        elif args[i] == "--auto":
            auto = True
            i += 1
        elif args[i] == "--pacer-state" and i + 1 < len(args):
            pacer_state = args[i + 1]
            i += 2
        elif args[i] == "--message" and i + 1 < len(args):
            message = args[i + 1]
            i += 2
        elif args[i] == "--task" and i + 1 < len(args):
            task_name = args[i + 1]
            i += 2
        else:
            i += 1

    if cmd == "wrap":
        if auto:
            summary = _read_pacer_state(pacer_state)
            tasks = summary["tasks_completed"]
            elapsed = summary["elapsed_minutes"]

        result = notify_session_end(tasks, elapsed, session_id, grade)
        if result:
            print(f"Notification sent: {tasks} tasks, {elapsed:.0f}m")
        else:
            print("Notification not sent (no topic or network error)")

    elif cmd == "error":
        if not message:
            print("Error: --message is required")
            return
        result = notify_session_error(message, task_name)
        if result:
            print(f"Error notification sent: {message[:80]}")
        else:
            print("Notification not sent (no topic or network error)")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli_main()
