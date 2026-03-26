#!/usr/bin/env python3
"""overhead_tracker.py — Measure CCA's token overhead at session startup.

Runs `claude -p --output-format json --no-session-persistence 'hello'`
and extracts the hidden token count from the API response. This measures
how many tokens CCA's hooks, CLAUDE.md, skills, MCP, and memory files
consume before the user types a single word.

Based on u/wirelesshealth's methodology (r/ClaudeCode, S185 finding):
- Empty dir baseline: ~16K tokens
- Real project baseline: ~23K tokens
- CCA measured: ~49K tokens (2x baseline — heavy hooks + CLAUDE.md)

Usage:
    python3 overhead_tracker.py              # Measure and display
    python3 overhead_tracker.py --json       # JSON output
    python3 overhead_tracker.py --history    # Show historical measurements
    python3 overhead_tracker.py --compare    # Compare to baselines
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "overhead_history.jsonl"

# Baselines from u/wirelesshealth (v2.1.84, March 2026)
BASELINE_EMPTY = 16_063
BASELINE_REAL_PROJECT = 23_000


def measure_overhead(project_dir: str = None) -> dict:
    """Measure token overhead by running a minimal claude session.

    Returns dict with token counts and metadata.
    """
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--no-session-persistence",
        "hello",
    ]

    env = dict(os.environ)
    cwd = project_dir or os.getcwd()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=cwd, env=env,
        )
    except FileNotFoundError:
        return {"error": "claude CLI not found"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout (120s)"}

    if result.returncode != 0:
        return {"error": f"exit code {result.returncode}", "stderr": result.stderr[:500]}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "invalid JSON response"}

    # Extract token counts
    usage = data.get("usage", {})
    model_usage = data.get("modelUsage", {})

    cache_creation = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    total_overhead = cache_creation + cache_read + input_tokens

    # Get model info
    model = "unknown"
    if model_usage:
        model = list(model_usage.keys())[0] if model_usage else "unknown"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project_dir": cwd,
        "total_overhead": total_overhead,
        "cache_creation": cache_creation,
        "cache_read": cache_read,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model,
        "vs_empty_baseline": total_overhead - BASELINE_EMPTY,
        "vs_project_baseline": total_overhead - BASELINE_REAL_PROJECT,
        "ratio_to_empty": round(total_overhead / BASELINE_EMPTY, 2) if BASELINE_EMPTY else 0,
    }


def save_measurement(measurement: dict):
    """Append measurement to history JSONL."""
    if "error" in measurement:
        return
    try:
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(measurement) + "\n")
    except OSError:
        pass


def load_history() -> list[dict]:
    """Load measurement history."""
    if not HISTORY_FILE.exists():
        return []
    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def format_tokens(n: int) -> str:
    """Format token count with K suffix."""
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def display_measurement(m: dict):
    """Pretty-print a measurement."""
    if "error" in m:
        print(f"ERROR: {m['error']}")
        return

    print(f"CCA Token Overhead Measurement")
    print(f"  Total overhead: {format_tokens(m['total_overhead'])} tokens")
    print(f"    Cache creation: {format_tokens(m['cache_creation'])}")
    print(f"    Cache read: {format_tokens(m['cache_read'])}")
    print(f"    Input tokens: {m['input_tokens']}")
    print(f"  Model: {m['model']}")
    print(f"  vs empty dir baseline ({format_tokens(BASELINE_EMPTY)}): +{format_tokens(m['vs_empty_baseline'])}")
    print(f"  vs real project baseline ({format_tokens(BASELINE_REAL_PROJECT)}): +{format_tokens(m['vs_project_baseline'])}")
    print(f"  Ratio to empty: {m['ratio_to_empty']}x")


def display_history():
    """Show measurement history with trend."""
    history = load_history()
    if not history:
        print("No measurements recorded yet. Run: python3 overhead_tracker.py")
        return

    print(f"CCA Overhead History ({len(history)} measurements)")
    print(f"{'Date':>12} {'Overhead':>10} {'vs Baseline':>12} {'Model':>20}")
    print("-" * 58)
    for m in history[-10:]:  # Last 10
        ts = m.get("timestamp", "?")[:10]
        overhead = format_tokens(m.get("total_overhead", 0))
        delta = f"+{format_tokens(m.get('vs_project_baseline', 0))}"
        model = m.get("model", "?")[:20]
        print(f"{ts:>12} {overhead:>10} {delta:>12} {model:>20}")

    # Trend
    if len(history) >= 2:
        first = history[0].get("total_overhead", 0)
        last = history[-1].get("total_overhead", 0)
        delta = last - first
        direction = "UP" if delta > 0 else "DOWN" if delta < 0 else "FLAT"
        print(f"\nTrend: {direction} ({format_tokens(abs(delta))} over {len(history)} measurements)")


def cli_main(args: list[str] = None) -> int:
    """CLI entry point."""
    args = args or sys.argv[1:]

    if "--history" in args:
        display_history()
        return 0

    if "--compare" in args:
        m = measure_overhead()
        save_measurement(m)
        display_measurement(m)
        print(f"\nBaselines (u/wirelesshealth, v2.1.84):")
        print(f"  Empty dir: {format_tokens(BASELINE_EMPTY)}")
        print(f"  Real project: {format_tokens(BASELINE_REAL_PROJECT)}")
        print(f"  CCA: {format_tokens(m.get('total_overhead', 0))} ({m.get('ratio_to_empty', 0)}x empty)")
        return 0

    if "--json" in args:
        m = measure_overhead()
        save_measurement(m)
        print(json.dumps(m, indent=2))
        return 0

    # Default: measure and display
    m = measure_overhead()
    save_measurement(m)
    display_measurement(m)
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
