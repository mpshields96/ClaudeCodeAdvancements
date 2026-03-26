#!/usr/bin/env python3
"""Tests for correlated_loss_analyzer.py — REQ-054: Cross-asset loss correlation detection."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from correlated_loss_analyzer import (
    CorrelationResult,
    LossCluster,
    LossEvent,
    WindowAnalyzer,
    coincidence_rate,
    expected_coincidence,
    loss_clusters,
)


class TestLossEvent(unittest.TestCase):
    """Test LossEvent data model."""

    def test_creation(self):
        ev = LossEvent(
            ticker="BTC", amount=-5.0,
            timestamp=datetime(2026, 3, 25, 14, 30),
        )
        self.assertEqual(ev.ticker, "BTC")
        self.assertLess(ev.amount, 0)

    def test_to_dict(self):
        ev = LossEvent(ticker="ETH", amount=-3.5,
                       timestamp=datetime(2026, 3, 25, 15, 0))
        d = ev.to_dict()
        self.assertIn("ticker", d)
        self.assertIn("amount", d)


class TestCoincidenceRate(unittest.TestCase):
    """Test raw coincidence rate calculation."""

    def test_fully_correlated(self):
        # BTC and ETH lose at the exact same times
        btc = [datetime(2026, 3, 25, i, 0) for i in range(10)]
        eth = [datetime(2026, 3, 25, i, 0) for i in range(10)]
        rate = coincidence_rate(btc, eth, window_minutes=60)
        self.assertAlmostEqual(rate, 1.0)

    def test_no_overlap(self):
        btc = [datetime(2026, 3, 25, i, 0) for i in range(5)]
        eth = [datetime(2026, 3, 26, i, 0) for i in range(5)]
        rate = coincidence_rate(btc, eth, window_minutes=60)
        self.assertAlmostEqual(rate, 0.0)

    def test_partial_overlap(self):
        btc = [datetime(2026, 3, 25, i, 0) for i in range(10)]
        eth = [datetime(2026, 3, 25, i, 0) for i in range(5)]  # Only first 5 overlap
        rate = coincidence_rate(btc, eth, window_minutes=60)
        self.assertGreater(rate, 0)
        self.assertLessEqual(rate, 1.0)

    def test_empty_input(self):
        rate = coincidence_rate([], [], window_minutes=60)
        self.assertEqual(rate, 0.0)

    def test_one_empty(self):
        btc = [datetime(2026, 3, 25, 10, 0)]
        rate = coincidence_rate(btc, [], window_minutes=60)
        self.assertEqual(rate, 0.0)


class TestExpectedCoincidence(unittest.TestCase):
    """Test expected coincidence under independence assumption."""

    def test_independent_baseline(self):
        # If BTC loses 10% of the time and ETH loses 10%, expected overlap = 1%
        rate = expected_coincidence(btc_loss_rate=0.10, eth_loss_rate=0.10)
        self.assertAlmostEqual(rate, 0.01)

    def test_high_rates(self):
        rate = expected_coincidence(btc_loss_rate=0.50, eth_loss_rate=0.50)
        self.assertAlmostEqual(rate, 0.25)

    def test_zero_rate(self):
        rate = expected_coincidence(btc_loss_rate=0.0, eth_loss_rate=0.10)
        self.assertAlmostEqual(rate, 0.0)


class TestLossClusters(unittest.TestCase):
    """Test loss event clustering."""

    def test_cluster_same_window(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 14, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 14, 10)),
        ]
        clusters = loss_clusters(events, window_minutes=30)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].events), 2)

    def test_separate_windows(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 10, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 15, 0)),
        ]
        clusters = loss_clusters(events, window_minutes=30)
        self.assertEqual(len(clusters), 2)

    def test_empty_events(self):
        clusters = loss_clusters([], window_minutes=30)
        self.assertEqual(len(clusters), 0)

    def test_cluster_total_loss(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 14, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 14, 10)),
            LossEvent("SOL", -2.0, datetime(2026, 3, 25, 14, 20)),
        ]
        clusters = loss_clusters(events, window_minutes=30)
        self.assertEqual(len(clusters), 1)
        self.assertAlmostEqual(clusters[0].total_loss, -10.0)

    def test_multi_asset_cluster(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 14, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 14, 5)),
        ]
        clusters = loss_clusters(events, window_minutes=30)
        self.assertEqual(clusters[0].asset_count, 2)


class TestWindowAnalyzer(unittest.TestCase):
    """Test the full window analyzer."""

    def test_analyze_correlated_losses(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 10, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 10, 5)),
            LossEvent("BTC", -4.0, datetime(2026, 3, 25, 14, 0)),
            LossEvent("ETH", -2.5, datetime(2026, 3, 25, 14, 10)),
            LossEvent("BTC", -6.0, datetime(2026, 3, 25, 20, 0)),
        ]
        analyzer = WindowAnalyzer(window_minutes=30)
        result = analyzer.analyze(events)
        self.assertIsInstance(result, CorrelationResult)
        self.assertGreater(result.coincidence_rate, 0)

    def test_analyze_no_events(self):
        analyzer = WindowAnalyzer()
        result = analyzer.analyze([])
        self.assertEqual(result.coincidence_rate, 0.0)

    def test_result_to_dict(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 10, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 10, 5)),
        ]
        analyzer = WindowAnalyzer()
        result = analyzer.analyze(events)
        d = result.to_dict()
        self.assertIn("coincidence_rate", d)
        self.assertIn("clusters", d)
        self.assertIn("recommendation", d)

    def test_result_summary_text(self):
        events = [
            LossEvent("BTC", -5.0, datetime(2026, 3, 25, 10, 0)),
            LossEvent("ETH", -3.0, datetime(2026, 3, 25, 10, 5)),
        ]
        analyzer = WindowAnalyzer()
        result = analyzer.analyze(events)
        text = result.summary_text()
        self.assertIsInstance(text, str)

    def test_recommendation_correlated(self):
        # Force high correlation
        events = []
        for i in range(20):
            t = datetime(2026, 3, 25, 10, 0) + timedelta(hours=i)
            events.append(LossEvent("BTC", -5.0, t))
            events.append(LossEvent("ETH", -3.0, t + timedelta(minutes=5)))
        analyzer = WindowAnalyzer(window_minutes=30)
        result = analyzer.analyze(events)
        # Should recommend staggering or reducing concurrent exposure
        self.assertIn("stagger", result.recommendation.lower())


if __name__ == "__main__":
    unittest.main()
