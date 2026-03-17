"""
Tests for CTX-2: context health status line.
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import statusline


class TestAdaptiveThresholds(unittest.TestCase):

    def test_standard_200k_window(self):
        t = statusline._adaptive_thresholds(200_000)
        self.assertEqual(t, {"yellow": 50, "red": 70, "critical": 85})

    def test_1m_window_tightens_thresholds(self):
        t = statusline._adaptive_thresholds(1_000_000)
        self.assertEqual(t["yellow"], 25)
        self.assertEqual(t["red"], 40)
        self.assertEqual(t["critical"], 60)

    def test_zero_window_returns_defaults(self):
        t = statusline._adaptive_thresholds(0)
        self.assertEqual(t, {"yellow": 50, "red": 70, "critical": 85})


class TestZoneClassification(unittest.TestCase):

    def test_green_zone(self):
        color, label, _ = statusline._zone(30.0)
        self.assertEqual(label, "ok  ")

    def test_yellow_zone(self):
        color, label, _ = statusline._zone(55.0)
        self.assertEqual(label, "warn")

    def test_red_zone(self):
        color, label, _ = statusline._zone(75.0)
        self.assertEqual(label, "HIGH")

    def test_critical_zone(self):
        color, label, _ = statusline._zone(90.0)
        self.assertEqual(label, "CRIT")

    def test_custom_thresholds(self):
        color, label, _ = statusline._zone(30.0, {"yellow": 25, "red": 40, "critical": 60})
        self.assertEqual(label, "warn")


class TestBar(unittest.TestCase):

    def test_empty_bar(self):
        bar = statusline._bar(0)
        self.assertEqual(bar, "[          ]")

    def test_full_bar(self):
        bar = statusline._bar(100)
        self.assertEqual(bar, "[==========]")

    def test_half_bar(self):
        bar = statusline._bar(50)
        self.assertEqual(bar, "[=====     ]")

    def test_over_100_capped(self):
        bar = statusline._bar(150)
        self.assertEqual(bar, "[==========]")


class TestFormatWindow(unittest.TestCase):

    def test_200k(self):
        self.assertEqual(statusline._format_window(200_000), "200k")

    def test_1m(self):
        self.assertEqual(statusline._format_window(1_000_000), "1M")


class TestAutocompactProximity(unittest.TestCase):
    """Tests for autocompact proximity display in status line."""

    def test_get_autocompact_pct_from_env(self):
        with patch.dict(os.environ, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60"}):
            self.assertEqual(statusline._get_autocompact_pct(), 60)

    def test_get_autocompact_pct_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(statusline._get_autocompact_pct())

    def test_get_autocompact_pct_invalid(self):
        with patch.dict(os.environ, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "abc"}):
            self.assertIsNone(statusline._get_autocompact_pct())

    def test_compute_proximity(self):
        self.assertEqual(statusline._autocompact_proximity(55.0, 60), 5.0)

    def test_compute_proximity_already_past(self):
        self.assertEqual(statusline._autocompact_proximity(65.0, 60), 0.0)

    def test_compute_proximity_none_when_not_set(self):
        self.assertIsNone(statusline._autocompact_proximity(55.0, None))

    def test_format_autocompact_part_close(self):
        """When proximity is low, show warning."""
        part = statusline._format_autocompact_part(5.0)
        self.assertIn("AC", part)
        self.assertIn("5", part)

    def test_format_autocompact_part_comfortable(self):
        """When proximity is comfortable (>15), no display needed."""
        part = statusline._format_autocompact_part(20.0)
        self.assertEqual(part, "")

    def test_format_autocompact_part_none(self):
        """No display when autocompact not configured."""
        part = statusline._format_autocompact_part(None)
        self.assertEqual(part, "")

    def test_format_autocompact_part_zero(self):
        """At or past threshold, show urgent warning."""
        part = statusline._format_autocompact_part(0.0)
        self.assertIn("AC", part)
        self.assertIn("NOW", part)


if __name__ == "__main__":
    unittest.main()
