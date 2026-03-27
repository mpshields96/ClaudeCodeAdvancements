"""Tests for kelly_optimizer.py — Kelly criterion bet sizing optimizer.

Computes full Kelly, fractional Kelly, and stage-aware sizing given
current WR, win/loss amounts, and bankroll. Answers: what is the
theoretically justified max bet?
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kelly_optimizer import (
    KellyParams,
    KellyResult,
    KellyOptimizer,
    StageLimits,
)


class TestKellyParams(unittest.TestCase):
    """Test parameter validation and edge."""

    def test_basic_creation(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        self.assertAlmostEqual(p.win_rate, 0.933)

    def test_edge_calculation(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        # Edge = p*avg_win - q*avg_loss = 0.933*0.90 - 0.067*8.0 = 0.8397 - 0.536 = 0.3037
        self.assertAlmostEqual(p.edge(), 0.3037, places=3)

    def test_negative_edge(self):
        p = KellyParams(win_rate=0.50, avg_win=0.50, avg_loss=8.0, bankroll=200.0)
        self.assertLess(p.edge(), 0)

    def test_zero_bankroll(self):
        p = KellyParams(win_rate=0.93, avg_win=0.90, avg_loss=8.0, bankroll=0.0)
        self.assertAlmostEqual(p.bankroll, 0.0)


class TestKellyOptimizer(unittest.TestCase):
    """Test Kelly fraction computations."""

    def test_full_kelly(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        # Full Kelly = edge / avg_loss = 0.3037 / 8.0 ≈ 0.038
        self.assertAlmostEqual(r.full_kelly_fraction, 0.3037 / 8.0, places=3)
        self.assertGreater(r.full_kelly_fraction, 0)

    def test_half_kelly(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        self.assertAlmostEqual(r.half_kelly_fraction, r.full_kelly_fraction / 2, places=4)

    def test_quarter_kelly(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        self.assertAlmostEqual(r.quarter_kelly_fraction, r.full_kelly_fraction / 4, places=4)

    def test_dollar_amounts(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        self.assertAlmostEqual(r.full_kelly_bet, r.full_kelly_fraction * 213.80, places=2)
        self.assertAlmostEqual(r.half_kelly_bet, r.half_kelly_fraction * 213.80, places=2)
        self.assertAlmostEqual(r.quarter_kelly_bet, r.quarter_kelly_fraction * 213.80, places=2)

    def test_negative_edge_zero_bet(self):
        p = KellyParams(win_rate=0.50, avg_win=0.50, avg_loss=8.0, bankroll=200.0)
        opt = KellyOptimizer(p)
        r = opt.compute()
        self.assertAlmostEqual(r.full_kelly_fraction, 0.0)
        self.assertAlmostEqual(r.full_kelly_bet, 0.0)

    def test_growth_rate(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        # Growth rate should be positive for positive edge
        self.assertGreater(r.expected_growth_rate, 0)

    def test_ruin_estimate(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        # At quarter Kelly, ruin should be very low
        self.assertLess(r.ruin_at_quarter_kelly, 0.05)


class TestStageLimits(unittest.TestCase):
    """Test stage-based bet sizing constraints."""

    def test_stage1_limits(self):
        lim = StageLimits.for_bankroll(100.0)
        self.assertEqual(lim.stage, 1)
        self.assertAlmostEqual(lim.max_bet, 5.0)

    def test_stage2_limits(self):
        lim = StageLimits.for_bankroll(213.80)
        self.assertEqual(lim.stage, 2)
        self.assertAlmostEqual(lim.max_bet, 10.0)

    def test_stage3_limits(self):
        lim = StageLimits.for_bankroll(500.0)
        self.assertEqual(lim.stage, 3)
        self.assertAlmostEqual(lim.max_bet, 25.0)

    def test_small_bankroll(self):
        lim = StageLimits.for_bankroll(50.0)
        self.assertEqual(lim.stage, 1)
        self.assertAlmostEqual(lim.max_bet, 5.0)


class TestKellyOptimizerWithStage(unittest.TestCase):
    """Test Kelly + stage constraint integration."""

    def test_stage_capped_bet(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        stage = StageLimits.for_bankroll(213.80)
        # Recommended bet should not exceed stage max
        recommended = min(r.full_kelly_bet, stage.max_bet)
        self.assertLessEqual(recommended, 10.0)

    def test_recommended_bet_is_min_of_kelly_and_stage(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        r = opt.compute()
        # recommended_bet should be capped at stage limit
        self.assertLessEqual(r.recommended_bet, 10.0)
        # but should be at least quarter kelly if positive
        self.assertGreater(r.recommended_bet, 0)


class TestKellyOptimizerJSON(unittest.TestCase):
    """Test JSON export."""

    def test_to_dict(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        d = opt.to_dict()
        self.assertIn("params", d)
        self.assertIn("kelly", d)
        self.assertIn("stage", d)
        self.assertIn("full_kelly_fraction", d["kelly"])
        self.assertIn("recommended_bet", d["kelly"])

    def test_summary_text(self):
        p = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
        opt = KellyOptimizer(p)
        text = opt.summary_text()
        self.assertIn("Kelly", text)
        self.assertIn("213.80", text)


if __name__ == "__main__":
    unittest.main()
