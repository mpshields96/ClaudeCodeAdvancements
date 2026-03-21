"""
worker_task_tracker.py — Detect workers who wrap without completing all assigned tasks.

Reads cca_internal_queue.jsonl and identifies sessions where tasks were assigned
to a worker but the worker sent fewer WRAP messages than tasks assigned.

Usage:
    python3 worker_task_tracker.py                    # uses default queue path
    python3 worker_task_tracker.py --path custom.jsonl
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_QUEUE_PATH = os.path.join(
    os.path.dirname(__file__), "cca_internal_queue.jsonl"
)

KNOWN_WORKERS = ("cli1", "cli2")


@dataclass
class WorkerSession:
    worker_id: str
    assigned_count: int = 0
    wrap_count: int = 0
    task_subjects: List[str] = field(default_factory=list)
    shutdown_received: bool = False
    session_index: int = 0

    @property
    def is_complete(self) -> bool:
        return self.wrap_count >= self.assigned_count

    @property
    def missing_tasks(self) -> List[str]:
        """Return tasks that appear incomplete (last N unmatched subjects)."""
        missing_count = self.assigned_count - self.wrap_count
        if missing_count <= 0:
            return []
        # Return the last N task subjects (most recently assigned = most likely incomplete)
        return self.task_subjects[-missing_count:]


def load_queue(path: str) -> List[dict]:
    """Load all messages from a JSONL queue file. Returns [] if file missing."""
    if not os.path.exists(path):
        return []
    messages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return messages


def _is_task_assignment(msg: dict, worker_id: str) -> bool:
    """True if this is a task assignment from desktop to the worker."""
    if msg.get("category") != "handoff":
        return False
    if msg.get("sender") != "desktop":
        return False
    if msg.get("target") != worker_id:
        return False
    subject = msg.get("subject", "")
    # Exclude SHUTDOWN messages and WRAP echo-backs
    if subject.upper().startswith("SHUTDOWN"):
        return False
    if subject.upper().startswith("WRAP"):
        return False
    return True


def _is_shutdown(msg: dict, worker_id: str) -> bool:
    """True if this is a SHUTDOWN signal to the worker."""
    return (
        msg.get("category") == "handoff"
        and msg.get("sender") == "desktop"
        and msg.get("target") == worker_id
        and msg.get("subject", "").upper().startswith("SHUTDOWN")
    )


def _is_wrap(msg: dict, worker_id: str) -> bool:
    """True if this is a WRAP completion message from the worker."""
    return (
        msg.get("category") == "handoff"
        and msg.get("sender") == worker_id
        and msg.get("target") == "desktop"
        and msg.get("subject", "").upper().startswith("WRAP")
    )


def parse_worker_sessions(messages: List[dict], worker_id: str) -> List[WorkerSession]:
    """
    Parse all sessions for a given worker from the message list.

    A session is a sequence of task assignments terminated by a SHUTDOWN message
    (or the end of the queue for the current active session).
    """
    sessions: List[WorkerSession] = []
    current: Optional[WorkerSession] = None
    session_index = 0

    for msg in messages:
        if _is_shutdown(msg, worker_id):
            if current is not None:
                current.shutdown_received = True
                sessions.append(current)
                current = None
            session_index += 1
            continue

        if _is_task_assignment(msg, worker_id):
            if current is None:
                current = WorkerSession(worker_id=worker_id, session_index=session_index)
            current.assigned_count += 1
            current.task_subjects.append(msg.get("subject", ""))
            continue

        if _is_wrap(msg, worker_id):
            if current is None:
                current = WorkerSession(worker_id=worker_id, session_index=session_index)
            current.wrap_count += 1
            continue

    # Capture any trailing open session (no SHUTDOWN yet)
    if current is not None and current.assigned_count > 0:
        sessions.append(current)

    return sessions


def detect_incomplete_sessions(messages: List[dict]) -> List[WorkerSession]:
    """Return all WorkerSession objects where wrap_count < assigned_count."""
    incomplete = []
    for worker_id in KNOWN_WORKERS:
        sessions = parse_worker_sessions(messages, worker_id)
        for session in sessions:
            if not session.is_complete:
                incomplete.append(session)
    return incomplete


def report(messages: List[dict]) -> str:
    """Generate a human-readable report of worker session completeness."""
    if not messages:
        return "No sessions found in queue."

    lines = ["Worker Task Tracker Report", "=" * 40]

    any_incomplete = False
    for worker_id in KNOWN_WORKERS:
        sessions = parse_worker_sessions(messages, worker_id)
        if not sessions:
            continue

        lines.append(f"\n{worker_id}:")
        for i, session in enumerate(sessions):
            status = "OK" if session.is_complete else "INCOMPLETE"
            shutdown_note = "" if session.shutdown_received else " (open session)"
            lines.append(
                f"  Session {i + 1}{shutdown_note}: "
                f"{session.assigned_count} assigned, {session.wrap_count} wrapped — {status}"
            )
            if not session.is_complete and session.missing_tasks:
                lines.append("  Missing tasks:")
                for t in session.missing_tasks:
                    lines.append(f"    - {t[:80]}")
                any_incomplete = True

    if not any_incomplete:
        lines.append("\nAll sessions complete. OK")
    else:
        missing_total = sum(
            s.assigned_count - s.wrap_count
            for w in KNOWN_WORKERS
            for s in parse_worker_sessions(messages, w)
            if not s.is_complete
        )
        lines.append(f"\nSummary: {missing_total} task(s) may be INCOMPLETE across all workers.")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect workers who wrapped early.")
    parser.add_argument("--path", default=DEFAULT_QUEUE_PATH, help="Path to JSONL queue")
    args = parser.parse_args()

    messages = load_queue(args.path)
    print(report(messages))


if __name__ == "__main__":
    main()
