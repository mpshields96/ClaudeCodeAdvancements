#!/usr/bin/env python3
"""allocation.py — MT-37 Phase 5: Portfolio allocation engines.

Implements three allocation methods:
1. Equal-weight (1/N) — baseline
2. Risk parity (inverse-volatility) — Qian 2005, Maillard et al. 2010
3. Black-Litterman — Black & Litterman 1992 (market prior + user views)

All methods return normalized weights summing to 1.0.
Constraint enforcement (min/max weight, no-short) available as post-processing.

Usage:
    from allocation import equal_weight, risk_parity, black_litterman, View

    # Equal weight
    w = equal_weight(["AAPL", "GOOG", "MSFT"])

    # Risk parity
    w = risk_parity({"AAPL": 0.20, "GOOG": 0.25, "MSFT": 0.30})

    # Black-Litterman with views
    views = [View(ticker="AAPL", expected_return=0.15, confidence=0.8)]
    w = black_litterman(market_weights, covariance, views=views)
"""

import math
import sys
from dataclasses import dataclass, field
from typing import Optional


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class View:
    """An investor view on a specific asset's expected return."""
    ticker: str
    expected_return: float  # e.g. 0.10 = 10% annual
    confidence: float       # 0.0 to 1.0


@dataclass
class AllocationResult:
    """Container for allocation output."""
    weights: dict[str, float]
    method: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "method": self.method,
            "metadata": self.metadata,
        }

    def summary(self) -> str:
        lines = [f"Allocation ({self.method}):"]
        for t in sorted(self.weights, key=lambda x: self.weights[x], reverse=True):
            lines.append(f"  {t}: {self.weights[t]*100:.1f}%")
        return "\n".join(lines)


# ── Equal Weight ─────────────────────────────────────────────────────────────

def equal_weight(tickers: list[str]) -> dict[str, float]:
    """1/N equal-weight allocation.

    DeMiguel et al. (2009) showed 1/N outperforms most optimization methods
    out-of-sample due to estimation error in mean-variance optimization.
    Used as a robust baseline.
    """
    if not tickers:
        raise ValueError("Cannot allocate with empty ticker list")
    n = len(tickers)
    w = 1.0 / n
    return {t: w for t in tickers}


# ── Risk Parity ──────────────────────────────────────────────────────────────

def risk_parity(volatilities: dict[str, float]) -> dict[str, float]:
    """Inverse-volatility risk parity allocation.

    Each asset's weight is proportional to 1/sigma, so each contributes
    equal risk (volatility) to the portfolio. Qian (2005), Maillard et al. (2010).

    Args:
        volatilities: Dict mapping ticker -> annualized volatility.

    Returns:
        Normalized weights summing to 1.0.
    """
    if not volatilities:
        raise ValueError("Cannot allocate with empty volatility dict")

    for t, v in volatilities.items():
        if v <= 0:
            raise ValueError(f"Volatility for {t} must be positive, got {v}")

    inv_vols = {t: 1.0 / v for t, v in volatilities.items()}
    total = sum(inv_vols.values())
    return {t: iv / total for t, iv in inv_vols.items()}


# ── Black-Litterman ──────────────────────────────────────────────────────────

# Risk aversion coefficient (standard BL default)
_DEFAULT_DELTA = 2.5
# Scalar for uncertainty in equilibrium returns (tau)
_DEFAULT_TAU = 0.05


def _implied_returns(
    market_weights: dict[str, float],
    covariance: dict[str, dict[str, float]],
    delta: float = _DEFAULT_DELTA,
) -> dict[str, float]:
    """Compute implied equilibrium returns: pi = delta * Sigma * w_mkt."""
    tickers = sorted(market_weights.keys())
    pi = {}
    for t in tickers:
        pi[t] = delta * sum(
            covariance[t].get(s, 0.0) * market_weights.get(s, 0.0)
            for s in tickers
        )
    return pi


def black_litterman(
    market_weights: dict[str, float],
    covariance: dict[str, dict[str, float]],
    views: list[View] = None,
    delta: float = _DEFAULT_DELTA,
    tau: float = _DEFAULT_TAU,
) -> dict[str, float]:
    """Black-Litterman allocation with optional investor views.

    When views is empty/None, returns market-cap weights (equilibrium).
    With views, blends equilibrium with view-adjusted expected returns.

    Simplified BL (diagonal P matrix — each view targets one asset):
        E[R] = pi + tau*Sigma*P'*(P*tau*Sigma*P' + Omega)^-1 * (Q - P*pi)
    Where P is identity-like (one view per asset), Q is view returns,
    Omega is view uncertainty diagonal.

    Args:
        market_weights: Market-cap weights (prior).
        covariance: Covariance matrix as nested dict.
        views: List of View objects (optional).
        delta: Risk aversion coefficient.
        tau: Uncertainty scalar for equilibrium returns.

    Returns:
        Normalized weights summing to 1.0.
    """
    if views is None:
        views = []

    tickers = sorted(market_weights.keys())
    n = len(tickers)

    # Implied equilibrium returns
    pi = _implied_returns(market_weights, covariance, delta)

    if not views:
        # No views — return market weights
        return dict(market_weights)

    # Filter views to only assets in our universe
    valid_views = [v for v in views if v.ticker in market_weights]
    if not valid_views:
        return dict(market_weights)

    # Build adjusted returns by blending pi with views
    # Simplified approach: for each view, adjust pi[ticker] toward view return
    # weighted by confidence and tau
    adjusted_pi = dict(pi)
    for view in valid_views:
        t = view.ticker
        # View uncertainty: lower confidence = higher uncertainty
        # omega = tau * cov[t][t] / confidence (higher confidence = lower omega)
        cov_tt = covariance.get(t, {}).get(t, 0.04)
        omega = tau * cov_tt / max(view.confidence, 0.01)

        # BL blending: weighted average of pi and view
        # weight_view = tau * cov_tt / (tau * cov_tt + omega)
        tau_sigma = tau * cov_tt
        w_view = tau_sigma / (tau_sigma + omega)

        adjusted_pi[t] = (1 - w_view) * pi[t] + w_view * view.expected_return

    # Convert adjusted returns to weights via inverse optimization:
    # w* = (delta * Sigma)^-1 * adjusted_pi
    # Simplified: use a proportional approach (avoid full matrix inversion)
    # w_i proportional to adjusted_pi[i] / (delta * cov[i][i])
    raw_weights = {}
    for t in tickers:
        cov_tt = covariance.get(t, {}).get(t, 0.04)
        raw_weights[t] = adjusted_pi[t] / (delta * cov_tt) if cov_tt > 0 else 0.0

    # Normalize to sum to 1 (long-only)
    # Shift to ensure all positive, then normalize
    min_w = min(raw_weights.values())
    if min_w < 0:
        # Shift all weights up so minimum is near zero
        for t in raw_weights:
            raw_weights[t] -= min_w

    total = sum(raw_weights.values())
    if total <= 0:
        return dict(market_weights)

    return {t: w / total for t, w in raw_weights.items()}


# ── Constraint Enforcement ───────────────────────────────────────────────────

def apply_constraints(
    weights: dict[str, float],
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    no_short: bool = False,
) -> dict[str, float]:
    """Enforce weight constraints and re-normalize.

    Iteratively clips weights to [min_weight, max_weight] and redistributes
    excess/deficit to unconstrained assets.
    """
    w = dict(weights)
    n = len(w)
    if n == 0:
        return w

    # Apply no-short first
    if no_short:
        for t in w:
            w[t] = max(w[t], 0.0)

    # Iterative clipping (max 10 rounds to converge)
    for _ in range(10):
        clipped = {}
        free = {}
        for t, val in w.items():
            if val < min_weight:
                clipped[t] = min_weight
            elif val > max_weight:
                clipped[t] = max_weight
            else:
                free[t] = val

        if not clipped:
            break

        # How much weight was redistributed
        clipped_sum = sum(clipped.values())
        free_sum = sum(free.values())
        target_free = 1.0 - clipped_sum

        if free_sum > 0 and target_free > 0:
            scale = target_free / free_sum
            for t in free:
                free[t] *= scale

        w = {**clipped, **free}

    # Final normalization
    total = sum(w.values())
    if total > 0:
        w = {t: v / total for t, v in w.items()}

    return w


# ── Rebalance Trigger ────────────────────────────────────────────────────────

def needs_rebalance(
    current: dict[str, float],
    target: dict[str, float],
    threshold: float = 0.05,
) -> bool:
    """Check if any asset drifts beyond threshold from target.

    Args:
        current: Current portfolio weights.
        target: Target allocation weights.
        threshold: Maximum allowed absolute drift (e.g. 0.05 = 5pp).

    Returns:
        True if any asset exceeds threshold drift.
    """
    all_tickers = set(current) | set(target)
    for t in all_tickers:
        c = current.get(t, 0.0)
        tgt = target.get(t, 0.0)
        if abs(c - tgt) > threshold:
            return True
    return False


# ── CLI ──────────────────────────────────────────────────────────────────────

def cli_main(args: list[str] = None) -> int:
    """CLI entry point for quick allocation demos."""
    import argparse

    parser = argparse.ArgumentParser(description="Portfolio allocation (MT-37 Phase 5)")
    parser.add_argument("--method", choices=["equal", "risk_parity"], default="equal")
    parser.add_argument("--tickers", nargs="+", help="Ticker symbols")
    parser.add_argument("--vols", nargs="+", type=float, help="Volatilities (for risk_parity)")

    parsed = parser.parse_args(args)

    if not parsed.tickers:
        parser.print_help()
        return 1

    if parsed.method == "equal":
        w = equal_weight(parsed.tickers)
        result = AllocationResult(weights=w, method="equal_weight")
    elif parsed.method == "risk_parity":
        if not parsed.vols or len(parsed.vols) != len(parsed.tickers):
            print("Error: --vols must match --tickers count", file=sys.stderr)
            return 1
        vols = dict(zip(parsed.tickers, parsed.vols))
        w = risk_parity(vols)
        result = AllocationResult(weights=w, method="risk_parity")
    else:
        return 1

    print(result.summary())
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
