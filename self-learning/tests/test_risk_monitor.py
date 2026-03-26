#!/usr/bin/env python3
"""Tests for risk_monitor.py — MT-37 Phase 3 Layer 3: Portfolio risk monitoring.

Drawdown tracking, volatility alerts, and regime-based risk signals.
Based on Ang 2014 (regime switching), Moskowitz et al. 2012 (TSMOM).
"""
import os
import sys
import unittest
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from risk_monitor import (
    DrawdownTracker,
    VolatilityMonitor,
    RiskDashboard,
    RiskLevel,
)


class TestDrawdownTracker(unittest.TestCase):
    """Test max drawdown computation and tracking."""

    def test_no_drawdown_in_uptrend(self):
        tracker = DrawdownTracker()
        values = [100, 110, 120, 130, 140]
        for v in values:
            tracker.update(v)
        self.assertAlmostEqual(tracker.current_drawdown, 0.0)
        self.assertAlmostEqual(tracker.max_drawdown, 0.0)

    def test_simple_drawdown(self):
        tracker = DrawdownTracker()
        for v in [100, 110, 100]:
            tracker.update(v)
        # From peak 110 to 100 = 9.09% drawdown
        self.assertAlmostEqual(tracker.current_drawdown, 10 / 110, places=4)

    def test_max_drawdown_persists(self):
        tracker = DrawdownTracker()
        for v in [100, 120, 90, 110]:
            tracker.update(v)
        # Max drawdown: 120 → 90 = 25%
        self.assertAlmostEqual(tracker.max_drawdown, 30 / 120, places=4)
        # Current drawdown: 120 → 110 = 8.33%
        self.assertAlmostEqual(tracker.current_drawdown, 10 / 120, places=4)

    def test_new_high_resets_current(self):
        tracker = DrawdownTracker()
        for v in [100, 90, 110]:
            tracker.update(v)
        self.assertAlmostEqual(tracker.current_drawdown, 0.0)

    def test_peak_tracks_correctly(self):
        tracker = DrawdownTracker()
        for v in [100, 150, 120]:
            tracker.update(v)
        self.assertEqual(tracker.peak, 150)

    def test_risk_level_green(self):
        tracker = DrawdownTracker()
        for v in [100, 99]:
            tracker.update(v)
        self.assertEqual(tracker.risk_level, RiskLevel.GREEN)

    def test_risk_level_yellow(self):
        tracker = DrawdownTracker()
        for v in [100, 90]:
            tracker.update(v)
        # 10% drawdown → YELLOW
        self.assertEqual(tracker.risk_level, RiskLevel.YELLOW)

    def test_risk_level_red(self):
        tracker = DrawdownTracker()
        for v in [100, 80]:
            tracker.update(v)
        # 20% drawdown → RED
        self.assertEqual(tracker.risk_level, RiskLevel.RED)

    def test_risk_level_critical(self):
        tracker = DrawdownTracker()
        for v in [100, 60]:
            tracker.update(v)
        # 40% drawdown → CRITICAL
        self.assertEqual(tracker.risk_level, RiskLevel.CRITICAL)

    def test_empty_tracker(self):
        tracker = DrawdownTracker()
        self.assertAlmostEqual(tracker.current_drawdown, 0.0)
        self.assertAlmostEqual(tracker.max_drawdown, 0.0)
        self.assertEqual(tracker.risk_level, RiskLevel.GREEN)

    def test_to_dict(self):
        tracker = DrawdownTracker()
        for v in [100, 120, 100]:
            tracker.update(v)
        d = tracker.to_dict()
        self.assertIn("current_drawdown", d)
        self.assertIn("max_drawdown", d)
        self.assertIn("peak", d)
        self.assertIn("risk_level", d)


class TestVolatilityMonitor(unittest.TestCase):
    """Test rolling volatility computation."""

    def test_constant_returns_zero_vol(self):
        mon = VolatilityMonitor(window=5)
        for v in [100, 100, 100, 100, 100]:
            mon.update(v)
        self.assertAlmostEqual(mon.current_volatility, 0.0, places=4)

    def test_volatile_series_nonzero(self):
        mon = VolatilityMonitor(window=5)
        for v in [100, 110, 95, 115, 90]:
            mon.update(v)
        self.assertGreater(mon.current_volatility, 0.0)

    def test_insufficient_data(self):
        mon = VolatilityMonitor(window=20)
        mon.update(100)
        self.assertAlmostEqual(mon.current_volatility, 0.0)

    def test_is_elevated(self):
        mon = VolatilityMonitor(window=5)
        # Extreme moves
        for v in [100, 130, 80, 140, 70]:
            mon.update(v)
        self.assertTrue(mon.is_elevated)

    def test_normal_vol_not_elevated(self):
        mon = VolatilityMonitor(window=5)
        for v in [100, 101, 100, 101, 100]:
            mon.update(v)
        self.assertFalse(mon.is_elevated)


class TestRiskDashboard(unittest.TestCase):
    """Test combined risk dashboard."""

    def test_update_processes_value(self):
        dash = RiskDashboard()
        dash.update(100)
        dash.update(110)
        dash.update(105)
        summary = dash.summary()
        self.assertIn("drawdown", summary)
        self.assertIn("volatility", summary)
        self.assertIn("overall_risk", summary)

    def test_overall_risk_green_when_calm(self):
        dash = RiskDashboard()
        for v in [100, 101, 102, 103, 104]:
            dash.update(v)
        summary = dash.summary()
        self.assertEqual(summary["overall_risk"], "GREEN")

    def test_overall_risk_escalates_with_drawdown(self):
        dash = RiskDashboard()
        for v in [100, 60]:
            dash.update(v)
        summary = dash.summary()
        self.assertIn(summary["overall_risk"], ["RED", "CRITICAL"])

    def test_alert_text_when_risky(self):
        dash = RiskDashboard()
        for v in [100, 75]:
            dash.update(v)
        alerts = dash.alerts()
        self.assertGreater(len(alerts), 0)
        self.assertTrue(any("drawdown" in a.lower() for a in alerts))

    def test_no_alerts_when_calm(self):
        dash = RiskDashboard()
        for v in [100, 101, 102]:
            dash.update(v)
        alerts = dash.alerts()
        self.assertEqual(len(alerts), 0)

    def test_summary_to_json_serializable(self):
        import json
        dash = RiskDashboard()
        for v in [100, 95, 105]:
            dash.update(v)
        s = dash.summary()
        # Should be JSON-serializable
        json.dumps(s)


if __name__ == "__main__":
    unittest.main()
