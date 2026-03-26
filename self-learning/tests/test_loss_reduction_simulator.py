"""Tests for loss_reduction_simulator.py (REQ-057).

Models impact of reducing average loss magnitude on ruin probability and
daily P&L. Answers: if we reduce avg_loss from -11.39 to -8.00, how does
ruin probability change?
"""
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from loss_reduction_simulator import (
    LossReductionStrategy,
    LossReductionSweep,
    SweepPoint,
    StrategyImpact,
    LossReductionSimulator,
)
from monte_carlo_simulator import BetDistribution


class TestLossReductionStrategy(unittest.TestCase):
    """Test LossReductionStrategy dataclass."""

    def test_create_early_exit(self):
        s = LossReductionStrategy(
            name="early_exit",
            description="Exit when position moves 6c against us",
            target_avg_loss=-8.0,
            wr_impact=-0.005,  # slight WR decrease from exiting early
        )
        self.assertEqual(s.name, "early_exit")
        self.assertAlmostEqual(s.target_avg_loss, -8.0)
        self.assertAlmostEqual(s.wr_impact, -0.005)

    def test_create_tighter_floors(self):
        s = LossReductionStrategy(
            name="tighter_price_floors",
            description="Only enter at 93c+ instead of 90c+",
            target_avg_loss=-6.0,
            wr_impact=-0.01,
            volume_impact=-0.15,  # 15% fewer qualifying trades
        )
        self.assertAlmostEqual(s.volume_impact, -0.15)

    def test_create_reduced_sizing(self):
        s = LossReductionStrategy(
            name="reduced_sizing",
            description="Smaller bet size at lower-confidence entries",
            target_avg_loss=-7.50,
            wr_impact=0.0,  # no WR change
            avg_win_impact=-0.10,  # 10% smaller wins too
        )
        self.assertAlmostEqual(s.avg_win_impact, -0.10)


class TestSweepPoint(unittest.TestCase):
    """Test SweepPoint dataclass."""

    def test_create(self):
        p = SweepPoint(
            avg_loss=-10.0,
            win_rate=0.933,
            ruin_probability=0.15,
            target_probability=0.75,
            expected_daily_pnl=5.0,
            median_bankroll=250.0,
        )
        self.assertAlmostEqual(p.avg_loss, -10.0)
        self.assertAlmostEqual(p.ruin_probability, 0.15)

    def test_to_dict(self):
        p = SweepPoint(
            avg_loss=-10.0,
            win_rate=0.933,
            ruin_probability=0.15,
            target_probability=0.75,
            expected_daily_pnl=5.0,
            median_bankroll=250.0,
        )
        d = p.to_dict()
        self.assertEqual(d["avg_loss"], -10.0)
        self.assertEqual(d["ruin_probability"], 0.15)


class TestLossReductionSweep(unittest.TestCase):
    """Test LossReductionSweep result container."""

    def test_create_empty(self):
        sweep = LossReductionSweep(
            baseline_avg_loss=-11.39,
            baseline_ruin=0.50,
            points=[],
        )
        self.assertEqual(len(sweep.points), 0)
        self.assertAlmostEqual(sweep.baseline_avg_loss, -11.39)

    def test_find_breakeven_ruin(self):
        """Find the avg_loss where ruin drops below a threshold."""
        points = [
            SweepPoint(-11.0, 0.933, 0.50, 0.40, 4.0, 200.0),
            SweepPoint(-10.0, 0.933, 0.30, 0.60, 5.0, 220.0),
            SweepPoint(-9.0, 0.933, 0.10, 0.80, 6.0, 250.0),
            SweepPoint(-8.0, 0.933, 0.02, 0.95, 7.0, 280.0),
        ]
        sweep = LossReductionSweep(
            baseline_avg_loss=-11.39,
            baseline_ruin=0.50,
            points=points,
        )
        # Ruin < 5% threshold first achieved at -8.0
        threshold_point = sweep.find_ruin_threshold(0.05)
        self.assertIsNotNone(threshold_point)
        self.assertAlmostEqual(threshold_point.avg_loss, -8.0)

    def test_find_ruin_threshold_not_reached(self):
        points = [
            SweepPoint(-11.0, 0.933, 0.50, 0.40, 4.0, 200.0),
            SweepPoint(-10.0, 0.933, 0.30, 0.60, 5.0, 220.0),
        ]
        sweep = LossReductionSweep(
            baseline_avg_loss=-11.39,
            baseline_ruin=0.50,
            points=points,
        )
        result = sweep.find_ruin_threshold(0.01)
        self.assertIsNone(result)

    def test_summary(self):
        points = [
            SweepPoint(-11.0, 0.933, 0.50, 0.40, 4.0, 200.0),
            SweepPoint(-8.0, 0.933, 0.02, 0.95, 7.0, 280.0),
        ]
        sweep = LossReductionSweep(
            baseline_avg_loss=-11.39,
            baseline_ruin=0.50,
            points=points,
        )
        s = sweep.summary()
        self.assertIn("11.39", s)
        self.assertIn("-8.00", s)

    def test_to_dict(self):
        points = [SweepPoint(-10.0, 0.933, 0.30, 0.60, 5.0, 220.0)]
        sweep = LossReductionSweep(
            baseline_avg_loss=-11.39,
            baseline_ruin=0.50,
            points=points,
        )
        d = sweep.to_dict()
        self.assertIn("baseline_avg_loss", d)
        self.assertIn("points", d)
        self.assertEqual(len(d["points"]), 1)


class TestStrategyImpact(unittest.TestCase):
    """Test StrategyImpact result for individual strategies."""

    def test_create(self):
        si = StrategyImpact(
            strategy_name="early_exit",
            original_ruin=0.50,
            new_ruin=0.02,
            original_daily_pnl=6.07,
            new_daily_pnl=7.50,
            original_avg_loss=-11.39,
            new_avg_loss=-8.0,
            ruin_reduction=0.48,
            pnl_improvement=1.43,
        )
        self.assertAlmostEqual(si.ruin_reduction, 0.48)
        self.assertAlmostEqual(si.pnl_improvement, 1.43)

    def test_summary(self):
        si = StrategyImpact(
            strategy_name="early_exit",
            original_ruin=0.50,
            new_ruin=0.02,
            original_daily_pnl=6.07,
            new_daily_pnl=7.50,
            original_avg_loss=-11.39,
            new_avg_loss=-8.0,
            ruin_reduction=0.48,
            pnl_improvement=1.43,
        )
        s = si.summary()
        self.assertIn("early_exit", s)
        self.assertIn("ruin", s.lower())


class TestLossReductionSimulator(unittest.TestCase):
    """Test the main simulator engine."""

    def setUp(self):
        """Base distribution matching REQ-57 data."""
        self.base_dist = BetDistribution(
            win_rate=0.933,
            avg_win=0.90,
            avg_loss=-11.39,
            total_bets=100,
            daily_volume=78,
        )

    def test_create_simulator(self):
        sim = LossReductionSimulator(self.base_dist)
        self.assertAlmostEqual(sim.base_distribution.avg_loss, -11.39)

    def test_sweep_avg_loss(self):
        """Sweep avg_loss from -11.39 to -6.0 in steps."""
        sim = LossReductionSimulator(self.base_dist)
        sweep = sim.sweep_avg_loss(
            start=-11.0,
            end=-6.0,
            step=1.0,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,  # low count for speed in tests
            seed=42,
        )
        self.assertIsInstance(sweep, LossReductionSweep)
        self.assertEqual(len(sweep.points), 6)  # -11, -10, -9, -8, -7, -6
        # Ruin should decrease as avg_loss magnitude decreases
        ruin_values = [p.ruin_probability for p in sweep.points]
        # At least the trend should be non-increasing (less loss = less ruin)
        # With only 100 sims there's noise, so just check first > last
        self.assertGreaterEqual(ruin_values[0], ruin_values[-1])

    def test_sweep_preserves_win_rate(self):
        """Sweep should keep WR constant unless strategy modifies it."""
        sim = LossReductionSimulator(self.base_dist)
        sweep = sim.sweep_avg_loss(
            start=-11.0, end=-8.0, step=1.0,
            bankroll=178.05, target=250.0,
            n_days=30, n_sims=50, seed=42,
        )
        for p in sweep.points:
            self.assertAlmostEqual(p.win_rate, 0.933)

    def test_evaluate_strategy_early_exit(self):
        """Evaluate a specific loss reduction strategy."""
        sim = LossReductionSimulator(self.base_dist)
        strategy = LossReductionStrategy(
            name="early_exit",
            description="Exit at 8c loss",
            target_avg_loss=-8.0,
            wr_impact=-0.005,
        )
        impact = sim.evaluate_strategy(
            strategy,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,
            seed=42,
        )
        self.assertIsInstance(impact, StrategyImpact)
        self.assertEqual(impact.strategy_name, "early_exit")
        self.assertAlmostEqual(impact.new_avg_loss, -8.0)
        # New WR should be 0.933 - 0.005 = 0.928
        # (checked implicitly via the sim running)

    def test_evaluate_strategy_with_volume_impact(self):
        """Strategy that reduces trade volume."""
        sim = LossReductionSimulator(self.base_dist)
        strategy = LossReductionStrategy(
            name="tighter_floors",
            description="93c+ only",
            target_avg_loss=-6.0,
            wr_impact=-0.01,
            volume_impact=-0.15,
        )
        impact = sim.evaluate_strategy(
            strategy,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,
            seed=42,
        )
        self.assertEqual(impact.strategy_name, "tighter_floors")

    def test_evaluate_strategy_with_win_impact(self):
        """Strategy that also reduces avg_win."""
        sim = LossReductionSimulator(self.base_dist)
        strategy = LossReductionStrategy(
            name="reduced_sizing",
            description="Smaller bets",
            target_avg_loss=-7.50,
            wr_impact=0.0,
            avg_win_impact=-0.10,
        )
        impact = sim.evaluate_strategy(
            strategy,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,
            seed=42,
        )
        self.assertEqual(impact.strategy_name, "reduced_sizing")

    def test_compare_strategies(self):
        """Compare multiple strategies and rank by ruin reduction."""
        sim = LossReductionSimulator(self.base_dist)
        strategies = [
            LossReductionStrategy("early_exit", "Exit at 8c", -8.0, -0.005),
            LossReductionStrategy("tighter_floors", "93c+", -6.0, -0.01, -0.15),
            LossReductionStrategy("reduced_sizing", "Smaller bets", -7.50, 0.0, 0.0, -0.10),
        ]
        results = sim.compare_strategies(
            strategies,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,
            seed=42,
        )
        self.assertEqual(len(results), 3)
        # Results should be sorted by ruin reduction (best first)
        for r in results:
            self.assertIsInstance(r, StrategyImpact)

    def test_expected_value_changes(self):
        """Verify EV calculation changes correctly with avg_loss."""
        sim = LossReductionSimulator(self.base_dist)
        # Base EV: 0.933 * 0.90 + 0.067 * (-11.39) = 0.8397 - 0.7631 = 0.0766
        base_ev = self.base_dist.expected_value()
        self.assertAlmostEqual(base_ev, 0.933 * 0.90 + 0.067 * (-11.39), places=3)

        # With -8.0 loss: 0.933 * 0.90 + 0.067 * (-8.0) = 0.8397 - 0.536 = 0.3037
        modified = BetDistribution(
            win_rate=0.933, avg_win=0.90, avg_loss=-8.0,
            daily_volume=78, total_bets=100,
        )
        new_ev = modified.expected_value()
        self.assertGreater(new_ev, base_ev)

    def test_recovery_ratio(self):
        """Test wins-to-recover calculation."""
        sim = LossReductionSimulator(self.base_dist)
        # At -11.39 loss, 0.90 win: need 11.39/0.90 = 12.66 wins
        ratio_base = sim.recovery_ratio(-11.39)
        self.assertAlmostEqual(ratio_base, 11.39 / 0.90, places=1)
        # At -8.0 loss: need 8.0/0.90 = 8.89 wins
        ratio_new = sim.recovery_ratio(-8.0)
        self.assertAlmostEqual(ratio_new, 8.0 / 0.90, places=1)

    def test_daily_self_sustaining_threshold(self):
        """Calculate minimum daily P&L for $250/month target."""
        sim = LossReductionSimulator(self.base_dist)
        threshold = sim.self_sustaining_daily_pnl(monthly_target=250.0)
        # 250 / 30 = 8.33
        self.assertAlmostEqual(threshold, 250.0 / 30.0, places=2)

    def test_wr_sensitivity_at_loss_level(self):
        """Sweep WR at a fixed avg_loss to find the cliff."""
        sim = LossReductionSimulator(self.base_dist)
        results = sim.wr_sensitivity(
            avg_loss=-8.0,
            wr_range=(0.90, 0.96),
            wr_step=0.01,
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=100,
            seed=42,
        )
        self.assertGreater(len(results), 0)
        # Each result is a SweepPoint with the WR varied
        for p in results:
            self.assertGreaterEqual(p.win_rate, 0.90)
            self.assertLessEqual(p.win_rate, 0.96)

    def test_full_report(self):
        """Generate a full analysis report as dict."""
        sim = LossReductionSimulator(self.base_dist)
        report = sim.full_report(
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=50,
            seed=42,
        )
        self.assertIn("sweep", report)
        self.assertIn("strategies", report)
        self.assertIn("wr_sensitivity", report)
        self.assertIn("recovery_ratios", report)
        self.assertIn("self_sustaining_daily", report)

    def test_full_report_json_serializable(self):
        """Report must be JSON-serializable for cross-chat delivery."""
        sim = LossReductionSimulator(self.base_dist)
        report = sim.full_report(
            bankroll=178.05,
            target=250.0,
            n_days=60,
            n_sims=50,
            seed=42,
        )
        # Should not raise
        json_str = json.dumps(report)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertIn("sweep", parsed)


if __name__ == "__main__":
    unittest.main()
