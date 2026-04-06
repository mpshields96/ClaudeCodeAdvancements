#!/usr/bin/env python3
"""
USAGE-3: Cost Threshold Alert Hook (PreToolUse)

Warns or blocks before expensive tool calls when the session's estimated
cost exceeds configurable thresholds. Reads cost data from:
  1. OTel receiver storage (if available — real-time, accurate)
  2. Transcript JSONL fallback (always available, slightly delayed)

Thresholds:
  - warn: inject additionalContext warning (default: $5.00)
  - block: deny the tool call (default: $20.00, opt-in via env var)

Cheap tools (Read, Glob, Grep, TodoWrite) are always silently allowed.

Hook event: PreToolUse
Configuration via environment variables:
  CLAUDE_COST_WARN_THRESHOLD   — USD threshold for warnings (default: 5.00)
  CLAUDE_COST_BLOCK_THRESHOLD  — USD threshold for blocking (default: 20.00)
  CLAUDE_COST_BLOCK_ENABLED    — set "1" to enable blocking (default: warn only)
  CLAUDE_COST_ALERT_DISABLED   — set "1" to disable entirely
  CLAUDE_OTEL_STORAGE_DIR      — OTel storage dir (default: ~/.claude-otel-metrics)

Usage (hooks config):
  PreToolUse: python3 /path/to/cost_alert.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_WARN_THRESHOLD = 5.00      # USD
DEFAULT_BLOCK_THRESHOLD = 20.00    # USD

# Tools that are cheap and should never trigger alerts
CHEAP_TOOLS = frozenset({
    "Read", "Glob", "Grep", "TodoWrite", "TodoRead",
    "AskFollowupQuestion", "AskUserQuestion",
})

# Tools that are expensive and warrant alerts
EXPENSIVE_TOOLS = frozenset({
    "Agent", "Bash", "Write", "Edit", "WebFetch", "WebSearch",
    "NotebookEdit",
})


def get_warn_threshold() -> float:
    """Get the warning threshold from env or default."""
    try:
        return float(os.environ.get("CLAUDE_COST_WARN_THRESHOLD", str(DEFAULT_WARN_THRESHOLD)))
    except (ValueError, TypeError):
        return DEFAULT_WARN_THRESHOLD


def get_block_threshold() -> float:
    """Get the blocking threshold from env or default."""
    try:
        return float(os.environ.get("CLAUDE_COST_BLOCK_THRESHOLD", str(DEFAULT_BLOCK_THRESHOLD)))
    except (ValueError, TypeError):
        return DEFAULT_BLOCK_THRESHOLD


def is_block_enabled() -> bool:
    """Check if blocking mode is enabled."""
    return os.environ.get("CLAUDE_COST_BLOCK_ENABLED", "") == "1"


def is_disabled() -> bool:
    """Check if cost alerts are entirely disabled."""
    return os.environ.get("CLAUDE_COST_ALERT_DISABLED", "") == "1"


def should_check(tool_name: str) -> bool:
    """
    Determine if this tool call should be checked for cost alerts.

    Cheap tools are always allowed. Only expensive or unknown tools trigger checks.
    """
    if tool_name in CHEAP_TOOLS:
        return False
    return True


# ---------------------------------------------------------------------------
# Cost estimation — OTel source
# ---------------------------------------------------------------------------

def get_session_cost_from_otel(session_id: str | None = None) -> float | None:
    """
    Read session cost from OTel receiver's stored metrics.

    Returns estimated cost in USD, or None if OTel data is unavailable.
    """
    storage_dir = Path(os.environ.get(
        "CLAUDE_OTEL_STORAGE_DIR",
        str(Path.home() / ".claude-otel-metrics")
    ))

    if not storage_dir.exists():
        return None

    now = datetime.now(tz=timezone.utc)
    today_file = storage_dir / f"{now.strftime('%Y-%m-%d')}.jsonl"

    if not today_file.exists():
        return None

    total_cost = 0.0
    found_any = False

    try:
        with open(today_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("metric") != "claude_code.cost.usage":
                    continue

                # Filter by session if specified
                if session_id:
                    resource = record.get("resource", {})
                    rec_session = resource.get("session.id", "")
                    if rec_session and rec_session != session_id:
                        continue

                value = record.get("value", 0)
                if isinstance(value, (int, float)):
                    total_cost += value
                    found_any = True

    except OSError:
        return None

    return total_cost if found_any else None


# ---------------------------------------------------------------------------
# Cost estimation — Transcript fallback
# ---------------------------------------------------------------------------

def get_session_cost_from_transcript(
    session_id: str,
    transcript_path: str | None = None,
) -> float | None:
    """
    Estimate session cost from transcript JSONL file.

    Uses the same logic as usage_counter.py's extract_session_usage.
    Returns estimated cost in USD, or None if transcript unavailable.
    """
    if transcript_path:
        path = Path(transcript_path)
    else:
        return None

    if not path.exists():
        return None

    # Cost rates (per 1M tokens) — Opus default since that's what CCA uses
    RATES = {
        "opus": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75},
        "sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_create": 3.75},
        "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.025, "cache_create": 0.3125},
    }

    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    cache_create = 0
    detected_model = "sonnet"

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Detect model
                model_str = entry.get("model", "")
                if not model_str and isinstance(entry.get("message"), dict):
                    model_str = entry["message"].get("model", "")
                if model_str:
                    ml = model_str.lower()
                    if "opus" in ml:
                        detected_model = "opus"
                    elif "haiku" in ml:
                        detected_model = "haiku"
                    elif "sonnet" in ml:
                        detected_model = "sonnet"

                # Extract usage
                usage = None
                if entry.get("type") == "assistant":
                    msg = entry.get("message", {})
                    if isinstance(msg, dict):
                        usage = msg.get("usage")
                if usage is None:
                    usage = entry.get("usage")
                if not isinstance(usage, dict):
                    continue

                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                cache_read += usage.get("cache_read_input_tokens", 0)
                cache_create += usage.get("cache_creation_input_tokens", 0)

    except OSError:
        return None

    if input_tokens == 0 and output_tokens == 0:
        return None

    rates = RATES.get(detected_model, RATES["sonnet"])
    cost = (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
        + (cache_read / 1_000_000) * rates["cache_read"]
        + (cache_create / 1_000_000) * rates["cache_create"]
    )

    return round(cost, 4)


def get_session_cost(hook_input: dict) -> float | None:
    """
    Get session cost from best available source.

    Tries OTel first (real-time), falls back to transcript (delayed).
    """
    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path")

    # Try OTel first
    cost = get_session_cost_from_otel(session_id)
    if cost is not None:
        return cost

    # Fall back to transcript
    return get_session_cost_from_transcript(session_id, transcript_path)


# ---------------------------------------------------------------------------
# Hook output
# ---------------------------------------------------------------------------

def build_warn_output(tool_name: str, cost: float, threshold: float) -> dict:
    """Build a PreToolUse warning output (non-blocking)."""
    return {
        "hookSpecificOutput": {
            "additionalContext": (
                f"[Cost Alert] Session cost is ${cost:.2f} "
                f"(threshold: ${threshold:.2f}). "
                f"Consider whether this {tool_name} call is necessary. "
                f"You can save context by using cheaper tools (Read/Glob/Grep) "
                f"or wrapping up the session."
            ),
        }
    }


def build_block_output(tool_name: str, cost: float, threshold: float) -> dict:
    """Build a PreToolUse blocking output."""
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Session cost ${cost:.2f} exceeds block threshold "
                f"${threshold:.2f}. Tool {tool_name} denied. "
                f"Run /cca-wrap to end session, or set "
                f"CLAUDE_COST_BLOCK_ENABLED=0 to disable blocking."
            ),
        }
    }


def build_allow_output() -> dict:
    """Build a silent allow output."""
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Hook entry point."""
    if is_disabled():
        print("{}")
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("{}")
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")

    if not should_check(tool_name):
        print("{}")
        sys.exit(0)

    cost = get_session_cost(hook_input)

    if cost is None:
        # No cost data available — allow silently
        print("{}")
        sys.exit(0)

    block_threshold = get_block_threshold()
    warn_threshold = get_warn_threshold()

    # Check block threshold first
    if is_block_enabled() and cost >= block_threshold:
        output = build_block_output(tool_name, cost, block_threshold)
        print(json.dumps(output))
        sys.exit(0)

    # Check warn threshold
    if cost >= warn_threshold:
        output = build_warn_output(tool_name, cost, warn_threshold)
        print(json.dumps(output))
        sys.exit(0)

    # Under threshold — allow silently
    print("{}")
    sys.exit(0)


if __name__ == "__main__":
    main()
