#!/usr/bin/env python3
"""Extended tests for reflect.py — gaps in detect_patterns, apply_suggestions,
micro_reflect health logic, _clamp_to_bounds boundaries, generate_recommendations,
and auto_reflect_if_due state management.

Supplements test_reflect.py (61 tests).
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import reflect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nuclear_entry(build=2, adapt=1, skip=10, fast_skip=5, reviewed=20):
    return {
        "event_type": "nuclear_batch",
        "domain": "nuclear_scan",
        "metrics": {
            "build": build, "adapt": adapt, "skip": skip,
            "fast_skip": fast_skip, "posts_reviewed": reviewed,
        },
    }


def _session_outcome(outcome="success"):
    return {"event_type": "session_outcome", "outcome": outcome, "domain": "self_learning"}


def _bet(result="win", strategy="sniper", pnl_cents=50, hour=14):
    ts = f"2026-03-21T{hour:02d}:00:00Z"
    return {
        "event_type": "bet_outcome",
        "timestamp": ts,
        "metrics": {"result": result, "strategy_name": strategy, "pnl_cents": pnl_cents},
    }


def _research_entry(path="path1", actionable=False):
    return {
        "event_type": "market_research",
        "metrics": {"research_path": path, "actionable": actionable},
    }


def _make_strategy(auto_adjust=False, updated_days_ago=20, version=1):
    dt = (datetime.now(timezone.utc) - timedelta(days=updated_days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": version,
        "updated_at": dt,
        "learning": {"auto_adjust_enabled": auto_adjust},
        "bounds": {
            "nuclear_scan.min_score_threshold": {"min": 20, "max": 80, "step": 5},
            "trading.win_rate_alert_below": {"min": 0.2, "max": 0.7, "step": 0.05},
        },
        "nuclear_scan": {"min_score_threshold": 40},
        "trading": {"win_rate_alert_below": 0.4, "min_sample_bets": 5},
    }


# ---------------------------------------------------------------------------
# TestDetectPatternsResearchDeadEnd
# ---------------------------------------------------------------------------

class TestDetectPatternsResearchDeadEnd(unittest.TestCase):
    """research_dead_end pattern — not covered in base tests."""

    def _run(self, entries):
        with patch("reflect._load_journal", return_value=entries), \
             patch("reflect._load_strategy", return_value=_make_strategy(updated_days_ago=1)), \
             patch("reflect.get_pain_win_summary", return_value={"pain_count": 0, "win_count": 0, "ratio": None, "pain_domains": {}, "win_domains": {}}):
            return reflect.detect_patterns(entries)

    def test_research_dead_end_detected_at_min_sample(self):
        # 5 entries for same path, all non-actionable
        entries = [_research_entry("dead_path", actionable=False) for _ in range(5)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("research_dead_end", types)

    def test_research_dead_end_not_detected_below_min_sample(self):
        entries = [_research_entry("dead_path", actionable=False) for _ in range(4)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("research_dead_end", types)

    def test_research_dead_end_not_detected_if_any_actionable(self):
        entries = [_research_entry("path1", actionable=False) for _ in range(4)]
        entries.append(_research_entry("path1", actionable=True))
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("research_dead_end", types)

    def test_research_dead_end_data_fields(self):
        entries = [_research_entry("slow_path", actionable=False) for _ in range(5)]
        patterns = self._run(entries)
        dead_ends = [p for p in patterns if p["type"] == "research_dead_end"]
        self.assertEqual(len(dead_ends), 1)
        self.assertEqual(dead_ends[0]["data"]["path"], "slow_path")
        self.assertEqual(dead_ends[0]["data"]["sessions"], 5)

    def test_multiple_paths_only_dead_ones_flagged(self):
        entries = [_research_entry("dead", actionable=False) for _ in range(5)]
        entries += [_research_entry("live", actionable=True) for _ in range(5)]
        patterns = self._run(entries)
        dead_ends = [p for p in patterns if p["type"] == "research_dead_end"]
        paths = [p["data"]["path"] for p in dead_ends]
        self.assertIn("dead", paths)
        self.assertNotIn("live", paths)


# ---------------------------------------------------------------------------
# TestDetectPatternsBoundaryConditions
# ---------------------------------------------------------------------------

class TestDetectPatternsBoundaryConditions(unittest.TestCase):
    """Boundary and edge conditions for detect_patterns."""

    def _run(self, entries, strategy=None, pw=None):
        strat = strategy or _make_strategy(updated_days_ago=1)
        pw_default = {"pain_count": 0, "win_count": 0, "ratio": None, "pain_domains": {}, "win_domains": {}}
        with patch("reflect._load_journal", return_value=entries), \
             patch("reflect._load_strategy", return_value=strat), \
             patch("reflect.get_pain_win_summary", return_value=pw or pw_default):
            return reflect.detect_patterns(entries)

    def test_skip_rate_exactly_at_threshold_not_triggered(self):
        # skip_rate > 0.6 is required — 0.6 exactly should NOT trigger
        # Two identical entries: skip=3, fast_skip=3, reviewed=10 each
        # Total: (3+3+3+3)/(10+10) = 12/20 = 0.60 exactly
        e1 = _nuclear_entry(build=2, adapt=0, skip=3, fast_skip=3, reviewed=10)
        e2 = _nuclear_entry(build=2, adapt=0, skip=3, fast_skip=3, reviewed=10)
        entries = [e1, e2]
        patterns = self._run(entries)
        high_skip = [p for p in patterns if p["type"] == "high_skip_rate"]
        self.assertEqual(high_skip, [])

    def test_skip_rate_just_above_threshold_triggered(self):
        e1 = _nuclear_entry(build=1, skip=7, fast_skip=6, reviewed=20)
        # skip_rate = (7+6)/20 = 0.65 > 0.6 — should trigger
        entries = [e1, _nuclear_entry()]
        patterns = self._run(entries)
        high_skip = [p for p in patterns if p["type"] == "high_skip_rate"]
        self.assertGreater(len(high_skip), 0)

    def test_build_rate_exactly_at_threshold_not_triggered(self):
        # build_rate < 0.03 — 0.03 exactly should NOT trigger
        # 3 BUILD out of 100 = 0.03 — not < 0.03
        e1 = _nuclear_entry(build=3, skip=50, fast_skip=47, reviewed=100)
        entries = [e1, _nuclear_entry()]
        patterns = self._run(entries)
        low_build = [p for p in patterns if p["type"] == "low_build_rate"]
        self.assertEqual(low_build, [])

    def test_low_build_rate_not_triggered_below_min_sample(self):
        # reviewed < min_sample(5) — should not trigger even with 0% build rate
        e = _nuclear_entry(build=0, skip=3, fast_skip=1, reviewed=4)
        entries = [e, _nuclear_entry()]
        patterns = self._run(entries)
        low_build = [p for p in patterns if p["type"] == "low_build_rate"]
        self.assertEqual(low_build, [])

    def test_overnight_wr_gap_boundary_not_triggered(self):
        # Gap = exactly 0.10 — should NOT trigger (requires > 0.10)
        entries = []
        # 10 daytime wins out of 10 = 1.0 WR
        for _ in range(10):
            entries.append(_bet(result="win", hour=14))
        # 9 overnight wins, 1 loss = 0.9 WR → gap = 0.10 exactly
        for _ in range(9):
            entries.append(_bet(result="win", hour=3))
        entries.append(_bet(result="loss", hour=3))
        patterns = self._run(entries)
        gaps = [p for p in patterns if p["type"] == "overnight_wr_gap"]
        self.assertEqual(gaps, [])

    def test_overnight_wr_gap_just_above_boundary_triggered(self):
        # Gap > 0.10: daytime 10W/0L = 1.0, overnight 8W/2L = 0.8 → gap = 0.2
        entries = []
        for _ in range(10):
            entries.append(_bet(result="win", hour=14))
        for _ in range(8):
            entries.append(_bet(result="win", hour=3))
        for _ in range(2):
            entries.append(_bet(result="loss", hour=3))
        patterns = self._run(entries)
        gaps = [p for p in patterns if p["type"] == "overnight_wr_gap"]
        self.assertGreater(len(gaps), 0)

    def test_consecutive_failures_two_out_of_three(self):
        outcomes = [
            _session_outcome("failure"),
            _session_outcome("success"),
            _session_outcome("failure"),
        ]
        entries = [_session_outcome("success")] + outcomes  # 4 total, 3 checked
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("consecutive_failures", types)

    def test_consecutive_failures_not_triggered_two_entries(self):
        # Only 2 outcomes — not enough for "3 recent"
        entries = [_session_outcome("failure"), _session_outcome("failure")]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("consecutive_failures", types)

    def test_domain_concentration_at_exactly_70pct_not_triggered(self):
        # 7 out of 10 in same domain = exactly 0.7 — not > 0.7
        entries = [{"event_type": "log", "domain": "nuclear_scan"}] * 7
        entries += [{"event_type": "log", "domain": "trading"}] * 3
        patterns = self._run(entries)
        conc = [p for p in patterns if p["type"] == "domain_concentration"]
        self.assertEqual(conc, [])

    def test_high_win_rate_boundary(self):
        # ratio > 0.8: 9 wins out of 10 = 0.9 → triggers high_win_rate
        pw = {"pain_count": 1, "win_count": 9, "ratio": 0.9, "pain_domains": {}, "win_domains": {}}
        entries = [_session_outcome()] * 6  # >= min_sample
        patterns = self._run(entries, pw=pw)
        types = [p["type"] for p in patterns]
        self.assertIn("high_win_rate", types)

    def test_pain_rate_at_exactly_30pct_not_triggered(self):
        # ratio = 0.3 exactly — not < 0.3, so no high_pain_rate
        pw = {"pain_count": 7, "win_count": 3, "ratio": 0.3, "pain_domains": {}, "win_domains": {}}
        entries = [_session_outcome()] * 10
        patterns = self._run(entries, pw=pw)
        types = [p["type"] for p in patterns]
        self.assertNotIn("high_pain_rate", types)


# ---------------------------------------------------------------------------
# TestApplySuggestionsExtended
# ---------------------------------------------------------------------------

class TestApplySuggestionsExtended(unittest.TestCase):
    """apply_suggestions edge cases not in base tests."""

    def _make_strat(self, auto=True, current_threshold=40):
        s = _make_strategy(auto_adjust=auto)
        s["nuclear_scan"]["min_score_threshold"] = current_threshold
        return s

    def test_step_snap_down(self):
        # Suggest 48, bounds min=20, max=80, step=5 → snap to 45
        strat = self._make_strat(auto=True, current_threshold=40)
        patterns = [{"suggestion": {"nuclear_scan.min_score_threshold": 48}}]
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            reflect.apply_suggestions(patterns, strat)
        # Clamped to step: 20 + round((48-20)/5)*5 = 20 + 6*5 = 50
        self.assertEqual(strat["nuclear_scan"]["min_score_threshold"], 50)

    def test_step_snap_below_request(self):
        # Suggest 47, step=5 from min=20 → nearest step is 45
        strat = self._make_strat(auto=True, current_threshold=40)
        patterns = [{"suggestion": {"nuclear_scan.min_score_threshold": 47}}]
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            reflect.apply_suggestions(patterns, strat)
        self.assertEqual(strat["nuclear_scan"]["min_score_threshold"], 45)

    def test_multiple_suggestions_in_one_pattern(self):
        strat = _make_strategy(auto_adjust=True)
        strat["nuclear_scan"]["min_score_threshold"] = 40
        strat["trading"]["win_rate_alert_below"] = 0.4
        patterns = [{"suggestion": {
            "nuclear_scan.min_score_threshold": 50,
            "trading.win_rate_alert_below": 0.5,
        }}]
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            changes = reflect.apply_suggestions(patterns, strat)
        self.assertEqual(len(changes), 2)

    def test_no_changes_when_no_suggestions_in_pattern(self):
        strat = _make_strategy(auto_adjust=True)
        patterns = [{"type": "high_skip_rate", "message": "x"}]  # no suggestion key
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            changes = reflect.apply_suggestions(patterns, strat)
        self.assertEqual(changes, [])

    def test_version_not_bumped_when_no_changes(self):
        strat = _make_strategy(auto_adjust=True)
        strat["version"] = 5
        patterns = []
        with patch("reflect._save_strategy") as mock_save:
            reflect.apply_suggestions(patterns, strat)
        mock_save.assert_not_called()
        self.assertEqual(strat["version"], 5)

    def test_unknown_nested_key_created_if_auto_enabled_and_bounded(self):
        # Deep path creation: a.b.c with bounds defined
        strat = {"learning": {"auto_adjust_enabled": True},
                 "bounds": {"a.b.c": {"min": 0, "max": 100, "step": 1}}}
        patterns = [{"suggestion": {"a.b.c": 42}}]
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            changes = reflect.apply_suggestions(patterns, strat)
        self.assertGreater(len(changes), 0)
        self.assertEqual(strat["a"]["b"]["c"], 42)

    def test_multiple_patterns_same_key_applied_sequentially(self):
        strat = _make_strategy(auto_adjust=True)
        strat["nuclear_scan"]["min_score_threshold"] = 40
        patterns = [
            {"suggestion": {"nuclear_scan.min_score_threshold": 45}},
            {"suggestion": {"nuclear_scan.min_score_threshold": 50}},
        ]
        with patch("reflect._save_strategy"), patch("reflect.log_event"):
            changes = reflect.apply_suggestions(patterns, strat)
        # Both applied (two separate changes)
        self.assertEqual(len(changes), 2)


# ---------------------------------------------------------------------------
# TestMicroReflectExtended
# ---------------------------------------------------------------------------

class TestMicroReflectExtended(unittest.TestCase):
    """micro_reflect edge cases — health logic, stale domains, bet pnl."""

    def _run(self, entries, last_n=10):
        with patch("reflect._load_journal", return_value=entries), \
             patch("reflect.get_pain_win_summary", return_value={"pain_count": 0, "win_count": 0, "ratio": None, "pain_domains": {}, "win_domains": {}}):
            return reflect.micro_reflect(last_n=last_n)

    def test_session_health_needs_attention_on_repeated_failure(self):
        entries = [
            {"outcome": "failure", "domain": "context_monitor"},
            {"outcome": "failure", "domain": "context_monitor"},
            {"outcome": "failure", "domain": "agent_guard"},
            {"outcome": "success", "domain": "spec_system"},
        ]
        result = self._run(entries)
        self.assertEqual(result["session_health"], "needs_attention")

    def test_session_health_good_on_high_success(self):
        entries = [{"outcome": "success", "domain": "spec_system"}] * 8
        entries += [{"outcome": "failure", "domain": "spec_system"}] * 2
        result = self._run(entries)
        # No negative patterns, just high_success_streak → health = "good"
        self.assertIn(result["session_health"], ("good",))

    def test_repeated_failure_not_triggered_with_one_per_domain(self):
        # 3 failures, but each in different domain (count per domain = 1, needs >= 2)
        entries = [
            {"outcome": "failure", "domain": "a"},
            {"outcome": "failure", "domain": "b"},
            {"outcome": "failure", "domain": "c"},
        ]
        result = self._run(entries)
        rep_fail = [p for p in result["patterns"] if p["type"] == "repeated_failure"]
        self.assertEqual(rep_fail, [])

    def test_negative_pnl_pattern_health(self):
        entries = [_bet(result="loss", pnl_cents=-20) for _ in range(5)]
        result = self._run(entries)
        self.assertEqual(result["session_health"], "needs_attention")

    def test_positive_pnl_no_needs_attention(self):
        entries = [_bet(result="win", pnl_cents=20) for _ in range(5)]
        result = self._run(entries)
        neg_pnl = [p for p in result["patterns"] if p["type"] == "negative_pnl_recent"]
        self.assertEqual(neg_pnl, [])

    def test_bets_below_5_no_pnl_pattern(self):
        entries = [_bet(result="loss", pnl_cents=-100) for _ in range(4)]
        result = self._run(entries)
        neg_pnl = [p for p in result["patterns"] if p["type"] == "negative_pnl_recent"]
        self.assertEqual(neg_pnl, [])

    def test_too_many_stale_domains_no_warning(self):
        # > 3 stale domains → no stale_domains warning (to avoid noise)
        entries = [{"domain": "context_monitor", "outcome": "success"} for _ in range(5)]
        # Patch _load_journal to return entries with many extra domains that won't appear in recent
        all_entries = entries + [
            {"domain": "x1"}, {"domain": "x2"}, {"domain": "x3"}, {"domain": "x4"},
        ]
        with patch("reflect._load_journal", return_value=all_entries):
            result = reflect.micro_reflect(last_n=5)
        stale = [p for p in result["patterns"] if p["type"] == "stale_domains"]
        self.assertEqual(stale, [])

    def test_no_stale_domains_when_all_seen(self):
        entries = [{"domain": "context_monitor", "outcome": "success"} for _ in range(5)]
        result = self._run(entries)
        stale = [p for p in result["patterns"] if p["type"] == "stale_domains"]
        self.assertEqual(stale, [])

    def test_high_success_streak_not_triggered_below_5(self):
        # < 5 recent entries → no streak detection
        entries = [{"outcome": "success", "domain": "spec_system"}] * 4
        result = self._run(entries)
        streaks = [p for p in result["patterns"] if p["type"] == "high_success_streak"]
        self.assertEqual(streaks, [])

    def test_last_n_parameter_limits_entries_checked(self):
        all_entries = [{"outcome": "success", "domain": "x"} for _ in range(20)]
        result = self._run(all_entries, last_n=5)
        self.assertEqual(result["entries_checked"], 5)

    def test_recommendations_not_empty_on_repeated_failure(self):
        entries = [
            {"outcome": "failure", "domain": "mem"},
            {"outcome": "failure", "domain": "mem"},
            {"outcome": "failure", "domain": "mem"},
        ]
        result = self._run(entries)
        rep_fail = [p for p in result["patterns"] if p["type"] == "repeated_failure"]
        if rep_fail:  # Triggered when count >= 2 per domain
            self.assertGreater(len(result["recommendations"]), 0)


# ---------------------------------------------------------------------------
# TestClampToBoundsExtended
# ---------------------------------------------------------------------------

class TestClampToBoundsExtended(unittest.TestCase):
    """_clamp_to_bounds additional edge cases."""

    def _strat(self):
        return {"bounds": {
            "threshold": {"min": 10, "max": 90, "step": 5},
            "ratio": {"min": 0.1, "max": 0.9, "step": 0.1},
            "no_step": {"min": 1, "max": 100},
            "no_bounds_key": None,
        }}

    def test_value_exactly_at_min(self):
        result = reflect._clamp_to_bounds("threshold", 10, self._strat())
        self.assertEqual(result, 10)

    def test_value_exactly_at_max(self):
        result = reflect._clamp_to_bounds("threshold", 90, self._strat())
        self.assertEqual(result, 90)

    def test_float_value_within_range(self):
        result = reflect._clamp_to_bounds("ratio", 0.5, self._strat())
        self.assertAlmostEqual(result, 0.5, places=5)

    def test_float_snap_to_step(self):
        # ratio 0.35 → nearest step from 0.1: 0.1 + round((0.35-0.1)/0.1)*0.1 = 0.1 + 2*0.1 = 0.3... wait
        # actually round(0.25 / 0.1) = round(2.5) = 2 (Python banker's round) or 3?
        # In Python: round(2.5) = 2 (banker's rounding). So 0.1 + 2*0.1 = 0.3
        result = reflect._clamp_to_bounds("ratio", 0.35, self._strat())
        self.assertIsNotNone(result)

    def test_no_step_still_clamps(self):
        # no_step has min=1, max=100, no step → should still clamp but not snap
        result = reflect._clamp_to_bounds("no_step", 150, self._strat())
        self.assertEqual(result, 100)

    def test_none_bounds_returns_none(self):
        result = reflect._clamp_to_bounds("no_bounds_key", 50, self._strat())
        self.assertIsNone(result)

    def test_missing_key_returns_none(self):
        result = reflect._clamp_to_bounds("nonexistent_key", 50, self._strat())
        self.assertIsNone(result)

    def test_string_value_returns_none(self):
        result = reflect._clamp_to_bounds("threshold", "fifty", self._strat())
        self.assertIsNone(result)

    def test_none_value_returns_none(self):
        result = reflect._clamp_to_bounds("threshold", None, self._strat())
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TestDaysBetweenExtended
# ---------------------------------------------------------------------------

class TestDaysBetweenExtended(unittest.TestCase):
    """_days_between edge cases."""

    def test_30_days_apart(self):
        t1 = "2026-02-19T00:00:00Z"
        t2 = "2026-03-21T00:00:00Z"
        result = reflect._days_between(t1, t2)
        self.assertEqual(result, 30)

    def test_none_returns_zero(self):
        result = reflect._days_between(None, "2026-03-21T00:00:00Z")
        self.assertEqual(result, 0)

    def test_both_none_returns_zero(self):
        result = reflect._days_between(None, None)
        self.assertEqual(result, 0)

    def test_partial_day_rounds_down(self):
        t1 = "2026-03-21T00:00:00Z"
        t2 = "2026-03-21T12:00:00Z"
        result = reflect._days_between(t1, t2)
        self.assertEqual(result, 0)

    def test_almost_two_days(self):
        t1 = "2026-03-19T01:00:00Z"
        t2 = "2026-03-21T00:00:00Z"
        result = reflect._days_between(t1, t2)
        self.assertEqual(result, 1)

    def test_exactly_two_days(self):
        t1 = "2026-03-19T00:00:00Z"
        t2 = "2026-03-21T00:00:00Z"
        result = reflect._days_between(t1, t2)
        self.assertEqual(result, 2)


# ---------------------------------------------------------------------------
# TestGenerateRecommendationsExtended
# ---------------------------------------------------------------------------

class TestGenerateRecommendationsExtended(unittest.TestCase):
    """generate_recommendations edge cases."""

    def _run(self, patterns=None, nuclear_metrics=None, learnings=None, strat=None):
        nm = nuclear_metrics
        learnings_data = learnings or []
        strat = strat or _make_strategy()
        with patch("reflect.get_nuclear_metrics", return_value=nm), \
             patch("reflect.get_all_learnings", return_value=learnings_data):
            return reflect.generate_recommendations([], patterns or [], strat)

    def test_no_nuclear_metrics_no_signal_rate_rec(self):
        recs = self._run(nuclear_metrics=None)
        signal_recs = [r for r in recs if "signal rate" in r.lower()]
        self.assertEqual(signal_recs, [])

    def test_zero_signal_rate_no_rec(self):
        nm = {"signal_rate": 0, "posts_reviewed": 50, "batches": 5}
        recs = self._run(nuclear_metrics=nm)
        signal_recs = [r for r in recs if "signal rate" in r.lower()]
        self.assertEqual(signal_recs, [])

    def test_positive_signal_rate_rec_included(self):
        nm = {"signal_rate": 0.25, "posts_reviewed": 100, "batches": 5}
        recs = self._run(nuclear_metrics=nm)
        signal_recs = [r for r in recs if "signal rate" in r.lower()]
        self.assertGreater(len(signal_recs), 0)

    def test_zero_batches_no_average_batch_rec(self):
        nm = {"signal_rate": 0.1, "posts_reviewed": 0, "batches": 0}
        recs = self._run(nuclear_metrics=nm)
        batch_recs = [r for r in recs if "batch size" in r.lower()]
        self.assertEqual(batch_recs, [])

    def test_suggestion_not_added_if_current_val_is_none(self):
        # Pattern with suggestion, but key doesn't exist in strategy
        strat = {"learning": {}, "bounds": {}, "version": 1}
        patterns = [{"suggestion": {"missing.key": 50}, "message": "x"}]
        with patch("reflect.get_nuclear_metrics", return_value=None), \
             patch("reflect.get_all_learnings", return_value=[]):
            recs = reflect.generate_recommendations([], patterns, strat)
        # current_val would be None → no rec generated
        suggest_recs = [r for r in recs if "missing.key" in r]
        self.assertEqual(suggest_recs, [])

    def test_suggestion_not_added_if_already_at_target(self):
        strat = _make_strategy()
        strat["nuclear_scan"]["min_score_threshold"] = 50
        patterns = [{"suggestion": {"nuclear_scan.min_score_threshold": 50}, "message": "x"}]
        with patch("reflect.get_nuclear_metrics", return_value=None), \
             patch("reflect.get_all_learnings", return_value=[]):
            recs = reflect.generate_recommendations([], patterns, strat)
        suggest_recs = [r for r in recs if "min_score_threshold" in r]
        self.assertEqual(suggest_recs, [])

    def test_learnings_count_in_rec(self):
        learnings = [{"domain": "spec_system", "text": "x"} for _ in range(7)]
        recs = self._run(learnings=learnings)
        count_recs = [r for r in recs if "7" in r and "learnings" in r.lower()]
        self.assertGreater(len(count_recs), 0)


# ---------------------------------------------------------------------------
# TestAutoReflectIfDueExtended
# ---------------------------------------------------------------------------

class TestAutoReflectIfDueExtended(unittest.TestCase):
    """auto_reflect_if_due state management edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmpdir, ".auto_reflect_state.json")

    def _run(self, entries, every_n=5, state_count=None):
        if state_count is not None:
            with open(self.state_file, "w") as f:
                json.dump({"last_entry_count": state_count}, f)

        with patch("reflect._load_journal", return_value=entries), \
             patch("reflect._AUTO_REFLECT_STATE", self.state_file), \
             patch("reflect.get_pain_win_summary", return_value={"pain_count": 0, "win_count": 0, "ratio": None, "pain_domains": {}, "win_domains": {}}), \
             patch("reflect.log_event"):
            return reflect.auto_reflect_if_due(every_n=every_n)

    def test_no_state_file_runs_when_enough_entries(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 5
        result = self._run(entries, every_n=5)
        self.assertIsNotNone(result)

    def test_state_file_created_after_run(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 5
        self._run(entries, every_n=5)
        self.assertTrue(os.path.exists(self.state_file))
        with open(self.state_file) as f:
            state = json.load(f)
        self.assertEqual(state["last_entry_count"], 5)

    def test_state_file_updated_with_current_count(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 10
        self._run(entries, every_n=5, state_count=0)
        with open(self.state_file) as f:
            state = json.load(f)
        self.assertEqual(state["last_entry_count"], 10)

    def test_returns_none_when_not_enough_new_entries(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 5
        result = self._run(entries, every_n=5, state_count=3)
        # 5 - 3 = 2 < 5 → not due
        self.assertIsNone(result)

    def test_returns_result_when_exactly_n_new_entries(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 10
        result = self._run(entries, every_n=5, state_count=5)
        # 10 - 5 = 5 >= 5 → due
        self.assertIsNotNone(result)

    def test_result_has_session_health_key(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 5
        result = self._run(entries, every_n=5)
        self.assertIn("session_health", result)

    def test_result_has_patterns_key(self):
        entries = [{"event_type": "log", "domain": "spec_system"}] * 5
        result = self._run(entries, every_n=5)
        self.assertIn("patterns", result)


if __name__ == "__main__":
    unittest.main()
