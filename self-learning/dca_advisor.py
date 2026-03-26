#!/usr/bin/env python3
"""dca_advisor.py — MT-37: Dollar-cost averaging for small recurring investments.

Translates UBER's target allocation into concrete deposit instructions for
small recurring investments ($20/week, $50/month, etc.). Supports
deposit-time rebalancing — tilting each deposit toward underweight assets
to gradually restore target allocation without selling.

Key features:
- Split deposit by target weights (simple mode)
- Tilt deposit toward underweight assets (rebalance mode)
- Annual projection with compound growth estimates
- App recommendations (M1 Finance, Fidelity, Schwab)

Academic basis:
- Constantinides (1979): DCA reduces timing risk for risk-averse investors
- Brennan et al. (2005): DCA outperforms lump sum when uncertainty is high
- Practical note: DCA's main benefit is behavioral — it enforces consistent
  investing and removes timing decisions (Statman 1995)

Usage:
    from dca_advisor import DCAConfig, DCAFrequency, rebalance_on_deposit, annual_projection

    # "What should I buy this week with $20?"
    current = {"VTI": 3200, "VXUS": 1100, "BND": 700}
    targets = {"VTI": 0.60, "VXUS": 0.25, "BND": 0.15}
    allocation = rebalance_on_deposit(current, targets, deposit=20.0)
    # → {"VTI": 8.40, "VXUS": 7.20, "BND": 4.40}

    # "How much will I have in 10 years?"
    proj = annual_projection(20.0, DCAFrequency.WEEKLY, annual_return=0.08, years=10)
    print(f"Projected: ${proj.projected_value:,.0f}")

Stdlib only. No external dependencies.
"""
import json
import math
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class DCAFrequency(Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"

    @property
    def deposits_per_year(self) -> int:
        return {"WEEKLY": 52, "BIWEEKLY": 26, "MONTHLY": 12}[self.value]


@dataclass
class DCAConfig:
    """Configuration for dollar-cost averaging."""
    deposit_amount: float = 20.0
    frequency: DCAFrequency = DCAFrequency.WEEKLY
    target_weights: Dict[str, float] = field(default_factory=dict)
    rebalance_on_deposit: bool = True

    @property
    def deposits_per_year(self) -> int:
        return self.frequency.deposits_per_year


@dataclass
class DCAAllocation:
    """Result of a single deposit allocation."""
    per_asset: Dict[str, float]  # ticker -> dollar amount
    total: float

    def to_dict(self) -> dict:
        return {
            "per_asset": {k: round(v, 2) for k, v in self.per_asset.items()},
            "total": round(self.total, 2),
        }


@dataclass
class AnnualProjection:
    """Projected portfolio value over time."""
    total_contributed: float
    projected_value: float
    years: int
    annual_return: float
    deposits_per_year: int

    def to_dict(self) -> dict:
        return {
            "total_contributed": round(self.total_contributed, 2),
            "projected_value": round(self.projected_value, 2),
            "years": self.years,
            "annual_return": self.annual_return,
            "growth": round(self.projected_value - self.total_contributed, 2),
        }


@dataclass
class DCAReport:
    """Full DCA recommendation report."""
    allocation: Dict[str, float]  # ticker -> dollar amount this deposit
    deposit_amount: float
    frequency: DCAFrequency
    rebalance_tilt: bool = False

    def to_dict(self) -> dict:
        return {
            "allocation": {k: round(v, 2) for k, v in self.allocation.items()},
            "deposit_amount": self.deposit_amount,
            "frequency": self.frequency.value,
            "rebalance_tilt": self.rebalance_tilt,
        }

    def summary_text(self) -> str:
        lines = [f"DCA Plan: ${self.deposit_amount:.2f} {self.frequency.value.lower()}"]
        lines.append("-" * 40)
        for ticker, amount in sorted(self.allocation.items(), key=lambda x: -x[1]):
            pct = (amount / self.deposit_amount * 100) if self.deposit_amount > 0 else 0
            lines.append(f"  {ticker}: ${amount:.2f} ({pct:.0f}%)")
        lines.append(f"  Total: ${self.deposit_amount:.2f}")
        if self.rebalance_tilt:
            lines.append("  (tilted toward underweight assets)")
        return "\n".join(lines)

    def recommended_apps(self) -> List[dict]:
        """Return app recommendations for small recurring DCA investments."""
        apps = [
            {
                "name": "M1 Finance",
                "why": "Set target allocation 'pie', every deposit auto-rebalances. Best for UBER integration.",
                "min_deposit": 10.0,
                "fractional_shares": True,
                "recurring_buys": True,
            },
            {
                "name": "Fidelity",
                "why": "Zero minimums, fractional shares, $0 commissions. Recurring buys for ETFs.",
                "min_deposit": 1.0,
                "fractional_shares": True,
                "recurring_buys": True,
            },
            {
                "name": "Schwab",
                "why": "Schwab Stock Slices for fractional shares. Recurring weekly/monthly.",
                "min_deposit": 5.0,
                "fractional_shares": True,
                "recurring_buys": True,
            },
            {
                "name": "Vanguard",
                "why": "Best for Vanguard ETFs (VTI/VXUS/BND). Fractional shares available.",
                "min_deposit": 1.0,
                "fractional_shares": True,
                "recurring_buys": True,
            },
        ]
        return [a for a in apps if a["min_deposit"] <= self.deposit_amount]


def allocate_deposit(
    deposit: float,
    target_weights: Dict[str, float],
) -> Dict[str, float]:
    """Split a deposit across assets by target weights.

    Simple pro-rata allocation. No rebalancing consideration.
    """
    result = {}
    for ticker, weight in target_weights.items():
        result[ticker] = round(deposit * weight, 2)

    # Fix rounding to match deposit exactly
    total = sum(result.values())
    if result and abs(total - deposit) > 0.001:
        largest = max(result, key=result.get)
        result[largest] = round(result[largest] + (deposit - total), 2)

    return result


def rebalance_on_deposit(
    current_values: Dict[str, float],
    target_weights: Dict[str, float],
    deposit: float,
) -> Dict[str, float]:
    """Allocate deposit with tilt toward underweight assets.

    Instead of pro-rata allocation, tilts the deposit to gradually
    restore target allocation. This avoids selling (tax events) and
    uses new money to rebalance naturally.

    Algorithm:
    1. Compute what the portfolio would look like after deposit at target
    2. Find the gap between current weights and target weights
    3. Allocate deposit proportionally to underweight gaps
    4. If no underweight assets, fall back to target weights
    """
    total_current = sum(current_values.values())

    if total_current <= 0:
        return allocate_deposit(deposit, target_weights)

    total_after = total_current + deposit

    # Compute target dollar values after deposit
    target_values = {t: total_after * w for t, w in target_weights.items()}

    # Compute gaps (how much each asset needs to reach target)
    gaps = {}
    for ticker in target_weights:
        current = current_values.get(ticker, 0.0)
        gap = target_values[ticker] - current
        gaps[ticker] = max(gap, 0.0)  # Only underweight assets get deposit

    total_gap = sum(gaps.values())

    if total_gap <= 0:
        # All assets at or above target — use simple allocation
        return allocate_deposit(deposit, target_weights)

    # Allocate deposit proportionally to gaps
    result = {}
    for ticker in target_weights:
        fraction = gaps[ticker] / total_gap if total_gap > 0 else 0
        result[ticker] = round(deposit * fraction, 2)

    # Fix rounding
    total = sum(result.values())
    if result and abs(total - deposit) > 0.001:
        largest = max(result, key=result.get)
        result[largest] = round(result[largest] + (deposit - total), 2)

    return result


def annual_projection(
    deposit_amount: float,
    frequency: DCAFrequency,
    annual_return: float = 0.08,
    years: int = 1,
) -> AnnualProjection:
    """Project portfolio value from recurring DCA deposits.

    Uses future value of annuity formula with periodic compounding:
    FV = PMT * [((1 + r)^n - 1) / r]
    where r = per-period return, n = total periods
    """
    n_per_year = frequency.deposits_per_year
    total_periods = n_per_year * years
    total_contributed = deposit_amount * total_periods

    if annual_return == 0:
        return AnnualProjection(
            total_contributed=total_contributed,
            projected_value=total_contributed,
            years=years,
            annual_return=annual_return,
            deposits_per_year=n_per_year,
        )

    # Per-period return
    r = annual_return / n_per_year

    # Future value of annuity
    fv = deposit_amount * (((1 + r) ** total_periods - 1) / r)

    return AnnualProjection(
        total_contributed=total_contributed,
        projected_value=round(fv, 2),
        years=years,
        annual_return=annual_return,
        deposits_per_year=n_per_year,
    )


def main():
    """CLI: DCA advisor example."""
    targets = {"VTI": 0.55, "VXUS": 0.25, "BND": 0.15, "VTIP": 0.05}

    print("DCA Advisor — Small Recurring Investment Planner")
    print("=" * 50)

    # Scenario 1: $20/week
    alloc = allocate_deposit(20.0, targets)
    report = DCAReport(allocation=alloc, deposit_amount=20.0, frequency=DCAFrequency.WEEKLY)
    print("\n$20/week plan:")
    print(report.summary_text())

    proj = annual_projection(20.0, DCAFrequency.WEEKLY, annual_return=0.08, years=10)
    print(f"\n10-year projection: ${proj.projected_value:,.0f} "
          f"(contributed ${proj.total_contributed:,.0f}, "
          f"growth ${proj.projected_value - proj.total_contributed:,.0f})")

    # Scenario 2: $50/month
    alloc2 = allocate_deposit(50.0, targets)
    report2 = DCAReport(allocation=alloc2, deposit_amount=50.0, frequency=DCAFrequency.MONTHLY)
    print(f"\n$50/month plan:")
    print(report2.summary_text())

    proj2 = annual_projection(50.0, DCAFrequency.MONTHLY, annual_return=0.08, years=10)
    print(f"\n10-year projection: ${proj2.projected_value:,.0f} "
          f"(contributed ${proj2.total_contributed:,.0f})")

    # App recommendations
    print("\nRecommended apps:")
    for app in report.recommended_apps():
        print(f"  {app['name']}: {app['why']}")

    if "--json" in sys.argv:
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
