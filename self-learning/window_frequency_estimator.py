"""Window frequency estimator — market capacity analysis.

Calculates theoretical max bet frequency from market structure (window
duration, assets, hours of operation), compares against observed signal
firing rates, and projects daily P&L at various bet frequencies.

Answers: how many bets/day can we actually get? Where is the capacity ceiling?

Usage:
    from window_frequency_estimator import (
        WindowFrequencyEstimator, MarketConfig, ObservedRate
    )

    markets = [
        MarketConfig(name="KXBTC15M", window_minutes=15, hours_per_day=24),
        MarketConfig(name="KXETH15M", window_minutes=15, hours_per_day=24),
        MarketConfig(name="KXSOL15M", window_minutes=15, hours_per_day=24),
    ]
    observed = [
        ObservedRate(market="KXBTC15M", total_bets=312, days_observed=14),
        ObservedRate(market="KXETH15M", total_bets=314, days_observed=14),
        ObservedRate(market="KXSOL15M", total_bets=277, days_observed=14),
    ]
    est = WindowFrequencyEstimator(markets, observed)
    print(est.summary_text())
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MarketConfig:
    """Configuration for a single market type."""

    name: str
    window_minutes: int  # duration of each trading window
    hours_per_day: int = 24  # how many hours the market is open

    def windows_per_day(self) -> int:
        """Total trading windows available per day."""
        total_minutes = self.hours_per_day * 60
        return total_minutes // self.window_minutes


@dataclass
class ObservedRate:
    """Observed signal firing rate for a market."""

    market: str
    total_bets: int
    days_observed: int
    total_windows: int = 0  # if known; 0 = calculate from market config

    def bets_per_day(self) -> float:
        if self.days_observed == 0:
            return 0.0
        return self.total_bets / self.days_observed

    def signal_fire_rate(self) -> float:
        """Fraction of windows that produced a signal."""
        if self.total_windows == 0:
            return 0.0
        return self.total_bets / self.total_windows


@dataclass
class FrequencyEstimate:
    """Output of frequency estimation."""

    total_theoretical_windows: int
    total_observed_bets_per_day: float
    signal_utilization: float  # observed / theoretical
    capacity_headroom: float  # theoretical - observed
    per_market: List[dict]
    ev_table: List[dict] = field(default_factory=list)


class WindowFrequencyEstimator:
    """Estimates bet frequency capacity across markets."""

    def __init__(self, markets: List[MarketConfig],
                 observed: Optional[List[ObservedRate]] = None) -> None:
        self.markets = markets
        self.observed = observed or []

    def estimate(self, win_rate: float = 0.0, avg_win: float = 0.0,
                 avg_loss: float = 0.0) -> FrequencyEstimate:
        """Run frequency estimation."""
        total_windows = sum(m.windows_per_day() for m in self.markets)

        # Build observed lookup
        obs_map = {o.market: o for o in self.observed}
        total_obs = sum(o.bets_per_day() for o in self.observed)

        utilization = total_obs / total_windows if total_windows > 0 else 0.0
        headroom = total_windows - total_obs

        # Per-market breakdown
        per_market = []
        for m in self.markets:
            entry = {
                "market": m.name,
                "windows_per_day": m.windows_per_day(),
                "window_minutes": m.window_minutes,
            }
            if m.name in obs_map:
                o = obs_map[m.name]
                entry["observed_bets_per_day"] = round(o.bets_per_day(), 1)
                entry["signal_rate"] = round(
                    o.bets_per_day() / m.windows_per_day(), 4
                ) if m.windows_per_day() > 0 else 0.0
            else:
                entry["observed_bets_per_day"] = 0.0
                entry["signal_rate"] = 0.0
            per_market.append(entry)

        # EV table at various frequencies
        ev_table = []
        if win_rate > 0 and avg_loss > 0:
            q = 1.0 - win_rate
            edge = win_rate * avg_win - q * avg_loss
            for bets in [20, 30, 40, 50, 64, 80, 100, 120, 150]:
                ev_table.append({
                    "bets_per_day": bets,
                    "expected_daily_pnl": round(bets * edge, 2),
                    "expected_wins": round(bets * win_rate, 1),
                    "expected_losses": round(bets * q, 1),
                })

        result = FrequencyEstimate(
            total_theoretical_windows=total_windows,
            total_observed_bets_per_day=round(total_obs, 1),
            signal_utilization=round(utilization, 4),
            capacity_headroom=round(headroom, 1),
            per_market=per_market,
            ev_table=ev_table,
        )
        return result

    def to_dict(self) -> dict:
        """Export as JSON-serializable dict."""
        report = self.estimate()
        return {
            "markets": [
                {"name": m.name, "window_minutes": m.window_minutes,
                 "windows_per_day": m.windows_per_day()}
                for m in self.markets
            ],
            "observed": [
                {"market": o.market, "total_bets": o.total_bets,
                 "days_observed": o.days_observed,
                 "bets_per_day": round(o.bets_per_day(), 1)}
                for o in self.observed
            ],
            "estimate": {
                "total_theoretical_windows": report.total_theoretical_windows,
                "total_observed_bets_per_day": report.total_observed_bets_per_day,
                "signal_utilization": report.signal_utilization,
                "capacity_headroom": report.capacity_headroom,
                "per_market": report.per_market,
            },
        }

    def summary_text(self) -> str:
        """Human-readable frequency analysis."""
        report = self.estimate()
        lines = [
            "=== WINDOW FREQUENCY ESTIMATOR ===",
            f"Markets: {len(self.markets)}",
            f"Total theoretical windows/day: {report.total_theoretical_windows}",
            f"Observed bets/day: {report.total_observed_bets_per_day}",
            f"Signal utilization: {report.signal_utilization:.1%}",
            f"Capacity headroom: {report.capacity_headroom:.0f} unused windows/day",
            "",
            "Per-market breakdown:",
        ]

        for m in report.per_market:
            lines.append(
                f"  {m['market']}: {m['windows_per_day']} windows | "
                f"{m['observed_bets_per_day']:.1f} bets/day | "
                f"{m['signal_rate']:.1%} fire rate"
            )

        return "\n".join(lines)
