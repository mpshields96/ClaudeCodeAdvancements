#!/usr/bin/env python3
"""tax_harvester.py — MT-37 Phase 3 Layer 4: Tax-loss harvesting scanner.

Scans portfolio holdings for tax-loss harvesting opportunities. Tracks
wash sale windows (30-day rule) and estimates tax savings.

Based on:
- Constantinides (1983): optimal TLH timing
- Berkin & Ye (2003): after-tax improvement from systematic TLH

Key rules:
- TLH = sell a losing position to realize the loss for tax deduction
- Wash sale rule: cannot repurchase same/substantially identical security
  within 30 days before or after the sale
- Short-term losses offset short-term gains (taxed at ordinary income rate)
- Long-term losses offset long-term gains (taxed at LTCG rate)
- Net losses can offset up to $3,000 of ordinary income per year

Usage:
    from tax_harvester import TaxHarvester

    holdings = [
        {"ticker": "VTI", "shares": 100, "cost_basis": 150.0,
         "current_price": 130.0, "purchase_date": date(2025, 6, 1)},
    ]
    harvester = TaxHarvester()
    candidates = harvester.scan(holdings)
    report = harvester.summary(candidates, marginal_rate=0.37)

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional


# Wash sale window (days)
WASH_SALE_WINDOW = 30

# Default minimum loss to flag as harvestable
DEFAULT_MIN_LOSS = 0.0


def compute_tax_savings(loss: float, marginal_rate: float, is_long_term: bool) -> float:
    """Estimate tax savings from realizing a loss.

    Args:
        loss: Dollar amount of the loss (positive = loss, negative = gain)
        marginal_rate: Applicable tax rate (ordinary income or LTCG)
        is_long_term: Whether holding period > 1 year

    Returns:
        Estimated tax savings in dollars.
    """
    if loss <= 0:
        return 0.0
    return loss * marginal_rate


@dataclass
class TLHCandidate:
    """A tax-loss harvesting candidate."""
    ticker: str
    shares: float
    cost_basis: float  # per share
    current_price: float  # per share
    purchase_date: date
    as_of_date: date = None
    in_wash_window: bool = False

    def __post_init__(self):
        if self.as_of_date is None:
            self.as_of_date = date.today()

    @property
    def unrealized_loss(self) -> float:
        """Total unrealized loss (positive = loss, 0 if gain)."""
        loss = self.shares * (self.cost_basis - self.current_price)
        return max(loss, 0.0)

    @property
    def is_harvestable(self) -> bool:
        """Whether this position has a loss worth harvesting."""
        return self.unrealized_loss > 0

    @property
    def is_long_term(self) -> bool:
        """Whether holding period exceeds 1 year."""
        delta = self.as_of_date - self.purchase_date
        return delta.days > 365

    def estimated_savings(self, marginal_rate: float = 0.37) -> float:
        """Estimate tax savings at given marginal rate."""
        rate = marginal_rate if not self.is_long_term else min(marginal_rate, 0.20)
        return compute_tax_savings(self.unrealized_loss, rate, self.is_long_term)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "shares": self.shares,
            "cost_basis": self.cost_basis,
            "current_price": self.current_price,
            "unrealized_loss": round(self.unrealized_loss, 2),
            "is_harvestable": self.is_harvestable,
            "is_long_term": self.is_long_term,
            "in_wash_window": self.in_wash_window,
            "purchase_date": self.purchase_date.isoformat(),
        }


class WashSaleTracker:
    """Track wash sale windows for sold securities."""

    def __init__(self):
        self._sales: Dict[str, date] = {}

    def record_sale(self, ticker: str, sale_date: date):
        """Record a sale for wash sale tracking."""
        # Keep the most recent sale date
        if ticker not in self._sales or sale_date > self._sales[ticker]:
            self._sales[ticker] = sale_date

    def is_in_wash_window(self, ticker: str, check_date: date) -> bool:
        """Check if a ticker is within the 30-day wash sale window."""
        if ticker not in self._sales:
            return False
        days_since = (check_date - self._sales[ticker]).days
        return 0 <= days_since <= WASH_SALE_WINDOW

    def days_remaining(self, ticker: str, check_date: date) -> int:
        """Days remaining in wash sale window (0 if outside)."""
        if ticker not in self._sales:
            return 0
        days_since = (check_date - self._sales[ticker]).days
        remaining = WASH_SALE_WINDOW - days_since
        return max(remaining, 0)


class TaxHarvester:
    """Scan portfolio for TLH opportunities."""

    def __init__(self, min_loss: float = DEFAULT_MIN_LOSS):
        self.min_loss = min_loss
        self.wash_tracker = WashSaleTracker()

    def scan(
        self,
        holdings: List[dict],
        as_of: Optional[date] = None,
    ) -> List[TLHCandidate]:
        """Scan holdings for TLH candidates.

        Each holding dict needs: ticker, shares, cost_basis, current_price, purchase_date.
        """
        if as_of is None:
            as_of = date.today()

        candidates = []
        for h in holdings:
            candidate = TLHCandidate(
                ticker=h["ticker"],
                shares=h["shares"],
                cost_basis=h["cost_basis"],
                current_price=h["current_price"],
                purchase_date=h["purchase_date"],
                as_of_date=as_of,
                in_wash_window=self.wash_tracker.is_in_wash_window(h["ticker"], as_of),
            )

            if candidate.is_harvestable and candidate.unrealized_loss >= self.min_loss:
                candidates.append(candidate)

        # Sort by largest loss first
        candidates.sort(key=lambda c: c.unrealized_loss, reverse=True)
        return candidates

    def summary(
        self,
        candidates: List[TLHCandidate],
        marginal_rate: float = 0.37,
    ) -> dict:
        """Generate summary report of TLH opportunities."""
        total_loss = sum(c.unrealized_loss for c in candidates)
        total_savings = sum(c.estimated_savings(marginal_rate) for c in candidates)
        wash_blocked = sum(1 for c in candidates if c.in_wash_window)

        return {
            "total_harvestable_loss": round(total_loss, 2),
            "estimated_tax_savings": round(total_savings, 2),
            "candidate_count": len(candidates),
            "wash_sale_blocked": wash_blocked,
            "marginal_rate": marginal_rate,
            "candidates": [c.to_dict() for c in candidates],
        }


def main():
    """CLI: example TLH scan."""
    holdings = [
        {"ticker": "VTI", "shares": 100, "cost_basis": 250.0,
         "current_price": 230.0, "purchase_date": date(2025, 6, 1)},
        {"ticker": "VXUS", "shares": 200, "cost_basis": 55.0,
         "current_price": 48.0, "purchase_date": date(2025, 3, 1)},
        {"ticker": "BND", "shares": 150, "cost_basis": 72.0,
         "current_price": 74.0, "purchase_date": date(2025, 1, 1)},
    ]

    harvester = TaxHarvester()
    candidates = harvester.scan(holdings)
    report = harvester.summary(candidates, marginal_rate=0.37)

    print("Tax-Loss Harvesting Scanner")
    print("=" * 50)
    print(f"Candidates found: {report['candidate_count']}")
    print(f"Total harvestable loss: ${report['total_harvestable_loss']:,.2f}")
    print(f"Estimated tax savings: ${report['estimated_tax_savings']:,.2f}")

    for c in candidates:
        print(f"\n  {c.ticker}: ${candidates[0].unrealized_loss:,.2f} loss")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
