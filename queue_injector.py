#!/usr/bin/env python3
"""
queue_injector.py — Cross-Chat Queue Context Injection Hook

UserPromptSubmit hook that injects unread cross-chat messages as
additionalContext, so Kalshi chats immediately see CCA research
findings without manual bridge file checking.

Works bidirectionally: CCA sees Kalshi requests, Kalshi sees CCA findings.

Hook setup (settings.local.json):
    {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "type": "command",
                    "command": "python3 /path/to/queue_injector.py"
                }
            ]
        }
    }

Environment variable CCA_CHAT_ID can override auto-detection:
    CCA_CHAT_ID=km  — force Kalshi Main identity
    CCA_CHAT_ID=kr  — force Kalshi Research identity
    CCA_CHAT_ID=cca — force CCA identity

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Queue file location — same as cross_chat_queue.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cross_chat_queue.jsonl")

# Priority order for sorting
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Project path patterns for identity detection
PROJECT_PATTERNS = {
    "ClaudeCodeAdvancements": "cca",
    "polymarket-bot": "kalshi",  # Ambiguous: could be main or research
}


def detect_chat_identity(
    cwd: Optional[str] = None,
    env_chat_id: Optional[str] = None,
) -> Optional[str]:
    """Determine which chat we're running in.

    Priority:
    1. Explicit env var CCA_CHAT_ID
    2. CWD-based pattern matching

    Returns: chat_id (cca, km, kr) or None if unknown.
    """
    # Check explicit override
    if env_chat_id:
        return env_chat_id

    # CWD-based detection
    if cwd:
        for pattern, chat_id in PROJECT_PATTERNS.items():
            if pattern in cwd:
                return chat_id

    return None


def _load_unread(target: str, path: str) -> list:
    """Load unread messages for a specific target chat."""
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


def build_injection_context(target: str, queue_path: str) -> str:
    """Build a context string from unread messages for the target chat.

    Returns empty string if no unread messages.
    """
    unread = _load_unread(target, queue_path)
    if not unread:
        return ""

    # Sort by priority (critical first)
    unread.sort(key=lambda m: PRIORITY_ORDER.get(m.get("priority", "low"), 3))

    total = len(unread)

    # Priority breakdown
    priority_counts = {}
    for msg in unread:
        p = msg.get("priority", "medium")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    priority_parts = []
    for p in ["critical", "high", "medium", "low"]:
        if p in priority_counts:
            priority_parts.append(f"{priority_counts[p]} {p}")

    # Build header
    chat_names = {"cca": "CCA", "km": "Kalshi Main", "kr": "Kalshi Research"}
    chat_name = chat_names.get(target, target)

    header = f"[cross-chat] {total} unread message{'s' if total != 1 else ''} for {chat_name}"
    if priority_parts:
        header += f" ({', '.join(priority_parts)})"

    # Build message list
    lines = [header]
    for msg in unread:
        priority_tag = msg.get("priority", "medium").upper()
        subject = msg.get("subject", "No subject")
        sender = msg.get("sender", "?")
        sender_name = chat_names.get(sender, sender)
        lines.append(f"  [{priority_tag}] {subject} (from {sender_name})")
        if msg.get("body"):
            body_preview = msg["body"][:150]
            if len(msg["body"]) > 150:
                body_preview += "..."
            lines.append(f"    {body_preview}")

    lines.append(f"  Ack: python3 cross_chat_queue.py ack --all --target {target}")

    return "\n".join(lines)


def generate_hook_response(context: str) -> str:
    """Generate the hook JSON response.

    Always continues (never blocks). Adds additionalContext only if
    there are unread messages.
    """
    response = {"continue": True}
    if context:
        response["additionalContext"] = context
    return json.dumps(response)


def run_hook(
    chat_id: Optional[str] = None,
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> str:
    """Run the full hook flow: detect identity -> check queue -> respond.

    Returns JSON string for hook output.
    """
    if not chat_id:
        return generate_hook_response("")

    context = build_injection_context(chat_id, queue_path)
    return generate_hook_response(context)


def main():
    """Entry point when invoked as a hook.

    Reads stdin (hook input), detects chat identity, checks queue,
    outputs JSON response.
    """
    try:
        # Read hook input from stdin (may be empty for UserPromptSubmit)
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            hook_input = {}

        # Detect chat identity
        env_chat_id = os.environ.get("CCA_CHAT_ID")
        cwd = os.getcwd()
        chat_id = detect_chat_identity(cwd=cwd, env_chat_id=env_chat_id)

        # For polymarket-bot, default to km (main) unless overridden
        if chat_id == "kalshi":
            chat_id = env_chat_id or "km"

        result = run_hook(chat_id=chat_id, queue_path=DEFAULT_QUEUE_PATH)
        print(result)

    except Exception:
        # Hooks must never crash — fail silently with valid JSON
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
