"""
CTX-7: PostCompact Hook — fires after context compaction completes.

Addresses the "context amnesia" problem: when Claude Code auto-compacts the
conversation, instructions from early in the session can be lost. This hook:

1. Resets the context health state file (zone -> green, tokens -> 0)
2. Writes a recovery digest with the compact summary + re-read instructions
3. Logs the compaction event to self-learning journal for pattern analysis
4. Increments compaction counter for session health tracking

PostCompact payload fields:
  session_id       - Current session ID
  transcript_path  - Path to session transcript JSONL
  cwd              - Current working directory
  trigger          - "auto" (system) or "manual" (user ran /compact)
  compact_summary  - AI-generated summary of compacted conversation

Environment variables (all optional):
  CLAUDE_CONTEXT_STATE_FILE       - State file (default: ~/.claude-context-health.json)
  CLAUDE_COMPACT_RECOVERY_PATH    - Recovery file (default: ./.claude-compact-recovery.md)
  CLAUDE_COMPACT_JOURNAL_PATH     - Journal file (default: ./self-learning/journal.jsonl)
  CLAUDE_POSTCOMPACT_DISABLED     - Set "1" to disable

Wire as PostCompact hook in .claude/settings.local.json:
  {
    "hooks": {
      "PostCompact": [
        {
          "matcher": "",
          "hooks": [
            {
              "type": "command",
              "command": "python3 /path/to/context-monitor/hooks/post_compact.py"
            }
          ]
        }
      ]
    }
  }
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"
DEFAULT_RECOVERY_PATH = Path(".claude-compact-recovery.md")
DEFAULT_JOURNAL_PATH = Path("self-learning/journal.jsonl")
MAX_SUMMARY_LEN = 1500


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------

def is_disabled() -> bool:
    """Check if hook is disabled via environment variable."""
    return os.environ.get("CLAUDE_POSTCOMPACT_DISABLED") == "1"


def resolve_paths() -> dict:
    """Resolve all config paths from environment or defaults."""
    state_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    recovery_str = os.environ.get("CLAUDE_COMPACT_RECOVERY_PATH", "")
    journal_str = os.environ.get("CLAUDE_COMPACT_JOURNAL_PATH", "")

    return {
        "state_file": Path(state_str) if state_str else DEFAULT_STATE_FILE,
        "recovery_file": Path(recovery_str) if recovery_str else DEFAULT_RECOVERY_PATH,
        "journal_file": Path(journal_str) if journal_str else DEFAULT_JOURNAL_PATH,
    }


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------

def parse_payload(raw: str) -> dict:
    """Parse PostCompact hook payload from stdin JSON."""
    try:
        if raw.strip():
            data = json.loads(raw)
        else:
            data = {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    return {
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
        "trigger": data.get("trigger", "unknown"),
        "compact_summary": data.get("compact_summary", ""),
    }


# ---------------------------------------------------------------------------
# State file update
# ---------------------------------------------------------------------------

def update_state_after_compact(state_path: Path, trigger: str, session_id: str) -> dict:
    """
    Reset context health state after compaction.

    After compaction, the context is fresh — zone resets to green, tokens to 0.
    Preserves window size and increments compaction counter.
    Returns the pre-compaction state for logging.
    """
    # Read existing state
    pre_state = {}
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                pre_state = json.load(f)
        except (json.JSONDecodeError, OSError):
            pre_state = {}

    # Build post-compaction state
    now = datetime.now(timezone.utc).isoformat()
    new_state = {
        "zone": "green",
        "pct": 0,
        "tokens": 0,
        "turns": 0,
        "window": pre_state.get("window", 200000),
        "session_id": session_id or pre_state.get("session_id", ""),
        "last_compaction_time": now,
        "last_compaction_auto": trigger == "auto",
        "compaction_count": pre_state.get("compaction_count", 0) + 1,
    }

    # Preserve adaptive thresholds if present
    if "thresholds" in pre_state:
        new_state["thresholds"] = pre_state["thresholds"]

    # Atomic write
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(new_state, f, indent=2)
        tmp.replace(state_path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass

    return pre_state


# ---------------------------------------------------------------------------
# Recovery digest
# ---------------------------------------------------------------------------

def build_recovery_digest(trigger: str, compact_summary: str, session_id: str) -> str:
    """
    Build a markdown recovery file for post-compaction context restoration.

    This file is written to disk so Claude can read it after compaction to
    quickly restore awareness of what was happening before compaction fired.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    trigger_label = "automatic (system)" if trigger == "auto" else "manual (/compact)"

    # Truncate long summaries
    summary = compact_summary.strip()
    if not summary:
        summary = "No summary available."
    elif len(summary) > MAX_SUMMARY_LEN:
        summary = summary[:MAX_SUMMARY_LEN] + "..."

    lines = [
        "<!-- COMPACT RECOVERY — auto-generated by CTX-7 PostCompact hook -->",
        "",
        "# Context Compaction Recovery",
        f"_Compaction: {trigger_label} at {now}_",
        f"_Session: `{session_id[:12]}...`_" if session_id else "_Session: unknown_",
        "",
        "## What Was Happening Before Compaction",
        "",
        summary,
        "",
        "## Recovery Steps",
        "",
        "1. Re-read `CLAUDE.md` for project rules and safety constraints",
        "2. Re-read `SESSION_STATE.md` for current task and progress",
        "3. Check for any `HANDOFF.md` files with task-specific context",
        "4. Run test suites before continuing work",
        "5. Resume the task described above",
        "",
        "## Important",
        "",
        "- Project rules in CLAUDE.md are authoritative — re-read them fully",
        "- Do NOT rely on pre-compaction memory for architectural decisions",
        "- Verify file state with `git status` before making changes",
    ]
    return "\n".join(lines) + "\n"


def write_recovery_file(path: Path, content: str) -> None:
    """Write recovery file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Self-learning journal
# ---------------------------------------------------------------------------

def build_compaction_event(
    trigger: str,
    session_id: str,
    compact_summary: str,
    pre_compaction_state: dict,
) -> dict:
    """Build a structured compaction event for the self-learning journal."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "type": "compaction",
        "timestamp": now,
        "session_id": session_id,
        "trigger": trigger,
        "pre_zone": pre_compaction_state.get("zone", "unknown"),
        "pre_pct": pre_compaction_state.get("pct", 0),
        "pre_turns": pre_compaction_state.get("turns", 0),
        "compact_summary_len": len(compact_summary),
        "compaction_count": pre_compaction_state.get("compaction_count", 0) + 1,
    }


def append_journal_event(journal_path: Path, event: dict) -> None:
    """Append a compaction event to the self-learning journal JSONL."""
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError:
        pass  # Non-critical — don't fail the hook over journal issues


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if is_disabled():
        sys.exit(0)

    # Parse payload from stdin
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    payload = parse_payload(raw)

    # Resolve paths
    paths = resolve_paths()

    # Step 1: Capture pre-compaction state, then reset
    pre_state = update_state_after_compact(
        paths["state_file"],
        payload["trigger"],
        payload["session_id"],
    )

    # Step 2: Write recovery digest
    digest = build_recovery_digest(
        trigger=payload["trigger"],
        compact_summary=payload["compact_summary"],
        session_id=payload["session_id"],
    )
    write_recovery_file(paths["recovery_file"], digest)

    # Step 3: Log to self-learning journal
    event = build_compaction_event(
        trigger=payload["trigger"],
        session_id=payload["session_id"],
        compact_summary=payload["compact_summary"],
        pre_compaction_state=pre_state,
    )
    append_journal_event(paths["journal_file"], event)

    sys.exit(0)


if __name__ == "__main__":
    main()
