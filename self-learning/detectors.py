#!/usr/bin/env python3
"""
detectors.py — Built-in pattern detectors for the pattern registry.

Each detector is a standalone class registered via @register_detector.
These were extracted from reflect.py's monolithic detect_patterns() function
as part of MT-28 Phase 2 (Pattern Plugin Registry).

Detectors are organized by domain:
- general: Works on any journal entries
- trading: Trading-specific patterns (bet outcomes, research, PnL)
- nuclear_scan: Nuclear scan batch patterns

Import this module to register all built-in detectors with the registry.
"""

import os
import sys
from collections import Counter
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from pattern_registry import register_detector, PatternDetector
from journal import _load_strategy, get_pain_win_summary


def _days_between(ts1, ts2):
    """Days between two ISO timestamps."""
    try:
        d1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return abs((d2 - d1).days)
    except (ValueError, AttributeError):
        return 0


# === General Detectors ===


@register_detector(
    name="verdict_drift",
    domain="general",
    description="Detect high skip rate or low BUILD rate in nuclear scan batches",
    min_sample=2,
)
class VerdictDriftDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        patterns = []
        nuclear = [e for e in entries if e.get("event_type") == "nuclear_batch"]
        if len(nuclear) < 2:
            return patterns

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

            if build_rate < 0.03 and reviewed >= self.min_sample:
                patterns.append({
                    "type": "low_build_rate",
                    "severity": "warning",
                    "message": f"BUILD rate is only {build_rate:.1%} across {reviewed} posts — refine high_value_keywords or scan different subreddits",
                    "data": {"build_rate": round(build_rate, 3), "reviewed": reviewed},
                })

        return patterns


@register_detector(
    name="domain_concentration",
    domain="general",
    description="Detect when one domain dominates journal entries",
    min_sample=5,
)
class DomainConcentrationDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        patterns = []
        domain_counts = Counter(e.get("domain", "unknown") for e in entries)
        total = len(entries)
        for domain, count in domain_counts.most_common(3):
            if count / total > 0.7 and total >= self.min_sample:
                patterns.append({
                    "type": "domain_concentration",
                    "severity": "info",
                    "message": f"{domain} accounts for {count/total:.0%} of all journal entries — diversify or acknowledge specialization",
                    "data": {"domain": domain, "pct": round(count / total, 2)},
                })
        return patterns


@register_detector(
    name="recurring_themes",
    domain="general",
    description="Detect recurring words in learnings across entries",
)
class RecurringThemesDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        all_learnings = []
        for e in entries:
            all_learnings.extend(e.get("learnings", []))
        if not all_learnings:
            return []

        learning_words = Counter()
        for l in all_learnings:
            words = [w.lower() for w in l.split() if len(w) > 4]
            learning_words.update(words)

        repeated = [(w, c) for w, c in learning_words.most_common(10) if c >= 3]
        if repeated:
            return [{
                "type": "recurring_themes",
                "severity": "info",
                "message": f"Recurring learning themes: {', '.join(w for w, _ in repeated[:5])}",
                "data": {"themes": repeated[:5]},
            }]
        return []


@register_detector(
    name="consecutive_failures",
    domain="general",
    description="Detect consecutive session outcome failures",
    min_sample=3,
)
class ConsecutiveFailuresDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        outcomes = [e for e in entries if e.get("event_type") == "session_outcome"]
        if len(outcomes) < 3:
            return []

        recent_3 = outcomes[-3:]
        failures = sum(1 for o in recent_3 if o.get("outcome") == "failure")
        if failures >= 2:
            return [{
                "type": "consecutive_failures",
                "severity": "warning",
                "message": f"{failures}/3 recent sessions had failure outcome — investigate root cause",
                "data": {"recent_outcomes": [o.get("outcome") for o in recent_3]},
            }]
        return []


@register_detector(
    name="pain_win_balance",
    domain="general",
    description="Detect pain/win signal imbalance",
    min_sample=5,
)
class PainWinBalanceDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        patterns = []
        pw = get_pain_win_summary()
        if pw["pain_count"] + pw["win_count"] < self.min_sample:
            return patterns

        if pw["ratio"] is not None and pw["ratio"] < 0.3:
            top_pain = max(pw["pain_domains"].items(), key=lambda x: x[1])[0] if pw["pain_domains"] else "unknown"
            patterns.append({
                "type": "high_pain_rate",
                "severity": "warning",
                "message": f"Pain/win ratio is {pw['ratio']:.0%} wins — top pain domain: {top_pain}. Investigate recurring friction.",
                "data": {"ratio": pw["ratio"], "pain_count": pw["pain_count"],
                         "win_count": pw["win_count"], "top_pain_domain": top_pain},
            })
        elif pw["ratio"] is not None and pw["ratio"] > 0.8:
            patterns.append({
                "type": "high_win_rate",
                "severity": "info",
                "message": f"Pain/win ratio is {pw['ratio']:.0%} wins — current approach is working well.",
                "data": {"ratio": pw["ratio"], "pain_count": pw["pain_count"],
                         "win_count": pw["win_count"]},
            })

        return patterns


@register_detector(
    name="stale_strategy",
    domain="general",
    description="Detect when strategy config hasn't been updated in >14 days",
    min_sample=10,
)
class StaleStrategyDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        if strategy is None:
            strategy = _load_strategy()
        updated = strategy.get("updated_at", "")
        if not updated:
            return []
        days_old = _days_between(updated, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        if days_old > 14 and len(entries) >= self.min_sample:
            return [{
                "type": "stale_strategy",
                "severity": "info",
                "message": f"Strategy config is {days_old} days old with {len(entries)} journal entries since — consider running reflect --apply",
                "data": {"days_old": days_old, "entries_since": len(entries)},
            }]
        return []


# === Trading Detectors ===


@register_detector(
    name="losing_strategy",
    domain="trading",
    description="Detect strategies with win rate below alert threshold",
)
class LosingStrategyDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        patterns = []
        bet_outcomes = [e for e in entries if e.get("event_type") == "bet_outcome"]
        if not bet_outcomes:
            return patterns

        strat_stats = {}
        for e in bet_outcomes:
            m = e.get("metrics", {})
            strat = m.get("strategy_name", "unknown")
            if strat not in strat_stats:
                strat_stats[strat] = {"wins": 0, "losses": 0, "pnl": 0, "total": 0}
            ss = strat_stats[strat]
            ss["total"] += 1
            result = m.get("result", "")
            if result == "win":
                ss["wins"] += 1
            elif result == "loss":
                ss["losses"] += 1
            ss["pnl"] += m.get("pnl_cents", 0)

        if strategy is None:
            strategy = _load_strategy()
        win_alert = strategy.get("trading", {}).get("win_rate_alert_below", 0.4)
        min_bets = strategy.get("trading", {}).get("min_sample_bets", 20)

        for strat, ss in strat_stats.items():
            decided = ss["wins"] + ss["losses"]
            if decided >= min_bets:
                wr = ss["wins"] / decided
                if wr < win_alert:
                    patterns.append({
                        "type": "losing_strategy",
                        "severity": "warning",
                        "message": f"Strategy '{strat}' has {wr:.0%} win rate over {decided} bets (PnL: {ss['pnl']}c) — review or retire",
                        "data": {"strategy": strat, "win_rate": round(wr, 3),
                                 "bets": decided, "pnl_cents": ss["pnl"]},
                    })

        return patterns


@register_detector(
    name="research_dead_end",
    domain="trading",
    description="Detect research paths with zero actionable results",
    min_sample=5,
)
class ResearchDeadEndDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        patterns = []
        research_entries = [e for e in entries if e.get("event_type") == "market_research"]
        if not research_entries:
            return patterns

        path_stats = {}
        for e in research_entries:
            m = e.get("metrics", {})
            path = m.get("research_path", "unknown")
            if path not in path_stats:
                path_stats[path] = {"total": 0, "actionable": 0}
            path_stats[path]["total"] += 1
            if m.get("actionable"):
                path_stats[path]["actionable"] += 1

        for path, ps in path_stats.items():
            if ps["total"] >= self.min_sample and ps["actionable"] == 0:
                patterns.append({
                    "type": "research_dead_end",
                    "severity": "warning",
                    "message": f"Research path '{path}' has 0 actionable results in {ps['total']} sessions — prune or pivot",
                    "data": {"path": path, "sessions": ps["total"]},
                })

        return patterns


@register_detector(
    name="negative_pnl",
    domain="trading",
    description="Detect negative cumulative PnL across all bets",
    min_sample=5,
)
class NegativePnlDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        bet_outcomes = [e for e in entries if e.get("event_type") == "bet_outcome"]
        if len(bet_outcomes) < self.min_sample:
            return []

        total_pnl = sum(e.get("metrics", {}).get("pnl_cents", 0) for e in bet_outcomes)
        if total_pnl < 0:
            return [{
                "type": "negative_pnl",
                "severity": "warning",
                "message": f"Cumulative PnL is {total_pnl}c over {len(bet_outcomes)} bets — net negative",
                "data": {"pnl_cents": total_pnl, "total_bets": len(bet_outcomes)},
            }]
        return []


@register_detector(
    name="strong_edge_discovery",
    domain="trading",
    description="Detect effective edge discovery rate",
    min_sample=3,
)
class StrongEdgeDiscoveryDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        edges_found = [e for e in entries if e.get("event_type") == "edge_discovered"]
        edges_rejected = [e for e in entries if e.get("event_type") == "edge_rejected"]
        total_edges = len(edges_found) + len(edges_rejected)
        if total_edges < 3 or len(edges_found) == 0:
            return []

        discovery_rate = len(edges_found) / total_edges
        if discovery_rate > 0.6:
            return [{
                "type": "strong_edge_discovery",
                "severity": "info",
                "message": f"Edge discovery rate is {discovery_rate:.0%} ({len(edges_found)}/{total_edges}) — research approach is effective",
                "data": {"rate": round(discovery_rate, 3),
                         "discovered": len(edges_found),
                         "rejected": len(edges_rejected)},
            }]
        return []


@register_detector(
    name="overnight_wr_gap",
    domain="trading",
    description="Detect time-of-day win rate degradation (overnight vs daytime)",
    min_sample=10,
)
class OvernightWrGapDetector(PatternDetector):
    def detect(self, entries, strategy=None):
        bet_outcomes = [e for e in entries if e.get("event_type") == "bet_outcome"]
        if not bet_outcomes:
            return []

        overnight = {"wins": 0, "losses": 0}
        daytime = {"wins": 0, "losses": 0}
        for e in bet_outcomes:
            ts = e.get("timestamp", "")
            try:
                hour = int(ts[11:13]) if len(ts) >= 13 else -1
            except (ValueError, IndexError):
                continue
            if hour < 0 or hour > 23:
                continue
            result = e.get("metrics", {}).get("result", "")
            target = overnight if hour < 8 else daytime
            if result == "win":
                target["wins"] += 1
            elif result == "loss":
                target["losses"] += 1

        on_decided = overnight["wins"] + overnight["losses"]
        day_decided = daytime["wins"] + daytime["losses"]
        if on_decided >= self.min_sample and day_decided >= self.min_sample:
            on_wr = overnight["wins"] / on_decided
            day_wr = daytime["wins"] / day_decided
            if day_wr - on_wr > 0.10:
                return [{
                    "type": "overnight_wr_gap",
                    "severity": "warning",
                    "message": (f"Overnight WR ({on_wr:.0%}, n={on_decided}) is {day_wr - on_wr:.0%} "
                               f"below daytime WR ({day_wr:.0%}, n={day_decided}) — "
                               f"run overnight_detector.py analyze for statistical significance"),
                    "data": {"overnight_wr": round(on_wr, 3), "daytime_wr": round(day_wr, 3),
                             "overnight_n": on_decided, "daytime_n": day_decided,
                             "gap": round(day_wr - on_wr, 3)},
                }]
        return []


# === Cross-Domain Transfer Detector ===

@register_detector(
    name="principle_transfer",
    domain=["general", "trading", "nuclear_scan"],
    description="Identifies high-scoring principles that could transfer to other domains",
    min_sample=1,
)
class PrincipleTransferDetector(PatternDetector):
    """Surfaces cross-domain principle transfer opportunities during reflect."""

    def detect(self, entries, strategy=None):
        patterns = []
        try:
            from principle_transfer import PrincipleTransfer
            pt = PrincipleTransfer(min_principle_score=0.65, min_affinity=0.3, min_usages=5)
            results = pt.scan_all_domains()
            for target_domain, candidates in results.items():
                for c in candidates[:2]:  # Top 2 per domain
                    patterns.append({
                        "type": "principle_transfer_opportunity",
                        "severity": "info",
                        "message": (
                            f"Transfer opportunity: '{c.principle_text[:50]}...' "
                            f"from {c.source_domain} -> {target_domain} "
                            f"(score={c.transfer_score:.2f})"
                        ),
                        "data": c.to_dict(),
                    })
        except Exception:
            pass  # Don't break reflect if transfer engine has issues
        return patterns
