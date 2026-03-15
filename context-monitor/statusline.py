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
import sys

# ANSI escape codes
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD_RED = "\033[1;31m"
DIM = "\033[2m"


def _zone(pct: float) -> tuple[str, str, str]:
    """Return (color_code, label, bar_color) for a context percentage."""
    if pct >= 85:
        return BOLD_RED, "CRIT", BOLD_RED
    if pct >= 70:
        return RED, "HIGH", RED
    if pct >= 50:
        return YELLOW, "warn", YELLOW
    return GREEN, "ok  ", GREEN


def _bar(pct: float, width: int = 10) -> str:
    """Return a fill bar string of fixed width, e.g. [======    ]"""
    filled = round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "[" + "=" * filled + " " * (width - filled) + "]"


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    ctx = data.get("context_window", {})
    pct = ctx.get("used_percentage", 0) or 0
    pct = min(float(pct), 100.0)

    cost_usd = data.get("cost", {}).get("total_cost_usd", 0) or 0
    model = data.get("model", {}).get("display_name", "")

    color, label, bar_color = _zone(pct)
    bar = _bar(pct)

    # Format: CTX [bar] 45% ok | $0.02 | Model
    ctx_part = f"CTX {bar_color}{bar}{RESET} {color}{pct:.0f}% {label}{RESET}"
    cost_part = f"{DIM}${cost_usd:.2f}{RESET}"
    model_part = f"{DIM}{model}{RESET}" if model else ""

    parts = [ctx_part, cost_part]
    if model_part:
        parts.append(model_part)

    print("  " + f" {DIM}|{RESET} ".join(parts))


if __name__ == "__main__":
    main()
