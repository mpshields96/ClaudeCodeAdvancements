#!/usr/bin/env python3
"""
cca_comm.py — Simple Communication Wrappers for CCA Hivemind

Wraps cca_internal_queue.py with easy one-liner commands for common
hivemind communication patterns. Designed to be memorable and fast.

Usage:
    python3 cca_comm.py inbox                    # Check your inbox (auto-detects chat ID)
    python3 cca_comm.py inbox cli1               # Check cli1's inbox
    python3 cca_comm.py say cli1 "message"       # Send FYI to cli1
    python3 cca_comm.py task cli1 "do X"         # Assign task to cli1
    python3 cca_comm.py claim "cca-loop"         # Claim scope on a file/module
    python3 cca_comm.py release "cca-loop"       # Release scope claim
    python3 cca_comm.py done "summary"           # Send wrap summary to desktop
    python3 cca_comm.py ack                      # Acknowledge all messages
    python3 cca_comm.py status                   # Show all queues + scopes
    python3 cca_comm.py broadcast "message"      # Send to all other chats

Auto-detection: If CCA_CHAT_ID env var is set, uses that. Otherwise
tries to detect from context (desktop app vs terminal).

Stdlib only. No external dependencies.
"""

import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import cca_internal_queue as ciq


ALL_CHAT_IDS = ["desktop", "cli1", "cli2", "terminal"]


def detect_chat_id() -> str:
    """Auto-detect which chat we are based on env var or context."""
    env_id = os.environ.get("CCA_CHAT_ID", "").strip()
    if env_id and env_id in ciq.VALID_CHATS:
        return env_id
    # Default: if running in Terminal.app, likely cli1/cli2
    # If running in Desktop Claude Code, likely desktop
    # Can't reliably distinguish — default to desktop
    return "desktop"


def cmd_inbox(args):
    """Check inbox for a specific chat."""
    target = args[0] if args else detect_chat_id()
    if target not in ciq.VALID_CHATS:
        print(f"Unknown chat: {target}. Valid: {list(ciq.VALID_CHATS.keys())}")
        return
    unread = ciq.get_unread(target)
    if not unread:
        print(f"No unread messages for {ciq.VALID_CHATS[target]}.")
        return
    print(f"Inbox for {ciq.VALID_CHATS[target]} ({len(unread)} unread):\n")
    for msg in sorted(unread, key=lambda m: ciq.VALID_PRIORITIES.index(m.get("priority", "low"))):
        print(f"  [{msg['priority'].upper()}] {msg['subject']}")
        if msg.get("body"):
            body_lines = msg["body"].split("\n")
            for line in body_lines[:3]:
                print(f"    {line}")
            if len(body_lines) > 3:
                print(f"    ... ({len(body_lines) - 3} more lines)")
        print()


def cmd_say(args):
    """Send a message to another chat."""
    if len(args) < 2:
        print("Usage: say <target> <message>")
        return
    target = args[0]
    message = " ".join(args[1:])
    me = detect_chat_id()
    msg = ciq.send_message(me, target, message, category="fyi")
    print(f"Sent to {ciq.VALID_CHATS[target]}: {message}")


def cmd_task(args):
    """Assign a task to another chat."""
    if len(args) < 2:
        print("Usage: task <target> <task_description>")
        return
    target = args[0]
    task = " ".join(args[1:])
    me = detect_chat_id()
    msg = ciq.send_message(me, target, task, priority="high", category="handoff")
    print(f"Task assigned to {ciq.VALID_CHATS[target]}: {task}")


def cmd_claim(args):
    """Claim scope on a file or module."""
    if not args:
        print("Usage: claim <scope_description> [file1,file2,...]")
        return
    scope = args[0]
    files = args[1].split(",") if len(args) > 1 else None
    me = detect_chat_id()
    # Send to all other chats
    for target in ciq.VALID_CHATS:
        if target != me:
            ciq.send_message(me, target, scope, category="scope_claim",
                           priority="high", files=files or [])
    print(f"Scope claimed: {scope}")


def cmd_release(args):
    """Release a scope claim."""
    if not args:
        print("Usage: release <scope_description>")
        return
    scope = args[0]
    me = detect_chat_id()
    for target in ciq.VALID_CHATS:
        if target != me:
            ciq.send_message(me, target, scope, category="scope_release")
    print(f"Scope released: {scope}")


def cmd_done(args):
    """Send wrap summary to desktop coordinator."""
    if not args:
        print("Usage: done <summary>")
        return
    summary = " ".join(args)
    me = detect_chat_id()
    if me == "desktop":
        print("You ARE desktop. Use /cca-wrap instead.")
        return
    ciq.send_message(me, "desktop", f"WRAP: {summary}", category="handoff", priority="high")
    print(f"Wrap summary sent to Desktop: {summary}")


def cmd_ack(args):
    """Acknowledge all messages."""
    me = args[0] if args else detect_chat_id()
    count = ciq.acknowledge_all(me)
    print(f"Acknowledged {count} messages for {ciq.VALID_CHATS.get(me, me)}.")


def cmd_status(args):
    """Show full hivemind status."""
    summary = ciq.get_unread_summary()
    scopes = ciq.get_active_scopes()

    if summary:
        print("UNREAD MESSAGES:")
        for chat_id, counts in summary.items():
            name = ciq.VALID_CHATS.get(chat_id, chat_id)
            parts = [f"{counts['total']} total"]
            for p in ciq.VALID_PRIORITIES:
                if p in counts:
                    parts.append(f"{counts[p]} {p}")
            print(f"  {name}: {', '.join(parts)}")
    else:
        print("No unread messages.")

    print()
    if scopes:
        print(f"ACTIVE SCOPES ({len(scopes)}):")
        for s in scopes:
            sender = ciq.VALID_CHATS.get(s.get("sender", ""), s.get("sender", ""))
            print(f"  {sender}: {s['subject']}")
    else:
        print("No active scope claims.")


def cmd_broadcast(args):
    """Send a message to all other chats."""
    if not args:
        print("Usage: broadcast <message>")
        return
    message = " ".join(args)
    me = detect_chat_id()
    count = 0
    for target in ciq.VALID_CHATS:
        if target != me:
            ciq.send_message(me, target, message, category="fyi")
            count += 1
    print(f"Broadcast to {count} chats: {message}")


COMMANDS = {
    "inbox": cmd_inbox,
    "say": cmd_say,
    "task": cmd_task,
    "claim": cmd_claim,
    "release": cmd_release,
    "done": cmd_done,
    "ack": cmd_ack,
    "status": cmd_status,
    "broadcast": cmd_broadcast,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("cca_comm.py — Simple CCA Hivemind Communication")
        print()
        print("Commands:")
        print("  inbox [chat_id]         Check inbox (default: auto-detect)")
        print("  say <target> <msg>      Send message to another chat")
        print("  task <target> <task>    Assign task (high priority)")
        print("  claim <scope> [files]   Claim scope on files/modules")
        print("  release <scope>         Release scope claim")
        print("  done <summary>          Send wrap summary to desktop")
        print("  ack [chat_id]           Acknowledge all messages")
        print("  status                  Show all queues + scopes")
        print("  broadcast <msg>         Send to all other chats")
        print()
        print("Set CCA_CHAT_ID env var to identify yourself (desktop/cli1/cli2)")
        print(f"Current: {detect_chat_id()}")
        sys.exit(1)

    cmd = sys.argv[1]
    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
