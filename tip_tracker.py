#!/usr/bin/env python3
"""
tip_tracker.py — Advancement Tip Persistence + Tracking

Every CCA/Kalshi response ends with "Advancement tip: ..." but these
tips have no persistence. This module captures, stores, and surfaces
them so none are lost across sessions.

Storage: advancement_tips.jsonl (append-only JSONL)
Each tip: id, text, source, session, status, created_at

Usage:
    # Add a tip
    python3 tip_tracker.py add "Use pytest -x" --source cca-desktop --session S89

    # List pending tips
    python3 tip_tracker.py pending

    # Mark as implemented
    python3 tip_tracker.py done <tip_id>

    # Show stats
    python3 tip_tracker.py stats

    # Extract tip from text (for hook integration)
    python3 tip_tracker.py extract "...Advancement tip: Do X..."

Stdlib only. No external dependencies.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TIP_PATH = os.path.join(SCRIPT_DIR, "advancement_tips.jsonl")

VALID_STATUSES = ["pending", "implemented", "skipped"]


def _make_tip_id(text: str) -> str:
    """Generate a short unique ID for a tip."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    content_hash = hashlib.sha256(f"{text}:{ts}".encode()).hexdigest()[:8]
    return f"tip_{ts}_{content_hash}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Storage ────────────────────────────────────────────────────────────────

def load_tips(path: str = DEFAULT_TIP_PATH) -> list[dict]:
    """Load all tips from the JSONL file."""
    if not os.path.exists(path):
        return []
    tips = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                tips.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tips


def _save_tips(tips: list[dict], path: str = DEFAULT_TIP_PATH) -> None:
    """Rewrite the entire tips file (for status updates)."""
    with open(path, "w", encoding="utf-8") as f:
        for tip in tips:
            f.write(json.dumps(tip, separators=(",", ":")) + "\n")


def _append_tip(tip: dict, path: str = DEFAULT_TIP_PATH) -> None:
    """Append a single tip to the file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(tip, separators=(",", ":")) + "\n")


# ── Core Operations ─────────────────────────────────────────────────────────

def add_tip(
    text: str,
    source: str = "unknown",
    session: str = "",
    path: str = DEFAULT_TIP_PATH,
) -> dict:
    """Add a new advancement tip.

    Args:
        text: The tip text (without "Advancement tip:" prefix)
        source: Which chat produced it (cca-desktop, cca-cli1, kalshi-main, etc.)
        session: Session identifier (S89, S104, etc.)
        path: Tips file path

    Returns:
        The tip dict that was written.
    """
    tip = {
        "id": _make_tip_id(text),
        "text": text,
        "source": source,
        "session": session,
        "status": "pending",
        "created_at": _now_iso(),
    }
    _append_tip(tip, path)
    return tip


def update_status(
    tip_id: str,
    status: str,
    path: str = DEFAULT_TIP_PATH,
) -> bool:
    """Update a tip's status. Returns True if found and updated."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    tips = load_tips(path)
    found = False
    for tip in tips:
        if tip.get("id") == tip_id:
            tip["status"] = status
            tip["updated_at"] = _now_iso()
            found = True
            break

    if found:
        _save_tips(tips, path)
    return found


# ── Filtering ──────────────────────────────────────────────────────────────

def get_pending(path: str = DEFAULT_TIP_PATH) -> list[dict]:
    """Get all pending tips."""
    return [t for t in load_tips(path) if t.get("status") == "pending"]


def get_by_source(source: str, path: str = DEFAULT_TIP_PATH) -> list[dict]:
    """Get all tips from a specific source chat."""
    return [t for t in load_tips(path) if t.get("source") == source]


def get_stats(path: str = DEFAULT_TIP_PATH) -> dict:
    """Get tip statistics."""
    tips = load_tips(path)
    stats = {"total": len(tips), "pending": 0, "implemented": 0, "skipped": 0}
    for tip in tips:
        s = tip.get("status", "pending")
        if s in stats:
            stats[s] += 1
    return stats


# ── Extraction ─────────────────────────────────────────────────────────────

def extract_tip(text: str) -> Optional[str]:
    """Extract advancement tip from assistant message text.

    Looks for "Advancement tip: <tip text>" pattern (case-insensitive).
    Returns the tip text or None if not found.
    """
    match = re.search(r'[Aa]dvancement\s+tip:\s*(.+)', text)
    if match:
        return match.group(1).strip()
    return None


# ── Formatting ─────────────────────────────────────────────────────────────

def format_for_init(path: str = DEFAULT_TIP_PATH) -> str:
    """Format pending tips for /cca-init briefing.

    Shows up to 5 tips. Returns empty string if none pending.
    """
    pending = get_pending(path)
    if not pending:
        return ""

    lines = [f"PENDING TIPS ({len(pending)} pending):"]
    for tip in pending[:5]:
        source = tip.get("source", "?")
        session = tip.get("session", "")
        session_str = f" [{session}]" if session else ""
        lines.append(f"  - {tip['text']} ({source}{session_str})")

    if len(pending) > 5:
        lines.append(f"  ...{len(pending) - 5} more")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("tip_tracker.py — Advancement Tip Tracker")
        print()
        print("Commands:")
        print("  add <tip_text> [--source X] [--session S]  Add a tip")
        print("  pending                                     List pending tips")
        print("  done <tip_id>                               Mark as implemented")
        print("  skip <tip_id>                               Mark as skipped")
        print("  stats                                       Show statistics")
        print("  extract <text>                              Extract tip from text")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        text = sys.argv[2] if len(sys.argv) > 2 else ""
        source = "cli"
        session = ""
        for i, arg in enumerate(sys.argv):
            if arg == "--source" and i + 1 < len(sys.argv):
                source = sys.argv[i + 1]
            if arg == "--session" and i + 1 < len(sys.argv):
                session = sys.argv[i + 1]
        if not text:
            print("Usage: add <tip_text>")
            sys.exit(1)
        tip = add_tip(text, source=source, session=session)
        print(f"Added: {tip['id']} — {tip['text']}")

    elif cmd == "pending":
        pending = get_pending()
        if not pending:
            print("No pending tips.")
            return
        print(f"Pending tips ({len(pending)}):\n")
        for tip in pending:
            print(f"  [{tip['id']}] {tip['text']}")
            print(f"    Source: {tip.get('source', '?')} | Session: {tip.get('session', '?')} | {tip['created_at']}")
            print()

    elif cmd == "done":
        if len(sys.argv) < 3:
            print("Usage: done <tip_id>")
            sys.exit(1)
        if update_status(sys.argv[2], "implemented"):
            print(f"Marked as implemented: {sys.argv[2]}")
        else:
            print(f"Tip not found: {sys.argv[2]}")

    elif cmd == "skip":
        if len(sys.argv) < 3:
            print("Usage: skip <tip_id>")
            sys.exit(1)
        if update_status(sys.argv[2], "skipped"):
            print(f"Marked as skipped: {sys.argv[2]}")
        else:
            print(f"Tip not found: {sys.argv[2]}")

    elif cmd == "stats":
        stats = get_stats()
        print(f"Tips: {stats['total']} total, {stats['pending']} pending, "
              f"{stats['implemented']} implemented, {stats['skipped']} skipped")

    elif cmd == "extract":
        text = " ".join(sys.argv[2:])
        tip = extract_tip(text)
        if tip:
            print(f"Extracted: {tip}")
        else:
            print("No advancement tip found in text.")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
