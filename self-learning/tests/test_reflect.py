#!/usr/bin/env python3
"""
Tests for self-learning/reflect.py — reflection engine for pattern detection,
strategy suggestions, micro-reflect, and auto-reflect scheduling.

782 LOC source, 0 previous tests — highest-risk untested module.
All tests patch journal I/O so no real files are touched.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

_TESTS_DIR = Path(__file__).resolve().parent
_MODULE_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_MODULE_DIR))

import reflect as rf


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_nuclear_entry(**kwargs):
    """Build a minimal nuclear_batch journal entry."""
    base = {
        "event_type": "nuclear_batch",
        "domain": "nuclear_scan",
        "outcome": "success",
        "metrics": {"posts_reviewed": 10, "build": 1, "skip": 7, "fast_skip": 1, "adapt": 1},
    }
    base.update(kwargs)
    return base


def _make_bet_entry(strategy="sniper", result="win", pnl=100,
                    timestamp="2026-03-20T12:00:00Z"):
    return {
        "event_type": "bet_outcome",
        "domain": "trading",
        "outcome": "success" if result == "win" else "failure",
        "timestamp": timestamp,
        "metrics": {
            "strategy_name": strategy,
            "result": result,
            "pnl_cents": pnl,
        },
    }


def _make_session_outcome(outcome="success"):
    return {"event_type": "session_outcome", "outcome": outcome, "domain": "cca"}


def _minimal_strategy():
    return {
        "version": 1,
        "updated_at": "2026-01-01T00:00:00Z",
        "updated_by": "test",
        "learning": {"auto_adjust_enabled": True},
        "nuclear_scan": {"min_score_threshold": 40},
        "trading": {"win_rate_alert_below": 0.4, "min_sample_bets": 5},
        "bounds": {
            "nuclear_scan.min_score_threshold": {"min": 30, "max": 80, "step": 5},
        },
    }


# ── _days_between ─────────────────────────────────────────────────────────────

class TestDaysBetween(unittest.TestCase):

    def test_same_timestamp(self):
        ts = "2026-03-20T10:00:00Z"
        self.assertEqual(rf._days_between(ts, ts), 0)

    def test_one_day_apart(self):
        t1 = "2026-03-20T10:00:00Z"
        t2 = "2026-03-21T10:00:00Z"
        self.assertEqual(rf._days_between(t1, t2), 1)

    def test_order_independent(self):
        t1 = "2026-03-20T10:00:00Z"
        t2 = "2026-03-25T10:00:00Z"
        self.assertEqual(rf._days_between(t1, t2), rf._days_between(t2, t1))

    def test_invalid_timestamp(self):
        self.assertEqual(rf._days_between("bad_ts", "also_bad"), 0)

    def test_empty_string(self):
        self.assertEqual(rf._days_between("", "2026-03-20T10:00:00Z"), 0)


# ── _clamp_to_bounds ──────────────────────────────────────────────────────────

class TestClampToBounds(unittest.TestCase):

    def setUp(self):
        self.strategy = {
            "bounds": {
                "nuclear_scan.min_score_threshold": {"min": 30, "max": 80, "step": 5},
                "trading.win_rate_alert_below": {"min": 0.1, "max": 0.6, "step": 0.05},
            }
        }

    def test_value_within_bounds(self):
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", 50, self.strategy)
        self.assertEqual(result, 50)

    def test_value_above_max_clamped(self):
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", 100, self.strategy)
        self.assertEqual(result, 80)

    def test_value_below_min_clamped(self):
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", 10, self.strategy)
        self.assertEqual(result, 30)

    def test_snaps_to_step(self):
        # 47 should snap to 45 (nearest multiple of 5 from 30)
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", 47, self.strategy)
        self.assertEqual(result, 45)

    def test_no_bounds_returns_none(self):
        result = rf._clamp_to_bounds("unknown.key", 50, self.strategy)
        self.assertIsNone(result)

    def test_non_numeric_returns_none(self):
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", "fifty", self.strategy)
        self.assertIsNone(result)

    def test_int_type_preserved(self):
        result = rf._clamp_to_bounds("nuclear_scan.min_score_threshold", 50, self.strategy)
        self.assertIsInstance(result, int)

    def test_float_bounds(self):
        result = rf._clamp_to_bounds("trading.win_rate_alert_below", 0.35, self.strategy)
        self.assertAlmostEqual(result, 0.35, places=5)


# ── detect_patterns ───────────────────────────────────────────────────────────

class TestDetectPatterns(unittest.TestCase):

    def _run(self, entries, mock_strategy=None, mock_pw=None):
        """Run detect_patterns with mocked journal I/O."""
        if mock_strategy is None:
            mock_strategy = _minimal_strategy()
        if mock_pw is None:
            mock_pw = {"pain_count": 0, "win_count": 0, "ratio": None,
                       "pain_domains": {}, "win_domains": {}}
        with patch.object(rf, "_load_strategy", return_value=mock_strategy), \
             patch("reflect.get_pain_win_summary", return_value=mock_pw), \
             patch("detectors.get_pain_win_summary", return_value=mock_pw), \
             patch("detectors._load_strategy", return_value=mock_strategy):
            return rf.detect_patterns(entries, min_sample=2)

    def test_empty_entries(self):
        patterns = self._run([])
        self.assertEqual(patterns, [])

    def test_single_entry_no_patterns(self):
        patterns = self._run([_make_nuclear_entry()])
        self.assertEqual(patterns, [])

    def test_high_skip_rate_detected(self):
        # 9/10 posts skipped = 90% skip rate
        entries = [
            _make_nuclear_entry(metrics={"posts_reviewed": 10, "build": 1, "skip": 8,
                                         "fast_skip": 1, "adapt": 0}),
            _make_nuclear_entry(metrics={"posts_reviewed": 10, "build": 0, "skip": 9,
                                         "fast_skip": 1, "adapt": 0}),
        ]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("high_skip_rate", types)

    def test_low_skip_rate_no_pattern(self):
        # Only 20% skip rate
        entries = [
            _make_nuclear_entry(metrics={"posts_reviewed": 10, "build": 5, "skip": 2,
                                         "fast_skip": 0, "adapt": 3}),
            _make_nuclear_entry(metrics={"posts_reviewed": 10, "build": 5, "skip": 1,
                                         "fast_skip": 1, "adapt": 3}),
        ]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("high_skip_rate", types)

    def test_low_build_rate_warning(self):
        # 0 BUILD out of 50 posts
        entries = [
            _make_nuclear_entry(metrics={"posts_reviewed": 25, "build": 0, "skip": 24,
                                         "fast_skip": 0, "adapt": 1}),
            _make_nuclear_entry(metrics={"posts_reviewed": 25, "build": 0, "skip": 23,
                                         "fast_skip": 1, "adapt": 1}),
        ]
        patterns = self._run(entries, mock_strategy=_minimal_strategy())
        types = [p["type"] for p in patterns]
        self.assertIn("low_build_rate", types)

    def test_domain_concentration_detected(self):
        entries = [{"domain": "nuclear_scan", "event_type": "other"} for _ in range(8)]
        entries += [{"domain": "trading", "event_type": "other"} for _ in range(2)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("domain_concentration", types)

    def test_domain_concentration_not_triggered_below_70pct(self):
        # 60% nuclear_scan — should NOT trigger
        entries = [{"domain": "nuclear_scan", "event_type": "other"} for _ in range(6)]
        entries += [{"domain": "trading", "event_type": "other"} for _ in range(4)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("domain_concentration", types)

    def test_consecutive_failures_detected(self):
        entries = [
            _make_session_outcome("failure"),
            _make_session_outcome("failure"),
            _make_session_outcome("success"),
        ]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("consecutive_failures", types)

    def test_no_consecutive_failures_when_mostly_success(self):
        entries = [
            _make_session_outcome("success"),
            _make_session_outcome("success"),
            _make_session_outcome("failure"),
        ]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("consecutive_failures", types)

    def test_losing_strategy_detected(self):
        # 1 win, 9 losses = 10% WR (below 40% threshold)
        entries = [_make_bet_entry("sniper", "win", 100)] + \
                  [_make_bet_entry("sniper", "loss", -100) for _ in range(9)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("losing_strategy", types)

    def test_losing_strategy_not_detected_below_min_sample(self):
        # Only 3 bets — below min_sample=5
        entries = [_make_bet_entry("sniper", "loss", -100) for _ in range(3)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("losing_strategy", types)

    def test_negative_pnl_pattern(self):
        entries = [_make_bet_entry("sniper", "loss", -100) for _ in range(5)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("negative_pnl", types)

    def test_positive_pnl_no_pattern(self):
        entries = [_make_bet_entry("sniper", "win", 100) for _ in range(5)]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("negative_pnl", types)

    def test_high_pain_rate_detected(self):
        pw = {"pain_count": 8, "win_count": 2, "ratio": 0.2,
              "pain_domains": {"trading": 5, "cca": 3}, "win_domains": {}}
        patterns = self._run(
            [{"event_type": "pain_win"} for _ in range(10)],
            mock_pw=pw
        )
        types = [p["type"] for p in patterns]
        self.assertIn("high_pain_rate", types)

    def test_high_win_rate_detected(self):
        pw = {"pain_count": 1, "win_count": 9, "ratio": 0.9,
              "pain_domains": {}, "win_domains": {"cca": 9}}
        patterns = self._run(
            [{"event_type": "pain_win"} for _ in range(10)],
            mock_pw=pw
        )
        types = [p["type"] for p in patterns]
        self.assertIn("high_win_rate", types)

    def test_stale_strategy_detected(self):
        # Strategy updated 30 days ago with 10+ entries
        old_strategy = _minimal_strategy()
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        old_strategy["updated_at"] = old_date
        entries = [{"event_type": "other"} for _ in range(15)]
        patterns = self._run(entries, mock_strategy=old_strategy)
        types = [p["type"] for p in patterns]
        self.assertIn("stale_strategy", types)

    def test_fresh_strategy_no_staleness(self):
        fresh_strategy = _minimal_strategy()
        fresh_strategy["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [{"event_type": "other"} for _ in range(15)]
        patterns = self._run(entries, mock_strategy=fresh_strategy)
        types = [p["type"] for p in patterns]
        self.assertNotIn("stale_strategy", types)

    def test_overnight_wr_gap_detected(self):
        # 10 overnight bets at 20% WR, 10 daytime bets at 80% WR
        overnight = [_make_bet_entry("sniper", "loss" if i < 8 else "win", -100,
                                      timestamp=f"2026-03-{10+i}T03:00:00Z")
                     for i in range(10)]
        daytime = [_make_bet_entry("sniper", "win" if i < 8 else "loss", 100,
                                    timestamp=f"2026-03-{10+i}T14:00:00Z")
                   for i in range(10)]
        patterns = self._run(overnight + daytime)
        types = [p["type"] for p in patterns]
        self.assertIn("overnight_wr_gap", types)

    def test_overnight_wr_gap_not_detected_insufficient_data(self):
        # Only 5 bets per window
        overnight = [_make_bet_entry("sniper", "loss", -100,
                                      timestamp=f"2026-03-{10+i}T03:00:00Z")
                     for i in range(5)]
        daytime = [_make_bet_entry("sniper", "win", 100,
                                    timestamp=f"2026-03-{10+i}T14:00:00Z")
                   for i in range(5)]
        patterns = self._run(overnight + daytime)
        types = [p["type"] for p in patterns]
        self.assertNotIn("overnight_wr_gap", types)

    def test_strong_edge_discovery_detected(self):
        edges_found = [{"event_type": "edge_discovered"} for _ in range(4)]
        edges_rejected = [{"event_type": "edge_rejected"} for _ in range(2)]
        patterns = self._run(edges_found + edges_rejected)
        types = [p["type"] for p in patterns]
        self.assertIn("strong_edge_discovery", types)

    def test_recurring_themes_detected(self):
        # Same word "testing" appearing 3+ times in learnings
        entries = [
            {"event_type": "other", "learnings": ["testing approach improved pipeline"]},
            {"event_type": "other", "learnings": ["testing coverage helps confidence"]},
            {"event_type": "other", "learnings": ["testing scripts caught errors"]},
        ]
        patterns = self._run(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("recurring_themes", types)


# ── apply_suggestions ─────────────────────────────────────────────────────────

class TestApplySuggestions(unittest.TestCase):

    def setUp(self):
        self.strategy = _minimal_strategy()

    def test_no_suggestions_returns_empty(self):
        patterns = [{"type": "high_skip_rate", "severity": "info",
                     "message": "test", "data": {}}]
        with patch.object(rf, "_save_strategy"), patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(changes, [])

    def test_applies_suggestion_when_auto_enabled(self):
        # Pattern suggests raising threshold from 40 to 50
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "Skip rate too high",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 50},
        }]
        with patch.object(rf, "_save_strategy") as mock_save, \
             patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(len(changes), 1)
        self.assertIn("40", changes[0])
        self.assertIn("50", changes[0])
        mock_save.assert_called_once()

    def test_rejects_when_auto_disabled(self):
        self.strategy["learning"]["auto_adjust_enabled"] = False
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 50},
        }]
        with patch.object(rf, "_save_strategy") as mock_save, \
             patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(changes, [])
        mock_save.assert_not_called()

    def test_rejects_out_of_bounds_key(self):
        # Key not in bounds — should reject
        patterns = [{
            "type": "test_pattern",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nonexistent.key": 999},
        }]
        with patch.object(rf, "_save_strategy") as mock_save, \
             patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(changes, [])
        mock_save.assert_not_called()

    def test_no_change_when_value_already_set(self):
        # Current value is already 40, suggestion is 40 — no change
        patterns = [{
            "type": "test_pattern",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 40},
        }]
        with patch.object(rf, "_save_strategy") as mock_save, \
             patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(changes, [])
        mock_save.assert_not_called()

    def test_strategy_version_bumped_on_change(self):
        initial_version = self.strategy["version"]
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 50},
        }]
        with patch.object(rf, "_save_strategy"), patch("reflect.log_event"):
            rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(self.strategy["version"], initial_version + 1)

    def test_clamped_value_noted_in_change_message(self):
        # Suggest value 100 but max is 80 — should clamp and note
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 100},
        }]
        with patch.object(rf, "_save_strategy"), patch("reflect.log_event"):
            changes = rf.apply_suggestions(patterns, self.strategy)
        self.assertEqual(len(changes), 1)
        self.assertIn("clamped", changes[0])


# ── micro_reflect ─────────────────────────────────────────────────────────────

class TestMicroReflect(unittest.TestCase):

    def _run(self, entries):
        with patch("reflect._load_journal", return_value=entries):
            return rf.micro_reflect(last_n=10)

    def test_insufficient_data(self):
        result = self._run([{"event_type": "session_outcome"}])
        self.assertEqual(result["session_health"], "insufficient_data")

    def test_high_success_streak(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(8)]
        entries += [{"event_type": "task", "outcome": "failure"} for _ in range(2)]
        result = self._run(entries)
        types = [p["type"] for p in result["patterns"]]
        self.assertIn("high_success_streak", types)

    def test_repeated_failure_detected(self):
        entries = [
            {"event_type": "task", "outcome": "failure", "domain": "spec-system"},
            {"event_type": "task", "outcome": "failure", "domain": "spec-system"},
            {"event_type": "task", "outcome": "failure", "domain": "spec-system"},
            {"event_type": "task", "outcome": "success", "domain": "spec-system"},
        ]
        result = self._run(entries)
        types = [p["type"] for p in result["patterns"]]
        self.assertIn("repeated_failure", types)
        self.assertEqual(result["session_health"], "needs_attention")

    def test_negative_pnl_recent(self):
        entries = [_make_bet_entry("sniper", "loss", -100) for _ in range(6)]
        result = self._run(entries)
        types = [p["type"] for p in result["patterns"]]
        self.assertIn("negative_pnl_recent", types)
        self.assertEqual(result["session_health"], "needs_attention")

    def test_positive_pnl_no_negative_pattern(self):
        entries = [_make_bet_entry("sniper", "win", 100) for _ in range(6)]
        result = self._run(entries)
        types = [p["type"] for p in result["patterns"]]
        self.assertNotIn("negative_pnl_recent", types)

    def test_stale_domains_detected(self):
        # 20 total entries with "agent-guard" domain, recent 10 have none
        old_entries = [{"event_type": "task", "outcome": "success", "domain": "agent-guard"}
                       for _ in range(10)]
        recent_entries = [{"event_type": "task", "outcome": "success", "domain": "spec-system"}
                          for _ in range(10)]
        all_entries = old_entries + recent_entries
        with patch("reflect._load_journal", return_value=all_entries):
            result = rf.micro_reflect(last_n=10)
        types = [p["type"] for p in result["patterns"]]
        self.assertIn("stale_domains", types)

    def test_good_health_no_patterns(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(10)]
        result = self._run(entries)
        self.assertEqual(result["session_health"], "good")

    def test_entries_checked_count(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(20)]
        result = self._run(entries)
        # last_n=10, should only check 10 entries
        self.assertEqual(result["entries_checked"], 10)

    def test_returns_expected_keys(self):
        result = self._run([{"event_type": "task", "outcome": "success"} for _ in range(5)])
        self.assertIn("entries_checked", result)
        self.assertIn("patterns", result)
        self.assertIn("recommendations", result)
        self.assertIn("session_health", result)


# ── auto_reflect_if_due ───────────────────────────────────────────────────────

class TestAutoReflectIfDue(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, ".auto_reflect_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, entries, every_n=5):
        with patch("reflect._load_journal", return_value=entries), \
             patch.object(rf, "_AUTO_REFLECT_STATE", self.state_path), \
             patch("reflect.log_event"):
            return rf.auto_reflect_if_due(every_n=every_n)

    def test_not_due_when_fewer_entries_than_every_n(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(3)]
        result = self._run(entries, every_n=5)
        self.assertIsNone(result)

    def test_due_when_enough_new_entries(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(10)]
        result = self._run(entries, every_n=5)
        self.assertIsNotNone(result)
        self.assertIn("session_health", result)

    def test_state_file_updated_after_run(self):
        entries = [{"event_type": "task", "outcome": "success"} for _ in range(10)]
        self._run(entries, every_n=5)
        # State file should now exist
        self.assertTrue(os.path.exists(self.state_path))
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(state["last_entry_count"], 10)

    def test_not_due_after_state_is_current(self):
        # Pre-populate state with current count
        with open(self.state_path, "w") as f:
            json.dump({"last_entry_count": 10}, f)
        entries = [{"event_type": "task"} for _ in range(12)]
        result = self._run(entries, every_n=5)
        # 12 - 10 = 2 new entries, less than every_n=5 — not due
        self.assertIsNone(result)

    def test_due_after_state_is_stale(self):
        # State says 5, now we have 15 — 10 new entries > every_n=5
        with open(self.state_path, "w") as f:
            json.dump({"last_entry_count": 5}, f)
        entries = [{"event_type": "task"} for _ in range(15)]
        result = self._run(entries, every_n=5)
        self.assertIsNotNone(result)

    def test_malformed_state_file_treated_as_zero(self):
        with open(self.state_path, "w") as f:
            f.write("not json")
        entries = [{"event_type": "task"} for _ in range(10)]
        result = self._run(entries, every_n=5)
        self.assertIsNotNone(result)


# ── generate_recommendations ──────────────────────────────────────────────────

class TestGenerateRecommendations(unittest.TestCase):

    def _run(self, entries, patterns, strategy=None, nuclear_metrics=None, learnings=None):
        if strategy is None:
            strategy = _minimal_strategy()
        if nuclear_metrics is None:
            nuclear_metrics = {}
        if learnings is None:
            learnings = []
        with patch("reflect.get_nuclear_metrics", return_value=nuclear_metrics), \
             patch("reflect.get_all_learnings", return_value=learnings):
            return rf.generate_recommendations(entries, patterns, strategy)

    def test_returns_list(self):
        recs = self._run([], [])
        self.assertIsInstance(recs, list)

    def test_strategy_suggestion_surfaced(self):
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "Skip rate is 70%",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 50},
        }]
        strategy = _minimal_strategy()
        recs = self._run([], patterns, strategy=strategy)
        # Should mention the suggested change
        self.assertTrue(any("40" in r and "50" in r for r in recs))

    def test_nuclear_signal_rate_included(self):
        nm = {"signal_rate": 0.15, "posts_reviewed": 50, "batches": 5}
        recs = self._run([], [], nuclear_metrics=nm)
        self.assertTrue(any("signal rate" in r.lower() for r in recs))

    def test_learnings_count_included(self):
        learnings = [{"domain": "cca", "text": "x"} for _ in range(5)]
        recs = self._run([], [], learnings=learnings)
        self.assertTrue(any("5" in r for r in recs))

    def test_no_suggestion_if_values_same(self):
        # Pattern suggests threshold=40 (already at 40) — no recommendation
        patterns = [{
            "type": "high_skip_rate",
            "severity": "info",
            "message": "test",
            "data": {},
            "suggestion": {"nuclear_scan.min_score_threshold": 40},
        }]
        strategy = _minimal_strategy()
        recs = self._run([], patterns, strategy=strategy)
        # The value is already 40 so no recommendation about it
        self.assertFalse(any("40 -> 40" in r for r in recs))


if __name__ == "__main__":
    unittest.main()
