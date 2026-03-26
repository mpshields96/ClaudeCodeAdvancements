#!/usr/bin/env python3
"""Tests for tax_harvester.py — MT-37 Phase 3 Layer 4: Tax-loss harvesting.

Identifies TLH candidates, tracks wash sale windows, and computes
tax savings estimates. Based on Constantinides 1983, Berkin & Ye 2003.
"""
import os
import sys
import unittest
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from tax_harvester import (
    TLHCandidate,
    WashSaleTracker,
    TaxHarvester,
    compute_tax_savings,
)


class TestComputeTaxSavings(unittest.TestCase):
    """Test tax savings computation."""

    def test_short_term_loss(self):
        # $1000 short-term loss at 37% marginal rate
        savings = compute_tax_savings(loss=1000, marginal_rate=0.37, is_long_term=False)
        self.assertAlmostEqual(savings, 370.0)

    def test_long_term_loss(self):
        # $1000 long-term loss at 20% LTCG rate
        savings = compute_tax_savings(loss=1000, marginal_rate=0.20, is_long_term=True)
        self.assertAlmostEqual(savings, 200.0)

    def test_zero_loss(self):
        savings = compute_tax_savings(loss=0, marginal_rate=0.37, is_long_term=False)
        self.assertAlmostEqual(savings, 0.0)

    def test_negative_loss_treated_as_zero(self):
        # A "gain" is not a TLH opportunity
        savings = compute_tax_savings(loss=-500, marginal_rate=0.37, is_long_term=False)
        self.assertAlmostEqual(savings, 0.0)


class TestTLHCandidate(unittest.TestCase):
    """Test TLH candidate identification."""

    def test_from_holding(self):
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=150.0,
            current_price=130.0,
            purchase_date=date(2025, 6, 1),
        )
        self.assertAlmostEqual(candidate.unrealized_loss, 2000.0)  # 100 * (150-130)
        self.assertTrue(candidate.is_harvestable)

    def test_no_loss_not_harvestable(self):
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=130.0,
            current_price=150.0,
            purchase_date=date(2025, 6, 1),
        )
        self.assertAlmostEqual(candidate.unrealized_loss, 0.0)
        self.assertFalse(candidate.is_harvestable)

    def test_is_long_term(self):
        # Held > 1 year
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=150.0,
            current_price=130.0,
            purchase_date=date(2024, 1, 1),
            as_of_date=date(2026, 3, 26),
        )
        self.assertTrue(candidate.is_long_term)

    def test_is_short_term(self):
        # Held < 1 year
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=150.0,
            current_price=130.0,
            purchase_date=date(2026, 1, 1),
            as_of_date=date(2026, 3, 26),
        )
        self.assertFalse(candidate.is_long_term)

    def test_tax_savings_estimate(self):
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=150.0,
            current_price=130.0,
            purchase_date=date(2026, 1, 1),
        )
        savings = candidate.estimated_savings(marginal_rate=0.37)
        # $2000 loss * 37% = $740
        self.assertAlmostEqual(savings, 740.0)

    def test_to_dict(self):
        candidate = TLHCandidate(
            ticker="VTI",
            shares=100,
            cost_basis=150.0,
            current_price=130.0,
            purchase_date=date(2025, 6, 1),
        )
        d = candidate.to_dict()
        self.assertEqual(d["ticker"], "VTI")
        self.assertIn("unrealized_loss", d)
        self.assertIn("is_harvestable", d)


class TestWashSaleTracker(unittest.TestCase):
    """Test 30-day wash sale window tracking."""

    def test_no_wash_sale_outside_window(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 1))
        # 31+ days later = no wash sale
        self.assertFalse(tracker.is_in_wash_window("VTI", date(2026, 2, 2)))

    def test_wash_sale_within_window(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 15))
        # 20 days later = within 30-day window
        self.assertTrue(tracker.is_in_wash_window("VTI", date(2026, 2, 4)))

    def test_wash_sale_exactly_30_days(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 1))
        # Exactly 30 days = still in window
        self.assertTrue(tracker.is_in_wash_window("VTI", date(2026, 1, 31)))

    def test_different_tickers_independent(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 15))
        # BND was never sold
        self.assertFalse(tracker.is_in_wash_window("BND", date(2026, 1, 20)))

    def test_days_remaining(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 1))
        remaining = tracker.days_remaining("VTI", date(2026, 1, 20))
        self.assertEqual(remaining, 11)  # 30 - 19 = 11

    def test_days_remaining_outside_window(self):
        tracker = WashSaleTracker()
        tracker.record_sale("VTI", date(2026, 1, 1))
        remaining = tracker.days_remaining("VTI", date(2026, 3, 1))
        self.assertEqual(remaining, 0)

    def test_no_sale_recorded(self):
        tracker = WashSaleTracker()
        self.assertFalse(tracker.is_in_wash_window("VTI", date(2026, 1, 1)))
        self.assertEqual(tracker.days_remaining("VTI", date(2026, 1, 1)), 0)


class TestTaxHarvester(unittest.TestCase):
    """Test the main tax harvester that scans portfolios."""

    def test_find_candidates_with_losses(self):
        holdings = [
            {"ticker": "VTI", "shares": 100, "cost_basis": 150.0,
             "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
            {"ticker": "BND", "shares": 200, "cost_basis": 80.0,
             "current_price": 85.0, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester()
        candidates = harvester.scan(holdings)
        # Only VTI has a loss
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].ticker, "VTI")

    def test_no_candidates_when_all_gains(self):
        holdings = [
            {"ticker": "VTI", "shares": 100, "cost_basis": 100.0,
             "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester()
        candidates = harvester.scan(holdings)
        self.assertEqual(len(candidates), 0)

    def test_respects_wash_sale_window(self):
        holdings = [
            {"ticker": "VTI", "shares": 100, "cost_basis": 150.0,
             "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester()
        harvester.wash_tracker.record_sale("VTI", date(2026, 3, 20))
        candidates = harvester.scan(holdings, as_of=date(2026, 3, 26))
        # VTI in wash window — should be flagged
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].in_wash_window)

    def test_minimum_loss_threshold(self):
        holdings = [
            {"ticker": "VTI", "shares": 1, "cost_basis": 100.0,
             "current_price": 99.50, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester(min_loss=10.0)
        candidates = harvester.scan(holdings)
        # $0.50 loss < $10 threshold
        self.assertEqual(len(candidates), 0)

    def test_total_harvestable_loss(self):
        holdings = [
            {"ticker": "VTI", "shares": 100, "cost_basis": 150.0,
             "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
            {"ticker": "VXUS", "shares": 50, "cost_basis": 60.0,
             "current_price": 50.0, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester()
        candidates = harvester.scan(holdings)
        total = sum(c.unrealized_loss for c in candidates)
        # VTI: 100*(150-130) = 2000, VXUS: 50*(60-50) = 500
        self.assertAlmostEqual(total, 2500.0)

    def test_summary_report(self):
        holdings = [
            {"ticker": "VTI", "shares": 100, "cost_basis": 150.0,
             "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
        ]
        harvester = TaxHarvester()
        candidates = harvester.scan(holdings)
        report = harvester.summary(candidates, marginal_rate=0.37)
        self.assertIn("total_harvestable_loss", report)
        self.assertIn("estimated_tax_savings", report)
        self.assertIn("candidates", report)


if __name__ == "__main__":
    unittest.main()
