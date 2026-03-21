#!/usr/bin/env python3
"""
principle_transfer.py — MT-28 Phase 3: Cross-Domain Principle Transfer

Identifies high-performing principles in one domain and suggests they be
tested in related domains. Uses domain affinity scoring to determine which
transfers are most likely to succeed.

Transfer score = principle_score * affinity_score

A principle with 0.85 score in trading_research and 0.75 affinity to
trading_execution gets transfer_score = 0.6375 — worth trying.

Domain affinity is predefined based on conceptual overlap:
- trading_research <-> trading_execution (high: same domain family)
- code_quality <-> session_management (medium: both about process)
- cca_operations <-> session_management (medium: operational overlap)
- nuclear_scan <-> trading_research (low: scanning != trading)

Usage:
    from principle_transfer import PrincipleTransfer

    pt = PrincipleTransfer()
    candidates = pt.find_transfer_candidates(target_domain="trading_execution")
    # Returns sorted list of TransferCandidate objects

    # Apply a transfer (adds target domain to principle's applicable_domains)
    pt.apply_transfer(principle_id="prin_abc12345", target_domain="trading_execution")

    # Scan all domains for transfer opportunities
    all_transfers = pt.scan_all_domains()

Zero external dependencies. Stdlib only.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import (
    Principle,
    VALID_DOMAINS,
    _load_principles,
    _save_principle,
)


# Domain affinity map: how related two domains are (0.0 = unrelated, 1.0 = same)
# Only stores non-zero, non-self affinities.
DOMAIN_AFFINITY_MAP: Dict[str, Dict[str, float]] = {
    "cca_operations": {
        "session_management": 0.70,
        "code_quality": 0.45,
        "general": 0.40,
        "nuclear_scan": 0.35,
        "trading_research": 0.15,
        "trading_execution": 0.10,
    },
    "trading_research": {
        "trading_execution": 0.85,
        "general": 0.25,
        "nuclear_scan": 0.20,
        "code_quality": 0.10,
        "session_management": 0.10,
        "cca_operations": 0.15,
    },
    "trading_execution": {
        "trading_research": 0.85,
        "general": 0.20,
        "session_management": 0.15,
        "code_quality": 0.10,
        "nuclear_scan": 0.10,
        "cca_operations": 0.10,
    },
    "code_quality": {
        "session_management": 0.50,
        "cca_operations": 0.45,
        "general": 0.40,
        "nuclear_scan": 0.20,
        "trading_research": 0.10,
        "trading_execution": 0.10,
    },
    "session_management": {
        "cca_operations": 0.70,
        "code_quality": 0.50,
        "general": 0.40,
        "nuclear_scan": 0.25,
        "trading_research": 0.10,
        "trading_execution": 0.15,
    },
    "nuclear_scan": {
        "cca_operations": 0.35,
        "trading_research": 0.20,
        "session_management": 0.25,
        "general": 0.30,
        "code_quality": 0.20,
        "trading_execution": 0.10,
    },
    "general": {
        "cca_operations": 0.40,
        "code_quality": 0.40,
        "session_management": 0.40,
        "nuclear_scan": 0.30,
        "trading_research": 0.25,
        "trading_execution": 0.20,
    },
}


@dataclass
class DomainAffinity:
    """Affinity between two domains."""
    source: str
    target: str
    score: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "score": round(self.score, 4),
            "reason": self.reason,
        }


@dataclass
class TransferCandidate:
    """A principle that could be transferred to a new domain."""
    principle_id: str
    principle_text: str
    source_domain: str
    target_domain: str
    principle_score: float
    affinity_score: float
    transfer_score: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "principle_id": self.principle_id,
            "principle_text": self.principle_text,
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "principle_score": round(self.principle_score, 4),
            "affinity_score": round(self.affinity_score, 4),
            "transfer_score": round(self.transfer_score, 4),
            "reason": self.reason,
        }


class PrincipleTransfer:
    """
    Cross-domain principle transfer engine.

    Identifies high-scoring principles in one domain and suggests they
    be applied to related domains based on domain affinity scoring.
    """

    def __init__(
        self,
        min_principle_score: float = 0.65,
        min_affinity: float = 0.3,
        min_usages: int = 5,
    ):
        self.min_principle_score = min_principle_score
        self.min_affinity = min_affinity
        self.min_usages = min_usages

    def get_affinity(self, source: str, target: str) -> float:
        """Get affinity score between two domains."""
        if source == target:
            return 1.0
        return DOMAIN_AFFINITY_MAP.get(source, {}).get(target, 0.0)

    def compute_transfer_score(
        self, principle_score: float, affinity_score: float
    ) -> float:
        """Compute transfer score as product of principle score and affinity."""
        return principle_score * affinity_score

    def find_transfer_candidates(
        self,
        target_domain: str,
        principles_path: Optional[str] = None,
    ) -> List[TransferCandidate]:
        """
        Find principles from other domains that could transfer to target_domain.

        Filters:
        - Principle must be active (not pruned)
        - Principle must have score >= min_principle_score
        - Principle must have usage_count >= min_usages
        - Source domain must have affinity >= min_affinity to target
        - Principle must not already apply to target domain

        Returns sorted by transfer_score descending.
        """
        if principles_path is None:
            from principle_registry import PRINCIPLES_PATH
            principles_path = PRINCIPLES_PATH

        principles = _load_principles(principles_path)
        candidates = []

        for p in principles.values():
            # Skip pruned
            if p.pruned:
                continue

            # Skip if same domain
            if p.source_domain == target_domain:
                continue

            # Skip if already applicable to target
            if target_domain in p.applicable_domains:
                continue

            # Check usage threshold
            if p.usage_count < self.min_usages:
                continue

            # Check principle score
            if p.score < self.min_principle_score:
                continue

            # Check domain affinity
            affinity = self.get_affinity(p.source_domain, target_domain)
            if affinity < self.min_affinity:
                continue

            transfer_score = self.compute_transfer_score(p.score, affinity)

            candidates.append(TransferCandidate(
                principle_id=p.id,
                principle_text=p.text,
                source_domain=p.source_domain,
                target_domain=target_domain,
                principle_score=p.score,
                affinity_score=affinity,
                transfer_score=transfer_score,
                reason=(
                    f"Principle scores {p.score:.2f} in {p.source_domain} "
                    f"(affinity {affinity:.2f} to {target_domain})"
                ),
            ))

        candidates.sort(key=lambda c: c.transfer_score, reverse=True)
        return candidates

    def apply_transfer(
        self,
        principle_id: str,
        target_domain: str,
        principles_path: Optional[str] = None,
    ) -> Principle:
        """
        Apply a transfer by adding target_domain to the principle's applicable_domains.

        Idempotent — if already applied, no-op.
        """
        if target_domain not in VALID_DOMAINS:
            raise ValueError(f"Invalid domain: {target_domain}. Must be one of {VALID_DOMAINS}")

        if principles_path is None:
            from principle_registry import PRINCIPLES_PATH
            principles_path = PRINCIPLES_PATH

        principles = _load_principles(principles_path)
        if principle_id not in principles:
            raise KeyError(f"Principle not found: {principle_id}")

        p = principles[principle_id]

        if target_domain not in p.applicable_domains:
            p.applicable_domains.append(target_domain)
            from principle_registry import _now_iso
            p.updated_at = _now_iso()
            _save_principle(p, principles_path)

        return p

    def scan_all_domains(
        self,
        principles_path: Optional[str] = None,
    ) -> Dict[str, List[TransferCandidate]]:
        """
        Scan all domains for transfer opportunities.

        Returns dict mapping target_domain -> list of TransferCandidate.
        Only includes domains with at least one candidate.
        """
        results = {}
        for domain in VALID_DOMAINS:
            candidates = self.find_transfer_candidates(
                target_domain=domain,
                principles_path=principles_path,
            )
            if candidates:
                results[domain] = candidates
        return results


def main():
    """CLI interface for principle transfer analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Cross-Domain Principle Transfer")
    sub = parser.add_subparsers(dest="cmd")

    # scan
    scan_p = sub.add_parser("scan", help="Scan all domains for transfers")
    scan_p.add_argument("--min-score", type=float, default=0.65)
    scan_p.add_argument("--min-affinity", type=float, default=0.3)
    scan_p.add_argument("--min-usages", type=int, default=5)

    # candidates
    cand_p = sub.add_parser("candidates", help="Find candidates for a target domain")
    cand_p.add_argument("target_domain", help="Target domain")
    cand_p.add_argument("--min-score", type=float, default=0.65)

    # apply
    apply_p = sub.add_parser("apply", help="Apply a transfer")
    apply_p.add_argument("principle_id", help="Principle ID")
    apply_p.add_argument("target_domain", help="Target domain")

    # affinity
    aff_p = sub.add_parser("affinity", help="Show affinity matrix")

    args = parser.parse_args()

    if args.cmd == "scan":
        pt = PrincipleTransfer(
            min_principle_score=args.min_score,
            min_affinity=args.min_affinity,
            min_usages=args.min_usages,
        )
        results = pt.scan_all_domains()
        if not results:
            print("No transfer opportunities found.")
            return
        for domain, candidates in sorted(results.items()):
            print(f"\n{domain} ({len(candidates)} candidates):")
            for c in candidates[:3]:
                print(f"  [{c.transfer_score:.2f}] {c.principle_text[:60]}")
                print(f"    from {c.source_domain} (score={c.principle_score:.2f}, "
                      f"affinity={c.affinity_score:.2f})")

    elif args.cmd == "candidates":
        pt = PrincipleTransfer(min_principle_score=args.min_score)
        candidates = pt.find_transfer_candidates(target_domain=args.target_domain)
        if not candidates:
            print(f"No transfer candidates for {args.target_domain}.")
            return
        for c in candidates:
            print(json.dumps(c.to_dict(), indent=2))

    elif args.cmd == "apply":
        pt = PrincipleTransfer()
        try:
            p = pt.apply_transfer(args.principle_id, args.target_domain)
            print(f"Applied: {p.id} now applicable to {p.applicable_domains}")
        except (KeyError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "affinity":
        for source in VALID_DOMAINS:
            affinities = DOMAIN_AFFINITY_MAP.get(source, {})
            targets = sorted(affinities.items(), key=lambda x: -x[1])
            top3 = ", ".join(f"{t}={s:.2f}" for t, s in targets[:3])
            print(f"  {source}: {top3}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
