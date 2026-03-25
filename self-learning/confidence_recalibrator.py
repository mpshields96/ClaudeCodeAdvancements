#!/usr/bin/env python3
"""confidence_recalibrator.py — MT-49 Phase 4: Principle confidence recalibration.

Applies Bayesian-inspired decay/boost to principle scores based on:
1. Staleness — principles not used recently decay toward the prior
2. Track record — Laplace-smoothed success rate (from principle_registry)

The recalibrated score = base_score * staleness_factor, where:
- base_score = (success + 1) / (usage + 2)  [Laplace-smoothed]
- staleness_factor = exp(-lambda * sessions_since_last_use)
  with lambda = 0.01 (half-life ~70 sessions)

This does NOT modify principles.jsonl — it produces a read-only view.
Use the output to inform priority decisions and pruning recommendations.

Usage:
    python3 self-learning/confidence_recalibrator.py recalibrate [--session N]
    python3 self-learning/confidence_recalibrator.py summary [--session N]

Stdlib only. No external dependencies.
"""

import argparse
import json
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import _load_principles, PRINCIPLES_PATH

# Decay constant: lambda = 0.01 means half-life ~69 sessions (ln(2)/0.01)
DECAY_LAMBDA = 0.01
# Floor: even very stale principles don't go below this factor
STALENESS_FLOOR = 0.3
# Threshold for categorizing change
DECAY_THRESHOLD = 0.1  # >10% drop = "decay"


def staleness_factor(last_used_session: int, current_session: int) -> float:
    """Compute staleness decay factor.

    Returns a float in [STALENESS_FLOOR, 1.0].
    Exponential decay: exp(-lambda * gap), floored.
    """
    gap = max(0, current_session - last_used_session)
    raw = math.exp(-DECAY_LAMBDA * gap)
    return max(STALENESS_FLOOR, min(1.0, raw))


def recalibrated_score(success_count: int, usage_count: int,
                       last_used_session: int, current_session: int) -> float:
    """Compute recalibrated score for a principle.

    base_score * staleness_factor, clamped to [0, 1].
    """
    base = (success_count + 1) / (usage_count + 2)
    sf = staleness_factor(last_used_session, current_session)
    return max(0.0, min(1.0, base * sf))


def recalibrate_all(principles_path: str = PRINCIPLES_PATH,
                    current_session: int = 0) -> dict:
    """Recalibrate all non-pruned principles.

    Returns dict: {principle_id: {original_score, recalibrated_score, staleness_factor, text, last_used_session}}
    """
    principles = _load_principles(principles_path)
    results = {}

    for pid, p in principles.items():
        if p.pruned:
            continue

        orig = p.score
        sf = staleness_factor(p.last_used_session, current_session)
        recal = max(0.0, min(1.0, orig * sf))

        results[pid] = {
            "original_score": round(orig, 4),
            "recalibrated_score": round(recal, 4),
            "staleness_factor": round(sf, 4),
            "text": p.text,
            "last_used_session": p.last_used_session,
        }

    return results


def categorize_change(original: float, recalibrated: float) -> str:
    """Categorize the score change: decay, stable, or boost."""
    diff = original - recalibrated
    if diff > DECAY_THRESHOLD:
        return "decay"
    return "stable"


def recalibration_summary(results: dict) -> dict:
    """Summarize recalibration results."""
    if not results:
        return {"total": 0, "decayed": 0, "stable": 0}

    decayed = 0
    stable = 0
    for entry in results.values():
        cat = categorize_change(entry["original_score"], entry["recalibrated_score"])
        if cat == "decay":
            decayed += 1
        else:
            stable += 1

    return {
        "total": len(results),
        "decayed": decayed,
        "stable": stable,
    }


def format_report(results: dict, current_session: int = 0) -> str:
    """Format a human-readable recalibration report."""
    if not results:
        return f"Recalibration: 0 principles (session {current_session})"

    summary = recalibration_summary(results)
    lines = [
        f"Recalibration: {summary['total']} principles (session {current_session})",
        f"  Decayed: {summary['decayed']}  Stable: {summary['stable']}",
    ]

    # Show top decayed principles
    decayed = [
        (pid, e) for pid, e in results.items()
        if categorize_change(e["original_score"], e["recalibrated_score"]) == "decay"
    ]
    decayed.sort(key=lambda x: x[1]["staleness_factor"])

    if decayed:
        lines.append("")
        lines.append("  Most decayed:")
        for pid, e in decayed[:5]:
            gap = current_session - e["last_used_session"]
            lines.append(
                f"    {e['text'][:60]} — "
                f"{e['original_score']:.2f} -> {e['recalibrated_score']:.2f} "
                f"(stale {gap} sessions)"
            )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Principle confidence recalibration")
    sub = parser.add_subparsers(dest="command")

    recal = sub.add_parser("recalibrate", help="Recalibrate all principles")
    recal.add_argument("--session", type=int, default=0, help="Current session number")
    recal.add_argument("--principles-path", default=None)
    recal.add_argument("--json", action="store_true", help="JSON output")

    summ = sub.add_parser("summary", help="Show recalibration summary")
    summ.add_argument("--session", type=int, default=0, help="Current session number")
    summ.add_argument("--principles-path", default=None)

    args = parser.parse_args()
    path = getattr(args, "principles_path", None) or PRINCIPLES_PATH

    if args.command == "recalibrate":
        results = recalibrate_all(path, args.session)
        if getattr(args, "json", False):
            print(json.dumps(results, indent=2))
        else:
            print(format_report(results, args.session))
    elif args.command == "summary":
        results = recalibrate_all(path, args.session)
        summary = recalibration_summary(results)
        print(json.dumps(summary, indent=2))
    else:
        print("Usage: confidence_recalibrator.py {recalibrate|summary}")
        print("  recalibrate [--session N] [--json]  — Recalibrate all principles")
        print("  summary [--session N]               — Show recalibration summary")


if __name__ == "__main__":
    main()
