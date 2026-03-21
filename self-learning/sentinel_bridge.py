#!/usr/bin/env python3
"""
sentinel_bridge.py — MT-28 Phase 6: Bridge between Sentinel mutations and principle registry.

Connects the SentinelMutator (improver.py) with the principle_registry system.
When improvement proposals succeed or fail, this bridge:
1. Creates/updates principles from validated proposals
2. Scores existing principles based on proposal outcomes
3. Generates counter-principles from rejected proposals
4. Feeds sentinel cross-pollinations into principle_transfer

This is the closed loop that makes the self-learning system truly adaptive:
    Session outcome → SentinelMutator → sentinel_bridge → principle_registry
    → predictive_recommender → next session → outcome → ...

Usage:
    from sentinel_bridge import SentinelBridge
    bridge = SentinelBridge()
    report = bridge.process_cycle(proposals)
    # report contains: principles_created, principles_scored, counter_principles

CLI:
    python3 sentinel_bridge.py cycle                    # Process current proposals
    python3 sentinel_bridge.py status                   # Show bridge statistics
    python3 sentinel_bridge.py sync --session 111       # Full sync from store

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import (
    Principle, VALID_DOMAINS, _load_principles, _save_principle,
    _generate_id, _now_iso, PRINCIPLES_PATH,
)
from improver import ImprovementProposal, ImprovementStore, SentinelMutator

# Map from improver target_module to principle domain
MODULE_TO_DOMAIN = {
    "self-learning": "cca_operations",
    "context-monitor": "session_management",
    "agent-guard": "code_quality",
    "spec-system": "code_quality",
    "memory-system": "cca_operations",
    "usage-dashboard": "session_management",
    "reddit-intelligence": "nuclear_scan",
    "design-skills": "cca_operations",
    "trading": "trading_execution",
    "kalshi": "trading_execution",
    "research": "trading_research",
}

# Minimum proposal quality to create a principle
MIN_IMPROVEMENT_FOR_PRINCIPLE = 0.1  # 10% improvement
MIN_VALIDATED_COUNT = 1  # At least 1 validation

# Counter-principle prefix
COUNTER_PREFIX = "[COUNTER] "


@dataclass
class BridgeCycleReport:
    """Result of a bridge processing cycle."""
    principles_created: int = 0
    principles_scored: int = 0
    counter_principles: int = 0
    transfers_suggested: int = 0
    errors: list = field(default_factory=list)
    details: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "principles_created": self.principles_created,
            "principles_scored": self.principles_scored,
            "counter_principles": self.counter_principles,
            "transfers_suggested": self.transfers_suggested,
            "errors": self.errors,
            "details": self.details,
        }

    def summary(self) -> str:
        lines = ["Sentinel Bridge Cycle Report"]
        lines.append(f"  Principles created: {self.principles_created}")
        lines.append(f"  Principles scored: {self.principles_scored}")
        lines.append(f"  Counter-principles: {self.counter_principles}")
        lines.append(f"  Transfer suggestions: {self.transfers_suggested}")
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for e in self.errors[:3]:
                lines.append(f"    - {e}")
        return "\n".join(lines)


class SentinelBridge:
    """Bridges SentinelMutator outputs to the principle registry."""

    def __init__(self, principles_path: Optional[str] = None,
                 store_path: Optional[str] = None):
        self._principles_path = principles_path or PRINCIPLES_PATH
        self._store_path = store_path
        self._sentinel = SentinelMutator()

    def _proposal_to_domain(self, proposal: ImprovementProposal) -> str:
        """Map a proposal's target module to a principle domain."""
        module = getattr(proposal, 'target_module', '') or ''
        return MODULE_TO_DOMAIN.get(module, "general")

    def _extract_principle_text(self, proposal: ImprovementProposal) -> str:
        """Extract a concise principle from a proposal's fix description."""
        fix = proposal.proposed_fix or ""
        # Remove common prefixes
        for prefix in ["[Cross-pollinated from", "[COUNTER]"]:
            if fix.startswith(prefix):
                idx = fix.find("]")
                if idx > 0:
                    fix = fix[idx + 1:].strip()
        # Truncate overly long fixes
        if len(fix) > 200:
            fix = fix[:197] + "..."
        return fix

    def _get_improvement_ratio(self, proposal: ImprovementProposal) -> float:
        """Extract improvement ratio from proposal outcome."""
        outcome = proposal.outcome or {}
        before = outcome.get("metric_before", 0)
        after = outcome.get("metric_after", 0)
        if before > 0:
            return (before - after) / before  # Positive = improvement
        return 0.0

    def create_principle_from_proposal(self, proposal: ImprovementProposal,
                                       current_session: int = 0) -> Optional[str]:
        """Create a new principle from a validated/committed proposal.

        Returns principle ID if created, None if skipped.
        """
        if proposal.status not in ("validated", "committed"):
            return None

        domain = self._proposal_to_domain(proposal)
        text = self._extract_principle_text(proposal)
        if not text:
            return None

        # Check if principle already exists
        pid = _generate_id(text, domain)
        existing = _load_principles(self._principles_path)
        if pid in existing:
            return None  # Already exists

        principle = Principle(
            id=pid,
            text=text,
            source_domain=domain,
            applicable_domains=[domain],
            success_count=1,  # Start with 1 success (it was validated)
            usage_count=1,
            created_session=current_session,
            last_used_session=current_session,
            created_at=_now_iso(),
            updated_at=_now_iso(),
            source_context=f"sentinel_bridge from {proposal.source}:{proposal.pattern_type}",
        )

        _save_principle(principle, self._principles_path)
        return pid

    def score_principle_from_outcome(self, proposal: ImprovementProposal,
                                     current_session: int = 0) -> Optional[str]:
        """Score an existing principle based on proposal outcome.

        Finds principles whose text matches the proposal fix and records
        success/failure based on the proposal outcome.

        Returns principle ID if scored, None if no match.
        """
        fix_text = self._extract_principle_text(proposal)
        domain = self._proposal_to_domain(proposal)
        pid = _generate_id(fix_text, domain)

        principles = _load_principles(self._principles_path)
        if pid not in principles:
            return None

        principle = principles[pid]
        outcome = proposal.outcome or {}
        improved = outcome.get("improved", False)

        if improved:
            principle.success_count += 1
        principle.usage_count += 1
        principle.last_used_session = current_session
        principle.updated_at = _now_iso()

        _save_principle(principle, self._principles_path)
        return pid

    def create_counter_principle(self, rejected_proposal: ImprovementProposal,
                                  current_session: int = 0) -> Optional[str]:
        """Create a counter-principle from a rejected/failed proposal.

        Counter-principles capture what NOT to do — they have inverted text
        and are scored on their "failure avoidance" rate.

        Returns principle ID if created, None if skipped.
        """
        if rejected_proposal.status != "rejected":
            return None

        domain = self._proposal_to_domain(rejected_proposal)
        original_fix = self._extract_principle_text(rejected_proposal)
        if not original_fix:
            return None

        counter_text = f"Avoid: {original_fix}"
        pid = _generate_id(counter_text, domain)

        existing = _load_principles(self._principles_path)
        if pid in existing:
            # Already have this counter-principle — score it
            existing[pid].success_count += 1  # Each failure is a "success" for the counter
            existing[pid].usage_count += 1
            existing[pid].updated_at = _now_iso()
            _save_principle(existing[pid], self._principles_path)
            return pid

        principle = Principle(
            id=pid,
            text=counter_text,
            source_domain=domain,
            applicable_domains=[domain],
            success_count=1,  # Starts validated (the rejection confirms the counter)
            usage_count=1,
            created_session=current_session,
            last_used_session=current_session,
            created_at=_now_iso(),
            updated_at=_now_iso(),
            source_context=f"sentinel_counter from rejected {rejected_proposal.pattern_type}",
        )

        _save_principle(principle, self._principles_path)
        return pid

    def process_cycle(self, proposals: list[ImprovementProposal],
                       current_session: int = 0) -> BridgeCycleReport:
        """Process a batch of proposals through the bridge.

        This is the main entry point. Call after each session wrap
        or after the sentinel evolve() cycle completes.
        """
        report = BridgeCycleReport()

        for p in proposals:
            try:
                # Validated/committed → create principle
                if p.status in ("validated", "committed"):
                    pid = self.create_principle_from_proposal(p, current_session)
                    if pid:
                        report.principles_created += 1
                        report.details.append(f"Created principle {pid} from {p.pattern_type}")

                    # Also score if principle already exists
                    scored = self.score_principle_from_outcome(p, current_session)
                    if scored:
                        report.principles_scored += 1

                # Rejected → create counter-principle + trigger mutations
                elif p.status == "rejected":
                    cpid = self.create_counter_principle(p, current_session)
                    if cpid:
                        report.counter_principles += 1
                        report.details.append(f"Counter-principle {cpid} from rejected {p.pattern_type}")

                    # Run sentinel mutation
                    mutations = self._sentinel.mutate_from_failure(p)
                    for m in mutations:
                        mpid = self.create_principle_from_proposal(m, current_session)
                        if mpid:
                            report.principles_created += 1

                # Score regardless of status if outcome exists
                if p.outcome and p.status not in ("validated", "committed"):
                    scored = self.score_principle_from_outcome(p, current_session)
                    if scored:
                        report.principles_scored += 1

            except Exception as e:
                report.errors.append(f"Error processing {p.pattern_type}: {str(e)}")

        # Run cross-pollination on validated proposals
        validated = [p for p in proposals if p.status in ("validated", "committed")]
        if validated:
            cross = self._sentinel.cross_pollinate(validated)
            for cp in cross:
                try:
                    pid = self.create_principle_from_proposal(cp, current_session)
                    if pid:
                        report.transfers_suggested += 1
                except Exception as e:
                    report.errors.append(f"Cross-pollination error: {str(e)}")

        return report

    def get_stats(self) -> dict:
        """Get bridge statistics."""
        principles = _load_principles(self._principles_path)
        counter_count = sum(1 for p in principles.values()
                           if p.text.startswith("Avoid:"))
        sentinel_count = sum(1 for p in principles.values()
                            if "sentinel" in (p.source_context or ""))

        return {
            "total_principles": len(principles),
            "counter_principles": counter_count,
            "sentinel_sourced": sentinel_count,
            "pruned": sum(1 for p in principles.values() if p.pruned),
            "reinforced": sum(1 for p in principles.values() if p.is_reinforced),
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sentinel Bridge — connects mutations to principles")
    parser.add_argument("command", choices=["cycle", "status", "sync"],
                        help="What to do")
    parser.add_argument("--session", type=int, default=0, help="Current session number")
    parser.add_argument("--store", default=None, help="Improvement store path")

    args = parser.parse_args()
    bridge = SentinelBridge(store_path=args.store)

    if args.command == "status":
        stats = bridge.get_stats()
        print("Sentinel Bridge Status:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.command == "cycle":
        store = ImprovementStore(args.store)
        proposals = store.load_all()
        report = bridge.process_cycle(proposals, args.session)
        print(report.summary())

    elif args.command == "sync":
        store = ImprovementStore(args.store)
        proposals = store.load_all()
        # Only process recent proposals (from this session or unprocessed)
        recent = [p for p in proposals if not hasattr(p, '_bridge_processed')]
        report = bridge.process_cycle(recent, args.session)
        print(report.summary())


if __name__ == "__main__":
    main()
