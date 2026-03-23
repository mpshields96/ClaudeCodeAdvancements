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
