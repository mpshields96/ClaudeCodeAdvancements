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
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import cca_internal_queue as ciq
import cross_chat_queue as ccq


ALL_CHAT_IDS = ["desktop", "cli1", "cli2", "terminal", "codex"]

# Kalshi chat IDs — routed through cross_chat_queue instead of internal queue
KALSHI_CHAT_IDS = {"km", "kr"}

# Map from cca_comm target IDs to cross_chat_queue sender/target IDs
# CCA desktop -> cross_chat uses "cca" as sender
KALSHI_NAMES = {"km": "Kalshi Main", "kr": "Kalshi Research"}


def is_kalshi_target(target: str) -> bool:
    """Check if target is a Kalshi chat (routes via cross_chat_queue)."""
    return target in KALSHI_CHAT_IDS


def all_valid_targets() -> list:
    """Return all valid targets (internal CCA + Kalshi)."""
    return list(ciq.VALID_CHATS.keys()) + list(KALSHI_CHAT_IDS)


def _qpath() -> str:
    """Get the queue path. Resolves at call time so tests can override DEFAULT_QUEUE_PATH."""
    return ciq.DEFAULT_QUEUE_PATH


def detect_chat_id() -> str:
    """Auto-detect which chat we are based on env var or context.

    Detection order:
    1. CCA_CHAT_ID env var (explicit, always wins)
    2. TMUX_PANE env var (in tmux = terminal worker)
    3. TERM_PROGRAM env var (Terminal.app / iTerm2 = terminal)
    4. Fallback: "desktop" with stderr warning
    """
    env_id = os.environ.get("CCA_CHAT_ID", "").strip()
    if env_id and env_id in ciq.VALID_CHATS:
        return env_id

    # Heuristic: if we're in tmux or a terminal emulator, we're likely a CLI worker
    tmux_pane = os.environ.get("TMUX_PANE", "")
    term_program = os.environ.get("TERM_PROGRAM", "")

    if tmux_pane or term_program in ("Apple_Terminal", "iTerm.app", "iTerm2"):
        # We're in a terminal but don't know which CLI worker
        print(
            "WARNING: CCA_CHAT_ID not set. Cannot determine which CCA identity you are.\n"
            "  Set it with: export CCA_CHAT_ID=cli1  (or cli2 / codex)\n"
            "  Or specify target: python3 cca_comm.py inbox cli1\n",
            file=sys.stderr,
        )
        return "desktop"  # Still default, but user is warned

    return "desktop"


def _target_name(target: str) -> str:
    """Get display name for any target (internal or Kalshi)."""
    if target in ciq.VALID_CHATS:
        return ciq.VALID_CHATS[target]
    return KALSHI_NAMES.get(target, target)


def cmd_inbox(args):
    """Check inbox for a specific chat."""
    target = args[0] if args else detect_chat_id()
    if target not in ciq.VALID_CHATS and not is_kalshi_target(target):
        print(f"Unknown chat: {target}. Valid: {all_valid_targets()}")
        return

    if is_kalshi_target(target):
        # Read from cross_chat_queue — messages targeted at this Kalshi chat
        unread = ccq.get_unread(target, ccq.DEFAULT_QUEUE_PATH)
    else:
        unread = ciq.get_unread(target, _qpath())

    if not unread:
        print(f"No unread messages for {_target_name(target)}.")
        return
    print(f"Inbox for {_target_name(target)} ({len(unread)} unread):\n")
    for msg in sorted(unread, key=lambda m: (ciq.VALID_PRIORITIES + ccq.VALID_PRIORITIES).index(m.get("priority", "low")) if m.get("priority", "low") in ciq.VALID_PRIORITIES else 3):
        print(f"  [{msg['priority'].upper()}] {msg.get('subject', '')}")
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
    if is_kalshi_target(target):
        ccq.send_message("cca", target, message, category="fyi", path=ccq.DEFAULT_QUEUE_PATH)
    else:
        ciq.send_message(me, target, message, category="fyi", path=_qpath())
    print(f"Sent to {_target_name(target)}: {message}")


BMAD_CONTEXT_CAP = 400  # words — compression threshold per BMAD party-mode research


def cmd_task(args):
    """Assign a task to another chat. Clears only OLD stale messages (>2h), preserves recent ones."""
    if len(args) < 2:
        print("Usage: task <target> <task_description>")
        return
    target = args[0]
    task = " ".join(args[1:])

    # BMAD context cap: warn if task exceeds 400 words (compression threshold)
    word_count = len(task.split())
    if word_count > BMAD_CONTEXT_CAP:
        print(f"BMAD context cap: task is {word_count} words (cap {BMAD_CONTEXT_CAP}). Consider trimming.")
    me = detect_chat_id()

    if is_kalshi_target(target):
        # Route through cross_chat_queue for Kalshi chats
        ccq.send_message("cca", target, task, priority="high",
                        category="action_item", path=ccq.DEFAULT_QUEUE_PATH)
        print(f"Task assigned to {_target_name(target)}: {task}")
        return

    # Internal CCA queue — clear stale messages first
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=2)).isoformat()
    stale = ciq.get_unread(target, _qpath())
    stale_old = [m for m in stale if m.get("created_at", "9999") < cutoff]
    if stale_old:
        for m in stale_old:
            ciq.acknowledge(m["id"], _qpath())
        print(f"Cleared {len(stale_old)} stale message(s) from {_target_name(target)} inbox.")
    ciq.send_message(me, target, task, priority="high", category="handoff", path=_qpath())
    print(f"Task assigned to {_target_name(target)}: {task}")


def _check_claim_conflicts(sender: str, scope: str, files: list, queue_path: str) -> list:
    """Check if a scope claim would conflict with existing active scopes.

    Checks both file-level conflicts (via check_scope_conflict) and
    subject-level overlap (same scope string already claimed by another chat).

    Returns list of conflicting scope claims (empty = safe to proceed).
    """
    conflicts = []

    # File-level conflict check
    if files:
        conflicts = ciq.check_scope_conflict(sender, files, queue_path)

    # Subject-level overlap: check if another chat already owns this scope
    active = ciq.get_active_scopes(queue_path)
    for claim in active:
        if claim.get("sender") == sender:
            continue
        claim_subject = claim.get("subject", "").lower()
        if scope.lower() == claim_subject or scope.lower() in claim_subject or claim_subject in scope.lower():
            # Avoid duplicate entries if already found via file check
            if claim not in conflicts:
                conflicts.append(claim)

    return conflicts


def cmd_claim(args):
    """Claim scope on a file or module. Checks for conflicts first."""
    if not args:
        print("Usage: claim <scope_description> [file1,file2,...]")
        return
    scope = args[0]
    files = args[1].split(",") if len(args) > 1 else None
    me = detect_chat_id()

    # Check for scope conflicts before claiming
    conflicts = _check_claim_conflicts(me, scope, files or [], _qpath())
    if conflicts:
        print(f"SCOPE CONFLICT DETECTED — cannot claim '{scope}':")
        for c in conflicts:
            owner = ciq.VALID_CHATS.get(c.get("sender", ""), c.get("sender", ""))
            print(f"  {owner} already owns: {c.get('subject', 'unknown')}")
        print("Resolve the conflict before claiming. Claim NOT sent.")
        return

    for target in ciq.VALID_CHATS:
        if target != me:
            ciq.send_message(me, target, scope, category="scope_claim",
                           priority="high", files=files or [], path=_qpath())
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
            ciq.send_message(me, target, scope, category="scope_release", path=_qpath())
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
    ciq.send_message(me, "desktop", f"WRAP: {summary}", category="handoff",
                    priority="high", path=_qpath())
    print(f"Wrap summary sent to Desktop: {summary}")


def cmd_ack(args):
    """Acknowledge all messages."""
    me = args[0] if args else detect_chat_id()
    count = ciq.acknowledge_all(me, _qpath())
    print(f"Acknowledged {count} messages for {ciq.VALID_CHATS.get(me, me)}.")


def _get_bridge_status() -> Any | None:
    """Load tri-chat bridge status if the helper is available."""
    try:
        from bridge_status import collect_bridge_status
    except ImportError:
        return None

    try:
        return collect_bridge_status()
    except OSError:
        return None


def _format_bridge_age(age_hours: float | None) -> str:
    """Compact bridge age formatting for status output."""
    if age_hours is None:
        return "missing"
    if age_hours < 1:
        return f"{int(age_hours * 60)}m"
    if age_hours < 48:
        return f"{age_hours:.1f}h"
    return f"{age_hours / 24.0:.1f}d"


def _print_bridge_snapshot(status: Any) -> None:
    """Print a compact bridge-health summary."""
    print("\nBRIDGE STATUS:")
    print(f"  Overall: {status.overall.upper()}")
    for lane in status.lanes:
        state = "missing" if not lane.exists else _format_bridge_age(lane.age_hours)
        print(f"  {lane.name}: {state}")

    if status.attention:
        print("  Attention:")
        for item in status.attention:
            print(f"    - {item}")


def _format_bridge_report(status: Any) -> str:
    """Render the detailed bridge report."""
    from bridge_status import format_report

    return format_report(status)


def cmd_status(args):
    """Show full hivemind status (internal CCA + Kalshi chats)."""
    summary = ciq.get_unread_summary(_qpath())
    scopes = ciq.get_active_scopes(_qpath())

    if summary:
        print("UNREAD MESSAGES (CCA Internal):")
        for chat_id, counts in summary.items():
            name = ciq.VALID_CHATS.get(chat_id, chat_id)
            parts = [f"{counts['total']} total"]
            for p in ciq.VALID_PRIORITIES:
                if p in counts:
                    parts.append(f"{counts[p]} {p}")
            print(f"  {name}: {', '.join(parts)}")
    else:
        print("No unread internal messages.")

    # Kalshi cross-chat queue status
    kalshi_unread = {}
    for kid in KALSHI_CHAT_IDS:
        msgs = ccq.get_unread(kid, ccq.DEFAULT_QUEUE_PATH)
        if msgs:
            kalshi_unread[kid] = len(msgs)
    # Also check messages FROM Kalshi to CCA
    cca_from_kalshi = ccq.get_unread("cca", ccq.DEFAULT_QUEUE_PATH)
    if cca_from_kalshi:
        kalshi_unread["cca (from Kalshi)"] = len(cca_from_kalshi)

    if kalshi_unread:
        print("\nUNREAD MESSAGES (Kalshi Cross-Chat):")
        for kid, count in kalshi_unread.items():
            name = KALSHI_NAMES.get(kid, kid)
            print(f"  {name}: {count} unread")

    print()
    if scopes:
        print(f"ACTIVE SCOPES ({len(scopes)}):")
        for s in scopes:
            sender = ciq.VALID_CHATS.get(s.get("sender", ""), s.get("sender", ""))
            print(f"  {sender}: {s['subject']}")
    else:
        print("No active scope claims.")

    bridge_status = _get_bridge_status()
    if bridge_status is not None:
        _print_bridge_snapshot(bridge_status)
    else:
        print("\nBRIDGE STATUS:")
        print("  Unavailable.")


def cmd_bridge(args):
    """Show the detailed tri-chat bridge status report."""
    bridge_status = _get_bridge_status()
    if bridge_status is None:
        print("Bridge status unavailable.")
        return
    print(_format_bridge_report(bridge_status).rstrip())


def cmd_question(args):
    """Send a question to another chat — reactive pair pattern (BMAD).

    Unlike 'say' (FYI), a question signals that desktop must reply this session.
    Usage: question <target> "question text"
    """
    if len(args) < 2:
        print("Usage: question <target> <question>")
        return
    target = args[0]
    question = " ".join(args[1:])
    me = detect_chat_id()
    if is_kalshi_target(target):
        ccq.send_message("cca", target, question, category="question", path=ccq.DEFAULT_QUEUE_PATH)
    else:
        ciq.send_message(me, target, question, category="question", path=_qpath())
    print(f"Question sent to {_target_name(target)} [needs reply this session]: {question}")


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
            ciq.send_message(me, target, message, category="fyi", path=_qpath())
            count += 1
    print(f"Broadcast to {count} chats: {message}")


def cmd_shutdown(args):
    """Send shutdown signal to a worker chat. Worker should run /cca-wrap-worker and exit."""
    if not args:
        print("Usage: shutdown <target>  (e.g., shutdown cli1)")
        return
    target = args[0]
    me = detect_chat_id()
    ciq.send_message(me, target, "SHUTDOWN: Run /cca-wrap-worker and exit.",
                    priority="critical", category="handoff", path=_qpath())
    print(f"Shutdown signal sent to {ciq.VALID_CHATS.get(target, target)}.")


def _get_recent_commits(n: int = 10) -> list[dict]:
    """Get recent git commits as list of {hash, message} dicts."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            capture_output=True, text=True, timeout=5,
            cwd=SCRIPT_DIR,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split(" ", 1)
            commits.append({
                "hash": parts[0],
                "message": parts[1] if len(parts) > 1 else "",
            })
        return commits
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_crashed_workers() -> list[dict]:
    """Detect crashed workers via crash_recovery module."""
    try:
        import crash_recovery
        scopes = ciq.get_active_scopes(_qpath())
        return crash_recovery.detect_crashed_workers(scopes)
    except ImportError:
        return []


def get_queue_stats(queue_path: str = None) -> dict:
    """Get queue throughput statistics.

    Returns dict with: total_messages, by_category, by_sender
    """
    if queue_path is None:
        queue_path = _qpath()
    msgs = ciq._load_queue(queue_path)
    by_category = {}
    by_sender = {}
    for msg in msgs:
        cat = msg.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        sender = msg.get("sender", "unknown")
        by_sender[sender] = by_sender.get(sender, 0) + 1
    return {
        "total_messages": len(msgs),
        "by_category": by_category,
        "by_sender": by_sender,
    }


def cmd_context(args):
    """Show worker context: recent commits, active scopes, queue stats, crash status.

    Usage: context [n]  — where n is number of recent commits to show (default 10)
    """
    n = int(args[0]) if args else 10

    # Recent commits
    commits = _get_recent_commits(n)
    if commits:
        print(f"RECENT COMMITS ({len(commits)}):")
        for c in commits:
            print(f"  {c['hash']} {c['message']}")
    else:
        print("RECENT COMMITS: none found")

    print()

    # Active scopes
    scopes = ciq.get_active_scopes(_qpath())
    if scopes:
        print(f"ACTIVE SCOPES ({len(scopes)}):")
        for s in scopes:
            sender = ciq.VALID_CHATS.get(s.get("sender", ""), s.get("sender", ""))
            print(f"  {sender}: {s['subject']}")
    else:
        print("No active scope claims.")

    print()

    # Queue stats
    stats = get_queue_stats()
    print(f"QUEUE STATS: {stats['total_messages']} total messages")
    if stats["by_category"]:
        parts = [f"{cat}={count}" for cat, count in sorted(stats["by_category"].items())]
        print(f"  Categories: {', '.join(parts)}")
    if stats["by_sender"]:
        parts = [f"{s}={count}" for s, count in sorted(stats["by_sender"].items())]
        print(f"  Senders: {', '.join(parts)}")

    print()

    # Crash detection
    crashed = _get_crashed_workers()
    if crashed:
        print(f"CRASHED WORKERS ({len(crashed)}):")
        for c in crashed:
            print(f"  {c['chat_id']}: scope '{c.get('scope', 'unknown')}'")
        print("  Run: python3 crash_recovery.py run")
    else:
        print("No crashed workers detected.")


COMMANDS = {
    "inbox": cmd_inbox,
    "say": cmd_say,
    "task": cmd_task,
    "question": cmd_question,
    "claim": cmd_claim,
    "release": cmd_release,
    "done": cmd_done,
    "ack": cmd_ack,
    "status": cmd_status,
    "bridge": cmd_bridge,
    "broadcast": cmd_broadcast,
    "assign": cmd_task,  # Alias: "assign" = "task" (used in /cca-auto-desktop docs)
    "shutdown": cmd_shutdown,
    "context": cmd_context,
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
        print("  bridge                  Show detailed bridge lane freshness")
        print("  broadcast <msg>         Send to all other chats")
        print("  context [n]             Show recent commits, scopes, queue stats")
        print()
        print("Set CCA_CHAT_ID env var to identify yourself (desktop/cli1/cli2/terminal/codex)")
        print(f"Current: {detect_chat_id()}")
        sys.exit(1)

    cmd = sys.argv[1]
    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
