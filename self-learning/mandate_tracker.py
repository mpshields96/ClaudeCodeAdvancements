"""5-day mandate progress tracker.

Tracks daily P&L against a configurable target window (default: $15-25/day
over 5 days). Projects success probability based on observed performance,
detects pace problems early, and recommends adjustments.

Usage:
    from mandate_tracker import MandateTracker, MandateConfig, DailyResult
    from datetime import date

    cfg = MandateConfig(total_days=5, daily_target_low=15.0, daily_target_high=25.0)
    tracker = MandateTracker(cfg)

    tracker.add_day(DailyResult(day=1, date=date(2026, 3, 27),
                                pnl=20.0, bets=64, wins=60, losses=4))
    print(tracker.summary_text())
    print(tracker.to_dict())  # JSON-serializable for monitoring
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass
class DailyResult:
    """One day's trading performance."""

    day: int  # 1-indexed day of the mandate
    date: date
    pnl: float  # net P&L in USD
    bets: int
    wins: int
    losses: int

    def win_rate(self) -> float:
        """Win rate as a fraction (0.0-1.0)."""
        if self.bets == 0:
            return 0.0
        return self.wins / self.bets

    def avg_pnl_per_bet(self) -> float:
        """Average P&L per bet."""
        if self.bets == 0:
            return 0.0
        return self.pnl / self.bets


@dataclass
class MandateConfig:
    """Configuration for a trading mandate."""

    total_days: int = 5
    daily_target_low: float = 15.0  # minimum acceptable daily avg
    daily_target_high: float = 25.0  # ideal daily avg
    expected_bets_per_day: int = 64  # for frequency comparison
    expected_wr: float = 0.933  # for WR comparison

    def total_target_low(self) -> float:
        return self.total_days * self.daily_target_low

    def total_target_high(self) -> float:
        return self.total_days * self.daily_target_high


@dataclass
class MandateStatus:
    """Current mandate status snapshot."""

    days_completed: int
    days_remaining: int
    total_pnl: float
    avg_daily_pnl: float
    projected_total: float  # avg_daily * total_days
    needed_daily_pace_low: float  # daily avg needed to hit low target
    needed_daily_pace_high: float  # daily avg needed to hit high target
    verdict: str  # PENDING, BEHIND, ON_TRACK, AHEAD, SUCCESS, FAILED
    avg_bets_per_day: float
    avg_wr: float


class MandateTracker:
    """Tracks progress toward a multi-day P&L mandate."""

    def __init__(self, config: MandateConfig) -> None:
        self.config = config
        self.days: List[DailyResult] = []

    def add_day(self, result: DailyResult) -> None:
        """Add a daily result."""
        self.days.append(result)

    def status(self) -> MandateStatus:
        """Compute current mandate status."""
        cfg = self.config
        n = len(self.days)
        remaining = cfg.total_days - n

        total_pnl = sum(d.pnl for d in self.days)
        avg_daily = total_pnl / n if n > 0 else 0.0
        projected = avg_daily * cfg.total_days

        total_bets = sum(d.bets for d in self.days)
        total_wins = sum(d.wins for d in self.days)
        avg_bets = total_bets / n if n > 0 else 0.0
        avg_wr = total_wins / total_bets if total_bets > 0 else 0.0

        # What daily pace is needed for remaining days?
        if remaining > 0:
            needed_low = (cfg.total_target_low() - total_pnl) / remaining
            needed_high = (cfg.total_target_high() - total_pnl) / remaining
        else:
            needed_low = 0.0
            needed_high = 0.0

        verdict = self._compute_verdict(n, remaining, total_pnl, projected)

        return MandateStatus(
            days_completed=n,
            days_remaining=remaining,
            total_pnl=total_pnl,
            avg_daily_pnl=avg_daily,
            projected_total=projected,
            needed_daily_pace_low=needed_low,
            needed_daily_pace_high=needed_high,
            verdict=verdict,
            avg_bets_per_day=avg_bets,
            avg_wr=avg_wr,
        )

    def _compute_verdict(self, n: int, remaining: int, total_pnl: float,
                         projected: float) -> str:
        """Determine mandate verdict."""
        cfg = self.config
        if n == 0:
            return "PENDING"

        # Mandate complete
        if remaining == 0:
            if total_pnl >= cfg.total_target_low():
                return "SUCCESS"
            return "FAILED"

        # In progress — evaluate pace
        if projected >= cfg.total_target_high():
            return "AHEAD"
        if projected >= cfg.total_target_low():
            return "ON_TRACK"
        return "BEHIND"

    def recommendations(self) -> List[str]:
        """Generate actionable recommendations based on current data."""
        if not self.days:
            return ["No data yet. Run first day of trading."]

        recs = []
        s = self.status()
        cfg = self.config

        # Check bet frequency
        if s.avg_bets_per_day < cfg.expected_bets_per_day * 0.6:
            recs.append(
                f"Low bet frequency: {s.avg_bets_per_day:.0f}/day vs "
                f"{cfg.expected_bets_per_day} expected. Check signal suppression or "
                f"market availability. Need more bets to hit target."
            )

        # Check win rate
        if s.avg_wr < cfg.expected_wr - 0.02:
            recs.append(
                f"Win rate below expected: {s.avg_wr:.1%} vs {cfg.expected_wr:.1%}. "
                f"Consider reviewing asset selection or entry thresholds."
            )

        # Check if behind pace
        if s.verdict == "BEHIND" and s.days_remaining > 0:
            recs.append(
                f"Behind pace. Need ${s.needed_daily_pace_low:.2f}/day to hit "
                f"${cfg.total_target_low():.0f} total. Current avg: "
                f"${s.avg_daily_pnl:.2f}/day."
            )

        # Variance warning on losing days
        losing_days = [d for d in self.days if d.pnl < 0]
        if losing_days and s.days_remaining > 0:
            recs.append(
                f"{len(losing_days)} losing day(s) observed. At 93% WR with "
                f"asymmetric payoff, this is expected variance. Do NOT increase "
                f"bet size to compensate."
            )

        # Good performance
        if s.verdict in ("ON_TRACK", "AHEAD") and not recs:
            recs.append("Performance on track. Maintain current strategy. No changes needed.")

        return recs

    def to_dict(self) -> dict:
        """Export full state as a JSON-serializable dict."""
        s = self.status()
        return {
            "config": {
                "total_days": self.config.total_days,
                "daily_target_low": self.config.daily_target_low,
                "daily_target_high": self.config.daily_target_high,
            },
            "days": [
                {
                    "day": d.day,
                    "date": d.date.isoformat(),
                    "pnl": d.pnl,
                    "bets": d.bets,
                    "wins": d.wins,
                    "losses": d.losses,
                    "win_rate": round(d.win_rate(), 4),
                }
                for d in self.days
            ],
            "status": {
                "days_completed": s.days_completed,
                "days_remaining": s.days_remaining,
                "total_pnl": round(s.total_pnl, 2),
                "avg_daily_pnl": round(s.avg_daily_pnl, 2),
                "projected_total": round(s.projected_total, 2),
                "needed_daily_pace_low": round(s.needed_daily_pace_low, 2),
                "needed_daily_pace_high": round(s.needed_daily_pace_high, 2),
                "verdict": s.verdict,
                "avg_bets_per_day": round(s.avg_bets_per_day, 1),
                "avg_wr": round(s.avg_wr, 4),
            },
            "recommendations": self.recommendations(),
        }

    def summary_text(self) -> str:
        """Human-readable summary for monitoring output."""
        s = self.status()
        lines = [
            f"=== MANDATE TRACKER: Day {s.days_completed}/{self.config.total_days} ===",
            f"Verdict: {s.verdict}",
            f"Total P&L: ${s.total_pnl:.2f}",
            f"Avg daily: ${s.avg_daily_pnl:.2f}/day",
            f"Projected 5-day total: ${s.projected_total:.2f}",
        ]

        if s.days_remaining > 0 and s.days_completed > 0:
            lines.append(
                f"Need: ${s.needed_daily_pace_low:.2f}/day to hit "
                f"${self.config.total_target_low():.0f} target"
            )

        lines.append(f"Avg bets/day: {s.avg_bets_per_day:.0f} | Avg WR: {s.avg_wr:.1%}")
        lines.append("")

        for d in self.days:
            marker = "+" if d.pnl >= 0 else ""
            lines.append(
                f"  Day {d.day} ({d.date}): {marker}${d.pnl:.2f} | "
                f"{d.bets} bets | {d.win_rate():.1%} WR"
            )

        recs = self.recommendations()
        if recs:
            lines.append("")
            lines.append("Recommendations:")
            for r in recs:
                lines.append(f"  - {r}")

        return "\n".join(lines)
