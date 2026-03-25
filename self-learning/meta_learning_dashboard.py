#!/usr/bin/env python3
"""meta_learning_dashboard.py — MT-49 Phase 1: Self-Learning Meta-Analysis.

Tracks the effectiveness of CCA's self-learning system across sessions.
Reads all self-learning JSONL data sources and computes meta-metrics:
- Principle accuracy and freshness
- Session grade trends
- Improvement proposal success rates
- Research delivery ROI
- Journal event coverage

Usage:
    python3 meta_learning_dashboard.py                    # Full report (text)
    python3 meta_learning_dashboard.py --json             # Full report (JSON)
    python3 meta_learning_dashboard.py --brief            # One-line summary
    python3 meta_learning_dashboard.py --data-dir /path   # Custom data directory
"""

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_jsonl(filepath: str) -> list[dict]:
    """Load a JSONL file, skipping malformed lines."""
    entries = []
    if not os.path.exists(filepath):
        return entries
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _laplace_score(success: int, total: int) -> float:
    """Laplace-smoothed success rate: (s+1)/(n+2)."""
    return (success + 1) / (total + 2)


class PrincipleAnalyzer:
    """Analyze principle registry effectiveness."""

    def __init__(self, filepath: str):
        self._entries = _load_jsonl(filepath)

    @property
    def total_principles(self) -> int:
        return len(self._entries)

    @property
    def active_principles(self) -> int:
        return sum(1 for e in self._entries if not e.get("pruned", False))

    @property
    def pruned_principles(self) -> int:
        return sum(1 for e in self._entries if e.get("pruned", False))

    @property
    def average_score(self) -> float:
        active = [e for e in self._entries if not e.get("pruned", False)]
        if not active:
            return 0.0
        scores = [_laplace_score(e.get("success_count", 0), e.get("usage_count", 0))
                  for e in active]
        return sum(scores) / len(scores)

    @property
    def domain_distribution(self) -> dict[str, int]:
        counter = Counter()
        for e in self._entries:
            if not e.get("pruned", False):
                counter[e.get("source_domain", "unknown")] += 1
        return dict(counter)

    def top_principles(self, n: int = 5) -> list[dict]:
        active = [e for e in self._entries if not e.get("pruned", False)]
        scored = [(e, _laplace_score(e.get("success_count", 0), e.get("usage_count", 0)))
                  for e in active]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:n]]

    def stale_principles(self, current_session: int = 169,
                         staleness_threshold: int = 50) -> list[dict]:
        stale = []
        for e in self._entries:
            if e.get("pruned", False):
                continue
            last_used = e.get("last_used_session", 0)
            if current_session - last_used >= staleness_threshold:
                stale.append(e)
        return stale

    def to_dict(self) -> dict:
        return {
            "total": self.total_principles,
            "active": self.active_principles,
            "pruned": self.pruned_principles,
            "average_score": round(self.average_score, 3),
            "domain_distribution": self.domain_distribution,
            "top_5": [{"id": p["id"], "text": p["text"],
                       "score": round(_laplace_score(p.get("success_count", 0),
                                                     p.get("usage_count", 0)), 3)}
                      for p in self.top_principles(5)],
        }


class SessionTrendAnalyzer:
    """Analyze session outcome trends."""

    GRADE_VALUES = {"A+": 4.3, "A": 4.0, "A-": 3.7,
                    "B+": 3.3, "B": 3.0, "B-": 2.7,
                    "C+": 2.3, "C": 2.0, "C-": 1.7,
                    "D": 1.0, "F": 0.0}

    def __init__(self, filepath: str):
        self._entries = _load_jsonl(filepath)
        # Sort by session_id
        self._entries.sort(key=lambda e: e.get("session_id", 0))

    @property
    def total_sessions(self) -> int:
        return len(self._entries)

    @property
    def grade_counts(self) -> dict[str, int]:
        counter = Counter()
        for e in self._entries:
            grade = e.get("grade", "?")
            counter[grade] += 1
        return dict(counter)

    @property
    def trend_direction(self) -> str:
        """Compute grade trend: improving, declining, or stable."""
        if len(self._entries) < 2:
            return "insufficient_data"
        values = [self.GRADE_VALUES.get(e.get("grade", "C"), 2.0)
                  for e in self._entries]
        # Simple: compare first half avg to second half avg
        mid = len(values) // 2
        first_half = sum(values[:mid]) / max(mid, 1)
        second_half = sum(values[mid:]) / max(len(values) - mid, 1)
        diff = second_half - first_half
        if diff > 0.3:
            return "improving"
        elif diff < -0.3:
            return "declining"
        return "stable"

    @property
    def avg_tests_per_session(self) -> float:
        if not self._entries:
            return 0.0
        tests = [e.get("tests_added", 0) for e in self._entries]
        return sum(tests) / len(tests)

    @property
    def avg_commits_per_session(self) -> float:
        if not self._entries:
            return 0.0
        commits = [e.get("commits", 0) for e in self._entries]
        return sum(commits) / len(commits)

    def to_dict(self) -> dict:
        return {
            "total": self.total_sessions,
            "grade_counts": self.grade_counts,
            "trend": self.trend_direction,
            "avg_tests_per_session": round(self.avg_tests_per_session, 1),
            "avg_commits_per_session": round(self.avg_commits_per_session, 1),
        }


class ImprovementTracker:
    """Track improvement proposal outcomes."""

    def __init__(self, filepath: str):
        self._entries = _load_jsonl(filepath)

    @property
    def total_proposals(self) -> int:
        return len(self._entries)

    @property
    def implemented_count(self) -> int:
        return sum(1 for e in self._entries if e.get("status") == "implemented")

    @property
    def success_rate(self) -> Optional[float]:
        implemented = [e for e in self._entries if e.get("status") == "implemented"]
        if not implemented:
            return None
        successes = sum(1 for e in implemented if e.get("outcome") == "success")
        return successes / len(implemented)

    @property
    def pattern_type_distribution(self) -> dict[str, int]:
        counter = Counter()
        for e in self._entries:
            counter[e.get("pattern_type", "unknown")] += 1
        return dict(counter)

    def to_dict(self) -> dict:
        return {
            "total_proposals": self.total_proposals,
            "implemented": self.implemented_count,
            "success_rate": round(self.success_rate, 3) if self.success_rate is not None else None,
            "pattern_types": self.pattern_type_distribution,
        }


class ResearchROITracker:
    """Track research delivery ROI."""

    def __init__(self, filepath: str):
        self._entries = _load_jsonl(filepath)

    @property
    def total_deliveries(self) -> int:
        return len(self._entries)

    @property
    def status_counts(self) -> dict[str, int]:
        counter = Counter()
        for e in self._entries:
            counter[e.get("status", "unknown")] += 1
        return dict(counter)

    @property
    def implementation_rate(self) -> float:
        if not self._entries:
            return 0.0
        implemented = sum(1 for e in self._entries if e.get("status") == "implemented")
        return implemented / len(self._entries)

    def to_dict(self) -> dict:
        return {
            "total_deliveries": self.total_deliveries,
            "status_counts": self.status_counts,
            "implementation_rate": round(self.implementation_rate, 3),
        }


class JournalAnalyzer:
    """Analyze journal event patterns."""

    def __init__(self, filepath: str):
        self._entries = _load_jsonl(filepath)

    @property
    def total_events(self) -> int:
        return len(self._entries)

    @property
    def event_type_counts(self) -> dict[str, int]:
        counter = Counter()
        for e in self._entries:
            counter[e.get("event_type", "unknown")] += 1
        return dict(counter)

    @property
    def domains_covered(self) -> set[str]:
        return {e.get("domain", "unknown") for e in self._entries if e.get("domain")}

    def to_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "event_types": self.event_type_counts,
            "domains_covered": sorted(self.domains_covered),
        }


class MetaLearningDashboard:
    """Top-level dashboard aggregating all self-learning metrics."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Default: self-learning/ for principle/journal data,
            # project root for session outcomes
            self._sl_dir = str(Path(__file__).parent)
            self._root_dir = str(Path(__file__).parent.parent)
        else:
            self._sl_dir = data_dir
            self._root_dir = data_dir

        self._principles = PrincipleAnalyzer(
            os.path.join(self._sl_dir, "principles.jsonl"))
        self._sessions = SessionTrendAnalyzer(
            os.path.join(self._root_dir, "session_outcomes.jsonl"))
        self._improvements = ImprovementTracker(
            os.path.join(self._sl_dir, "improvements.jsonl"))
        self._research = ResearchROITracker(
            os.path.join(self._sl_dir, "research_outcomes.jsonl"))
        self._journal = JournalAnalyzer(
            os.path.join(self._sl_dir, "journal.jsonl"))

    def _compute_health(self) -> str:
        """Compute overall self-learning health."""
        # Need at least some data to assess
        if self._sessions.total_sessions == 0 and self._principles.total_principles == 0:
            return "UNKNOWN"

        score = 0
        checks = 0

        # Principle health
        if self._principles.active_principles > 0:
            checks += 1
            if self._principles.average_score >= 0.5:
                score += 1

        # Session trend
        if self._sessions.total_sessions >= 3:
            checks += 1
            trend = self._sessions.trend_direction
            if trend in ("improving", "stable"):
                score += 1

        # Improvement success
        if self._improvements.success_rate is not None:
            checks += 1
            if self._improvements.success_rate >= 0.5:
                score += 1

        if checks == 0:
            return "UNKNOWN"

        ratio = score / checks
        if ratio >= 0.8:
            return "HEALTHY"
        elif ratio >= 0.5:
            return "MODERATE"
        else:
            return "NEEDS_ATTENTION"

    def _compute_recommendations(self) -> list[str]:
        """Generate actionable recommendations based on data."""
        recs = []

        if self._principles.total_principles == 0:
            recs.append("No principles in registry. Run principle seeding from LEARNINGS.md.")

        if self._principles.active_principles > 0 and self._principles.average_score < 0.4:
            recs.append("Average principle score is low. Review and prune weak principles.")

        if self._sessions.total_sessions > 0 and self._sessions.trend_direction == "declining":
            recs.append("Session grade trend is declining. Investigate recent session failures.")

        if self._improvements.total_proposals > 0 and self._improvements.success_rate is not None:
            if self._improvements.success_rate < 0.5:
                recs.append("Improvement success rate below 50%. Review proposal quality.")

        if self._research.total_deliveries > 0 and self._research.implementation_rate < 0.3:
            recs.append("Research implementation rate below 30%. Focus on actionable research.")

        if not recs:
            recs.append("Self-learning system operating normally. Continue current trajectory.")

        return recs

    def generate_report(self) -> dict:
        """Generate full meta-learning report."""
        health = self._compute_health()
        recs = self._compute_recommendations()

        # Count active data sources
        active_sources = 0
        if self._principles.total_principles > 0:
            active_sources += 1
        if self._sessions.total_sessions > 0:
            active_sources += 1
        if self._improvements.total_proposals > 0:
            active_sources += 1
        if self._research.total_deliveries > 0:
            active_sources += 1
        if self._journal.total_events > 0:
            active_sources += 1

        return {
            "principles": self._principles.to_dict(),
            "sessions": self._sessions.to_dict(),
            "improvements": self._improvements.to_dict(),
            "research": self._research.to_dict(),
            "journal": self._journal.to_dict(),
            "summary": {
                "overall_health": health,
                "data_sources_active": active_sources,
                "recommendations": recs,
            },
        }

    def brief_summary(self) -> str:
        """One-line summary for /cca-init briefing."""
        report = self.generate_report()
        health = report["summary"]["overall_health"]
        p_count = report["principles"]["total"]
        p_avg = report["principles"]["average_score"]
        s_count = report["sessions"]["total"]
        s_trend = report["sessions"]["trend"]
        imp_rate = report["improvements"]["success_rate"]
        imp_str = f"{imp_rate:.0%}" if imp_rate is not None else "N/A"

        return (f"Self-Learning: {health} | "
                f"{p_count} principles (avg {p_avg:.2f}) | "
                f"{s_count} sessions ({s_trend}) | "
                f"Improvement success: {imp_str}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MT-49: Self-Learning Meta-Analysis Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--brief", action="store_true", help="One-line summary")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Custom data directory (default: auto-detect)")
    args = parser.parse_args()

    dashboard = MetaLearningDashboard(data_dir=args.data_dir)

    if args.brief:
        print(dashboard.brief_summary())
        return

    report = dashboard.generate_report()

    if args.json:
        print(json.dumps(report, indent=2))
        return

    # Text report
    print("=" * 60)
    print("  SELF-LEARNING META-ANALYSIS DASHBOARD (MT-49)")
    print("=" * 60)
    print()

    # Health
    health = report["summary"]["overall_health"]
    print(f"Overall Health: {health}")
    print(f"Data Sources Active: {report['summary']['data_sources_active']}/5")
    print()

    # Principles
    p = report["principles"]
    print(f"PRINCIPLES: {p['total']} total ({p['active']} active, {p['pruned']} pruned)")
    print(f"  Average Score: {p['average_score']:.3f}")
    if p["domain_distribution"]:
        domains = ", ".join(f"{k}: {v}" for k, v in sorted(p["domain_distribution"].items()))
        print(f"  Domains: {domains}")
    if p["top_5"]:
        print("  Top principles:")
        for tp in p["top_5"][:3]:
            print(f"    [{tp['score']:.2f}] {tp['text'][:60]}")
    print()

    # Sessions
    s = report["sessions"]
    print(f"SESSIONS: {s['total']} tracked")
    print(f"  Grade Trend: {s['trend']}")
    if s["grade_counts"]:
        grades = ", ".join(f"{k}: {v}" for k, v in sorted(s["grade_counts"].items()))
        print(f"  Grades: {grades}")
    print(f"  Avg Tests/Session: {s['avg_tests_per_session']:.1f}")
    print(f"  Avg Commits/Session: {s['avg_commits_per_session']:.1f}")
    print()

    # Improvements
    i = report["improvements"]
    print(f"IMPROVEMENTS: {i['total_proposals']} proposals ({i['implemented']} implemented)")
    if i["success_rate"] is not None:
        print(f"  Success Rate: {i['success_rate']:.1%}")
    print()

    # Research
    r = report["research"]
    print(f"RESEARCH: {r['total_deliveries']} deliveries")
    print(f"  Implementation Rate: {r['implementation_rate']:.1%}")
    if r["status_counts"]:
        statuses = ", ".join(f"{k}: {v}" for k, v in sorted(r["status_counts"].items()))
        print(f"  Statuses: {statuses}")
    print()

    # Journal
    j = report["journal"]
    print(f"JOURNAL: {j['total_events']} events")
    if j["domains_covered"]:
        print(f"  Domains: {', '.join(j['domains_covered'])}")
    print()

    # Recommendations
    print("RECOMMENDATIONS:")
    for rec in report["summary"]["recommendations"]:
        print(f"  - {rec}")
    print()


if __name__ == "__main__":
    main()
