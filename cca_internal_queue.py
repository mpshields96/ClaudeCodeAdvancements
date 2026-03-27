#!/usr/bin/env python3
"""
cca_internal_queue.py — CCA Internal Communication Queue

Problem: Multiple CCA chats run in parallel (desktop, workers, and Codex). Without
coordination, they step on each other's files, duplicate work, or miss
handoff requests. The CCA-Kalshi cross_chat_queue.py solved the same
problem for inter-project communication — this steals that technology
for intra-project use.

Solution: A structured JSONL queue with read/unread tracking per chat.
Each message has a sender, target, priority, category, and read status.
Categories are tailored for coordination: scope claims, file locks,
conflict alerts, handoffs, and status updates.

Storage: cca_internal_queue.jsonl (this project directory)

Usage:
    # Claim scope (I'm working on X, don't touch it)
    python3 cca_internal_queue.py send --from desktop --to terminal \
        --category scope_claim --subject "Working on cca-loop" \
        --body "Do NOT touch cca-loop/, SESSION_RESUME.md, or bash_guard global hook wiring"

    # Report a file conflict
    python3 cca_internal_queue.py send --from terminal --to desktop \
        --category conflict_alert --priority high \
        --subject "Modified agent-guard/bash_guard.py"

    # Hand off work
    python3 cca_internal_queue.py send --from desktop --to terminal \
        --category handoff --subject "CI/CD GitHub Actions" \
        --body "Workflow file drafted but not tested. Pick up from .github/workflows/tests.yml"

    # Check unread messages
    python3 cca_internal_queue.py unread --for desktop

    # Mark messages as read
    python3 cca_internal_queue.py ack <message_id>

    # Unread summary
    python3 cca_internal_queue.py summary

    # Active scope claims
    python3 cca_internal_queue.py scopes

Stdlib only. No external dependencies.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")

# Chat identifiers
VALID_CHATS = {
    "desktop": "CCA Desktop",
    "terminal": "CCA Terminal",
    "cli1": "CCA CLI 1",
    "cli2": "CCA CLI 2",
    "codex": "Codex",
}

VALID_PRIORITIES = ["critical", "high", "medium", "low"]

VALID_CATEGORIES = [
    "scope_claim",      # I'm working on X, don't touch it
    "scope_release",    # I'm done with X, it's free
    "conflict_alert",   # I modified file X (heads up)
    "handoff",          # Please pick up task X
    "status_update",    # Progress report
    "question",         # Needs a response
    "fyi",              # Informational, no action needed
]


# ── Data Types ──────────────────────────────────────────────────────────────

def _make_id(sender: str, target: str, subject: str) -> str:
    """Generate a deterministic message ID.

    Includes target in hash to avoid collisions when the same sender
    broadcasts the same subject to multiple targets in one second.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    content_hash = hashlib.sha256(f"{sender}:{target}:{subject}:{ts}".encode()).hexdigest()[:8]
    return f"cca_{ts}_{content_hash}"


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
    """Rewrite the entire queue atomically (used for updates like ack).

    Uses temp file + os.replace() to prevent corruption from concurrent
    access or crashes mid-write. os.replace() is atomic on POSIX.
    """
    dir_path = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp", prefix=".cca_queue_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, separators=(",", ":")) + "\n")
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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
    category: str = "fyi",
    files: list[str] | None = None,
    path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """
    Send a message from one CCA chat to another.

    Args:
        sender: Chat ID (desktop, terminal, cli1, cli2, codex)
        target: Chat ID (desktop, terminal, cli1, cli2, codex)
        subject: Short summary (one line)
        body: Full details
        priority: critical/high/medium/low
        category: scope_claim/scope_release/conflict_alert/handoff/status_update/question/fyi
        files: List of file paths this message concerns (for scope claims/conflicts)
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

    if files:
        msg["files"] = files

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
    category: str | None = None,
    path: str = DEFAULT_QUEUE_PATH,
) -> list[dict]:
    """List messages with optional filters."""
    messages = _load_queue(path)
    if target:
        messages = [m for m in messages if m.get("target") == target]
    if status:
        messages = [m for m in messages if m.get("status") == status]
    if category:
        messages = [m for m in messages if m.get("category") == category]
    return messages


# ── Scope Tracking ─────────────────────────────────────────────────────────

def get_active_scopes(path: str = DEFAULT_QUEUE_PATH) -> list[dict]:
    """
    Get currently active scope claims. A scope is active if there's a
    scope_claim without a matching scope_release after it.

    Returns list of active scope_claim messages with sender info.
    """
    messages = _load_queue(path)

    # Collect all scope claims and releases
    claims = [m for m in messages if m.get("category") == "scope_claim"]
    releases = [m for m in messages if m.get("category") == "scope_release"]

    # A claim is released if there's a release from the same sender
    # with a created_at after the claim's created_at
    active = []
    seen = set()  # Deduplicate broadcast claims: (sender, subject)
    for claim in claims:
        key = (claim.get("sender", ""), claim.get("subject", ""))
        if key in seen:
            continue
        released = any(
            r.get("sender") == claim.get("sender")
            and r.get("created_at", "") > claim.get("created_at", "")
            and _scopes_overlap(claim, r)
            for r in releases
        )
        if not released:
            seen.add(key)
            active.append(claim)

    return active


def _scopes_overlap(claim: dict, release: dict) -> bool:
    """Check if a release matches a claim by subject or files."""
    # Subject match
    if claim.get("subject", "").lower() in release.get("subject", "").lower():
        return True
    if release.get("subject", "").lower() in claim.get("subject", "").lower():
        return True
    # File overlap
    claim_files = set(claim.get("files", []))
    release_files = set(release.get("files", []))
    if claim_files and release_files and claim_files & release_files:
        return True
    return False


def check_scope_conflict(
    sender: str,
    files: list[str],
    path: str = DEFAULT_QUEUE_PATH,
) -> list[dict]:
    """
    Check if any files conflict with active scope claims from the other chat.

    Args:
        sender: The chat that wants to work on these files
        files: List of file paths to check

    Returns:
        List of conflicting scope claims (empty = safe to proceed)
    """
    active = get_active_scopes(path)
    conflicts = []

    for claim in active:
        # Skip own claims
        if claim.get("sender") == sender:
            continue

        claim_files = set(claim.get("files", []))
        check_files = set(files)

        # Direct file overlap
        if claim_files & check_files:
            conflicts.append(claim)
            continue

        # Check if any claimed path is a prefix of checked files or vice versa
        for cf in claim_files:
            for f in check_files:
                if f.startswith(cf) or cf.startswith(f):
                    conflicts.append(claim)
                    break

    return conflicts


# ── Hook Integration ────────────────────────────────────────────────────────

def format_unread_context(target: str, path: str = DEFAULT_QUEUE_PATH) -> str:
    """
    Format unread messages as a context string for hook injection.
    Returns empty string if no unread messages.

    Example output:
    "[cca-internal] 2 unread from CCA Terminal (1 scope_claim, 1 handoff).
     Top: Working on cca-loop [high/scope_claim]."
    """
    unread = get_unread(target, path)
    if not unread:
        return ""

    chat_name = VALID_CHATS.get(target, target)
    other_chat = [c for c in VALID_CHATS if c != target]
    total = len(unread)

    # Category breakdown
    cat_parts = []
    for cat in VALID_CATEGORIES:
        count = sum(1 for m in unread if m.get("category") == cat)
        if count:
            cat_parts.append(f"{count} {cat}")

    cat_str = ", ".join(cat_parts) if cat_parts else ""

    # Sort by priority, then scope_claims first
    priority_order = {p: i for i, p in enumerate(VALID_PRIORITIES)}
    category_order = {c: i for i, c in enumerate(VALID_CATEGORIES)}
    sorted_unread = sorted(
        unread,
        key=lambda m: (
            priority_order.get(m.get("priority", "low"), 99),
            category_order.get(m.get("category", "fyi"), 99),
        ),
    )
    top = sorted_unread[0]

    # Determine sender name
    senders = {m.get("sender") for m in unread}
    sender_names = ", ".join(VALID_CHATS.get(s, s) for s in senders)

    parts = [
        f"[cca-internal] {total} unread from {sender_names}",
    ]
    if cat_str:
        parts[0] += f" ({cat_str})"
    parts[0] += "."

    parts.append(f"Top: {top['subject']} [{top['priority']}/{top['category']}].")

    # Add active scope warnings
    active_scopes = get_active_scopes(path)
    other_scopes = [s for s in active_scopes if s.get("sender") != target]
    if other_scopes:
        scope_subjects = [s["subject"] for s in other_scopes[:3]]
        parts.append(f"Active scope claims: {'; '.join(scope_subjects)}.")

    return " ".join(parts)


def queue_health(path: str = DEFAULT_QUEUE_PATH) -> dict:
    """
    Diagnostic health check for the queue. Used by /cca-init to verify
    queue state before starting work.

    Returns dict with: status, total_messages, unread_count, active_scopes,
    stale_scopes, corrupt_lines.
    """
    result = {
        "status": "healthy",
        "total_messages": 0,
        "unread_count": 0,
        "active_scopes": 0,
        "stale_scopes": 0,
        "corrupt_lines": 0,
    }

    if not os.path.exists(path):
        return result

    # Count total messages and corrupt lines
    corrupt = 0
    messages = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    corrupt += 1
    except OSError:
        result["status"] = "error"
        return result

    result["total_messages"] = len(messages)
    result["corrupt_lines"] = corrupt
    result["unread_count"] = sum(1 for m in messages if m.get("status") == "unread")

    # Count active and stale scopes
    active = get_active_scopes(path)
    result["active_scopes"] = len(active)

    now = datetime.now(timezone.utc)
    stale_count = 0
    for scope in active:
        created = scope.get("created_at", "")
        if created:
            try:
                scope_time = datetime.fromisoformat(created)
                if (now - scope_time) > timedelta(minutes=30):
                    stale_count += 1
            except (ValueError, TypeError):
                pass
    result["stale_scopes"] = stale_count

    # Determine overall status
    if corrupt > 0:
        result["status"] = "warning"
    elif stale_count > 0:
        result["status"] = "warning"

    return result


def format_queue_health(health: dict) -> str:
    """Format queue health dict as a one-line status string for /cca-init."""
    status = health.get("status", "unknown")
    total = health.get("total_messages", 0)
    unread = health.get("unread_count", 0)
    scopes = health.get("active_scopes", 0)
    stale = health.get("stale_scopes", 0)
    corrupt = health.get("corrupt_lines", 0)

    parts = [f"Queue: {status}"]
    parts.append(f"{total} msgs ({unread} unread)")
    if scopes > 0:
        parts.append(f"{scopes} active scopes")
    if stale > 0:
        parts.append(f"{stale} stale")
    if corrupt > 0:
        parts.append(f"{corrupt} corrupt lines")
    return " | ".join(parts)


def expire_stale_scopes(
    timeout_minutes: int = 30,
    path: str = DEFAULT_QUEUE_PATH,
) -> list[dict]:
    """
    Auto-release scope claims older than timeout_minutes.

    For each expired scope, writes a scope_release message to the queue.
    Returns list of expired scope claims.
    """
    active = get_active_scopes(path)
    if not active:
        return []

    now = datetime.now(timezone.utc)
    expired = []

    for scope in active:
        created = scope.get("created_at", "")
        if not created:
            continue
        try:
            scope_time = datetime.fromisoformat(created)
        except (ValueError, TypeError):
            continue

        if (now - scope_time) > timedelta(minutes=timeout_minutes):
            expired.append(scope)
            # Write a scope_release to clear it
            send_message(
                sender=scope.get("sender", "system"),
                target=scope.get("target", "desktop"),
                subject=scope.get("subject", "unknown scope"),
                body=f"Auto-expired after {timeout_minutes}m inactivity. Original claim: {scope.get('id', 'unknown')}",
                category="scope_release",
                files=scope.get("files", []),
                path=path,
            )

    return expired


def format_scope_warning(path: str = DEFAULT_QUEUE_PATH) -> str:
    """
    Format active scope claims as a warning string.
    Useful for injection at session start.

    Example: "SCOPE CLAIMS ACTIVE: terminal owns cca-loop/ (claimed 10m ago)"
    """
    active = get_active_scopes(path)
    if not active:
        return ""

    parts = ["SCOPE CLAIMS ACTIVE:"]
    for claim in active:
        sender_name = VALID_CHATS.get(claim.get("sender", ""), claim.get("sender", ""))
        parts.append(f"{sender_name} owns \"{claim['subject']}\"")
        if claim.get("files"):
            parts[-1] += f" ({', '.join(claim['files'][:3])})"

    return " ".join(parts)


def hivemind_preflight(
    chat_id: str = "",
    auto_expire: bool = True,
    path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """
    Hivemind readiness check for /cca-init. Combines:
    1. Queue health check (corrupt lines, total messages)
    2. Stale scope auto-release (if auto_expire=True)
    3. Unread message count for this chat
    4. Active scope warnings

    Args:
        chat_id: This chat's ID (desktop, terminal, cli1, cli2, codex). If empty, reads CCA_CHAT_ID.
        auto_expire: Whether to auto-release stale scopes (>30 min).
        path: Queue file path.

    Returns:
        Dict with: status, health, expired_scopes, unread_count, active_scopes,
        scope_warning, summary (one-line human-readable string).
    """
    if not chat_id:
        chat_id = os.environ.get("CCA_CHAT_ID", "desktop")

    result = {
        "status": "ready",
        "chat_id": chat_id,
        "health": {},
        "expired_scopes": [],
        "unread_count": 0,
        "active_scopes": 0,
        "scope_warning": "",
        "summary": "",
    }

    # Step 1: Queue health
    health = queue_health(path)
    result["health"] = health

    # Step 2: Auto-expire stale scopes
    if auto_expire:
        expired = expire_stale_scopes(timeout_minutes=30, path=path)
        result["expired_scopes"] = expired

    # Step 3: Unread messages for this chat
    if chat_id in VALID_CHATS:
        unread = get_unread(chat_id, path)
        result["unread_count"] = len(unread)

    # Step 4: Active scope warnings
    active = get_active_scopes(path)
    result["active_scopes"] = len(active)
    result["scope_warning"] = format_scope_warning(path)

    # Determine status
    if health.get("status") == "error":
        result["status"] = "error"
    elif health.get("corrupt_lines", 0) > 0:
        result["status"] = "warning"
    elif result["unread_count"] > 0:
        result["status"] = "action_needed"

    # Build summary line
    parts = [f"Hivemind: {result['status']}"]
    if result["unread_count"] > 0:
        parts.append(f"{result['unread_count']} unread")
    if result["active_scopes"] > 0:
        parts.append(f"{result['active_scopes']} active scopes")
    if result["expired_scopes"]:
        parts.append(f"{len(result['expired_scopes'])} stale scopes auto-released")
    if health.get("corrupt_lines", 0) > 0:
        parts.append(f"{health['corrupt_lines']} corrupt queue lines")
    result["summary"] = " | ".join(parts)

    return result


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli_send(args):
    files = args.files.split(",") if args.files else None
    msg = send_message(
        sender=args.sender,
        target=args.to,
        subject=args.subject,
        body=args.body or "",
        priority=args.priority,
        category=args.category,
        files=files,
    )
    print(f"Sent: {msg['id']} -> {VALID_CHATS[args.to]} [{args.priority}/{args.category}]")
    print(f"  Subject: {args.subject}")


def _cli_unread(args):
    unread = get_unread(args.target)
    if not unread:
        print(f"No unread messages for {VALID_CHATS.get(args.target, args.target)}.")
        return

    print(f"Unread messages for {VALID_CHATS[args.target]} ({len(unread)}):\n")
    for msg in sorted(unread, key=lambda m: VALID_PRIORITIES.index(m.get("priority", "low"))):
        print(f"  [{msg['priority'].upper()}] [{msg['category']}] {msg['subject']}")
        print(f"    ID: {msg['id']} | From: {VALID_CHATS.get(msg['sender'], msg['sender'])} | {msg['created_at']}")
        if msg.get("body"):
            body_preview = msg["body"][:120]
            if len(msg["body"]) > 120:
                body_preview += "..."
            print(f"    {body_preview}")
        if msg.get("files"):
            print(f"    Files: {', '.join(msg['files'][:5])}")
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
    messages = list_messages(target=args.target, status=args.status, category=args.category)
    if not messages:
        print("No messages match the filter.")
        return

    for msg in messages:
        status_marker = "*" if msg.get("status") == "unread" else " "
        print(f"{status_marker} [{msg['priority'].upper():>8}] [{msg['category']}] {msg['subject']}")
        print(f"    {msg['sender']} -> {msg['target']} | {msg['created_at']} | {msg['status']}")


def _cli_summary(args):
    summary = get_unread_summary()
    if not summary:
        print("No unread messages.")
        return

    print("Unread message summary:\n")
    for chat_id, counts in summary.items():
        chat_name = VALID_CHATS.get(chat_id, chat_id)
        parts = [f"{counts['total']} total"]
        for p in VALID_PRIORITIES:
            if p in counts:
                parts.append(f"{counts[p]} {p}")
        print(f"  {chat_name}: {', '.join(parts)}")


def _cli_scopes(args):
    active = get_active_scopes()
    if not active:
        print("No active scope claims.")
        return

    print(f"Active scope claims ({len(active)}):\n")
    for claim in active:
        sender_name = VALID_CHATS.get(claim.get("sender", ""), claim.get("sender", ""))
        print(f"  {sender_name}: {claim['subject']}")
        if claim.get("files"):
            print(f"    Files: {', '.join(claim['files'])}")
        if claim.get("body"):
            print(f"    {claim['body'][:120]}")
        print(f"    Since: {claim['created_at']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="CCA Desktop <-> Terminal communication queue")
    sub = parser.add_subparsers(dest="command", help="Command")

    # send
    send_p = sub.add_parser("send", help="Send a message")
    send_p.add_argument("--from", dest="sender", required=True, choices=VALID_CHATS.keys())
    send_p.add_argument("--to", required=True, choices=VALID_CHATS.keys())
    send_p.add_argument("--subject", required=True)
    send_p.add_argument("--body", default="")
    send_p.add_argument("--priority", default="medium", choices=VALID_PRIORITIES)
    send_p.add_argument("--category", default="fyi", choices=VALID_CATEGORIES)
    send_p.add_argument("--files", default="", help="Comma-separated file paths")

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
    list_p.add_argument("--category", default=None, choices=VALID_CATEGORIES + [None])

    # summary
    sub.add_parser("summary", help="Unread summary per chat")

    # scopes
    sub.add_parser("scopes", help="Show active scope claims")

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
        "scopes": _cli_scopes,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
