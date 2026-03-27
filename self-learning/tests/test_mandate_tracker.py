"""Tests for mandate_tracker.py — 5-day mandate progress tracker.

Tracks daily P&L against a target (e.g. $15-25/day over 5 days),
projects probability of success, and recommends adjustments.
"""
import sys
import os
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mandate_tracker import (
    DailyResult,
    MandateConfig,
    MandateTracker,
    MandateStatus,
)


class TestDailyResult(unittest.TestCase):
    """Test DailyResult dataclass."""

    def test_basic_creation(self):
        r = DailyResult(day=1, date=date(2026, 3, 27), pnl=20.0, bets=64, wins=60, losses=4)
        self.assertEqual(r.day, 1)
        self.assertAlmostEqual(r.pnl, 20.0)
        self.assertEqual(r.bets, 64)

    def test_win_rate(self):
        r = DailyResult(day=1, date=date(2026, 3, 27), pnl=15.0, bets=100, wins=93, losses=7)
        self.assertAlmostEqual(r.win_rate(), 0.93)

    def test_win_rate_zero_bets(self):
        r = DailyResult(day=1, date=date(2026, 3, 27), pnl=0.0, bets=0, wins=0, losses=0)
        self.assertAlmostEqual(r.win_rate(), 0.0)

    def test_avg_pnl_per_bet(self):
        r = DailyResult(day=1, date=date(2026, 3, 27), pnl=20.0, bets=80, wins=74, losses=6)
        self.assertAlmostEqual(r.avg_pnl_per_bet(), 0.25)


class TestMandateConfig(unittest.TestCase):
    """Test MandateConfig defaults and custom values."""

    def test_defaults(self):
        cfg = MandateConfig()
        self.assertEqual(cfg.total_days, 5)
        self.assertAlmostEqual(cfg.daily_target_low, 15.0)
        self.assertAlmostEqual(cfg.daily_target_high, 25.0)

    def test_custom_config(self):
        cfg = MandateConfig(total_days=7, daily_target_low=10.0, daily_target_high=20.0)
        self.assertEqual(cfg.total_days, 7)
        self.assertAlmostEqual(cfg.daily_target_low, 10.0)

    def test_total_target(self):
        cfg = MandateConfig(total_days=5, daily_target_low=15.0, daily_target_high=25.0)
        self.assertAlmostEqual(cfg.total_target_low(), 75.0)
        self.assertAlmostEqual(cfg.total_target_high(), 125.0)


class TestMandateTrackerEmpty(unittest.TestCase):
    """Test tracker with no results yet."""

    def test_empty_tracker(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        status = tracker.status()
        self.assertEqual(status.days_completed, 0)
        self.assertEqual(status.days_remaining, 5)
        self.assertAlmostEqual(status.total_pnl, 0.0)

    def test_empty_on_track(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        status = tracker.status()
        # Day 0: technically on track (haven't started)
        self.assertIn(status.verdict, ["ON_TRACK", "PENDING"])


class TestMandateTrackerWithResults(unittest.TestCase):
    """Test tracker with daily results."""

    def _make_tracker(self, pnls):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        base = date(2026, 3, 27)
        for i, pnl in enumerate(pnls):
            bets = 64
            wr = 0.933
            wins = int(bets * wr)
            losses = bets - wins
            tracker.add_day(DailyResult(
                day=i + 1,
                date=base + timedelta(days=i),
                pnl=pnl,
                bets=bets,
                wins=wins,
                losses=losses,
            ))
        return tracker

    def test_one_good_day(self):
        tracker = self._make_tracker([22.0])
        s = tracker.status()
        self.assertEqual(s.days_completed, 1)
        self.assertEqual(s.days_remaining, 4)
        self.assertAlmostEqual(s.total_pnl, 22.0)
        self.assertAlmostEqual(s.avg_daily_pnl, 22.0)

    def test_two_days_mixed(self):
        tracker = self._make_tracker([22.0, -5.0])
        s = tracker.status()
        self.assertEqual(s.days_completed, 2)
        self.assertAlmostEqual(s.total_pnl, 17.0)
        self.assertAlmostEqual(s.avg_daily_pnl, 8.5)

    def test_five_days_success(self):
        tracker = self._make_tracker([20.0, 18.0, 25.0, 15.0, 22.0])
        s = tracker.status()
        self.assertEqual(s.days_completed, 5)
        self.assertEqual(s.days_remaining, 0)
        self.assertAlmostEqual(s.total_pnl, 100.0)
        self.assertEqual(s.verdict, "SUCCESS")

    def test_five_days_failure(self):
        tracker = self._make_tracker([5.0, -10.0, 8.0, 3.0, -2.0])
        s = tracker.status()
        self.assertAlmostEqual(s.total_pnl, 4.0)
        self.assertEqual(s.verdict, "FAILED")

    def test_projected_total(self):
        tracker = self._make_tracker([20.0, 18.0])
        s = tracker.status()
        # avg = 19, projected = 19 * 5 = 95
        self.assertAlmostEqual(s.projected_total, 95.0)

    def test_needed_daily_pace(self):
        tracker = self._make_tracker([10.0])
        s = tracker.status()
        # Need 75 total min. Have 10. Remaining = 65 over 4 days = 16.25/day
        self.assertAlmostEqual(s.needed_daily_pace_low, 16.25)

    def test_behind_pace_verdict(self):
        tracker = self._make_tracker([5.0, 3.0])
        s = tracker.status()
        # avg = 4, projected = 20. Target low = 75. Way behind.
        self.assertEqual(s.verdict, "BEHIND")

    def test_ahead_pace_verdict(self):
        tracker = self._make_tracker([30.0, 28.0])
        s = tracker.status()
        # avg = 29, projected = 145. Well above 125 high target.
        self.assertEqual(s.verdict, "AHEAD")

    def test_on_track_verdict(self):
        tracker = self._make_tracker([18.0, 20.0])
        s = tracker.status()
        # avg = 19, projected = 95. Between 75-125.
        self.assertEqual(s.verdict, "ON_TRACK")


class TestMandateTrackerRecommendations(unittest.TestCase):
    """Test that tracker produces actionable recommendations."""

    def test_good_day_no_change(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=20.0, bets=64, wins=60, losses=4,
        ))
        recs = tracker.recommendations()
        self.assertIsInstance(recs, list)
        # Good day — should have at most 1-2 recommendations
        self.assertLessEqual(len(recs), 3)

    def test_bad_day_has_recs(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=-15.0, bets=30, wins=25, losses=5,
        ))
        recs = tracker.recommendations()
        self.assertGreater(len(recs), 0)

    def test_low_frequency_flagged(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=5.0, bets=20, wins=19, losses=1,
        ))
        recs = tracker.recommendations()
        freq_recs = [r for r in recs if "frequency" in r.lower() or "bets" in r.lower()]
        self.assertGreater(len(freq_recs), 0)

    def test_low_wr_flagged(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=-5.0, bets=64, wins=55, losses=9,
        ))
        recs = tracker.recommendations()
        wr_recs = [r for r in recs if "win rate" in r.lower() or "wr" in r.lower()]
        self.assertGreater(len(wr_recs), 0)


class TestMandateTrackerJSON(unittest.TestCase):
    """Test JSON export for monitoring integration."""

    def test_to_dict(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=20.0, bets=64, wins=60, losses=4,
        ))
        d = tracker.to_dict()
        self.assertIn("config", d)
        self.assertIn("days", d)
        self.assertIn("status", d)
        self.assertIn("recommendations", d)
        self.assertEqual(len(d["days"]), 1)
        self.assertEqual(d["status"]["days_completed"], 1)

    def test_empty_to_dict(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        d = tracker.to_dict()
        self.assertEqual(len(d["days"]), 0)


class TestMandateTrackerSummaryText(unittest.TestCase):
    """Test human-readable summary output."""

    def test_summary_contains_key_info(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        tracker.add_day(DailyResult(
            day=1, date=date(2026, 3, 27), pnl=20.0, bets=64, wins=60, losses=4,
        ))
        text = tracker.summary_text()
        self.assertIn("Day 1", text)
        self.assertIn("20.0", text)
        self.assertIn("ON_TRACK", text)

    def test_summary_shows_verdict(self):
        cfg = MandateConfig()
        tracker = MandateTracker(cfg)
        for i in range(5):
            tracker.add_day(DailyResult(
                day=i + 1, date=date(2026, 3, 27) + timedelta(days=i),
                pnl=20.0, bets=64, wins=60, losses=4,
            ))
        text = tracker.summary_text()
        self.assertIn("SUCCESS", text)


if __name__ == "__main__":
    unittest.main()
