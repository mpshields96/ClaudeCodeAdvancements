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
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"
DEFAULT_RECOVERY_PATH = Path(".claude-compact-recovery.md")
DEFAULT_JOURNAL_PATH = Path("self-learning/journal.jsonl")
DEFAULT_SNAPSHOT_PATH = Path.home() / ".claude-compaction-snapshot.json"
MAX_SUMMARY_LEN = 1500
SNAPSHOT_MAX_AGE_SECONDS = 3600  # Ignore snapshots older than 1 hour


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
    snapshot_str = os.environ.get("CLAUDE_COMPACTION_SNAPSHOT_PATH", "")

    return {
        "state_file": Path(state_str) if state_str else DEFAULT_STATE_FILE,
        "recovery_file": Path(recovery_str) if recovery_str else DEFAULT_RECOVERY_PATH,
        "journal_file": Path(journal_str) if journal_str else DEFAULT_JOURNAL_PATH,
        "snapshot_file": Path(snapshot_str) if snapshot_str else DEFAULT_SNAPSHOT_PATH,
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
        "window": pre_state.get("window", 200_000),
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
# Snapshot consumption (reads PreCompact snapshot, deletes after use)
# ---------------------------------------------------------------------------

def read_snapshot(snapshot_path: Path) -> Optional[dict]:
    """
    Read and consume the PreCompact snapshot file.

    Returns the snapshot dict if valid and fresh, None otherwise.
    Deletes the file after reading to prevent stale reuse.
    """
    if not snapshot_path.exists():
        return None
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        _safe_delete(snapshot_path)
        return None

    # Staleness guard: ignore snapshots older than SNAPSHOT_MAX_AGE_SECONDS
    ts_str = data.get("timestamp", "")
    if ts_str:
        try:
            snap_time = datetime.fromisoformat(ts_str)
            now = datetime.now(timezone.utc)
            age = (now - snap_time).total_seconds()
            if age > SNAPSHOT_MAX_AGE_SECONDS:
                _safe_delete(snapshot_path)
                return None
        except (ValueError, TypeError):
            pass  # Can't parse timestamp — use snapshot anyway

    # Delete after reading (one-time use)
    _safe_delete(snapshot_path)

    # Basic version check
    if data.get("version", 0) != 1:
        return None

    return data


def _safe_delete(path: Path) -> None:
    """Delete a file, ignoring errors."""
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Recovery digest (enhanced with snapshot support)
# ---------------------------------------------------------------------------

def build_recovery_digest_from_snapshot(
    trigger: str,
    compact_summary: str,
    session_id: str,
    snapshot: dict,
) -> str:
    """
    Build a task-specific recovery digest using PreCompact snapshot data.

    This provides much richer context than the generic digest, letting Claude
    resume work immediately without spending turns re-reading files.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    trigger_label = "automatic (system)" if trigger == "auto" else "manual (/compact)"

    # Session info
    chat_role = snapshot.get("chat_role", "")
    session_header = snapshot.get("session_header", "")
    session_line = f"_Session: {session_header}_" if session_header else (
        f"_Session: `{session_id[:12]}...`_" if session_id else "_Session: unknown_"
    )
    if chat_role:
        session_line += f" _({chat_role})_"

    # Context health
    health = snapshot.get("context_health", {})
    health_lines = []
    if health:
        zone = health.get("zone", "unknown")
        pct = health.get("pct", 0)
        tokens = health.get("tokens", 0)
        turns = health.get("turns", 0)
        window = health.get("window", 200_000)
        window_str = f"{window // 1_000_000}M" if window >= 1_000_000 else f"{window // 1000}k"
        health_lines.append(
            f"- Context was at **{zone} zone** ({pct:.0f}%, ~{tokens:,} tokens, {turns} turns of {window_str})"
        )

    # Git status
    git_status = snapshot.get("git_status", [])
    git_diff = snapshot.get("git_diff_stat", "")

    # Tasks
    tasks = snapshot.get("todays_tasks_todos", [])

    # Compact summary
    summary = compact_summary.strip()
    if summary and len(summary) > MAX_SUMMARY_LEN:
        summary = summary[:MAX_SUMMARY_LEN] + "..."

    lines = [
        "<!-- COMPACT RECOVERY — auto-generated by CTX-7 PostCompact hook (snapshot-enhanced) -->",
        "",
        "# Context Compaction Recovery",
        f"_Compaction: {trigger_label} at {now}_",
        session_line,
        "",
    ]

    # Pre-compaction state
    if health_lines or git_status:
        lines.append("## Pre-Compaction State")
        lines.extend(health_lines)
        cwd = snapshot.get("cwd", "")
        if cwd:
            lines.append(f"- Working in: `{cwd}`")
        lines.append("")

    # Git status section
    if git_status:
        lines.append("## Files Modified (git status)")
        for gs_line in git_status[:20]:  # Cap display at 20 files
            lines.append(f"- `{gs_line}`")
        if git_diff:
            lines.append(f"- _{git_diff}_")
        lines.append("")

    # Current tasks
    if tasks:
        lines.append("## Current Tasks (from TODAYS_TASKS.md)")
        for task in tasks[:10]:  # Cap at 10 tasks
            lines.append(f"- {task}")
        lines.append("")

    # Compact summary
    if summary and summary != "No summary available.":
        lines.append("## What Was Happening Before Compaction")
        lines.append("")
        lines.append(summary)
        lines.append("")

    # Critical rules injection (v2) — embed rules when pre-compaction context was high
    critical_rules = snapshot.get("critical_rules", {})
    pre_pct = health.get("pct", 0) if health else 0
    rules_injected = False
    if critical_rules and pre_pct >= 30:
        rules_injected = True
        lines.append("## Critical Rules (Re-injected — Context Was High Before Compaction)")
        lines.append("")
        cardinal = critical_rules.get("cardinal_safety", "")
        if cardinal:
            lines.append("### Cardinal Safety Rules")
            lines.append(cardinal)
            lines.append("")
        gotchas = critical_rules.get("known_gotchas", "")
        if gotchas:
            lines.append("### Known Gotchas")
            lines.append(gotchas)
            lines.append("")

    # Recovery steps — step 1 wording adapts based on whether rules were injected
    step1 = (
        "1. Rules above are re-injected — cardinal safety and gotchas are inline"
        if rules_injected
        else "1. Re-read `CLAUDE.md` for project rules and safety constraints"
    )
    lines.extend([
        "## Recovery Steps",
        "",
        step1,
        "2. Re-read `SESSION_STATE.md` for current task and progress",
        "3. Run `git diff` on modified files to see your in-progress work",
        "4. Continue with the tasks listed above",
        "",
        "## Important",
        "",
        "- Project rules in CLAUDE.md are authoritative — re-read them fully",
        "- Do NOT rely on pre-compaction memory for architectural decisions",
        "- Verify file state with `git status` before making changes",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Recovery digest (generic fallback — no snapshot available)
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
        "event_type": "compaction",
        "domain": "context_monitor",
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

    # Step 2: Read PreCompact snapshot (if available) and build recovery digest
    snapshot = read_snapshot(paths["snapshot_file"])
    if snapshot:
        digest = build_recovery_digest_from_snapshot(
            trigger=payload["trigger"],
            compact_summary=payload["compact_summary"],
            session_id=payload["session_id"],
            snapshot=snapshot,
        )
    else:
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
