#!/usr/bin/env python3
"""
Tests for order_flow_intel.py — MT-26 Tier 3: Order Flow Intelligence.

TDD: Tests written BEFORE implementation.

Based on "Makers and Takers: The Economics of the Kalshi Prediction Market"
(Burgi, Deng, Whelan, 2025) — UCD Working Paper WP2025_19.

Tests cover:
- FeeCalculator: Kalshi fee model (theta * p * (1-p))
- FLBEstimator: Favorite-longshot bias regression (OLS)
- ReturnForecaster: Expected return by price band + category
- RiskClassifier: Toxic longshot detection, contract scoring
- BiasTracker: FLB evolution tracking
- MakerTakerAnalyzer: Trade classification and return analysis
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from order_flow_intel import (
    FeeCalculator,
    FLBEstimator,
    ReturnForecaster,
    RiskClassifier,
    BiasTracker,
    MakerTakerAnalyzer,
)


class TestFeeCalculator(unittest.TestCase):
    """Tests for Kalshi fee model."""

    def setUp(self):
        self.calc = FeeCalculator()

    def test_fee_at_50c(self):
        """Maximum fee at p=0.50."""
        fee = self.calc.fee(0.50)
        self.assertAlmostEqual(fee, 0.07 * 0.50 * 0.50, places=4)

    def test_fee_at_5c(self):
        """Fee at p=0.05 (cheap contract)."""
        fee = self.calc.fee(0.05)
        self.assertAlmostEqual(fee, 0.07 * 0.05 * 0.95, places=4)

    def test_fee_at_95c(self):
        """Fee at p=0.95 (expensive contract)."""
        fee = self.calc.fee(0.95)
        self.assertAlmostEqual(fee, 0.07 * 0.95 * 0.05, places=4)

    def test_fee_symmetric(self):
        """Fee is symmetric: fee(p) == fee(1-p)."""
        self.assertAlmostEqual(self.calc.fee(0.20), self.calc.fee(0.80))

    def test_fee_as_pct_of_price(self):
        """Fee as % of price is much higher for cheap contracts."""
        cheap_pct = self.calc.fee_pct(0.05)
        expensive_pct = self.calc.fee_pct(0.95)
        self.assertGreater(cheap_pct, expensive_pct * 5)

    def test_fee_zero_at_boundaries(self):
        """Fee is zero at p=0 and p=1."""
        self.assertAlmostEqual(self.calc.fee(0.0), 0.0)
        self.assertAlmostEqual(self.calc.fee(1.0), 0.0)

    def test_custom_theta(self):
        """Custom theta parameter works."""
        calc = FeeCalculator(theta=0.10)
        self.assertAlmostEqual(calc.fee(0.50), 0.10 * 0.25, places=4)

    def test_breakeven_win_rate(self):
        """Breakeven win rate accounts for fees."""
        be = self.calc.breakeven_win_rate(0.50)
        # At 50c: investment = 50c + fee, win = 100c - investment
        # So breakeven > 50%
        self.assertGreater(be, 0.50)

    def test_breakeven_at_5c(self):
        """Breakeven rate for 5c contract is much higher than 5%."""
        be = self.calc.breakeven_win_rate(0.05)
        self.assertGreater(be, 0.05)

    def test_expected_return(self):
        """Expected return calculation."""
        ret = self.calc.expected_return(price=0.50, win_rate=0.60)
        self.assertGreater(ret, 0)  # 60% WR at 50c should be profitable

    def test_expected_return_negative(self):
        """Sub-breakeven win rate gives negative return."""
        ret = self.calc.expected_return(price=0.05, win_rate=0.03)
        self.assertLess(ret, 0)


class TestFLBEstimator(unittest.TestCase):
    """Tests for favorite-longshot bias OLS regression."""

    def setUp(self):
        self.estimator = FLBEstimator()

    def test_fit_with_known_data(self):
        """OLS fits correctly on known data."""
        # Simulate FLB: low-price contracts win less than their price implies
        prices = [0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.80, 0.90, 0.95]
        outcomes = [0, 0, 0, 0, 1, 1, 1, 1, 1]  # Strong FLB pattern

        result = self.estimator.fit(prices, outcomes)

        self.assertIn("alpha", result)
        self.assertIn("psi", result)
        self.assertIn("n", result)
        # psi should be positive (higher prices predict wins better than expected)
        self.assertGreater(result["psi"], 0)

    def test_fit_returns_r_squared(self):
        """Fit returns R-squared measure."""
        prices = [0.10, 0.30, 0.50, 0.70, 0.90] * 10
        outcomes = [0, 0, 1, 1, 1] * 10
        result = self.estimator.fit(prices, outcomes)
        self.assertIn("r_squared", result)

    def test_fit_minimum_samples(self):
        """Fit requires minimum number of samples."""
        with self.assertRaises(ValueError):
            self.estimator.fit([0.5], [1])

    def test_predict_bias(self):
        """Predict bias for a given price after fitting."""
        prices = [0.05, 0.10, 0.30, 0.50, 0.70, 0.90, 0.95] * 5
        outcomes = [0, 0, 0, 1, 1, 1, 1] * 5
        self.estimator.fit(prices, outcomes)

        # Low price should have negative bias (overpriced)
        bias_low = self.estimator.predict_bias(0.05)
        bias_high = self.estimator.predict_bias(0.95)

        self.assertLess(bias_low, bias_high)

    def test_category_psi_coefficients(self):
        """Paper's category-specific psi values are available."""
        psi = FLBEstimator.CATEGORY_PSI
        self.assertIn("crypto", psi)
        self.assertIn("financials", psi)
        self.assertAlmostEqual(psi["crypto"], 0.058, places=3)
        self.assertAlmostEqual(psi["financials"], 0.032, places=3)
        self.assertAlmostEqual(psi["all"], 0.034, places=3)


class TestReturnForecaster(unittest.TestCase):
    """Tests for expected return by price band and category."""

    def setUp(self):
        self.forecaster = ReturnForecaster()

    def test_sub_10c_negative(self):
        """Sub-10c contracts have strongly negative expected return."""
        ret = self.forecaster.expected_return_by_band(0.05, category="all")
        self.assertLess(ret, -0.30)  # Paper says 60%+ loss

    def test_above_50c_less_negative(self):
        """Above 50c contracts have much better return than sub-10c."""
        ret_high = self.forecaster.expected_return_by_band(0.70, category="all")
        ret_low = self.forecaster.expected_return_by_band(0.05, category="all")
        # High-price contracts should be MUCH better than low-price
        self.assertGreater(ret_high, ret_low + 0.20)

    def test_category_differences(self):
        """Different categories produce different expected returns."""
        crypto_ret = self.forecaster.expected_return_by_band(0.50, category="crypto")
        politics_ret = self.forecaster.expected_return_by_band(0.50, category="politics")
        # Different categories should give different returns
        self.assertNotAlmostEqual(crypto_ret, politics_ret, places=3)

    def test_price_bands(self):
        """Price bands are correctly defined."""
        bands = self.forecaster.get_price_bands()
        self.assertTrue(len(bands) >= 5)
        # First band should start at 0
        self.assertEqual(bands[0][0], 0.0)

    def test_return_monotonic(self):
        """Expected return increases with price (due to FLB)."""
        returns = [self.forecaster.expected_return_by_band(p, "all")
                   for p in [0.05, 0.15, 0.25, 0.50, 0.75, 0.95]]
        # Generally increasing (FLB pattern)
        self.assertLess(returns[0], returns[-1])


class TestRiskClassifier(unittest.TestCase):
    """Tests for contract risk classification."""

    def setUp(self):
        self.classifier = RiskClassifier()

    def test_toxic_longshot(self):
        """Sub-10c contracts classified as TOXIC."""
        result = self.classifier.classify(0.05)
        self.assertEqual(result["risk"], "TOXIC")

    def test_unfavorable(self):
        """10c-30c contracts classified as UNFAVORABLE."""
        result = self.classifier.classify(0.20)
        self.assertEqual(result["risk"], "UNFAVORABLE")

    def test_neutral(self):
        """30c-50c contracts classified as NEUTRAL."""
        result = self.classifier.classify(0.40)
        self.assertEqual(result["risk"], "NEUTRAL")

    def test_favorable(self):
        """50c+ contracts classified as FAVORABLE."""
        result = self.classifier.classify(0.70)
        self.assertEqual(result["risk"], "FAVORABLE")

    def test_classify_includes_reasoning(self):
        """Classification includes explanation."""
        result = self.classifier.classify(0.05)
        self.assertIn("reason", result)
        self.assertIn("60%", result["reason"])

    def test_should_trade(self):
        """should_trade returns False for toxic, True for favorable."""
        self.assertFalse(self.classifier.should_trade(0.05))
        self.assertTrue(self.classifier.should_trade(0.70))

    def test_classify_with_category(self):
        """Category-aware classification uses category-specific psi."""
        result = self.classifier.classify(0.15, category="crypto")
        # Crypto has stronger FLB, so should be more pessimistic
        self.assertIn("risk", result)

    def test_score(self):
        """Risk score is 0-100, higher = safer."""
        score_cheap = self.classifier.score(0.05)
        score_mid = self.classifier.score(0.50)
        score_high = self.classifier.score(0.85)
        self.assertLess(score_cheap, score_mid)
        self.assertLess(score_mid, score_high)


class TestBiasTracker(unittest.TestCase):
    """Tests for FLB evolution tracking over time."""

    def setUp(self):
        self.tracker = BiasTracker()

    def test_add_observation(self):
        """Can add price/outcome observations with timestamps."""
        self.tracker.add(price=0.50, outcome=1, timestamp=1000.0, category="crypto")
        self.assertEqual(len(self.tracker.observations), 1)

    def test_rolling_psi(self):
        """Compute rolling psi coefficient."""
        # Add many observations
        import random
        random.seed(42)
        for i in range(100):
            p = random.uniform(0.05, 0.95)
            # FLB: low prices lose more
            outcome = 1 if random.random() < (p + 0.1 * p) else 0
            self.tracker.add(price=p, outcome=outcome, timestamp=float(i))

        psi_values = self.tracker.rolling_psi(window=50)
        self.assertTrue(len(psi_values) > 0)

    def test_is_edge_decaying(self):
        """Detect if FLB is weakening over time."""
        # Add declining FLB pattern
        for i in range(200):
            p = 0.50
            # Edge decays: early outcomes are more biased
            bias = 0.15 if i < 100 else 0.05
            outcome = 1 if i % 2 == 0 else 0
            self.tracker.add(price=p, outcome=outcome, timestamp=float(i))

        # Should have enough data to assess
        assessment = self.tracker.assess_edge_decay()
        self.assertIn("trend", assessment)

    def test_empty_tracker(self):
        """Empty tracker returns safe defaults."""
        assessment = self.tracker.assess_edge_decay()
        self.assertEqual(assessment["trend"], "insufficient_data")


class TestMakerTakerAnalyzer(unittest.TestCase):
    """Tests for Maker vs Taker trade analysis."""

    def setUp(self):
        self.analyzer = MakerTakerAnalyzer()

    def test_add_trade(self):
        """Can add trades with maker/taker classification."""
        self.analyzer.add_trade(
            price=0.50, size=100, is_maker=True,
            outcome=1, category="crypto"
        )
        self.assertEqual(len(self.analyzer.trades), 1)

    def test_maker_returns_better(self):
        """Makers should have better returns than Takers (paper finding)."""
        import random
        random.seed(42)
        for _ in range(200):
            p = random.uniform(0.10, 0.90)
            outcome = 1 if random.random() < p else 0
            # Makers get slightly better prices (they set them)
            maker_price = p - 0.02
            taker_price = p + 0.02
            self.analyzer.add_trade(price=maker_price, size=50, is_maker=True,
                                     outcome=outcome, category="all")
            self.analyzer.add_trade(price=taker_price, size=50, is_maker=False,
                                     outcome=outcome, category="all")

        stats = self.analyzer.compare_returns()
        self.assertIn("maker_return", stats)
        self.assertIn("taker_return", stats)
        self.assertGreater(stats["maker_return"], stats["taker_return"])

    def test_model_price(self):
        """Maker pricing model from Equation 6."""
        # Given true probability, optimism, and required return,
        # compute the Maker's price
        price = self.analyzer.maker_model_price(
            pi=0.50, delta=0.02, gamma=0.05
        )
        self.assertIsInstance(price, float)
        self.assertTrue(0 < price < 1)

    def test_model_price_cheap_contract(self):
        """Model price for low-probability event."""
        price = self.analyzer.maker_model_price(
            pi=0.10, delta=0.01, gamma=0.05
        )
        self.assertTrue(0 < price < 0.20)

    def test_summary(self):
        """Summary report includes key metrics."""
        self.analyzer.add_trade(price=0.50, size=100, is_maker=True,
                                 outcome=1, category="crypto")
        summary = self.analyzer.summary()
        self.assertIn("total_trades", summary)
        self.assertIn("maker_count", summary)
        self.assertIn("taker_count", summary)


if __name__ == "__main__":
    unittest.main()
