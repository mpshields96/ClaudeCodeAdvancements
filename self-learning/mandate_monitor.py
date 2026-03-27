"""Cross-session mandate progress monitor.

Persists daily trading results to a JSONL file and provides trajectory
analysis across sessions. Unlike mandate_tracker.py (single-session analysis),
this module accumulates data over the full mandate period and detects
multi-day trends.

Usage:
    from mandate_monitor import MandateMonitor

    monitor = MandateMonitor()  # uses default state file
    monitor.record_day(day=1, date="2026-03-27", pnl=20.5, bets=64, wins=60, losses=4)
    print(monitor.trajectory_text())
    print(monitor.health_check())
"""
import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional


DEFAULT_STATE_FILE = os.path.join(
    os.path.dirname(__file__), "mandate_state.jsonl"
)

# Mandate parameters (from S197/S198 analysis)
MANDATE_DAYS = 5
DAILY_TARGET_LOW = 15.0
DAILY_TARGET_HIGH = 25.0
MANDATE_START = "2026-03-27"


@dataclass
class DayRecord:
    """One day's mandate performance, persisted to JSONL."""

    day: int
    date_str: str
    pnl: float
    bets: int
    wins: int
    losses: int
    recorded_at: str = ""

    def __post_init__(self):
        if not self.recorded_at:
            self.recorded_at = datetime.now(tz=None).astimezone().isoformat()

    def win_rate(self) -> float:
        if self.bets == 0:
            return 0.0
        return self.wins / self.bets

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DayRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TrajectoryAnalysis:
    """Multi-day trend analysis."""

    days_recorded: int
    days_remaining: int
    total_pnl: float
    daily_avg_pnl: float
    total_bets: int
    overall_wr: float
    pace_verdict: str  # ON_TRACK, BEHIND, AHEAD, CRITICAL
    projected_total: float
    needed_daily_rate: float
    trend: str  # IMPROVING, STABLE, DECLINING, INSUFFICIENT_DATA
    consecutive_red_days: int
    best_day_pnl: float
    worst_day_pnl: float

    def to_dict(self) -> dict:
        return asdict(self)


class MandateMonitor:
    """Persistent cross-session mandate monitor."""

    def __init__(self, state_file: str = DEFAULT_STATE_FILE,
                 mandate_days: int = MANDATE_DAYS,
                 daily_target_low: float = DAILY_TARGET_LOW,
                 daily_target_high: float = DAILY_TARGET_HIGH):
        self.state_file = state_file
        self.mandate_days = mandate_days
        self.daily_target_low = daily_target_low
        self.daily_target_high = daily_target_high
        self._records: List[DayRecord] = []
        self._load()

    def _load(self):
        """Load existing records from JSONL state file."""
        self._records = []
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._records.append(DayRecord.from_dict(json.loads(line)))
                        except (json.JSONDecodeError, TypeError):
                            continue

    def _save_record(self, record: DayRecord):
        """Append a single record to the JSONL file."""
        with open(self.state_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def record_day(self, day: int, date_str: str, pnl: float,
                   bets: int, wins: int, losses: int) -> DayRecord:
        """Record a day's results. Overwrites if day already exists."""
        # Remove existing record for this day (allows corrections)
        self._records = [r for r in self._records if r.day != day]
        record = DayRecord(
            day=day, date_str=date_str, pnl=pnl,
            bets=bets, wins=wins, losses=losses
        )
        self._records.append(record)
        self._records.sort(key=lambda r: r.day)
        # Rewrite entire file (small file, correctness > performance)
        self._rewrite()
        return record

    def _rewrite(self):
        """Rewrite the entire state file from current records."""
        with open(self.state_file, "w") as f:
            for r in self._records:
                f.write(json.dumps(r.to_dict()) + "\n")

    @property
    def records(self) -> List[DayRecord]:
        return list(self._records)

    def days_recorded(self) -> int:
        return len(self._records)

    def total_pnl(self) -> float:
        return sum(r.pnl for r in self._records)

    def analyze(self) -> TrajectoryAnalysis:
        """Compute multi-day trajectory analysis."""
        n = len(self._records)
        if n == 0:
            return TrajectoryAnalysis(
                days_recorded=0, days_remaining=self.mandate_days,
                total_pnl=0.0, daily_avg_pnl=0.0, total_bets=0,
                overall_wr=0.0, pace_verdict="NO_DATA",
                projected_total=0.0,
                needed_daily_rate=self.daily_target_low,
                trend="INSUFFICIENT_DATA",
                consecutive_red_days=0, best_day_pnl=0.0, worst_day_pnl=0.0
            )

        total_pnl = self.total_pnl()
        daily_avg = total_pnl / n
        total_bets = sum(r.bets for r in self._records)
        total_wins = sum(r.wins for r in self._records)
        overall_wr = total_wins / total_bets if total_bets > 0 else 0.0

        days_remaining = max(0, self.mandate_days - n)
        projected_total = daily_avg * self.mandate_days if n > 0 else 0.0

        # Needed daily rate for remaining days to hit low target
        total_target = self.daily_target_low * self.mandate_days
        remaining_needed = total_target - total_pnl
        needed_daily_rate = remaining_needed / days_remaining if days_remaining > 0 else 0.0

        # Pace verdict
        if daily_avg >= self.daily_target_high:
            pace_verdict = "AHEAD"
        elif daily_avg >= self.daily_target_low:
            pace_verdict = "ON_TRACK"
        elif daily_avg >= self.daily_target_low * 0.5:
            pace_verdict = "BEHIND"
        else:
            pace_verdict = "CRITICAL"

        # Trend (need 2+ days)
        if n < 2:
            trend = "INSUFFICIENT_DATA"
        else:
            sorted_records = sorted(self._records, key=lambda r: r.day)
            # Compare second half to first half
            mid = n // 2
            first_half_avg = sum(r.pnl for r in sorted_records[:mid]) / mid
            second_half_avg = sum(r.pnl for r in sorted_records[mid:]) / (n - mid)
            diff = second_half_avg - first_half_avg
            if diff > 2.0:
                trend = "IMPROVING"
            elif diff < -2.0:
                trend = "DECLINING"
            else:
                trend = "STABLE"

        # Consecutive red days (from most recent)
        consecutive_red = 0
        for r in reversed(sorted(self._records, key=lambda r: r.day)):
            if r.pnl < 0:
                consecutive_red += 1
            else:
                break

        pnls = [r.pnl for r in self._records]
        return TrajectoryAnalysis(
            days_recorded=n,
            days_remaining=days_remaining,
            total_pnl=total_pnl,
            daily_avg_pnl=daily_avg,
            total_bets=total_bets,
            overall_wr=overall_wr,
            pace_verdict=pace_verdict,
            projected_total=projected_total,
            needed_daily_rate=needed_daily_rate,
            trend=trend,
            consecutive_red_days=consecutive_red,
            best_day_pnl=max(pnls),
            worst_day_pnl=min(pnls),
        )

    def trajectory_text(self) -> str:
        """Human-readable trajectory summary."""
        a = self.analyze()
        if a.days_recorded == 0:
            return "MANDATE MONITOR: No data recorded yet."

        lines = [
            f"MANDATE MONITOR — Day {a.days_recorded}/{self.mandate_days}",
            f"  Total P&L: ${a.total_pnl:+.2f} | Daily avg: ${a.daily_avg_pnl:.2f}",
            f"  Bets: {a.total_bets} | WR: {a.overall_wr:.1%}",
            f"  Pace: {a.pace_verdict} | Trend: {a.trend}",
            f"  Projected total: ${a.projected_total:.2f}",
        ]
        if a.days_remaining > 0:
            lines.append(
                f"  Need ${a.needed_daily_rate:.2f}/day for remaining {a.days_remaining} days"
            )
        if a.consecutive_red_days > 0:
            lines.append(
                f"  WARNING: {a.consecutive_red_days} consecutive red day(s)"
            )
        lines.append(
            f"  Range: best ${a.best_day_pnl:+.2f} / worst ${a.worst_day_pnl:+.2f}"
        )
        return "\n".join(lines)

    def health_check(self) -> str:
        """Quick health status for cross-chat updates."""
        a = self.analyze()
        if a.days_recorded == 0:
            return "MANDATE: awaiting Day 1 data"
        return (
            f"MANDATE Day {a.days_recorded}/{self.mandate_days}: "
            f"${a.total_pnl:+.2f} total, ${a.daily_avg_pnl:.2f}/day avg, "
            f"{a.overall_wr:.1%} WR, {a.pace_verdict}"
        )

    def day_summary(self, day: int) -> Optional[str]:
        """Summary for a specific day."""
        matches = [r for r in self._records if r.day == day]
        if not matches:
            return None
        r = matches[0]
        return (
            f"Day {r.day} ({r.date_str}): ${r.pnl:+.2f} | "
            f"{r.bets} bets, {r.wins}W/{r.losses}L ({r.win_rate():.1%})"
        )

    def clear(self):
        """Clear all records (for testing or new mandate)."""
        self._records = []
        if os.path.exists(self.state_file):
            os.remove(self.state_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        monitor = MandateMonitor()
        print(monitor.trajectory_text())
    elif len(sys.argv) > 1 and sys.argv[1] == "health":
        monitor = MandateMonitor()
        print(monitor.health_check())
    else:
        print("Usage: python3 mandate_monitor.py [status|health]")
        print("  status — full trajectory analysis")
        print("  health — one-line health check")
