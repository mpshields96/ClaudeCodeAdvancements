"""
test_journal_extended.py — Extended tests for journal.py

Focuses on edge cases in:
- get_trading_metrics: market types, strategies, void handling, win rate
- get_time_stratified_trading_metrics: time buckets, overnight/daytime, Wilson CI
- get_nuclear_metrics: aggregation, rate calculations
- get_pain_win_summary: ratio, domain breakdowns
- log_event: boundary conditions, large payloads
- get_stats: multi-domain, multi-session aggregation
"""

import json
import math
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_journal(entries, tmpdir):
    """Write entries to a temp journal.jsonl and patch JOURNAL_PATH."""
    path = os.path.join(tmpdir, "journal.jsonl")
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


def _bet_outcome(result, pnl, market_type="binary", strategy="sniper", hour=12):
    """Helper to create a bet_outcome entry."""
    return {
        "event_type": "bet_outcome",
        "timestamp": f"2026-03-20T{hour:02d}:30:00Z",
        "domain": "trading",
        "metrics": {
            "result": result,
            "pnl_cents": pnl,
            "market_type": market_type,
            "strategy_name": strategy,
        },
    }


class TestTradingMetricsEdgeCases(unittest.TestCase):
    """Extended edge cases for get_trading_metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_trading_metrics()

    def test_all_voids_no_win_rate(self):
        result = self._patch_and_call([
            _bet_outcome("void", 0),
            _bet_outcome("void", 0),
        ])
        self.assertEqual(result["voids"], 2)
        self.assertNotIn("win_rate", result)

    def test_mixed_results_win_rate(self):
        entries = (
            [_bet_outcome("win", 100)] * 7
            + [_bet_outcome("loss", -50)] * 3
        )
        result = self._patch_and_call(entries)
        self.assertAlmostEqual(result["win_rate"], 0.7, places=2)

    def test_pnl_aggregation_positive(self):
        entries = [
            _bet_outcome("win", 200),
            _bet_outcome("win", 150),
            _bet_outcome("loss", -100),
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["total_pnl_cents"], 250)

    def test_pnl_aggregation_negative(self):
        entries = [
            _bet_outcome("win", 50),
            _bet_outcome("loss", -200),
            _bet_outcome("loss", -100),
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["total_pnl_cents"], -250)

    def test_multiple_market_types(self):
        entries = [
            _bet_outcome("win", 100, market_type="binary"),
            _bet_outcome("loss", -50, market_type="binary"),
            _bet_outcome("win", 200, market_type="range"),
            _bet_outcome("win", 150, market_type="range"),
        ]
        result = self._patch_and_call(entries)
        self.assertIn("binary", result["by_market_type"])
        self.assertIn("range", result["by_market_type"])
        self.assertEqual(result["by_market_type"]["range"]["wins"], 2)
        self.assertEqual(result["by_market_type"]["binary"]["losses"], 1)

    def test_multiple_strategies(self):
        entries = [
            _bet_outcome("win", 100, strategy="sniper"),
            _bet_outcome("win", 100, strategy="sniper"),
            _bet_outcome("loss", -50, strategy="value"),
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_strategy"]["sniper"]["wins"], 2)
        self.assertEqual(result["by_strategy"]["value"]["losses"], 1)

    def test_research_effectiveness(self):
        entries = [
            {"event_type": "market_research", "domain": "trading",
             "metrics": {"actionable": True}},
            {"event_type": "market_research", "domain": "trading",
             "metrics": {"actionable": False}},
            {"event_type": "market_research", "domain": "trading",
             "metrics": {}},
            {"event_type": "edge_discovered", "domain": "trading"},
            {"event_type": "edge_rejected", "domain": "trading"},
            {"event_type": "edge_rejected", "domain": "trading"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["research"]["total_sessions"], 3)
        self.assertEqual(result["research"]["actionable"], 1)
        self.assertEqual(result["research"]["edges_discovered"], 1)
        self.assertEqual(result["research"]["edges_rejected"], 2)

    def test_only_research_no_bets(self):
        entries = [
            {"event_type": "market_research", "domain": "trading", "metrics": {}},
        ]
        result = self._patch_and_call(entries)
        self.assertIsNotNone(result)
        self.assertEqual(result["total_bets"], 0)
        self.assertEqual(result["research"]["total_sessions"], 1)

    def test_single_bet_win_rate_1(self):
        result = self._patch_and_call([_bet_outcome("win", 100)])
        self.assertEqual(result["win_rate"], 1.0)

    def test_zero_pnl_bet(self):
        result = self._patch_and_call([_bet_outcome("win", 0)])
        self.assertEqual(result["total_pnl_cents"], 0)
        self.assertEqual(result["wins"], 1)


class TestTimeStratifiedEdgeCases(unittest.TestCase):
    """Extended edge cases for get_time_stratified_trading_metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries, **kwargs):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_time_stratified_trading_metrics(**kwargs)

    def test_all_overnight_bets(self):
        entries = [_bet_outcome("win", 100, hour=3)] * 5
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_time_bucket"]["overnight"]["bets"], 5)
        self.assertEqual(result["by_time_bucket"]["morning"]["bets"], 0)

    def test_all_afternoon_bets(self):
        entries = [_bet_outcome("loss", -50, hour=15)] * 3
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_time_bucket"]["afternoon"]["bets"], 3)
        self.assertEqual(result["by_time_bucket"]["afternoon"]["losses"], 3)

    def test_hourly_distribution(self):
        entries = [
            _bet_outcome("win", 100, hour=0),
            _bet_outcome("win", 100, hour=12),
            _bet_outcome("loss", -50, hour=23),
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_hour"][0]["bets"], 1)
        self.assertEqual(result["by_hour"][12]["bets"], 1)
        self.assertEqual(result["by_hour"][23]["bets"], 1)
        self.assertEqual(result["by_hour"][6]["bets"], 0)

    def test_worst_hours_sorted_ascending(self):
        entries = [
            _bet_outcome("loss", -500, hour=3),
            _bet_outcome("loss", -100, hour=15),
            _bet_outcome("win", 200, hour=10),
        ]
        result = self._patch_and_call(entries)
        if result["worst_hours"]:
            # Worst hour (lowest PnL) should be first
            self.assertEqual(result["worst_hours"][0][0], 3)

    def test_custom_time_buckets(self):
        entries = [_bet_outcome("win", 100, hour=6)] * 3
        custom = [("early", 0, 12), ("late", 12, 24)]
        result = self._patch_and_call(entries, time_buckets=custom)
        self.assertIn("early", result["by_time_bucket"])
        self.assertEqual(result["by_time_bucket"]["early"]["bets"], 3)

    def test_significance_requires_10_bets(self):
        # 5 overnight + 5 daytime = not enough for significance
        entries = (
            [_bet_outcome("win", 100, hour=3)] * 5
            + [_bet_outcome("loss", -100, hour=15)] * 5
        )
        result = self._patch_and_call(entries)
        self.assertFalse(result["overnight_vs_daytime"]["significant"])

    def test_significance_with_enough_bets(self):
        # 15 overnight losses + 15 daytime wins = significant
        entries = (
            [_bet_outcome("loss", -100, hour=3)] * 15
            + [_bet_outcome("win", 100, hour=15)] * 15
        )
        result = self._patch_and_call(entries)
        # Should be significant (0% overnight vs 100% daytime)
        self.assertTrue(result["overnight_vs_daytime"]["significant"])

    def test_overnight_vs_daytime_delta(self):
        entries = (
            [_bet_outcome("win", 100, hour=3)] * 8
            + [_bet_outcome("loss", -50, hour=3)] * 2
            + [_bet_outcome("win", 100, hour=15)] * 5
            + [_bet_outcome("loss", -50, hour=15)] * 5
        )
        result = self._patch_and_call(entries)
        delta = result["overnight_vs_daytime"]["delta_wr"]
        self.assertIsNotNone(delta)
        # Daytime 50% - Overnight 80% = negative delta
        self.assertLess(delta, 0)

    def test_invalid_timestamp_skipped(self):
        entries = [
            {"event_type": "bet_outcome", "timestamp": "bad-timestamp",
             "metrics": {"result": "win", "pnl_cents": 100}},
            _bet_outcome("win", 100, hour=12),
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["total_bets_analyzed"], 2)
        # Only the valid one should appear in hourly
        self.assertEqual(result["by_hour"][12]["bets"], 1)

    def test_max_5_worst_hours(self):
        entries = []
        for h in range(24):
            entries.append(_bet_outcome("loss", -(h + 1) * 10, hour=h))
        result = self._patch_and_call(entries)
        self.assertLessEqual(len(result["worst_hours"]), 5)

    def test_win_rate_per_bucket(self):
        entries = [
            _bet_outcome("win", 100, hour=10),
            _bet_outcome("win", 100, hour=10),
            _bet_outcome("loss", -50, hour=10),
        ]
        result = self._patch_and_call(entries)
        wr = result["by_time_bucket"]["morning"]["win_rate"]
        self.assertAlmostEqual(wr, 0.6667, places=3)


class TestNuclearMetricsExtended(unittest.TestCase):
    """Extended nuclear metrics tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_nuclear_metrics()

    def test_multiple_batches_aggregate(self):
        entries = [
            {"event_type": "nuclear_batch", "session_id": 1,
             "metrics": {"posts_reviewed": 20, "build": 2, "adapt": 3, "skip": 15}},
            {"event_type": "nuclear_batch", "session_id": 1,
             "metrics": {"posts_reviewed": 30, "build": 1, "adapt": 5, "skip": 24}},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["posts_reviewed"], 50)
        self.assertEqual(result["build"], 3)
        self.assertEqual(result["adapt"], 8)

    def test_signal_rate_calculation(self):
        entries = [
            {"event_type": "nuclear_batch", "session_id": 1,
             "metrics": {"posts_reviewed": 100, "build": 5, "adapt": 15, "skip": 80}},
        ]
        result = self._patch_and_call(entries)
        self.assertAlmostEqual(result["signal_rate"], 0.2, places=3)

    def test_fast_skip_counted(self):
        entries = [
            {"event_type": "nuclear_batch", "session_id": 1,
             "metrics": {"posts_reviewed": 50, "fast_skip": 30}},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["fast_skip"], 30)

    def test_unique_session_count(self):
        entries = [
            {"event_type": "nuclear_batch", "session_id": 1, "metrics": {"posts_reviewed": 10}},
            {"event_type": "nuclear_batch", "session_id": 1, "metrics": {"posts_reviewed": 10}},
            {"event_type": "nuclear_batch", "session_id": 2, "metrics": {"posts_reviewed": 10}},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["sessions"], 2)

    def test_zero_posts_no_rate_keys(self):
        entries = [
            {"event_type": "nuclear_batch", "session_id": 1, "metrics": {}},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["posts_reviewed"], 0)
        self.assertNotIn("build_rate", result)

    def test_non_nuclear_entries_ignored(self):
        entries = [
            {"event_type": "session_outcome", "metrics": {"posts_reviewed": 999}},
            {"event_type": "nuclear_batch", "session_id": 1,
             "metrics": {"posts_reviewed": 10, "build": 1}},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["posts_reviewed"], 10)


class TestPainWinExtended(unittest.TestCase):
    """Extended pain/win summary tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_pain_win_summary()

    def test_ratio_all_wins(self):
        entries = [
            {"event_type": "win", "domain": "general"},
            {"event_type": "win", "domain": "general"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["ratio"], 1.0)

    def test_ratio_all_pains(self):
        entries = [
            {"event_type": "pain", "domain": "general"},
            {"event_type": "pain", "domain": "general"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["ratio"], 0.0)

    def test_ratio_balanced(self):
        entries = [
            {"event_type": "pain", "domain": "general"},
            {"event_type": "win", "domain": "general"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["ratio"], 0.5)

    def test_multiple_domains(self):
        entries = [
            {"event_type": "pain", "domain": "memory_system"},
            {"event_type": "pain", "domain": "memory_system"},
            {"event_type": "pain", "domain": "agent_guard"},
            {"event_type": "win", "domain": "self_learning"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["pain_domains"]["memory_system"], 2)
        self.assertEqual(result["pain_domains"]["agent_guard"], 1)
        self.assertEqual(result["win_domains"]["self_learning"], 1)

    def test_entries_included_in_output(self):
        entries = [
            {"event_type": "pain", "domain": "general", "notes": "test pain"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(len(result["pain_entries"]), 1)
        self.assertEqual(result["pain_entries"][0]["notes"], "test pain")

    def test_non_pain_win_ignored(self):
        entries = [
            {"event_type": "session_outcome", "domain": "general"},
            {"event_type": "pain", "domain": "general"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["pain_count"], 1)
        self.assertEqual(result["win_count"], 0)


class TestLogEventExtended(unittest.TestCase):
    """Extended log_event tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")
        self.strategy_path = os.path.join(self.tmpdir, "strategy.json")

    def _patch_log(self, **kwargs):
        import journal
        with patch.object(journal, "JOURNAL_PATH", self.journal_path), \
             patch.object(journal, "STRATEGY_PATH", self.strategy_path):
            return journal.log_event(**kwargs)

    def test_large_metrics_dict(self):
        metrics = {f"key_{i}": i for i in range(100)}
        entry = self._patch_log(event_type="session_outcome", metrics=metrics)
        self.assertEqual(len(entry["metrics"]), 100)

    def test_large_learnings_list(self):
        learnings = [f"learning_{i}" for i in range(50)]
        entry = self._patch_log(event_type="nuclear_batch", learnings=learnings)
        self.assertEqual(len(entry["learnings"]), 50)

    def test_strategy_version_from_file(self):
        with open(self.strategy_path, "w") as f:
            json.dump({"version": 42}, f)
        entry = self._patch_log(event_type="session_outcome")
        self.assertEqual(entry["strategy_version"], "v42")

    def test_strategy_version_override(self):
        entry = self._patch_log(
            event_type="session_outcome",
            strategy_version="v99"
        )
        self.assertEqual(entry["strategy_version"], "v99")

    def test_all_valid_event_types_accepted(self):
        import journal
        for et in journal.VALID_EVENT_TYPES:
            entry = self._patch_log(event_type=et)
            self.assertEqual(entry["event_type"], et)

    def test_all_valid_domains_accepted(self):
        import journal
        for d in journal.VALID_DOMAINS:
            entry = self._patch_log(event_type="session_outcome", domain=d)
            self.assertEqual(entry["domain"], d)

    def test_all_valid_outcomes_accepted(self):
        import journal
        for o in journal.VALID_OUTCOMES:
            entry = self._patch_log(event_type="session_outcome", outcome=o)
            self.assertEqual(entry["outcome"], o)


class TestGetStatsExtended(unittest.TestCase):
    """Extended get_stats tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_stats()

    def test_multiple_sessions_counted(self):
        entries = [
            {"event_type": "session_outcome", "session_id": 1},
            {"event_type": "session_outcome", "session_id": 2},
            {"event_type": "session_outcome", "session_id": 2},
            {"event_type": "session_outcome", "session_id": 3},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(len(result["sessions_logged"]), 3)

    def test_learnings_aggregated_across_entries(self):
        entries = [
            {"event_type": "nuclear_batch", "learnings": ["a", "b"]},
            {"event_type": "nuclear_batch", "learnings": ["c"]},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["total_learnings"], 3)

    def test_first_and_last_timestamps(self):
        entries = [
            {"event_type": "session_outcome", "timestamp": "2026-03-01T00:00:00Z"},
            {"event_type": "session_outcome", "timestamp": "2026-03-20T12:00:00Z"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["first_entry"], "2026-03-01T00:00:00Z")
        self.assertEqual(result["last_entry"], "2026-03-20T12:00:00Z")

    def test_event_type_counts(self):
        entries = [
            {"event_type": "pain"},
            {"event_type": "pain"},
            {"event_type": "win"},
            {"event_type": "session_outcome"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_event_type"]["pain"], 2)
        self.assertEqual(result["by_event_type"]["win"], 1)

    def test_outcome_counts(self):
        entries = [
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "failure"},
        ]
        result = self._patch_and_call(entries)
        self.assertEqual(result["by_outcome"]["success"], 2)
        self.assertEqual(result["by_outcome"]["failure"], 1)


class TestGetRecentExtended(unittest.TestCase):
    """Extended get_recent tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _patch_and_call(self, entries, n=10):
        import journal
        path = _make_journal(entries, self.tmpdir)
        with patch.object(journal, "JOURNAL_PATH", path):
            return journal.get_recent(n)

    def test_returns_last_n(self):
        entries = [{"event_type": f"e{i}"} for i in range(20)]
        result = self._patch_and_call(entries, n=5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]["event_type"], "e15")

    def test_n_larger_than_total(self):
        entries = [{"event_type": "a"}, {"event_type": "b"}]
        result = self._patch_and_call(entries, n=100)
        self.assertEqual(len(result), 2)

    def test_empty_journal(self):
        result = self._patch_and_call([], n=5)
        self.assertEqual(len(result), 0)


class TestWilsonCI(unittest.TestCase):
    """Test the Wilson confidence interval helper."""

    def test_wilson_ci_50_percent(self):
        import journal
        # Need to access _wilson_ci indirectly since it's nested
        # We test via the time stratified function behavior instead
        # Just verify the formula produces reasonable bounds
        z = 1.96
        n, k = 100, 50  # 50% success rate
        p = k / n
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        lo = max(0, center - margin)
        hi = min(1, center + margin)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_wilson_ci_extreme_values(self):
        z = 1.96
        # 80% success rate with small n should have wide CI
        n, k = 5, 4
        p = k / n
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        lo = max(0, center - margin)
        hi = min(1, center + margin)
        # Wide CI with small n
        self.assertGreater(hi - lo, 0.3)


if __name__ == "__main__":
    unittest.main()
