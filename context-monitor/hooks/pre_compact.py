"""
CTX-8: PreCompact Hook — fires before context compaction.

Captures external session state to a JSON snapshot so the PostCompact hook
(CTX-7) can build a task-specific recovery digest instead of a generic one.

What it captures:
  - Context health from ~/.claude-context-health.json
  - git status (modified/untracked files)
  - git diff --stat (scope of changes)
  - TODAYS_TASKS.md TODO items
  - SESSION_STATE.md header (session number, date)
  - Compact anchor content
  - Chat role from CCA_CHAT_ID env var

What it does NOT capture:
  - Conversation content (inaccessible from hook)
  - Full file contents (too large, re-readable)

The snapshot is written atomically to ~/.claude-compaction-snapshot.json
and consumed (read + deleted) by the PostCompact hook.

Environment variables (all optional):
  CLAUDE_PRECOMPACT_DISABLED         - Set "1" to disable
  CLAUDE_COMPACTION_SNAPSHOT_PATH    - Snapshot path (default: ~/.claude-compaction-snapshot.json)
  CLAUDE_CONTEXT_STATE_FILE          - State file (default: ~/.claude-context-health.json)

Wire as PreCompact hook in .claude/settings.local.json:
  {
    "hooks": {
      "PreCompact": [
        {
          "matcher": "",
          "hooks": [
            {
              "type": "command",
              "command": "python3 /path/to/context-monitor/hooks/pre_compact.py"
            }
          ]
        }
      ]
    }
  }
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_VERSION = 1
DEFAULT_SNAPSHOT_PATH = Path.home() / ".claude-compaction-snapshot.json"
DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"
MAX_GIT_STATUS_LINES = 50
MAX_TODAYS_TASKS = 20
MAX_SESSION_HEADER_LINES = 50
GIT_TIMEOUT = 5  # seconds


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------

def is_disabled() -> bool:
    """Check if hook is disabled via environment variable."""
    return os.environ.get("CLAUDE_PRECOMPACT_DISABLED") == "1"


def resolve_paths() -> dict:
    """Resolve all config paths from environment or defaults."""
    snapshot_str = os.environ.get("CLAUDE_COMPACTION_SNAPSHOT_PATH", "")
    state_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    return {
        "snapshot": Path(snapshot_str) if snapshot_str else DEFAULT_SNAPSHOT_PATH,
        "state_file": Path(state_str) if state_str else DEFAULT_STATE_FILE,
    }


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------

def parse_payload(raw: str) -> dict:
    """Parse PreCompact hook payload from stdin JSON."""
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
        "hook_event_name": data.get("hook_event_name", "PreCompact"),
    }


# ---------------------------------------------------------------------------
# State capture functions (all return safe defaults on failure)
# ---------------------------------------------------------------------------

def read_context_health(state_path: Path) -> dict:
    """Read context health state file. Returns empty dict on failure."""
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "zone": data.get("zone", "unknown"),
            "pct": data.get("pct", 0),
            "tokens": data.get("tokens", 0),
            "turns": data.get("turns", 0),
            "window": data.get("window", 200_000),
        }
    except (json.JSONDecodeError, OSError):
        return {}


def run_git_command(args: list[str], cwd: str) -> str:
    """Run a git command with timeout. Returns empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            cwd=cwd or None,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def capture_git_status(cwd: str) -> list[str]:
    """Capture git status --short, limited to MAX_GIT_STATUS_LINES."""
    output = run_git_command(["status", "--short"], cwd)
    if not output:
        return []
    lines = output.splitlines()[:MAX_GIT_STATUS_LINES]
    return lines


def capture_git_diff_stat(cwd: str) -> str:
    """Capture git diff --stat summary line."""
    output = run_git_command(["diff", "--stat"], cwd)
    if not output:
        return ""
    # Return the last line which is the summary (e.g., "3 files changed, 180 insertions(+)")
    lines = output.splitlines()
    return lines[-1].strip() if lines else ""


def capture_todays_tasks(cwd: str) -> list[str]:
    """Extract TODO items from TODAYS_TASKS.md."""
    tasks_path = Path(cwd) / "TODAYS_TASKS.md" if cwd else Path("TODAYS_TASKS.md")
    if not tasks_path.exists():
        return []
    try:
        content = tasks_path.read_text(encoding="utf-8")
        todos = []
        for line in content.splitlines():
            stripped = line.strip()
            if "[TODO]" in stripped:
                # Clean up the line: remove leading "- " or "* "
                clean = stripped.lstrip("-* ").strip()
                todos.append(clean)
                if len(todos) >= MAX_TODAYS_TASKS:
                    break
        return todos
    except OSError:
        return []


def capture_session_header(cwd: str) -> str:
    """Extract session header from SESSION_STATE.md (first meaningful line).

    Looks for lines matching 'Session NNN' pattern (with a digit after 'Session ').
    Skips markdown headings that happen to contain the word 'Session'.
    """
    import re
    state_path = Path(cwd) / "SESSION_STATE.md" if cwd else Path("SESSION_STATE.md")
    if not state_path.exists():
        return ""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= MAX_SESSION_HEADER_LINES:
                    break
                stripped = line.strip()
                # Skip markdown headings
                if stripped.startswith("#"):
                    continue
                # Look for "Session NNN" pattern (must have a digit)
                if re.search(r"Session\s+\d+", stripped):
                    return stripped
        return ""
    except OSError:
        return ""


def capture_anchor_summary(cwd: str) -> str:
    """Read compact anchor file for zone/health summary."""
    anchor_path = Path(cwd) / ".claude-compact-anchor.md" if cwd else Path(".claude-compact-anchor.md")
    if not anchor_path.exists():
        return ""
    try:
        content = anchor_path.read_text(encoding="utf-8")
        # Extract the Zone line
        for line in content.splitlines():
            if line.startswith("- Zone:"):
                return line.lstrip("- ").strip()
        return ""
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Snapshot building and writing
# ---------------------------------------------------------------------------

def build_snapshot(payload: dict, paths: dict) -> dict:
    """Build the complete compaction snapshot from all sources."""
    cwd = payload.get("cwd", "") or os.getcwd()

    snapshot = {
        "version": SNAPSHOT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": "auto",  # PreCompact doesn't tell us, PostCompact does
        "session_id": payload.get("session_id", ""),
        "cwd": cwd,
        "chat_role": os.environ.get("CCA_CHAT_ID", ""),
        "context_health": read_context_health(paths["state_file"]),
        "git_status": capture_git_status(cwd),
        "git_diff_stat": capture_git_diff_stat(cwd),
        "todays_tasks_todos": capture_todays_tasks(cwd),
        "session_header": capture_session_header(cwd),
        "anchor_content": capture_anchor_summary(cwd),
    }
    return snapshot


def write_snapshot(path: Path, snapshot: dict) -> bool:
    """Write snapshot atomically. Returns True on success."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)
        tmp.replace(path)
        return True
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


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

    # Build and write snapshot
    snapshot = build_snapshot(payload, paths)
    write_snapshot(paths["snapshot"], snapshot)

    # PreCompact hooks cannot block — always exit 0
    sys.exit(0)


if __name__ == "__main__":
    main()
