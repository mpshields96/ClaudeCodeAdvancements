#!/usr/bin/env python3
"""Tests for dca_advisor.py — MT-37: Dollar-cost averaging for small recurring investments."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dca_advisor import (
    DCAAllocation,
    DCAConfig,
    DCAFrequency,
    DCAReport,
    allocate_deposit,
    annual_projection,
    rebalance_on_deposit,
)


class TestAllocateDeposit(unittest.TestCase):
    """Test splitting a deposit across target weights."""

    def test_simple_allocation(self):
        targets = {"VTI": 0.60, "VXUS": 0.25, "BND": 0.15}
        result = allocate_deposit(20.0, targets)
        self.assertAlmostEqual(result["VTI"], 12.0)
        self.assertAlmostEqual(result["VXUS"], 5.0)
        self.assertAlmostEqual(result["BND"], 3.0)

    def test_allocation_sums_to_deposit(self):
        targets = {"A": 0.50, "B": 0.30, "C": 0.20}
        result = allocate_deposit(50.0, targets)
        total = sum(result.values())
        self.assertAlmostEqual(total, 50.0, places=2)

    def test_zero_deposit(self):
        result = allocate_deposit(0.0, {"VTI": 1.0})
        self.assertAlmostEqual(result["VTI"], 0.0)

    def test_single_asset(self):
        result = allocate_deposit(100.0, {"VTI": 1.0})
        self.assertAlmostEqual(result["VTI"], 100.0)


class TestRebalanceOnDeposit(unittest.TestCase):
    """Test deposit-time rebalancing (tilt deposit toward underweight assets)."""

    def test_tilt_toward_underweight(self):
        current_values = {"VTI": 700.0, "VXUS": 200.0, "BND": 100.0}
        target_weights = {"VTI": 0.60, "VXUS": 0.25, "BND": 0.15}
        deposit = 20.0
        result = rebalance_on_deposit(current_values, target_weights, deposit)
        # VXUS is most underweight (20% vs 25% target), should get more
        # VTI is overweight (70% vs 60%), should get less
        self.assertGreater(result["VXUS"], result["VTI"])

    def test_result_sums_to_deposit(self):
        current_values = {"A": 500.0, "B": 300.0, "C": 200.0}
        targets = {"A": 0.40, "B": 0.35, "C": 0.25}
        result = rebalance_on_deposit(current_values, targets, 50.0)
        total = sum(result.values())
        self.assertAlmostEqual(total, 50.0, places=2)

    def test_empty_portfolio_uses_target_weights(self):
        result = rebalance_on_deposit({}, {"VTI": 0.60, "BND": 0.40}, 20.0)
        self.assertAlmostEqual(result["VTI"], 12.0)
        self.assertAlmostEqual(result["BND"], 8.0)

    def test_no_negative_allocations(self):
        # VTI massively overweight
        current_values = {"VTI": 9000.0, "BND": 1000.0}
        targets = {"VTI": 0.50, "BND": 0.50}
        result = rebalance_on_deposit(current_values, targets, 20.0)
        for v in result.values():
            self.assertGreaterEqual(v, 0.0)


class TestAnnualProjection(unittest.TestCase):
    """Test annual investment projection."""

    def test_weekly_20(self):
        proj = annual_projection(
            deposit_amount=20.0,
            frequency=DCAFrequency.WEEKLY,
            annual_return=0.08,
        )
        # 52 deposits of $20 = $1040 contributed
        self.assertAlmostEqual(proj.total_contributed, 1040.0, places=0)
        # With 8% return, should be slightly more than contributed
        self.assertGreater(proj.projected_value, proj.total_contributed)

    def test_monthly_50(self):
        proj = annual_projection(
            deposit_amount=50.0,
            frequency=DCAFrequency.MONTHLY,
            annual_return=0.08,
        )
        self.assertAlmostEqual(proj.total_contributed, 600.0, places=0)
        self.assertGreater(proj.projected_value, proj.total_contributed)

    def test_multi_year(self):
        proj = annual_projection(
            deposit_amount=20.0,
            frequency=DCAFrequency.WEEKLY,
            annual_return=0.08,
            years=10,
        )
        self.assertAlmostEqual(proj.total_contributed, 10400.0, places=0)
        # 10 years at 8% with weekly $20 should compound significantly
        self.assertGreater(proj.projected_value, 14000.0)

    def test_zero_return(self):
        proj = annual_projection(
            deposit_amount=50.0,
            frequency=DCAFrequency.MONTHLY,
            annual_return=0.0,
            years=5,
        )
        self.assertAlmostEqual(proj.projected_value, proj.total_contributed, places=2)


class TestDCAConfig(unittest.TestCase):
    """Test DCA configuration."""

    def test_defaults(self):
        cfg = DCAConfig()
        self.assertEqual(cfg.deposit_amount, 20.0)
        self.assertEqual(cfg.frequency, DCAFrequency.WEEKLY)

    def test_custom(self):
        cfg = DCAConfig(deposit_amount=50.0, frequency=DCAFrequency.MONTHLY)
        self.assertEqual(cfg.deposit_amount, 50.0)
        self.assertEqual(cfg.frequency, DCAFrequency.MONTHLY)

    def test_deposits_per_year(self):
        weekly = DCAConfig(frequency=DCAFrequency.WEEKLY)
        monthly = DCAConfig(frequency=DCAFrequency.MONTHLY)
        self.assertEqual(weekly.deposits_per_year, 52)
        self.assertEqual(monthly.deposits_per_year, 12)


class TestDCAReport(unittest.TestCase):
    """Test DCA report generation."""

    def test_report_to_dict(self):
        report = DCAReport(
            allocation={"VTI": 12.0, "BND": 8.0},
            deposit_amount=20.0,
            frequency=DCAFrequency.WEEKLY,
            rebalance_tilt=True,
        )
        d = report.to_dict()
        self.assertIn("allocation", d)
        self.assertIn("deposit_amount", d)
        self.assertIn("frequency", d)

    def test_report_summary_text(self):
        report = DCAReport(
            allocation={"VTI": 12.0, "VXUS": 5.0, "BND": 3.0},
            deposit_amount=20.0,
            frequency=DCAFrequency.WEEKLY,
        )
        text = report.summary_text()
        self.assertIn("VTI", text)
        self.assertIn("$12.00", text)
        self.assertIn("$20.00", text)

    def test_app_recommendations(self):
        report = DCAReport(
            allocation={"VTI": 12.0},
            deposit_amount=20.0,
            frequency=DCAFrequency.WEEKLY,
        )
        apps = report.recommended_apps()
        self.assertIsInstance(apps, list)
        self.assertGreater(len(apps), 0)
        # Should include M1 Finance for small DCA
        app_names = [a["name"] for a in apps]
        self.assertIn("M1 Finance", app_names)


if __name__ == "__main__":
    unittest.main()
