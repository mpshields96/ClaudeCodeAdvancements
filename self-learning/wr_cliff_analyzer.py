"""wr_cliff_analyzer.py — Win rate cliff detection.

Identifies the exact win rate threshold where ruin probability jumps
from safe (<5%) to dangerous (>20%) for given strategy parameters.
Maps these cliffs across different avg_loss levels.

Key insight from REQ-57: at current -$11.39 avg_loss, the cliff is
between 92% and 94% WR. This module finds the precise breakpoint.

Usage:
    from wr_cliff_analyzer import WRCliffAnalyzer

    analyzer = WRCliffAnalyzer(
        current_wr=0.933, avg_win=0.90,
        daily_volume=78, bankroll=178.05,
    )
    cliff_map = analyzer.cliff_map(loss_levels=[-11.39, -10.0, -8.0, -6.0])
    print(cliff_map.summary())
"""
from __future__ import annotations
import random
from dataclasses import dataclass

from monte_carlo_simulator import BetDistribution, MonteCarloSimulator


@dataclass
class CliffPoint:
    """A WR cliff at a specific avg_loss level."""

    avg_loss: float
    cliff_wr: float  # WR where ruin crosses threshold
    safe_wr: float  # lowest WR tested where ruin < safe_threshold
    danger_wr: float  # highest WR tested where ruin > danger_threshold
    margin_from_current: float  # current_wr - cliff_wr

    def to_dict(self) -> dict:
        return {
            "avg_loss": round(self.avg_loss, 2),
            "cliff_wr": round(self.cliff_wr, 4),
            "safe_wr": round(self.safe_wr, 4),
            "danger_wr": round(self.danger_wr, 4),
            "margin_from_current": round(self.margin_from_current, 4),
        }


@dataclass
class WRCliffMap:
    """Map of WR cliffs across avg_loss levels."""

    current_wr: float
    current_avg_loss: float
    cliffs: list[CliffPoint]

    def safety_margin(self) -> float:
        """Distance from current WR to nearest cliff (at current avg_loss)."""
        for c in self.cliffs:
            if abs(c.avg_loss - self.current_avg_loss) < 0.01:
                return c.margin_from_current
        if self.cliffs:
            return self.cliffs[0].margin_from_current
        return 0.0

    def summary(self) -> str:
        lines = [
            f"WR Cliff Map (current WR: {self.current_wr:.1%})",
            f"{'avg_loss':>10} {'cliff_WR':>10} {'safe_WR':>10} {'danger_WR':>10} {'margin':>10}",
            "-" * 55,
        ]
        for c in self.cliffs:
            lines.append(
                f"${c.avg_loss:>8.2f} {c.cliff_wr:>10.1%}"
                f" {c.safe_wr:>10.1%} {c.danger_wr:>10.1%}"
                f" {c.margin_from_current:>+10.1%}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "current_wr": round(self.current_wr, 4),
            "current_avg_loss": round(self.current_avg_loss, 2),
            "cliffs": [c.to_dict() for c in self.cliffs],
        }


class WRCliffAnalyzer:
    """Finds WR cliffs using binary search with Monte Carlo validation."""

    SAFE_RUIN_THRESHOLD = 0.05  # ruin < 5% = "safe"
    DANGER_RUIN_THRESHOLD = 0.20  # ruin > 20% = "dangerous"

    def __init__(
        self,
        current_wr: float,
        avg_win: float,
        daily_volume: int,
        bankroll: float,
        target: float = 250.0,
        n_days: int = 60,
    ):
        self.current_wr = current_wr
        self.avg_win = avg_win
        self.daily_volume = daily_volume
        self.bankroll = bankroll
        self.target = target
        self.n_days = n_days

    def _run_sim(
        self, wr: float, avg_loss: float, n_sims: int, seed: int | None
    ) -> float:
        """Run Monte Carlo and return ruin probability."""
        dist = BetDistribution(
            win_rate=wr,
            avg_win=self.avg_win,
            avg_loss=avg_loss,
            daily_volume=self.daily_volume,
            total_bets=100,
        )
        sim = MonteCarloSimulator(dist)
        result = sim.run(
            starting_bankroll=self.bankroll,
            target_bankroll=self.target,
            n_days=self.n_days,
            n_simulations=n_sims,
            seed=seed,
        )
        return result.ruin_probability

    def find_cliff(
        self,
        avg_loss: float,
        n_sims: int = 1000,
        seed: int | None = None,
        wr_low: float = 0.80,
        wr_high: float = 0.99,
        precision: float = 0.005,
    ) -> CliffPoint:
        """Binary search for the WR cliff at a given avg_loss.

        Finds the WR where ruin crosses from safe (<5%) to dangerous (>20%).
        """
        best_safe = wr_high
        best_danger = wr_low

        # Binary search for the cliff
        while wr_high - wr_low > precision:
            mid = (wr_low + wr_high) / 2
            ruin = self._run_sim(mid, avg_loss, n_sims, seed)

            if ruin <= self.SAFE_RUIN_THRESHOLD:
                best_safe = min(best_safe, mid)
                wr_high = mid
            elif ruin >= self.DANGER_RUIN_THRESHOLD:
                best_danger = max(best_danger, mid)
                wr_low = mid
            else:
                # In the transition zone
                wr_high = mid

        cliff_wr = (best_safe + best_danger) / 2
        margin = self.current_wr - cliff_wr

        return CliffPoint(
            avg_loss=avg_loss,
            cliff_wr=cliff_wr,
            safe_wr=best_safe,
            danger_wr=best_danger,
            margin_from_current=margin,
        )

    def cliff_map(
        self,
        loss_levels: list[float] | None = None,
        n_sims: int = 1000,
        seed: int | None = None,
    ) -> WRCliffMap:
        """Build a cliff map across multiple avg_loss levels."""
        if loss_levels is None:
            loss_levels = [-11.39, -10.0, -9.0, -8.0, -7.0, -6.0]

        cliffs = []
        for loss in loss_levels:
            cliff = self.find_cliff(loss, n_sims=n_sims, seed=seed)
            cliffs.append(cliff)

        return WRCliffMap(
            current_wr=self.current_wr,
            current_avg_loss=loss_levels[0] if loss_levels else -11.39,
            cliffs=cliffs,
        )

    def full_report(
        self,
        loss_levels: list[float] | None = None,
        n_sims: int = 1000,
        seed: int | None = None,
    ) -> dict:
        """Generate complete cliff analysis report."""
        cm = self.cliff_map(loss_levels=loss_levels, n_sims=n_sims, seed=seed)

        # Recommendation based on safety margin
        margin = cm.safety_margin()
        if margin < 0.01:
            recommendation = (
                "CRITICAL: Current WR is within 1% of the ruin cliff. "
                "Reduce avg_loss immediately to widen the safety margin."
            )
        elif margin < 0.03:
            recommendation = (
                "WARNING: Safety margin is narrow ({:.1%}). "
                "Consider avg_loss reduction to gain breathing room.".format(margin)
            )
        else:
            recommendation = (
                "HEALTHY: Safety margin of {:.1%} from cliff. "
                "Current parameters are sustainable.".format(margin)
            )

        return {
            "cliff_map": cm.to_dict(),
            "safety_margin": round(margin, 4),
            "recommendation": recommendation,
        }
