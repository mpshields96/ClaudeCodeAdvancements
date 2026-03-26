#!/usr/bin/env python3
"""Token Budget System (MT-38) — Peak/off-peak aware token budgeting.

Returns the current budget window and behavioral guidelines based on time of day.
Used by /cca-init, /polybot-init, and any session startup to display budget level.

Usage:
    python3 token_budget.py              # Show current budget
    python3 token_budget.py --json       # JSON output for programmatic use
    python3 token_budget.py --brief      # One-line for briefings
"""

import json
import sys
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # Python < 3.9 fallback

ET_ZONE = ZoneInfo("America/New_York") if ZoneInfo else None

# Budget windows (US Eastern Time)
WINDOWS = {
    "PEAK": {
        "hours": "8 AM - 2 PM ET weekdays",
        "budget_pct": 60,
        "label": "PEAK (60%)",
        "color": "red",
        "rules": [
            "No agent spawns (gsd:plan-phase, parallel workers)",
            "Use gsd:quick exclusively",
            "Concise responses — shorter than usual",
            "Batch reads, skip optional exploration",
            "Pace across full 5-hour window — both CCA + Kalshi chats share limits",
        ],
    },
    "SHOULDER": {
        "hours": "6-8 AM / 2-6 PM ET weekdays",
        "budget_pct": 80,
        "label": "SHOULDER (80%)",
        "color": "yellow",
        "rules": [
            "Single agent spawns OK if needed",
            "Normal response length",
            "Avoid parallel agent spawns",
        ],
    },
    "OFF-PEAK": {
        "hours": "6 PM - 6 AM ET / all weekend",
        "budget_pct": 100,
        "label": "OFF-PEAK (100%)",
        "color": "green",
        "rules": [
            "Full autonomy — agents, parallel work, research",
            "Front-load expensive operations here",
        ],
    },
}


def get_budget(now=None):
    """Return the current budget window info.

    Args:
        now: datetime override for testing. Defaults to current local time.

    Returns:
        dict with keys: window, budget_pct, label, hours, rules, color,
        is_weekend, hour, weekday
    """
    if now is None:
        # Convert to ET regardless of machine timezone
        if ET_ZONE:
            now = datetime.now(ET_ZONE)
        else:
            now = datetime.now()

    hour = now.hour
    weekday = now.weekday()  # 0=Mon, 6=Sun
    is_weekend = weekday >= 5

    if is_weekend:
        window = "OFF-PEAK"
    elif 8 <= hour < 14:
        window = "PEAK"
    elif (6 <= hour < 8) or (14 <= hour < 18):
        window = "SHOULDER"
    else:
        window = "OFF-PEAK"

    info = WINDOWS[window].copy()
    info["window"] = window
    info["is_weekend"] = is_weekend
    info["hour"] = hour
    info["weekday"] = weekday
    info["weekday_name"] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][weekday]
    info["timestamp"] = now.isoformat()
    return info


def format_brief(info):
    """One-line briefing string."""
    return f"Token budget: {info['label']} ({info['weekday_name']} {info['hour']:02d}:xx ET)"


def format_full(info):
    """Multi-line display."""
    lines = [
        f"TOKEN BUDGET: {info['label']}",
        f"Time: {info['weekday_name']} {info['hour']:02d}:xx ({'weekend' if info['is_weekend'] else 'weekday'})",
        f"Window: {info['hours']}",
        "",
        "Guidelines:",
    ]
    for rule in info["rules"]:
        lines.append(f"  - {rule}")
    return "\n".join(lines)


# Autoloop scheduling constants (MT-38 Phase 4)
AUTOLOOP_COOLDOWNS = {
    "PEAK": 300,       # 5 min — conserve rate limits
    "SHOULDER": 60,    # 1 min — moderate pace
    "OFF-PEAK": 15,    # 15 sec — full speed
}

AUTOLOOP_MODEL_PREF = {
    "PEAK": "sonnet",      # Lighter model during peak
    "SHOULDER": "opus",    # Full model OK at shoulder
    "OFF-PEAK": "opus",    # Full power
}

AUTOLOOP_REASONS = {
    "PEAK": "Peak hours (8AM-2PM ET) — extended cooldown, lighter model to conserve rate limits",
    "SHOULDER": "Shoulder hours (6-8AM/2-6PM ET) — moderate cooldown",
    "OFF-PEAK": "Off-peak hours — full speed, no restrictions",
}


def get_autoloop_settings(now=None):
    """Return autoloop scheduling settings based on current budget window.

    Args:
        now: datetime override for testing.

    Returns:
        dict with: cooldown (seconds), model_preference, defer (bool),
        window, budget_pct, reason
    """
    budget = get_budget(now)
    window = budget["window"]

    return {
        "cooldown": AUTOLOOP_COOLDOWNS[window],
        "model_preference": AUTOLOOP_MODEL_PREF[window],
        "defer": False,  # Never fully stop — just slow down
        "window": window,
        "budget_pct": budget["budget_pct"],
        "reason": AUTOLOOP_REASONS[window],
    }


def main():
    info = get_budget()

    if "--json" in sys.argv:
        print(json.dumps(info, indent=2))
    elif "--brief" in sys.argv:
        print(format_brief(info))
    else:
        print(format_full(info))


if __name__ == "__main__":
    main()
