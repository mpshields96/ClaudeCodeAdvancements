"""Tests for mandate_dashboard.py — unified mandate monitoring dashboard.

Combines all 10 Kalshi analytical tools into a single dashboard runner.
One call produces a complete mandate health report.
"""
import sys
import os
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mandate_dashboard import (
    MandateDashboard,
    MandateDashboardConfig,
    DailySnapshot,
)


class TestDailySnapshot(unittest.TestCase):
    """Test daily snapshot data structure."""

    def test_basic_creation(self):
        s = DailySnapshot(
            day=1, date=date(2026, 3, 27), pnl=20.0, bets=64,
            wins=60, losses=4, bankroll=233.80,
        )
        self.assertEqual(s.day, 1)
        self.assertAlmostEqual(s.pnl, 20.0)

    def test_win_rate(self):
        s = DailySnapshot(
            day=1, date=date(2026, 3, 27), pnl=20.0, bets=100,
            wins=93, losses=7, bankroll=233.80,
        )
        self.assertAlmostEqual(s.win_rate(), 0.93)

    def test_zero_bets(self):
        s = DailySnapshot(
            day=1, date=date(2026, 3, 27), pnl=0.0, bets=0,
            wins=0, losses=0, bankroll=213.80,
        )
        self.assertAlmostEqual(s.win_rate(), 0.0)


class TestMandateDashboardConfig(unittest.TestCase):
    """Test dashboard configuration."""

    def test_defaults(self):
        cfg = MandateDashboardConfig()
        self.assertEqual(cfg.mandate_days, 5)
        self.assertAlmostEqual(cfg.daily_target_low, 15.0)
        self.assertAlmostEqual(cfg.initial_bankroll, 213.80)
        self.assertAlmostEqual(cfg.avg_win, 0.90)
        self.assertAlmostEqual(cfg.avg_loss, 8.0)
        self.assertAlmostEqual(cfg.expected_wr, 0.933)

    def test_custom_config(self):
        cfg = MandateDashboardConfig(mandate_days=7, initial_bankroll=300.0)
        self.assertEqual(cfg.mandate_days, 7)
        self.assertAlmostEqual(cfg.initial_bankroll, 300.0)


class TestMandateDashboardEmpty(unittest.TestCase):
    """Test dashboard with no data."""

    def test_empty_report(self):
        cfg = MandateDashboardConfig()
        dash = MandateDashboard(cfg)
        report = dash.run()
        self.assertIn("mandate", report)
        self.assertIn("kelly", report)
        self.assertIn("frequency", report)
        self.assertEqual(report["mandate"]["status"]["days_completed"], 0)

    def test_empty_summary(self):
        cfg = MandateDashboardConfig()
        dash = MandateDashboard(cfg)
        text = dash.summary_text()
        self.assertIn("MANDATE DASHBOARD", text)


class TestMandateDashboardWithData(unittest.TestCase):
    """Test dashboard with daily snapshots."""

    def _make_dashboard(self, snapshots):
        cfg = MandateDashboardConfig()
        dash = MandateDashboard(cfg)
        for s in snapshots:
            dash.add_day(s)
        return dash

    def test_one_day(self):
        dash = self._make_dashboard([
            DailySnapshot(day=1, date=date(2026, 3, 27), pnl=20.0,
                          bets=64, wins=60, losses=4, bankroll=233.80),
        ])
        report = dash.run()
        self.assertEqual(report["mandate"]["status"]["days_completed"], 1)
        self.assertAlmostEqual(report["mandate"]["status"]["total_pnl"], 20.0)
        # Kelly should use updated bankroll
        self.assertIn("full_kelly_fraction", report["kelly"]["kelly"])

    def test_kelly_uses_latest_bankroll(self):
        dash = self._make_dashboard([
            DailySnapshot(day=1, date=date(2026, 3, 27), pnl=20.0,
                          bets=64, wins=60, losses=4, bankroll=233.80),
            DailySnapshot(day=2, date=date(2026, 3, 28), pnl=-5.0,
                          bets=64, wins=58, losses=6, bankroll=228.80),
        ])
        report = dash.run()
        # Kelly params should use bankroll from latest day
        self.assertAlmostEqual(report["kelly"]["params"]["bankroll"], 228.80)

    def test_frequency_included(self):
        dash = self._make_dashboard([
            DailySnapshot(day=1, date=date(2026, 3, 27), pnl=20.0,
                          bets=64, wins=60, losses=4, bankroll=233.80),
        ])
        report = dash.run()
        self.assertIn("total_theoretical_windows", report["frequency"])

    def test_recommendations_present(self):
        dash = self._make_dashboard([
            DailySnapshot(day=1, date=date(2026, 3, 27), pnl=20.0,
                          bets=64, wins=60, losses=4, bankroll=233.80),
        ])
        report = dash.run()
        self.assertIn("recommendations", report["mandate"])

    def test_five_day_success(self):
        days = []
        base_bankroll = 213.80
        for i in range(5):
            pnl = 20.0
            base_bankroll += pnl
            days.append(DailySnapshot(
                day=i + 1, date=date(2026, 3, 27) + timedelta(days=i),
                pnl=pnl, bets=64, wins=60, losses=4, bankroll=base_bankroll,
            ))
        dash = self._make_dashboard(days)
        report = dash.run()
        self.assertEqual(report["mandate"]["status"]["verdict"], "SUCCESS")

    def test_overall_health(self):
        dash = self._make_dashboard([
            DailySnapshot(day=1, date=date(2026, 3, 27), pnl=20.0,
                          bets=64, wins=60, losses=4, bankroll=233.80),
        ])
        report = dash.run()
        self.assertIn("overall_health", report)
        self.assertIn(report["overall_health"], ["HEALTHY", "WARNING", "CRITICAL"])


class TestMandateDashboardSummaryText(unittest.TestCase):
    """Test human-readable dashboard output."""

    def test_summary_sections(self):
        cfg = MandateDashboardConfig()
        dash = MandateDashboard(cfg)
        dash.add_day(DailySnapshot(
            day=1, date=date(2026, 3, 27), pnl=20.0,
            bets=64, wins=60, losses=4, bankroll=233.80,
        ))
        text = dash.summary_text()
        self.assertIn("MANDATE", text)
        self.assertIn("KELLY", text)
        self.assertIn("FREQUENCY", text)

    def test_summary_shows_verdict(self):
        cfg = MandateDashboardConfig()
        dash = MandateDashboard(cfg)
        dash.add_day(DailySnapshot(
            day=1, date=date(2026, 3, 27), pnl=20.0,
            bets=64, wins=60, losses=4, bankroll=233.80,
        ))
        text = dash.summary_text()
        self.assertIn("ON_TRACK", text)


if __name__ == "__main__":
    unittest.main()
