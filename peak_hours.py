#!/usr/bin/env python3
"""
peak_hours.py — Rate limit awareness for multi-chat orchestration.

Reports whether current time is peak or off-peak for Anthropic's
2x usage limits promotion (active March 13-28, 2026).

Peak hours: 8AM-2PM ET on WEEKDAYS only (standard limits)
Off-peak: all other hours + weekends (2x double limits)

Usage:
    python3 peak_hours.py              # Human-readable status
    python3 peak_hours.py --json       # Machine-readable JSON
    python3 peak_hours.py --check      # Exit code: 0=off-peak, 1=peak

Designed for:
- launch_worker.sh / launch_kalshi.sh: skip launch during peak
- /cca-auto-desktop coordination round: adjust behavior
- Session pacer: factor into wrap timing

Stdlib only. No external dependencies.
"""

import json
import sys
from datetime import datetime, timezone, timedelta


# Anthropic 2x promotion dates
PROMO_START = datetime(2026, 3, 13, tzinfo=timezone.utc)
PROMO_END = datetime(2026, 3, 29, tzinfo=timezone.utc)  # End of March 28

# Peak hours in ET (Eastern Time, UTC-4 for EDT)
PEAK_START_HOUR = 8   # 8 AM ET
PEAK_END_HOUR = 14    # 2 PM ET (exclusive)
ET_OFFSET = timedelta(hours=-4)  # EDT


def get_status() -> dict:
    """Get current peak/off-peak status."""
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc + ET_OFFSET

    is_weekday = now_et.weekday() < 5  # Mon=0 to Fri=4
    is_peak_hour = PEAK_START_HOUR <= now_et.hour < PEAK_END_HOUR
    is_peak = is_weekday and is_peak_hour

    promo_active = PROMO_START <= now_utc < PROMO_END
    has_double_limits = promo_active and not is_peak

    # Recommendation for multi-chat
    if is_peak:
        recommendation = "CONSERVE: peak hours, standard limits. Avoid launching extra chats."
        max_chats = 2
    elif has_double_limits:
        recommendation = "FULL SPEED: off-peak with 2x limits. Safe to run 3 chats."
        max_chats = 3
    else:
        recommendation = "NORMAL: standard limits. 2-3 chats depending on workload."
        max_chats = 3

    return {
        "time_et": now_et.strftime("%H:%M %A"),
        "is_peak": is_peak,
        "is_weekday": is_weekday,
        "promo_active": promo_active,
        "has_double_limits": has_double_limits,
        "recommendation": recommendation,
        "max_recommended_chats": max_chats,
    }


def main():
    args = sys.argv[1:]

    status = get_status()

    if "--json" in args:
        print(json.dumps(status, indent=2))
    elif "--check" in args:
        # Exit code: 0 = off-peak (safe), 1 = peak (conserve)
        sys.exit(1 if status["is_peak"] else 0)
    else:
        peak_str = "PEAK (standard limits)" if status["is_peak"] else "OFF-PEAK"
        if status["has_double_limits"]:
            peak_str += " (2x limits active)"
        print(f"Time: {status['time_et']} ET — {peak_str}")
        print(f"Recommendation: {status['recommendation']}")
        print(f"Max recommended chats: {status['max_recommended_chats']}")


if __name__ == "__main__":
    main()
