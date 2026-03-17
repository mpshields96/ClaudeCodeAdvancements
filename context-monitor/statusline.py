#!/usr/bin/env python3
"""
CTX-2: Context Health Status Line

Reads Claude Code session JSON from stdin, outputs a color-coded context
health line for the Claude Code status bar.

Claude Code sends this data to every statusline script:
  context_window.used_percentage    — pre-calculated % of context used
  context_window.context_window_size — max tokens (200k or 1M)
  cost.total_cost_usd               — session cost
  model.display_name                — model name
  session_id                        — session identifier

Configuration via statusLine in settings.json or settings.local.json:
  {
    "statusLine": {
      "type": "command",
      "command": "python3 /path/to/context-monitor/statusline.py"
    }
  }

Output (one line, ANSI-colored):
  CTX [=======    ] 45% ok  | $0.02 | Sonnet
  CTX [==========] 62% warn | $0.08 | Sonnet    (yellow)
  CTX [==========] 78% HIGH | $0.15 | Sonnet    (red)
  CTX [==========] 92% CRIT | $0.23 | Sonnet    (bold red)
"""
import json
import os
import sys

# ANSI escape codes
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD_RED = "\033[1;31m"
DIM = "\033[2m"

# Absolute token quality ceilings (must match meter.py QUALITY_CEILINGS)
_QUALITY_CEILINGS = {"yellow": 250_000, "red": 400_000, "critical": 600_000}
_DEFAULT_THRESHOLDS = {"yellow": 50, "red": 70, "critical": 85}


def _adaptive_thresholds(window: int) -> dict:
    """Compute zone thresholds that respect absolute quality ceilings.

    For 200k: standard (50/70/85). For 1M: tighter (25/40/60).
    """
    if window <= 0:
        return dict(_DEFAULT_THRESHOLDS)
    return {
        zone: min(_DEFAULT_THRESHOLDS[zone], int((_QUALITY_CEILINGS[zone] / window) * 100))
        for zone in ("yellow", "red", "critical")
    }


def _zone(pct: float, thresholds: dict | None = None) -> tuple[str, str, str]:
    """Return (color_code, label, bar_color) for a context percentage."""
    t = thresholds or _DEFAULT_THRESHOLDS
    if pct >= t["critical"]:
        return BOLD_RED, "CRIT", BOLD_RED
    if pct >= t["red"]:
        return RED, "HIGH", RED
    if pct >= t["yellow"]:
        return YELLOW, "warn", YELLOW
    return GREEN, "ok  ", GREEN


def _bar(pct: float, width: int = 10) -> str:
    """Return a fill bar string of fixed width, e.g. [======    ]"""
    filled = round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "[" + "=" * filled + " " * (width - filled) + "]"


def _format_window(window: int) -> str:
    """Format window size for display: 200k, 500k, 1M."""
    if window >= 1_000_000:
        return f"{window // 1_000_000}M"
    return f"{window // 1000}k"


def _get_autocompact_pct() -> int | None:
    """Read CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from environment."""
    raw = os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "")
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _autocompact_proximity(pct: float, autocompact_pct: int | None) -> float | None:
    """Percentage points remaining before auto-compact fires. None if not configured."""
    if autocompact_pct is None:
        return None
    return max(0.0, round(autocompact_pct - pct, 1))


def _format_autocompact_part(proximity: float | None) -> str:
    """Format autocompact proximity for status line display.

    Shows nothing when comfortable (>15 points away) or not configured.
    Shows "AC:Xpts" when approaching, "AC:NOW" when at/past threshold.
    """
    if proximity is None:
        return ""
    if proximity > 15:
        return ""
    if proximity <= 0:
        return f"{BOLD_RED}AC:NOW{RESET}"
    if proximity <= 5:
        return f"{RED}AC:{proximity:.0f}pts{RESET}"
    return f"{YELLOW}AC:{proximity:.0f}pts{RESET}"


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    ctx = data.get("context_window", {})
    pct = ctx.get("used_percentage", 0) or 0
    pct = min(float(pct), 100.0)
    window = ctx.get("context_window_size", 200_000) or 200_000

    cost_usd = data.get("cost", {}).get("total_cost_usd", 0) or 0
    model = data.get("model", {}).get("display_name", "")

    # Use adaptive thresholds based on actual window size
    thresholds = _adaptive_thresholds(window)
    color, label, bar_color = _zone(pct, thresholds)
    bar = _bar(pct)

    # Format: CTX [bar] 45% ok | $0.02 | Model | 1M
    ctx_part = f"CTX {bar_color}{bar}{RESET} {color}{pct:.0f}% {label}{RESET}"
    cost_part = f"{DIM}${cost_usd:.2f}{RESET}"
    model_part = f"{DIM}{model}{RESET}" if model else ""

    # Autocompact proximity
    ac_pct = _get_autocompact_pct()
    ac_proximity = _autocompact_proximity(pct, ac_pct)
    ac_part = _format_autocompact_part(ac_proximity)

    parts = [ctx_part, cost_part]
    if ac_part:
        parts.append(ac_part)
    if model_part:
        parts.append(model_part)
    # Show window size when it differs from the standard 200k
    if window != 200_000:
        parts.append(f"{DIM}{_format_window(window)}{RESET}")

    print("  " + f" {DIM}|{RESET} ".join(parts))


if __name__ == "__main__":
    main()
