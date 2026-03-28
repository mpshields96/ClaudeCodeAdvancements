#!/usr/bin/env python3
"""confidence_recalibrator.py — MT-49 Phase 4: Principle confidence recalibration.

Applies Bayesian-inspired decay/boost to principle scores based on:
1. Staleness — principles not used recently decay toward the prior
2. Track record — Laplace-smoothed success rate (from principle_registry)

The recalibrated score = base_score * staleness_factor, where:
- base_score = (success + 1) / (usage + 2)  [Laplace-smoothed]
- staleness_factor = exp(-lambda * sessions_since_last_use)
  with lambda = 0.01 (half-life ~70 sessions)

Read-only mode (recalibrate/summary): produces a view without modifying files.
Apply mode: writes recalibrated scores back to principles.jsonl using atomic rewrite.
  - Checkpoint (recal_checkpoint.json) prevents double-applying within min_gap sessions.
  - Only principles with >DECAY_THRESHOLD score change are updated.
  - --dry-run flag previews changes without writing.

Usage:
    python3 self-learning/confidence_recalibrator.py recalibrate [--session N]
    python3 self-learning/confidence_recalibrator.py summary [--session N]
    python3 self-learning/confidence_recalibrator.py apply [--session N] [--dry-run]

Stdlib only. No external dependencies.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.expanduser("~"), ".claude-memory", "recal_checkpoint.json"
)
DEFAULT_MIN_GAP = 10  # Minimum sessions between recalibration runs

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


def _load_checkpoint(checkpoint_path: str) -> dict:
    """Load recalibration checkpoint. Returns empty dict if not found."""
    if not os.path.exists(checkpoint_path):
        return {}
    try:
        with open(checkpoint_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_checkpoint(checkpoint_path: str, current_session: int) -> None:
    """Save recalibration checkpoint atomically."""
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    tmp = checkpoint_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"last_recalibrated_session": current_session}, f)
    os.replace(tmp, checkpoint_path)


def apply_recalibration(
    principles_path: str = PRINCIPLES_PATH,
    current_session: int = 0,
    checkpoint_path: str = DEFAULT_CHECKPOINT_PATH,
    min_gap: int = DEFAULT_MIN_GAP,
    dry_run: bool = False,
) -> dict:
    """Apply recalibrated scores back to principles.jsonl.

    Writes updated score entries for principles whose recalibrated score
    differs from the original by more than DECAY_THRESHOLD. Uses a checkpoint
    to prevent double-applying within min_gap sessions.

    Args:
        principles_path: Path to principles.jsonl
        current_session: Current session number
        checkpoint_path: Path to checkpoint JSON file
        min_gap: Minimum sessions between recalibration runs
        dry_run: If True, compute changes but do not write

    Returns:
        dict with keys: applied (int), skipped (int), reason (str), changes (list)
    """
    # Check checkpoint
    cp = _load_checkpoint(checkpoint_path)
    last_session = cp.get("last_recalibrated_session", 0)
    gap = current_session - last_session

    if gap < min_gap and not dry_run:
        return {
            "applied": 0,
            "skipped": 0,
            "reason": f"recalibrated recently (session {last_session}, gap={gap} < min_gap={min_gap})",
            "changes": [],
        }

    principles = _load_principles(principles_path)
    changes = []

    for pid, p in principles.items():
        if p.pruned:
            continue

        orig = p.score
        sf = staleness_factor(p.last_used_session, current_session)
        recal = max(0.0, min(1.0, orig * sf))

        # Only update if change exceeds threshold
        if abs(orig - recal) > DECAY_THRESHOLD:
            changes.append({
                "id": pid,
                "original_score": round(orig, 4),
                "recalibrated_score": round(recal, 4),
                "staleness_factor": round(sf, 4),
                "text": p.text[:80],
            })

    if dry_run:
        return {
            "applied": len(changes),
            "skipped": len(principles) - len(changes),
            "reason": "dry_run",
            "changes": changes,
        }

    # Apply: append updated entries to JSONL (latest-wins semantics)
    now_iso = datetime.now(timezone.utc).isoformat()
    if changes:
        with open(principles_path, "a") as f:
            for change in changes:
                p = principles[change["id"]]
                updated = p.to_dict()
                updated["score"] = change["recalibrated_score"]
                updated["updated_at"] = now_iso
                updated["source_context"] = (
                    f"{updated.get('source_context', '')} "
                    f"[recalibrated s{current_session}: "
                    f"{change['original_score']:.3f}->{change['recalibrated_score']:.3f}]"
                ).strip()
                f.write(json.dumps(updated) + "\n")

    _save_checkpoint(checkpoint_path, current_session)

    return {
        "applied": len(changes),
        "skipped": len([p for p in principles.values() if not p.pruned]) - len(changes),
        "reason": "ok",
        "changes": changes,
    }


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

    apply_p = sub.add_parser("apply", help="Apply recalibrated scores to principles.jsonl")
    apply_p.add_argument("--session", type=int, default=0, help="Current session number")
    apply_p.add_argument("--principles-path", default=None)
    apply_p.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT_PATH,
                         help="Path to checkpoint JSON")
    apply_p.add_argument("--min-gap", type=int, default=DEFAULT_MIN_GAP,
                         help="Minimum sessions between runs")
    apply_p.add_argument("--dry-run", action="store_true",
                         help="Preview changes without writing")

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
    elif args.command == "apply":
        result = apply_recalibration(
            principles_path=path,
            current_session=args.session,
            checkpoint_path=args.checkpoint,
            min_gap=args.min_gap,
            dry_run=args.dry_run,
        )
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"{prefix}Recalibration apply: {result['applied']} updated, "
              f"{result['skipped']} unchanged — {result['reason']}")
        if result["changes"]:
            for c in result["changes"][:5]:
                print(f"  {c['text'][:60]} — "
                      f"{c['original_score']:.3f} -> {c['recalibrated_score']:.3f}")
            if len(result["changes"]) > 5:
                print(f"  ... and {len(result['changes']) - 5} more")
    else:
        print("Usage: confidence_recalibrator.py {recalibrate|summary|apply}")
        print("  recalibrate [--session N] [--json]  — View recalibrated scores (read-only)")
        print("  summary [--session N]               — Show summary counts")
        print("  apply [--session N] [--dry-run]     — Write recalibrated scores back")


if __name__ == "__main__":
    main()
