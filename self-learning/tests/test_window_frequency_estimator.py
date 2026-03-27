"""Tests for window_frequency_estimator.py — market window frequency analysis.

Calculates theoretical max bet frequency from market structure (window
duration, assets, hours of operation) and compares against observed rates.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from window_frequency_estimator import (
    MarketConfig,
    FrequencyEstimate,
    WindowFrequencyEstimator,
    ObservedRate,
)


class TestMarketConfig(unittest.TestCase):
    """Test market configuration."""

    def test_15min_windows_per_day(self):
        m = MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24)
        self.assertEqual(m.windows_per_day(), 96)

    def test_hourly_windows(self):
        m = MarketConfig(name="KXBTCD", window_minutes=60, hours_per_day=24)
        self.assertEqual(m.windows_per_day(), 24)

    def test_partial_day(self):
        m = MarketConfig(name="HIGHNY", window_minutes=1440, hours_per_day=24)
        self.assertEqual(m.windows_per_day(), 1)

    def test_custom_hours(self):
        m = MarketConfig(name="test", window_minutes=15, hours_per_day=12)
        self.assertEqual(m.windows_per_day(), 48)


class TestObservedRate(unittest.TestCase):
    """Test observed rate calculations."""

    def test_signal_rate(self):
        o = ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14)
        self.assertAlmostEqual(o.bets_per_day(), 312 / 14)

    def test_signal_rate_fraction(self):
        o = ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14,
                         total_windows=96 * 14)
        self.assertAlmostEqual(o.signal_fire_rate(), 312 / (96 * 14), places=4)

    def test_zero_days(self):
        o = ObservedRate(market="KXBTC15M", total_bets=0, days_observed=0)
        self.assertAlmostEqual(o.bets_per_day(), 0.0)


class TestWindowFrequencyEstimator(unittest.TestCase):
    """Test the estimator with multiple markets."""

    def _default_estimator(self):
        markets = [
            MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
            MarketConfig(name="KXETH15M", window_minutes=15, hours_per_day=24),
            MarketConfig(name="KXSOL15M", window_minutes=15, hours_per_day=24),
        ]
        observed = [
            ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14),
            ObservedRate(market="KXETH15M", total_bets=314, days_observed=14),
            ObservedRate(market="KXSOL15M", total_bets=277, days_observed=14),
        ]
        return WindowFrequencyEstimator(markets, observed)

    def test_total_theoretical_windows(self):
        est = self._default_estimator()
        report = est.estimate()
        # 3 markets * 96 windows = 288
        self.assertEqual(report.total_theoretical_windows, 288)

    def test_total_observed_bets_per_day(self):
        est = self._default_estimator()
        report = est.estimate()
        expected = (312 + 314 + 277) / 14
        self.assertAlmostEqual(report.total_observed_bets_per_day, expected, places=1)

    def test_signal_utilization(self):
        est = self._default_estimator()
        report = est.estimate()
        # ~64.5 bets/day out of 288 windows = ~22.4%
        self.assertGreater(report.signal_utilization, 0.15)
        self.assertLess(report.signal_utilization, 0.35)

    def test_per_market_breakdown(self):
        est = self._default_estimator()
        report = est.estimate()
        self.assertEqual(len(report.per_market), 3)
        btc = [m for m in report.per_market if m["market"] == "KXBTC15M"][0]
        self.assertAlmostEqual(btc["observed_bets_per_day"], 312 / 14, places=1)

    def test_ev_at_various_frequencies(self):
        est = self._default_estimator()
        report = est.estimate(win_rate=0.933, avg_win=0.90, avg_loss=8.0)
        self.assertIn("ev_table", report.__dict__)
        self.assertGreater(len(report.ev_table), 0)
        # At 64 bets/day, EV should be positive
        ev_64 = [e for e in report.ev_table if e["bets_per_day"] == 64]
        if ev_64:
            self.assertGreater(ev_64[0]["expected_daily_pnl"], 0)

    def test_empty_observed(self):
        markets = [
            MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
        ]
        est = WindowFrequencyEstimator(markets, [])
        report = est.estimate()
        self.assertEqual(report.total_theoretical_windows, 96)
        self.assertAlmostEqual(report.total_observed_bets_per_day, 0.0)

    def test_with_xrp_excluded(self):
        markets = [
            MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
            MarketConfig(name="KXETH15M", window_minutes=15, hours_per_day=24),
            MarketConfig(name="KXSOL15M", window_minutes=15, hours_per_day=24),
        ]
        # Only 3 markets, no XRP
        observed = [
            ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14),
            ObservedRate(market="KXETH15M", total_bets=314, days_observed=14),
            ObservedRate(market="KXSOL15M", total_bets=277, days_observed=14),
        ]
        est = WindowFrequencyEstimator(markets, observed)
        report = est.estimate()
        self.assertEqual(report.total_theoretical_windows, 288)  # 3 * 96

    def test_capacity_headroom(self):
        est = self._default_estimator()
        report = est.estimate()
        # Headroom = theoretical - observed
        self.assertGreater(report.capacity_headroom, 200)


class TestWindowFrequencyEstimatorJSON(unittest.TestCase):
    """Test JSON export."""

    def test_to_dict(self):
        markets = [
            MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
        ]
        observed = [
            ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14),
        ]
        est = WindowFrequencyEstimator(markets, observed)
        d = est.to_dict()
        self.assertIn("markets", d)
        self.assertIn("estimate", d)

    def test_summary_text(self):
        markets = [
            MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
        ]
        observed = [
            ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14),
        ]
        est = WindowFrequencyEstimator(markets, observed)
        text = est.summary_text()
        self.assertIn("KXBTC15M", text)
        self.assertIn("96", text)


if __name__ == "__main__":
    unittest.main()
