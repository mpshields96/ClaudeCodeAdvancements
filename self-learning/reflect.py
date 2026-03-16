#!/usr/bin/env python3
"""
reflect.py — CCA Self-Learning Reflection Engine

Reads the journal, detects patterns, and outputs actionable recommendations.
Optionally updates strategy.json with tuned parameters.

Usage:
    python3 self-learning/reflect.py                    # Full reflection report
    python3 self-learning/reflect.py --domain nuclear_scan  # Domain-specific
    python3 self-learning/reflect.py --apply             # Apply suggested strategy changes
    python3 self-learning/reflect.py --brief             # One-paragraph summary
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from journal import (
    _load_journal, _load_strategy, _save_strategy,
    get_stats, get_nuclear_metrics, get_all_learnings,
    log_event, VALID_DOMAINS,
)


def _days_between(ts1, ts2):
    """Days between two ISO timestamps."""
    try:
        d1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return abs((d2 - d1).days)
    except (ValueError, AttributeError):
        return 0


def detect_patterns(entries, min_sample=5):
    """Detect recurring patterns from journal entries."""
    patterns = []

    if len(entries) < 2:
        return patterns

    # Pattern 1: Verdict distribution drift
    nuclear = [e for e in entries if e.get("event_type") == "nuclear_batch"]
    if len(nuclear) >= 2:
        total_metrics = {}
        for e in nuclear:
            for k, v in e.get("metrics", {}).items():
                if isinstance(v, (int, float)):
                    total_metrics[k] = total_metrics.get(k, 0) + v

        reviewed = total_metrics.get("posts_reviewed", 0)
        if reviewed > 0:
            build_rate = total_metrics.get("build", 0) / reviewed
            skip_rate = (total_metrics.get("skip", 0) + total_metrics.get("fast_skip", 0)) / reviewed

            if skip_rate > 0.6:
                patterns.append({
                    "type": "high_skip_rate",
                    "severity": "info",
                    "message": f"Skip rate is {skip_rate:.0%} — consider raising min_score_threshold to filter more noise upfront",
                    "data": {"skip_rate": round(skip_rate, 3), "build_rate": round(build_rate, 3)},
                    "suggestion": {"nuclear_scan.min_score_threshold": 50},
                })

            if build_rate < 0.03 and reviewed >= min_sample:
                patterns.append({
                    "type": "low_build_rate",
                    "severity": "warning",
                    "message": f"BUILD rate is only {build_rate:.1%} across {reviewed} posts — refine high_value_keywords or scan different subreddits",
                    "data": {"build_rate": round(build_rate, 3), "reviewed": reviewed},
                })

    # Pattern 2: Domain concentration
    domain_counts = Counter(e.get("domain", "unknown") for e in entries)
    total = len(entries)
    for domain, count in domain_counts.most_common(3):
        if count / total > 0.7 and total >= min_sample:
            patterns.append({
                "type": "domain_concentration",
                "severity": "info",
                "message": f"{domain} accounts for {count/total:.0%} of all journal entries — diversify or acknowledge specialization",
                "data": {"domain": domain, "pct": round(count / total, 2)},
            })

    # Pattern 3: Recurring learnings (same learning appears multiple times)
    all_learnings = []
    for e in entries:
        all_learnings.extend(e.get("learnings", []))
    if all_learnings:
        learning_words = Counter()
        for l in all_learnings:
            # Extract key phrases (words > 4 chars)
            words = [w.lower() for w in l.split() if len(w) > 4]
            learning_words.update(words)

        repeated = [(w, c) for w, c in learning_words.most_common(10) if c >= 3]
        if repeated:
            patterns.append({
                "type": "recurring_themes",
                "severity": "info",
                "message": f"Recurring learning themes: {', '.join(w for w, _ in repeated[:5])}",
                "data": {"themes": repeated[:5]},
            })

    # Pattern 4: Session outcome trends
    outcomes = [e for e in entries if e.get("event_type") == "session_outcome"]
    if len(outcomes) >= 3:
        recent_3 = outcomes[-3:]
        failures = sum(1 for o in recent_3 if o.get("outcome") == "failure")
        if failures >= 2:
            patterns.append({
                "type": "consecutive_failures",
                "severity": "warning",
                "message": f"{failures}/3 recent sessions had failure outcome — investigate root cause",
                "data": {"recent_outcomes": [o.get("outcome") for o in recent_3]},
            })

    # Pattern 5: Strategy version staleness
    strategy = _load_strategy()
    updated = strategy.get("updated_at", "")
    if updated:
        days_old = _days_between(updated, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        if days_old > 14 and len(entries) >= 10:
            patterns.append({
                "type": "stale_strategy",
                "severity": "info",
                "message": f"Strategy config is {days_old} days old with {len(entries)} journal entries since — consider running reflect --apply",
                "data": {"days_old": days_old, "entries_since": len(entries)},
            })

    return patterns


def generate_recommendations(entries, patterns, strategy):
    """Generate actionable recommendations from patterns and data."""
    recs = []

    nuclear_metrics = get_nuclear_metrics()
    if nuclear_metrics:
        sr = nuclear_metrics.get("signal_rate", 0)
        if sr > 0:
            recs.append(f"Nuclear signal rate: {sr:.1%} (BUILD+ADAPT per post reviewed)")

        reviewed = nuclear_metrics.get("posts_reviewed", 0)
        total_batches = nuclear_metrics.get("batches", 0)
        if total_batches > 0:
            recs.append(f"Average batch size: {reviewed / total_batches:.0f} posts/batch")

    # Check if any strategy adjustments from patterns
    for p in patterns:
        if p.get("suggestion"):
            for key, val in p["suggestion"].items():
                parts = key.split(".")
                current = strategy
                for part in parts[:-1]:
                    current = current.get(part, {})
                current_val = current.get(parts[-1])
                if current_val is not None and current_val != val:
                    recs.append(f"Suggest: {key} {current_val} -> {val} ({p['message']})")

    # Learning density
    all_l = get_all_learnings()
    if all_l:
        recs.append(f"Total learnings captured: {len(all_l)} across {len(set(l['domain'] for l in all_l))} domains")

    return recs


def apply_suggestions(patterns, strategy):
    """Apply pattern-suggested changes to strategy config."""
    changes = []
    for p in patterns:
        if not p.get("suggestion"):
            continue
        for key, val in p["suggestion"].items():
            parts = key.split(".")
            current = strategy
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            old_val = current.get(parts[-1])
            if old_val != val:
                current[parts[-1]] = val
                changes.append(f"{key}: {old_val} -> {val}")

    if changes:
        strategy["version"] = strategy.get("version", 0) + 1
        strategy["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        strategy["updated_by"] = "reflect.py"
        _save_strategy(strategy)

        # Log the strategy update
        log_event(
            event_type="strategy_update",
            domain="self_learning",
            outcome="success",
            learnings=changes,
            notes=f"Auto-applied {len(changes)} changes from pattern detection",
        )

    return changes


def reflect(domain=None, apply=False, brief=False):
    """Run full reflection and output report."""
    entries = _load_journal()

    if domain:
        entries = [e for e in entries if e.get("domain") == domain]

    strategy = _load_strategy()
    patterns = detect_patterns(entries)
    recs = generate_recommendations(entries, patterns, strategy)

    if brief:
        stats = get_stats()
        total = stats.get("total_entries", 0)
        if total == 0:
            print("No journal entries yet. Start logging with: python3 self-learning/journal.py log <event_type>")
            return

        pattern_summary = "; ".join(p["message"] for p in patterns[:3]) if patterns else "no patterns detected yet"
        print(f"CCA Self-Learning: {total} entries, {len(patterns)} patterns detected. {pattern_summary}")
        return

    # Full report
    print("=" * 60)
    print("CCA SELF-LEARNING REFLECTION REPORT")
    print(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if domain:
        print(f"Domain filter: {domain}")
    print("=" * 60)

    stats = get_stats()
    print(f"\nJournal: {stats.get('total_entries', 0)} entries")
    print(f"Sessions logged: {stats.get('sessions_logged', [])}")
    print(f"Period: {stats.get('first_entry', '?')} to {stats.get('last_entry', '?')}")

    if stats.get("by_event_type"):
        print(f"\nBy event type:")
        for k, v in sorted(stats["by_event_type"].items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")

    if stats.get("by_domain"):
        print(f"\nBy domain:")
        for k, v in sorted(stats["by_domain"].items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")

    # Nuclear-specific metrics
    nm = get_nuclear_metrics()
    if nm and (not domain or domain == "nuclear_scan"):
        print(f"\n--- Nuclear Scan Metrics ---")
        print(f"Sessions: {nm['sessions']} | Batches: {nm['batches']}")
        print(f"Posts reviewed: {nm['posts_reviewed']}")
        print(f"BUILD: {nm['build']} | ADAPT: {nm['adapt']} | REF: {nm['reference']} | SKIP: {nm['skip']} | FAST-SKIP: {nm.get('fast_skip', 0)}")
        if "signal_rate" in nm:
            print(f"Signal rate (BUILD+ADAPT/reviewed): {nm['signal_rate']:.1%}")
        if "build_rate" in nm:
            print(f"BUILD rate: {nm['build_rate']:.1%}")

    # Patterns
    if patterns:
        print(f"\n--- Detected Patterns ({len(patterns)}) ---")
        for p in patterns:
            severity = p["severity"].upper()
            print(f"[{severity}] {p['type']}: {p['message']}")

    # Recommendations
    if recs:
        print(f"\n--- Recommendations ---")
        for r in recs:
            print(f"  - {r}")

    # Apply suggestions if requested
    if apply:
        changes = apply_suggestions(patterns, strategy)
        if changes:
            print(f"\n--- Applied Strategy Changes ---")
            for c in changes:
                print(f"  APPLIED: {c}")
            print(f"Strategy version bumped to v{strategy.get('version', '?')}")
        else:
            print("\nNo strategy changes to apply.")

    print("\n" + "=" * 60)


def _cli():
    parser = argparse.ArgumentParser(description="CCA Self-Learning Reflection")
    parser.add_argument("--domain", choices=VALID_DOMAINS, help="Filter by domain")
    parser.add_argument("--apply", action="store_true", help="Apply suggested strategy changes")
    parser.add_argument("--brief", action="store_true", help="One-line summary")
    args = parser.parse_args()
    reflect(domain=args.domain, apply=args.apply, brief=args.brief)


if __name__ == "__main__":
    _cli()
