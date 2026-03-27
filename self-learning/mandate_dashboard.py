"""Unified mandate monitoring dashboard.

Combines mandate_tracker, kelly_optimizer, and window_frequency_estimator
into a single dashboard. One call produces a complete mandate health report.

Usage:
    from mandate_dashboard import MandateDashboard, MandateDashboardConfig, DailySnapshot
    from datetime import date

    cfg = MandateDashboardConfig()
    dash = MandateDashboard(cfg)
    dash.add_day(DailySnapshot(day=1, date=date(2026, 3, 27),
                               pnl=20.0, bets=64, wins=60, losses=4, bankroll=233.80))
    report = dash.run()
    print(dash.summary_text())
"""
from dataclasses import dataclass
from datetime import date
from typing import List

from mandate_tracker import MandateTracker, MandateConfig, DailyResult
from kelly_optimizer import KellyOptimizer, KellyParams
from window_frequency_estimator import (
    WindowFrequencyEstimator, MarketConfig, ObservedRate,
)


@dataclass
class DailySnapshot:
    """One day's complete trading data for the dashboard."""

    day: int
    date: date
    pnl: float
    bets: int
    wins: int
    losses: int
    bankroll: float  # end-of-day bankroll

    def win_rate(self) -> float:
        if self.bets == 0:
            return 0.0
        return self.wins / self.bets


@dataclass
class MandateDashboardConfig:
    """Dashboard configuration with sensible defaults for 5-day mandate."""

    mandate_days: int = 5
    daily_target_low: float = 15.0
    daily_target_high: float = 25.0
    initial_bankroll: float = 213.80
    avg_win: float = 0.90
    avg_loss: float = 8.0
    expected_wr: float = 0.933
    # Market structure for frequency estimation
    markets: list = None

    def __post_init__(self):
        if self.markets is None:
            self.markets = [
                {"name": "KXBTC15M", "window_minutes": 15, "hours_per_day": 24},
                {"name": "KXETH15M", "window_minutes": 15, "hours_per_day": 24},
                {"name": "KXSOL15M", "window_minutes": 15, "hours_per_day": 24},
            ]


class MandateDashboard:
    """Unified mandate monitoring dashboard."""

    def __init__(self, config: MandateDashboardConfig) -> None:
        self.config = config
        self.snapshots: List[DailySnapshot] = []

    def add_day(self, snapshot: DailySnapshot) -> None:
        """Add a daily snapshot."""
        self.snapshots.append(snapshot)

    def run(self) -> dict:
        """Run all analyses and return unified report."""
        cfg = self.config

        # 1. Mandate tracker
        mandate_cfg = MandateConfig(
            total_days=cfg.mandate_days,
            daily_target_low=cfg.daily_target_low,
            daily_target_high=cfg.daily_target_high,
            expected_bets_per_day=64,
            expected_wr=cfg.expected_wr,
        )
        tracker = MandateTracker(mandate_cfg)
        for s in self.snapshots:
            tracker.add_day(DailyResult(
                day=s.day, date=s.date, pnl=s.pnl,
                bets=s.bets, wins=s.wins, losses=s.losses,
            ))
        mandate_report = tracker.to_dict()

        # 2. Kelly optimizer (use latest bankroll)
        bankroll = cfg.initial_bankroll
        if self.snapshots:
            bankroll = self.snapshots[-1].bankroll

        # Compute observed avg_win and avg_loss from data if available
        total_wins = sum(s.wins for s in self.snapshots)
        total_losses = sum(s.losses for s in self.snapshots)
        total_bets = sum(s.bets for s in self.snapshots)
        observed_wr = total_wins / total_bets if total_bets > 0 else cfg.expected_wr

        kelly_params = KellyParams(
            win_rate=observed_wr,
            avg_win=cfg.avg_win,
            avg_loss=cfg.avg_loss,
            bankroll=bankroll,
        )
        kelly_opt = KellyOptimizer(kelly_params)
        kelly_report = kelly_opt.to_dict()

        # 3. Window frequency estimator
        markets = [
            MarketConfig(name=m["name"], window_minutes=m["window_minutes"],
                         hours_per_day=m["hours_per_day"])
            for m in cfg.markets
        ]
        # Build observed rates from snapshots
        total_days = len(self.snapshots) if self.snapshots else 1
        total_obs_bets = sum(s.bets for s in self.snapshots)
        observed = []
        if total_obs_bets > 0:
            # Distribute evenly across markets as approximation
            per_market = total_obs_bets // len(markets)
            for m in markets:
                observed.append(ObservedRate(
                    market=m.name, total_bets=per_market, days_observed=total_days,
                ))

        freq_est = WindowFrequencyEstimator(markets, observed)
        freq_report = freq_est.estimate(
            win_rate=observed_wr, avg_win=cfg.avg_win, avg_loss=cfg.avg_loss,
        )

        # 4. Overall health assessment
        mandate_status = tracker.status()
        health = self._assess_health(mandate_status, kelly_opt.compute(), freq_report)

        return {
            "mandate": mandate_report,
            "kelly": kelly_report,
            "frequency": {
                "total_theoretical_windows": freq_report.total_theoretical_windows,
                "total_observed_bets_per_day": freq_report.total_observed_bets_per_day,
                "signal_utilization": freq_report.signal_utilization,
                "capacity_headroom": freq_report.capacity_headroom,
                "per_market": freq_report.per_market,
                "ev_table": freq_report.ev_table,
            },
            "overall_health": health,
        }

    def _assess_health(self, mandate_status, kelly_result, freq_report) -> str:
        """Determine overall dashboard health."""
        problems = 0

        # Mandate behind
        if mandate_status.verdict == "BEHIND":
            problems += 2
        if mandate_status.verdict == "FAILED":
            problems += 3

        # WR significantly below expected
        if mandate_status.avg_wr < self.config.expected_wr - 0.03:
            problems += 1

        # Very low frequency
        if mandate_status.avg_bets_per_day < 30:
            problems += 1

        # Negative edge
        if kelly_result.edge_per_bet <= 0:
            problems += 3

        if problems >= 3:
            return "CRITICAL"
        if problems >= 1:
            return "WARNING"
        return "HEALTHY"

    def summary_text(self) -> str:
        """Human-readable dashboard summary."""
        report = self.run()
        ms = report["mandate"]["status"]
        ks = report["kelly"]["kelly"]
        fs = report["frequency"]

        lines = [
            "=" * 60,
            "  MANDATE DASHBOARD — 5-DAY PROGRESS REPORT",
            "=" * 60,
            "",
            f"  Overall Health: {report['overall_health']}",
            "",
            "--- MANDATE TRACKER ---",
            f"  Days: {ms['days_completed']}/{self.config.mandate_days}",
            f"  Verdict: {ms['verdict']}",
            f"  Total P&L: ${ms['total_pnl']:.2f}",
            f"  Avg daily: ${ms['avg_daily_pnl']:.2f}/day",
            f"  Projected: ${ms['projected_total']:.2f}",
        ]

        if ms["days_remaining"] > 0 and ms["days_completed"] > 0:
            lines.append(
                f"  Need: ${ms['needed_daily_pace_low']:.2f}/day for ${self.config.daily_target_low * self.config.mandate_days:.0f} target"
            )

        lines.extend([
            "",
            "--- KELLY OPTIMIZER ---",
            f"  Full Kelly: {ks['full_kelly_fraction']:.4f} = ${ks['full_kelly_bet']:.2f}/bet",
            f"  Quarter Kelly: {ks['quarter_kelly_fraction']:.4f} = ${ks['quarter_kelly_bet']:.2f}/bet",
            f"  Recommended: ${ks['recommended_bet']:.2f}/bet",
            "",
            "--- FREQUENCY ANALYSIS ---",
            f"  Theoretical windows/day: {fs['total_theoretical_windows']}",
            f"  Observed bets/day: {fs['total_observed_bets_per_day']}",
            f"  Utilization: {fs['signal_utilization']:.1%}",
            f"  Headroom: {fs['capacity_headroom']:.0f} unused windows",
        ])

        recs = report["mandate"].get("recommendations", [])
        if recs:
            lines.extend(["", "--- RECOMMENDATIONS ---"])
            for r in recs:
                lines.append(f"  - {r}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
