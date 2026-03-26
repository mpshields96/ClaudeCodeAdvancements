#!/usr/bin/env python3
"""Sniper bet volume predictor from crypto volatility signals.

Predicts expected daily sniper bet count based on BTC intraday range,
day-of-week, and macro event proximity. Used by Kalshi chat to set
expectations and adjust position sizing.

One file = one job. Stdlib-first.

Usage:
    python3 volume_predictor.py predict --btc-range 1500
    python3 volume_predictor.py predict --btc-range 2400 --weekday 6
    python3 volume_predictor.py calibrate <csv_path>
    python3 volume_predictor.py backtest <csv_path>
"""

import csv
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Constants — calibrated from S143 data (14 data points, March 2026)
# ---------------------------------------------------------------------------

# BTC 24h range thresholds (USD) — rough boundaries from observed data
RANGE_LOW = 1000      # Below this: quiet day
RANGE_MEDIUM = 1800   # Above this: active day
RANGE_HIGH = 2500     # Above this: very active day

# Volume bands (bets/day)
VOLUME_LOW = (15, 40)
VOLUME_MEDIUM = (40, 80)
VOLUME_HIGH = (80, 140)

# Weekend multiplier — crypto vol profile differs on weekends
WEEKEND_MULTIPLIER = 0.7  # Weekends tend to have less volume

# Macro event multiplier — FOMC/CPI/NFP days spike crypto vol
MACRO_MULTIPLIER = 1.3

# Default calibration data path
DEFAULT_CAL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "volume_calibration.json"
)


@dataclass
class VolumeEstimate:
    """Predicted sniper bet volume for a day."""
    band: str           # LOW / MEDIUM / HIGH
    min_bets: int
    max_bets: int
    midpoint: int
    confidence: str     # LOW / MEDIUM / HIGH (based on calibration data)
    btc_range_usd: float
    is_weekend: bool
    is_macro_day: bool
    multiplier: float   # Combined multiplier applied

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalibrationPoint:
    """One day's observed volume vs BTC range."""
    date: str
    btc_range_usd: float
    bet_count: int
    weekday: int  # 0=Mon, 6=Sun
    is_macro_day: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def predict_volume(
    btc_range_usd: float,
    weekday: Optional[int] = None,
    is_macro_day: bool = False,
) -> VolumeEstimate:
    """Predict sniper bet volume from BTC 24h range.

    Args:
        btc_range_usd: BTC 24h high-low range in USD
        weekday: Day of week (0=Mon, 6=Sun). None = use current day.
        is_macro_day: Whether FOMC/CPI/NFP is scheduled today.

    Returns:
        VolumeEstimate with band, range, and confidence.
    """
    if weekday is None:
        weekday = datetime.now(timezone.utc).weekday()

    is_weekend = weekday >= 5

    # Base volume band from BTC range
    if btc_range_usd >= RANGE_HIGH:
        band = "HIGH"
        base_min, base_max = VOLUME_HIGH
    elif btc_range_usd >= RANGE_MEDIUM:
        band = "MEDIUM"
        base_min, base_max = VOLUME_MEDIUM
    else:
        band = "LOW"
        base_min, base_max = VOLUME_LOW

    # Apply multipliers
    multiplier = 1.0
    if is_weekend:
        multiplier *= WEEKEND_MULTIPLIER
    if is_macro_day:
        multiplier *= MACRO_MULTIPLIER

    adj_min = max(1, int(base_min * multiplier))
    adj_max = max(adj_min + 1, int(base_max * multiplier))
    midpoint = (adj_min + adj_max) // 2

    # Confidence based on how much calibration data we have
    # With only 14 data points, confidence is universally LOW
    confidence = "LOW"

    return VolumeEstimate(
        band=band,
        min_bets=adj_min,
        max_bets=adj_max,
        midpoint=midpoint,
        confidence=confidence,
        btc_range_usd=btc_range_usd,
        is_weekend=is_weekend,
        is_macro_day=is_macro_day,
        multiplier=round(multiplier, 2),
    )


def calibrate_from_data(data_points: list) -> dict:
    """Calibrate prediction parameters from historical data.

    Args:
        data_points: List of CalibrationPoint instances.

    Returns:
        Dict with calibrated thresholds and multipliers.
    """
    if len(data_points) < 5:
        return {"error": "Need at least 5 data points for calibration", "n": len(data_points)}

    # Sort by BTC range
    sorted_pts = sorted(data_points, key=lambda p: p.btc_range_usd)

    # Find volume breakpoints using simple tercile split
    n = len(sorted_pts)
    t1 = n // 3
    t2 = 2 * n // 3

    low_range = [p.btc_range_usd for p in sorted_pts[:t1]]
    mid_range = [p.btc_range_usd for p in sorted_pts[t1:t2]]
    high_range = [p.btc_range_usd for p in sorted_pts[t2:]]

    low_vol = [p.bet_count for p in sorted_pts[:t1]]
    mid_vol = [p.bet_count for p in sorted_pts[t1:t2]]
    high_vol = [p.bet_count for p in sorted_pts[t2:]]

    def _avg(lst):
        return sum(lst) / len(lst) if lst else 0

    def _corr(xs, ys):
        """Pearson correlation between two lists."""
        if len(xs) < 3:
            return 0.0
        n = len(xs)
        mx, my = _avg(xs), _avg(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        dy = math.sqrt(sum((y - my) ** 2 for y in ys))
        if dx == 0 or dy == 0:
            return 0.0
        return num / (dx * dy)

    all_ranges = [p.btc_range_usd for p in data_points]
    all_vols = [p.bet_count for p in data_points]

    # Weekend effect
    weekend_pts = [p for p in data_points if p.weekday >= 5]
    weekday_pts = [p for p in data_points if p.weekday < 5]
    weekend_avg = _avg([p.bet_count for p in weekend_pts]) if weekend_pts else 0
    weekday_avg = _avg([p.bet_count for p in weekday_pts]) if weekday_pts else 1

    return {
        "n": n,
        "range_low_threshold": max(low_range) if low_range else RANGE_LOW,
        "range_high_threshold": min(high_range) if high_range else RANGE_HIGH,
        "avg_volume_low": round(_avg(low_vol), 1),
        "avg_volume_mid": round(_avg(mid_vol), 1),
        "avg_volume_high": round(_avg(high_vol), 1),
        "correlation": round(_corr(all_ranges, all_vols), 3),
        "weekend_multiplier": round(weekend_avg / weekday_avg, 2) if weekday_avg > 0 else WEEKEND_MULTIPLIER,
        "weekend_n": len(weekend_pts),
        "weekday_n": len(weekday_pts),
    }


def load_calibration_csv(path: str) -> list:
    """Load calibration data from CSV.

    Expected columns: date, btc_range_usd, bet_count, weekday, is_macro_day
    """
    points = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(CalibrationPoint(
                date=row["date"],
                btc_range_usd=float(row["btc_range_usd"]),
                bet_count=int(row["bet_count"]),
                weekday=int(row["weekday"]),
                is_macro_day=row.get("is_macro_day", "").lower() in ("true", "1", "yes"),
            ))
    return points


def backtest(data_points: list) -> dict:
    """Backtest predictions against historical data.

    Returns accuracy metrics: how often the actual bet count fell within
    the predicted band range.
    """
    if not data_points:
        return {"error": "No data points", "n": 0}

    hits = 0
    band_hits = 0
    errors = []

    for pt in data_points:
        est = predict_volume(pt.btc_range_usd, weekday=pt.weekday, is_macro_day=pt.is_macro_day)
        within_range = est.min_bets <= pt.bet_count <= est.max_bets
        correct_band = (
            (est.band == "LOW" and pt.bet_count < 50) or
            (est.band == "MEDIUM" and 30 <= pt.bet_count <= 90) or
            (est.band == "HIGH" and pt.bet_count > 60)
        )
        if within_range:
            hits += 1
        if correct_band:
            band_hits += 1
        errors.append(abs(pt.bet_count - est.midpoint))

    n = len(data_points)
    return {
        "n": n,
        "range_accuracy": round(hits / n, 3),
        "band_accuracy": round(band_hits / n, 3),
        "mean_abs_error": round(sum(errors) / n, 1),
        "max_error": max(errors) if errors else 0,
    }


def main():
    """CLI interface."""
    if len(sys.argv) < 2:
        print("Usage: volume_predictor.py [predict|calibrate|backtest] ...")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "predict":
        btc_range = 1500.0  # default
        weekday = None
        is_macro = False
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--btc-range" and i + 1 < len(args):
                btc_range = float(args[i + 1])
                i += 2
            elif args[i] == "--weekday" and i + 1 < len(args):
                weekday = int(args[i + 1])
                i += 2
            elif args[i] == "--macro":
                is_macro = True
                i += 1
            else:
                i += 1

        est = predict_volume(btc_range, weekday=weekday, is_macro_day=is_macro)
        print(f"Volume: {est.band} ({est.min_bets}-{est.max_bets} bets, midpoint {est.midpoint})")
        print(f"BTC range: ${btc_range:.0f} | Weekend: {est.is_weekend} | Macro: {est.is_macro_day} | Mult: {est.multiplier}x")
        print(f"Confidence: {est.confidence}")

    elif cmd == "calibrate":
        if len(sys.argv) < 3:
            print("Usage: calibrate <csv_path>")
            sys.exit(1)
        points = load_calibration_csv(sys.argv[2])
        result = calibrate_from_data(points)
        print(json.dumps(result, indent=2))

    elif cmd == "backtest":
        if len(sys.argv) < 3:
            print("Usage: backtest <csv_path>")
            sys.exit(1)
        points = load_calibration_csv(sys.argv[2])
        result = backtest(points)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
