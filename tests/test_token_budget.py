#!/usr/bin/env python3
"""Tests for token_budget.py (MT-38)."""

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from token_budget import get_budget, format_brief, format_full


class TestGetBudget(unittest.TestCase):
    """Test budget window detection."""

    def test_peak_weekday_morning(self):
        now = datetime(2026, 3, 24, 10, 30)  # Tuesday 10:30 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "PEAK")
        self.assertEqual(info["budget_pct"], 60)

    def test_peak_weekday_start(self):
        now = datetime(2026, 3, 24, 8, 0)  # Tuesday 8:00 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "PEAK")

    def test_peak_weekday_end(self):
        now = datetime(2026, 3, 24, 13, 59)  # Tuesday 1:59 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "PEAK")

    def test_shoulder_early_morning(self):
        now = datetime(2026, 3, 24, 7, 0)  # Tuesday 7:00 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "SHOULDER")
        self.assertEqual(info["budget_pct"], 80)

    def test_shoulder_afternoon(self):
        now = datetime(2026, 3, 24, 15, 0)  # Tuesday 3:00 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "SHOULDER")

    def test_shoulder_end(self):
        now = datetime(2026, 3, 24, 17, 59)  # Tuesday 5:59 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "SHOULDER")

    def test_offpeak_evening(self):
        now = datetime(2026, 3, 24, 20, 0)  # Tuesday 8:00 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")
        self.assertEqual(info["budget_pct"], 100)

    def test_offpeak_late_night(self):
        now = datetime(2026, 3, 24, 2, 0)  # Tuesday 2:00 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")

    def test_offpeak_early_morning_boundary(self):
        now = datetime(2026, 3, 24, 5, 59)  # Tuesday 5:59 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")

    def test_shoulder_6am_boundary(self):
        now = datetime(2026, 3, 24, 6, 0)  # Tuesday 6:00 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "SHOULDER")

    def test_offpeak_6pm_boundary(self):
        now = datetime(2026, 3, 24, 18, 0)  # Tuesday 6:00 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")

    def test_weekend_saturday_peak_hours(self):
        """Weekend should be OFF-PEAK even during normal peak hours."""
        now = datetime(2026, 3, 28, 10, 0)  # Saturday 10:00 AM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")
        self.assertTrue(info["is_weekend"])

    def test_weekend_sunday(self):
        now = datetime(2026, 3, 29, 14, 0)  # Sunday 2:00 PM
        info = get_budget(now)
        self.assertEqual(info["window"], "OFF-PEAK")
        self.assertTrue(info["is_weekend"])

    def test_weekday_not_weekend(self):
        now = datetime(2026, 3, 24, 10, 0)  # Tuesday
        info = get_budget(now)
        self.assertFalse(info["is_weekend"])

    def test_friday_is_weekday(self):
        now = datetime(2026, 3, 27, 10, 0)  # Friday
        info = get_budget(now)
        self.assertEqual(info["window"], "PEAK")
        self.assertFalse(info["is_weekend"])


class TestInfoFields(unittest.TestCase):
    """Test that all required fields are present."""

    def test_all_fields_present(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))
        required = ["window", "budget_pct", "label", "hours", "rules",
                     "color", "is_weekend", "hour", "weekday",
                     "weekday_name", "timestamp"]
        for field in required:
            self.assertIn(field, info, f"Missing field: {field}")

    def test_rules_is_list(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))
        self.assertIsInstance(info["rules"], list)
        self.assertGreater(len(info["rules"]), 0)

    def test_weekday_name_correct(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))  # Tuesday
        self.assertEqual(info["weekday_name"], "Tue")


class TestFormatting(unittest.TestCase):
    """Test display formatting."""

    def test_brief_contains_label(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))
        brief = format_brief(info)
        self.assertIn("PEAK (60%)", brief)
        self.assertIn("Tue", brief)
        self.assertIn("ET", brief)

    def test_full_contains_guidelines(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))
        full = format_full(info)
        self.assertIn("TOKEN BUDGET:", full)
        self.assertIn("Guidelines:", full)
        self.assertIn("gsd:quick", full)

    def test_json_roundtrip(self):
        info = get_budget(datetime(2026, 3, 24, 10, 0))
        serialized = json.dumps(info)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["window"], "PEAK")
        self.assertEqual(deserialized["budget_pct"], 60)


class TestAutoloopScheduling(unittest.TestCase):
    """Test autoloop scheduling settings (MT-38 Phase 4)."""

    def test_offpeak_full_speed(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 22, 0)  # Tuesday 10 PM
        settings = get_autoloop_settings(now)
        self.assertEqual(settings["cooldown"], 15)
        self.assertEqual(settings["model_preference"], "opus")
        self.assertFalse(settings["defer"])

    def test_peak_extended_cooldown(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 10, 0)  # Tuesday 10 AM
        settings = get_autoloop_settings(now)
        self.assertEqual(settings["cooldown"], 300)  # 5 min
        self.assertEqual(settings["model_preference"], "sonnet")
        self.assertFalse(settings["defer"])

    def test_shoulder_moderate_cooldown(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 15, 0)  # Tuesday 3 PM
        settings = get_autoloop_settings(now)
        self.assertEqual(settings["cooldown"], 60)
        self.assertEqual(settings["model_preference"], "opus")
        self.assertFalse(settings["defer"])

    def test_weekend_full_speed(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 28, 10, 0)  # Saturday 10 AM
        settings = get_autoloop_settings(now)
        self.assertEqual(settings["cooldown"], 15)
        self.assertFalse(settings["defer"])

    def test_returns_budget_info(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 10, 0)
        settings = get_autoloop_settings(now)
        self.assertEqual(settings["window"], "PEAK")
        self.assertEqual(settings["budget_pct"], 60)

    def test_all_fields_present(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 10, 0)
        settings = get_autoloop_settings(now)
        for field in ["cooldown", "model_preference", "defer", "window", "budget_pct", "reason"]:
            self.assertIn(field, settings, f"Missing field: {field}")

    def test_reason_explains_peak(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 10, 0)
        settings = get_autoloop_settings(now)
        self.assertIn("peak", settings["reason"].lower())

    def test_reason_explains_offpeak(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 22, 0)
        settings = get_autoloop_settings(now)
        self.assertIn("off-peak", settings["reason"].lower())

    def test_shoulder_reason(self):
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 15, 0)
        settings = get_autoloop_settings(now)
        self.assertIn("shoulder", settings["reason"].lower())

    def test_peak_defer_flag_off_by_default(self):
        """Peak slows down but doesn't stop — defer is False."""
        from token_budget import get_autoloop_settings
        now = datetime(2026, 3, 24, 10, 0)
        settings = get_autoloop_settings(now)
        self.assertFalse(settings["defer"])

    def test_cooldown_types(self):
        from token_budget import get_autoloop_settings
        for hour in [2, 7, 10, 15, 22]:
            now = datetime(2026, 3, 24, hour, 0)
            settings = get_autoloop_settings(now)
            self.assertIsInstance(settings["cooldown"], int)
            self.assertGreater(settings["cooldown"], 0)


if __name__ == "__main__":
    unittest.main()
