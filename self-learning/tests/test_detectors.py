#!/usr/bin/env python3
"""Tests for detectors.py — MT-28 Phase 2: Built-in pattern detector plugins."""

import os
import sys
import json
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)
sys.path.insert(0, os.path.dirname(MODULE_DIR))


class DetectorTestBase(unittest.TestCase):
    """Base class with helpers for detector tests."""

    def setUp(self):
        # Clear registry before each test so detectors re-register cleanly
        import pattern_registry
        pattern_registry._registry.clear()
        # Re-import detectors to register them fresh
        if "detectors" in sys.modules:
            del sys.modules["detectors"]
        import detectors  # noqa: F811
        self.registry = pattern_registry

    def _make_bet_outcome(self, strategy_name="sniper", result="win",
                          pnl_cents=100, timestamp="2026-03-21T14:00:00Z"):
        return {
            "event_type": "bet_outcome",
            "timestamp": timestamp,
            "metrics": {
                "strategy_name": strategy_name,
                "result": result,
                "pnl_cents": pnl_cents,
            },
        }


class TestVerdictDriftDetector(DetectorTestBase):

    def test_high_skip_rate(self):
        """Detects when skip rate > 60%."""
        entries = [
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 100, "skip": 70, "fast_skip": 0, "build": 5}},
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 100, "skip": 65, "fast_skip": 5, "build": 3}},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("high_skip_rate", types)

    def test_low_build_rate(self):
        """Detects when BUILD rate < 3%."""
        entries = [
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 100, "skip": 50, "fast_skip": 0, "build": 1}},
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 100, "skip": 50, "fast_skip": 0, "build": 2}},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("low_build_rate", types)

    def test_no_trigger_with_one_batch(self):
        """Needs at least 2 nuclear batches."""
        entries = [
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 100, "skip": 90, "build": 1}},
        ]
        patterns = self.registry.run_all_detectors(entries)
        verdict_types = [p["type"] for p in patterns if p["type"] in ("high_skip_rate", "low_build_rate")]
        self.assertEqual(len(verdict_types), 0)


class TestDomainConcentrationDetector(DetectorTestBase):

    def test_detects_concentration(self):
        """Detects when one domain > 70%."""
        entries = [{"domain": "nuclear_scan"} for _ in range(8)]
        entries += [{"domain": "trading"} for _ in range(2)]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("domain_concentration", types)

    def test_no_trigger_balanced(self):
        """No trigger when domains are balanced."""
        entries = [{"domain": "nuclear_scan"} for _ in range(5)]
        entries += [{"domain": "trading"} for _ in range(5)]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("domain_concentration", types)


class TestRecurringThemesDetector(DetectorTestBase):

    def test_detects_recurring_words(self):
        """Detects words appearing 3+ times in learnings."""
        entries = [
            {"learnings": ["Always verify before committing"]},
            {"learnings": ["Need to verify configuration first"]},
            {"learnings": ["Should verify the output matches"]},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("recurring_themes", types)

    def test_no_trigger_without_learnings(self):
        """No trigger when entries have no learnings."""
        entries = [{"event_type": "test"} for _ in range(5)]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("recurring_themes", types)


class TestConsecutiveFailuresDetector(DetectorTestBase):

    def test_detects_failures(self):
        """Detects 2+ failures in last 3 session outcomes."""
        entries = [
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "failure"},
            {"event_type": "session_outcome", "outcome": "failure"},
            {"event_type": "session_outcome", "outcome": "failure"},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("consecutive_failures", types)

    def test_no_trigger_mostly_success(self):
        """No trigger when mostly successes."""
        entries = [
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "success"},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("consecutive_failures", types)


class TestLosingStrategyDetector(DetectorTestBase):

    def test_detects_low_win_rate(self):
        """Detects strategy with win rate below threshold."""
        entries = []
        for i in range(25):
            result = "win" if i < 5 else "loss"  # 20% WR
            entries.append(self._make_bet_outcome(
                strategy_name="bad_strat", result=result, pnl_cents=-50 if result == "loss" else 100))

        strategy = {"trading": {"win_rate_alert_below": 0.4, "min_sample_bets": 20}}
        patterns = self.registry.run_all_detectors(entries, strategy=strategy)
        types = [p["type"] for p in patterns]
        self.assertIn("losing_strategy", types)

    def test_no_trigger_good_strategy(self):
        """No trigger for strategies above threshold."""
        entries = []
        for i in range(25):
            result = "win" if i < 20 else "loss"  # 80% WR
            entries.append(self._make_bet_outcome(
                strategy_name="good_strat", result=result))

        strategy = {"trading": {"win_rate_alert_below": 0.4, "min_sample_bets": 20}}
        patterns = self.registry.run_all_detectors(entries, strategy=strategy)
        types = [p["type"] for p in patterns]
        self.assertNotIn("losing_strategy", types)

    def test_no_trigger_insufficient_sample(self):
        """No trigger with too few bets."""
        entries = [self._make_bet_outcome(result="loss") for _ in range(5)]
        strategy = {"trading": {"win_rate_alert_below": 0.4, "min_sample_bets": 20}}
        patterns = self.registry.run_all_detectors(entries, strategy=strategy)
        types = [p["type"] for p in patterns]
        self.assertNotIn("losing_strategy", types)


class TestResearchDeadEndDetector(DetectorTestBase):

    def test_detects_dead_end(self):
        """Detects research path with zero actionable results."""
        entries = [
            {"event_type": "market_research", "metrics": {"research_path": "dead_end", "actionable": False}}
            for _ in range(6)
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("research_dead_end", types)

    def test_no_trigger_with_actionable(self):
        """No trigger when path has actionable results."""
        entries = [
            {"event_type": "market_research", "metrics": {"research_path": "good_path", "actionable": True}}
            for _ in range(6)
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("research_dead_end", types)


class TestNegativePnlDetector(DetectorTestBase):

    def test_detects_negative_pnl(self):
        """Detects when cumulative PnL is negative."""
        entries = [self._make_bet_outcome(result="loss", pnl_cents=-100) for _ in range(6)]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("negative_pnl", types)

    def test_no_trigger_positive_pnl(self):
        """No trigger when PnL is positive."""
        entries = [self._make_bet_outcome(result="win", pnl_cents=100) for _ in range(6)]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("negative_pnl", types)


class TestStrongEdgeDiscoveryDetector(DetectorTestBase):

    def test_detects_strong_discovery(self):
        """Detects edge discovery rate > 60%."""
        entries = [
            {"event_type": "edge_discovered"},
            {"event_type": "edge_discovered"},
            {"event_type": "edge_discovered"},
            {"event_type": "edge_rejected"},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("strong_edge_discovery", types)

    def test_no_trigger_low_discovery(self):
        """No trigger when discovery rate is low."""
        entries = [
            {"event_type": "edge_discovered"},
            {"event_type": "edge_rejected"},
            {"event_type": "edge_rejected"},
            {"event_type": "edge_rejected"},
        ]
        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("strong_edge_discovery", types)


class TestOvernightWrGapDetector(DetectorTestBase):

    def test_detects_gap(self):
        """Detects overnight vs daytime WR gap > 10%."""
        entries = []
        # 10 overnight bets: 5 wins (50% WR)
        for i in range(10):
            entries.append(self._make_bet_outcome(
                result="win" if i < 5 else "loss",
                timestamp="2026-03-21T03:00:00Z"))
        # 10 daytime bets: 9 wins (90% WR)
        for i in range(10):
            entries.append(self._make_bet_outcome(
                result="win" if i < 9 else "loss",
                timestamp="2026-03-21T14:00:00Z"))

        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertIn("overnight_wr_gap", types)

    def test_no_trigger_similar_wr(self):
        """No trigger when overnight and daytime WR are similar."""
        entries = []
        for i in range(10):
            entries.append(self._make_bet_outcome(
                result="win" if i < 8 else "loss",
                timestamp="2026-03-21T03:00:00Z"))
        for i in range(10):
            entries.append(self._make_bet_outcome(
                result="win" if i < 8 else "loss",
                timestamp="2026-03-21T14:00:00Z"))

        patterns = self.registry.run_all_detectors(entries)
        types = [p["type"] for p in patterns]
        self.assertNotIn("overnight_wr_gap", types)


class TestStaleStrategyDetector(DetectorTestBase):

    def test_detects_stale(self):
        """Detects strategy older than 14 days with enough entries."""
        entries = [{"domain": "general"} for _ in range(15)]
        strategy = {"updated_at": "2026-01-01T00:00:00Z"}
        patterns = self.registry.run_all_detectors(entries, strategy=strategy)
        types = [p["type"] for p in patterns]
        self.assertIn("stale_strategy", types)

    def test_no_trigger_fresh_strategy(self):
        """No trigger for recently updated strategy."""
        from datetime import datetime, timezone
        entries = [{"domain": "general"} for _ in range(15)]
        strategy = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        patterns = self.registry.run_all_detectors(entries, strategy=strategy)
        types = [p["type"] for p in patterns]
        self.assertNotIn("stale_strategy", types)


class TestRegistryIntegration(DetectorTestBase):

    def test_all_12_detectors_registered(self):
        """All 12 built-in detectors are registered."""
        self.assertEqual(len(self.registry.get_all_detectors()), 12)

    def test_general_detectors_count(self):
        """7 general-domain detectors (6 original + principle_transfer)."""
        gen = self.registry.get_detectors(domain="general")
        self.assertEqual(len(gen), 7)

    def test_trading_detectors_count(self):
        """6 trading-domain detectors (5 original + principle_transfer)."""
        trade = self.registry.get_detectors(domain="trading")
        self.assertEqual(len(trade), 6)

    def test_domain_filter_isolates(self):
        """Domain filtering only returns matching detectors."""
        entries = [self._make_bet_outcome(result="loss", pnl_cents=-100) for _ in range(6)]
        # Run only general detectors — should NOT find negative_pnl
        gen_patterns = self.registry.run_all_detectors(entries, domain="general")
        types = [p["type"] for p in gen_patterns]
        self.assertNotIn("negative_pnl", types)

    def test_empty_entries_no_crash(self):
        """Running all detectors on empty entries doesn't crash."""
        patterns = self.registry.run_all_detectors(entries=[])
        self.assertIsInstance(patterns, list)

    def test_list_detectors_metadata(self):
        """list_detectors returns correct metadata for all."""
        info = self.registry.list_detectors()
        self.assertEqual(len(info), 12)
        names = {d["name"] for d in info}
        self.assertIn("verdict_drift", names)
        self.assertIn("losing_strategy", names)
        self.assertIn("overnight_wr_gap", names)
        self.assertIn("principle_transfer", names)


if __name__ == "__main__":
    unittest.main()
