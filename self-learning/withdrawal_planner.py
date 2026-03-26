#!/usr/bin/env python3
"""withdrawal_planner.py — MT-37 Phase 3 Layer 4: Withdrawal rate planning.

Safe withdrawal rate computation with CAPE-adjusted guardrails and
Guyton-Klinger decision rules for retirement income planning.

Based on:
- Bengen (1994): The 4% rule — original SWR research
- Kitces (2008): CAPE-based SWR adjustment
- Guyton-Klinger (2006): Decision rules for withdrawal adjustments

Key concepts:
- 4% rule: withdraw 4% of initial portfolio annually, adjust for inflation
- CAPE adjustment: lower SWR when market is expensive (high CAPE)
- Guardrails: cut withdrawals when rate exceeds 120% of initial,
  raise when below 80%

Usage:
    from withdrawal_planner import plan_withdrawal

    plan = plan_withdrawal(
        portfolio_value=1_000_000,
        annual_expenses=40_000,
        current_age=65,
        horizon_years=30,
        cape_ratio=28,
    )
    print(plan.summary_text())

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass
from enum import Enum


# Historical median CAPE ratio (Shiller PE10)
MEDIAN_CAPE = 16.0

# CAPE adjustment factor: how much to adjust rate per unit CAPE deviation
CAPE_SENSITIVITY = 0.001  # 0.1% per CAPE unit deviation from median

# Guardrail thresholds (Guyton-Klinger)
GK_UPPER_GUARDRAIL = 1.20  # Cut if rate > 120% of initial
GK_LOWER_GUARDRAIL = 0.80  # Raise if rate < 80% of initial

# SWR bounds
MIN_SWR = 0.025  # 2.5% floor
MAX_SWR = 0.07   # 7% cap


class WithdrawalAction(Enum):
    MAINTAIN = "MAINTAIN"
    CUT = "CUT"
    RAISE = "RAISE"


def base_withdrawal_rate(horizon_years: int = 30) -> float:
    """Compute base safe withdrawal rate for a given horizon.

    Uses Bengen's research: 4% for 30-year horizon, adjusted for
    shorter/longer periods. Roughly: rate = 1 / (horizon * 0.8)
    clamped to [MIN_SWR, MAX_SWR].
    """
    if horizon_years <= 0:
        return MAX_SWR

    # Approximation based on historical success rates
    # 30yr → 4%, 20yr → 5%, 40yr → 3.5%
    rate = 1.2 / horizon_years
    return max(MIN_SWR, min(MAX_SWR, rate))


def cape_adjusted_rate(base_rate: float, cape_ratio: float) -> float:
    """Adjust withdrawal rate based on current CAPE ratio (Kitces 2008).

    When CAPE is above median: reduce SWR (market expensive, lower returns expected)
    When CAPE is below median: increase SWR (market cheap, higher returns expected)
    """
    deviation = MEDIAN_CAPE - cape_ratio  # positive when cheap, negative when expensive
    adjustment = deviation * CAPE_SENSITIVITY
    adjusted = base_rate + adjustment
    return max(MIN_SWR, min(MAX_SWR, adjusted))


def guyton_klinger_check(
    planned_withdrawal: float,
    portfolio_value: float,
    initial_rate: float,
) -> WithdrawalAction:
    """Apply Guyton-Klinger guardrail decision rules.

    Compares current effective withdrawal rate to initial rate.
    If too high → cut. If too low → can raise. Otherwise → maintain.
    """
    if portfolio_value <= 0:
        return WithdrawalAction.CUT

    current_rate = planned_withdrawal / portfolio_value

    if current_rate > initial_rate * GK_UPPER_GUARDRAIL:
        return WithdrawalAction.CUT
    elif current_rate < initial_rate * GK_LOWER_GUARDRAIL:
        return WithdrawalAction.RAISE
    return WithdrawalAction.MAINTAIN


@dataclass
class WithdrawalPlan:
    """Complete withdrawal plan output."""
    safe_rate: float
    annual_amount: float
    portfolio_value: float
    annual_expenses: float
    horizon_years: int
    cape_ratio: float | None
    guardrail_action: WithdrawalAction
    is_sustainable: bool

    def to_dict(self) -> dict:
        return {
            "safe_rate": round(self.safe_rate, 4),
            "annual_amount": round(self.annual_amount, 2),
            "portfolio_value": self.portfolio_value,
            "annual_expenses": self.annual_expenses,
            "horizon_years": self.horizon_years,
            "cape_ratio": self.cape_ratio,
            "guardrail_action": self.guardrail_action.value,
            "is_sustainable": self.is_sustainable,
        }

    def summary_text(self) -> str:
        lines = [
            f"Safe withdrawal rate: {self.safe_rate:.1%}",
            f"Annual amount: ${self.annual_amount:,.0f} (of ${self.portfolio_value:,.0f})",
            f"Expenses: ${self.annual_expenses:,.0f}/year",
            f"Horizon: {self.horizon_years} years",
        ]
        if self.cape_ratio:
            lines.append(f"CAPE adjustment: {self.cape_ratio:.0f} (median={MEDIAN_CAPE:.0f})")
        lines.append(f"Guardrail: {self.guardrail_action.value}")
        lines.append(f"Sustainable: {'YES' if self.is_sustainable else 'NO'}")
        return "\n".join(lines)


def plan_withdrawal(
    portfolio_value: float,
    annual_expenses: float,
    current_age: int = 65,
    horizon_years: int = 30,
    cape_ratio: float | None = None,
) -> WithdrawalPlan:
    """Generate a complete withdrawal plan.

    Args:
        portfolio_value: Current portfolio value
        annual_expenses: Target annual withdrawal
        current_age: Current age (informational)
        horizon_years: Planning horizon in years
        cape_ratio: Current Shiller CAPE (None = use base rate only)
    """
    rate = base_withdrawal_rate(horizon_years)

    if cape_ratio is not None:
        rate = cape_adjusted_rate(rate, cape_ratio)

    annual_amount = portfolio_value * rate
    is_sustainable = annual_amount >= annual_expenses

    gk_action = guyton_klinger_check(
        planned_withdrawal=annual_expenses,
        portfolio_value=portfolio_value,
        initial_rate=rate,
    )

    return WithdrawalPlan(
        safe_rate=rate,
        annual_amount=annual_amount,
        portfolio_value=portfolio_value,
        annual_expenses=annual_expenses,
        horizon_years=horizon_years,
        cape_ratio=cape_ratio,
        guardrail_action=gk_action,
        is_sustainable=is_sustainable,
    )


def main():
    """CLI: example withdrawal planning."""
    plan = plan_withdrawal(
        portfolio_value=1_500_000,
        annual_expenses=50_000,
        current_age=62,
        horizon_years=33,
        cape_ratio=28,
    )

    print("Withdrawal Planner")
    print("=" * 50)
    print(plan.summary_text())

    if "--json" in sys.argv:
        print(json.dumps(plan.to_dict(), indent=2))


if __name__ == "__main__":
    main()
