#!/usr/bin/env python3
"""
principle_registry.py — MT-28 Phase 1: EvolveR-Style Principle Registry

Stores, scores, and retrieves strategic principles distilled from session
trajectories. Principles are domain-tagged and scored using Laplace-smoothed
success rates. Cross-domain transfer happens in Phase 3.

Storage: self-learning/principles.jsonl (append-only entries, latest wins)
Scoring: s(p) = (success_count + 1) / (usage_count + 2)  [Laplace-smoothed]
Pruning: Principles below 0.3 score with 10+ usages get pruned.

Usage:
    python3 self-learning/principle_registry.py add \\
        --text "When evidence is ambiguous, seek corroboration" \\
        --domain cca_operations

    python3 self-learning/principle_registry.py list [--domain X] [--min-score 0.5]
    python3 self-learning/principle_registry.py score <id> --success|--failure
    python3 self-learning/principle_registry.py prune [--dry-run]
    python3 self-learning/principle_registry.py top [N] [--domain X]
    python3 self-learning/principle_registry.py stats
"""

import json
import os
import sys
import hashlib
import argparse
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")

from metric_config import get_metric

# Score thresholds (loaded from metric_config, user-overridable)
PRUNE_SCORE = get_metric("principle_registry.prune_score", 0.3)
PRUNE_MIN_USAGES = get_metric("principle_registry.prune_min_usages", 10)
REINFORCE_SCORE = get_metric("principle_registry.reinforce_score", 0.7)
MAX_PRINCIPLES_PER_DOMAIN = get_metric("principle_registry.max_principles_per_domain", 100)

VALID_DOMAINS = [
    "cca_operations",
    "trading_research",
    "trading_execution",
    "code_quality",
    "session_management",
    "nuclear_scan",
    "general",
]


@dataclass
class Principle:
    """A strategic principle distilled from session experience."""
    id: str
    text: str
    source_domain: str
    applicable_domains: list  # Domains where this principle applies
    success_count: int = 0
    usage_count: int = 0
    created_session: int = 0
    last_used_session: int = 0
    created_at: str = ""
    updated_at: str = ""
    pruned: bool = False
    source_context: str = ""  # What session/event spawned this principle

    @property
    def score(self) -> float:
        """Laplace-smoothed success rate."""
        return (self.success_count + 1) / (self.usage_count + 2)

    @property
    def should_prune(self) -> bool:
        """True if score below threshold with enough data."""
        return (self.score < PRUNE_SCORE and
                self.usage_count >= PRUNE_MIN_USAGES and
                not self.pruned)

    @property
    def is_reinforced(self) -> bool:
        """True if this principle has proven itself."""
        return self.score >= REINFORCE_SCORE and self.usage_count >= 5

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score, 4)
        return d


def _generate_id(text: str, domain: str) -> str:
    """Generate a deterministic 8-char hex ID from text + domain."""
    content = f"{text.lower().strip()}:{domain}"
    return "prin_" + hashlib.sha256(content.encode()).hexdigest()[:8]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_principles(path: str = PRINCIPLES_PATH) -> dict:
    """Load all principles, latest version wins (append-only JSONL)."""
    principles = {}
    if not os.path.exists(path):
        return principles

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                pid = data.get("id", "")
                if pid:
                    principles[pid] = Principle(**{
                        k: v for k, v in data.items()
                        if k in Principle.__dataclass_fields__
                    })
            except (json.JSONDecodeError, TypeError):
                continue

    return principles


def _save_principle(principle: Principle, path: str = PRINCIPLES_PATH) -> None:
    """Append a principle entry (append-only JSONL)."""
    with open(path, "a") as f:
        f.write(json.dumps(principle.to_dict()) + "\n")


def _atomic_rewrite(principles: dict, path: str = PRINCIPLES_PATH) -> None:
    """Rewrite the full file (for pruning operations only)."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for p in principles.values():
            f.write(json.dumps(p.to_dict()) + "\n")
    os.replace(tmp, path)


def _text_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity for dedup. Returns 0-1."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


# === Public API ===

def add_principle(
    text: str,
    source_domain: str,
    applicable_domains: Optional[list] = None,
    session: int = 0,
    source_context: str = "",
    path: str = PRINCIPLES_PATH,
) -> Principle:
    """Add a new principle. Deduplicates by text similarity."""
    if source_domain not in VALID_DOMAINS:
        raise ValueError(f"Invalid domain: {source_domain}. Must be one of {VALID_DOMAINS}")

    if applicable_domains is None:
        applicable_domains = [source_domain]

    for d in applicable_domains:
        if d not in VALID_DOMAINS:
            raise ValueError(f"Invalid applicable domain: {d}")

    # Check domain cap
    existing = _load_principles(path)
    domain_count = sum(
        1 for p in existing.values()
        if p.source_domain == source_domain and not p.pruned
    )
    if domain_count >= MAX_PRINCIPLES_PER_DOMAIN:
        raise ValueError(
            f"Domain '{source_domain}' has {domain_count} principles "
            f"(max {MAX_PRINCIPLES_PER_DOMAIN}). Prune before adding."
        )

    # Dedup: reject if >80% word overlap with existing active principle in same domain
    for p in existing.values():
        if p.pruned:
            continue
        if p.source_domain != source_domain:
            continue
        if _text_similarity(text, p.text) > 0.8:
            raise ValueError(
                f"Duplicate principle detected (similarity >{80}% with {p.id}): "
                f"'{p.text[:60]}...'"
            )

    pid = _generate_id(text, source_domain)
    now = _now_iso()

    principle = Principle(
        id=pid,
        text=text.strip(),
        source_domain=source_domain,
        applicable_domains=applicable_domains,
        created_session=session,
        last_used_session=session,
        created_at=now,
        updated_at=now,
        source_context=source_context,
    )

    _save_principle(principle, path)
    return principle


def record_usage(
    principle_id: str,
    success: bool,
    session: int = 0,
    path: str = PRINCIPLES_PATH,
) -> Principle:
    """Record a usage of a principle (success or failure)."""
    principles = _load_principles(path)
    if principle_id not in principles:
        raise KeyError(f"Principle not found: {principle_id}")

    p = principles[principle_id]
    if p.pruned:
        raise ValueError(f"Principle {principle_id} is pruned")

    p.usage_count += 1
    if success:
        p.success_count += 1
    if session > 0:
        p.last_used_session = session
    p.updated_at = _now_iso()

    _save_principle(p, path)
    return p


def get_principles(
    domain: Optional[str] = None,
    min_score: float = 0.0,
    include_pruned: bool = False,
    path: str = PRINCIPLES_PATH,
) -> list:
    """Get principles, optionally filtered by domain and min score."""
    principles = _load_principles(path)
    result = []

    for p in principles.values():
        if p.pruned and not include_pruned:
            continue
        if domain and domain not in p.applicable_domains:
            continue
        if p.score < min_score:
            continue
        result.append(p)

    result.sort(key=lambda x: x.score, reverse=True)
    return result


def get_top_principles(
    n: int = 5,
    domain: Optional[str] = None,
    path: str = PRINCIPLES_PATH,
) -> list:
    """Get top N principles by score for a domain."""
    return get_principles(domain=domain, path=path)[:n]


def prune_principles(
    dry_run: bool = False,
    path: str = PRINCIPLES_PATH,
) -> list:
    """Prune underperforming principles. Returns list of pruned IDs."""
    principles = _load_principles(path)
    pruned = []

    for p in principles.values():
        if p.should_prune:
            pruned.append(p.id)
            if not dry_run:
                p.pruned = True
                p.updated_at = _now_iso()

    if not dry_run and pruned:
        _atomic_rewrite(principles, path)

    return pruned


def get_stats(path: str = PRINCIPLES_PATH) -> dict:
    """Get summary statistics about the principle registry."""
    principles = _load_principles(path)
    active = [p for p in principles.values() if not p.pruned]
    pruned = [p for p in principles.values() if p.pruned]

    domain_counts = {}
    for p in active:
        domain_counts[p.source_domain] = domain_counts.get(p.source_domain, 0) + 1

    scores = [p.score for p in active] if active else [0.5]
    avg_score = sum(scores) / len(scores)
    reinforced = sum(1 for p in active if p.is_reinforced)

    return {
        "total": len(principles),
        "active": len(active),
        "pruned": len(pruned),
        "reinforced": reinforced,
        "avg_score": round(avg_score, 4),
        "domain_counts": domain_counts,
        "prunable": sum(1 for p in active if p.should_prune),
    }


def get_principle_by_id(
    principle_id: str,
    path: str = PRINCIPLES_PATH,
) -> Optional[Principle]:
    """Get a single principle by ID."""
    principles = _load_principles(path)
    return principles.get(principle_id)


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Principle Registry")
    sub = parser.add_subparsers(dest="cmd")

    # add
    add_p = sub.add_parser("add", help="Add a new principle")
    add_p.add_argument("--text", required=True, help="The principle text")
    add_p.add_argument("--domain", required=True, help="Source domain")
    add_p.add_argument("--applicable", nargs="*", help="Applicable domains")
    add_p.add_argument("--session", type=int, default=0)
    add_p.add_argument("--context", default="", help="Source context")

    # list
    list_p = sub.add_parser("list", help="List principles")
    list_p.add_argument("--domain", help="Filter by domain")
    list_p.add_argument("--min-score", type=float, default=0.0)
    list_p.add_argument("--include-pruned", action="store_true")

    # score
    score_p = sub.add_parser("score", help="Record usage outcome")
    score_p.add_argument("id", help="Principle ID")
    score_p.add_argument("--success", action="store_true")
    score_p.add_argument("--failure", action="store_true")
    score_p.add_argument("--session", type=int, default=0)

    # prune
    prune_p = sub.add_parser("prune", help="Prune underperformers")
    prune_p.add_argument("--dry-run", action="store_true")

    # top
    top_p = sub.add_parser("top", help="Show top N principles")
    top_p.add_argument("n", type=int, nargs="?", default=5)
    top_p.add_argument("--domain", help="Filter by domain")

    # stats
    sub.add_parser("stats", help="Show statistics")

    args = parser.parse_args()

    if args.cmd == "add":
        try:
            p = add_principle(
                text=args.text,
                source_domain=args.domain,
                applicable_domains=args.applicable,
                session=args.session,
                source_context=args.context,
            )
            print(f"Added: {p.id} (score: {p.score:.2f})")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "list":
        principles = get_principles(
            domain=args.domain,
            min_score=args.min_score,
            include_pruned=args.include_pruned,
        )
        if not principles:
            print("No principles found.")
            return
        for p in principles:
            status = " [PRUNED]" if p.pruned else (" [REINFORCED]" if p.is_reinforced else "")
            print(f"  {p.id} | score={p.score:.2f} | {p.usage_count}u/{p.success_count}s | "
                  f"{p.source_domain}{status}")
            print(f"    {p.text[:80]}")

    elif args.cmd == "score":
        if not args.success and not args.failure:
            print("Error: --success or --failure required", file=sys.stderr)
            sys.exit(1)
        try:
            p = record_usage(args.id, success=args.success, session=args.session)
            print(f"Updated: {p.id} -> score={p.score:.2f} ({p.usage_count}u/{p.success_count}s)")
        except (KeyError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "prune":
        pruned = prune_principles(dry_run=args.dry_run)
        action = "Would prune" if args.dry_run else "Pruned"
        if pruned:
            print(f"{action} {len(pruned)} principles: {', '.join(pruned)}")
        else:
            print("Nothing to prune.")

    elif args.cmd == "top":
        principles = get_top_principles(n=args.n, domain=args.domain)
        if not principles:
            print("No principles found.")
            return
        for i, p in enumerate(principles, 1):
            print(f"  {i}. [{p.score:.2f}] {p.text[:70]}")
            print(f"     {p.id} | {p.source_domain} | {p.usage_count}u/{p.success_count}s")

    elif args.cmd == "stats":
        stats = get_stats()
        print(f"Principles: {stats['active']} active, {stats['pruned']} pruned, "
              f"{stats['reinforced']} reinforced")
        print(f"Avg score: {stats['avg_score']:.2f} | Prunable: {stats['prunable']}")
        if stats["domain_counts"]:
            print("By domain:")
            for d, c in sorted(stats["domain_counts"].items()):
                print(f"  {d}: {c}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
