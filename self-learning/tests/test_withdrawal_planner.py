#!/usr/bin/env python3
"""Tests for withdrawal_planner.py — MT-37 Phase 3 Layer 4: Withdrawal planning.

Safe withdrawal rate with CAPE-adjusted guardrails and Guyton-Klinger rules.
Based on Bengen 1994, Kitces 2008, Guyton-Klinger 2006.
"""
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from withdrawal_planner import (
    base_withdrawal_rate,
    cape_adjusted_rate,
    guyton_klinger_check,
    WithdrawalPlan,
    WithdrawalAction,
    plan_withdrawal,
)


class TestBaseWithdrawalRate(unittest.TestCase):
    """Test Bengen's 4% rule baseline."""

    def test_standard_30_year(self):
        rate = base_withdrawal_rate(horizon_years=30)
        self.assertAlmostEqual(rate, 0.04, places=2)

    def test_longer_horizon_lower_rate(self):
        rate30 = base_withdrawal_rate(horizon_years=30)
        rate40 = base_withdrawal_rate(horizon_years=40)
        self.assertLess(rate40, rate30)

    def test_shorter_horizon_higher_rate(self):
        rate30 = base_withdrawal_rate(horizon_years=30)
        rate20 = base_withdrawal_rate(horizon_years=20)
        self.assertGreater(rate20, rate30)

    def test_minimum_floor(self):
        rate = base_withdrawal_rate(horizon_years=50)
        self.assertGreater(rate, 0.02)  # Should never go below 2%

    def test_maximum_cap(self):
        rate = base_withdrawal_rate(horizon_years=10)
        self.assertLess(rate, 0.10)  # Should never exceed 10%


class TestCapeAdjustedRate(unittest.TestCase):
    """Test CAPE-adjusted withdrawal rate (Kitces 2008)."""

    def test_high_cape_lowers_rate(self):
        # High CAPE (expensive market) → lower SWR
        normal = cape_adjusted_rate(base_rate=0.04, cape_ratio=20)
        high = cape_adjusted_rate(base_rate=0.04, cape_ratio=35)
        self.assertLess(high, normal)

    def test_low_cape_raises_rate(self):
        # Low CAPE (cheap market) → higher SWR
        normal = cape_adjusted_rate(base_rate=0.04, cape_ratio=20)
        low = cape_adjusted_rate(base_rate=0.04, cape_ratio=12)
        self.assertGreater(low, normal)

    def test_median_cape_near_base(self):
        # Historical median CAPE ~16-17 → rate near base
        rate = cape_adjusted_rate(base_rate=0.04, cape_ratio=16)
        self.assertAlmostEqual(rate, 0.04, places=2)

    def test_never_negative(self):
        rate = cape_adjusted_rate(base_rate=0.04, cape_ratio=100)
        self.assertGreater(rate, 0)

    def test_capped_above(self):
        rate = cape_adjusted_rate(base_rate=0.04, cape_ratio=5)
        self.assertLess(rate, 0.08)  # Shouldn't recommend >8% even in cheap market


class TestGuytonKlingerCheck(unittest.TestCase):
    """Test Guyton-Klinger guardrail rules."""

    def test_normal_withdrawal_no_change(self):
        action = guyton_klinger_check(
            planned_withdrawal=40000,
            portfolio_value=1000000,
            initial_rate=0.04,
        )
        self.assertEqual(action, WithdrawalAction.MAINTAIN)

    def test_high_rate_triggers_cut(self):
        # Withdrawal rate > 120% of initial → cut
        action = guyton_klinger_check(
            planned_withdrawal=60000,  # 6% of 1M vs 4% initial
            portfolio_value=1000000,
            initial_rate=0.04,
        )
        self.assertEqual(action, WithdrawalAction.CUT)

    def test_low_rate_triggers_raise(self):
        # Withdrawal rate < 80% of initial → can raise
        action = guyton_klinger_check(
            planned_withdrawal=25000,  # 2.5% of 1M vs 4% initial
            portfolio_value=1000000,
            initial_rate=0.04,
        )
        self.assertEqual(action, WithdrawalAction.RAISE)

    def test_borderline_maintains(self):
        # Exactly at initial rate
        action = guyton_klinger_check(
            planned_withdrawal=40000,
            portfolio_value=1000000,
            initial_rate=0.04,
        )
        self.assertEqual(action, WithdrawalAction.MAINTAIN)


class TestPlanWithdrawal(unittest.TestCase):
    """Test full withdrawal planning."""

    def test_basic_plan(self):
        plan = plan_withdrawal(
            portfolio_value=1000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
        )
        self.assertIsInstance(plan, WithdrawalPlan)
        self.assertGreater(plan.safe_rate, 0)
        self.assertGreater(plan.annual_amount, 0)

    def test_cape_adjustment_applied(self):
        plan_normal = plan_withdrawal(
            portfolio_value=1000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
            cape_ratio=16,
        )
        plan_expensive = plan_withdrawal(
            portfolio_value=1000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
            cape_ratio=35,
        )
        self.assertLess(plan_expensive.safe_rate, plan_normal.safe_rate)

    def test_sustainability_check(self):
        # Expenses way above safe rate → unsustainable
        plan = plan_withdrawal(
            portfolio_value=500000,
            annual_expenses=80000,
            current_age=65,
            horizon_years=30,
        )
        self.assertFalse(plan.is_sustainable)

    def test_sustainable_plan(self):
        plan = plan_withdrawal(
            portfolio_value=2000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
        )
        self.assertTrue(plan.is_sustainable)

    def test_to_dict(self):
        plan = plan_withdrawal(
            portfolio_value=1000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
        )
        d = plan.to_dict()
        self.assertIn("safe_rate", d)
        self.assertIn("annual_amount", d)
        self.assertIn("is_sustainable", d)
        self.assertIn("guardrail_action", d)

    def test_summary_text(self):
        plan = plan_withdrawal(
            portfolio_value=1000000,
            annual_expenses=40000,
            current_age=65,
            horizon_years=30,
        )
        text = plan.summary_text()
        self.assertIn("$", text)
        self.assertIn("%", text)


if __name__ == "__main__":
    unittest.main()
