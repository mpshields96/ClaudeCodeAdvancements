"""edge_decay_detector.py — Strategy edge stability monitoring.

Detects whether a trading strategy's edge (win rate, EV) is stable,
improving, or deteriorating over time using rolling window analysis
and linear regression on window statistics.

Critical for the 5-day Kalshi challenge: if the sniper edge is decaying,
we need to know before it hits the WR cliff (93% → 92% is catastrophic).

Usage:
    from edge_decay_detector import EdgeDecayDetector, BetOutcome

    outcomes = [BetOutcome(date=d, pnl=p, strategy="sniper") for d, p in data]
    detector = EdgeDecayDetector(window_size=20)
    trend = detector.detect(outcomes)
    print(trend.direction)  # "stable", "improving", "declining", "unknown"

    if trend.should_alert:
        print(f"WARNING: {trend.message}")
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass
from datetime import date


@dataclass
class BetOutcome:
    """A single resolved bet."""

    date: date
    pnl: float
    strategy: str

    @property
    def is_win(self) -> bool:
        return self.pnl > 0


@dataclass
class WindowStats:
    """Statistics for a rolling window of bets."""

    start_date: date
    end_date: date
    n_bets: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expected_value: float
    daily_pnl: float

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "n_bets": self.n_bets,
            "win_rate": round(self.win_rate, 4),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "expected_value": round(self.expected_value, 4),
            "daily_pnl": round(self.daily_pnl, 2),
        }


@dataclass
class EdgeTrend:
    """Detected trend in the strategy's edge."""

    direction: str  # "stable", "improving", "declining", "unknown"
    wr_slope: float  # change in WR per window
    ev_slope: float  # change in EV per window
    confidence: float  # R^2 of the regression (0-1)
    message: str
    should_alert: bool = False

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "wr_slope": round(self.wr_slope, 6),
            "ev_slope": round(self.ev_slope, 6),
            "confidence": round(self.confidence, 4),
            "message": self.message,
            "should_alert": self.should_alert,
        }


def _linear_regression(ys: list[float]) -> tuple[float, float]:
    """Simple linear regression: returns (slope, r_squared).

    x values are 0, 1, 2, ..., len(ys)-1.
    """
    n = len(ys)
    if n < 2:
        return 0.0, 0.0

    xs = list(range(n))
    x_mean = (n - 1) / 2.0
    y_mean = statistics.mean(ys)

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)

    if denominator == 0:
        return 0.0, 0.0

    slope = numerator / denominator

    # R-squared
    ss_res = sum((y - (y_mean + slope * (x - x_mean))) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)

    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r_squared = max(0.0, r_squared)

    return slope, r_squared


class EdgeDecayDetector:
    """Detects edge stability using rolling window analysis."""

    MIN_WINDOWS = 3  # need at least 3 windows for trend detection

    def __init__(self, window_size: int = 20, alert_wr_drop: float = 0.05):
        """
        Args:
            window_size: Number of bets per rolling window.
            alert_wr_drop: WR drop (absolute) that triggers an alert.
        """
        self.window_size = window_size
        self.alert_wr_drop = alert_wr_drop

    def rolling_windows(
        self, outcomes: list[BetOutcome], strategy: str | None = None
    ) -> list[WindowStats]:
        """Compute rolling window statistics over bet outcomes."""
        filtered = outcomes
        if strategy:
            filtered = [o for o in outcomes if o.strategy == strategy]

        if len(filtered) < self.window_size:
            return []

        windows = []
        for i in range(0, len(filtered) - self.window_size + 1, self.window_size):
            chunk = filtered[i : i + self.window_size]
            wins = [o for o in chunk if o.is_win]
            losses = [o for o in chunk if not o.is_win]

            wr = len(wins) / len(chunk)
            avg_w = statistics.mean([o.pnl for o in wins]) if wins else 0.0
            avg_l = statistics.mean([o.pnl for o in losses]) if losses else 0.0
            ev = wr * avg_w + (1 - wr) * avg_l

            # Estimate daily P&L from this window
            days = (chunk[-1].date - chunk[0].date).days or 1
            daily = sum(o.pnl for o in chunk) / days

            windows.append(
                WindowStats(
                    start_date=chunk[0].date,
                    end_date=chunk[-1].date,
                    n_bets=len(chunk),
                    win_rate=wr,
                    avg_win=avg_w,
                    avg_loss=avg_l,
                    expected_value=ev,
                    daily_pnl=daily,
                )
            )

        return windows

    def detect(
        self, outcomes: list[BetOutcome], strategy: str | None = None
    ) -> EdgeTrend:
        """Detect edge trend from bet outcomes."""
        windows = self.rolling_windows(outcomes, strategy)

        if len(windows) < self.MIN_WINDOWS:
            return EdgeTrend(
                direction="unknown",
                wr_slope=0.0,
                ev_slope=0.0,
                confidence=0.0,
                message=f"Insufficient data: {len(windows)} windows"
                f" (need {self.MIN_WINDOWS})",
                should_alert=False,
            )

        # Regression on WR and EV across windows
        wr_values = [w.win_rate for w in windows]
        ev_values = [w.expected_value for w in windows]

        wr_slope, wr_r2 = _linear_regression(wr_values)
        ev_slope, ev_r2 = _linear_regression(ev_values)

        # Determine direction based on WR slope
        # Thresholds: slope magnitude and R^2 confidence
        total_wr_change = wr_slope * (len(windows) - 1)

        if abs(total_wr_change) < 0.02:
            direction = "stable"
            message = (
                f"Edge stable: WR change {total_wr_change:+.1%} over"
                f" {len(windows)} windows (R2={wr_r2:.2f})"
            )
        elif total_wr_change > 0:
            direction = "improving"
            message = (
                f"Edge improving: WR +{total_wr_change:.1%} over"
                f" {len(windows)} windows (R2={wr_r2:.2f})"
            )
        else:
            direction = "declining"
            message = (
                f"Edge declining: WR {total_wr_change:.1%} over"
                f" {len(windows)} windows (R2={wr_r2:.2f})"
            )

        # Alert if WR dropped more than threshold
        should_alert = False
        if len(windows) >= 2:
            first_wr = statistics.mean(wr_values[: len(wr_values) // 2])
            last_wr = statistics.mean(wr_values[len(wr_values) // 2 :])
            if first_wr - last_wr >= self.alert_wr_drop:
                should_alert = True
                message += (
                    f" ALERT: WR dropped {first_wr:.1%} → {last_wr:.1%}"
                    f" (>{self.alert_wr_drop:.0%} threshold)"
                )

        return EdgeTrend(
            direction=direction,
            wr_slope=wr_slope,
            ev_slope=ev_slope,
            confidence=wr_r2,
            message=message,
            should_alert=should_alert,
        )

    def full_report(
        self, outcomes: list[BetOutcome], strategy: str | None = None
    ) -> dict:
        """Generate complete edge decay analysis report."""
        windows = self.rolling_windows(outcomes, strategy)
        trend = self.detect(outcomes, strategy)

        return {
            "trend": trend.to_dict(),
            "windows": [w.to_dict() for w in windows],
            "latest_window": windows[-1].to_dict() if windows else None,
            "n_outcomes": len(outcomes),
            "window_size": self.window_size,
            "n_windows": len(windows),
        }
