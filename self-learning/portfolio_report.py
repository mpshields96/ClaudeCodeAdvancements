#!/usr/bin/env python3
"""portfolio_report.py — MT-37 Layer 5: Portfolio analytics and reporting.

Computes portfolio-level performance metrics, risk attribution, and
generates structured analytics data for reporting.

Metrics computed:
- Annualized return (geometric)
- Sharpe ratio (annualized, Sharpe 1966)
- Sortino ratio (downside deviation only, Sortino & Price 1994)
- Maximum drawdown
- Risk attribution (marginal contribution to risk)

Academic basis:
- Sharpe (1966): reward-to-variability ratio
- Sortino & Price (1994): downside risk framework
- Brinson et al. (1986): performance attribution
- Menchero (2000): risk decomposition for multi-asset portfolios

Usage:
    from portfolio_report import portfolio_analytics

    holdings = {
        "VTI": {"weight": 0.60, "volatility": 0.16},
        "BND": {"weight": 0.40, "volatility": 0.04},
    }
    values = [100000, 101000, 102500, ...]  # daily portfolio values
    report = portfolio_analytics(holdings, values, risk_free_annual=0.05)
    print(report.summary_text())

Stdlib only. No external dependencies.
"""
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def annualized_return(
    values: List[float],
    periods_per_year: int = 252,
) -> float:
    """Compute annualized geometric return from a value series.

    Uses the compound annual growth rate (CAGR) formula:
    CAGR = (V_final / V_initial)^(periods_per_year / n_periods) - 1
    """
    if len(values) < 2:
        return 0.0

    v_initial = values[0]
    v_final = values[-1]
    if v_initial <= 0:
        return 0.0

    n_periods = len(values) - 1
    total_return = v_final / v_initial

    if total_return <= 0:
        return -1.0

    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0

    return total_return ** (1.0 / years) - 1.0


def _daily_returns(values: List[float]) -> List[float]:
    """Compute simple daily returns from value series."""
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            returns.append((values[i] - values[i - 1]) / values[i - 1])
    return returns


def compute_sharpe(
    returns: List[float],
    risk_free_annual: float = 0.05,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sharpe ratio.

    Sharpe = (mean_return - rf_per_period) / std(returns) * sqrt(periods_per_year)
    """
    if len(returns) < 2:
        return 0.0

    rf_per_period = risk_free_annual / periods_per_year
    mean_return = sum(returns) / len(returns)
    excess = mean_return - rf_per_period

    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0

    if std < 1e-12:
        # Near-zero vol: return sign * large number
        return math.copysign(99.0, excess) if excess != 0 else 0.0

    return (excess / std) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: List[float],
    risk_free_annual: float = 0.05,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sortino ratio (Sortino & Price 1994).

    Uses only downside deviation (negative returns relative to target).
    """
    if len(returns) < 2:
        return 0.0

    rf_per_period = risk_free_annual / periods_per_year
    mean_return = sum(returns) / len(returns)
    excess = mean_return - rf_per_period

    # Downside deviation: only count returns below rf
    downside_sq = [
        (r - rf_per_period) ** 2 for r in returns if r < rf_per_period
    ]

    if not downside_sq:
        # No downside -> very high ratio
        return math.copysign(99.0, excess) if excess != 0 else 0.0

    downside_var = sum(downside_sq) / len(returns)  # Use full N, not just downside count
    downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0

    if downside_std < 1e-12:
        return math.copysign(99.0, excess) if excess != 0 else 0.0

    return (excess / downside_std) * math.sqrt(periods_per_year)


def max_drawdown(values: List[float]) -> float:
    """Compute maximum drawdown from a value series.

    Returns a fraction (0.25 = 25% drawdown from peak).
    """
    if len(values) < 2:
        return 0.0

    peak = values[0]
    max_dd = 0.0

    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

    return max_dd


@dataclass
class RiskAttribution:
    """Risk decomposition across portfolio assets."""
    contributions: Dict[str, float]  # ticker -> fraction of total risk
    portfolio_vol: float             # Estimated portfolio volatility

    def to_dict(self) -> dict:
        return {
            "contributions": {k: round(v, 4) for k, v in self.contributions.items()},
            "portfolio_vol": round(self.portfolio_vol, 4),
        }


def risk_attribution(
    weights: Dict[str, float],
    volatilities: Dict[str, float],
) -> RiskAttribution:
    """Compute marginal risk contribution for each asset.

    Simplified model assuming zero correlation (independent assets).
    Uses weight * vol as the risk contribution proxy, then normalizes.

    For a full implementation, you'd use the covariance matrix:
    MCR_i = (w_i * sum_j(w_j * cov_ij)) / sigma_p
    But with only volatilities (no correlations), we approximate.
    """
    raw_contributions = {}
    total_risk = 0.0

    for ticker in weights:
        w = weights.get(ticker, 0.0)
        v = volatilities.get(ticker, 0.0)
        risk = w * v
        raw_contributions[ticker] = risk
        total_risk += risk

    # Normalize to fractions summing to 1
    contributions = {}
    for ticker, risk in raw_contributions.items():
        contributions[ticker] = risk / total_risk if total_risk > 0 else 0.0

    # Portfolio vol estimate (assuming zero correlation — conservative)
    port_var = sum(
        (weights.get(t, 0) * volatilities.get(t, 0)) ** 2 for t in weights
    )
    portfolio_vol = math.sqrt(port_var)

    return RiskAttribution(contributions=contributions, portfolio_vol=portfolio_vol)


@dataclass
class AssetReport:
    """Per-asset summary within the portfolio."""
    ticker: str
    weight: float
    volatility: float
    risk_contribution: float  # Fraction of total risk


@dataclass
class PortfolioReport:
    """Full portfolio analytics report."""
    annualized_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    risk_attr: RiskAttribution
    assets: List[AssetReport]

    def to_dict(self) -> dict:
        return {
            "annualized_return": round(self.annualized_return, 4),
            "sharpe": round(self.sharpe, 4),
            "sortino": round(self.sortino, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "risk_attribution": self.risk_attr.to_dict(),
            "assets": [
                {
                    "ticker": a.ticker,
                    "weight": round(a.weight, 4),
                    "volatility": round(a.volatility, 4),
                    "risk_contribution": round(a.risk_contribution, 4),
                }
                for a in self.assets
            ],
        }

    def summary_text(self) -> str:
        lines = [
            f"Annualized Return: {self.annualized_return:.1%}",
            f"Sharpe Ratio: {self.sharpe:.2f}",
            f"Sortino Ratio: {self.sortino:.2f}",
            f"Max Drawdown: {self.max_drawdown:.1%}",
            f"Portfolio Vol: {self.risk_attr.portfolio_vol:.1%}",
            "",
            "Risk Attribution:",
        ]
        for a in self.assets:
            lines.append(
                f"  {a.ticker}: {a.weight:.0%} weight, "
                f"{a.risk_contribution:.0%} risk"
            )
        return "\n".join(lines)


def portfolio_analytics(
    holdings: Dict[str, dict],
    values: List[float],
    risk_free_annual: float = 0.05,
    periods_per_year: int = 252,
) -> PortfolioReport:
    """Compute full portfolio analytics from holdings and value series.

    holdings: dict of ticker -> {"weight": float, "volatility": float}
    values: list of portfolio values (daily or periodic)
    """
    ann_ret = annualized_return(values, periods_per_year)
    returns = _daily_returns(values)
    sharpe = compute_sharpe(returns, risk_free_annual, periods_per_year)
    sort = sortino_ratio(returns, risk_free_annual, periods_per_year)
    mdd = max_drawdown(values)

    weights = {t: h["weight"] for t, h in holdings.items()}
    vols = {t: h["volatility"] for t, h in holdings.items()}
    risk_attr = risk_attribution(weights, vols)

    assets = []
    for ticker, h in holdings.items():
        assets.append(AssetReport(
            ticker=ticker,
            weight=h["weight"],
            volatility=h["volatility"],
            risk_contribution=risk_attr.contributions.get(ticker, 0.0),
        ))

    return PortfolioReport(
        annualized_return=ann_ret,
        sharpe=sharpe,
        sortino=sort,
        max_drawdown=mdd,
        risk_attr=risk_attr,
        assets=assets,
    )


def main():
    """CLI: example portfolio analytics."""
    holdings = {
        "VTI": {"weight": 0.55, "volatility": 0.16},
        "VXUS": {"weight": 0.25, "volatility": 0.18},
        "BND": {"weight": 0.15, "volatility": 0.04},
        "VTIP": {"weight": 0.05, "volatility": 0.03},
    }

    # Simulate 252 daily values (~1 year)
    import random
    random.seed(42)
    values = [500000.0]
    for _ in range(251):
        daily_ret = random.gauss(0.0003, 0.008)  # ~7.5% annual, ~12.7% vol
        values.append(values[-1] * (1 + daily_ret))

    report = portfolio_analytics(holdings, values)

    print("Portfolio Analytics Report")
    print("=" * 50)
    print(report.summary_text())

    if "--json" in sys.argv:
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
