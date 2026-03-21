#!/usr/bin/env python3
"""Tests for peak_hours.py — rate limit awareness utility."""

import json
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

import peak_hours


class TestGetStatus(unittest.TestCase):
    """Test get_status() under various time conditions."""

    def _mock_time(self, year=2026, month=3, day=20, hour=10, minute=0, weekday_name="Friday"):
        """Create a UTC datetime. hour is in ET (will be converted to UTC by adding 4)."""
        utc_hour = hour + 4  # EDT offset
        return datetime(year, month, day, utc_hour, minute, tzinfo=timezone.utc)

    def test_weekday_peak_hours(self):
        """8AM-2PM ET on weekday = peak."""
        # Friday March 20, 2026 at 10:00 ET = 14:00 UTC
        mock_utc = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertTrue(status["is_peak"])
        self.assertEqual(status["max_recommended_chats"], 2)

    def test_weekday_off_peak_morning(self):
        """6AM ET on weekday = off-peak."""
        mock_utc = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)  # 6AM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["is_peak"])

    def test_weekday_off_peak_evening(self):
        """6PM ET on weekday = off-peak."""
        mock_utc = datetime(2026, 3, 20, 22, 0, tzinfo=timezone.utc)  # 6PM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["is_peak"])

    def test_weekend_never_peak(self):
        """Weekend is never peak, even during peak hours."""
        # Saturday March 21, 2026 at 10:00 ET = 14:00 UTC
        mock_utc = datetime(2026, 3, 21, 14, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["is_peak"])
        self.assertFalse(status["is_weekday"])

    def test_promo_active_during_range(self):
        """Promo is active March 13-28, 2026."""
        mock_utc = datetime(2026, 3, 20, 20, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertTrue(status["promo_active"])

    def test_promo_inactive_before_range(self):
        """Promo is inactive before March 13."""
        mock_utc = datetime(2026, 3, 10, 20, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["promo_active"])

    def test_promo_inactive_after_range(self):
        """Promo is inactive after March 28."""
        mock_utc = datetime(2026, 3, 30, 20, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["promo_active"])

    def test_double_limits_off_peak_with_promo(self):
        """Off-peak during promo = double limits."""
        # Saturday March 21, 2026 (weekend, promo active)
        mock_utc = datetime(2026, 3, 21, 20, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertTrue(status["has_double_limits"])
        self.assertEqual(status["max_recommended_chats"], 3)

    def test_no_double_limits_peak_with_promo(self):
        """Peak during promo = standard limits (no double)."""
        # Friday 10AM ET during promo
        mock_utc = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["has_double_limits"])

    def test_peak_boundary_8am(self):
        """Exactly 8AM ET = peak."""
        mock_utc = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)  # 8AM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertTrue(status["is_peak"])

    def test_peak_boundary_2pm_exclusive(self):
        """Exactly 2PM ET = off-peak (exclusive upper bound)."""
        mock_utc = datetime(2026, 3, 20, 18, 0, tzinfo=timezone.utc)  # 2PM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["is_peak"])

    def test_peak_boundary_759am(self):
        """7:59 AM ET = off-peak."""
        mock_utc = datetime(2026, 3, 20, 11, 59, tzinfo=timezone.utc)  # 7:59 AM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            status = peak_hours.get_status()
        self.assertFalse(status["is_peak"])

    def test_status_has_all_keys(self):
        """Status dict should have all expected keys."""
        status = peak_hours.get_status()
        expected_keys = {"time_et", "is_peak", "is_weekday", "promo_active",
                         "has_double_limits", "recommendation", "max_recommended_chats"}
        self.assertEqual(set(status.keys()), expected_keys)

    def test_recommendation_contains_text(self):
        """Recommendation should be a non-empty string."""
        status = peak_hours.get_status()
        self.assertIsInstance(status["recommendation"], str)
        self.assertTrue(len(status["recommendation"]) > 10)

    def test_max_chats_is_int(self):
        """Max recommended chats should be an integer."""
        status = peak_hours.get_status()
        self.assertIsInstance(status["max_recommended_chats"], int)
        self.assertIn(status["max_recommended_chats"], (2, 3))


class TestMainCLI(unittest.TestCase):
    """Test CLI output modes."""

    def test_json_output_valid(self):
        """--json flag should produce valid JSON."""
        import io
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            with patch('sys.argv', ['peak_hours.py', '--json']):
                peak_hours.main()
        finally:
            sys.stdout = old_stdout
        data = json.loads(captured.getvalue())
        self.assertIn("is_peak", data)

    def test_human_output_has_time(self):
        """Default output should show time."""
        import io
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            with patch('sys.argv', ['peak_hours.py']):
                peak_hours.main()
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn("Time:", output)
        self.assertIn("ET", output)

    def test_check_exit_code_off_peak(self):
        """--check should exit 0 when off-peak."""
        mock_utc = datetime(2026, 3, 21, 20, 0, tzinfo=timezone.utc)  # Saturday
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with patch('sys.argv', ['peak_hours.py', '--check']):
                with self.assertRaises(SystemExit) as cm:
                    peak_hours.main()
                self.assertEqual(cm.exception.code, 0)

    def test_check_exit_code_peak(self):
        """--check should exit 1 when peak."""
        mock_utc = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)  # Fri 10AM ET
        with patch('peak_hours.datetime') as mock_dt:
            mock_dt.now.return_value = mock_utc
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with patch('sys.argv', ['peak_hours.py', '--check']):
                with self.assertRaises(SystemExit) as cm:
                    peak_hours.main()
                self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
