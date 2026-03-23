#!/usr/bin/env python3
"""
regime_detector.py — MT-26 Phase 1: Market Regime Detection

Classifies market price data into regimes:
- TRENDING: Sustained directional movement (good for sniper bets)
- MEAN_REVERTING: Oscillating around a center (predictable reversals)
- CHAOTIC: High-volatility erratic movement (skip — edge degrades)
- UNKNOWN: Insufficient data

Uses three statistical metrics (no ML, no external deps):
1. Volatility: Standard deviation of returns (log returns)
2. Trend strength: R-squared of linear regression on prices
3. Mean reversion score: Hurst exponent approximation via R/S analysis

The Kalshi bot can use this to:
- Trade normally in TRENDING regimes (sniper edge is strongest)
- Adjust sizing in MEAN_REVERTING (shorter-term reversals)
- Skip or reduce in CHAOTIC (edge degrades, losses cluster)

Usage:
    from regime_detector import RegimeDetector

    detector = RegimeDetector()
    result = detector.classify(candles)
    # result = {"regime": "TRENDING", "confidence": 0.85,
    #           "metrics": {...}, "advice": "..."}

    # Or from a simple price list:
    result = detector.classify_from_prices([100, 101, 102, ...])

CLI:
    echo '[100, 101, 102, ...]' | python3 regime_detector.py
"""

import math
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metric_config import get_metric


class RegimeDetector:
    """Classifies market regimes from OHLCV candle data."""

    # Thresholds loaded from metric_config (user-overridable via ~/.cca-metrics.json)
    MIN_CANDLES = get_metric("regime_detector.min_candles", 10)
    TREND_THRESHOLD = get_metric("regime_detector.trend_threshold", 0.5)
    CHAOTIC_VOL_THRESHOLD = get_metric("regime_detector.chaotic_vol_threshold", 0.03)
    MR_HURST_THRESHOLD = get_metric("regime_detector.mr_hurst_threshold", 0.4)

    def classify(self, candles):
        """Classify market regime from OHLCV candle data.

        Args:
            candles: List of dicts with 'close', 'high', 'low' keys.
                     Optionally 'volume'. Ordered oldest to newest.

        Returns:
            dict with:
                regime: str — TRENDING, MEAN_REVERTING, CHAOTIC, UNKNOWN
                confidence: float — 0.0 to 1.0
                metrics: dict — volatility, trend_strength, mean_reversion_score
                advice: str — trading recommendation
        """
        if len(candles) < self.MIN_CANDLES:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "metrics": {"volatility": 0.0, "trend_strength": 0.0,
                            "mean_reversion_score": 0.5},
                "advice": "Insufficient data — need at least "
                          f"{self.MIN_CANDLES} candles for regime detection.",
            }

        closes = [c["close"] for c in candles]

        # Compute metrics
        volatility = self._compute_volatility(closes)
        trend_strength = self._compute_trend_strength(closes)
        mr_score = self._compute_hurst_approx(closes)

        metrics = {
            "volatility": round(volatility, 6),
            "trend_strength": round(trend_strength, 4),
            "mean_reversion_score": round(mr_score, 4),
        }

        # Classify regime using decision tree
        regime, confidence = self._classify_regime(
            volatility, trend_strength, mr_score)

        advice = self._generate_advice(regime, confidence, metrics)

        return {
            "regime": regime,
            "confidence": round(confidence, 3),
            "metrics": metrics,
            "advice": advice,
        }

    def classify_from_prices(self, prices):
        """Convenience: classify from a simple list of close prices.

        Args:
            prices: List of float close prices, oldest to newest.

        Returns:
            Same dict as classify().
        """
        candles = [{"close": p, "high": p * 1.005, "low": p * 0.995}
                   for p in prices]
        return self.classify(candles)

    def _compute_volatility(self, closes):
        """Compute annualized volatility from log returns.

        Uses standard deviation of log returns. Higher = more chaotic.
        """
        if len(closes) < 2:
            return 0.0

        log_returns = []
        for i in range(1, len(closes)):
            if closes[i] > 0 and closes[i - 1] > 0:
                log_returns.append(math.log(closes[i] / closes[i - 1]))

        if not log_returns:
            return 0.0

        mean = sum(log_returns) / len(log_returns)
        variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
        return math.sqrt(variance)

    def _compute_trend_strength(self, closes):
        """Compute trend strength via R-squared of linear regression.

        R-squared close to 1.0 = strong linear trend.
        R-squared close to 0.0 = no linear trend (noisy or mean-reverting).
        """
        n = len(closes)
        if n < 2:
            return 0.0

        # Simple linear regression: y = closes, x = 0..n-1
        x_mean = (n - 1) / 2.0
        y_mean = sum(closes) / n

        ss_xy = sum((i - x_mean) * (closes[i] - y_mean) for i in range(n))
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        ss_yy = sum((closes[i] - y_mean) ** 2 for i in range(n))

        if ss_xx == 0 or ss_yy == 0:
            return 0.0

        r = ss_xy / math.sqrt(ss_xx * ss_yy)
        r_squared = r ** 2

        return min(r_squared, 1.0)

    def _compute_hurst_approx(self, closes):
        """Approximate Hurst exponent via rescaled range (R/S) analysis.

        H < 0.5 = mean-reverting
        H = 0.5 = random walk
        H > 0.5 = trending/persistent

        Returns a "mean reversion score" = 1.0 - H (so higher = more MR).
        """
        n = len(closes)
        if n < 10:
            return 0.5  # Not enough data, assume random walk

        # Compute returns
        returns = [closes[i] - closes[i - 1] for i in range(1, n)]
        if not returns:
            return 0.5

        mean_r = sum(returns) / len(returns)

        # Cumulative deviations from mean
        deviations = [r - mean_r for r in returns]
        cumulative = []
        s = 0
        for d in deviations:
            s += d
            cumulative.append(s)

        # Range
        r_range = max(cumulative) - min(cumulative)

        # Standard deviation
        variance = sum(d ** 2 for d in deviations) / len(deviations)
        std = math.sqrt(variance) if variance > 0 else 1e-10

        # R/S ratio
        rs = r_range / std if std > 0 else 0

        # Estimate H: R/S ~ n^H, so H = log(R/S) / log(n)
        if rs > 0 and len(returns) > 1:
            hurst = math.log(rs) / math.log(len(returns))
            hurst = max(0.0, min(1.0, hurst))  # Clamp to [0, 1]
        else:
            hurst = 0.5

        # Return mean reversion score (inverted Hurst)
        return 1.0 - hurst

    def _classify_regime(self, volatility, trend_strength, mr_score):
        """Decision tree for regime classification.

        Returns (regime_str, confidence_float).
        """
        # High volatility + low trend = CHAOTIC
        if volatility > self.CHAOTIC_VOL_THRESHOLD and trend_strength < 0.3:
            confidence = min(volatility / (self.CHAOTIC_VOL_THRESHOLD * 2), 1.0)
            return "CHAOTIC", confidence

        # Strong linear trend = TRENDING
        if trend_strength > self.TREND_THRESHOLD:
            confidence = min(trend_strength, 1.0)
            return "TRENDING", confidence

        # High mean reversion score + low trend = MEAN_REVERTING
        if mr_score > (1.0 - self.MR_HURST_THRESHOLD) and trend_strength < 0.3:
            confidence = min(mr_score, 1.0)
            return "MEAN_REVERTING", confidence

        # Default: check which signal is strongest
        if trend_strength > mr_score and trend_strength > 0.3:
            return "TRENDING", trend_strength * 0.7
        if mr_score > 0.6:
            return "MEAN_REVERTING", mr_score * 0.7

        # Moderate volatility, no clear signal
        return "MEAN_REVERTING", 0.4

    def _generate_advice(self, regime, confidence, metrics):
        """Generate trading advice based on regime."""
        if regime == "TRENDING":
            return (f"Trade normally — strong trend detected "
                    f"(R²={metrics['trend_strength']:.2f}). "
                    f"Sniper edge is strongest in trending regimes.")

        if regime == "MEAN_REVERTING":
            return (f"Trade with caution — mean-reverting regime "
                    f"(MR={metrics['mean_reversion_score']:.2f}). "
                    f"Consider shorter holding periods.")

        if regime == "CHAOTIC":
            return (f"Skip or reduce position sizes — chaotic regime detected "
                    f"(vol={metrics['volatility']:.4f}). "
                    f"Edge degrades and losses cluster in high volatility.")

        return (f"Insufficient data — need at least {self.MIN_CANDLES} "
                f"candles for regime detection.")


def _cli():
    """CLI: pipe JSON price list to classify."""
    import argparse
    parser = argparse.ArgumentParser(description="Market Regime Detector")
    parser.add_argument("--prices", type=str,
                        help="JSON array of close prices")
    args = parser.parse_args()

    if args.prices:
        prices = json.loads(args.prices)
    else:
        # Read from stdin
        data = sys.stdin.read().strip()
        if data:
            prices = json.loads(data)
        else:
            print("Usage: echo '[100, 101, ...]' | python3 regime_detector.py")
            sys.exit(1)

    detector = RegimeDetector()
    result = detector.classify_from_prices(prices)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
