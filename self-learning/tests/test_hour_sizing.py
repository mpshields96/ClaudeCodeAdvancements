#!/usr/bin/env python3
"""Tests for hour_sizing.py — Time-of-day bet sizing adjuster."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hour_sizing import (
    HourProfile,
    HourSizingAdjuster,
    SizingAdjustment,
)


class TestHourProfile(unittest.TestCase):
    """Test HourProfile dataclass."""

    def test_basic(self):
        hp = HourProfile(hour_utc=10, n_bets=20, win_rate=0.97, avg_ev=1.409)
        self.assertEqual(hp.hour_utc, 10)
        self.assertAlmostEqual(hp.avg_ev, 1.409)

    def test_to_dict(self):
        hp = HourProfile(hour_utc=10, n_bets=20, win_rate=0.97, avg_ev=1.409)
        d = hp.to_dict()
        self.assertEqual(d["hour_utc"], 10)
        self.assertIn("avg_ev", d)


class TestHourSizingAdjuster(unittest.TestCase):
    """Test the sizing adjuster."""

    def setUp(self):
        self.adjuster = HourSizingAdjuster()

    def test_default_profiles_loaded(self):
        """Should have profiles for known hours."""
        self.assertGreater(len(self.adjuster.profiles), 10)

    def test_high_ev_hour_gets_boost(self):
        """Hour 10 (EV=+1.409) should get sizing multiplier > 1.0."""
        adj = self.adjuster.get_adjustment(hour_utc=10)
        self.assertIsInstance(adj, SizingAdjustment)
        self.assertGreater(adj.multiplier, 1.0)

    def test_low_ev_hour_gets_reduction(self):
        """Hour 5 (EV=-0.671) should get sizing multiplier < 1.0."""
        adj = self.adjuster.get_adjustment(hour_utc=5)
        self.assertLess(adj.multiplier, 1.0)

    def test_blocked_hour_gets_zero(self):
        """Hour 8 (blocked) should get multiplier = 0.0."""
        adj = self.adjuster.get_adjustment(hour_utc=8)
        self.assertAlmostEqual(adj.multiplier, 0.0)

    def test_neutral_hour(self):
        """Average-EV hour should get multiplier near 1.0."""
        adj = self.adjuster.get_adjustment(hour_utc=15)
        self.assertGreater(adj.multiplier, 0.5)
        self.assertLess(adj.multiplier, 1.5)

    def test_apply_to_bet_size(self):
        """Applying to $10 base should scale correctly."""
        adj = self.adjuster.get_adjustment(hour_utc=10)
        scaled = adj.apply(base_max_loss=10.0)
        self.assertGreater(scaled, 10.0)

    def test_apply_respects_floor(self):
        """Even low-EV hours shouldn't go below floor."""
        adj = self.adjuster.get_adjustment(hour_utc=5)
        scaled = adj.apply(base_max_loss=10.0, floor=5.0)
        self.assertGreaterEqual(scaled, 5.0)

    def test_apply_respects_cap(self):
        """Even high-EV hours shouldn't exceed cap."""
        adj = self.adjuster.get_adjustment(hour_utc=10)
        scaled = adj.apply(base_max_loss=10.0, cap=12.0)
        self.assertLessEqual(scaled, 12.0)

    def test_unknown_hour_gets_default(self):
        """Hours without explicit data get multiplier 1.0."""
        # Hour 99 doesn't exist
        adj = self.adjuster.get_adjustment(hour_utc=99)
        self.assertAlmostEqual(adj.multiplier, 1.0)

    def test_full_day_schedule(self):
        """Get adjustments for all 24 hours."""
        schedule = self.adjuster.daily_schedule(base_max_loss=10.0)
        self.assertEqual(len(schedule), 24)
        # All should be non-negative
        for hour, adj in schedule.items():
            self.assertGreaterEqual(adj.multiplier, 0.0)

    def test_schedule_has_variation(self):
        """Schedule should not be all 1.0 — there should be real variation."""
        schedule = self.adjuster.daily_schedule(base_max_loss=10.0)
        multipliers = [adj.multiplier for adj in schedule.values()]
        self.assertGreater(max(multipliers), 1.0)
        self.assertLess(min(multipliers), 1.0)

    def test_custom_profiles(self):
        """Support custom hour profiles."""
        profiles = [
            HourProfile(hour_utc=0, n_bets=50, win_rate=0.98, avg_ev=2.0),
            HourProfile(hour_utc=12, n_bets=50, win_rate=0.90, avg_ev=-1.0),
        ]
        adj = HourSizingAdjuster(profiles=profiles)
        h0 = adj.get_adjustment(hour_utc=0)
        h12 = adj.get_adjustment(hour_utc=12)
        self.assertGreater(h0.multiplier, h12.multiplier)

    def test_asset_specific(self):
        """Can get adjustment for specific asset."""
        adj_btc = self.adjuster.get_adjustment(hour_utc=10, asset="KXBTC")
        self.assertIsInstance(adj_btc, SizingAdjustment)

    def test_to_json_schedule(self):
        schedule = self.adjuster.daily_schedule(base_max_loss=10.0)
        data = {str(h): a.to_dict() for h, a in schedule.items()}
        j = json.dumps(data)
        parsed = json.loads(j)
        self.assertEqual(len(parsed), 24)


class TestSizingAdjustment(unittest.TestCase):
    """Test SizingAdjustment dataclass."""

    def test_apply_basic(self):
        adj = SizingAdjustment(
            hour_utc=10, multiplier=1.3, reason="High EV hour", confidence="HIGH"
        )
        self.assertAlmostEqual(adj.apply(10.0), 13.0)

    def test_apply_zero_multiplier(self):
        adj = SizingAdjustment(
            hour_utc=8, multiplier=0.0, reason="Blocked", confidence="HIGH"
        )
        self.assertAlmostEqual(adj.apply(10.0), 0.0)

    def test_apply_with_floor_and_cap(self):
        adj = SizingAdjustment(
            hour_utc=10, multiplier=2.0, reason="Test", confidence="LOW"
        )
        scaled = adj.apply(10.0, floor=5.0, cap=15.0)
        self.assertAlmostEqual(scaled, 15.0)

    def test_to_dict(self):
        adj = SizingAdjustment(
            hour_utc=10, multiplier=1.3, reason="High EV", confidence="HIGH"
        )
        d = adj.to_dict()
        self.assertIn("multiplier", d)
        self.assertIn("reason", d)


class TestCLI(unittest.TestCase):
    """Test CLI output."""

    def test_cli_schedule(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "hour_sizing.py"),
                "--base", "10",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("00", result.stdout)

    def test_cli_single_hour(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "hour_sizing.py"),
                "--hour", "10",
                "--base", "10",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_cli_json(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "hour_sizing.py"),
                "--base", "10",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 24)


if __name__ == "__main__":
    unittest.main()
