#!/usr/bin/env python3
"""uber_pipeline.py — MT-37 UBER: Unified pipeline orchestrator.

Chains all 10 UBER modules (Layers 1-5) into a single analyze_portfolio()
call. This is the entry point for the wealth management intelligence system.

Pipeline flow:
  PortfolioInput → risk_monitor → rebalance_advisor → tax_harvester
                 → portfolio_report → behavioral_guard → UBERReport

Each module runs independently and gracefully degrades if data is missing.
The orchestrator collects all results into a structured UBERReport with
sections, action items, and a human-readable summary.

Usage:
    from uber_pipeline import UBERPipeline, PortfolioInput

    portfolio = PortfolioInput(
        holdings={
            "VTI": {"shares": 100, "cost_basis": 180.0, "current_price": 220.0,
                     "volatility": 0.16, "domestic": True},
        },
        target_weights={"VTI": 0.60, "BND": 0.40},
        days_since_rebalance=45,
        portfolio_values=[100000, 101000, 102000, ...],
    )
    pipeline = UBERPipeline()
    report = pipeline.analyze(portfolio)
    print(report.summary_text())

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from behavioral_guard import BehavioralGuard
from portfolio_report import portfolio_analytics
from rebalance_advisor import RebalanceAdvisor
from risk_monitor import RiskDashboard
from tax_harvester import TaxHarvester


@dataclass
class PortfolioInput:
    """Input data for the UBER pipeline.

    holdings: dict of ticker -> {shares, cost_basis, current_price, volatility, domestic}
    target_weights: dict of ticker -> target weight (0-1)
    days_since_rebalance: days since last rebalance event
    portfolio_values: historical portfolio values for analytics (daily)
    """
    holdings: Dict[str, dict]
    target_weights: Dict[str, float]
    days_since_rebalance: int = 0
    portfolio_values: List[float] = field(default_factory=list)

    def current_weights(self) -> Dict[str, float]:
        """Compute current portfolio weights from holdings."""
        total = self.total_value()
        if total <= 0:
            return {}
        return {
            ticker: (h["shares"] * h["current_price"]) / total
            for ticker, h in self.holdings.items()
        }

    def total_value(self) -> float:
        """Total current portfolio value."""
        return sum(
            h["shares"] * h["current_price"]
            for h in self.holdings.values()
        )


@dataclass
class UBERConfig:
    """Configuration for the UBER pipeline."""
    kelly_fraction: float = 0.5
    drift_threshold: float = 0.05
    calendar_interval_days: int = 90
    home_bias_threshold: float = 0.70
    overconfidence_threshold: float = 10
    risk_free_annual: float = 0.05


@dataclass
class UBERReport:
    """Unified report from the UBER pipeline."""
    sections: Dict[str, dict]
    portfolio_value: float = 0.0

    def to_dict(self) -> dict:
        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "sections": self.sections,
            "summary": self.summary_text(),
        }

    def summary_text(self) -> str:
        lines = ["UBER Portfolio Intelligence Report"]
        lines.append("=" * 50)

        if self.portfolio_value > 0:
            lines.append(f"Portfolio value: ${self.portfolio_value:,.0f}")

        # Risk section
        risk = self.sections.get("risk", {})
        if risk:
            lines.append(f"Risk level: {risk.get('overall_risk', 'N/A')}")

        # Rebalancing section
        rebal = self.sections.get("rebalancing", {})
        if rebal:
            if rebal.get("should_rebalance"):
                triggers = ", ".join(rebal.get("triggers", []))
                lines.append(f"Rebalancing: RECOMMENDED ({triggers})")
            else:
                lines.append("Rebalancing: not needed")

        # Analytics section
        analytics = self.sections.get("analytics", {})
        if analytics:
            sharpe = analytics.get("sharpe", 0)
            ann_ret = analytics.get("annualized_return", 0)
            lines.append(f"Annualized return: {ann_ret:.1%}")
            lines.append(f"Sharpe ratio: {sharpe:.2f}")

        # Tax section
        tax = self.sections.get("tax_harvesting", {})
        candidates = tax.get("candidates", [])
        if candidates:
            total_savings = sum(c.get("estimated_savings", 0) for c in candidates)
            lines.append(f"TLH candidates: {len(candidates)} (est. savings ${total_savings:,.0f})")

        # Behavioral section
        behavioral = self.sections.get("behavioral", {})
        alerts = behavioral.get("alerts", [])
        if alerts:
            lines.append(f"Behavioral alerts: {len(alerts)}")
            for a in alerts:
                lines.append(f"  [{a.get('severity', '?')}] {a.get('bias', '?')}")

        return "\n".join(lines)

    def action_items(self) -> List[str]:
        """Extract actionable items from all sections."""
        items = []

        # Rebalancing actions
        rebal = self.sections.get("rebalancing", {})
        if rebal.get("should_rebalance"):
            for action in rebal.get("actions", []):
                direction = action.get("direction", "?")
                ticker = action.get("ticker", "?")
                pct = action.get("amount_pct", 0)
                dollar = action.get("dollar_amount", 0)
                if dollar > 0:
                    items.append(f"{direction} {ticker}: {pct:.1%} (${dollar:,.0f})")
                else:
                    items.append(f"{direction} {ticker}: {pct:.1%}")

        # TLH actions
        tax = self.sections.get("tax_harvesting", {})
        for c in tax.get("candidates", []):
            ticker = c.get("ticker", "?")
            savings = c.get("estimated_savings", 0)
            items.append(f"Harvest loss in {ticker} (est. ${savings:,.0f} tax savings)")

        # Behavioral warnings
        behavioral = self.sections.get("behavioral", {})
        for a in behavioral.get("alerts", []):
            items.append(f"Bias warning: {a.get('bias', '?')} — {a.get('recommendation', '')[:80]}")

        return items


class UBERPipeline:
    """Unified pipeline orchestrating all UBER modules."""

    def __init__(self, config: Optional[UBERConfig] = None):
        self.config = config or UBERConfig()

    def analyze(self, portfolio: PortfolioInput) -> UBERReport:
        """Run full UBER analysis on a portfolio."""
        sections: Dict[str, dict] = {}
        total_value = portfolio.total_value()

        # 1. Risk monitoring
        sections["risk"] = self._run_risk(portfolio)

        # 2. Rebalancing analysis
        sections["rebalancing"] = self._run_rebalancing(portfolio, total_value)

        # 3. Tax-loss harvesting
        sections["tax_harvesting"] = self._run_tax(portfolio)

        # 4. Portfolio analytics
        sections["analytics"] = self._run_analytics(portfolio)

        # 5. Behavioral guard
        sections["behavioral"] = self._run_behavioral(portfolio)

        return UBERReport(sections=sections, portfolio_value=total_value)

    def _run_risk(self, portfolio: PortfolioInput) -> dict:
        """Run risk monitoring on portfolio value history."""
        dash = RiskDashboard()
        for v in portfolio.portfolio_values:
            dash.update(v)
        return dash.summary()

    def _run_rebalancing(self, portfolio: PortfolioInput, bankroll: float) -> dict:
        """Run rebalancing analysis."""
        advisor = RebalanceAdvisor(
            drift_threshold=self.config.drift_threshold,
            calendar_interval_days=self.config.calendar_interval_days,
        )
        current_weights = portfolio.current_weights()
        rec = advisor.analyze(
            current=current_weights,
            target=portfolio.target_weights,
            days_since_last=portfolio.days_since_rebalance,
            bankroll=bankroll,
        )
        return rec.to_dict()

    def _run_tax(self, portfolio: PortfolioInput) -> dict:
        """Run tax-loss harvesting scan."""
        from datetime import date

        harvester = TaxHarvester()
        holdings_list = []
        for ticker, h in portfolio.holdings.items():
            holdings_list.append({
                "ticker": ticker,
                "shares": h["shares"],
                "cost_basis": h["cost_basis"],
                "current_price": h["current_price"],
                "purchase_date": h.get("purchase_date", date(2025, 1, 1)),
            })
        candidates = harvester.scan(holdings_list)
        return harvester.summary(candidates)

    def _run_analytics(self, portfolio: PortfolioInput) -> dict:
        """Run portfolio analytics."""
        if not portfolio.portfolio_values or len(portfolio.portfolio_values) < 2:
            return {"annualized_return": 0.0, "sharpe": 0.0, "sortino": 0.0,
                    "max_drawdown": 0.0, "risk_attribution": {"contributions": {}, "portfolio_vol": 0.0},
                    "assets": []}

        holdings_for_report = {}
        for ticker, h in portfolio.holdings.items():
            holdings_for_report[ticker] = {
                "weight": portfolio.current_weights().get(ticker, 0.0),
                "volatility": h.get("volatility", 0.15),
            }
        report = portfolio_analytics(
            holdings_for_report,
            portfolio.portfolio_values,
            risk_free_annual=self.config.risk_free_annual,
        )
        return report.to_dict()

    def _run_behavioral(self, portfolio: PortfolioInput) -> dict:
        """Run behavioral bias checks."""
        guard = BehavioralGuard(
            home_bias_threshold=self.config.home_bias_threshold,
            overconfidence_threshold=self.config.overconfidence_threshold,
        )

        # Build context from portfolio data
        weights = portfolio.current_weights()
        domestic_tickers = {
            t for t, h in portfolio.holdings.items()
            if h.get("domestic", False)
        }

        # Check for holdings with unrealized losses
        holdings_with_losses = []
        for ticker, h in portfolio.holdings.items():
            unrealized_pct = (h["current_price"] - h["cost_basis"]) / h["cost_basis"] if h["cost_basis"] > 0 else 0
            if unrealized_pct < 0:
                holdings_with_losses.append({
                    "ticker": ticker,
                    "unrealized_gain_pct": unrealized_pct,
                })

        context = {
            "trades": [],
            "holdings_with_losses": holdings_with_losses,
            "recent_loss_pct": 0.0,
            "proposed_action": "hold",
            "weights": weights,
            "domestic_tickers": domestic_tickers,
            "trades_per_month": 0,
        }

        alerts = guard.scan(context)
        return {"alerts": guard.to_dict(alerts), "count": len(alerts)}


def main():
    """CLI: run UBER analysis on example portfolio."""
    portfolio = PortfolioInput(
        holdings={
            "VTI": {"shares": 100, "cost_basis": 180.0, "current_price": 220.0,
                     "volatility": 0.16, "domestic": True},
            "VXUS": {"shares": 80, "cost_basis": 55.0, "current_price": 48.0,
                      "volatility": 0.18, "domestic": False},
            "BND": {"shares": 200, "cost_basis": 78.0, "current_price": 75.0,
                     "volatility": 0.04, "domestic": True},
        },
        target_weights={"VTI": 0.55, "VXUS": 0.25, "BND": 0.20},
        days_since_rebalance=95,
        portfolio_values=[50000 + i * 40 for i in range(120)],
    )

    pipeline = UBERPipeline()
    report = pipeline.analyze(portfolio)
    print(report.summary_text())

    print("\nAction Items:")
    for item in report.action_items():
        print(f"  - {item}")

    if "--json" in sys.argv:
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
