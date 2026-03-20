#!/usr/bin/env python3
"""
wrap_tracker.py — Session Wrap Assessment Persistence

Persists /cca-wrap self-assessments (grade, wins, losses, test counts)
to a JSONL file so trends are visible across sessions.

Storage: wrap_assessments.jsonl (append-only JSONL)
Each entry: session, grade, wins, losses, test_count, timestamp, etc.

Usage:
    # Log a wrap assessment
    python3 wrap_tracker.py log 89 A --wins "Built tests" "Fixed bug" --losses "None" --tests 3475

    # Show recent assessments
    python3 wrap_tracker.py recent [N]

    # Show stats
    python3 wrap_tracker.py stats

    # Show trend
    python3 wrap_tracker.py trend

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(SCRIPT_DIR, "wrap_assessments.jsonl")

VALID_GRADES = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"]

GRADE_VALUES = {
    "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7,
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Storage ────────────────────────────────────────────────────────────────

def load_assessments(path=DEFAULT_PATH):
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _append_entry(entry, path=DEFAULT_PATH):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


# ── Core Operations ─────────────────────────────────────────────────────────

def log_assessment(
    session,
    grade,
    wins,
    losses,
    test_count,
    test_suites=None,
    commits=None,
    next_different=None,
    path=DEFAULT_PATH,
):
    if grade not in VALID_GRADES:
        raise ValueError(f"Invalid grade: {grade}. Must be one of {VALID_GRADES}")

    entry = {
        "session": session,
        "grade": grade,
        "wins": wins,
        "losses": losses,
        "test_count": test_count,
        "timestamp": _now_iso(),
    }
    if test_suites is not None:
        entry["test_suites"] = test_suites
    if commits is not None:
        entry["commits"] = commits
    if next_different is not None:
        entry["next_different"] = next_different

    _append_entry(entry, path)
    return entry


# ── Queries ──────────────────────────────────────────────────────────────────

def get_by_session(session_id, path=DEFAULT_PATH):
    for entry in load_assessments(path):
        if entry.get("session") == session_id:
            return entry
    return None


def get_stats(path=DEFAULT_PATH):
    entries = load_assessments(path)
    if not entries:
        return {"total_sessions": 0, "grade_distribution": {}, "latest_test_count": 0, "test_count_growth": 0}

    grade_dist = {}
    for e in entries:
        g = e.get("grade", "?")
        base = g[0]  # Group A-/A together as A, B+/B/B- as B
        grade_dist[base] = grade_dist.get(base, 0) + 1

    first_tc = entries[0].get("test_count", 0)
    last_tc = entries[-1].get("test_count", 0)

    return {
        "total_sessions": len(entries),
        "grade_distribution": grade_dist,
        "latest_test_count": last_tc,
        "test_count_growth": last_tc - first_tc,
    }


def get_trend(path=DEFAULT_PATH, window=5):
    entries = load_assessments(path)
    if not entries:
        return {"direction": "unknown", "recent_grades": []}

    recent = entries[-window:]
    grades = [e.get("grade", "C") for e in recent]
    values = [GRADE_VALUES.get(g, 2.0) for g in grades]

    if len(values) < 2:
        return {"direction": "unknown", "recent_grades": grades}

    # Simple linear trend: compare first half avg to second half avg
    mid = len(values) // 2
    first_half = sum(values[:mid]) / mid
    second_half = sum(values[mid:]) / (len(values) - mid)
    delta = second_half - first_half

    if delta > 0.3:
        direction = "improving"
    elif delta < -0.3:
        direction = "declining"
    else:
        direction = "stable"

    return {
        "direction": direction,
        "recent_grades": grades,
        "avg_grade_value": round(sum(values) / len(values), 2),
    }


# ── Formatting ───────────────────────────────────────────────────────────────

def format_for_init(path=DEFAULT_PATH, n=5):
    entries = load_assessments(path)
    if not entries:
        return ""

    recent = entries[-n:]
    lines = [f"Last {len(recent)} sessions:"]
    for e in recent:
        s = e.get("session", "?")
        g = e.get("grade", "?")
        tc = e.get("test_count", "?")
        wins_preview = e.get("wins", [])[:2]
        wins_str = ", ".join(wins_preview)
        if len(e.get("wins", [])) > 2:
            wins_str += "..."
        lines.append(f"  S{s}: {g} | {tc} tests | {wins_str}")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("wrap_tracker.py — Session Wrap Assessment Tracker")
        print()
        print("Commands:")
        print("  log <session> <grade> --wins W1 W2 --losses L1 --tests N  Log assessment")
        print("  recent [N]                                                 Show recent")
        print("  stats                                                      Show stats")
        print("  trend                                                      Show trend")
        return

    cmd = sys.argv[1]

    if cmd == "log":
        if len(sys.argv) < 4:
            print("Usage: log <session> <grade> --wins ... --losses ... --tests N")
            sys.exit(1)
        session = int(sys.argv[2])
        grade = sys.argv[3]
        wins, losses = [], []
        test_count = 0
        i = 4
        mode = None
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--wins":
                mode = "wins"
            elif arg == "--losses":
                mode = "losses"
            elif arg == "--tests":
                mode = "tests"
            elif mode == "wins":
                wins.append(arg)
            elif mode == "losses":
                losses.append(arg)
            elif mode == "tests":
                test_count = int(arg)
                mode = None
            i += 1
        entry = log_assessment(session, grade, wins, losses, test_count)
        print(f"Logged: S{session} grade={grade} tests={test_count}")

    elif cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        entries = load_assessments()
        for e in entries[-n:]:
            print(f"S{e.get('session', '?')}: {e.get('grade', '?')} | "
                  f"{e.get('test_count', '?')} tests | "
                  f"Wins: {', '.join(e.get('wins', []))}")

    elif cmd == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "trend":
        trend = get_trend()
        print(f"Trend: {trend['direction']}")
        print(f"Recent grades: {' -> '.join(trend.get('recent_grades', []))}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
