#!/usr/bin/env python3
"""
stagnation_resolver.py — Formalize decisions for stagnating master tasks.

When priority_picker flags MTs as stagnating (many sessions untouched),
this tool classifies severity and recommends actions: archive, reduce
priority, or schedule dedicated time.

CLI:
    python3 stagnation_resolver.py analyze       # Analyze all stagnating MTs
    python3 stagnation_resolver.py resolve MT-18  # Record a decision for MT-18

Stdlib only. No external dependencies.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

CCA_DIR = Path.home() / "Projects/ClaudeCodeAdvancements"
STAGNATION_LOG = CCA_DIR / ".cca-stagnation-log.jsonl"

# Severity thresholds (sessions untouched)
# Adjusted by base_value and completion_pct
THRESHOLD_MILD = 10
THRESHOLD_MODERATE = 25
THRESHOLD_SEVERE = 40
THRESHOLD_CRITICAL = 75


def classify_stagnation(
    sessions_untouched: int,
    completion_pct: float,
    base_value: int,
) -> dict:
    """Classify an MT's stagnation severity.

    Higher base_value and completion_pct reduce severity
    (valuable and partially-done work deserves more patience).
    """
    if sessions_untouched <= 0 or completion_pct >= 100:
        return {"severity": "none", "score": 0}

    # Adjust threshold based on value and completion
    # High value (8-10) gets 2x patience, low value (1-3) gets 0.5x
    value_factor = max(0.5, min(2.0, base_value / 5.0))
    # Partial completion (50%+) gets 1.5x patience
    completion_factor = 1.5 if completion_pct >= 50 else (1.2 if completion_pct > 0 else 1.0)

    adjusted = sessions_untouched / (value_factor * completion_factor)

    if adjusted >= THRESHOLD_CRITICAL:
        severity = "critical"
    elif adjusted >= THRESHOLD_SEVERE:
        severity = "severe"
    elif adjusted >= THRESHOLD_MODERATE:
        severity = "moderate"
    elif adjusted >= THRESHOLD_MILD:
        severity = "mild"
    else:
        severity = "none"

    return {"severity": severity, "score": round(adjusted, 1)}


def recommend_action(
    mt_id: str,
    severity: str,
    sessions_untouched: int,
    completion_pct: float,
) -> dict:
    """Recommend an action for a stagnating MT."""
    if severity == "none":
        return {"mt_id": mt_id, "action": "none", "reason": "Not stagnating"}

    # Partial completion prefers scheduling over archiving
    has_progress = completion_pct > 0

    if severity == "critical":
        if has_progress and completion_pct >= 50:
            return {
                "mt_id": mt_id,
                "action": "schedule",
                "reason": f"{sessions_untouched} sessions untouched but {completion_pct}% done — schedule dedicated time",
            }
        return {
            "mt_id": mt_id,
            "action": "archive",
            "reason": f"{sessions_untouched} sessions untouched, {completion_pct}% complete — archive and revisit if priorities change",
        }

    if severity == "severe":
        if has_progress and completion_pct >= 50:
            return {
                "mt_id": mt_id,
                "action": "schedule",
                "reason": f"{sessions_untouched} sessions untouched but {completion_pct}% done — schedule within 5 sessions",
            }
        return {
            "mt_id": mt_id,
            "action": "archive" if not has_progress else "reduce_priority",
            "reason": f"{sessions_untouched} sessions untouched, {completion_pct}% complete",
        }

    if severity == "moderate":
        if has_progress and completion_pct >= 50:
            return {
                "mt_id": mt_id,
                "action": "schedule",
                "reason": f"Stagnating at {completion_pct}% — needs dedicated session",
            }
        return {
            "mt_id": mt_id,
            "action": "reduce_priority",
            "reason": f"{sessions_untouched} sessions untouched — reduce base_value or deprioritize",
        }

    # mild
    return {
        "mt_id": mt_id,
        "action": "reduce_priority" if not has_progress else "schedule",
        "reason": f"Mildly stagnating ({sessions_untouched} sessions) — monitor",
    }


def record_decision(
    mt_id: str,
    action: str,
    reason: str,
    log_file: Path = STAGNATION_LOG,
) -> None:
    """Record a stagnation resolution decision."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "mt_id": mt_id,
        "action": action,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_decisions(log_file: Path = STAGNATION_LOG) -> list:
    """Load stagnation resolution history."""
    if not log_file.exists():
        return []
    decisions = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                decisions.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return decisions


def analyze_batch(mts: List[dict]) -> List[dict]:
    """Analyze multiple MTs for stagnation."""
    results = []
    for mt in mts:
        classification = classify_stagnation(
            mt["sessions_untouched"],
            mt.get("completion_pct", 0),
            mt.get("base_value", 5),
        )
        recommendation = recommend_action(
            mt["mt_id"],
            classification["severity"],
            mt["sessions_untouched"],
            mt.get("completion_pct", 0),
        )
        recommendation["severity"] = classification["severity"]
        recommendation["score"] = classification["score"]
        results.append(recommendation)
    return results


def format_report(results: List[dict]) -> str:
    """Format analysis results as a human-readable report."""
    if not results:
        return "No stagnating MTs found."

    actionable = [r for r in results if r["action"] != "none"]
    if not actionable:
        return "No stagnating MTs require action."

    lines = ["Stagnation Report:", "=" * 40]
    for r in sorted(actionable, key=lambda x: ["none", "mild", "moderate", "severe", "critical"].index(x["severity"]), reverse=True):
        lines.append(f"\n{r['mt_id']} [{r['severity'].upper()}]")
        lines.append(f"  Action: {r['action']}")
        lines.append(f"  Reason: {r['reason']}")
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python3 stagnation_resolver.py analyze")
        print("  python3 stagnation_resolver.py resolve MT-ID action reason")
        sys.exit(0)

    cmd = args[0]

    if cmd == "analyze":
        # Hardcoded known stagnating MTs — in production, parse from MASTER_TASKS.md
        known_stagnating = [
            {"mt_id": "MT-18", "sessions_untouched": 98, "completion_pct": 0, "base_value": 4},
            {"mt_id": "MT-13", "sessions_untouched": 49, "completion_pct": 0, "base_value": 4},
        ]
        results = analyze_batch(known_stagnating)
        print(format_report(results))

    elif cmd == "resolve":
        if len(args) < 4:
            print("Usage: stagnation_resolver.py resolve MT-ID action reason")
            sys.exit(1)
        mt_id, action, reason = args[1], args[2], " ".join(args[3:])
        record_decision(mt_id, action, reason)
        print(f"Recorded: {mt_id} -> {action}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
