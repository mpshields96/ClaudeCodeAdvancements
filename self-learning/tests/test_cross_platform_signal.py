#!/usr/bin/env python3
"""
Tests for cross_platform_signal.py — MT-26 Phase 1: Cross-Platform Signal

Tests price divergence detection, signal generation, and lag analysis
between prediction market platforms (Polymarket/Kalshi).
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cross_platform_signal import (
    PriceObservation,
    DivergenceSignal,
    CrossPlatformSignal,
    SignalDirection,
)


class TestSignalDirection(unittest.TestCase):
    """SignalDirection enum values."""

    def test_enum_values(self):
        self.assertEqual(SignalDirection.KALSHI_HIGHER.value, "kalshi_higher")
        self.assertEqual(SignalDirection.POLYMARKET_HIGHER.value, "polymarket_higher")
        self.assertEqual(SignalDirection.CONVERGED.value, "converged")


class TestPriceObservation(unittest.TestCase):
    """PriceObservation dataclass."""

    def test_creation(self):
        obs = PriceObservation(
            platform="kalshi",
            contract_id="BTC-UP-100K",
            price=0.65,
            timestamp="2026-03-21T10:00:00Z",
        )
        self.assertEqual(obs.platform, "kalshi")
        self.assertEqual(obs.price, 0.65)

    def test_to_dict(self):
        obs = PriceObservation(
            platform="polymarket",
            contract_id="BTC-UP-100K",
            price=0.70,
            timestamp="2026-03-21T10:00:00Z",
        )
        d = obs.to_dict()
        self.assertEqual(d["platform"], "polymarket")
        self.assertEqual(d["price"], 0.70)


class TestDivergenceSignal(unittest.TestCase):
    """DivergenceSignal dataclass."""

    def test_creation(self):
        sig = DivergenceSignal(
            contract_id="BTC-UP-100K",
            kalshi_price=0.60,
            polymarket_price=0.68,
            divergence=0.08,
            direction=SignalDirection.POLYMARKET_HIGHER,
            confidence=0.75,
            timestamp="2026-03-21T10:00:00Z",
            actionable=True,
        )
        self.assertEqual(sig.divergence, 0.08)
        self.assertTrue(sig.actionable)

    def test_to_dict(self):
        sig = DivergenceSignal(
            contract_id="BTC-UP-100K",
            kalshi_price=0.60,
            polymarket_price=0.68,
            divergence=0.08,
            direction=SignalDirection.POLYMARKET_HIGHER,
            confidence=0.75,
            timestamp="2026-03-21T10:00:00Z",
            actionable=True,
        )
        d = sig.to_dict()
        self.assertEqual(d["direction"], "polymarket_higher")
        self.assertIn("divergence", d)


class TestCrossPlatformSignalInit(unittest.TestCase):
    """Initialization."""

    def test_default_init(self):
        cps = CrossPlatformSignal()
        self.assertGreater(cps.min_divergence, 0)
        self.assertGreater(cps.lookback_window, 0)

    def test_custom_thresholds(self):
        cps = CrossPlatformSignal(min_divergence=0.05, lookback_window=60)
        self.assertEqual(cps.min_divergence, 0.05)
        self.assertEqual(cps.lookback_window, 60)

    def test_invalid_divergence(self):
        with self.assertRaises(ValueError):
            CrossPlatformSignal(min_divergence=-0.01)

    def test_invalid_lookback(self):
        with self.assertRaises(ValueError):
            CrossPlatformSignal(lookback_window=0)


class TestAddObservation(unittest.TestCase):
    """Adding price observations."""

    def setUp(self):
        self.cps = CrossPlatformSignal()

    def test_add_single(self):
        self.cps.add_observation(
            platform="kalshi",
            contract_id="BTC-UP-100K",
            price=0.65,
            timestamp="2026-03-21T10:00:00Z",
        )
        self.assertEqual(len(self.cps.observations), 1)

    def test_add_multiple_platforms(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.70, "2026-03-21T10:00:00Z")
        self.assertEqual(len(self.cps.observations), 2)

    def test_invalid_platform(self):
        with self.assertRaises(ValueError):
            self.cps.add_observation("binance", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")

    def test_invalid_price_range(self):
        with self.assertRaises(ValueError):
            self.cps.add_observation("kalshi", "BTC-UP", 1.5, "2026-03-21T10:00:00Z")
        with self.assertRaises(ValueError):
            self.cps.add_observation("kalshi", "BTC-UP", -0.1, "2026-03-21T10:00:00Z")

    def test_add_batch(self):
        observations = [
            {"platform": "kalshi", "contract_id": "BTC-UP", "price": 0.65,
             "timestamp": "2026-03-21T10:00:00Z"},
            {"platform": "polymarket", "contract_id": "BTC-UP", "price": 0.70,
             "timestamp": "2026-03-21T10:00:00Z"},
        ]
        self.cps.add_batch(observations)
        self.assertEqual(len(self.cps.observations), 2)


class TestDetectDivergence(unittest.TestCase):
    """Detecting price divergence between platforms."""

    def setUp(self):
        self.cps = CrossPlatformSignal(min_divergence=0.03)

    def test_no_divergence_when_prices_close(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.66, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        actionable = [s for s in signals if s.actionable]
        self.assertEqual(len(actionable), 0)

    def test_divergence_detected(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.60, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.70, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        actionable = [s for s in signals if s.actionable]
        self.assertGreater(len(actionable), 0)

    def test_divergence_direction_polymarket_higher(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        self.assertEqual(signals[0].direction, SignalDirection.POLYMARKET_HIGHER)

    def test_divergence_direction_kalshi_higher(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.70, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.60, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        self.assertEqual(signals[0].direction, SignalDirection.KALSHI_HIGHER)

    def test_single_platform_no_signal(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        self.assertEqual(len(signals), 0)

    def test_divergence_magnitude(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        self.assertAlmostEqual(signals[0].divergence, 0.10, places=2)

    def test_multiple_timepoints(self):
        # Two different timestamps
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        self.cps.add_observation("kalshi", "BTC-UP", 0.60, "2026-03-21T10:05:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.68, "2026-03-21T10:05:00Z")
        signals = self.cps.detect_divergences(contract_id="BTC-UP")
        self.assertGreater(len(signals), 0)


class TestLagAnalysis(unittest.TestCase):
    """Analyzing which platform leads in price discovery."""

    def setUp(self):
        self.cps = CrossPlatformSignal(min_divergence=0.03)

    def test_polymarket_leads(self):
        # Polymarket moves first, Kalshi follows
        self.cps.add_observation("polymarket", "BTC-UP", 0.60, "2026-03-21T10:00:00Z")
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:05:00Z")
        self.cps.add_observation("kalshi", "BTC-UP", 0.58, "2026-03-21T10:05:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:10:00Z")
        self.cps.add_observation("kalshi", "BTC-UP", 0.64, "2026-03-21T10:10:00Z")

        analysis = self.cps.analyze_lag(contract_id="BTC-UP")
        self.assertIn("leader", analysis)

    def test_lag_returns_dict(self):
        self.cps.add_observation("polymarket", "BTC-UP", 0.60, "2026-03-21T10:00:00Z")
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        analysis = self.cps.analyze_lag(contract_id="BTC-UP")
        self.assertIsInstance(analysis, dict)
        self.assertIn("leader", analysis)
        self.assertIn("avg_divergence", analysis)
        self.assertIn("n_observations", analysis)

    def test_insufficient_data(self):
        analysis = self.cps.analyze_lag(contract_id="BTC-UP")
        self.assertEqual(analysis["leader"], "unknown")


class TestGetSignals(unittest.TestCase):
    """Getting actionable signals for the Kalshi bot."""

    def setUp(self):
        self.cps = CrossPlatformSignal(min_divergence=0.03)

    def test_get_actionable_signals(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        signals = self.cps.get_actionable_signals()
        self.assertIsInstance(signals, list)

    def test_signals_are_divergence_signals(self):
        self.cps.add_observation("kalshi", "BTC-UP", 0.55, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        signals = self.cps.get_actionable_signals()
        for s in signals:
            self.assertIsInstance(s, DivergenceSignal)
            self.assertTrue(s.actionable)

    def test_no_signals_when_no_data(self):
        signals = self.cps.get_actionable_signals()
        self.assertEqual(len(signals), 0)


class TestSaveLoad(unittest.TestCase):
    """Persistence."""

    def setUp(self):
        self.cps = CrossPlatformSignal(min_divergence=0.03)
        self.cps.add_observation("kalshi", "BTC-UP", 0.65, "2026-03-21T10:00:00Z")
        self.cps.add_observation("polymarket", "BTC-UP", 0.70, "2026-03-21T10:00:00Z")

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.cps.save(path)
            cps2 = CrossPlatformSignal.load(path)
            self.assertEqual(len(cps2.observations), 2)
        finally:
            os.unlink(path)

    def test_save_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.cps.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("observations", data)
            self.assertIn("min_divergence", data)
        finally:
            os.unlink(path)

    def test_load_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            CrossPlatformSignal.load("/tmp/nonexistent_signal.json")


if __name__ == "__main__":
    unittest.main()
