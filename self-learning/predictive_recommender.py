#!/usr/bin/env python3
"""
predictive_recommender.py — MT-28 Phase 5: Predictive Pre-Session Recommendations

Uses principle scores, session trajectory patterns, and domain context to
generate actionable recommendations BEFORE a session starts. This is the
predictive layer on top of the reactive principle_registry + reflect pipeline.

Key idea: instead of only learning from past sessions (reactive), we predict
what principles and strategies are most relevant for the UPCOMING session
based on what type of work is planned.

Inputs:
- Principle registry (scored principles by domain)
- Session journal (past session patterns)
- Planned work context (which MTs, which domains)

Outputs:
- Ranked list of relevant principles to inject at session start
- Risk warnings based on past failure patterns
- Suggested focus areas based on trajectory analysis

Usage:
    from predictive_recommender import PredictiveRecommender
    rec = PredictiveRecommender()
    recs = rec.recommend(planned_domains=["trading_research", "cca_operations"])
    for r in recs:
        print(f"[{r.relevance:.0%}] {r.principle_text} ({r.reason})")

CLI:
    python3 predictive_recommender.py recommend --domains trading_research cca_operations
    python3 predictive_recommender.py risks --domains trading_research
    python3 predictive_recommender.py inject --domains cca_operations --format markdown

Stdlib only. No external dependencies.
"""

import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import (
    Principle,
    VALID_DOMAINS,
    _load_principles,
    REINFORCE_SCORE,
)
from principle_transfer import DOMAIN_AFFINITY_MAP

JOURNAL_PATH = os.path.join(SCRIPT_DIR, "journal.jsonl")

# Recommendation thresholds
MIN_RELEVANCE = 0.3       # Below this, don't recommend
MAX_RECOMMENDATIONS = 10  # Don't overwhelm with too many
RECENCY_DECAY_SESSIONS = 50  # Half-life in sessions for recency weighting
RISK_THRESHOLD = 0.4      # Principles below this score flag as risks


@dataclass
class Recommendation:
    """A single pre-session recommendation."""
    principle_id: str
    principle_text: str
    source_domain: str
    relevance: float           # 0-1, how relevant to planned session
    reason: str                # Why this is recommended
    category: str              # "reinforce", "caution", "transfer", "emerging"
    principle_score: float     # Raw principle score
    usage_count: int           # How many times tested

    def to_dict(self) -> dict:
        return {
            "principle_id": self.principle_id,
            "principle_text": self.principle_text,
            "source_domain": self.source_domain,
            "relevance": round(self.relevance, 4),
            "reason": self.reason,
            "category": self.category,
            "principle_score": round(self.principle_score, 4),
            "usage_count": self.usage_count,
        }


@dataclass
class RiskWarning:
    """A warning about a known failure pattern."""
    principle_id: str
    principle_text: str
    domain: str
    score: float
    usage_count: int
    risk_level: str   # "high", "medium", "low"
    warning: str      # Human-readable warning

    def to_dict(self) -> dict:
        return {
            "principle_id": self.principle_id,
            "principle_text": self.principle_text,
            "domain": self.domain,
            "score": round(self.score, 4),
            "usage_count": self.usage_count,
            "risk_level": self.risk_level,
            "warning": self.warning,
        }


@dataclass
class SessionProfile:
    """Extracted profile of a past session from journal entries."""
    session_number: int
    domains_touched: list = field(default_factory=list)
    event_types: list = field(default_factory=list)
    grade: Optional[str] = None
    test_count: int = 0
    timestamp: Optional[str] = None


class PredictiveRecommender:
    """Generates pre-session recommendations from principles and history."""

    def __init__(self, principles_path: Optional[str] = None,
                 journal_path: Optional[str] = None):
        self._principles_path = principles_path
        self._journal_path = journal_path or JOURNAL_PATH

    def _get_principles(self) -> dict[str, Principle]:
        """Load all non-pruned principles."""
        all_principles = _load_principles(self._principles_path) if self._principles_path else _load_principles()
        return {pid: p for pid, p in all_principles.items() if not p.pruned}

    def _get_session_profiles(self, limit: int = 50) -> list[SessionProfile]:
        """Extract session profiles from journal."""
        if not os.path.exists(self._journal_path):
            return []

        sessions: dict[int, SessionProfile] = {}
        try:
            with open(self._journal_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    session_num = entry.get("session", 0)
                    if session_num <= 0:
                        continue

                    if session_num not in sessions:
                        sessions[session_num] = SessionProfile(
                            session_number=session_num,
                            timestamp=entry.get("timestamp"),
                        )

                    profile = sessions[session_num]
                    event_type = entry.get("type", "")
                    if event_type and event_type not in profile.event_types:
                        profile.event_types.append(event_type)

                    domain = entry.get("domain", "")
                    if domain and domain not in profile.domains_touched:
                        profile.domains_touched.append(domain)

                    if "grade" in entry:
                        profile.grade = entry["grade"]
                    if "test_count" in entry:
                        profile.test_count = entry["test_count"]

        except OSError:
            return []

        # Return most recent N sessions
        sorted_sessions = sorted(sessions.values(),
                                 key=lambda s: s.session_number, reverse=True)
        return sorted_sessions[:limit]

    def _domain_relevance(self, principle: Principle,
                          planned_domains: list[str]) -> float:
        """Calculate how relevant a principle is to planned domains.

        Direct domain match = 1.0
        Affinity-based match = affinity score
        No match = 0.0
        """
        max_relevance = 0.0

        for target in planned_domains:
            # Direct domain match
            if target in principle.applicable_domains or target == principle.source_domain:
                max_relevance = max(max_relevance, 1.0)
                continue

            # Affinity-based match
            source = principle.source_domain
            affinity = DOMAIN_AFFINITY_MAP.get(source, {}).get(target, 0.0)
            # Also check reverse direction
            reverse_affinity = DOMAIN_AFFINITY_MAP.get(target, {}).get(source, 0.0)
            best_affinity = max(affinity, reverse_affinity)

            max_relevance = max(max_relevance, best_affinity)

        return max_relevance

    def _recency_weight(self, principle: Principle,
                        current_session: int = 0) -> float:
        """Weight by how recently a principle was used.

        More recently used principles get higher weight.
        Uses exponential decay with configurable half-life.
        """
        if current_session <= 0 or principle.last_used_session <= 0:
            return 0.5  # Neutral weight if no session info

        sessions_ago = current_session - principle.last_used_session
        if sessions_ago <= 0:
            return 1.0

        # Exponential decay: weight = 2^(-sessions_ago / half_life)
        decay = math.pow(2, -sessions_ago / RECENCY_DECAY_SESSIONS)
        return max(0.1, decay)  # Floor at 0.1

    def _categorize(self, principle: Principle, domain_relevance: float,
                    planned_domains: list[str]) -> str:
        """Determine recommendation category."""
        is_direct = any(d in principle.applicable_domains or
                        d == principle.source_domain
                        for d in planned_domains)

        if principle.is_reinforced and is_direct:
            return "reinforce"
        elif principle.score < RISK_THRESHOLD and principle.usage_count >= 5:
            return "caution"
        elif not is_direct and domain_relevance > 0.3:
            return "transfer"
        elif principle.usage_count < 5:
            return "emerging"
        else:
            return "reinforce"

    def recommend(self, planned_domains: list[str],
                  current_session: int = 0,
                  max_results: int = MAX_RECOMMENDATIONS) -> list[Recommendation]:
        """Generate ranked recommendations for an upcoming session.

        Args:
            planned_domains: Domains the session will work on.
            current_session: Current session number (for recency weighting).
            max_results: Maximum recommendations to return.

        Returns:
            Sorted list of Recommendation objects (highest relevance first).
        """
        if not planned_domains:
            return []

        principles = self._get_principles()
        if not principles:
            return []

        recommendations = []
        for pid, principle in principles.items():
            domain_rel = self._domain_relevance(principle, planned_domains)
            if domain_rel < MIN_RELEVANCE:
                continue

            recency = self._recency_weight(principle, current_session)
            category = self._categorize(principle, domain_rel, planned_domains)

            # Composite relevance score
            # Domain relevance is primary (60%), principle score secondary (25%),
            # recency tertiary (15%)
            relevance = (0.60 * domain_rel +
                         0.25 * principle.score +
                         0.15 * recency)

            # Boost reinforced principles slightly
            if category == "reinforce" and principle.is_reinforced:
                relevance = min(1.0, relevance * 1.15)

            # Reduce score for caution items (they're warnings, not tips)
            if category == "caution":
                relevance *= 0.8

            # Build reason string
            if category == "reinforce":
                reason = f"Proven in {principle.source_domain} ({principle.usage_count} uses, {principle.score:.0%} success)"
            elif category == "caution":
                reason = f"Low success rate in {principle.source_domain} ({principle.score:.0%}) — be careful"
            elif category == "transfer":
                reason = f"Strong in {principle.source_domain}, may apply to {', '.join(planned_domains)}"
            else:
                reason = f"New principle ({principle.usage_count} uses) — worth testing"

            recommendations.append(Recommendation(
                principle_id=pid,
                principle_text=principle.text,
                source_domain=principle.source_domain,
                relevance=relevance,
                reason=reason,
                category=category,
                principle_score=principle.score,
                usage_count=principle.usage_count,
            ))

        # Sort by relevance descending
        recommendations.sort(key=lambda r: r.relevance, reverse=True)
        return recommendations[:max_results]

    def get_risks(self, planned_domains: list[str]) -> list[RiskWarning]:
        """Identify risk patterns relevant to planned domains.

        Returns principles with low scores that are relevant to planned work.
        These are things that have been tried and failed — caution zones.
        """
        if not planned_domains:
            return []

        principles = self._get_principles()
        risks = []

        for pid, principle in principles.items():
            if principle.usage_count < 3:
                continue  # Not enough data to flag as risk

            domain_rel = self._domain_relevance(principle, planned_domains)
            if domain_rel < MIN_RELEVANCE:
                continue

            if principle.score >= RISK_THRESHOLD:
                continue  # Not a risk

            # Determine risk level
            if principle.score < 0.2 and principle.usage_count >= 10:
                risk_level = "high"
                warning = f"Consistently fails ({principle.score:.0%} over {principle.usage_count} uses). Avoid this approach."
            elif principle.score < 0.3:
                risk_level = "medium"
                warning = f"More failures than successes ({principle.score:.0%}). Consider alternatives."
            else:
                risk_level = "low"
                warning = f"Below average ({principle.score:.0%}). Monitor if you use this approach."

            risks.append(RiskWarning(
                principle_id=pid,
                principle_text=principle.text,
                domain=principle.source_domain,
                score=principle.score,
                usage_count=principle.usage_count,
                risk_level=risk_level,
                warning=warning,
            ))

        # Sort: high risk first, then medium, then low
        risk_order = {"high": 0, "medium": 1, "low": 2}
        risks.sort(key=lambda r: (risk_order.get(r.risk_level, 3), r.score))
        return risks

    def format_injection(self, planned_domains: list[str],
                         current_session: int = 0,
                         format: str = "markdown") -> str:
        """Generate injectable text for session start.

        This is what gets injected into the UserPromptSubmit hook
        to prime the session with relevant knowledge.
        """
        recs = self.recommend(planned_domains, current_session)
        risks = self.get_risks(planned_domains)

        if not recs and not risks:
            return ""

        lines = []

        if recs:
            reinforced = [r for r in recs if r.category == "reinforce"]
            transfers = [r for r in recs if r.category == "transfer"]
            emerging = [r for r in recs if r.category == "emerging"]

            if reinforced:
                lines.append("**Proven principles for this session:**")
                for r in reinforced[:5]:
                    lines.append(f"- {r.principle_text} ({r.principle_score:.0%} success)")
                lines.append("")

            if transfers:
                lines.append("**Cross-domain insights worth testing:**")
                for r in transfers[:3]:
                    lines.append(f"- {r.principle_text} (from {r.source_domain})")
                lines.append("")

            if emerging:
                lines.append("**New principles to validate:**")
                for r in emerging[:3]:
                    lines.append(f"- {r.principle_text} ({r.usage_count} uses so far)")
                lines.append("")

        if risks:
            lines.append("**Risk warnings:**")
            for r in risks[:3]:
                icon = "!!" if r.risk_level == "high" else "!"
                lines.append(f"- [{icon}] {r.principle_text} — {r.warning}")
            lines.append("")

        return "\n".join(lines)

    def summary(self, planned_domains: list[str],
                current_session: int = 0) -> str:
        """Human-readable summary for CLI output."""
        recs = self.recommend(planned_domains, current_session)
        risks = self.get_risks(planned_domains)

        lines = [f"Predictive Recommendations for domains: {', '.join(planned_domains)}"]
        lines.append("=" * 60)

        if not recs and not risks:
            lines.append("No principles found for these domains.")
            lines.append("Build experience by adding principles via principle_registry.py")
            return "\n".join(lines)

        if recs:
            lines.append(f"\nRecommendations ({len(recs)}):")
            lines.append("-" * 40)
            for i, r in enumerate(recs, 1):
                lines.append(f"  {i}. [{r.category.upper():<10}] {r.principle_text}")
                lines.append(f"     Relevance: {r.relevance:.0%} | Score: {r.principle_score:.0%} | Uses: {r.usage_count}")
                lines.append(f"     {r.reason}")
                lines.append("")

        if risks:
            lines.append(f"\nRisk Warnings ({len(risks)}):")
            lines.append("-" * 40)
            for r in risks:
                lines.append(f"  [{r.risk_level.upper():<6}] {r.principle_text}")
                lines.append(f"    {r.warning}")
                lines.append("")

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pre-session predictive recommendations")
    parser.add_argument("command", choices=["recommend", "risks", "inject", "summary"],
                        help="What to generate")
    parser.add_argument("--domains", nargs="+", default=["cca_operations"],
                        help="Planned domains for the session")
    parser.add_argument("--session", type=int, default=0,
                        help="Current session number")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format")
    parser.add_argument("--max", type=int, default=MAX_RECOMMENDATIONS,
                        help="Max recommendations")

    args = parser.parse_args()
    rec = PredictiveRecommender()

    if args.command == "recommend":
        recs = rec.recommend(args.domains, args.session, args.max)
        if args.format == "json":
            print(json.dumps([r.to_dict() for r in recs], indent=2))
        else:
            for r in recs:
                print(f"[{r.relevance:.0%}] {r.principle_text}")
                print(f"  Category: {r.category} | Score: {r.principle_score:.0%} | {r.reason}")
                print()

    elif args.command == "risks":
        risks = rec.get_risks(args.domains)
        if args.format == "json":
            print(json.dumps([r.to_dict() for r in risks], indent=2))
        else:
            if not risks:
                print("No risk warnings for these domains.")
            for r in risks:
                print(f"[{r.risk_level.upper()}] {r.principle_text}")
                print(f"  {r.warning}")
                print()

    elif args.command == "inject":
        text = rec.format_injection(args.domains, args.session, args.format)
        if text:
            print(text)
        else:
            print("No recommendations to inject.")

    elif args.command == "summary":
        print(rec.summary(args.domains, args.session))


if __name__ == "__main__":
    main()
