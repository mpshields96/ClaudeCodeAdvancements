"""Tests for wr_cliff_analyzer.py — WR cliff detection.

Finds the exact win rate threshold where ruin probability jumps from
safe (<5%) to dangerous (>20%). Maps these cliffs across different
avg_loss levels to create a safety map.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wr_cliff_analyzer import (
    CliffPoint,
    WRCliffMap,
    WRCliffAnalyzer,
)


class TestCliffPoint(unittest.TestCase):
    def test_create(self):
        cp = CliffPoint(
            avg_loss=-11.39,
            cliff_wr=0.932,
            safe_wr=0.940,
            danger_wr=0.920,
            margin_from_current=0.001,
        )
        self.assertAlmostEqual(cp.cliff_wr, 0.932)

    def test_to_dict(self):
        cp = CliffPoint(-11.39, 0.932, 0.940, 0.920, 0.001)
        d = cp.to_dict()
        json.dumps(d)


class TestWRCliffMap(unittest.TestCase):
    def test_create(self):
        points = [
            CliffPoint(-11.39, 0.932, 0.940, 0.920, 0.001),
            CliffPoint(-8.00, 0.910, 0.920, 0.900, 0.023),
        ]
        cm = WRCliffMap(
            current_wr=0.933,
            current_avg_loss=-11.39,
            cliffs=points,
        )
        self.assertEqual(len(cm.cliffs), 2)

    def test_safety_margin(self):
        """Report safety margin from current WR to nearest cliff."""
        points = [
            CliffPoint(-11.39, 0.932, 0.940, 0.920, 0.001),
        ]
        cm = WRCliffMap(current_wr=0.933, current_avg_loss=-11.39, cliffs=points)
        margin = cm.safety_margin()
        self.assertAlmostEqual(margin, 0.001)  # 0.933 - 0.932

    def test_summary(self):
        points = [
            CliffPoint(-11.39, 0.932, 0.940, 0.920, 0.001),
            CliffPoint(-8.00, 0.910, 0.920, 0.900, 0.023),
        ]
        cm = WRCliffMap(current_wr=0.933, current_avg_loss=-11.39, cliffs=points)
        s = cm.summary()
        self.assertIn("93.2%", s)

    def test_to_dict(self):
        points = [CliffPoint(-11.39, 0.932, 0.940, 0.920, 0.001)]
        cm = WRCliffMap(current_wr=0.933, current_avg_loss=-11.39, cliffs=points)
        d = cm.to_dict()
        json.dumps(d)


class TestWRCliffAnalyzer(unittest.TestCase):
    def test_create(self):
        a = WRCliffAnalyzer(
            current_wr=0.933,
            avg_win=0.90,
            daily_volume=78,
            bankroll=178.05,
        )
        self.assertAlmostEqual(a.current_wr, 0.933)

    def test_find_cliff_at_loss_level(self):
        """Find the WR cliff for a specific avg_loss."""
        a = WRCliffAnalyzer(
            current_wr=0.933, avg_win=0.90,
            daily_volume=78, bankroll=178.05,
        )
        cliff = a.find_cliff(avg_loss=-11.39, n_sims=200, seed=42)
        self.assertIsInstance(cliff, CliffPoint)
        # Cliff WR should be below 1.0 and above 0.5
        self.assertGreater(cliff.cliff_wr, 0.50)
        self.assertLess(cliff.cliff_wr, 1.0)

    def test_cliff_map(self):
        """Build cliff map across multiple avg_loss levels."""
        a = WRCliffAnalyzer(
            current_wr=0.933, avg_win=0.90,
            daily_volume=78, bankroll=178.05,
        )
        cm = a.cliff_map(
            loss_levels=[-11.39, -10.0, -8.0],
            n_sims=200,
            seed=42,
        )
        self.assertIsInstance(cm, WRCliffMap)
        self.assertEqual(len(cm.cliffs), 3)

    def test_lower_loss_has_lower_cliff(self):
        """At lower avg_loss (less negative), the WR cliff should be lower."""
        a = WRCliffAnalyzer(
            current_wr=0.933, avg_win=0.90,
            daily_volume=78, bankroll=178.05,
        )
        cliff_high = a.find_cliff(avg_loss=-11.39, n_sims=500, seed=42)
        cliff_low = a.find_cliff(avg_loss=-6.0, n_sims=500, seed=42)
        # Lower loss magnitude = lower cliff WR (more safety margin)
        self.assertLess(cliff_low.cliff_wr, cliff_high.cliff_wr)

    def test_margin_improves_with_loss_reduction(self):
        """Safety margin should increase as avg_loss decreases."""
        a = WRCliffAnalyzer(
            current_wr=0.933, avg_win=0.90,
            daily_volume=78, bankroll=178.05,
        )
        cliff_high = a.find_cliff(avg_loss=-11.39, n_sims=500, seed=42)
        cliff_low = a.find_cliff(avg_loss=-8.0, n_sims=500, seed=42)
        self.assertGreater(cliff_low.margin_from_current, cliff_high.margin_from_current)

    def test_full_report(self):
        a = WRCliffAnalyzer(
            current_wr=0.933, avg_win=0.90,
            daily_volume=78, bankroll=178.05,
        )
        report = a.full_report(n_sims=200, seed=42)
        self.assertIn("cliff_map", report)
        self.assertIn("safety_margin", report)
        self.assertIn("recommendation", report)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
