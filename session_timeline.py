#!/usr/bin/env python3
"""
session_timeline.py — Unified session timeline aggregator.

Combines data from multiple tracking modules into a single per-session view:
- wrap_tracker: session grade, wins, losses, test count
- trial_tracker: MT validation trials
- loop_health: health metrics, regressions
- init_benchmarker: init performance metrics

All modules now use canonical session IDs (via session_id.py), making
cross-module correlation reliable.

CLI:
    python3 session_timeline.py recent [N]     # Last N sessions (default 10)
    python3 session_timeline.py session S101   # Deep dive on one session
    python3 session_timeline.py stats          # Aggregate statistics
    python3 session_timeline.py json [N]       # JSON output

Stdlib only. No external dependencies.
"""

import json
import sys
from pathlib import Path

from session_id import normalize as normalize_session_id, extract_number

PROJECT_ROOT = Path(__file__).resolve().parent


def _load_jsonl(path: Path) -> list[dict]:
    """Load entries from a JSONL file."""
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _session_id_from_entry(entry: dict) -> str | None:
    """Extract canonical session ID from any entry format."""
    # Try canonical field first
    sid = entry.get("session_id")
    if sid:
        try:
            return normalize_session_id(sid)
        except (ValueError, TypeError):
            pass

    # Fall back to "session" field (int or string)
    s = entry.get("session")
    if s is not None:
        try:
            return normalize_session_id(s)
        except (ValueError, TypeError):
            pass

    return None


def load_wrap_data() -> dict[str, dict]:
    """Load wrap_tracker assessments keyed by session ID."""
    path = PROJECT_ROOT / "wrap_assessments.jsonl"
    result = {}
    for entry in _load_jsonl(path):
        sid = _session_id_from_entry(entry)
        if sid:
            result[sid] = {
                "grade": entry.get("grade"),
                "wins": entry.get("wins", []),
                "losses": entry.get("losses", []),
                "test_count": entry.get("test_count", 0),
                "test_suites": entry.get("test_suites"),
                "commits": entry.get("commits"),
                "timestamp": entry.get("timestamp"),
            }
    return result


def load_trial_data() -> dict[str, list[dict]]:
    """Load trial_tracker results grouped by session ID."""
    path = PROJECT_ROOT / ".cca-trial-results.jsonl"
    result: dict[str, list[dict]] = {}
    for entry in _load_jsonl(path):
        sid = _session_id_from_entry(entry)
        if sid:
            trial = {
                "mt_id": entry.get("mt_id"),
                "result": entry.get("result"),
                "commits": entry.get("commits", 0),
                "tests_added": entry.get("tests_added", 0),
            }
            result.setdefault(sid, []).append(trial)
    return result


def load_health_data() -> dict[str, dict]:
    """Load loop_health records keyed by session ID."""
    path = PROJECT_ROOT / ".cca-loop-health.jsonl"
    result = {}
    for entry in _load_jsonl(path):
        sid = _session_id_from_entry(entry)
        if sid:
            result[sid] = {
                "grade": entry.get("grade"),
                "test_pass": entry.get("test_pass", 0),
                "test_fail": entry.get("test_fail", 0),
                "duration_secs": entry.get("duration_secs", 0),
                "error_type": entry.get("error_type"),
            }
    return result


def load_benchmark_data() -> dict[str, dict]:
    """Load init_benchmarker metrics keyed by session ID."""
    path = PROJECT_ROOT / ".cca-init-benchmarks.jsonl"
    result = {}
    for entry in _load_jsonl(path):
        sid = _session_id_from_entry(entry)
        if sid:
            result[sid] = {
                "init_type": entry.get("init_type"),
                "time_to_first_commit_min": entry.get("time_to_first_commit_min"),
                "total_commits": entry.get("total_commits"),
                "new_tests": entry.get("new_tests"),
                "quality_issues": entry.get("quality_issues"),
            }
    return result


def build_timeline(n: int | None = None) -> list[dict]:
    """Build unified timeline from all data sources.

    Returns list of session dicts sorted by session number descending.
    Each dict has: session_id, session_num, wrap, trials, health, benchmark.
    """
    wrap = load_wrap_data()
    trials = load_trial_data()
    health = load_health_data()
    bench = load_benchmark_data()

    # Collect all known session IDs
    all_sids = set()
    all_sids.update(wrap.keys())
    all_sids.update(trials.keys())
    all_sids.update(health.keys())
    all_sids.update(bench.keys())

    timeline = []
    for sid in all_sids:
        try:
            num = extract_number(sid)
        except (ValueError, TypeError):
            continue

        entry = {
            "session_id": sid,
            "session_num": num,
            "wrap": wrap.get(sid),
            "trials": trials.get(sid, []),
            "health": health.get(sid),
            "benchmark": bench.get(sid),
        }
        timeline.append(entry)

    # Sort by session number descending (most recent first)
    timeline.sort(key=lambda x: x["session_num"], reverse=True)

    if n is not None:
        timeline = timeline[:n]

    return timeline


def get_session(session_id) -> dict | None:
    """Get all data for a specific session."""
    sid = normalize_session_id(session_id)
    timeline = build_timeline()
    for entry in timeline:
        if entry["session_id"] == sid:
            return entry
    return None


def get_stats() -> dict:
    """Aggregate statistics across all sessions."""
    timeline = build_timeline()
    if not timeline:
        return {"total_sessions": 0}

    grades = []
    total_tests = 0
    total_commits = 0
    trial_passes = 0
    trial_fails = 0

    for entry in timeline:
        w = entry.get("wrap")
        if w:
            if w.get("grade"):
                grades.append(w["grade"])
            total_tests = max(total_tests, w.get("test_count", 0))
            if w.get("commits"):
                total_commits += w["commits"]

        for t in entry.get("trials", []):
            if t.get("result") == "pass":
                trial_passes += 1
            elif t.get("result") == "fail":
                trial_fails += 1

    grade_values = {
        "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7,
    }
    grade_nums = [grade_values.get(g, 0) for g in grades if g in grade_values]
    avg_grade = round(sum(grade_nums) / len(grade_nums), 2) if grade_nums else 0

    return {
        "total_sessions": len(timeline),
        "sessions_with_wraps": len(grades),
        "avg_grade_value": avg_grade,
        "latest_test_count": total_tests,
        "trial_passes": trial_passes,
        "trial_fails": trial_fails,
        "session_range": f"S{timeline[-1]['session_num']}-S{timeline[0]['session_num']}",
    }


# === Formatting ===

def format_timeline_row(entry: dict) -> str:
    """Format a single timeline entry as a compact row."""
    sid = entry["session_id"]
    w = entry.get("wrap") or {}
    h = entry.get("health") or {}
    trials = entry.get("trials", [])
    b = entry.get("benchmark") or {}

    grade = w.get("grade", h.get("grade", "-"))
    tests = w.get("test_count", 0)
    commits = w.get("commits", b.get("total_commits", "-"))
    wins_count = len(w.get("wins", []))

    trial_str = ""
    if trials:
        passes = sum(1 for t in trials if t.get("result") == "pass")
        fails = sum(1 for t in trials if t.get("result") == "fail")
        mts = set(t.get("mt_id", "?") for t in trials)
        trial_str = f" | Trials: {passes}P/{fails}F ({','.join(mts)})"

    health_str = ""
    if h.get("error_type"):
        health_str = f" | Error: {h['error_type']}"

    return f"  {sid}: {grade} | {tests} tests | {commits} commits | {wins_count} wins{trial_str}{health_str}"


def format_session_detail(entry: dict) -> str:
    """Format detailed view of a single session."""
    lines = [f"=== {entry['session_id']} ==="]

    w = entry.get("wrap")
    if w:
        lines.append(f"\nWrap Assessment:")
        lines.append(f"  Grade: {w.get('grade', '?')}")
        lines.append(f"  Tests: {w.get('test_count', '?')}")
        if w.get("commits"):
            lines.append(f"  Commits: {w['commits']}")
        if w.get("wins"):
            lines.append(f"  Wins: {', '.join(w['wins'][:5])}")
        if w.get("losses"):
            lines.append(f"  Losses: {', '.join(w['losses'][:5])}")

    trials = entry.get("trials", [])
    if trials:
        lines.append(f"\nTrials ({len(trials)}):")
        for t in trials:
            lines.append(f"  {t.get('mt_id', '?')}: {t.get('result', '?')} "
                        f"({t.get('commits', 0)} commits, {t.get('tests_added', 0)} tests)")

    h = entry.get("health")
    if h:
        lines.append(f"\nLoop Health:")
        lines.append(f"  Grade: {h.get('grade', '?')}")
        lines.append(f"  Tests: {h.get('test_pass', 0)}/{h.get('test_pass', 0) + h.get('test_fail', 0)}")
        dur = h.get("duration_secs", 0)
        lines.append(f"  Duration: {dur // 60}m{dur % 60:02d}s")
        if h.get("error_type"):
            lines.append(f"  Error: {h['error_type']}")

    b = entry.get("benchmark")
    if b:
        lines.append(f"\nBenchmark:")
        lines.append(f"  Init type: {b.get('init_type', '?')}")
        lines.append(f"  Time to first commit: {b.get('time_to_first_commit_min', '?')} min")
        lines.append(f"  Quality issues: {b.get('quality_issues', '?')}")

    return "\n".join(lines)


# === CLI ===

def main():
    args = sys.argv[1:]
    if not args:
        args = ["recent"]

    cmd = args[0]

    if cmd == "recent":
        n = int(args[1]) if len(args) > 1 else 10
        timeline = build_timeline(n)
        if not timeline:
            print("No session data found.")
            return
        print(f"Last {len(timeline)} sessions:")
        for entry in timeline:
            print(format_timeline_row(entry))

    elif cmd == "session":
        if len(args) < 2:
            print("Usage: session_timeline.py session <session_id>")
            sys.exit(1)
        entry = get_session(args[1])
        if entry:
            print(format_session_detail(entry))
        else:
            print(f"No data found for session {args[1]}")

    elif cmd == "stats":
        stats = get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif cmd == "json":
        n = int(args[1]) if len(args) > 1 else 10
        timeline = build_timeline(n)
        print(json.dumps(timeline, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: session_timeline.py [recent|session|stats|json] [args]")
        sys.exit(1)


if __name__ == "__main__":
    main()
