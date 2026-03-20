#!/usr/bin/env python3
"""
queue_hook.py — Unified Queue Check Hook (PostToolUse + UserPromptSubmit)

Replaces queue_injector.py with a faster, dual-event hook that fires on BOTH
PostToolUse and UserPromptSubmit. This ensures autonomous chats see new
messages between every tool call, not just when the user types.

Checks both queues:
- cross_chat_queue.jsonl (CCA <-> Kalshi communication)
- cca_internal_queue.jsonl (Desktop <-> Terminal coordination)

Throttled: PostToolUse checks every 30s to avoid latency spam.
UserPromptSubmit always checks (user deserves fresh context).

Performance target: <5ms per invocation (reads two small JSONL files).

Hook setup (settings.local.json):
    {
        "hooks": {
            "PostToolUse": [{
                "type": "command",
                "command": "python3 /path/to/queue_hook.py"
            }],
            "UserPromptSubmit": [{
                "type": "command",
                "command": "python3 /path/to/queue_hook.py"
            }]
        }
    }

Environment variables:
    CCA_CHAT_ID        — Cross-chat identity (cca, km, kr)
    CCA_INTERNAL_ID    — Internal queue identity (desktop, terminal)
    CCA_QUEUE_INTERVAL — Throttle interval in seconds (default: 30)

Stdlib only. No external dependencies.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CROSS_PATH = os.path.join(SCRIPT_DIR, "cross_chat_queue.jsonl")
DEFAULT_INTERNAL_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")
THROTTLE_STATE_FILE = os.path.join(SCRIPT_DIR, ".queue_hook_last_check")
DEFAULT_INTERVAL = 30  # seconds

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
CROSS_CHAT_NAMES = {"cca": "CCA", "km": "Kalshi Main", "kr": "Kalshi Research"}
INTERNAL_CHAT_NAMES = {"desktop": "Desktop", "terminal": "Terminal"}


def should_check_queues(
    last_check: float,
    now: float,
    interval: float = DEFAULT_INTERVAL,
    force: bool = False,
) -> bool:
    """Determine if we should check queues based on throttle interval.

    Args:
        last_check: timestamp of last check
        now: current timestamp
        interval: minimum seconds between checks
        force: if True, always check (for UserPromptSubmit)
    """
    if force:
        return True
    return (now - last_check) >= interval


def _load_unread(target: str, path: str) -> list:
    """Load unread messages for a specific target from a JSONL file."""
    if not os.path.exists(path):
        return []
    unread = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("target") == target and msg.get("status") == "unread":
                        unread.append(msg)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return unread


def _format_messages(messages: list, source_label: str, names: dict) -> list:
    """Format messages into display lines."""
    if not messages:
        return []

    messages.sort(key=lambda m: PRIORITY_ORDER.get(m.get("priority", "low"), 3))
    total = len(messages)

    priority_counts = {}
    for msg in messages:
        p = msg.get("priority", "medium")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    priority_parts = []
    for p in ["critical", "high", "medium", "low"]:
        if p in priority_counts:
            priority_parts.append(f"{priority_counts[p]} {p}")

    header = f"[{source_label}] {total} unread"
    if priority_parts:
        header += f" ({', '.join(priority_parts)})"

    lines = [header]
    for msg in messages:
        ptag = msg.get("priority", "medium").upper()
        subject = msg.get("subject", "No subject")
        sender = msg.get("sender", "?")
        sender_name = names.get(sender, sender)
        category = msg.get("category", "")

        if category == "scope_claim":
            lines.append(f"  [SCOPE CLAIM] {subject} (from {sender_name})")
        else:
            lines.append(f"  [{ptag}] {subject} (from {sender_name})")

        if msg.get("body"):
            body_preview = msg["body"][:120]
            if len(msg["body"]) > 120:
                body_preview += "..."
            lines.append(f"    {body_preview}")

    return lines


def check_queues(
    cross_chat_id: Optional[str] = None,
    cross_path: str = DEFAULT_CROSS_PATH,
    internal_path: str = DEFAULT_INTERNAL_PATH,
    internal_identity: Optional[str] = None,
) -> str:
    """Check both queues and return combined context string.

    Returns empty string if no unread messages.
    """
    all_lines = []

    # Check cross-chat queue
    if cross_chat_id:
        cross_unread = _load_unread(cross_chat_id, cross_path)
        cross_lines = _format_messages(cross_unread, "cross-chat", CROSS_CHAT_NAMES)
        all_lines.extend(cross_lines)

    # Check internal queue
    if internal_identity:
        internal_unread = _load_unread(internal_identity, internal_path)
        internal_lines = _format_messages(internal_unread, "internal", INTERNAL_CHAT_NAMES)
        all_lines.extend(internal_lines)

    return "\n".join(all_lines) if all_lines else ""


def detect_identity(
    cwd: Optional[str] = None,
    env_cross_id: Optional[str] = None,
    env_internal_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Detect cross-chat ID and internal ID.

    Returns: (cross_chat_id, internal_identity)
    """
    cross_id = env_cross_id
    internal_id = env_internal_id

    if not cross_id and cwd:
        if "ClaudeCodeAdvancements" in cwd:
            cross_id = "cca"
        elif "polymarket-bot" in cwd:
            cross_id = "km"

    return cross_id, internal_id


def format_hook_response(context: str, hook_type: str = "PostToolUse") -> str:
    """Format the hook JSON response.

    Never blocks or denies — always passes through with optional context.
    """
    if hook_type == "UserPromptSubmit":
        response = {"continue": True}
        if context:
            response["additionalContext"] = context
    else:
        # PostToolUse
        response = {}
        if context:
            response["additionalContext"] = context

    return json.dumps(response)


def _read_last_check() -> float:
    """Read the last check timestamp from state file."""
    try:
        if os.path.exists(THROTTLE_STATE_FILE):
            return float(Path(THROTTLE_STATE_FILE).read_text().strip())
    except (ValueError, OSError):
        pass
    return 0.0


def _write_last_check(ts: float) -> None:
    """Write the last check timestamp to state file."""
    try:
        Path(THROTTLE_STATE_FILE).write_text(str(ts))
    except OSError:
        pass


def main():
    """Entry point when invoked as a hook."""
    try:
        # Read hook input
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            hook_input = {}

        # Determine hook type from input
        hook_type = "PostToolUse"
        if "userMessage" in hook_input or "prompt" in hook_input:
            hook_type = "UserPromptSubmit"

        # Throttle check for PostToolUse
        now = time.time()
        interval = float(os.environ.get("CCA_QUEUE_INTERVAL", DEFAULT_INTERVAL))
        force = (hook_type == "UserPromptSubmit")

        if not force:
            last_check = _read_last_check()
            if not should_check_queues(last_check, now, interval):
                print(json.dumps({}))
                return

        # Detect identity
        env_cross = os.environ.get("CCA_CHAT_ID")
        env_internal = os.environ.get("CCA_INTERNAL_ID")
        cross_id, internal_id = detect_identity(
            cwd=os.getcwd(),
            env_cross_id=env_cross,
            env_internal_id=env_internal,
        )

        # Check queues
        context = check_queues(
            cross_chat_id=cross_id,
            internal_identity=internal_id,
        )

        # Update throttle state
        _write_last_check(now)

        # Output
        print(format_hook_response(context, hook_type))

    except Exception:
        # Hooks must never crash
        print(json.dumps({}))


if __name__ == "__main__":
    main()
