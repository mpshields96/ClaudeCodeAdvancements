#!/usr/bin/env python3
"""
Ebbinghaus-inspired memory decay for CCA's Frontier 1 memory system.

Replaces hard TTL cutoffs (HIGH=365d, MEDIUM=180d, LOW=90d) with continuous
exponential decay. Based on Prism MCP's forgetting curve pattern:
  effective = base * decay_rate ^ days_since_last_access

Per-confidence decay rates prevent HIGH memories from fading too fast:
  HIGH=0.98   -> 50% at ~34 days, effectively permanent for active memories
  MEDIUM=0.96 -> 50% at ~17 days, moderate decay
  LOW=0.93    -> 50% at ~10 days, fast decay for speculative memories

Usage:
    from decay import compute_effective_confidence, should_prune

    score = compute_effective_confidence(85.0, days=20, confidence="HIGH")
    prune = should_prune(30.0, days=60, confidence="LOW")
"""
from __future__ import annotations

import math

# Per-confidence decay rates (daily retention fraction)
DECAY_RATES = {
    "HIGH": 0.98,
    "MEDIUM": 0.96,
    "LOW": 0.93,
}

# Default floor below which memories are candidates for pruning
DEFAULT_PRUNE_FLOOR = 5.0


def get_decay_rate(confidence: str) -> float:
    """Return the daily decay rate for a confidence level.

    Args:
        confidence: One of "HIGH", "MEDIUM", "LOW"

    Returns:
        Daily retention fraction (0-1). Higher = slower decay.

    Raises:
        ValueError: If confidence level is not recognized.
    """
    rate = DECAY_RATES.get(confidence.upper())
    if rate is None:
        raise ValueError(f"Unknown confidence level: {confidence!r}. Expected HIGH, MEDIUM, or LOW.")
    return rate


def compute_effective_confidence(
    base: float,
    days: float,
    confidence: str = "MEDIUM",
    decay_rate: float | None = None,
) -> float:
    """Compute effective confidence after decay.

    Args:
        base: Original confidence score (0-100).
        days: Days since last access. Negative values are clamped to 0
              (clock-skew protection, matching Prism's approach).
        confidence: Confidence level for automatic decay rate lookup.
        decay_rate: Override the per-confidence decay rate. If provided,
                    the confidence parameter is ignored for rate selection.

    Returns:
        Effective confidence score (0-100), never negative.
    """
    if base <= 0:
        return 0.0

    # Clock-skew protection: treat negative days as 0
    days = max(0.0, days)

    rate = decay_rate if decay_rate is not None else get_decay_rate(confidence)
    effective = base * (rate ** days)

    return round(effective, 2)


def should_prune(
    base: float,
    days: float,
    confidence: str = "MEDIUM",
    floor: float = DEFAULT_PRUNE_FLOOR,
    decay_rate: float | None = None,
) -> bool:
    """Check if a memory has decayed below the pruning threshold.

    Args:
        base: Original confidence score (0-100).
        days: Days since last access.
        confidence: Confidence level for decay rate lookup.
        floor: Minimum effective score before pruning (default 5.0).
        decay_rate: Override decay rate.

    Returns:
        True if the memory should be pruned.
    """
    effective = compute_effective_confidence(base, days, confidence, decay_rate)
    return effective < floor


def days_until_prune(
    base: float,
    confidence: str = "MEDIUM",
    floor: float = DEFAULT_PRUNE_FLOOR,
    decay_rate: float | None = None,
) -> float | None:
    """Calculate how many days until a memory decays below the prune floor.

    Args:
        base: Original confidence score (0-100).
        confidence: Confidence level for decay rate lookup.
        floor: Pruning threshold.
        decay_rate: Override decay rate.

    Returns:
        Days until pruning, or None if the memory is already below floor
        or would never reach the floor (base <= 0).
    """
    if base <= 0 or base < floor:
        return None

    rate = decay_rate if decay_rate is not None else get_decay_rate(confidence)

    if rate >= 1.0:
        return None  # No decay — never prunes

    # Solve: floor = base * rate^days  =>  days = log(floor/base) / log(rate)
    return round(math.log(floor / base) / math.log(rate), 1)


def half_life(confidence: str = "MEDIUM", decay_rate: float | None = None) -> float:
    """Calculate the half-life in days for a given decay rate.

    Args:
        confidence: Confidence level for decay rate lookup.
        decay_rate: Override decay rate.

    Returns:
        Days until a memory retains 50% of its original value.
    """
    rate = decay_rate if decay_rate is not None else get_decay_rate(confidence)

    if rate >= 1.0 or rate <= 0.0:
        return float("inf")

    return round(math.log(0.5) / math.log(rate), 1)
