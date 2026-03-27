"""Signal threshold sensitivity analyzer.

Models how bet frequency and WR change at various drift thresholds.
Uses calibration data from observed trading at known thresholds to
extrapolate performance at hypothetical thresholds.

The core tradeoff: lower thresholds = more signals but lower WR.
This tool finds the EV-optimal threshold.

Model assumptions (conservative):
- Frequency scales inversely with threshold (lower = more signals)
- WR degrades linearly as threshold decreases (weaker signals)
- These are first-order approximations calibrated from observed data

Usage:
    from signal_threshold_analyzer import SignalThresholdAnalyzer, ThresholdPoint

    calibration = [
        ThresholdPoint(threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
                       avg_win=0.90, avg_loss=8.0),
    ]
    analyzer = SignalThresholdAnalyzer(calibration)
    report = analyzer.sweep()
    print(analyzer.summary_text())
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ThresholdPoint:
    """Performance at a specific drift threshold."""

    threshold_pct: float  # e.g. 0.10 for 0.10%
    bets_per_day: float
    win_rate: float
    avg_win: float
    avg_loss: float

    def edge_per_bet(self) -> float:
        """Expected value per bet."""
        q = 1.0 - self.win_rate
        return self.win_rate * self.avg_win - q * self.avg_loss

    def expected_daily_pnl(self) -> float:
        """Expected daily P&L."""
        return self.bets_per_day * self.edge_per_bet()


@dataclass
class ThresholdReport:
    """Result of a threshold sweep."""

    points: List[ThresholdPoint]
    optimal_threshold: float
    optimal_daily_pnl: float
    recommendation: str


class SignalThresholdAnalyzer:
    """Analyzes drift threshold sensitivity on frequency and WR."""

    # Default sweep thresholds
    SWEEP_THRESHOLDS = [0.02, 0.03, 0.05, 0.07, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]

    def __init__(self, calibration: List[ThresholdPoint]) -> None:
        self.calibration = calibration

    def sweep(self, thresholds: Optional[List[float]] = None) -> ThresholdReport:
        """Sweep across thresholds and find the optimal one."""
        if thresholds is None:
            thresholds = self.SWEEP_THRESHOLDS

        # Use calibration to build interpolation model
        # Primary calibration point (highest confidence)
        cal = self.calibration[0]

        # Model: frequency ~ 1/threshold (more signals at lower thresholds)
        # Model: WR degrades as threshold decreases
        # Calibration: at cal.threshold_pct, we observe cal.bets_per_day and cal.win_rate
        ref_threshold = cal.threshold_pct
        ref_bets = cal.bets_per_day
        ref_wr = cal.win_rate

        # If we have multiple calibration points, use them to improve the model
        if len(self.calibration) >= 2:
            cal2 = self.calibration[1]
            # Estimate frequency scaling factor from two points
            # bets ~ k / threshold^alpha
            if cal2.threshold_pct != cal.threshold_pct and cal2.bets_per_day > 0:
                import math
                ratio_t = cal.threshold_pct / cal2.threshold_pct
                ratio_b = cal.bets_per_day / cal2.bets_per_day
                if ratio_t > 0 and ratio_b > 0:
                    alpha = math.log(ratio_b) / math.log(ratio_t)
                else:
                    alpha = 1.0
            else:
                alpha = 1.0
        else:
            alpha = 1.0  # Default: linear inverse relationship

        points = []
        for t in thresholds:
            # Estimate frequency: bets ~ ref_bets * (ref_threshold / t)^alpha
            freq = ref_bets * (ref_threshold / t) ** alpha
            # Cap frequency at theoretical max (288 windows for 3 assets)
            freq = min(freq, 288.0)

            # Estimate WR degradation
            # At reference threshold, WR = ref_wr
            # As threshold decreases, WR drops (weaker signals)
            # Conservative model: WR drops 1% per 0.02% threshold decrease
            threshold_diff = ref_threshold - t  # positive if t < ref
            wr_drop = max(0, threshold_diff) * 0.5  # 0.5% WR per 0.01% threshold decrease
            wr = max(0.50, ref_wr - wr_drop)  # floor at 50%

            # As threshold increases above reference, WR improves slightly
            if t > ref_threshold:
                wr_gain = (t - ref_threshold) * 0.2  # smaller gains going up
                wr = min(0.98, ref_wr + wr_gain)

            points.append(ThresholdPoint(
                threshold_pct=t,
                bets_per_day=round(freq, 1),
                win_rate=round(wr, 4),
                avg_win=cal.avg_win,
                avg_loss=cal.avg_loss,
            ))

        # Find optimal (max daily EV)
        best = max(points, key=lambda p: p.expected_daily_pnl())
        recommendation = self._make_recommendation(best, cal)

        return ThresholdReport(
            points=points,
            optimal_threshold=best.threshold_pct,
            optimal_daily_pnl=round(best.expected_daily_pnl(), 2),
            recommendation=recommendation,
        )

    def _make_recommendation(self, best: ThresholdPoint,
                             current: ThresholdPoint) -> str:
        """Generate actionable recommendation."""
        if best.threshold_pct == current.threshold_pct:
            return (
                f"Current threshold ({current.threshold_pct:.2f}%) is already "
                f"near-optimal. Expected ${best.expected_daily_pnl():.2f}/day. "
                f"No change recommended."
            )

        direction = "lower" if best.threshold_pct < current.threshold_pct else "raise"
        return (
            f"Model suggests {direction}ing threshold from "
            f"{current.threshold_pct:.2f}% to {best.threshold_pct:.2f}%. "
            f"Expected: {best.bets_per_day:.0f} bets/day at "
            f"{best.win_rate:.1%} WR = ${best.expected_daily_pnl():.2f}/day "
            f"(vs current ${current.expected_daily_pnl():.2f}/day). "
            f"CAUTION: Model is extrapolated — validate with 30+ bets at new "
            f"threshold before committing."
        )

    def to_dict(self) -> dict:
        """Export as JSON-serializable dict."""
        report = self.sweep()
        return {
            "calibration": [
                {
                    "threshold_pct": c.threshold_pct,
                    "bets_per_day": c.bets_per_day,
                    "win_rate": c.win_rate,
                    "daily_pnl": round(c.expected_daily_pnl(), 2),
                }
                for c in self.calibration
            ],
            "sweep": [
                {
                    "threshold_pct": p.threshold_pct,
                    "bets_per_day": p.bets_per_day,
                    "win_rate": round(p.win_rate, 4),
                    "edge_per_bet": round(p.edge_per_bet(), 4),
                    "daily_pnl": round(p.expected_daily_pnl(), 2),
                }
                for p in report.points
            ],
            "optimal": {
                "threshold_pct": report.optimal_threshold,
                "daily_pnl": report.optimal_daily_pnl,
            },
            "recommendation": report.recommendation,
        }

    def summary_text(self) -> str:
        """Human-readable threshold analysis."""
        report = self.sweep()
        lines = [
            "=== SIGNAL THRESHOLD ANALYZER ===",
            f"Calibration: {len(self.calibration)} point(s)",
            f"  Current: {self.calibration[0].threshold_pct:.2f}% → "
            f"{self.calibration[0].bets_per_day:.0f} bets/day, "
            f"{self.calibration[0].win_rate:.1%} WR",
            "",
            "Threshold sweep:",
            f"{'Threshold':>10} {'Bets/day':>10} {'WR':>8} {'Edge':>8} {'Daily PnL':>12}",
            "-" * 52,
        ]

        for p in report.points:
            marker = " *" if p.threshold_pct == report.optimal_threshold else ""
            lines.append(
                f"{p.threshold_pct:>9.2f}% {p.bets_per_day:>10.1f} "
                f"{p.win_rate:>7.1%} ${p.edge_per_bet():>7.4f} "
                f"${p.expected_daily_pnl():>11.2f}{marker}"
            )

        lines.extend([
            "",
            f"Optimal: {report.optimal_threshold:.2f}% → ${report.optimal_daily_pnl:.2f}/day",
            "",
            f"Recommendation: {report.recommendation}",
        ])
        return "\n".join(lines)
