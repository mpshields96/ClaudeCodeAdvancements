#!/usr/bin/env python3
"""
cross_chat_board.py — Unified Cross-Chat Action Board

Shows the state of ALL pending cross-chat items in a single 15-line summary.
Replaces reading 5 separate files with one command.

Usage:
    python3 cross_chat_board.py          # Show full board
    python3 cross_chat_board.py brief    # Init-mode: 8-line summary only
    python3 cross_chat_board.py update   # Write this chat's status to CCA_STATUS.md
    python3 cross_chat_board.py ack REQ-N  # Mark a request delivered

READS:
    ~/.claude/cross-chat/REQUEST_QUEUE.md   — structured request tracker
    ~/.claude/cross-chat/CCA_TO_POLYBOT.md  — CCA deliveries (last entry date)
    ~/.claude/cross-chat/POLYBOT_TO_CCA.md  — Kalshi requests (last entry date)
    ~/.claude/cross-chat/BOT_STATUS.md      — bot health (if monitoring chat writes it)
    ~/.claude/cross-chat/CCA_STATUS.md      — CCA's current focus

WRITES:
    ~/.claude/cross-chat/CCA_STATUS.md      — when run with 'update' flag
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CROSS_CHAT = Path.home() / ".claude" / "cross-chat"
QUEUE_FILE = CROSS_CHAT / "REQUEST_QUEUE.md"
CCA_TO_BOT = CROSS_CHAT / "CCA_TO_POLYBOT.md"
BOT_TO_CCA = CROSS_CHAT / "POLYBOT_TO_CCA.md"
BOT_STATUS = CROSS_CHAT / "BOT_STATUS.md"
CCA_STATUS = CROSS_CHAT / "CCA_STATUS.md"


def parse_pending_requests(path: Path) -> list[dict]:
    """Extract PENDING/IN_PROGRESS items from REQUEST_QUEUE.md."""
    if not path.exists():
        return []
    text = path.read_text()
    items = []
    # Each request block: ### REQ-NNN | PRIORITY | Status: STATUS
    blocks = re.split(r"(?=###\s+REQ-\d+)", text)
    for block in blocks:
        m = re.match(r"###\s+(REQ-\d+)\s*\|\s*(\w+)\s*\|\s*Status:\s*(\w+)", block)
        if not m:
            continue
        req_id, priority, status = m.group(1), m.group(2), m.group(3)
        if status not in ("PENDING", "IN_PROGRESS"):
            continue
        topic_m = re.search(r"Topic:\s*(.+)", block)
        topic = topic_m.group(1).strip() if topic_m else "?"
        date_m = re.search(r"Submitted:\s*(\d{4}-\d{2}-\d{2})", block)
        submitted = date_m.group(1) if date_m else "?"
        items.append({"id": req_id, "priority": priority, "status": status,
                      "topic": topic, "submitted": submitted})
    return items


def last_entry_date(path: Path) -> str:
    """Get the date of the last timestamped entry in a cross-chat file."""
    if not path.exists():
        return "never"
    text = path.read_text()
    dates = re.findall(r"\[(\d{4}-\d{2}-\d{2})", text)
    return dates[-1] if dates else "unknown"


def last_entry_topic(path: Path) -> str:
    """Get the topic of the last entry."""
    if not path.exists():
        return ""
    text = path.read_text()
    # Find last ## [...] entry
    entries = re.findall(r"##\s+\[.+?\]\s+—\s+(.+)", text)
    return entries[-1][:60] if entries else ""


def age_days(date_str: str) -> int:
    """How many days since this date string (YYYY-MM-DD)."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - d).days
    except Exception:
        return -1


def priority_sort_key(item: dict) -> int:
    return {"URGENT": 0, "NORMAL": 1, "BACKGROUND": 2}.get(item["priority"], 3)


def bot_status_summary() -> str:
    """One-line bot health summary from BOT_STATUS.md."""
    if not BOT_STATUS.exists():
        return "BOT_STATUS.md not found — monitoring chat not writing it"
    text = BOT_STATUS.read_text()
    # Look for P&L or status lines
    pnl_m = re.search(r"(P&L|pnl|profit|balance)[:\s]+([^\n]+)", text, re.IGNORECASE)
    if pnl_m:
        return pnl_m.group(0)[:80]
    return text.strip()[:80] if text.strip() else "empty"


def show_board(brief: bool = False) -> None:
    now = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"CROSS-CHAT ACTION BOARD — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    # --- Pending requests ---
    pending = parse_pending_requests(QUEUE_FILE)
    pending.sort(key=priority_sort_key)
    urgent = [r for r in pending if r["priority"] == "URGENT"]
    normal = [r for r in pending if r["priority"] != "URGENT"]

    if urgent:
        print(f"\n!! URGENT ({len(urgent)} items):")
        for r in urgent[:5]:
            age = age_days(r["submitted"])
            age_str = f"{age}d ago" if age >= 0 else ""
            print(f"  {r['id']}: {r['topic'][:50]} [{age_str}]")
    else:
        print("\nURGENT: none")

    if not brief:
        if normal:
            print(f"\nPENDING ({len(normal)} items):")
            for r in normal[:6]:
                age = age_days(r["submitted"])
                age_str = f"{age}d ago" if age >= 0 else ""
                print(f"  {r['id']} [{r['priority']}]: {r['topic'][:45]} [{age_str}]")

    # --- Comms staleness ---
    cca_last = last_entry_date(CCA_TO_BOT)
    bot_last = last_entry_date(BOT_TO_CCA)
    cca_age = age_days(cca_last)
    bot_age = age_days(bot_last)
    cca_topic = last_entry_topic(CCA_TO_BOT)
    bot_topic = last_entry_topic(BOT_TO_CCA)

    print(f"\nCOMMUNICATION STATE:")
    cca_flag = " !! STALE" if cca_age > 2 else ""
    bot_flag = " !! STALE" if bot_age > 1 else ""
    print(f"  CCA → Kalshi: {cca_last} ({cca_age}d ago){cca_flag}")
    if cca_topic:
        print(f"    Last: {cca_topic[:55]}")
    print(f"  Kalshi → CCA: {bot_last} ({bot_age}d ago){bot_flag}")
    if bot_topic:
        print(f"    Last: {bot_topic[:55]}")

    # --- Bot status ---
    if not brief:
        bot_sum = bot_status_summary()
        print(f"\nBOT STATUS: {bot_sum}")

    # --- Action prompt ---
    stale_reqs = [r for r in pending if age_days(r["submitted"]) > 7]
    print(f"\nACTION:")
    if urgent:
        print(f"  → Pick up: {urgent[0]['id']} — {urgent[0]['topic'][:50]}")
    if cca_age > 2:
        print(f"  → CCA delivery stale ({cca_age}d) — write update to CCA_TO_POLYBOT.md")
    if stale_reqs:
        print(f"  → {len(stale_reqs)} requests >7 days old — close or answer stale items")
    if not urgent and cca_age <= 2 and not stale_reqs:
        print("  → Comms healthy — no action needed")

    print(f"{'='*60}\n")


def update_cca_status(focus: str = "") -> None:
    """Write CCA's current state to CCA_STATUS.md."""
    now = datetime.now(timezone.utc)
    template = f"""## CCA STATUS — Updated {now.strftime('%Y-%m-%d %H:%M UTC')}

### CURRENT FOCUS
{focus if focus else '[Not set — run: python3 cross_chat_board.py update "working on X"]'}

### LAST DELIVERY
{last_entry_date(CCA_TO_BOT)} — {last_entry_topic(CCA_TO_BOT)}

### PENDING INTAKE
{len(parse_pending_requests(QUEUE_FILE))} items in REQUEST_QUEUE.md (see cross_chat_board.py for detail)

### ANYTHING CCA NEEDS FROM MONITORING CHAT
[Add blockers or data requests here]

### HOW TO USE THIS FILE
CCA writes at session START and WRAP.
Monitoring chat reads every 3rd cycle (same time as CCA_TO_POLYBOT.md check).
"""
    CCA_STATUS.write_text(template)
    print(f"Updated CCA_STATUS.md at {now.strftime('%Y-%m-%d %H:%M UTC')}")


def mark_delivered(req_id: str) -> None:
    """Mark a REQUEST_QUEUE item as DELIVERED."""
    if not QUEUE_FILE.exists():
        print(f"REQUEST_QUEUE.md not found")
        return
    text = QUEUE_FILE.read_text()
    # Find the block for this ID
    old = f"### {req_id} |"
    if old not in text:
        # Try partial match
        pattern = re.search(rf"###\s+{re.escape(req_id)}\s*\|[^\n]+Status:\s*\w+", text)
        if not pattern:
            print(f"  {req_id} not found in REQUEST_QUEUE.md")
            return
        old_line = pattern.group(0)
    else:
        lines = text.split("\n")
        old_line = next((l for l in lines if l.startswith(f"### {req_id} |")), None)
        if not old_line:
            print(f"  {req_id} not found")
            return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_line = re.sub(r"Status:\s*\w+", f"Status: DELIVERED", old_line)
    new_text = text.replace(old_line, new_line)
    # Add delivery note after the block header
    delivery_note = f"Delivered: {now} by CCA (S258 research delivery)"
    # Insert after the changed line
    new_text = new_text.replace(
        new_line,
        new_line + f"\n{delivery_note}"
    )
    QUEUE_FILE.write_text(new_text)
    print(f"  Marked {req_id} as DELIVERED")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("board", "show"):
        show_board(brief=False)
    elif args[0] == "brief":
        show_board(brief=True)
    elif args[0] == "update":
        focus = " ".join(args[1:]) if len(args) > 1 else ""
        update_cca_status(focus)
    elif args[0] == "ack" and len(args) > 1:
        mark_delivered(args[1])
    else:
        print(f"Usage: cross_chat_board.py [board|brief|update|ack REQ-N]")
