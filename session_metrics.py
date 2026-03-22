#!/usr/bin/env python3
"""session_metrics.py — Aggregate cross-session metrics from CCA data sources.

Pulls data from wrap_tracker, tip_tracker, and apf_session_tracker to provide
unified session analytics. Designed for /cca-report, /cca-dashboard, and CLI use.

Data sources:
    - wrap_assessments.jsonl   — grades, test counts, wins/losses per session
    - advancement_tips.jsonl   — tips generated per session
    - ~/.cca-apf-snapshots.jsonl — APF (action-per-frontier) trends

Usage:
    python3 session_metrics.py summary          # Overall project health
    python3 session_metrics.py session S115     # Single session detail
    python3 session_metrics.py growth           # Test + feature growth over time
    python3 session_metrics.py streaks          # Grade streaks and patterns
    python3 session_metrics.py --json summary   # JSON output for programmatic use

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
WRAP_FILE = SCRIPT_DIR / "wrap_assessments.jsonl"
TIPS_FILE = SCRIPT_DIR / "advancement_tips.jsonl"
APF_FILE = Path.home() / ".cca-apf-snapshots.jsonl"

GRADE_VALUES = {
    "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "D-": 0.7,
}


# ── Data Loading ──────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list:
    """Load a JSONL file, returning list of dicts."""
    if not path.exists():
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


def load_wraps(path: Optional[Path] = None) -> list:
    """Load wrap assessments."""
    return _load_jsonl(path or WRAP_FILE)


def load_tips(path: Optional[Path] = None) -> list:
    """Load advancement tips."""
    return _load_jsonl(path or TIPS_FILE)


def load_apf(path: Optional[Path] = None) -> list:
    """Load APF snapshots."""
    return _load_jsonl(path or APF_FILE)


# ── Metrics ───────────────────────────────────────────────────────────────

@dataclass
class ProjectSummary:
    """Aggregate project health metrics."""
    total_sessions: int = 0
    total_tests: int = 0
    test_growth: int = 0
    avg_grade: float = 0.0
    avg_grade_letter: str = "?"
    grade_distribution: Dict[str, int] = field(default_factory=dict)
    total_tips: int = 0
    implemented_tips: int = 0
    latest_apf: float = 0.0
    session_range: str = ""

    def to_dict(self) -> dict:
        return {
            "total_sessions": self.total_sessions,
            "total_tests": self.total_tests,
            "test_growth": self.test_growth,
            "avg_grade": self.avg_grade,
            "avg_grade_letter": self.avg_grade_letter,
            "grade_distribution": self.grade_distribution,
            "total_tips": self.total_tips,
            "implemented_tips": self.implemented_tips,
            "latest_apf": self.latest_apf,
            "session_range": self.session_range,
        }


def _grade_to_letter(value: float) -> str:
    """Convert numeric grade value back to letter."""
    if value >= 3.85:
        return "A"
    elif value >= 3.5:
        return "A-"
    elif value >= 3.15:
        return "B+"
    elif value >= 2.85:
        return "B"
    elif value >= 2.5:
        return "B-"
    elif value >= 2.15:
        return "C+"
    elif value >= 1.85:
        return "C"
    elif value >= 1.5:
        return "C-"
    elif value >= 1.15:
        return "D+"
    elif value >= 0.85:
        return "D"
    else:
        return "D-"


def get_summary(
    wrap_path: Optional[Path] = None,
    tips_path: Optional[Path] = None,
    apf_path: Optional[Path] = None,
) -> ProjectSummary:
    """Compute aggregate project summary."""
    wraps = load_wraps(wrap_path)
    tips = load_tips(tips_path)
    apf = load_apf(apf_path)

    summary = ProjectSummary()

    if wraps:
        summary.total_sessions = len(wraps)
        summary.total_tests = wraps[-1].get("test_count", 0)
        first_tc = wraps[0].get("test_count", 0)
        summary.test_growth = summary.total_tests - first_tc

        # Grade stats
        grade_values = []
        for w in wraps:
            g = w.get("grade", "C")
            base = g[0]
            summary.grade_distribution[base] = summary.grade_distribution.get(base, 0) + 1
            grade_values.append(GRADE_VALUES.get(g, 2.0))

        if grade_values:
            summary.avg_grade = round(sum(grade_values) / len(grade_values), 2)
            summary.avg_grade_letter = _grade_to_letter(summary.avg_grade)

        first_s = wraps[0].get("session", "?")
        last_s = wraps[-1].get("session", "?")
        summary.session_range = f"S{first_s}-S{last_s}"

    if tips:
        summary.total_tips = len(tips)
        summary.implemented_tips = sum(
            1 for t in tips if t.get("status") == "implemented"
        )

    if apf:
        latest = apf[-1]
        summary.latest_apf = latest.get("apf_percent", 0.0)

    return summary


@dataclass
class SessionDetail:
    """Detailed view of a single session."""
    session_number: int = 0
    grade: str = "?"
    grade_value: float = 0.0
    test_count: int = 0
    test_delta: int = 0  # vs previous session
    wins: list = field(default_factory=list)
    losses: list = field(default_factory=list)
    commits: int = 0
    tips_generated: int = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "session_number": self.session_number,
            "grade": self.grade,
            "grade_value": self.grade_value,
            "test_count": self.test_count,
            "test_delta": self.test_delta,
            "wins": self.wins,
            "losses": self.losses,
            "commits": self.commits,
            "tips_generated": self.tips_generated,
            "timestamp": self.timestamp,
        }


def get_session_detail(
    session_num: int,
    wrap_path: Optional[Path] = None,
    tips_path: Optional[Path] = None,
) -> Optional[SessionDetail]:
    """Get detailed metrics for a specific session."""
    wraps = load_wraps(wrap_path)
    tips = load_tips(tips_path)

    # Find the session
    target = None
    prev = None
    for i, w in enumerate(wraps):
        if w.get("session") == session_num:
            target = w
            if i > 0:
                prev = wraps[i - 1]
            break

    if target is None:
        return None

    detail = SessionDetail(
        session_number=session_num,
        grade=target.get("grade", "?"),
        grade_value=GRADE_VALUES.get(target.get("grade", "C"), 2.0),
        test_count=target.get("test_count", 0),
        wins=target.get("wins", []),
        losses=target.get("losses", []),
        commits=target.get("commits", 0),
        timestamp=target.get("timestamp", ""),
    )

    if prev:
        detail.test_delta = detail.test_count - prev.get("test_count", 0)

    # Count tips from this session
    session_label = f"S{session_num}"
    detail.tips_generated = sum(
        1 for t in tips if t.get("session") == session_label
    )

    return detail


@dataclass
class GrowthMetrics:
    """Test and feature growth over time."""
    data_points: list = field(default_factory=list)  # list of (session, test_count)
    total_growth: int = 0
    avg_growth_per_session: float = 0.0
    peak_session: int = 0
    peak_tests: int = 0

    def to_dict(self) -> dict:
        return {
            "data_points": self.data_points,
            "total_growth": self.total_growth,
            "avg_growth_per_session": self.avg_growth_per_session,
            "peak_session": self.peak_session,
            "peak_tests": self.peak_tests,
        }


def get_growth(wrap_path: Optional[Path] = None) -> GrowthMetrics:
    """Compute test growth trajectory."""
    wraps = load_wraps(wrap_path)
    metrics = GrowthMetrics()

    if not wraps:
        return metrics

    metrics.data_points = [
        (w.get("session", 0), w.get("test_count", 0))
        for w in wraps
    ]

    first_tc = wraps[0].get("test_count", 0)
    last_tc = wraps[-1].get("test_count", 0)
    metrics.total_growth = last_tc - first_tc

    if len(wraps) > 1:
        metrics.avg_growth_per_session = round(
            metrics.total_growth / (len(wraps) - 1), 1
        )

    # Find peak
    for w in wraps:
        tc = w.get("test_count", 0)
        if tc >= metrics.peak_tests:
            metrics.peak_tests = tc
            metrics.peak_session = w.get("session", 0)

    return metrics


@dataclass
class StreakInfo:
    """Grade streak analysis."""
    current_streak_grade: str = "?"
    current_streak_length: int = 0
    longest_a_streak: int = 0
    sessions_since_last_decline: int = 0  # sessions since grade dropped
    recent_trend: str = "unknown"  # improving, stable, declining

    def to_dict(self) -> dict:
        return {
            "current_streak_grade": self.current_streak_grade,
            "current_streak_length": self.current_streak_length,
            "longest_a_streak": self.longest_a_streak,
            "sessions_since_last_decline": self.sessions_since_last_decline,
            "recent_trend": self.recent_trend,
        }


def get_streaks(wrap_path: Optional[Path] = None) -> StreakInfo:
    """Analyze grade streaks and patterns."""
    wraps = load_wraps(wrap_path)
    info = StreakInfo()

    if not wraps:
        return info

    grades = [w.get("grade", "C") for w in wraps]
    base_grades = [g[0] for g in grades]  # A-, B+ -> A, B

    # Current streak (same base grade)
    if base_grades:
        current = base_grades[-1]
        streak = 1
        for g in reversed(base_grades[:-1]):
            if g == current:
                streak += 1
            else:
                break
        info.current_streak_grade = current
        info.current_streak_length = streak

    # Longest A streak
    a_streak = 0
    max_a = 0
    for g in base_grades:
        if g == "A":
            a_streak += 1
            max_a = max(max_a, a_streak)
        else:
            a_streak = 0
    info.longest_a_streak = max_a

    # Sessions since last decline
    values = [GRADE_VALUES.get(g, 2.0) for g in grades]
    decline_idx = -1
    for i in range(len(values) - 1, 0, -1):
        if values[i] < values[i - 1]:
            decline_idx = i
            break
    if decline_idx >= 0:
        info.sessions_since_last_decline = len(values) - 1 - decline_idx
    else:
        info.sessions_since_last_decline = len(values)  # never declined

    # Recent trend (last 5)
    recent = values[-5:] if len(values) >= 5 else values
    if len(recent) >= 2:
        mid = len(recent) // 2
        first_half = sum(recent[:mid]) / mid
        second_half = sum(recent[mid:]) / (len(recent) - mid)
        delta = second_half - first_half
        if delta > 0.3:
            info.recent_trend = "improving"
        elif delta < -0.3:
            info.recent_trend = "declining"
        else:
            info.recent_trend = "stable"

    return info


# ── Formatting ────────────────────────────────────────────────────────────

def format_summary(summary: ProjectSummary) -> str:
    """Human-readable summary."""
    lines = [
        "=== CCA Project Health ===",
        f"Sessions tracked: {summary.total_sessions} ({summary.session_range})",
        f"Tests: {summary.total_tests:,} (+{summary.test_growth:,} growth)",
        f"Avg grade: {summary.avg_grade_letter} ({summary.avg_grade:.2f}/4.0)",
        f"Grade distribution: {summary.grade_distribution}",
        f"Tips: {summary.total_tips} total, {summary.implemented_tips} implemented",
    ]
    if summary.latest_apf > 0:
        lines.append(f"Latest APF: {summary.latest_apf:.1f}%")
    return "\n".join(lines)


def format_session(detail: SessionDetail) -> str:
    """Human-readable session detail."""
    delta_str = f"+{detail.test_delta}" if detail.test_delta >= 0 else str(detail.test_delta)
    lines = [
        f"=== Session S{detail.session_number} ===",
        f"Grade: {detail.grade} ({detail.grade_value:.1f}/4.0)",
        f"Tests: {detail.test_count:,} ({delta_str} from previous)",
        f"Commits: {detail.commits or 'N/A'}",
        f"Tips generated: {detail.tips_generated}",
    ]
    if detail.wins:
        lines.append("Wins:")
        for w in detail.wins:
            lines.append(f"  + {w}")
    if detail.losses:
        lines.append("Losses:")
        for l in detail.losses:
            lines.append(f"  - {l}")
    return "\n".join(lines)


def format_growth(metrics: GrowthMetrics) -> str:
    """Human-readable growth trajectory."""
    lines = [
        "=== Test Growth ===",
        f"Total growth: +{metrics.total_growth:,} tests",
        f"Avg per session: +{metrics.avg_growth_per_session:.0f}",
        f"Peak: S{metrics.peak_session} ({metrics.peak_tests:,} tests)",
    ]
    if metrics.data_points:
        lines.append("Timeline:")
        for s, tc in metrics.data_points[-10:]:
            lines.append(f"  S{s}: {tc:,}")
    return "\n".join(lines)


def format_streaks(info: StreakInfo) -> str:
    """Human-readable streak analysis."""
    return "\n".join([
        "=== Grade Streaks ===",
        f"Current: {info.current_streak_length}x {info.current_streak_grade}",
        f"Longest A streak: {info.longest_a_streak}",
        f"Sessions since decline: {info.sessions_since_last_decline}",
        f"Recent trend: {info.recent_trend}",
    ])


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    json_output = "--json" in args
    args = [a for a in args if a != "--json"]

    if not args:
        print("session_metrics.py — Cross-session analytics")
        print()
        print("Commands:")
        print("  summary          Overall project health")
        print("  session S115     Single session detail")
        print("  growth           Test growth over time")
        print("  streaks          Grade streaks and patterns")
        print("  --json <cmd>     JSON output")
        return

    cmd = args[0]

    if cmd == "summary":
        summary = get_summary()
        if json_output:
            print(json.dumps(summary.to_dict(), indent=2))
        else:
            print(format_summary(summary))

    elif cmd == "session":
        if len(args) < 2:
            print("Usage: session_metrics.py session S115")
            sys.exit(1)
        session_str = args[1].lstrip("Ss")
        try:
            session_num = int(session_str)
        except ValueError:
            print(f"Invalid session: {args[1]}")
            sys.exit(1)
        detail = get_session_detail(session_num)
        if detail is None:
            print(f"No data for session S{session_num}")
            sys.exit(1)
        if json_output:
            print(json.dumps(detail.to_dict(), indent=2))
        else:
            print(format_session(detail))

    elif cmd == "growth":
        metrics = get_growth()
        if json_output:
            print(json.dumps(metrics.to_dict(), indent=2))
        else:
            print(format_growth(metrics))

    elif cmd == "streaks":
        info = get_streaks()
        if json_output:
            print(json.dumps(info.to_dict(), indent=2))
        else:
            print(format_streaks(info))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
