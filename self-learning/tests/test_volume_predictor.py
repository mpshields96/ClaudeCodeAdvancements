#!/usr/bin/env python3
"""Tests for volume_predictor.py — sniper bet volume prediction from crypto volatility."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from volume_predictor import (
    VolumeEstimate,
    CalibrationPoint,
    predict_volume,
    calibrate_from_data,
    load_calibration_csv,
    backtest,
    RANGE_LOW,
    RANGE_MEDIUM,
    RANGE_HIGH,
)


class TestPredictVolume(unittest.TestCase):
    """Test the core prediction function."""

    def test_low_range_gives_low_band(self):
        est = predict_volume(800.0, weekday=2)
        self.assertEqual(est.band, "LOW")
        self.assertGreater(est.min_bets, 0)
        self.assertLess(est.max_bets, 50)

    def test_medium_range_gives_medium_band(self):
        est = predict_volume(2000.0, weekday=1)
        self.assertEqual(est.band, "MEDIUM")

    def test_high_range_gives_high_band(self):
        est = predict_volume(3000.0, weekday=3)
        self.assertEqual(est.band, "HIGH")
        self.assertGreater(est.min_bets, 60)

    def test_boundary_low_medium(self):
        est_low = predict_volume(RANGE_MEDIUM - 1, weekday=2)
        est_mid = predict_volume(RANGE_MEDIUM, weekday=2)
        self.assertEqual(est_low.band, "LOW")
        self.assertEqual(est_mid.band, "MEDIUM")

    def test_boundary_medium_high(self):
        est_mid = predict_volume(RANGE_HIGH - 1, weekday=2)
        est_high = predict_volume(RANGE_HIGH, weekday=2)
        self.assertEqual(est_mid.band, "MEDIUM")
        self.assertEqual(est_high.band, "HIGH")

    def test_weekend_reduces_volume(self):
        weekday_est = predict_volume(2000.0, weekday=2)
        weekend_est = predict_volume(2000.0, weekday=5)
        self.assertTrue(weekend_est.is_weekend)
        self.assertFalse(weekday_est.is_weekend)
        self.assertLess(weekend_est.midpoint, weekday_est.midpoint)

    def test_macro_day_increases_volume(self):
        normal_est = predict_volume(2000.0, weekday=2, is_macro_day=False)
        macro_est = predict_volume(2000.0, weekday=2, is_macro_day=True)
        self.assertTrue(macro_est.is_macro_day)
        self.assertGreater(macro_est.midpoint, normal_est.midpoint)

    def test_weekend_plus_macro(self):
        est = predict_volume(2000.0, weekday=6, is_macro_day=True)
        self.assertTrue(est.is_weekend)
        self.assertTrue(est.is_macro_day)
        # Weekend * macro should partially cancel
        self.assertAlmostEqual(est.multiplier, 0.7 * 1.3, places=2)

    def test_midpoint_is_average_of_range(self):
        est = predict_volume(2000.0, weekday=2)
        expected = (est.min_bets + est.max_bets) // 2
        self.assertEqual(est.midpoint, expected)

    def test_min_bets_never_zero(self):
        est = predict_volume(100.0, weekday=6)  # Very low range + weekend
        self.assertGreaterEqual(est.min_bets, 1)

    def test_max_always_greater_than_min(self):
        for r in [100, 500, 1000, 2000, 3000, 5000]:
            for wd in [0, 5]:
                est = predict_volume(float(r), weekday=wd)
                self.assertGreater(est.max_bets, est.min_bets)

    def test_to_dict(self):
        est = predict_volume(1500.0, weekday=2)
        d = est.to_dict()
        self.assertIn("band", d)
        self.assertIn("min_bets", d)
        self.assertIn("btc_range_usd", d)
        self.assertEqual(d["btc_range_usd"], 1500.0)

    def test_confidence_is_low_by_default(self):
        est = predict_volume(2000.0, weekday=2)
        self.assertEqual(est.confidence, "LOW")

    def test_zero_range(self):
        est = predict_volume(0.0, weekday=2)
        self.assertEqual(est.band, "LOW")


class TestCalibrationPoint(unittest.TestCase):
    """Test CalibrationPoint data class."""

    def test_create(self):
        pt = CalibrationPoint(
            date="2026-03-24",
            btc_range_usd=2400.0,
            bet_count=67,
            weekday=0,
        )
        self.assertEqual(pt.bet_count, 67)
        self.assertFalse(pt.is_macro_day)

    def test_to_dict(self):
        pt = CalibrationPoint("2026-03-24", 2400.0, 67, 0, True)
        d = pt.to_dict()
        self.assertEqual(d["date"], "2026-03-24")
        self.assertTrue(d["is_macro_day"])


class TestCalibrateFromData(unittest.TestCase):
    """Test calibration from historical data."""

    def _make_points(self, n=10):
        """Generate n synthetic calibration points."""
        import random
        random.seed(42)
        points = []
        for i in range(n):
            btc_range = 500 + i * 300
            bets = int(20 + btc_range * 0.03 + random.gauss(0, 10))
            points.append(CalibrationPoint(
                date=f"2026-03-{i+1:02d}",
                btc_range_usd=float(btc_range),
                bet_count=max(1, bets),
                weekday=i % 7,
            ))
        return points

    def test_calibrate_returns_thresholds(self):
        points = self._make_points(10)
        result = calibrate_from_data(points)
        self.assertIn("range_low_threshold", result)
        self.assertIn("range_high_threshold", result)
        self.assertIn("correlation", result)
        self.assertEqual(result["n"], 10)

    def test_calibrate_too_few_points(self):
        points = self._make_points(3)
        result = calibrate_from_data(points[:3])
        self.assertIn("error", result)

    def test_correlation_positive(self):
        # With linear relationship, correlation should be positive
        points = self._make_points(15)
        result = calibrate_from_data(points)
        self.assertGreater(result["correlation"], 0)

    def test_weekend_multiplier_calculated(self):
        points = self._make_points(10)
        result = calibrate_from_data(points)
        self.assertIn("weekend_multiplier", result)
        self.assertGreater(result["weekend_multiplier"], 0)


class TestLoadCalibrationCSV(unittest.TestCase):
    """Test CSV loading."""

    def test_load_valid_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("date,btc_range_usd,bet_count,weekday,is_macro_day\n")
            f.write("2026-03-24,2400,67,0,false\n")
            f.write("2026-03-25,1500,100,1,true\n")
            path = f.name

        try:
            points = load_calibration_csv(path)
            self.assertEqual(len(points), 2)
            self.assertEqual(points[0].btc_range_usd, 2400.0)
            self.assertEqual(points[1].bet_count, 100)
            self.assertTrue(points[1].is_macro_day)
        finally:
            os.unlink(path)


class TestBacktest(unittest.TestCase):
    """Test backtesting functionality."""

    def test_backtest_returns_metrics(self):
        points = [
            CalibrationPoint("2026-03-24", 2400.0, 67, 0),
            CalibrationPoint("2026-03-25", 1500.0, 100, 1),
            CalibrationPoint("2026-03-16", 3000.0, 136, 6),
        ]
        result = backtest(points)
        self.assertEqual(result["n"], 3)
        self.assertIn("range_accuracy", result)
        self.assertIn("band_accuracy", result)
        self.assertIn("mean_abs_error", result)

    def test_backtest_empty(self):
        result = backtest([])
        self.assertIn("error", result)

    def test_backtest_perfect_match(self):
        # Create points that should fall within predicted ranges
        points = [
            CalibrationPoint("2026-03-01", 800.0, 25, 2),   # LOW band, 25 in range
            CalibrationPoint("2026-03-02", 2000.0, 60, 3),  # MEDIUM band
        ]
        result = backtest(points)
        self.assertGreater(result["range_accuracy"], 0)

    def test_backtest_accuracy_bounded(self):
        points = [CalibrationPoint(f"2026-03-{i:02d}", 1500.0, 30, i % 7) for i in range(1, 8)]
        result = backtest(points)
        self.assertGreaterEqual(result["range_accuracy"], 0.0)
        self.assertLessEqual(result["range_accuracy"], 1.0)
        self.assertGreaterEqual(result["band_accuracy"], 0.0)
        self.assertLessEqual(result["band_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
