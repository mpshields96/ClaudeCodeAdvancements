#!/usr/bin/env python3
"""
cross_chat_queue.py — Bidirectional Cross-Chat Message Queue

Problem: CCA delivers research findings to Kalshi chats via bridge files
(KALSHI_INTEL.md, CCA_TO_POLYBOT.md, KALSHI_ACTION_ITEMS.md) but there's
no notification mechanism. Zero items get picked up because neither chat
knows when new content arrives.

Solution: A structured JSONL queue with read/unread tracking per chat.
Each message has a sender, target, priority, and read status.

Chats check for unread messages at session start. CCA's UserPromptSubmit
hook can inject "N unread messages for Kalshi" as context.

Storage: cross_chat_queue.jsonl (this project directory)

Usage:
    # Send a message from CCA to Kalshi main chat
    python3 cross_chat_queue.py send --from cca --to km --priority high \
        --subject "Block 08:xx UTC sniper bets" --body "z=-4.30, p<0.0001"

    # Check unread messages for a target chat
    python3 cross_chat_queue.py unread --for km

    # Mark messages as read
    python3 cross_chat_queue.py ack <message_id>

    # List all messages
    python3 cross_chat_queue.py list [--status unread] [--for km]

    # Summary: unread counts per chat
    python3 cross_chat_queue.py summary

Stdlib only. No external dependencies.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cross_chat_queue.jsonl")

# Chat identifiers
VALID_CHATS = {
    "cca": "ClaudeCodeAdvancements",
    "km": "Kalshi Main",
    "kr": "Kalshi Research",
}

VALID_PRIORITIES = ["critical", "high", "medium", "low"]

VALID_CATEGORIES = [
    "action_item",      # Specific thing to implement
    "research_finding",  # Paper, signal, framework to evaluate
    "status_update",     # Progress report or outcome
    "question",          # Needs a response
    "fyi",              # Informational, no action needed
]


# ── Data Types ──────────────────────────────────────────────────────────────

def _make_id(sender: str, target: str, subject: str) -> str:
    """Generate a deterministic message ID.

    Includes target in hash to avoid collisions when the same sender
    sends the same subject to multiple targets in one second.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    content_hash = hashlib.sha256(f"{sender}:{target}:{subject}:{ts}".encode()).hexdigest()[:8]
    return f"msg_{ts}_{content_hash}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Storage ────────────────────────────────────────────────────────────────

def _load_queue(path: str = DEFAULT_QUEUE_PATH) -> list[dict]:
    """Load all messages from the queue file."""
    if not os.path.exists(path):
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def _save_queue(messages: list[dict], path: str = DEFAULT_QUEUE_PATH) -> None:
    """Rewrite the entire queue (used for updates like ack)."""
    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, separators=(",", ":")) + "\n")


def _append_message(message: dict, path: str = DEFAULT_QUEUE_PATH) -> None:
    """Append a single message to the queue."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, separators=(",", ":")) + "\n")


# ── Core Operations ─────────────────────────────────────────────────────────

def send_message(
    sender: str,
    target: str,
    subject: str,
    body: str = "",
    priority: str = "medium",
    category: str = "action_item",
    ref_file: str = "",
    ref_line: str = "",
    path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """
    Send a message from one chat to another.

    Args:
        sender: Chat ID (cca, km, kr)
        target: Chat ID (cca, km, kr)
        subject: Short summary (one line)
        body: Full details
        priority: critical/high/medium/low
        category: action_item/research_finding/status_update/question/fyi
        ref_file: Reference file (e.g., "KALSHI_INTEL.md")
        ref_line: Line reference (e.g., "lines 796-806")
        path: Queue file path

    Returns:
        The message dict that was written.
    """
    if sender not in VALID_CHATS:
        raise ValueError(f"Invalid sender: {sender}. Must be one of {list(VALID_CHATS.keys())}")
    if target not in VALID_CHATS:
        raise ValueError(f"Invalid target: {target}. Must be one of {list(VALID_CHATS.keys())}")
    if sender == target:
        raise ValueError("Cannot send a message to yourself")
    if not subject:
        raise ValueError("Subject cannot be empty")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}. Must be one of {VALID_PRIORITIES}")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}. Must be one of {VALID_CATEGORIES}")

    msg = {
        "id": _make_id(sender, target, subject),
        "sender": sender,
        "target": target,
        "subject": subject,
        "body": body,
        "priority": priority,
        "category": category,
        "status": "unread",
        "created_at": _now_iso(),
        "read_at": None,
    }

    if ref_file:
        msg["ref_file"] = ref_file
    if ref_line:
        msg["ref_line"] = ref_line

    # Dedup: skip if identical sender+target+subject+body sent in last 24h
    existing = _load_queue(path)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for old in reversed(existing):
        created = old.get("created_at", "")
        if created and created < cutoff.isoformat():
            break  # Past 24h window, stop scanning
        if (old.get("sender") == sender and old.get("target") == target
                and old.get("subject") == subject and old.get("body") == body):
            return old  # Duplicate — return existing message, don't append

    _append_message(msg, path)
    return msg


def get_unread(target: str, path: str = DEFAULT_QUEUE_PATH) -> list[dict]:
    """Get all unread messages for a specific chat."""
    messages = _load_queue(path)
    return [
        m for m in messages
        if m.get("target") == target and m.get("status") == "unread"
    ]


def get_unread_summary(path: str = DEFAULT_QUEUE_PATH) -> dict[str, dict]:
    """
    Get unread message counts per chat with priority breakdown.
    Returns: {chat_id: {"total": N, "critical": N, "high": N, ...}}
    """
    messages = _load_queue(path)
    summary: dict[str, dict] = {}

    for chat_id in VALID_CHATS:
        unread = [m for m in messages if m.get("target") == chat_id and m.get("status") == "unread"]
        if not unread:
            continue
        breakdown = {"total": len(unread)}
        for p in VALID_PRIORITIES:
            count = sum(1 for m in unread if m.get("priority") == p)
            if count:
                breakdown[p] = count
        summary[chat_id] = breakdown

    return summary


def acknowledge(message_id: str, path: str = DEFAULT_QUEUE_PATH) -> bool:
    """Mark a message as read. Returns True if found and updated."""
    messages = _load_queue(path)
    found = False
    for msg in messages:
        if msg.get("id") == message_id and msg.get("status") == "unread":
            msg["status"] = "read"
            msg["read_at"] = _now_iso()
            found = True
            break

    if found:
        _save_queue(messages, path)
    return found


def acknowledge_all(target: str, path: str = DEFAULT_QUEUE_PATH) -> int:
    """Mark all unread messages for a target as read. Returns count."""
    messages = _load_queue(path)
    count = 0
    for msg in messages:
        if msg.get("target") == target and msg.get("status") == "unread":
            msg["status"] = "read"
            msg["read_at"] = _now_iso()
            count += 1

    if count:
        _save_queue(messages, path)
    return count


def list_messages(
    target: str | None = None,
    status: str | None = None,
    path: str = DEFAULT_QUEUE_PATH,
) -> list[dict]:
    """List messages with optional filters."""
    messages = _load_queue(path)
    if target:
        messages = [m for m in messages if m.get("target") == target]
    if status:
        messages = [m for m in messages if m.get("status") == status]
    return messages


# ── Hook Integration ────────────────────────────────────────────────────────

def format_unread_context(target: str, path: str = DEFAULT_QUEUE_PATH) -> str:
    """
    Format unread messages as a context string for hook injection.
    Returns empty string if no unread messages.

    Example output:
    "[cross-chat] 3 unread messages for Kalshi Main (1 critical, 2 high).
     Top: Block 08:xx UTC sniper bets [critical]. Run: python3 cross_chat_queue.py unread --for km"
    """
    unread = get_unread(target, path)
    if not unread:
        return ""

    chat_name = VALID_CHATS.get(target, target)
    total = len(unread)

    # Priority breakdown
    priority_parts = []
    for p in VALID_PRIORITIES:
        count = sum(1 for m in unread if m.get("priority") == p)
        if count:
            priority_parts.append(f"{count} {p}")

    priority_str = ", ".join(priority_parts) if priority_parts else ""

    # Top message (highest priority first)
    sorted_unread = sorted(unread, key=lambda m: VALID_PRIORITIES.index(m.get("priority", "low")))
    top = sorted_unread[0]

    parts = [
        f"[cross-chat] {total} unread message{'s' if total != 1 else ''} for {chat_name}",
    ]
    if priority_str:
        parts[0] += f" ({priority_str})"
    parts[0] += "."

    parts.append(f"Top: {top['subject']} [{top['priority']}].")

    return " ".join(parts)


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli_send(args):
    msg = send_message(
        sender=args.sender,
        target=args.to,
        subject=args.subject,
        body=args.body or "",
        priority=args.priority,
        category=args.category,
        ref_file=args.ref_file or "",
        ref_line=args.ref_line or "",
    )
    print(f"Sent: {msg['id']} -> {VALID_CHATS[args.to]} [{args.priority}]")
    print(f"  Subject: {args.subject}")


def _cli_unread(args):
    unread = get_unread(args.target)
    if not unread:
        print(f"No unread messages for {VALID_CHATS.get(args.target, args.target)}.")
        return

    print(f"Unread messages for {VALID_CHATS[args.target]} ({len(unread)}):\n")
    for msg in sorted(unread, key=lambda m: VALID_PRIORITIES.index(m.get("priority", "low"))):
        print(f"  [{msg['priority'].upper()}] {msg['subject']}")
        print(f"    ID: {msg['id']} | From: {VALID_CHATS[msg['sender']]} | {msg['created_at']}")
        if msg.get("body"):
            body_preview = msg["body"][:120]
            if len(msg["body"]) > 120:
                body_preview += "..."
            print(f"    {body_preview}")
        if msg.get("ref_file"):
            ref = msg["ref_file"]
            if msg.get("ref_line"):
                ref += f" {msg['ref_line']}"
            print(f"    Ref: {ref}")
        print()


def _cli_ack(args):
    if args.all:
        count = acknowledge_all(args.target)
        print(f"Acknowledged {count} messages for {VALID_CHATS.get(args.target, args.target)}.")
    else:
        if acknowledge(args.message_id):
            print(f"Acknowledged: {args.message_id}")
        else:
            print(f"Not found or already read: {args.message_id}")


def _cli_list(args):
    messages = list_messages(target=args.target, status=args.status)
    if not messages:
        print("No messages match the filter.")
        return

    for msg in messages:
        status_marker = "*" if msg.get("status") == "unread" else " "
        print(f"{status_marker} [{msg['priority'].upper():>8}] {msg['subject']}")
        print(f"    {msg['sender']} -> {msg['target']} | {msg['created_at']} | {msg['status']}")


def _cli_summary(args):
    summary = get_unread_summary()
    if not summary:
        print("No unread messages for any chat.")
        return

    print("Unread message summary:\n")
    for chat_id, counts in summary.items():
        chat_name = VALID_CHATS.get(chat_id, chat_id)
        parts = [f"{counts['total']} total"]
        for p in VALID_PRIORITIES:
            if p in counts:
                parts.append(f"{counts[p]} {p}")
        print(f"  {chat_name}: {', '.join(parts)}")


def main():
    parser = argparse.ArgumentParser(description="Cross-chat message queue")
    sub = parser.add_subparsers(dest="command", help="Command")

    # send
    send_p = sub.add_parser("send", help="Send a message")
    send_p.add_argument("--from", dest="sender", required=True, choices=VALID_CHATS.keys())
    send_p.add_argument("--to", required=True, choices=VALID_CHATS.keys())
    send_p.add_argument("--subject", required=True)
    send_p.add_argument("--body", default="")
    send_p.add_argument("--priority", default="medium", choices=VALID_PRIORITIES)
    send_p.add_argument("--category", default="action_item", choices=VALID_CATEGORIES)
    send_p.add_argument("--ref-file", default="")
    send_p.add_argument("--ref-line", default="")

    # unread
    unread_p = sub.add_parser("unread", help="Check unread messages")
    unread_p.add_argument("--for", dest="target", required=True, choices=VALID_CHATS.keys())

    # ack
    ack_p = sub.add_parser("ack", help="Acknowledge a message")
    ack_p.add_argument("message_id", nargs="?", default="")
    ack_p.add_argument("--all", action="store_true", help="Acknowledge all for a target")
    ack_p.add_argument("--for", dest="target", default="", choices=list(VALID_CHATS.keys()) + [""])

    # list
    list_p = sub.add_parser("list", help="List messages")
    list_p.add_argument("--for", dest="target", default=None, choices=list(VALID_CHATS.keys()) + [None])
    list_p.add_argument("--status", default=None, choices=["unread", "read"])

    # summary
    sub.add_parser("summary", help="Unread summary per chat")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "send": _cli_send,
        "unread": _cli_unread,
        "ack": _cli_ack,
        "list": _cli_list,
        "summary": _cli_summary,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
