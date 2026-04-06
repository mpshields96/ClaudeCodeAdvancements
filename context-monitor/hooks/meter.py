"""
CTX-1: Context Meter Hook — PostToolUse

Reads the session transcript JSONL after every tool call, estimates how full
the context window is, classifies into green/yellow/red/critical zones, and
writes the result to a local state file.

The state file is read by:
- CTX-2: status line integration (shows context% in Claude Code status bar)
- CTX-3: alert hook (warns before expensive calls)
- CTX-4: auto-handoff hook (triggers at critical threshold)

Usage (PostToolUse hook in .claude/settings.local.json):
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/context-monitor/hooks/meter.py"
          }
        ]
      }
    ]
  }
}

Environment variables (all optional):
  CLAUDE_CONTEXT_WINDOW              - Context window size in tokens (default: 200000)
  CLAUDE_CONTEXT_STATE_FILE          - State file path (default: ~/.claude-context-health.json)
  CLAUDE_CONTEXT_DISABLED            - Set to "1" to disable this hook
  CLAUDE_AUTOCOMPACT_PCT_OVERRIDE    - CC's autocompact threshold (read-only, state output includes proximity)
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WINDOW = 200_000  # 200K tokens — Opus 4.6 standard (1M burns limits too fast)
DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"

DEFAULT_THRESHOLDS = {
    "yellow": 50,
    "red": 70,
    "critical": 85,
}

# Absolute token ceilings where quality degrades regardless of window size.
# Community-validated across 411 Reddit posts (nuclear scan):
# - Quality starts declining at ~250k tokens
# - Significant degradation at ~400k tokens
# - Severe degradation at ~600k tokens
QUALITY_CEILINGS = {
    "yellow": 250_000,
    "red": 400_000,
    "critical": 600_000,
}


# ---------------------------------------------------------------------------
# Core logic (pure functions, easily testable)
# ---------------------------------------------------------------------------

def adaptive_thresholds(window: int, adaptive: bool = True) -> dict:
    """
    Compute zone thresholds that respect both percentage-based and absolute
    token quality ceilings.

    For small windows (<=200k), standard percentages (50/70/85%) apply because
    the absolute ceilings (250k/400k/600k) exceed the window size.

    For large windows (800k, 1M), the absolute ceilings dominate. At 1M:
      yellow = min(50%, 250k/1M = 25%) = 25%
      red    = min(70%, 400k/1M = 40%) = 40%
      critical = min(85%, 600k/1M = 60%) = 60%

    This ensures quality warnings fire BEFORE degradation starts, regardless
    of window size.
    """
    if not adaptive or window <= 0:
        return dict(DEFAULT_THRESHOLDS)

    result = {}
    for zone in ("yellow", "red", "critical"):
        pct_threshold = DEFAULT_THRESHOLDS[zone]
        abs_pct = int((QUALITY_CEILINGS[zone] / window) * 100)
        result[zone] = min(pct_threshold, abs_pct)

    return result


def estimate_tokens_from_transcript(transcript_path: Path) -> tuple[int, int]:
    """
    Read transcript JSONL and return (estimated_tokens, turn_count).

    Strategy:
    1. If any turn has usage data, use the maximum total prompt tokens seen
       (input_tokens + cache_read_input_tokens + cache_creation_input_tokens).
       This represents the full conversation context at that point.
       Claude Code transcripts (type=assistant) store usage inside 'message';
       test fixtures and legacy formats store usage at the top level.
    2. Fall back to character counting (1 token ≈ 4 chars for English) if
       no usage fields are present.

    The maximum total prompt tokens seen across all turns is the best proxy for
    current context usage because each assistant turn's input includes the
    full conversation history up to that point.
    """
    if not transcript_path.exists():
        return 0, 0

    max_input_tokens = 0
    has_usage = False
    total_chars = 0
    turn_count = 0

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                turn_count += 1

                # Try exact token counts from usage field.
                # Claude Code transcripts (type=assistant) nest usage inside 'message'.
                # Test fixtures and older formats put usage at the top level.
                usage = entry.get("usage", {})
                if not usage and entry.get("type") == "assistant":
                    usage = entry.get("message", {}).get("usage", {})
                if isinstance(usage, dict):
                    input_tok = usage.get("input_tokens", 0)
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    cache_create = usage.get("cache_creation_input_tokens", 0)
                    total_tok = input_tok + cache_read + cache_create
                    if total_tok > 0:
                        has_usage = True
                        max_input_tokens = max(max_input_tokens, total_tok)

                # Always accumulate char count as fallback.
                # For new Claude Code format, content lives inside 'message'.
                content = entry.get("content", "")
                if not content and "message" in entry:
                    content = entry["message"].get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            total_chars += len(block.get("text", ""))

    except OSError:
        return 0, 0

    if has_usage:
        return max_input_tokens, turn_count

    # Fallback: 1 token ≈ 4 characters
    return total_chars // 4, turn_count


def estimate_cache_ratio_from_transcript(transcript_path: Path) -> tuple[int, int, int]:
    """
    Read transcript JSONL and return (cache_read, cache_creation, turns_with_usage)
    from the LAST turn that has usage data.

    Returns (0, 0, 0) if no usage data or file missing.
    Used for cache bust detection: a low cache_read / (cache_read + cache_creation)
    ratio on a non-first turn suggests the prompt cache was invalidated.
    """
    if not transcript_path.exists():
        return 0, 0, 0

    last_cache_read = 0
    last_cache_create = 0
    turns_with_usage = 0

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                usage = entry.get("usage", {})
                if not usage and entry.get("type") == "assistant":
                    usage = entry.get("message", {}).get("usage", {})
                if isinstance(usage, dict):
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    cache_create = usage.get("cache_creation_input_tokens", 0)
                    if cache_read > 0 or cache_create > 0:
                        turns_with_usage += 1
                        last_cache_read = cache_read
                        last_cache_create = cache_create
    except OSError:
        return 0, 0, 0

    return last_cache_read, last_cache_create, turns_with_usage


def compute_cache_ratio(cache_read: int, cache_create: int) -> float | None:
    """
    Compute cache hit ratio: cache_read / (cache_read + cache_create).

    Returns None if no cache tokens seen (ratio is meaningless with no data).
    Returns 0.0–1.0 otherwise.
    """
    total = cache_read + cache_create
    if total == 0:
        return None
    return cache_read / total


def detect_cache_bust(
    cache_read: int,
    cache_create: int,
    turns_with_usage: int,
    threshold: float = 0.5,
) -> tuple[bool, float | None]:
    """
    Detect a likely cache bust.

    A cache bust is when the cache hit ratio drops below `threshold` on a turn
    that is NOT the first usage-bearing turn (first turn always has low cache_read
    because nothing has been cached yet).

    Returns (bust_detected: bool, ratio: float | None).
    """
    if turns_with_usage <= 1:
        # First turn always has low cache_read — not a bust
        return False, compute_cache_ratio(cache_read, cache_create)

    ratio = compute_cache_ratio(cache_read, cache_create)
    if ratio is None:
        return False, None

    return ratio < threshold, ratio


def get_autocompact_pct() -> int | None:
    """Read CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from environment.

    Returns the percentage as an int (e.g., 30 for 30%), or None if not set
    or invalid. This env var controls when Claude Code fires auto-compaction.
    """
    raw = os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "")
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def compute_autocompact_proximity(pct: float, autocompact_pct: int | None) -> float | None:
    """Compute how close current usage is to the autocompact threshold.

    Returns the percentage points remaining before compaction fires,
    or 0.0 if already past the threshold. Returns None if autocompact
    is not configured.
    """
    if autocompact_pct is None:
        return None
    remaining = autocompact_pct - pct
    return max(0.0, round(remaining, 1))


def compute_context_percentage(tokens: int, window: int) -> float:
    """
    Return context usage as a percentage (0–100), capped at 100.
    """
    if window <= 0:
        return 0.0
    raw = (tokens / window) * 100
    return round(min(raw, 100.0), 1)


def classify_health_zone(pct: float, thresholds: dict | None = None) -> str:
    """
    Map a context percentage to a named zone.

    Zones (configurable via thresholds dict):
      green    0–49%   — full effectiveness, no action needed
      yellow   50–69%  — suggest /compact before complex tasks
      red      70–84%  — alert before tool use, recommend handoff
      critical ≥85%    — auto-trigger handoff generation
    """
    t = thresholds or DEFAULT_THRESHOLDS
    if pct >= t.get("critical", 85):
        return "critical"
    if pct >= t.get("red", 70):
        return "red"
    if pct >= t.get("yellow", 50):
        return "yellow"
    return "green"


def derive_transcript_path(session_id: str, project_dir: str) -> Path:
    """
    Construct the transcript path from session_id and project directory.

    Claude Code stores transcripts at:
      ~/.claude/projects/<PROJECT_HASH>/<session_id>.jsonl

    PROJECT_HASH is the absolute project path with '/' replaced by '-'.
    Example: /Users/foo/Projects/Bar → -Users-foo-Projects-Bar
    """
    clean_dir = project_dir.rstrip("/")
    project_hash = clean_dir.replace("/", "-")
    return Path.home() / ".claude" / "projects" / project_hash / f"{session_id}.jsonl"


def parse_hook_input(payload: dict) -> tuple[str, str]:
    """Extract (session_id, tool_name) from the PostToolUse hook payload."""
    return payload.get("session_id", ""), payload.get("tool_name", "")


def write_state_file(
    path: Path,
    pct: float,
    zone: str,
    tokens: int,
    turns: int,
    session_id: str,
    window: int = DEFAULT_WINDOW,
    thresholds: dict | None = None,
    autocompact_pct: int | None = None,
    cache_bust_detected: bool = False,
    cache_ratio: float | None = None,
    preserve_keys: dict | None = None,
) -> None:
    """
    Write context health state to a JSON file.
    Creates parent directories if needed. Overwrites existing file atomically.

    State schema:
      pct                   - context usage percentage (0–100)
      zone                  - green | yellow | red | critical | unknown
      tokens                - estimated token count
      turns                 - number of conversation turns counted
      window                - configured context window size
      thresholds            - active zone thresholds {yellow, red, critical} (percentages)
      session_id            - Claude Code session identifier
      autocompact_pct       - CLAUDE_AUTOCOMPACT_PCT_OVERRIDE value (null if not set)
      autocompact_proximity - percentage points until compaction fires (null if not set)
      cache_bust_detected   - True if cache hit ratio dropped below threshold on non-first turn
      cache_ratio           - last turn's cache_read / (cache_read + cache_creation), or null
      updated_at            - ISO timestamp of this write
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "pct": pct,
        "zone": zone,
        "tokens": tokens,
        "turns": turns,
        "window": window,
        "thresholds": thresholds or DEFAULT_THRESHOLDS,
        "session_id": session_id,
        "autocompact_pct": autocompact_pct,
        "autocompact_proximity": compute_autocompact_proximity(pct, autocompact_pct),
        "cache_bust_detected": cache_bust_detected,
        "cache_ratio": cache_ratio,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Preserve caller-supplied keys (e.g. idle_since written by stop hook)
    if preserve_keys:
        for k, v in preserve_keys.items():
            state.setdefault(k, v)
    # Atomic write via temp file
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        tmp_path.replace(path)
    except OSError:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def run_meter(
    session_id: str,
    transcript_path: Path,
    state_path: Path,
    window: int = DEFAULT_WINDOW,
    thresholds: dict | None = None,
    autocompact_pct: int | None = None,
) -> dict:
    """
    Core meter logic: read transcript, compute health, write state.
    Returns the state dict (for testing/inspection).

    Uses adaptive thresholds by default: for large windows (>200k),
    zone boundaries tighten to reflect absolute quality ceilings.
    Pass explicit thresholds to override adaptive behavior.

    autocompact_pct: value of CLAUDE_AUTOCOMPACT_PCT_OVERRIDE (or None).
    When set, the state file includes proximity to compaction threshold.

    Also computes cache bust detection: if cache hit ratio drops below 0.5
    on a non-first turn, writes cache_bust_detected=True to state file.
    """
    tokens, turns = estimate_tokens_from_transcript(transcript_path)

    # Use adaptive thresholds unless explicitly overridden
    active_thresholds = thresholds or adaptive_thresholds(window)

    if turns == 0 and not transcript_path.exists():
        zone = "unknown"
        pct = 0.0
    else:
        pct = compute_context_percentage(tokens, window)
        zone = classify_health_zone(pct, active_thresholds)

    # Cache bust detection (Signal 1)
    cache_read, cache_create, turns_with_usage = estimate_cache_ratio_from_transcript(transcript_path)
    bust, ratio = detect_cache_bust(cache_read, cache_create, turns_with_usage)

    # Read previous state to detect transitions (emit warning only on new bust)
    prev_bust = False
    if state_path.exists():
        try:
            prev_state = json.loads(state_path.read_text())
            prev_bust = bool(prev_state.get("cache_bust_detected", False))
            # Preserve any keys written by other hooks (e.g. idle_since from stop hook)
            preserve = {k: v for k, v in prev_state.items()
                        if k not in ("pct", "zone", "tokens", "turns", "window",
                                     "thresholds", "session_id", "autocompact_pct",
                                     "autocompact_proximity", "cache_bust_detected",
                                     "cache_ratio", "updated_at")}
        except (json.JSONDecodeError, OSError):
            preserve = {}
    else:
        preserve = {}

    write_state_file(
        path=state_path,
        pct=pct,
        zone=zone,
        tokens=tokens,
        turns=turns,
        session_id=session_id,
        window=window,
        thresholds=active_thresholds,
        autocompact_pct=autocompact_pct,
        cache_bust_detected=bust,
        cache_ratio=ratio,
        preserve_keys=preserve,
    )

    newly_busted = bust and not prev_bust
    return {
        "pct": pct,
        "zone": zone,
        "tokens": tokens,
        "turns": turns,
        "cache_bust_detected": bust,
        "cache_ratio": ratio,
        "newly_busted": newly_busted,
    }


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    PostToolUse hook entry point. Reads JSON from stdin, runs meter, exits 0.
    Never blocks — always exits 0 so Claude Code continues normally.
    """
    if os.environ.get("CLAUDE_CONTEXT_DISABLED") == "1":
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    session_id, _ = parse_hook_input(payload)
    if not session_id:
        sys.exit(0)

    project_dir = os.getcwd()
    transcript_path = derive_transcript_path(session_id, project_dir)

    state_file_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    state_path = Path(state_file_str) if state_file_str else DEFAULT_STATE_FILE

    window = int(os.environ.get("CLAUDE_CONTEXT_WINDOW", str(DEFAULT_WINDOW)))
    autocompact = get_autocompact_pct()

    result = run_meter(
        session_id=session_id,
        transcript_path=transcript_path,
        state_path=state_path,
        window=window,
        autocompact_pct=autocompact,
    )

    # Emit cache bust warning once when newly detected (Signal 1)
    if result.get("newly_busted"):
        ratio = result.get("cache_ratio")
        ratio_pct = f"{ratio:.0%}" if ratio is not None else "unknown"
        msg = (
            f"Warning: cache hit ratio {ratio_pct} — something may be busting the cache "
            f"(--resume, CLAUDE.md change, MCP schema injection)."
        )
        print(json.dumps({"suppressOutput": False, "message": msg}))

    # PostToolUse hook — exit 0 (non-blocking)
    sys.exit(0)


if __name__ == "__main__":
    main()
