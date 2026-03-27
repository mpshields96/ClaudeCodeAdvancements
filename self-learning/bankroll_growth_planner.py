"""bankroll_growth_planner.py — Bankroll trajectory projections.

Projects bankroll growth over N days using current strategy parameters.
Answers key questions for the 5-day Kalshi challenge:
1. What will bankroll be after 5/30/60 days at current parameters?
2. When does ruin probability become negligible?
3. When does daily P&L exceed self-sustaining threshold ($8.33/day)?

Uses analytical approximation (CLT for daily P&L distribution) rather
than Monte Carlo — faster, deterministic, no random seed dependency.

Usage:
    from bankroll_growth_planner import GrowthParams, BankrollGrowthPlanner

    params = GrowthParams(
        starting_bankroll=178.05, daily_pnl=5.97, daily_volume=78,
        win_rate=0.933, avg_win=0.90, avg_loss=-11.39,
    )
    planner = BankrollGrowthPlanner(params)
    plan = planner.project(n_days=30)
    print(plan.summary())
"""
import math
from dataclasses import dataclass, field


@dataclass
class GrowthParams:
    """Parameters for bankroll growth projection."""

    starting_bankroll: float
    daily_pnl: float  # expected daily P&L
    daily_volume: int  # bets per day
    win_rate: float
    avg_win: float
    avg_loss: float  # negative

    def bet_variance(self) -> float:
        """Variance of a single bet outcome."""
        ev = self.win_rate * self.avg_win + (1 - self.win_rate) * self.avg_loss
        return (
            self.win_rate * (self.avg_win - ev) ** 2
            + (1 - self.win_rate) * (self.avg_loss - ev) ** 2
        )

    def daily_variance(self) -> float:
        """Variance of daily P&L (sum of independent bets)."""
        return self.bet_variance() * self.daily_volume

    def daily_std(self) -> float:
        """Standard deviation of daily P&L."""
        return math.sqrt(self.daily_variance())

    def to_dict(self) -> dict:
        return {
            "starting_bankroll": round(self.starting_bankroll, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_volume": self.daily_volume,
            "win_rate": round(self.win_rate, 4),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "daily_std": round(self.daily_std(), 2),
        }


@dataclass
class DayProjection:
    """Projection for a single day."""

    day: int
    expected_bankroll: float
    p5_bankroll: float  # 5th percentile (pessimistic)
    p95_bankroll: float  # 95th percentile (optimistic)
    ruin_probability: float
    self_sustaining: bool  # daily P&L >= $8.33

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "expected_bankroll": round(self.expected_bankroll, 2),
            "p5_bankroll": round(self.p5_bankroll, 2),
            "p95_bankroll": round(self.p95_bankroll, 2),
            "ruin_probability": round(self.ruin_probability, 4),
            "self_sustaining": self.self_sustaining,
        }


@dataclass
class GrowthPlan:
    """Complete growth projection over N days."""

    params: GrowthParams
    projections: list[DayProjection]
    days_to_self_sustaining: int | None  # None if already there or never
    days_to_safe_bankroll: int | None  # day when ruin < 1%

    def summary(self) -> str:
        lines = [
            f"Bankroll Growth Projection (start: ${self.params.starting_bankroll:.2f},"
            f" daily P&L: ${self.params.daily_pnl:.2f})",
            f"{'Day':>5} {'Expected':>10} {'P5':>10} {'P95':>10} {'Ruin':>8}",
            "-" * 50,
        ]
        for p in self.projections:
            flag = " *" if p.self_sustaining else ""
            lines.append(
                f"{p.day:>5} ${p.expected_bankroll:>9.2f}"
                f" ${p.p5_bankroll:>9.2f} ${p.p95_bankroll:>9.2f}"
                f" {p.ruin_probability:>7.2%}{flag}"
            )
        if self.days_to_safe_bankroll is not None:
            lines.append(f"\nSafe bankroll (ruin < 1%): day {self.days_to_safe_bankroll}")
        if self.days_to_self_sustaining is not None:
            lines.append(f"Self-sustaining ($8.33/day): day {self.days_to_self_sustaining}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "params": self.params.to_dict(),
            "projections": [p.to_dict() for p in self.projections],
            "days_to_self_sustaining": self.days_to_self_sustaining,
            "days_to_safe_bankroll": self.days_to_safe_bankroll,
        }


class BankrollGrowthPlanner:
    """Projects bankroll trajectory using analytical (CLT) approximation."""

    SELF_SUSTAINING_DAILY = 250.0 / 30.0  # $8.33/day

    def __init__(self, params: GrowthParams):
        self.params = params

    def _ruin_estimate(self, bankroll: float) -> float:
        """Exponential ruin approximation: P(ruin) ≈ exp(-2 * EV * B / Var).

        Uses daily aggregates for more realistic estimate.
        """
        daily_ev = self.params.daily_pnl
        daily_var = self.params.daily_variance()

        if daily_var <= 0 or daily_ev <= 0 or bankroll <= 0:
            return 1.0

        ruin = math.exp(-2 * daily_ev * bankroll / daily_var)
        return min(1.0, max(0.0, ruin))

    def _z_score(self, percentile: float) -> float:
        """Approximate z-score for normal distribution percentile."""
        # Approximation for common percentiles
        z_table = {
            0.01: -2.326, 0.05: -1.645, 0.10: -1.282,
            0.25: -0.674, 0.50: 0.0,
            0.75: 0.674, 0.90: 1.282, 0.95: 1.645, 0.99: 2.326,
        }
        return z_table.get(percentile, 0.0)

    def project(self, n_days: int = 30) -> GrowthPlan:
        """Project bankroll trajectory for n_days."""
        projections = []
        daily_ev = self.params.daily_pnl
        daily_std = self.params.daily_std()
        z5 = self._z_score(0.05)
        z95 = self._z_score(0.95)

        days_safe = None
        days_sustaining = None

        for day in range(1, n_days + 1):
            # Expected bankroll after `day` days
            expected = self.params.starting_bankroll + daily_ev * day

            # CLT: cumulative P&L after `day` days ~ N(day*EV, day*Var)
            cumulative_std = daily_std * math.sqrt(day)
            p5 = expected + z5 * cumulative_std
            p95 = expected + z95 * cumulative_std

            # Ruin based on expected bankroll at this point
            ruin = self._ruin_estimate(expected)

            # Self-sustaining check (fixed bet size = same daily P&L regardless of bankroll)
            is_sustaining = daily_ev >= self.SELF_SUSTAINING_DAILY

            projections.append(DayProjection(
                day=day,
                expected_bankroll=expected,
                p5_bankroll=p5,
                p95_bankroll=p95,
                ruin_probability=ruin,
                self_sustaining=is_sustaining,
            ))

            if days_safe is None and ruin < 0.01:
                days_safe = day
            if days_sustaining is None and is_sustaining:
                days_sustaining = day

        return GrowthPlan(
            params=self.params,
            projections=projections,
            days_to_self_sustaining=days_sustaining,
            days_to_safe_bankroll=days_safe,
        )

    def milestones(self, n_days: int = 60) -> dict:
        """Key milestone projections."""
        plan = self.project(n_days=n_days)

        def get_day(d: int) -> dict | None:
            for p in plan.projections:
                if p.day == d:
                    return p.to_dict()
            return None

        return {
            "day_5": get_day(5),
            "day_10": get_day(10),
            "day_30": get_day(30),
            "day_60": get_day(60),
            "days_to_safe_bankroll": plan.days_to_safe_bankroll,
            "days_to_self_sustaining": plan.days_to_self_sustaining,
        }

    def full_report(self, n_days: int = 30) -> dict:
        """Complete growth analysis report."""
        plan = self.project(n_days=n_days)
        milestones = self.milestones(n_days=max(n_days, 60))

        return {
            "plan": plan.to_dict(),
            "milestones": milestones,
            "current_daily_vs_target": {
                "current_daily": round(self.params.daily_pnl, 2),
                "target_daily": round(self.SELF_SUSTAINING_DAILY, 2),
                "gap_pct": round(
                    (1 - self.params.daily_pnl / self.SELF_SUSTAINING_DAILY) * 100, 1
                )
                if self.params.daily_pnl < self.SELF_SUSTAINING_DAILY
                else 0.0,
                "monthly_at_current": round(self.params.daily_pnl * 30, 2),
            },
        }
