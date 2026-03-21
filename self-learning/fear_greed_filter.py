#!/usr/bin/env python3
"""
fear_greed_filter.py — MT-26 Tier 2: Fear & Greed Contrarian Filter

Uses the Alternative.me Fear & Greed Index value as a signal quality modifier.
At sentiment extremes, crypto direction becomes more predictable:
- Extreme fear (<= 20): Mean reversion expected — contrarian long bias
- Extreme greed (>= 80): Correction expected — contrarian short bias
- Neutral (40-60): No directional bias

This module does NOT call external APIs. The bot provides the F&G value
(0-100 integer), this module provides the interpretation.

Output:
- SentimentZone classification
- Direction bias (UP/DOWN/NONE)
- Sizing modifier (0.5 to 1.5)
- Confidence score (0.0 to 1.0)

Usage:
    from fear_greed_filter import FearGreedFilter

    fgf = FearGreedFilter()
    signal = fgf.classify(fg_value=12)
    # signal.zone = EXTREME_FEAR
    # signal.direction_bias = "UP"
    # signal.sizing_modifier = 1.2
    # signal.confidence = 0.75

    # With trend context for stronger signals
    signal = fgf.classify_with_trend(fg_value=12, trend="UP")

Zero external dependencies. Stdlib only.
"""

import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class SentimentZone(Enum):
    """Fear & Greed sentiment zones."""
    EXTREME_FEAR = "EXTREME_FEAR"      # 0-20
    FEAR = "FEAR"                       # 21-40
    NEUTRAL = "NEUTRAL"                 # 41-60
    GREED = "GREED"                     # 61-80
    EXTREME_GREED = "EXTREME_GREED"     # 81-100


@dataclass
class SentimentSignal:
    """Output of the fear & greed filter."""
    zone: SentimentZone
    fg_value: int
    sizing_modifier: float      # 0.5 to 1.5
    direction_bias: str         # UP, DOWN, SLIGHT_UP, SLIGHT_DOWN, NONE
    confidence: float           # 0.0 to 1.0
    advice: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone": self.zone.value,
            "fg_value": self.fg_value,
            "sizing_modifier": round(self.sizing_modifier, 3),
            "direction_bias": self.direction_bias,
            "confidence": round(self.confidence, 3),
            "advice": self.advice,
        }


class FearGreedFilter:
    """Classifies Fear & Greed Index values into actionable signals.

    Default thresholds (Alternative.me convention):
        0-20:  Extreme Fear
        21-40: Fear
        41-60: Neutral
        61-80: Greed
        81-100: Extreme Greed
    """

    def __init__(
        self,
        extreme_fear_threshold: int = 20,
        fear_threshold: int = 40,
        greed_threshold: int = 60,
        extreme_greed_threshold: int = 80,
    ):
        self.extreme_fear = extreme_fear_threshold
        self.fear = fear_threshold
        self.greed = greed_threshold
        self.extreme_greed = extreme_greed_threshold

    def classify(self, fg_value: int) -> SentimentSignal:
        """Classify a Fear & Greed Index value.

        Args:
            fg_value: Fear & Greed Index value (0-100).
                      Values outside range are clamped.

        Returns:
            SentimentSignal with zone, bias, modifier, confidence.
        """
        fg_value = max(0, min(100, fg_value))

        zone = self._classify_zone(fg_value)
        direction_bias = self._compute_direction_bias(fg_value, zone)
        sizing_modifier = self._compute_sizing_modifier(fg_value, zone)
        confidence = self._compute_confidence(fg_value)
        advice = self._generate_advice(zone, direction_bias, fg_value)

        return SentimentSignal(
            zone=zone,
            fg_value=fg_value,
            sizing_modifier=sizing_modifier,
            direction_bias=direction_bias,
            confidence=confidence,
            advice=advice,
        )

    def classify_with_trend(
        self, fg_value: int, trend: str
    ) -> SentimentSignal:
        """Classify with trend context for stronger signals.

        When sentiment diverges from trend (fear + uptrend, greed + downtrend),
        the contrarian signal is stronger. When they agree (fear + downtrend),
        momentum may continue and the contrarian signal is weaker.

        Args:
            fg_value: Fear & Greed Index value (0-100).
            trend: Current price trend — "UP", "DOWN", or "FLAT".

        Returns:
            SentimentSignal with trend-adjusted confidence.
        """
        signal = self.classify(fg_value)

        # Adjust confidence based on trend-sentiment divergence
        if signal.zone in (SentimentZone.EXTREME_FEAR, SentimentZone.FEAR):
            if trend == "UP":
                # Fear + uptrend = strong contrarian (divergence)
                signal.confidence = min(1.0, signal.confidence * 1.3)
            elif trend == "DOWN":
                # Fear + downtrend = momentum may continue (agreement)
                signal.confidence = signal.confidence * 0.7
        elif signal.zone in (SentimentZone.EXTREME_GREED, SentimentZone.GREED):
            if trend == "DOWN":
                # Greed + downtrend = strong contrarian (divergence)
                signal.confidence = min(1.0, signal.confidence * 1.3)
            elif trend == "UP":
                # Greed + uptrend = momentum may continue
                signal.confidence = signal.confidence * 0.7

        return signal

    def _classify_zone(self, fg_value: int) -> SentimentZone:
        """Map F&G value to sentiment zone."""
        if fg_value <= self.extreme_fear:
            return SentimentZone.EXTREME_FEAR
        if fg_value <= self.fear:
            return SentimentZone.FEAR
        if fg_value <= self.greed:
            return SentimentZone.NEUTRAL
        if fg_value <= self.extreme_greed:
            return SentimentZone.GREED
        return SentimentZone.EXTREME_GREED

    def _compute_direction_bias(
        self, fg_value: int, zone: SentimentZone
    ) -> str:
        """Compute directional bias from sentiment.

        Extreme fear -> UP (contrarian long)
        Moderate fear -> SLIGHT_UP
        Neutral -> NONE
        Moderate greed -> SLIGHT_DOWN
        Extreme greed -> DOWN (contrarian short)
        """
        if zone == SentimentZone.EXTREME_FEAR:
            return "UP"
        if zone == SentimentZone.FEAR:
            return "SLIGHT_UP"
        if zone == SentimentZone.NEUTRAL:
            return "NONE"
        if zone == SentimentZone.GREED:
            return "SLIGHT_DOWN"
        return "DOWN"

    def _compute_sizing_modifier(
        self, fg_value: int, zone: SentimentZone
    ) -> float:
        """Compute sizing modifier.

        Extreme fear: size UP (1.1 to 1.3) — contrarian opportunity
        Neutral: 1.0 — no adjustment
        Extreme greed: size DOWN (0.7 to 0.9) — correction risk

        The modifier is linear within each zone.
        """
        if zone == SentimentZone.EXTREME_FEAR:
            # 0 -> 1.3, 20 -> 1.1
            t = fg_value / self.extreme_fear if self.extreme_fear > 0 else 0
            return 1.3 - 0.2 * t
        if zone == SentimentZone.FEAR:
            # 21 -> 1.05, 40 -> 1.0
            span = self.fear - self.extreme_fear
            t = (fg_value - self.extreme_fear) / span if span > 0 else 1
            return 1.05 - 0.05 * t
        if zone == SentimentZone.NEUTRAL:
            return 1.0
        if zone == SentimentZone.GREED:
            # 61 -> 0.95, 80 -> 0.85
            span = self.extreme_greed - self.greed
            t = (fg_value - self.greed) / span if span > 0 else 1
            return 0.95 - 0.1 * t
        # EXTREME_GREED: 81 -> 0.8, 100 -> 0.65
        span = 100 - self.extreme_greed
        t = (fg_value - self.extreme_greed) / span if span > 0 else 1
        return 0.8 - 0.15 * t

    def _compute_confidence(self, fg_value: int) -> float:
        """Compute confidence in the sentiment signal.

        More extreme values = higher confidence. Neutral = lowest.
        Uses distance from center (50) as a proxy.
        """
        distance = abs(fg_value - 50)
        # Map 0-50 distance to 0.1-0.85 confidence
        confidence = 0.1 + (distance / 50.0) * 0.75
        return min(1.0, max(0.0, confidence))

    def _generate_advice(
        self, zone: SentimentZone, bias: str, fg_value: int
    ) -> str:
        """Generate trading advice string."""
        if zone == SentimentZone.EXTREME_FEAR:
            return (
                f"Extreme fear (F&G={fg_value}). "
                f"Contrarian long bias — mean reversion expected. "
                f"Size up if regime supports it."
            )
        if zone == SentimentZone.FEAR:
            return (
                f"Fear (F&G={fg_value}). "
                f"Slight contrarian long bias. "
                f"Market may be oversold but momentum could continue."
            )
        if zone == SentimentZone.NEUTRAL:
            return (
                f"Neutral sentiment (F&G={fg_value}). "
                f"No directional bias from sentiment. "
                f"Rely on other signals for direction."
            )
        if zone == SentimentZone.GREED:
            return (
                f"Greed (F&G={fg_value}). "
                f"Slight contrarian short bias. "
                f"Market may be overbought but FOMO could persist."
            )
        return (
            f"Extreme greed (F&G={fg_value}). "
            f"Contrarian short bias — correction risk elevated. "
            f"Reduce position sizes."
        )


def _cli():
    """CLI interface."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Fear & Greed Contrarian Filter")
    parser.add_argument("--value", type=int, required=True,
                        help="Fear & Greed Index value (0-100)")
    parser.add_argument("--trend", type=str, default=None,
                        help="Current trend: UP, DOWN, FLAT")
    args = parser.parse_args()

    fgf = FearGreedFilter()

    if args.trend:
        signal = fgf.classify_with_trend(args.value, args.trend)
    else:
        signal = fgf.classify(args.value)

    print(json.dumps(signal.to_dict(), indent=2))


if __name__ == "__main__":
    _cli()
