"""Tests for strategy_allocator.py — multi-strategy capital allocation.

Answers: given N strategies with known WR/avg_win/avg_loss profiles, what
fraction of bankroll should each strategy receive to maximize expected P&L
while constraining ruin probability?
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from strategy_allocator import (
    StrategyProfile,
    AllocationResult,
    AllocationConstraints,
    StrategyAllocator,
)


class TestStrategyProfile(unittest.TestCase):
    """Test StrategyProfile dataclass."""

    def test_create_sniper(self):
        p = StrategyProfile(
            name="expiry_sniper_v1",
            win_rate=0.933,
            avg_win=0.90,
            avg_loss=-11.39,
            daily_volume=78,
            n_bets=100,
        )
        self.assertEqual(p.name, "expiry_sniper_v1")
        self.assertAlmostEqual(p.win_rate, 0.933)

    def test_create_sports(self):
        p = StrategyProfile(
            name="sports_sniper",
            win_rate=0.0,  # no data yet (paper mode)
            avg_win=0.0,
            avg_loss=0.0,
            daily_volume=0,
            n_bets=0,
            is_paper=True,
        )
        self.assertTrue(p.is_paper)

    def test_expected_value(self):
        p = StrategyProfile(
            name="sniper", win_rate=0.933, avg_win=0.90,
            avg_loss=-11.39, daily_volume=78, n_bets=100,
        )
        ev = p.expected_value()
        expected = 0.933 * 0.90 + 0.067 * (-11.39)
        self.assertAlmostEqual(ev, expected, places=3)

    def test_daily_expected_pnl(self):
        p = StrategyProfile(
            name="sniper", win_rate=0.933, avg_win=0.90,
            avg_loss=-11.39, daily_volume=78, n_bets=100,
        )
        daily = p.daily_expected_pnl()
        self.assertAlmostEqual(daily, p.expected_value() * 78, places=1)

    def test_expected_value_zero_bets(self):
        p = StrategyProfile(
            name="empty", win_rate=0.0, avg_win=0.0,
            avg_loss=0.0, daily_volume=0, n_bets=0,
        )
        self.assertAlmostEqual(p.expected_value(), 0.0)

    def test_to_dict(self):
        p = StrategyProfile(
            name="sniper", win_rate=0.933, avg_win=0.90,
            avg_loss=-11.39, daily_volume=78, n_bets=100,
        )
        d = p.to_dict()
        self.assertEqual(d["name"], "sniper")
        self.assertIn("expected_value", d)

    def test_edge_ratio(self):
        """Edge ratio = EV / |avg_loss| — how efficient is each dollar risked."""
        p = StrategyProfile(
            name="sniper", win_rate=0.933, avg_win=0.90,
            avg_loss=-11.39, daily_volume=78, n_bets=100,
        )
        ratio = p.edge_ratio()
        self.assertGreater(ratio, 0)

    def test_variance(self):
        p = StrategyProfile(
            name="sniper", win_rate=0.933, avg_win=0.90,
            avg_loss=-11.39, daily_volume=78, n_bets=100,
        )
        v = p.variance()
        self.assertGreater(v, 0)


class TestAllocationConstraints(unittest.TestCase):
    """Test allocation constraints."""

    def test_default_constraints(self):
        c = AllocationConstraints()
        self.assertAlmostEqual(c.max_ruin_probability, 0.05)
        self.assertAlmostEqual(c.min_allocation, 0.0)
        self.assertAlmostEqual(c.max_allocation, 1.0)

    def test_custom_constraints(self):
        c = AllocationConstraints(
            max_ruin_probability=0.01,
            min_allocation=0.05,
            max_allocation=0.80,
            require_min_bets=20,
        )
        self.assertAlmostEqual(c.max_ruin_probability, 0.01)
        self.assertEqual(c.require_min_bets, 20)


class TestAllocationResult(unittest.TestCase):
    """Test AllocationResult dataclass."""

    def test_create(self):
        r = AllocationResult(
            allocations={"sniper": 0.70, "sports": 0.30},
            expected_daily_pnl=15.0,
            combined_ruin_probability=0.02,
            strategy_contributions={"sniper": 12.0, "sports": 3.0},
        )
        self.assertAlmostEqual(sum(r.allocations.values()), 1.0)
        self.assertAlmostEqual(r.expected_daily_pnl, 15.0)

    def test_summary(self):
        r = AllocationResult(
            allocations={"sniper": 0.70, "sports": 0.30},
            expected_daily_pnl=15.0,
            combined_ruin_probability=0.02,
            strategy_contributions={"sniper": 12.0, "sports": 3.0},
        )
        s = r.summary()
        self.assertIn("sniper", s)
        self.assertIn("70.0%", s)

    def test_to_dict(self):
        r = AllocationResult(
            allocations={"sniper": 1.0},
            expected_daily_pnl=6.0,
            combined_ruin_probability=0.045,
            strategy_contributions={"sniper": 6.0},
        )
        d = r.to_dict()
        self.assertIn("allocations", d)
        # Must be JSON serializable
        json.dumps(d)


class TestStrategyAllocator(unittest.TestCase):
    """Test the main allocator engine."""

    def setUp(self):
        self.sniper = StrategyProfile(
            name="expiry_sniper_v1",
            win_rate=0.933,
            avg_win=0.90,
            avg_loss=-11.39,
            daily_volume=78,
            n_bets=100,
        )
        self.sports = StrategyProfile(
            name="sports_sniper",
            win_rate=0.85,
            avg_win=1.20,
            avg_loss=-5.0,
            daily_volume=20,
            n_bets=30,
        )

    def test_create_allocator(self):
        alloc = StrategyAllocator([self.sniper])
        self.assertEqual(len(alloc.strategies), 1)

    def test_single_strategy_gets_100pct(self):
        """A single proven strategy should get 100% allocation."""
        alloc = StrategyAllocator([self.sniper])
        result = alloc.allocate(bankroll=178.05)
        self.assertAlmostEqual(result.allocations["expiry_sniper_v1"], 1.0)

    def test_two_strategies_allocation(self):
        """Two strategies should split based on edge quality."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        result = alloc.allocate(bankroll=178.05)
        total = sum(result.allocations.values())
        self.assertAlmostEqual(total, 1.0, places=2)
        # Both should get some allocation
        self.assertGreater(result.allocations["expiry_sniper_v1"], 0)
        self.assertGreater(result.allocations["sports_sniper"], 0)

    def test_paper_strategy_excluded_by_default(self):
        """Paper-mode strategies should get 0 allocation by default."""
        paper_sports = StrategyProfile(
            name="sports_sniper", win_rate=0.85, avg_win=1.20,
            avg_loss=-5.0, daily_volume=20, n_bets=5, is_paper=True,
        )
        alloc = StrategyAllocator([self.sniper, paper_sports])
        constraints = AllocationConstraints(require_min_bets=20)
        result = alloc.allocate(bankroll=178.05, constraints=constraints)
        self.assertAlmostEqual(result.allocations.get("sports_sniper", 0.0), 0.0)

    def test_kelly_based_allocation(self):
        """Verify allocation uses Kelly-inspired sizing."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        result = alloc.allocate(bankroll=178.05)
        # Strategy with better edge ratio should get higher allocation
        # (or at least positive)
        self.assertGreater(result.expected_daily_pnl, 0)

    def test_allocation_respects_max_constraint(self):
        """Max allocation constraint should be respected."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        constraints = AllocationConstraints(max_allocation=0.60)
        result = alloc.allocate(bankroll=178.05, constraints=constraints)
        for name, frac in result.allocations.items():
            self.assertLessEqual(frac, 0.60 + 0.001)

    def test_expected_daily_pnl_positive(self):
        """Combined expected P&L should be positive for positive-EV strategies."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        result = alloc.allocate(bankroll=178.05)
        self.assertGreater(result.expected_daily_pnl, 0)

    def test_contribution_sums_to_total(self):
        """Strategy contributions should sum to total expected P&L."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        result = alloc.allocate(bankroll=178.05)
        total_contrib = sum(result.strategy_contributions.values())
        self.assertAlmostEqual(total_contrib, result.expected_daily_pnl, places=1)

    def test_scenario_analysis(self):
        """Run multiple allocation scenarios at different bankrolls."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        scenarios = alloc.scenario_analysis(
            bankrolls=[100.0, 178.05, 300.0, 500.0],
        )
        self.assertEqual(len(scenarios), 4)
        for s in scenarios:
            self.assertIn("bankroll", s)
            self.assertIn("allocation", s)

    def test_marginal_value(self):
        """Adding a positive-EV strategy should still produce positive total P&L."""
        alloc_dual = StrategyAllocator([self.sniper, self.sports])
        result_dual = alloc_dual.allocate(bankroll=178.05)

        # Both strategies are positive EV, so combined P&L should be positive
        self.assertGreater(result_dual.expected_daily_pnl, 0)
        # Both should contribute positively
        for name, contrib in result_dual.strategy_contributions.items():
            if result_dual.allocations[name] > 0:
                self.assertGreater(contrib, 0)

    def test_full_report(self):
        """Generate complete allocation report."""
        alloc = StrategyAllocator([self.sniper, self.sports])
        report = alloc.full_report(bankroll=178.05)
        self.assertIn("optimal_allocation", report)
        self.assertIn("strategy_profiles", report)
        self.assertIn("scenarios", report)
        # JSON serializable
        json.dumps(report)

    def test_negative_ev_strategy_gets_zero(self):
        """A negative-EV strategy should get 0 allocation."""
        bad = StrategyProfile(
            name="losing_strategy", win_rate=0.50, avg_win=0.50,
            avg_loss=-5.0, daily_volume=10, n_bets=50,
        )
        alloc = StrategyAllocator([self.sniper, bad])
        result = alloc.allocate(bankroll=178.05)
        self.assertAlmostEqual(result.allocations.get("losing_strategy", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
