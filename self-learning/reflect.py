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
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from journal import (
    _load_journal, _load_strategy, _save_strategy,
    get_stats, get_nuclear_metrics, get_trading_metrics, get_all_learnings,
    get_pain_win_summary, log_event, VALID_DOMAINS,
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
    """Detect recurring patterns from journal entries.

    Uses the pattern registry (MT-28 Phase 2) to run all registered detectors.
    Import detectors module to ensure built-in detectors are registered.
    """
    if len(entries) < 2:
        return []

    # Ensure built-in detectors are registered
    try:
        import detectors  # noqa: F401 — side-effect import registers detectors
    except ImportError:
        pass

    from pattern_registry import run_all_detectors
    strategy = _load_strategy()
    return run_all_detectors(entries=entries, strategy=strategy)


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


def _clamp_to_bounds(key, value, strategy):
    """Enforce bounded parameter safety rails. Returns clamped value or None if unbounded."""
    bounds = strategy.get("bounds", {})
    b = bounds.get(key)
    if not b:
        return None  # No bounds defined — reject auto-adjust for this key
    if not isinstance(value, (int, float)):
        return None
    lo, hi = b.get("min", float("-inf")), b.get("max", float("inf"))
    step = b.get("step", 1)
    clamped = max(lo, min(hi, value))
    # Snap to nearest step from min
    if step and step > 0 and lo != float("-inf"):
        clamped = lo + round((clamped - lo) / step) * step
        clamped = max(lo, min(hi, clamped))
    # Preserve int type if original was int
    if isinstance(value, int):
        clamped = int(clamped)
    return clamped


def apply_suggestions(patterns, strategy):
    """Apply pattern-suggested changes to strategy config.

    Safety rails:
    - Only adjusts parameters that have bounds defined in strategy.bounds
    - Clamps values to [min, max] range and snaps to step increments
    - Respects learning.auto_adjust_enabled flag
    - Logs every change with before/after values
    """
    auto_enabled = strategy.get("learning", {}).get("auto_adjust_enabled", False)
    changes = []
    rejected = []

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
            if old_val == val:
                continue

            if not auto_enabled:
                rejected.append(f"{key}: {old_val} -> {val} (auto_adjust disabled)")
                continue

            clamped = _clamp_to_bounds(key, val, strategy)
            if clamped is None:
                rejected.append(f"{key}: {old_val} -> {val} (no bounds defined — rejected)")
                continue

            if clamped == old_val:
                rejected.append(f"{key}: {old_val} -> {val} (clamped to {clamped}, no change)")
                continue

            current[parts[-1]] = clamped
            if clamped != val:
                changes.append(f"{key}: {old_val} -> {clamped} (requested {val}, clamped)")
            else:
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


def reflect(domain=None, apply=False, brief=False, propose=False, session_id=None):
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

    # Trading metrics
    tm = get_trading_metrics()
    if tm and (not domain or domain == "trading"):
        print(f"\n--- Trading Metrics ---")
        print(f"Bets: {tm['total_bets']} | Wins: {tm['wins']} | Losses: {tm['losses']} | Voids: {tm['voids']}")
        if "win_rate" in tm:
            print(f"Win rate: {tm['win_rate']:.1%} | PnL: {tm['total_pnl_cents']}c")
        if tm["by_strategy"]:
            print(f"By strategy:")
            for s, d in sorted(tm["by_strategy"].items(), key=lambda x: -x[1]["pnl_cents"]):
                wr = d["wins"] / (d["wins"] + d["losses"]) if (d["wins"] + d["losses"]) > 0 else 0
                print(f"  {s}: {d['bets']} bets, {wr:.0%} WR, {d['pnl_cents']}c PnL")
        if tm["research"]["total_sessions"] > 0:
            r = tm["research"]
            print(f"Research: {r['total_sessions']} sessions, {r['actionable']} actionable ({r.get('actionable_rate', 0):.0%})")
            print(f"Edges: {r['edges_discovered']} discovered, {r['edges_rejected']} rejected")

    # Pain/Win summary
    pw = get_pain_win_summary()
    if pw["pain_count"] + pw["win_count"] > 0:
        print(f"\n--- Pain/Win Signals ---")
        print(f"Wins: {pw['win_count']} | Pains: {pw['pain_count']} | Ratio: {pw['ratio']:.0%} wins" if pw["ratio"] else "")
        if pw["pain_domains"]:
            print(f"Pain by domain: {dict(pw['pain_domains'])}")
        if pw["win_domains"]:
            print(f"Win by domain: {dict(pw['win_domains'])}")

    # Principles (MT-28)
    try:
        from principle_registry import get_top_principles, get_stats as get_principle_stats
        pstats = get_principle_stats()
        if pstats["active"] > 0:
            print(f"\n--- Strategic Principles ({pstats['active']} active, {pstats['reinforced']} reinforced) ---")
            top = get_top_principles(n=5, domain=domain)
            for i, p in enumerate(top, 1):
                status = " [REINFORCED]" if p.is_reinforced else ""
                print(f"  {i}. [{p.score:.2f}] {p.text[:70]}{status}")
            if pstats["prunable"] > 0:
                print(f"  ({pstats['prunable']} principles eligible for pruning)")
    except ImportError:
        pass  # principle_registry not available yet

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

    # MT-10: Generate improvement proposals from detected patterns
    if propose and patterns:
        try:
            from improver import Improver
            imp = Improver(auto_approve_low=True)
            proposals = imp.generate_from_reflect(patterns, session_id=session_id)
            if proposals:
                print(f"\n--- Improvement Proposals ({len(proposals)}) ---")
                for p in proposals:
                    print(f"  [{p.risk_level}] {p.pattern_type}: {p.proposed_fix[:100]}")
            else:
                print("\nNo new improvement proposals (all deduped or already tracked).")
        except Exception as e:
            print(f"\n  [improver] Error generating proposals: {e}", file=sys.stderr)

    print("\n" + "=" * 60)


def micro_reflect(last_n=10):
    """Lightweight mid-session reflection. Returns quick insights dict.

    Unlike full reflect(), this is designed to be called after completing
    a deliverable — it's fast, returns data (not prints), and focuses on
    the most recent entries only.

    Returns dict with: patterns_found, recommendations, session_health.
    """
    entries = _load_journal()
    recent = entries[-last_n:] if len(entries) > last_n else entries

    result = {
        "entries_checked": len(recent),
        "patterns": [],
        "recommendations": [],
        "session_health": "unknown",
    }

    if len(recent) < 2:
        result["session_health"] = "insufficient_data"
        return result

    # Quick pattern checks on recent entries only
    # 1. Repeated failures in same domain
    failures = [e for e in recent if e.get("outcome") in ("failure", "needs_improvement")]
    if len(failures) >= 3:
        domains = Counter(e.get("domain", "unknown") for e in failures)
        top_domain, count = domains.most_common(1)[0]
        if count >= 2:
            result["patterns"].append({
                "type": "repeated_failure",
                "domain": top_domain,
                "count": count,
                "message": f"{count} failures in {top_domain} domain in last {last_n} entries",
            })
            result["recommendations"].append(
                f"Investigate {top_domain} failures — may need approach change"
            )

    # 2. High success rate (positive signal — keep doing this)
    successes = [e for e in recent if e.get("outcome") == "success"]
    if len(successes) >= len(recent) * 0.7 and len(recent) >= 5:
        result["patterns"].append({
            "type": "high_success_streak",
            "count": len(successes),
            "message": f"{len(successes)}/{len(recent)} recent entries are successes",
        })

    # 3. Trading-specific: check for negative PnL trend
    bets = [e for e in recent if e.get("event_type") == "bet_outcome"]
    if len(bets) >= 5:
        pnl_values = [e.get("metrics", {}).get("pnl_cents", 0) for e in bets]
        total_pnl = sum(pnl_values)
        if total_pnl < 0:
            result["patterns"].append({
                "type": "negative_pnl_recent",
                "total_pnl_cents": total_pnl,
                "bets": len(bets),
                "message": f"Recent {len(bets)} bets show negative PnL: {total_pnl}c",
            })
            result["recommendations"].append(
                "Review recent losing bets — check if pattern is structural or variance"
            )

    # 4. Stale domains (nothing logged for a while)
    if entries:
        domains_seen = set(e.get("domain") for e in recent if e.get("domain"))
        all_domains = set(e.get("domain") for e in entries if e.get("domain"))
        stale = all_domains - domains_seen - {"unknown", None}
        if stale and len(stale) <= 3:  # Don't warn about everything
            result["patterns"].append({
                "type": "stale_domains",
                "domains": sorted(stale),
                "message": f"Domains not active recently: {', '.join(sorted(stale))}",
            })

    # Overall health
    if result["patterns"]:
        has_negative = any(p["type"] in ("repeated_failure", "negative_pnl_recent")
                          for p in result["patterns"])
        result["session_health"] = "needs_attention" if has_negative else "good"
    else:
        result["session_health"] = "good"

    return result


# State file for tracking when last auto-reflect ran
_AUTO_REFLECT_STATE = os.path.join(SCRIPT_DIR, ".auto_reflect_state.json")


def auto_reflect_if_due(every_n=10, session_id=None):
    """Check if auto-reflection is due and run it if so.

    Tracks the journal entry count at last reflection. If N new entries
    have been logged since then, runs micro_reflect() and logs the result
    to the journal.

    Returns the micro_reflect result if it ran, None if not due yet.
    """
    entries = _load_journal()
    current_count = len(entries)

    # Load last reflect state
    last_count = 0
    if os.path.exists(_AUTO_REFLECT_STATE):
        try:
            with open(_AUTO_REFLECT_STATE) as f:
                state = json.load(f)
                last_count = state.get("last_entry_count", 0)
        except (json.JSONDecodeError, OSError):
            last_count = 0

    if current_count - last_count < every_n:
        return None  # Not due yet

    # Run micro-reflection
    result = micro_reflect(last_n=every_n)

    # Log the reflection to journal
    if result.get("patterns"):
        log_event(
            event_type="pattern_detected",
            session_id=session_id,
            domain="self_learning",
            outcome="success" if result["session_health"] == "good" else "needs_improvement",
            metrics={"entries_checked": result["entries_checked"],
                     "patterns_found": len(result["patterns"])},
            notes=f"Auto-reflect: {result['session_health']}. "
                  + "; ".join(p["message"] for p in result["patterns"][:3]),
        )

    # Update state
    with open(_AUTO_REFLECT_STATE, "w") as f:
        json.dump({"last_entry_count": current_count,
                    "last_reflect_at": datetime.now(timezone.utc).isoformat()}, f)

    return result


def analyze_current_session(transcript_path=None, session_id=None):
    """Run trace_analyzer on the most recent (or specified) session transcript.

    Feeds results into the self-learning journal as a trace_analysis event.
    Returns the analysis report dict, or None if no transcript found.
    """
    from trace_analyzer import TraceAnalyzer

    if not transcript_path:
        # Find the most recent transcript JSONL
        projects_dir = Path.home() / ".claude" / "projects"
        if not projects_dir.exists():
            return None

        # Find all .jsonl files, sort by modification time
        transcripts = []
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                for f in project_dir.glob("*.jsonl"):
                    transcripts.append(f)

        if not transcripts:
            return None

        # Most recent by mtime
        transcripts.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        transcript_path = str(transcripts[0])

    try:
        report = TraceAnalyzer(transcript_path).analyze()
    except Exception as e:
        print(f"  [trace] Error analyzing transcript: {e}", file=sys.stderr)
        return None

    # Log to self-learning journal
    learnings = []
    for rec in report.get("recommendations", []):
        learnings.append(rec)

    metrics = {
        "score": report["score"],
        "retries": report["retries"]["total_retries"],
        "waste_rate": round(report["waste"]["waste_rate"], 3),
        "efficiency_ratio": report["efficiency"]["ratio"],
        "efficiency_rating": report["efficiency"]["rating"],
        "velocity_pct": report["velocity"]["velocity_pct"],
        "commits": report["velocity"]["commits"],
        "file_creates": report["velocity"]["file_creates"],
        "total_entries": report["total_entries"],
    }

    log_event(
        event_type="trace_analysis",
        domain="self_learning",
        outcome="success" if report["score"] >= 50 else "needs_improvement",
        metrics=metrics,
        learnings=learnings,
        notes=f"Session {report.get('session_id', 'unknown')}: score {report['score']}/100",
    )

    # MT-10: Generate improvement proposals from trace findings
    try:
        from improver import Improver
        imp = Improver(auto_approve_low=True)
        proposals = imp.generate_from_trace(report, session_id=session_id)
        if proposals:
            report["proposals"] = [p.to_dict() for p in proposals]
    except Exception:
        pass  # Improver is optional — don't break trace analysis if it fails

    return report


def _cli():
    parser = argparse.ArgumentParser(description="CCA Self-Learning Reflection")
    parser.add_argument("--domain", choices=VALID_DOMAINS, help="Filter by domain")
    parser.add_argument("--apply", action="store_true", help="Apply suggested strategy changes")
    parser.add_argument("--brief", action="store_true", help="One-line summary")
    parser.add_argument("--trace", action="store_true", help="Analyze most recent session transcript")
    parser.add_argument("--trace-path", help="Analyze specific transcript JSONL file")
    parser.add_argument("--propose", action="store_true", help="Generate improvement proposals from patterns (MT-10)")
    parser.add_argument("--session", type=int, help="Session ID for proposal tracking")
    parser.add_argument("--micro", action="store_true", help="Quick mid-session reflection (returns JSON)")
    parser.add_argument("--last-n", type=int, default=10, help="Entries to check for --micro (default 10)")
    args = parser.parse_args()

    if args.micro:
        result = micro_reflect(last_n=args.last_n)
        print(json.dumps(result, indent=2))
        return

    if args.trace or args.trace_path:
        report = analyze_current_session(args.trace_path, session_id=args.session)
        if report:
            print(f"Trace analysis: score {report['score']}/100 | "
                  f"{report['retries']['total_retries']} retries | "
                  f"waste {report['waste']['waste_rate']:.0%} | "
                  f"velocity {report['velocity']['velocity_pct']:.1f}%")
            if report["recommendations"]:
                for rec in report["recommendations"]:
                    print(f"  - {rec}")
        else:
            print("No transcript found to analyze.")
        return

    reflect(domain=args.domain, apply=args.apply, brief=args.brief,
            propose=args.propose, session_id=args.session)


if __name__ == "__main__":
    _cli()
