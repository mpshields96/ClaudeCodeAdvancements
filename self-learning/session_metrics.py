#!/usr/bin/env python3
"""session_metrics.py — MT-49 Phase 6: Session-over-session metrics tracker.

Answers the question: "Is CCA getting smarter over time?"

Reads journal.jsonl session_outcome entries and computes trends:
- Grade trend (A/B/C → numeric, linear regression)
- Test velocity (new tests per session)
- Learnings captured per session
- Win/pain ratio per session
- APF (Actionable Per Find) trend
- Principle registry health

Outputs a summary report (dict) and a briefing_text() for /cca-init.

Usage:
    from session_metrics import SessionMetricsTracker

    tracker = SessionMetricsTracker()  # uses default journal path
    report = tracker.summary_report()
    print(tracker.briefing_text())

CLI:
    python3 self-learning/session_metrics.py [--json] [--last N]

Stdlib only. No external dependencies.
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JOURNAL_PATH = os.path.join(SCRIPT_DIR, "journal.jsonl")
DEFAULT_PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")

# Grade → GPA-style numeric mapping
GRADE_MAP = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}

# Minimum slope magnitude to call improving/declining (avoids noise)
TREND_THRESHOLD = 0.05


def grade_to_numeric(grade) -> Optional[float]:
    """Convert letter grade to numeric GPA-style value."""
    if not grade or not isinstance(grade, str):
        return None
    return GRADE_MAP.get(grade.strip())


@dataclass
class MetricsTrend:
    """Result of a trend computation."""
    direction: str  # "improving", "declining", "stable", "insufficient_data"
    slope: float = 0.0
    recent_avg: Optional[float] = None
    values: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "slope": self.slope,
            "recent_avg": self.recent_avg,
            "values": self.values,
        }


def compute_trend_direction(values: List[float]) -> MetricsTrend:
    """Compute trend direction from a series of numeric values.

    Uses simple linear regression (least squares) to determine slope.
    Direction is classified by slope magnitude vs TREND_THRESHOLD.
    """
    if len(values) < 2:
        return MetricsTrend(direction="insufficient_data", values=values)

    n = len(values)
    # Simple linear regression: y = mx + b
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0.0

    # Recent average: last 2 values or all if < 2
    recent_count = min(2, n)
    recent_avg = sum(values[-recent_count:]) / recent_count

    if slope > TREND_THRESHOLD:
        direction = "improving"
    elif slope < -TREND_THRESHOLD:
        direction = "declining"
    else:
        direction = "stable"

    return MetricsTrend(
        direction=direction,
        slope=round(slope, 4),
        recent_avg=round(recent_avg, 4),
        values=values,
    )


@dataclass
class SessionSnapshot:
    """Metrics from a single session extracted from journal."""
    session_id: int
    timestamp: str = ""
    grade: Optional[str] = None
    grade_numeric: Optional[float] = None
    tests_total: Optional[int] = None
    tests_new: Optional[int] = None
    commits: Optional[int] = None
    learnings_count: int = 0
    apf: Optional[float] = None
    outcome: str = ""

    @classmethod
    def from_journal_entry(cls, entry: dict) -> "SessionSnapshot":
        """Build snapshot from a session_outcome journal entry."""
        metrics = entry.get("metrics", {})
        grade = metrics.get("grade")
        learnings = entry.get("learnings", [])

        return cls(
            session_id=entry.get("session_id", 0),
            timestamp=entry.get("timestamp", ""),
            grade=grade,
            grade_numeric=grade_to_numeric(grade),
            tests_total=metrics.get("tests_after") or metrics.get("tests_total"),
            tests_new=metrics.get("tests_new"),
            commits=metrics.get("commits"),
            learnings_count=len(learnings) if isinstance(learnings, list) else 0,
            apf=metrics.get("signal_rate"),
            outcome=entry.get("outcome", ""),
        )


class SessionMetricsTracker:
    """Aggregates journal data into session-over-session metrics."""

    def __init__(
        self,
        journal_path: str = DEFAULT_JOURNAL_PATH,
        principles_path: str = DEFAULT_PRINCIPLES_PATH,
    ):
        self.journal_path = journal_path
        self.principles_path = principles_path
        self.snapshots: List[SessionSnapshot] = []
        self._win_counts: Dict[int, int] = {}
        self._pain_counts: Dict[int, int] = {}
        self._load()

    def _load(self):
        """Load and parse journal entries."""
        if not os.path.exists(self.journal_path):
            return

        raw_entries = []
        with open(self.journal_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Separate session outcomes from win/pain events
        outcome_by_session = {}
        for entry in raw_entries:
            event_type = entry.get("event_type", "")
            sid = entry.get("session_id")

            if event_type == "session_outcome":
                # Keep latest entry per session (dedup)
                outcome_by_session[sid] = entry
            elif event_type == "win" and sid is not None:
                self._win_counts[sid] = self._win_counts.get(sid, 0) + 1
            elif event_type == "pain" and sid is not None:
                self._pain_counts[sid] = self._pain_counts.get(sid, 0) + 1

        # Build snapshots sorted by session_id
        for sid in sorted(outcome_by_session.keys(), key=lambda x: x if isinstance(x, int) else 0):
            snap = SessionSnapshot.from_journal_entry(outcome_by_session[sid])
            self.snapshots.append(snap)

    def grade_trend(self) -> MetricsTrend:
        """Compute trend of session grades over time."""
        values = [s.grade_numeric for s in self.snapshots if s.grade_numeric is not None]
        return compute_trend_direction(values)

    def test_velocity_trend(self) -> MetricsTrend:
        """Compute trend of new tests per session.

        Uses tests_new if available, otherwise computes delta from consecutive
        tests_total values.
        """
        values = []
        prev_total = None
        for s in self.snapshots:
            if s.tests_new is not None:
                values.append(float(s.tests_new))
            elif s.tests_total is not None and prev_total is not None:
                delta = s.tests_total - prev_total
                if delta >= 0:
                    values.append(float(delta))
            if s.tests_total is not None:
                prev_total = s.tests_total
        return compute_trend_direction(values)

    def learnings_trend(self) -> MetricsTrend:
        """Compute trend of learnings captured per session."""
        values = [float(s.learnings_count) for s in self.snapshots]
        return compute_trend_direction(values)

    def apf_trend(self) -> MetricsTrend:
        """Compute APF (Actionable Per Find) trend for scan sessions.

        Filters to values in 0-1 range (valid percentages). Some journal
        entries have signal_rate as a non-percentage metric — skip those.
        """
        values = [s.apf for s in self.snapshots
                  if s.apf is not None and 0 <= s.apf <= 1.0]
        return compute_trend_direction(values)

    def win_pain_ratios(self) -> List[float]:
        """Compute win/pain ratio per session (wins / max(pains, 1))."""
        ratios = []
        for snap in self.snapshots:
            sid = snap.session_id
            wins = self._win_counts.get(sid, 0)
            pains = self._pain_counts.get(sid, 0)
            ratio = wins / max(pains, 1)
            ratios.append(ratio)
        return ratios

    def _load_principles(self) -> Dict[str, int]:
        """Count active and pruned principles."""
        if not os.path.exists(self.principles_path):
            return {"active": 0, "pruned": 0}

        active = 0
        pruned = 0
        with open(self.principles_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    p = json.loads(line)
                    if p.get("pruned", False):
                        pruned += 1
                    else:
                        active += 1
                except json.JSONDecodeError:
                    continue
        return {"active": active, "pruned": pruned}

    def summary_report(self) -> dict:
        """Generate full metrics summary report."""
        if not self.snapshots:
            return {
                "total_sessions": 0,
                "grade_trend": MetricsTrend(direction="insufficient_data").to_dict(),
                "test_velocity_trend": MetricsTrend(direction="insufficient_data").to_dict(),
                "learnings_trend": MetricsTrend(direction="insufficient_data").to_dict(),
                "apf_trend": MetricsTrend(direction="insufficient_data").to_dict(),
                "win_pain_trend": MetricsTrend(direction="insufficient_data").to_dict(),
                "principle_count": self._load_principles(),
                "latest_session": None,
            }

        latest = self.snapshots[-1]
        win_pain = self.win_pain_ratios()

        return {
            "total_sessions": len(self.snapshots),
            "grade_trend": self.grade_trend().to_dict(),
            "test_velocity_trend": self.test_velocity_trend().to_dict(),
            "learnings_trend": self.learnings_trend().to_dict(),
            "apf_trend": self.apf_trend().to_dict(),
            "win_pain_trend": compute_trend_direction(win_pain).to_dict(),
            "principle_count": self._load_principles(),
            "latest_session": {
                "session_id": latest.session_id,
                "grade": latest.grade,
                "tests_total": latest.tests_total,
                "tests_new": latest.tests_new,
                "commits": latest.commits,
            },
        }

    def briefing_text(self) -> str:
        """Generate concise briefing text for /cca-init."""
        report = self.summary_report()

        if report["total_sessions"] == 0:
            return "Session metrics: no data yet."

        lines = [f"Session metrics ({report['total_sessions']} sessions tracked):"]

        # Grade trend
        gt = report["grade_trend"]
        if gt["direction"] != "insufficient_data":
            lines.append(f"  Grades: {gt['direction']} (recent avg {gt['recent_avg']:.1f}/4.3)")

        # Test velocity
        tv = report["test_velocity_trend"]
        if tv["direction"] != "insufficient_data":
            lines.append(f"  Test velocity: {tv['direction']} (recent avg {tv['recent_avg']:.0f} new/session)")

        # Learnings
        lt = report["learnings_trend"]
        if lt["direction"] != "insufficient_data":
            lines.append(f"  Learnings: {lt['direction']} (recent avg {lt['recent_avg']:.1f}/session)")

        # APF
        at = report["apf_trend"]
        if at["direction"] != "insufficient_data":
            lines.append(f"  APF: {at['direction']} (recent avg {at['recent_avg']:.1%})")

        # Principles
        pc = report["principle_count"]
        if pc["active"] > 0:
            lines.append(f"  Principles: {pc['active']} active, {pc['pruned']} pruned")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Session-over-session metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--last", type=int, default=0, help="Show only last N sessions")
    parser.add_argument("--journal", default=DEFAULT_JOURNAL_PATH, help="Journal path")
    args = parser.parse_args()

    tracker = SessionMetricsTracker(journal_path=args.journal)

    if args.json:
        print(json.dumps(tracker.summary_report(), indent=2))
    else:
        print(tracker.briefing_text())
        print()
        report = tracker.summary_report()
        if report["latest_session"]:
            ls = report["latest_session"]
            print(f"Latest: S{ls['session_id']} — grade {ls['grade']}, "
                  f"{ls['tests_new']} new tests, {ls['commits']} commits")


if __name__ == "__main__":
    main()
