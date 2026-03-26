#!/usr/bin/env python3
"""kelly_sizer.py — MT-37 Phase 3 Layer 3: Portfolio position sizing.

Fractional Kelly criterion with confidence scaling for long-term investment
portfolios. Based on academic foundations:
- Kelly (1956): optimal growth rate criterion
- Thorp (2006): practical Kelly for investing
- MacLean et al. (2011): growth-security tradeoff analysis

Key concepts:
- Full Kelly maximizes geometric growth but has extreme drawdowns
- Fractional Kelly (half or quarter) trades growth for much lower variance
- Confidence scaling further adjusts sizing based on estimation certainty

Usage:
    from kelly_sizer import portfolio_kelly_sizes

    assets = [
        {"ticker": "VTI", "win_prob": 0.55, "win_return": 0.10,
         "loss_return": 0.08, "confidence": 0.8},
    ]
    sizes = portfolio_kelly_sizes(assets, fraction=0.5, bankroll=100000)
    for s in sizes:
        print(f"{s.ticker}: {s.kelly_pct:.1%} → ${s.dollar_amount:,.0f}")

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass
from typing import List


def kelly_fraction(win_prob: float, win_return: float, loss_return: float) -> float:
    """Compute full Kelly fraction for a binary outcome.

    f* = (p * b - q) / b
    where p = win probability, q = 1-p, b = win/loss ratio

    Returns 0 if edge is negative (don't bet).
    """
    if loss_return <= 0:
        return 0.0

    p = win_prob
    q = 1.0 - p
    b = win_return / loss_return

    f = (p * b - q) / b
    return max(f, 0.0)


def fractional_kelly(
    win_prob: float,
    win_return: float,
    loss_return: float,
    fraction: float = 0.5,
) -> float:
    """Compute fractional Kelly (default half-Kelly).

    Half-Kelly achieves ~75% of the growth rate of full Kelly but with
    drastically reduced variance and drawdowns (Thorp 2006).
    """
    full = kelly_fraction(win_prob, win_return, loss_return)
    return full * fraction


def confidence_scaled_kelly(
    win_prob: float,
    win_return: float,
    loss_return: float,
    fraction: float = 0.5,
    confidence: float = 1.0,
) -> float:
    """Kelly sizing scaled by confidence in the estimate.

    When confidence < 1.0, we reduce position size proportionally.
    This accounts for estimation error in win_prob and returns.
    Confidence is clamped to [0, 1].
    """
    confidence = max(0.0, min(1.0, confidence))
    base = fractional_kelly(win_prob, win_return, loss_return, fraction)
    return base * confidence


@dataclass
class SizingResult:
    """Result of Kelly sizing for one asset."""
    ticker: str
    kelly_pct: float  # Fraction of bankroll to allocate
    dollar_amount: float  # Dollar amount at given bankroll
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "kelly_pct": self.kelly_pct,
            "dollar_amount": self.dollar_amount,
            "confidence": self.confidence,
        }

    def summary_text(self) -> str:
        return f"{self.ticker}: {self.kelly_pct:.1%} → ${self.dollar_amount:,.0f} (conf {self.confidence:.0%})"


def portfolio_kelly_sizes(
    assets: List[dict],
    fraction: float = 0.5,
    bankroll: float = 100000.0,
) -> List[SizingResult]:
    """Compute Kelly-optimal sizing for a portfolio of independent assets.

    Each asset dict needs: ticker, win_prob, win_return, loss_return, confidence.

    Uses conservative 1/N scaling when total Kelly exceeds 100% — divides
    bankroll proportionally among positive-edge assets, capped at bankroll.
    """
    raw_sizes = []
    for asset in assets:
        pct = confidence_scaled_kelly(
            win_prob=asset["win_prob"],
            win_return=asset["win_return"],
            loss_return=asset["loss_return"],
            fraction=fraction,
            confidence=asset.get("confidence", 1.0),
        )
        raw_sizes.append((asset["ticker"], pct, asset.get("confidence", 1.0)))

    # Cap total allocation at 100% of bankroll
    total_pct = sum(pct for _, pct, _ in raw_sizes)
    if total_pct > 1.0 and total_pct > 0:
        scale = 1.0 / total_pct
    else:
        scale = 1.0

    results = []
    for ticker, pct, conf in raw_sizes:
        scaled_pct = pct * scale
        results.append(SizingResult(
            ticker=ticker,
            kelly_pct=scaled_pct,
            dollar_amount=round(scaled_pct * bankroll, 2),
            confidence=conf,
        ))

    return results


def main():
    """CLI: example portfolio sizing."""
    # Example: simple 3-asset portfolio
    assets = [
        {"ticker": "VTI", "win_prob": 0.55, "win_return": 0.12, "loss_return": 0.10, "confidence": 0.8},
        {"ticker": "VXUS", "win_prob": 0.52, "win_return": 0.10, "loss_return": 0.12, "confidence": 0.6},
        {"ticker": "BND", "win_prob": 0.65, "win_return": 0.04, "loss_return": 0.02, "confidence": 0.9},
    ]

    bankroll = 100000
    fraction = 0.5

    print(f"Portfolio Kelly Sizing (half-Kelly, ${bankroll:,} bankroll)")
    print("=" * 60)

    sizes = portfolio_kelly_sizes(assets, fraction=fraction, bankroll=bankroll)
    for s in sizes:
        print(f"  {s.summary_text()}")

    total = sum(s.dollar_amount for s in sizes)
    print(f"\nTotal allocated: ${total:,.0f} ({total/bankroll:.1%})")

    if "--json" in sys.argv:
        print(json.dumps([s.to_dict() for s in sizes], indent=2))


if __name__ == "__main__":
    main()
