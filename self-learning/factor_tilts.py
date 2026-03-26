#!/usr/bin/env python3
"""factor_tilts.py — MT-37 Phase 6: Factor overlay system.

Scores assets on four evidence-based factors and applies tilts to base weights:
1. Value — cheap assets (low P/E, low P/B). Fama & French 1992.
2. Momentum — 12-1 month return. Carhart 1997, Jegadeesh & Titman 1993.
3. Quality — high ROE, low leverage, stable earnings. Asness et al. 2019.
4. Low Volatility — lower-vol assets. Ang et al. 2006.

Only factors with 20+ years out-of-sample evidence and structural economic
rationale (Harvey et al. 2016 filter) are included.

Usage:
    from factor_tilts import score_value, score_momentum, apply_tilts

    scores = {"value": score_value(pe_ratio=12, pb_ratio=1.5),
              "momentum": score_momentum(return_12m=0.20, return_1m=0.02)}
    tilt = compute_composite_tilt(scores)
"""

import math
import sys
from dataclasses import dataclass, field
from typing import Optional


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class FactorScore:
    """Score for a single factor on a single asset."""
    ticker: str
    factor: str       # "value", "momentum", "quality", "low_vol"
    score: float      # 0.0 to 1.0 (0.5 = neutral)
    z_score: float    # Raw z-score before normalization


@dataclass
class TiltResult:
    """Container for factor tilt output."""
    base_weights: dict[str, float]
    tilted_weights: dict[str, float]
    factor_scores: dict[str, dict[str, float]]  # ticker -> {factor: score}
    tilts: dict[str, float]  # ticker -> composite tilt

    def to_dict(self) -> dict:
        return {
            "base_weights": self.base_weights,
            "tilted_weights": self.tilted_weights,
            "factor_scores": self.factor_scores,
            "tilts": self.tilts,
        }


# ── Sigmoid utility ──────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Sigmoid function mapping R -> (0, 1). Neutral at x=0 -> 0.5."""
    return 1.0 / (1.0 + math.exp(-x))


# ── Value Factor ─────────────────────────────────────────────────────────────

# Median P/E and P/B for normalization (approximate S&P 500 long-run)
_MEDIAN_PE = 20.0
_MEDIAN_PB = 3.0


def score_value(
    pe_ratio: Optional[float] = None,
    pb_ratio: Optional[float] = None,
) -> float:
    """Score value factor: cheap = high score, expensive = low score.

    Uses inverse P/E and inverse P/B, averaged and passed through sigmoid.
    Negative P/E (losses) treated as very expensive.

    Returns 0.0 to 1.0, with 0.5 = neutral.
    """
    if pe_ratio is None and pb_ratio is None:
        return 0.5

    signals = []

    if pe_ratio is not None:
        if pe_ratio <= 0:
            # Negative earnings = very expensive
            signals.append(-2.0)
        else:
            # z-score: positive when cheap (low PE), negative when expensive
            z = (_MEDIAN_PE - pe_ratio) / _MEDIAN_PE
            signals.append(z * 2.0)

    if pb_ratio is not None:
        if pb_ratio <= 0:
            signals.append(-2.0)
        else:
            z = (_MEDIAN_PB - pb_ratio) / _MEDIAN_PB
            signals.append(z * 2.0)

    avg_signal = sum(signals) / len(signals) if signals else 0.0
    return _sigmoid(avg_signal)


# ── Momentum Factor ──────────────────────────────────────────────────────────

def score_momentum(
    return_12m: Optional[float] = None,
    return_1m: Optional[float] = None,
) -> float:
    """Score momentum factor: 12-month minus 1-month return.

    Carhart (1997) 4-factor model: momentum = 12-1 month return.
    Skipping the most recent month avoids short-term reversal.

    Returns 0.0 to 1.0, with 0.5 = neutral.
    """
    if return_12m is None:
        return 0.5

    r1m = return_1m if return_1m is not None else 0.0
    momentum = return_12m - r1m

    # Scale: 20% momentum = strong signal (~0.8 score)
    z = momentum / 0.15
    return _sigmoid(z)


# ── Quality Factor ───────────────────────────────────────────────────────────

def score_quality(
    roe: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    earnings_stability: Optional[float] = None,
) -> float:
    """Score quality factor: high ROE, low leverage, stable earnings.

    Asness, Frazzini & Pedersen (2019) "Quality Minus Junk".

    Returns 0.0 to 1.0, with 0.5 = neutral.
    """
    signals = []

    if roe is not None:
        # ROE: 15% = good, 5% = poor
        z = (roe - 0.10) / 0.10
        signals.append(z)

    if debt_to_equity is not None:
        # D/E: lower is better. 0.5 = good, 2.0 = poor
        z = (1.0 - debt_to_equity) / 1.0
        signals.append(z)

    if earnings_stability is not None:
        # 0-1 scale: 1.0 = very stable
        z = (earnings_stability - 0.5) / 0.3
        signals.append(z)

    if not signals:
        return 0.5

    avg_signal = sum(signals) / len(signals)
    return _sigmoid(avg_signal)


# ── Low-Volatility Factor ───────────────────────────────────────────────────

def score_low_vol(
    volatility: float,
    market_vol: float = 0.20,
) -> float:
    """Score low-volatility factor: lower vol = higher score.

    Ang, Hodrick, Xing & Zhang (2006): low-vol anomaly.

    Returns 0.0 to 1.0, with 0.5 = neutral (vol == market_vol).
    """
    if market_vol <= 0:
        return 0.5

    # Ratio: <1 means lower than market, >1 means higher
    ratio = volatility / market_vol
    z = (1.0 - ratio) / 0.5  # 50% below market = z=+1
    return _sigmoid(z)


# ── Composite Tilt ───────────────────────────────────────────────────────────

# Default equal weighting across factors
_DEFAULT_FACTOR_WEIGHTS = {
    "value": 0.25,
    "momentum": 0.25,
    "quality": 0.25,
    "low_vol": 0.25,
}


def compute_composite_tilt(
    scores: dict[str, float],
    factor_weights: Optional[dict[str, float]] = None,
) -> float:
    """Compute composite tilt from factor scores.

    Each score is centered (score - 0.5) then weighted.
    Returns a value typically in [-0.5, 0.5] where 0 = neutral.
    """
    if not scores:
        return 0.0

    fw = factor_weights or _DEFAULT_FACTOR_WEIGHTS

    tilt = 0.0
    total_weight = 0.0
    for factor, score in scores.items():
        w = fw.get(factor, 0.0)
        tilt += (score - 0.5) * w
        total_weight += w

    if total_weight > 0:
        tilt /= total_weight

    return tilt


# ── Apply Tilts to Weights ───────────────────────────────────────────────────

def apply_tilts(
    base_weights: dict[str, float],
    tilts: dict[str, float],
    magnitude: float = 0.3,
) -> dict[str, float]:
    """Apply factor tilts to base allocation weights.

    adjusted_w[i] = base_w[i] * (1 + magnitude * tilt[i])
    Then normalize to sum to 1.0 and clip negatives.

    Args:
        base_weights: Starting allocation weights.
        tilts: Per-ticker composite tilts (from compute_composite_tilt).
        magnitude: How strongly tilts affect weights (0 = no effect, 1 = full).

    Returns:
        Adjusted weights, normalized, no negatives.
    """
    adjusted = {}
    for t, w in base_weights.items():
        tilt = tilts.get(t, 0.0)
        adjusted[t] = w * (1.0 + magnitude * tilt)

    # Clip negatives
    for t in adjusted:
        adjusted[t] = max(adjusted[t], 0.0)

    # Normalize
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {t: v / total for t, v in adjusted.items()}
    else:
        # Fallback to base weights
        adjusted = dict(base_weights)

    return adjusted
