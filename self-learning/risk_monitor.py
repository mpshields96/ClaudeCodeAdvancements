#!/usr/bin/env python3
"""risk_monitor.py — MT-37 Phase 3 Layer 3: Portfolio risk monitoring.

Tracks drawdowns, rolling volatility, and generates risk alerts.
Provides a combined risk dashboard for portfolio health assessment.

Based on:
- Ang (2014): Asset Management — regime switching, drawdown awareness
- Moskowitz et al. (2012): Time series momentum — vol scaling

Risk levels:
- GREEN:    drawdown < 5%, vol normal
- YELLOW:   drawdown 5-15% or elevated vol
- RED:      drawdown 15-30%
- CRITICAL: drawdown > 30%

Usage:
    from risk_monitor import RiskDashboard

    dash = RiskDashboard()
    for daily_value in portfolio_values:
        dash.update(daily_value)
    print(dash.summary())
    print(dash.alerts())

Stdlib only. No external dependencies.
"""
import json
import math
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class RiskLevel(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    CRITICAL = "CRITICAL"


# Drawdown thresholds
DD_YELLOW = 0.05   # 5%
DD_RED = 0.15      # 15%
DD_CRITICAL = 0.30  # 30%

# Volatility threshold (annualized, approximate)
VOL_ELEVATED = 0.25  # 25% annualized vol considered elevated


class DrawdownTracker:
    """Track portfolio drawdowns from peak."""

    def __init__(self):
        self.peak: float = 0.0
        self.current_value: float = 0.0
        self.max_drawdown: float = 0.0
        self._has_data = False

    def update(self, value: float):
        """Update with new portfolio value."""
        if not self._has_data or value > self.peak:
            self.peak = value
        self.current_value = value
        self._has_data = True

        dd = self.current_drawdown
        if dd > self.max_drawdown:
            self.max_drawdown = dd

    @property
    def current_drawdown(self) -> float:
        """Current drawdown from peak (0.0 = at peak, 0.25 = 25% below)."""
        if self.peak <= 0:
            return 0.0
        return max(0.0, (self.peak - self.current_value) / self.peak)

    @property
    def risk_level(self) -> RiskLevel:
        dd = self.current_drawdown
        if dd >= DD_CRITICAL:
            return RiskLevel.CRITICAL
        elif dd >= DD_RED:
            return RiskLevel.RED
        elif dd >= DD_YELLOW:
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    def to_dict(self) -> dict:
        return {
            "current_drawdown": round(self.current_drawdown, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "peak": self.peak,
            "current_value": self.current_value,
            "risk_level": self.risk_level.value,
        }


class VolatilityMonitor:
    """Track rolling volatility from return series."""

    def __init__(self, window: int = 20):
        self.window = window
        self._values: List[float] = []

    def update(self, value: float):
        """Update with new portfolio value."""
        self._values.append(value)

    @property
    def current_volatility(self) -> float:
        """Compute rolling volatility (annualized std of returns)."""
        if len(self._values) < 2:
            return 0.0

        # Use last `window` values
        recent = self._values[-self.window:]
        if len(recent) < 2:
            return 0.0

        # Compute log returns
        returns = []
        for i in range(1, len(recent)):
            if recent[i - 1] > 0 and recent[i] > 0:
                returns.append(math.log(recent[i] / recent[i - 1]))

        if len(returns) < 2:
            return 0.0

        # Standard deviation of returns
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)

        # Annualize (252 trading days)
        return daily_vol * math.sqrt(252)

    @property
    def is_elevated(self) -> bool:
        return self.current_volatility > VOL_ELEVATED


class RiskDashboard:
    """Combined risk monitoring dashboard."""

    def __init__(self, vol_window: int = 20):
        self.drawdown = DrawdownTracker()
        self.volatility = VolatilityMonitor(window=vol_window)

    def update(self, value: float):
        """Update all monitors with new portfolio value."""
        self.drawdown.update(value)
        self.volatility.update(value)

    def summary(self) -> dict:
        """Full risk summary."""
        dd_risk = self.drawdown.risk_level
        vol_elevated = self.volatility.is_elevated

        # Overall risk = max of drawdown risk and vol escalation
        if dd_risk in (RiskLevel.RED, RiskLevel.CRITICAL):
            overall = dd_risk.value
        elif dd_risk == RiskLevel.YELLOW or vol_elevated:
            overall = RiskLevel.YELLOW.value
        else:
            overall = RiskLevel.GREEN.value

        return {
            "drawdown": self.drawdown.to_dict(),
            "volatility": {
                "current": round(self.volatility.current_volatility, 4),
                "is_elevated": vol_elevated,
                "window": self.volatility.window,
            },
            "overall_risk": overall,
        }

    def alerts(self) -> List[str]:
        """Generate human-readable risk alerts."""
        alerts = []

        dd = self.drawdown.current_drawdown
        if dd >= DD_CRITICAL:
            alerts.append(f"CRITICAL: Portfolio drawdown {dd:.1%} from peak — consider defensive action")
        elif dd >= DD_RED:
            alerts.append(f"WARNING: Portfolio drawdown {dd:.1%} from peak — monitor closely")
        elif dd >= DD_YELLOW:
            alerts.append(f"NOTICE: Portfolio drawdown {dd:.1%} from peak")

        if self.volatility.is_elevated:
            vol = self.volatility.current_volatility
            alerts.append(f"ELEVATED VOL: Annualized volatility {vol:.1%} exceeds {VOL_ELEVATED:.0%} threshold")

        return alerts


def main():
    """CLI: example risk monitoring."""
    # Simulate a portfolio with a drawdown
    values = [
        100000, 102000, 105000, 103000, 108000,
        106000, 112000, 109000, 100000, 95000,
        92000, 96000, 98000, 101000, 104000,
    ]

    dash = RiskDashboard()
    print("Portfolio Risk Monitor")
    print("=" * 50)

    for i, v in enumerate(values):
        dash.update(v)

    s = dash.summary()
    print(f"Current value: ${values[-1]:,.0f}")
    print(f"Peak: ${dash.drawdown.peak:,.0f}")
    print(f"Drawdown: {s['drawdown']['current_drawdown']:.1%}")
    print(f"Max drawdown: {s['drawdown']['max_drawdown']:.1%}")
    print(f"Volatility: {s['volatility']['current']:.1%}")
    print(f"Overall risk: {s['overall_risk']}")

    alerts = dash.alerts()
    if alerts:
        print("\nAlerts:")
        for a in alerts:
            print(f"  {a}")

    if "--json" in sys.argv:
        print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
