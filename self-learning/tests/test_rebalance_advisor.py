#!/usr/bin/env python3
"""Tests for rebalance_advisor.py — MT-37 Layer 5: Rebalancing recommendations."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rebalance_advisor import (
    DriftResult,
    RebalanceAction,
    RebalanceAdvisor,
    RebalanceRecommendation,
    RebalanceTrigger,
    calendar_trigger,
    drift_analysis,
    threshold_trigger,
)


class TestDriftAnalysis(unittest.TestCase):
    """Test portfolio drift calculations."""

    def test_no_drift_when_aligned(self):
        current = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
        target = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
        result = drift_analysis(current, target)
        self.assertEqual(result.max_drift, 0.0)
        self.assertEqual(result.total_drift, 0.0)

    def test_drift_computed_correctly(self):
        current = {"VTI": 0.70, "VXUS": 0.20, "BND": 0.10}
        target = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
        result = drift_analysis(current, target)
        self.assertAlmostEqual(result.drifts["VTI"], 0.10)
        self.assertAlmostEqual(result.drifts["VXUS"], -0.10)
        self.assertAlmostEqual(result.drifts["BND"], 0.0)
        self.assertAlmostEqual(result.max_drift, 0.10)

    def test_total_drift_sum_of_abs(self):
        current = {"A": 0.50, "B": 0.30, "C": 0.20}
        target = {"A": 0.40, "B": 0.40, "C": 0.20}
        result = drift_analysis(current, target)
        self.assertAlmostEqual(result.total_drift, 0.20)

    def test_missing_ticker_in_current_treated_as_zero(self):
        current = {"VTI": 1.0}
        target = {"VTI": 0.60, "BND": 0.40}
        result = drift_analysis(current, target)
        self.assertAlmostEqual(result.drifts["VTI"], 0.40)
        self.assertAlmostEqual(result.drifts["BND"], -0.40)

    def test_missing_ticker_in_target_treated_as_zero(self):
        current = {"VTI": 0.60, "ARKK": 0.40}
        target = {"VTI": 0.60}
        result = drift_analysis(current, target)
        self.assertAlmostEqual(result.drifts["ARKK"], 0.40)

    def test_to_dict(self):
        current = {"A": 0.55, "B": 0.45}
        target = {"A": 0.50, "B": 0.50}
        result = drift_analysis(current, target)
        d = result.to_dict()
        self.assertIn("drifts", d)
        self.assertIn("max_drift", d)
        self.assertIn("total_drift", d)


class TestThresholdTrigger(unittest.TestCase):
    """Test threshold-based rebalancing trigger."""

    def test_no_trigger_below_threshold(self):
        current = {"A": 0.52, "B": 0.48}
        target = {"A": 0.50, "B": 0.50}
        self.assertFalse(threshold_trigger(current, target, threshold=0.05))

    def test_trigger_at_threshold(self):
        current = {"A": 0.55, "B": 0.45}
        target = {"A": 0.50, "B": 0.50}
        self.assertTrue(threshold_trigger(current, target, threshold=0.05))

    def test_trigger_above_threshold(self):
        current = {"A": 0.60, "B": 0.40}
        target = {"A": 0.50, "B": 0.50}
        self.assertTrue(threshold_trigger(current, target, threshold=0.05))

    def test_custom_threshold(self):
        current = {"A": 0.53, "B": 0.47}
        target = {"A": 0.50, "B": 0.50}
        self.assertFalse(threshold_trigger(current, target, threshold=0.05))
        self.assertTrue(threshold_trigger(current, target, threshold=0.03))


class TestCalendarTrigger(unittest.TestCase):
    """Test calendar-based rebalancing trigger."""

    def test_trigger_when_overdue(self):
        self.assertTrue(calendar_trigger(days_since_last=95, interval_days=90))

    def test_no_trigger_when_recent(self):
        self.assertFalse(calendar_trigger(days_since_last=30, interval_days=90))

    def test_trigger_exactly_at_interval(self):
        self.assertTrue(calendar_trigger(days_since_last=90, interval_days=90))

    def test_custom_interval(self):
        self.assertTrue(calendar_trigger(days_since_last=185, interval_days=180))
        self.assertFalse(calendar_trigger(days_since_last=170, interval_days=180))


class TestRebalanceAdvisor(unittest.TestCase):
    """Test the full rebalancing advisor."""

    def setUp(self):
        self.advisor = RebalanceAdvisor(
            drift_threshold=0.05,
            calendar_interval_days=90,
        )
        self.current = {"VTI": 0.70, "VXUS": 0.20, "BND": 0.10}
        self.target = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}

    def test_recommends_rebalance_on_drift(self):
        rec = self.advisor.analyze(self.current, self.target, days_since_last=10)
        self.assertTrue(rec.should_rebalance)
        self.assertIn(RebalanceTrigger.THRESHOLD, rec.triggers)

    def test_recommends_rebalance_on_calendar(self):
        current = {"VTI": 0.61, "VXUS": 0.29, "BND": 0.10}
        target = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
        rec = self.advisor.analyze(current, target, days_since_last=100)
        self.assertTrue(rec.should_rebalance)
        self.assertIn(RebalanceTrigger.CALENDAR, rec.triggers)

    def test_no_rebalance_when_aligned_and_recent(self):
        current = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
        rec = self.advisor.analyze(current, self.target, days_since_last=10)
        self.assertFalse(rec.should_rebalance)

    def test_actions_generated(self):
        rec = self.advisor.analyze(self.current, self.target, days_since_last=10)
        actions = rec.actions
        self.assertTrue(len(actions) > 0)
        # VTI should be SELL (overweight)
        vti_action = [a for a in actions if a.ticker == "VTI"][0]
        self.assertEqual(vti_action.direction, "SELL")
        self.assertAlmostEqual(vti_action.amount_pct, 0.10)
        # VXUS should be BUY (underweight)
        vxus_action = [a for a in actions if a.ticker == "VXUS"][0]
        self.assertEqual(vxus_action.direction, "BUY")
        self.assertAlmostEqual(vxus_action.amount_pct, 0.10)

    def test_actions_skip_zero_drift(self):
        rec = self.advisor.analyze(self.current, self.target, days_since_last=10)
        actions = rec.actions
        tickers = [a.ticker for a in actions]
        # BND has zero drift, should not appear
        self.assertNotIn("BND", tickers)

    def test_bankroll_dollar_amounts(self):
        rec = self.advisor.analyze(
            self.current, self.target, days_since_last=10, bankroll=100000
        )
        vti_action = [a for a in rec.actions if a.ticker == "VTI"][0]
        self.assertAlmostEqual(vti_action.dollar_amount, 10000.0)

    def test_to_dict(self):
        rec = self.advisor.analyze(self.current, self.target, days_since_last=10)
        d = rec.to_dict()
        self.assertIn("should_rebalance", d)
        self.assertIn("triggers", d)
        self.assertIn("actions", d)
        self.assertIn("drift", d)

    def test_summary_text(self):
        rec = self.advisor.analyze(
            self.current, self.target, days_since_last=10, bankroll=100000
        )
        text = rec.summary_text()
        self.assertIn("VTI", text)
        self.assertIn("SELL", text)

    def test_both_triggers(self):
        rec = self.advisor.analyze(self.current, self.target, days_since_last=100)
        self.assertIn(RebalanceTrigger.THRESHOLD, rec.triggers)
        self.assertIn(RebalanceTrigger.CALENDAR, rec.triggers)


if __name__ == "__main__":
    unittest.main()
