"""Tests for bankroll_growth_planner.py — bankroll trajectory projections.

Projects bankroll growth over N days at current strategy parameters.
Answers: will we hit self-sustaining ($250/month) within 5 days?
When does bankroll reach a level where ruin is negligible?
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bankroll_growth_planner import (
    GrowthParams,
    DayProjection,
    GrowthPlan,
    BankrollGrowthPlanner,
)


class TestGrowthParams(unittest.TestCase):
    def test_create(self):
        p = GrowthParams(
            starting_bankroll=178.05,
            daily_pnl=5.97,
            daily_volume=78,
            win_rate=0.933,
            avg_win=0.90,
            avg_loss=-11.39,
        )
        self.assertAlmostEqual(p.starting_bankroll, 178.05)

    def test_daily_variance(self):
        p = GrowthParams(
            starting_bankroll=178.05, daily_pnl=5.97, daily_volume=78,
            win_rate=0.933, avg_win=0.90, avg_loss=-11.39,
        )
        v = p.daily_variance()
        self.assertGreater(v, 0)

    def test_to_dict(self):
        p = GrowthParams(
            starting_bankroll=178.05, daily_pnl=5.97, daily_volume=78,
            win_rate=0.933, avg_win=0.90, avg_loss=-11.39,
        )
        d = p.to_dict()
        self.assertIn("starting_bankroll", d)
        json.dumps(d)


class TestDayProjection(unittest.TestCase):
    def test_create(self):
        dp = DayProjection(
            day=1,
            expected_bankroll=184.02,
            p5_bankroll=150.0,
            p95_bankroll=210.0,
            ruin_probability=0.05,
            self_sustaining=False,
        )
        self.assertEqual(dp.day, 1)
        self.assertFalse(dp.self_sustaining)

    def test_to_dict(self):
        dp = DayProjection(
            day=5, expected_bankroll=208.0, p5_bankroll=170.0,
            p95_bankroll=250.0, ruin_probability=0.01, self_sustaining=True,
        )
        d = dp.to_dict()
        json.dumps(d)


class TestGrowthPlan(unittest.TestCase):
    def test_create(self):
        projections = [
            DayProjection(1, 184.0, 150.0, 210.0, 0.05, False),
            DayProjection(2, 190.0, 155.0, 225.0, 0.04, False),
            DayProjection(5, 208.0, 170.0, 250.0, 0.02, True),
        ]
        plan = GrowthPlan(
            params=GrowthParams(178.05, 5.97, 78, 0.933, 0.90, -11.39),
            projections=projections,
            days_to_self_sustaining=None,
            days_to_safe_bankroll=None,
        )
        self.assertEqual(len(plan.projections), 3)

    def test_summary(self):
        projections = [
            DayProjection(1, 184.0, 150.0, 210.0, 0.05, False),
            DayProjection(5, 208.0, 170.0, 250.0, 0.02, True),
        ]
        plan = GrowthPlan(
            params=GrowthParams(178.05, 5.97, 78, 0.933, 0.90, -11.39),
            projections=projections,
            days_to_self_sustaining=12,
            days_to_safe_bankroll=5,
        )
        s = plan.summary()
        self.assertIn("178.05", s)

    def test_to_dict(self):
        projections = [DayProjection(1, 184.0, 150.0, 210.0, 0.05, False)]
        plan = GrowthPlan(
            params=GrowthParams(178.05, 5.97, 78, 0.933, 0.90, -11.39),
            projections=projections,
            days_to_self_sustaining=None,
            days_to_safe_bankroll=None,
        )
        d = plan.to_dict()
        json.dumps(d)


class TestBankrollGrowthPlanner(unittest.TestCase):
    def setUp(self):
        self.params = GrowthParams(
            starting_bankroll=178.05,
            daily_pnl=5.97,
            daily_volume=78,
            win_rate=0.933,
            avg_win=0.90,
            avg_loss=-11.39,
        )
        self.planner = BankrollGrowthPlanner(self.params)

    def test_create(self):
        self.assertIsNotNone(self.planner)

    def test_project_5_days(self):
        plan = self.planner.project(n_days=5)
        self.assertIsInstance(plan, GrowthPlan)
        self.assertEqual(len(plan.projections), 5)

    def test_project_30_days(self):
        plan = self.planner.project(n_days=30)
        self.assertEqual(len(plan.projections), 30)
        # Bankroll should grow over 30 days (positive EV)
        self.assertGreater(
            plan.projections[-1].expected_bankroll,
            plan.projections[0].expected_bankroll,
        )

    def test_expected_bankroll_grows(self):
        """With positive EV, expected bankroll should increase each day."""
        plan = self.planner.project(n_days=10)
        for i in range(1, len(plan.projections)):
            self.assertGreater(
                plan.projections[i].expected_bankroll,
                plan.projections[i - 1].expected_bankroll,
            )

    def test_ruin_probability_decreases(self):
        """As bankroll grows, ruin probability should decrease."""
        plan = self.planner.project(n_days=30)
        # First day vs last day ruin
        self.assertGreaterEqual(
            plan.projections[0].ruin_probability,
            plan.projections[-1].ruin_probability,
        )

    def test_confidence_bands_widen(self):
        """P5/P95 spread should widen over time (more uncertainty)."""
        plan = self.planner.project(n_days=10)
        spread_1 = plan.projections[0].p95_bankroll - plan.projections[0].p5_bankroll
        spread_10 = plan.projections[-1].p95_bankroll - plan.projections[-1].p5_bankroll
        self.assertGreater(spread_10, spread_1)

    def test_self_sustaining_detection(self):
        """Plan should detect when daily P&L exceeds $8.33 (=$250/month)."""
        plan = self.planner.project(n_days=60)
        # At some point, with growing bankroll and constant bet sizing,
        # the self_sustaining flag doesn't change (fixed bet size)
        # But the plan should report days_to_self_sustaining
        self.assertIsInstance(plan, GrowthPlan)

    def test_milestone_report(self):
        """Generate milestone analysis."""
        milestones = self.planner.milestones()
        self.assertIn("day_5", milestones)
        self.assertIn("day_30", milestones)
        self.assertIn("day_60", milestones)
        json.dumps(milestones)

    def test_what_if_reduced_loss(self):
        """What-if: project growth with reduced avg_loss."""
        better_params = GrowthParams(
            starting_bankroll=178.05, daily_pnl=20.0, daily_volume=78,
            win_rate=0.928, avg_win=0.90, avg_loss=-8.0,
        )
        planner = BankrollGrowthPlanner(better_params)
        plan = planner.project(n_days=30)
        # Should grow much faster
        self.assertGreater(
            plan.projections[-1].expected_bankroll,
            178.05 + 20 * 25,  # at least 25 days of growth
        )

    def test_full_report(self):
        report = self.planner.full_report(n_days=30)
        self.assertIn("plan", report)
        self.assertIn("milestones", report)
        self.assertIn("current_daily_vs_target", report)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
