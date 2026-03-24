#!/usr/bin/env python3
"""Session prompt-to-outcome tracker for CCA self-learning (MT-10).

Tracks what each session planned vs what it delivered.
Persists to JSONL for cross-session trend analysis.
One file = one job.

Usage:
    python3 session_outcome_tracker.py record <session_id> [--planned "task1,task2"] [--completed "task1"] [--commits N] [--tests-added N] [--tests-total N]
    python3 session_outcome_tracker.py show <session_id>
    python3 session_outcome_tracker.py trend [--last N]
    python3 session_outcome_tracker.py parse-state <session_state_path>
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional


# Default store location
DEFAULT_STORE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "session_outcomes.jsonl"
)


class SessionOutcome:
    """One session's planned vs actual outcome."""

    def __init__(
        self,
        session_id: int,
        chat_type: str = "solo",
        planned_tasks: Optional[list] = None,
        completed_tasks: Optional[list] = None,
        blocked_tasks: Optional[list] = None,
        blockers: Optional[list] = None,
        commits: int = 0,
        tests_added: int = 0,
        tests_total: int = 0,
        grade: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        timestamp: Optional[str] = None,
    ):
        self.session_id = session_id
        self.chat_type = chat_type
        self.planned_tasks = planned_tasks or []
        self.completed_tasks = completed_tasks or []
        self.blocked_tasks = blocked_tasks or []
        self.blockers = blockers or []
        self.commits = commits
        self.tests_added = tests_added
        self.tests_total = tests_total
        self.grade = grade
        self.duration_minutes = duration_minutes
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "chat_type": self.chat_type,
            "planned_tasks": self.planned_tasks,
            "completed_tasks": self.completed_tasks,
            "blocked_tasks": self.blocked_tasks,
            "blockers": self.blockers,
            "commits": self.commits,
            "tests_added": self.tests_added,
            "tests_total": self.tests_total,
            "grade": self.grade,
            "duration_minutes": self.duration_minutes,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionOutcome":
        return cls(
            session_id=d.get("session_id", 0),
            chat_type=d.get("chat_type", "solo"),
            planned_tasks=d.get("planned_tasks", []),
            completed_tasks=d.get("completed_tasks", []),
            blocked_tasks=d.get("blocked_tasks", []),
            blockers=d.get("blockers", []),
            commits=d.get("commits", 0),
            tests_added=d.get("tests_added", 0),
            tests_total=d.get("tests_total", 0),
            grade=d.get("grade"),
            duration_minutes=d.get("duration_minutes"),
            timestamp=d.get("timestamp"),
        )


class OutcomeStore:
    """Append-only JSONL store for session outcomes."""

    def __init__(self, path: str = DEFAULT_STORE_PATH):
        self.path = path

    def append(self, outcome: SessionOutcome) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(outcome.to_dict()) + "\n")

    def load_all(self) -> list:
        if not os.path.exists(self.path):
            return []
        outcomes = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    outcomes.append(SessionOutcome.from_dict(d))
                except (json.JSONDecodeError, KeyError):
                    continue
        return outcomes

    def load_last(self, n: int) -> list:
        all_outcomes = self.load_all()
        return all_outcomes[-n:] if len(all_outcomes) >= n else all_outcomes

    def get_by_session_id(self, session_id: int) -> Optional[SessionOutcome]:
        outcomes = self.load_all()
        result = None
        for o in outcomes:
            if o.session_id == session_id:
                result = o  # last one wins (dedup)
        return result


def parse_session_state_planned(content: str) -> list:
    """Extract planned/next tasks from SESSION_STATE.md content."""
    tasks = []
    in_next = False
    for line in content.split("\n"):
        if "**Next (prioritized):**" in line:
            in_next = True
            continue
        if in_next:
            # Match numbered items like "1. **MT-22 SUPERVISED TRIAL**: ..."
            m = re.match(r"\s*\d+\.\s+\*\*(.+?)\*\*", line)
            if m:
                tasks.append(m.group(1).strip() + ": " + line.split("**:")[-1].strip().rstrip(".") if "**:" in line else m.group(1).strip())
            elif line.strip().startswith("---") or (line.strip().startswith("##") and line.strip() != ""):
                break
            elif line.strip() == "":
                # Allow blank lines within section
                continue
    return tasks


def parse_session_state_completed(content: str) -> list:
    """Extract completed tasks from SESSION_STATE.md content."""
    tasks = []
    in_done = False
    for line in content.split("\n"):
        if "**What was done this session" in line:
            in_done = True
            continue
        if in_done:
            # Match bullet items like "- **MT-22 Phase 1 COMPLETE**: ..."
            m = re.match(r"\s*-\s+\*\*(.+?)\*\*", line)
            if m:
                tasks.append(m.group(1).strip())
            elif line.strip().startswith("**Next") or line.strip().startswith("---"):
                break
    return tasks


def parse_session_id(content: str) -> Optional[int]:
    """Extract session number from SESSION_STATE.md content."""
    m = re.search(r"Session\s+(\d+)\s*[—\-]", content)
    if m:
        return int(m.group(1))
    return None


def count_session_commits(session_id: int, repo_dir: str = ".") -> int:
    """Count git commits with the session prefix (e.g., 'S133:')."""
    prefix = f"S{session_id}:"
    result = subprocess.run(
        ["git", "log", "--oneline", "-50"],
        capture_output=True, text=True, cwd=repo_dir
    )
    if result.returncode != 0:
        return 0
    return sum(1 for line in result.stdout.strip().split("\n") if prefix in line)


def record_from_session_state(
    state_path: str,
    session_id: Optional[int] = None,
    tests_added: int = 0,
    tests_total: int = 0,
    store_path: str = DEFAULT_STORE_PATH,
    repo_dir: str = ".",
) -> Optional[SessionOutcome]:
    """Auto-record a session outcome by reading SESSION_STATE.md + git log.

    Called by /cca-wrap to automatically capture the session's outcome.
    Returns the recorded SessionOutcome, or None if session ID not found.
    """
    with open(state_path) as f:
        content = f.read()

    sid = session_id or parse_session_id(content)
    if sid is None:
        return None

    planned = parse_session_state_planned(content)
    completed = parse_session_state_completed(content)
    commits = count_session_commits(sid, repo_dir)
    rate = compute_completion_rate(planned, completed)
    grade = compute_session_grade(rate, commits, tests_added)

    outcome = SessionOutcome(
        session_id=sid,
        planned_tasks=planned,
        completed_tasks=completed,
        commits=commits,
        tests_added=tests_added,
        tests_total=tests_total,
        grade=grade,
    )

    store = OutcomeStore(store_path)
    store.append(outcome)
    return outcome


def compute_completion_rate(planned: list, completed: list) -> float:
    """Fraction of planned tasks that were completed. Capped at 1.0."""
    if not planned:
        return 1.0
    return min(len(completed) / len(planned), 1.0)


def compute_session_grade(
    completion_rate: float, commits: int, tests_added: int
) -> str:
    """Compute a letter grade from session metrics.

    Scoring:
    - Completion rate: 0-40 points (40% weight)
    - Commits: 0-30 points (30% weight)
    - Tests added: 0-30 points (30% weight)

    Grade thresholds: A+ >= 90, A >= 75, B+ >= 65, B >= 50, C >= 30, D < 30
    """
    # Completion score: 0-40
    completion_score = completion_rate * 40

    # Commit score: 0-30 (5+ commits = full marks)
    commit_score = min(commits / 5, 1.0) * 30

    # Test score: 0-30 (30+ tests = full marks)
    test_score = min(tests_added / 30, 1.0) * 30

    total = completion_score + commit_score + test_score

    if total >= 90:
        return "A+"
    elif total >= 75:
        return "A"
    elif total >= 65:
        return "B+"
    elif total >= 50:
        return "B"
    elif total >= 30:
        return "C"
    else:
        return "D"


def trend_report(outcomes: list) -> dict:
    """Generate trend analytics from a list of SessionOutcomes."""
    if not outcomes:
        return {
            "total_sessions": 0,
            "avg_commits": 0,
            "avg_tests_added": 0,
            "avg_completion_rate": 0,
            "grade_distribution": {},
        }

    total = len(outcomes)
    avg_commits = sum(o.commits for o in outcomes) / total
    avg_tests = sum(o.tests_added for o in outcomes) / total

    # Completion rates
    rates = []
    for o in outcomes:
        if o.planned_tasks:
            rates.append(compute_completion_rate(o.planned_tasks, o.completed_tasks))
    avg_rate = sum(rates) / len(rates) if rates else 0

    # Grade distribution
    grade_dist = defaultdict(int)
    for o in outcomes:
        if o.grade:
            grade_dist[o.grade] += 1

    return {
        "total_sessions": total,
        "avg_commits": avg_commits,
        "avg_tests_added": avg_tests,
        "avg_completion_rate": avg_rate,
        "grade_distribution": dict(grade_dist),
    }


# --- Analysis functions (Get Smarter pillar) ---

GRADE_ORDER = {"D": 0, "C": 1, "B": 2, "B+": 3, "A": 4, "A+": 5}


def detect_recurring_blockers(outcomes: list) -> list:
    """Find blockers that appear in 2+ sessions.

    Returns list of {"blocker": str, "count": int, "sessions": list[int]}.
    """
    if not outcomes:
        return []
    blocker_map = defaultdict(list)
    for o in outcomes:
        for b in (o.blockers or []):
            blocker_map[b.lower()].append(o.session_id)
    return sorted(
        [
            {"blocker": k, "count": len(v), "sessions": v}
            for k, v in blocker_map.items()
            if len(v) >= 2
        ],
        key=lambda x: x["count"],
        reverse=True,
    )


def detect_task_type_success(outcomes: list) -> list:
    """Analyze success rates by task type prefix (e.g., MT-22, MT-10).

    Tasks not matching MT-N pattern are grouped under "other".
    Returns list of {"type": str, "planned": int, "completed": int, "success_rate": float}.
    """
    if not outcomes:
        return []
    type_stats = defaultdict(lambda: {"planned": 0, "completed": 0})

    for o in outcomes:
        planned_types = defaultdict(int)
        completed_types = defaultdict(int)

        for t in (o.planned_tasks or []):
            mt = _extract_mt_prefix(t)
            planned_types[mt] += 1

        for t in (o.completed_tasks or []):
            mt = _extract_mt_prefix(t)
            completed_types[mt] += 1

        for mt, count in planned_types.items():
            type_stats[mt]["planned"] += count
        for mt, count in completed_types.items():
            type_stats[mt]["completed"] += count

    result = []
    for mt, stats in type_stats.items():
        if stats["planned"] > 0:
            result.append({
                "type": mt,
                "planned": stats["planned"],
                "completed": stats["completed"],
                "success_rate": min(stats["completed"] / stats["planned"], 1.0),
            })
    return sorted(result, key=lambda x: x["success_rate"])


def _extract_mt_prefix(task: str) -> str:
    """Extract MT-N prefix from a task string, or 'other'."""
    m = re.match(r"(MT-\d+)", task)
    return m.group(1) if m else "other"


def detect_productivity_trend(outcomes: list) -> dict:
    """Detect if commits, tests, and grades are trending up/down/stable.

    Uses simple comparison of first-half vs second-half averages.
    Needs at least 2 outcomes for trend detection.
    """
    if len(outcomes) < 2:
        return {
            "commits_trend": "insufficient_data",
            "tests_trend": "insufficient_data",
            "grade_trend": "insufficient_data",
            "session_count": len(outcomes),
        }

    mid = len(outcomes) // 2
    first_half = outcomes[:mid]
    second_half = outcomes[mid:]

    def avg(items, attr):
        vals = [getattr(i, attr) for i in items]
        return sum(vals) / len(vals) if vals else 0

    def grade_avg(items):
        vals = [GRADE_ORDER.get(i.grade, 2) for i in items if i.grade]
        return sum(vals) / len(vals) if vals else 2

    commits_first = avg(first_half, "commits")
    commits_second = avg(second_half, "commits")
    tests_first = avg(first_half, "tests_added")
    tests_second = avg(second_half, "tests_added")
    grade_first = grade_avg(first_half)
    grade_second = grade_avg(second_half)

    threshold = 0.2  # 20% change = significant

    def trend(first, second):
        if first == 0 and second == 0:
            return "stable"
        if first == 0:
            return "up"
        change = (second - first) / max(first, 1)
        if change > threshold:
            return "up"
        elif change < -threshold:
            return "down"
        return "stable"

    def grade_trend(first, second):
        diff = second - first
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        return "stable"

    return {
        "commits_trend": trend(commits_first, commits_second),
        "tests_trend": trend(tests_first, tests_second),
        "grade_trend": grade_trend(grade_first, grade_second),
        "avg_commits_recent": round(commits_second, 1),
        "avg_tests_recent": round(tests_second, 1),
        "session_count": len(outcomes),
    }


def generate_recommendations(outcomes: list) -> list:
    """Generate actionable recommendations from outcome patterns.

    Returns list of recommendation strings, prioritized by impact.
    """
    if not outcomes:
        return []

    recs = []

    # 1. Recurring blockers
    blockers = detect_recurring_blockers(outcomes)
    for b in blockers:
        recs.append(
            f"Recurring blocker: '{b['blocker']}' appeared in {b['count']} sessions "
            f"({b['sessions']}). Fix the root cause to unblock future work."
        )

    # 2. Low success rate task types
    type_success = detect_task_type_success(outcomes)
    for ts in type_success:
        if ts["success_rate"] < 0.5 and ts["planned"] >= 2:
            recs.append(
                f"MT type '{ts['type']}' has low completion rate "
                f"({ts['success_rate']:.0%}, {ts['completed']}/{ts['planned']}). "
                f"Break these tasks into smaller pieces or address blockers."
            )

    # 3. Productivity trends
    trend = detect_productivity_trend(outcomes)
    if trend["commits_trend"] == "down":
        recs.append(
            "Commits per session declining. Sessions may be getting less productive "
            "or tasks more complex. Consider smaller task scopes."
        )
    if trend["tests_trend"] == "down":
        recs.append(
            "Tests per session declining. Maintain TDD discipline — tests are "
            "the primary quality signal."
        )
    if trend.get("grade_trend") == "declining":
        recs.append(
            "Session grades declining. Review recent sessions for scope creep, "
            "blockers, or context degradation."
        )

    return recs


def analyze_outcomes(outcomes: list) -> dict:
    """Top-level analysis: combines all detectors into one report.

    Returns a JSON-serializable dict suitable for session context injection.
    """
    return {
        "recurring_blockers": detect_recurring_blockers(outcomes),
        "task_type_success": detect_task_type_success(outcomes),
        "productivity_trend": detect_productivity_trend(outcomes),
        "recommendations": generate_recommendations(outcomes),
    }


def main():
    """CLI interface."""
    if len(sys.argv) < 2:
        print("Usage: session_outcome_tracker.py [record|show|trend|parse-state] ...")
        sys.exit(1)

    cmd = sys.argv[1]
    store = OutcomeStore()

    if cmd == "record":
        if len(sys.argv) < 3:
            print("Usage: record <session_id> [--planned ...] [--completed ...] [--commits N] [--tests-added N] [--tests-total N]")
            sys.exit(1)
        sid = int(sys.argv[2])
        kwargs = {"session_id": sid}
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--planned" and i + 1 < len(args):
                kwargs["planned_tasks"] = [t.strip() for t in args[i + 1].split(",")]
                i += 2
            elif args[i] == "--completed" and i + 1 < len(args):
                kwargs["completed_tasks"] = [t.strip() for t in args[i + 1].split(",")]
                i += 2
            elif args[i] == "--commits" and i + 1 < len(args):
                kwargs["commits"] = int(args[i + 1])
                i += 2
            elif args[i] == "--tests-added" and i + 1 < len(args):
                kwargs["tests_added"] = int(args[i + 1])
                i += 2
            elif args[i] == "--tests-total" and i + 1 < len(args):
                kwargs["tests_total"] = int(args[i + 1])
                i += 2
            else:
                i += 1

        planned = kwargs.get("planned_tasks", [])
        completed = kwargs.get("completed_tasks", [])
        rate = compute_completion_rate(planned, completed)
        kwargs["grade"] = compute_session_grade(
            rate, kwargs.get("commits", 0), kwargs.get("tests_added", 0)
        )
        outcome = SessionOutcome(**kwargs)
        store.append(outcome)
        print(f"Recorded session {sid}: grade={outcome.grade}, {len(completed)}/{len(planned)} tasks, {outcome.commits} commits, +{outcome.tests_added} tests")

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: show <session_id>")
            sys.exit(1)
        sid = int(sys.argv[2])
        outcome = store.get_by_session_id(sid)
        if outcome:
            print(json.dumps(outcome.to_dict(), indent=2))
        else:
            print(f"No record for session {sid}")

    elif cmd == "trend":
        n = 10
        if "--last" in sys.argv:
            idx = sys.argv.index("--last")
            if idx + 1 < len(sys.argv):
                n = int(sys.argv[idx + 1])
        outcomes = store.load_last(n)
        report = trend_report(outcomes)
        print(json.dumps(report, indent=2))

    elif cmd == "auto-record":
        # Auto-record from SESSION_STATE.md — designed for /cca-wrap integration
        state_path = sys.argv[2] if len(sys.argv) > 2 else "SESSION_STATE.md"
        tests_added = 0
        tests_total = 0
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--tests-added" and i + 1 < len(args):
                tests_added = int(args[i + 1])
                i += 2
            elif args[i] == "--tests-total" and i + 1 < len(args):
                tests_total = int(args[i + 1])
                i += 2
            elif not args[i].startswith("--"):
                state_path = args[i]
                i += 1
            else:
                i += 1
        outcome = record_from_session_state(
            state_path, tests_added=tests_added, tests_total=tests_total
        )
        if outcome:
            print(f"Auto-recorded S{outcome.session_id}: grade={outcome.grade}, "
                  f"{len(outcome.completed_tasks)}/{len(outcome.planned_tasks)} tasks, "
                  f"{outcome.commits} commits, +{outcome.tests_added} tests")
        else:
            print("Could not parse session ID from SESSION_STATE.md")
            sys.exit(1)

    elif cmd == "analyze":
        n = 10
        if "--last" in sys.argv:
            idx = sys.argv.index("--last")
            if idx + 1 < len(sys.argv):
                n = int(sys.argv[idx + 1])
        outcomes = store.load_last(n)
        report = analyze_outcomes(outcomes)
        print(json.dumps(report, indent=2))

    elif cmd == "parse-state":
        if len(sys.argv) < 3:
            print("Usage: parse-state <session_state_path>")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            content = f.read()
        planned = parse_session_state_planned(content)
        completed = parse_session_state_completed(content)
        print(f"Planned ({len(planned)}):")
        for t in planned:
            print(f"  - {t}")
        print(f"\nCompleted ({len(completed)}):")
        for t in completed:
            print(f"  - {t}")
        rate = compute_completion_rate(planned, completed)
        print(f"\nCompletion rate: {rate:.0%}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
