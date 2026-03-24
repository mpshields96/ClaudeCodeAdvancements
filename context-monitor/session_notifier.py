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
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

NTFY_BASE = "https://ntfy.sh"
DEFAULT_COOLDOWN_MINUTES = 30  # Matthew directive S144: reduce notification spam
COOLDOWN_STATE_FILE = os.path.expanduser("~/.cca-ntfy-cooldown.json")


# ── Cooldown mechanism (MT-35 Phase 3, S144 Matthew directive) ──────────────


def _get_cooldown_minutes() -> float:
    """Get cooldown from env or default. 0 = no cooldown."""
    try:
        return float(os.environ.get("CCA_NTFY_COOLDOWN_MIN", DEFAULT_COOLDOWN_MINUTES))
    except (ValueError, TypeError):
        return DEFAULT_COOLDOWN_MINUTES


def _check_cooldown(priority: str, state_file: str = None) -> bool:
    """Check if we're still in cooldown period.

    High priority messages always bypass cooldown.
    Returns True if send should proceed, False if in cooldown.
    """
    if state_file is None:
        state_file = COOLDOWN_STATE_FILE

    if priority == "high":
        return True  # Errors always get through

    cooldown_min = _get_cooldown_minutes()
    if cooldown_min <= 0:
        return True  # Cooldown disabled

    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
            last_sent = data.get("last_sent_ts", 0)
            elapsed_min = (time.time() - last_sent) / 60.0
            if elapsed_min < cooldown_min:
                return False  # Still in cooldown
    except (json.JSONDecodeError, OSError, TypeError):
        pass  # Fail open — send if state is corrupt

    return True


def _record_send(state_file: str = None) -> None:
    """Record that a notification was just sent."""
    if state_file is None:
        state_file = COOLDOWN_STATE_FILE
    try:
        os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
        with open(state_file, "w") as f:
            json.dump({"last_sent_ts": time.time()}, f)
    except OSError:
        pass  # Fail open


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

    Cooldown: Non-high-priority messages are rate-limited to one per
    CCA_NTFY_COOLDOWN_MIN minutes (default 30). High priority always sends.
    """
    if not _check_cooldown(priority):
        return False  # In cooldown, skip silently

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
            if resp.status == 200:
                _record_send()
                return True
            return False
    except (URLError, HTTPError, OSError):
        return False


# ── Loop health formatting (MT-35 Phase 3) ──────────────────────────────────


def format_loop_health_message(
    iteration: int,
    max_iterations: int,
    total_crashes: int,
    uptime_minutes: float,
    last_session_grade: str = None,
    test_suites_passing: int = None,
) -> dict:
    """Format a periodic loop health ping."""
    title = "CCA Loop Health"

    parts = [f"{iteration}/{max_iterations} iterations", f"{uptime_minutes:.0f}m uptime"]
    if total_crashes > 0:
        parts.append(f"{total_crashes} crashes")
    if last_session_grade:
        parts.append(f"Last: {last_session_grade}")
    if test_suites_passing is not None:
        parts.append(f"{test_suites_passing} suites OK")

    return {"title": title, "body": " | ".join(parts)}


def format_loop_stopped_message(
    reason: str,
    total_iterations: int,
    total_crashes: int,
    uptime_minutes: float,
) -> dict:
    """Format a loop-stopped notification."""
    title = "CCA Loop Stopped"

    parts = [
        f"{total_iterations} iterations",
        f"{uptime_minutes:.0f}m",
        f"{total_crashes} crashes",
        reason,
    ]

    return {"title": title, "body": " | ".join(parts)}


# ── High-level API ───────────────────────────────────────────────────────────


def notify_loop_health(
    iteration: int,
    max_iterations: int,
    total_crashes: int,
    uptime_minutes: float,
    last_session_grade: str = None,
    test_suites_passing: int = None,
) -> bool:
    """Send periodic loop health ping. Low priority to avoid buzzing."""
    msg = format_loop_health_message(
        iteration, max_iterations, total_crashes, uptime_minutes,
        last_session_grade, test_suites_passing,
    )
    return send_notification(msg["title"], msg["body"], priority="low")


def notify_loop_stopped(
    reason: str,
    total_iterations: int,
    total_crashes: int,
    uptime_minutes: float,
) -> bool:
    """Send loop-stopped notification. High priority if crash-related."""
    msg = format_loop_stopped_message(reason, total_iterations, total_crashes, uptime_minutes)
    priority = "high" if "crash" in reason.lower() else "default"
    return send_notification(msg["title"], msg["body"], priority=priority)


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

    # Loop health flags
    iteration = 0
    max_iter = 50
    crashes = 0
    uptime = 0.0
    iterations_total = 0
    reason = ""

    # Re-parse for loop flags
    j = 1
    while j < len(args):
        if args[j] == "--iteration" and j + 1 < len(args):
            iteration = int(args[j + 1])
            j += 2
        elif args[j] == "--max" and j + 1 < len(args):
            max_iter = int(args[j + 1])
            j += 2
        elif args[j] == "--crashes" and j + 1 < len(args):
            crashes = int(args[j + 1])
            j += 2
        elif args[j] == "--uptime" and j + 1 < len(args):
            uptime = float(args[j + 1])
            j += 2
        elif args[j] == "--iterations" and j + 1 < len(args):
            iterations_total = int(args[j + 1])
            j += 2
        elif args[j] == "--reason" and j + 1 < len(args):
            reason = args[j + 1]
            j += 2
        else:
            j += 1

    if cmd == "loop-health":
        result = notify_loop_health(
            iteration=iteration, max_iterations=max_iter,
            total_crashes=crashes, uptime_minutes=uptime,
        )
        if result:
            print(f"Loop health sent: {iteration}/{max_iter}")
        else:
            print("Notification not sent (no topic or network error)")

    elif cmd == "loop-stopped":
        result = notify_loop_stopped(
            reason=reason, total_iterations=iterations_total,
            total_crashes=crashes, uptime_minutes=uptime,
        )
        if result:
            print(f"Loop stopped sent: {reason}")
        else:
            print("Notification not sent (no topic or network error)")

    elif cmd == "wrap":
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
