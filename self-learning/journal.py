#!/usr/bin/env python3
"""
journal.py — CCA Self-Learning Journal

Structured append-only event log for tracking session outcomes, review patterns,
and strategy effectiveness. Adapted from YoYo self-evolving agent pattern.

Storage: self-learning/journal.jsonl (one JSON object per line)
Strategy: self-learning/strategy.json (tunable parameters)

Usage:
    # Log a nuclear scan batch
    python3 self-learning/journal.py log nuclear_batch \
        --session 1 --domain nuclear_scan \
        --metrics '{"posts_reviewed": 45, "build": 2, "adapt": 8}' \
        --learnings '["OTel approach better than transcript parsing", "LSP hidden flag"]'

    # Log a session outcome
    python3 self-learning/journal.py log session_outcome \
        --session 14 --domain general \
        --outcome success \
        --notes "Nuclear scan batch 1 complete"

    # Show journal stats
    python3 self-learning/journal.py stats

    # Show recent entries
    python3 self-learning/journal.py recent [N]

    # Dump full journal
    python3 self-learning/journal.py dump
"""

import sys
import os
import json
import argparse
from collections import Counter
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_PATH = os.path.join(SCRIPT_DIR, "journal.jsonl")
STRATEGY_PATH = os.path.join(SCRIPT_DIR, "strategy.json")

VALID_EVENT_TYPES = [
    "nuclear_batch",      # Completed a batch of nuclear post reviews
    "session_outcome",    # End-of-session summary
    "review_verdict",     # Individual post review result
    "strategy_update",    # Strategy config was changed
    "pattern_detected",   # Reflection detected a pattern
    "learning_captured",  # New learning added to LEARNINGS.md
    "build_shipped",      # A BUILD candidate was implemented
    "error",              # Something went wrong
    "pain",               # Something went wrong / wasted time / caused frustration
    "win",                # Something worked well / saved time / produced good results
    # Trading domain (MT-0)
    "bet_placed",         # A bet was placed on a market
    "bet_outcome",        # Bet result: win/loss/void
    "market_research",    # Research session on a market or edge
    "edge_discovered",    # A new tradeable edge was found
    "edge_rejected",      # A research path didn't produce an edge
    "strategy_shift",     # Trading strategy parameter change
    # Trace analysis (MT-7)
    "trace_analysis",     # Transcript pattern analysis results
]

VALID_DOMAINS = [
    "nuclear_scan",
    "memory_system",
    "spec_system",
    "context_monitor",
    "agent_guard",
    "usage_dashboard",
    "reddit_intelligence",
    "self_learning",
    "general",
    "trading",            # MT-0: Kalshi/prediction market trading
]

VALID_OUTCOMES = ["success", "partial", "failure", "skipped"]


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_journal():
    """Load all journal entries. Returns list of dicts."""
    entries = []
    if not os.path.exists(JOURNAL_PATH):
        return entries
    with open(JOURNAL_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _append_entry(entry):
    """Append a single entry to the journal."""
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def _load_strategy():
    """Load strategy config."""
    if not os.path.exists(STRATEGY_PATH):
        return {}
    with open(STRATEGY_PATH, "r") as f:
        return json.load(f)


def _save_strategy(strategy):
    """Save strategy config atomically."""
    tmp = STRATEGY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(strategy, f, indent=2)
        f.write("\n")
    os.replace(tmp, STRATEGY_PATH)


def log_event(event_type, session_id=None, domain="general", outcome=None,
              metrics=None, learnings=None, notes=None, strategy_version=None):
    """Log a structured event to the journal."""
    if event_type not in VALID_EVENT_TYPES:
        print(f"Warning: unknown event_type '{event_type}', logging anyway", file=sys.stderr)

    if domain not in VALID_DOMAINS:
        print(f"Warning: unknown domain '{domain}', logging anyway", file=sys.stderr)

    if outcome and outcome not in VALID_OUTCOMES:
        print(f"Warning: unknown outcome '{outcome}', logging anyway", file=sys.stderr)

    strategy = _load_strategy()
    sv = strategy_version or f"v{strategy.get('version', 0)}"

    entry = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "session_id": session_id,
        "domain": domain,
        "outcome": outcome,
        "metrics": metrics or {},
        "learnings": learnings or [],
        "strategy_version": sv,
        "notes": notes,
    }

    # Strip None values for compact storage
    entry = {k: v for k, v in entry.items() if v is not None}

    _append_entry(entry)
    return entry


def get_stats():
    """Aggregate journal stats."""
    entries = _load_journal()
    if not entries:
        return {"total_entries": 0}

    stats = {
        "total_entries": len(entries),
        "by_event_type": {},
        "by_domain": {},
        "by_outcome": {},
        "sessions_logged": set(),
        "first_entry": entries[0].get("timestamp", "unknown"),
        "last_entry": entries[-1].get("timestamp", "unknown"),
        "total_learnings": 0,
    }

    for e in entries:
        et = e.get("event_type", "unknown")
        stats["by_event_type"][et] = stats["by_event_type"].get(et, 0) + 1

        d = e.get("domain", "unknown")
        stats["by_domain"][d] = stats["by_domain"].get(d, 0) + 1

        o = e.get("outcome")
        if o:
            stats["by_outcome"][o] = stats["by_outcome"].get(o, 0) + 1

        sid = e.get("session_id")
        if sid is not None:
            stats["sessions_logged"].add(sid)

        stats["total_learnings"] += len(e.get("learnings", []))

    stats["sessions_logged"] = sorted(stats["sessions_logged"], key=lambda x: str(x))
    return stats


def get_recent(n=10):
    """Get the N most recent entries."""
    entries = _load_journal()
    return entries[-n:]


def get_entries_by_domain(domain):
    """Filter entries by domain."""
    return [e for e in _load_journal() if e.get("domain") == domain]


def get_all_learnings():
    """Extract all learnings across all entries."""
    learnings = []
    for e in _load_journal():
        for l in e.get("learnings", []):
            learnings.append({
                "learning": l,
                "session": e.get("session_id"),
                "domain": e.get("domain"),
                "timestamp": e.get("timestamp"),
            })
    return learnings


def get_nuclear_metrics():
    """Aggregate nuclear scan specific metrics."""
    entries = [e for e in _load_journal() if e.get("event_type") == "nuclear_batch"]
    if not entries:
        return None

    total = {
        "sessions": len(set(e.get("session_id", 0) for e in entries)),
        "batches": len(entries),
        "posts_reviewed": 0,
        "build": 0,
        "adapt": 0,
        "reference": 0,
        "skip": 0,
        "fast_skip": 0,
    }

    for e in entries:
        m = e.get("metrics", {})
        for key in ["posts_reviewed", "build", "adapt", "reference", "skip", "fast_skip"]:
            total[key] += m.get(key, 0)

    if total["posts_reviewed"] > 0:
        total["build_rate"] = round(total["build"] / total["posts_reviewed"], 3)
        total["adapt_rate"] = round(total["adapt"] / total["posts_reviewed"], 3)
        total["signal_rate"] = round(
            (total["build"] + total["adapt"]) / total["posts_reviewed"], 3
        )

    return total


def get_trading_metrics():
    """Aggregate trading-specific metrics from bet outcomes and research sessions.

    Returns dict with:
    - total_bets, wins, losses, voids, win_rate
    - total_pnl_cents
    - by_market_type: {type: {bets, wins, losses, pnl_cents}}
    - by_strategy: {name: {bets, wins, losses, pnl_cents}}
    - research: {total_sessions, actionable, actionable_rate, edges_discovered, edges_rejected}
    """
    entries = _load_journal()
    outcomes = [e for e in entries if e.get("event_type") == "bet_outcome"]
    research = [e for e in entries if e.get("event_type") == "market_research"]
    edges_found = [e for e in entries if e.get("event_type") == "edge_discovered"]
    edges_nope = [e for e in entries if e.get("event_type") == "edge_rejected"]

    if not outcomes and not research and not edges_found and not edges_nope:
        return None

    total = {
        "total_bets": len(outcomes),
        "wins": 0,
        "losses": 0,
        "voids": 0,
        "total_pnl_cents": 0,
        "by_market_type": {},
        "by_strategy": {},
        "research": {
            "total_sessions": len(research),
            "actionable": 0,
            "edges_discovered": len(edges_found),
            "edges_rejected": len(edges_nope),
        },
    }

    for e in outcomes:
        m = e.get("metrics", {})
        result = m.get("result", "unknown")
        pnl = m.get("pnl_cents", 0)
        mtype = m.get("market_type", "unknown")
        strat = m.get("strategy_name", "unknown")

        if result == "win":
            total["wins"] += 1
        elif result == "loss":
            total["losses"] += 1
        elif result == "void":
            total["voids"] += 1

        total["total_pnl_cents"] += pnl

        # By market type
        if mtype not in total["by_market_type"]:
            total["by_market_type"][mtype] = {"bets": 0, "wins": 0, "losses": 0, "pnl_cents": 0}
        mt = total["by_market_type"][mtype]
        mt["bets"] += 1
        if result == "win":
            mt["wins"] += 1
        elif result == "loss":
            mt["losses"] += 1
        mt["pnl_cents"] += pnl

        # By strategy
        if strat not in total["by_strategy"]:
            total["by_strategy"][strat] = {"bets": 0, "wins": 0, "losses": 0, "pnl_cents": 0}
        st = total["by_strategy"][strat]
        st["bets"] += 1
        if result == "win":
            st["wins"] += 1
        elif result == "loss":
            st["losses"] += 1
        st["pnl_cents"] += pnl

    # Win rate (exclude voids)
    decided = total["wins"] + total["losses"]
    if decided > 0:
        total["win_rate"] = round(total["wins"] / decided, 3)

    # Research effectiveness
    for e in research:
        if e.get("metrics", {}).get("actionable"):
            total["research"]["actionable"] += 1
    if total["research"]["total_sessions"] > 0:
        total["research"]["actionable_rate"] = round(
            total["research"]["actionable"] / total["research"]["total_sessions"], 3
        )

    return total


def get_pain_win_summary():
    """Aggregate pain/win signals for pattern analysis.

    Returns dict with:
    - pain_count, win_count
    - pain_domains, win_domains (Counter by domain)
    - pain_entries, win_entries (raw entries for deeper analysis)
    - ratio: win_count / (pain_count + win_count) if any, else None
    """
    entries = _load_journal()
    pains = [e for e in entries if e.get("event_type") == "pain"]
    wins = [e for e in entries if e.get("event_type") == "win"]

    pain_domains = Counter(e.get("domain", "unknown") for e in pains)
    win_domains = Counter(e.get("domain", "unknown") for e in wins)

    total = len(pains) + len(wins)
    return {
        "pain_count": len(pains),
        "win_count": len(wins),
        "pain_domains": dict(pain_domains),
        "win_domains": dict(win_domains),
        "pain_entries": pains,
        "win_entries": wins,
        "ratio": round(len(wins) / total, 3) if total > 0 else None,
    }


def _cli():
    parser = argparse.ArgumentParser(description="CCA Self-Learning Journal")
    sub = parser.add_subparsers(dest="command")

    # log
    log_p = sub.add_parser("log", help="Log an event")
    log_p.add_argument("event_type", help="Event type")
    log_p.add_argument("--session", type=int, help="Session ID")
    log_p.add_argument("--domain", default="general", help="Domain")
    log_p.add_argument("--outcome", help="Outcome")
    log_p.add_argument("--metrics", help="JSON metrics object")
    log_p.add_argument("--learnings", help="JSON array of learnings")
    log_p.add_argument("--notes", help="Free text notes")

    # stats
    sub.add_parser("stats", help="Show journal stats")

    # recent
    recent_p = sub.add_parser("recent", help="Show recent entries")
    recent_p.add_argument("n", nargs="?", type=int, default=10, help="Number of entries")

    # dump
    sub.add_parser("dump", help="Dump full journal")

    # nuclear
    sub.add_parser("nuclear-stats", help="Nuclear scan metrics")

    # learnings
    sub.add_parser("learnings", help="All captured learnings")

    # pain-win
    sub.add_parser("pain-win", help="Pain/win signal summary")

    # trading-stats
    sub.add_parser("trading-stats", help="Trading metrics summary")

    args = parser.parse_args()

    if args.command == "log":
        metrics = json.loads(args.metrics) if args.metrics else None
        learnings = json.loads(args.learnings) if args.learnings else None
        entry = log_event(
            event_type=args.event_type,
            session_id=args.session,
            domain=args.domain,
            outcome=args.outcome,
            metrics=metrics,
            learnings=learnings,
            notes=args.notes,
        )
        print(json.dumps(entry, indent=2))

    elif args.command == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2, default=list))

    elif args.command == "recent":
        for e in get_recent(args.n):
            print(json.dumps(e))

    elif args.command == "dump":
        for e in _load_journal():
            print(json.dumps(e, indent=2))

    elif args.command == "nuclear-stats":
        nm = get_nuclear_metrics()
        if nm:
            print(json.dumps(nm, indent=2))
        else:
            print("No nuclear scan data yet.")

    elif args.command == "learnings":
        for l in get_all_learnings():
            print(f"[{l['timestamp']}] [{l['domain']}] {l['learning']}")

    elif args.command == "pain-win":
        pw = get_pain_win_summary()
        print(json.dumps({k: v for k, v in pw.items() if k not in ("pain_entries", "win_entries")}, indent=2))

    elif args.command == "trading-stats":
        tm = get_trading_metrics()
        if tm:
            print(json.dumps(tm, indent=2))
        else:
            print("No trading data yet.")

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
