"""
USAGE-1: Token/Cost Counter CLI

Reads Claude Code transcript JSONL files to provide per-session and aggregate
token/cost analysis. All logic is pure functions for easy testing.

Usage:
  python3 usage_counter.py sessions [--project PATH] [--limit N]
  python3 usage_counter.py session <id> [--project PATH]
  python3 usage_counter.py today [--project PATH]
  python3 usage_counter.py week [--project PATH]
  python3 usage_counter.py project [PATH]

Transcript format (from context-monitor/hooks/meter.py — proven):
  Path: ~/.claude/projects/<PROJECT_HASH>/<session_id>.jsonl
  PROJECT_HASH = absolute project dir with / replaced by -
  Token data in assistant entries: entry["message"]["usage"]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Cost models (per 1M tokens)
# ---------------------------------------------------------------------------

COST_MODELS = {
    "sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_create": 3.75,
    },
    "opus": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_create": 18.75,
    },
    "haiku": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_create": 0.3125,
    },
}

DEFAULT_MODEL = "sonnet"


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def cost_for_tokens(
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_create: int,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Calculate cost breakdown for a set of token counts and a model.

    Returns a dict with per-category costs and total, all in USD.
    """
    rates = COST_MODELS.get(model, COST_MODELS[DEFAULT_MODEL])
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    cache_read_cost = (cache_read / 1_000_000) * rates["cache_read"]
    cache_create_cost = (cache_create / 1_000_000) * rates["cache_create"]
    total = input_cost + output_cost + cache_read_cost + cache_create_cost

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "cache_read_cost": round(cache_read_cost, 6),
        "cache_create_cost": round(cache_create_cost, 6),
        "total": round(total, 6),
        "model": model,
    }


def detect_model(entry: dict) -> str | None:
    """
    Detect model name from a transcript entry.

    Looks for 'model' field at top level or inside 'message'.
    Normalizes to one of: sonnet, opus, haiku. Returns None if not found.
    """
    model_str = entry.get("model", "")
    if not model_str and isinstance(entry.get("message"), dict):
        model_str = entry["message"].get("model", "")
    if not model_str:
        return None

    model_lower = model_str.lower()
    if "opus" in model_lower:
        return "opus"
    if "haiku" in model_lower:
        return "haiku"
    if "sonnet" in model_lower:
        return "sonnet"
    # Unknown model string — return None so caller can use default
    return None


def extract_session_usage(transcript_path: Path) -> dict:
    """
    Parse a transcript JSONL file and extract aggregate token usage.

    Returns a dict with:
      - input_tokens: total input tokens across all turns
      - output_tokens: total output tokens across all turns
      - cache_read_tokens: total cache read tokens
      - cache_create_tokens: total cache creation tokens
      - total_tokens: sum of all categories
      - turn_count: number of entries in the transcript
      - assistant_turns: number of assistant entries with usage data
      - model: detected model (or 'sonnet' default)
      - first_timestamp: ISO string of earliest entry, or None
      - last_timestamp: ISO string of latest entry, or None
      - session_id: derived from filename
    """
    result = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_create_tokens": 0,
        "total_tokens": 0,
        "turn_count": 0,
        "assistant_turns": 0,
        "model": DEFAULT_MODEL,
        "first_timestamp": None,
        "last_timestamp": None,
        "session_id": transcript_path.stem,
    }

    if not transcript_path.exists():
        return result

    detected_model = None
    timestamps = []

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

                result["turn_count"] += 1

                # Extract timestamp if present
                ts = entry.get("timestamp")
                if not ts and isinstance(entry.get("message"), dict):
                    ts = entry["message"].get("timestamp")
                if ts:
                    timestamps.append(ts)

                # Detect model from any entry
                m = detect_model(entry)
                if m:
                    detected_model = m

                # Extract usage — try message.usage first (Claude Code format),
                # then top-level usage (test fixtures / legacy)
                usage = None
                if entry.get("type") == "assistant":
                    msg = entry.get("message", {})
                    if isinstance(msg, dict):
                        usage = msg.get("usage")
                if usage is None:
                    usage = entry.get("usage")

                if not isinstance(usage, dict):
                    continue

                input_tok = usage.get("input_tokens", 0)
                output_tok = usage.get("output_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                cache_create = usage.get("cache_creation_input_tokens", 0)

                if input_tok or output_tok or cache_read or cache_create:
                    result["assistant_turns"] += 1
                    result["input_tokens"] += input_tok
                    result["output_tokens"] += output_tok
                    result["cache_read_tokens"] += cache_read
                    result["cache_create_tokens"] += cache_create

    except OSError:
        return result

    if detected_model:
        result["model"] = detected_model

    result["total_tokens"] = (
        result["input_tokens"]
        + result["output_tokens"]
        + result["cache_read_tokens"]
        + result["cache_create_tokens"]
    )

    if timestamps:
        timestamps.sort()
        result["first_timestamp"] = timestamps[0]
        result["last_timestamp"] = timestamps[-1]

    return result


def derive_project_hash(project_dir: str) -> str:
    """Convert an absolute project path to the Claude Code project hash."""
    clean = project_dir.rstrip("/")
    return clean.replace("/", "-")


def get_project_transcript_dir(project_dir: str) -> Path:
    """Return the directory containing transcripts for a project."""
    project_hash = derive_project_hash(project_dir)
    return Path.home() / ".claude" / "projects" / project_hash


def list_sessions(
    project_dir: str,
    limit: int = 0,
    since: datetime | None = None,
) -> list[dict]:
    """
    Discover and parse all session transcripts for a project.

    Args:
        project_dir: Absolute path to the project directory.
        limit: Max sessions to return (0 = all). Applied after sorting.
        since: Only include sessions modified on or after this datetime.

    Returns a list of session dicts, each containing:
      - All fields from extract_session_usage()
      - file_mtime: datetime of the transcript file modification time
      - costs: dict from cost_for_tokens()
    """
    transcript_dir = get_project_transcript_dir(project_dir)
    if not transcript_dir.exists():
        return []

    sessions = []
    for jsonl_file in transcript_dir.glob("*.jsonl"):
        # Get file modification time
        try:
            stat = jsonl_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            continue

        # Filter by date if requested
        if since is not None:
            if mtime < since:
                continue

        usage = extract_session_usage(jsonl_file)
        costs = cost_for_tokens(
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cache_read=usage["cache_read_tokens"],
            cache_create=usage["cache_create_tokens"],
            model=usage["model"],
        )

        session = {**usage, "file_mtime": mtime, "costs": costs}
        sessions.append(session)

    # Sort by modification time, most recent first
    sessions.sort(key=lambda s: s["file_mtime"], reverse=True)

    if limit > 0:
        sessions = sessions[:limit]

    return sessions


def aggregate_sessions(sessions: list[dict]) -> dict:
    """
    Aggregate token counts and costs across multiple sessions.

    Returns a dict with totals and session count.
    """
    agg = {
        "session_count": len(sessions),
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_create_tokens": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "by_model": {},
    }

    for s in sessions:
        agg["input_tokens"] += s["input_tokens"]
        agg["output_tokens"] += s["output_tokens"]
        agg["cache_read_tokens"] += s["cache_read_tokens"]
        agg["cache_create_tokens"] += s["cache_create_tokens"]
        agg["total_tokens"] += s["total_tokens"]
        agg["total_cost"] += s["costs"]["total"]

        model = s["model"]
        if model not in agg["by_model"]:
            agg["by_model"][model] = {
                "session_count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
            }
        agg["by_model"][model]["session_count"] += 1
        agg["by_model"][model]["total_tokens"] += s["total_tokens"]
        agg["by_model"][model]["total_cost"] += s["costs"]["total"]

    agg["total_cost"] = round(agg["total_cost"], 6)
    for m in agg["by_model"]:
        agg["by_model"][m]["total_cost"] = round(agg["by_model"][m]["total_cost"], 6)

    return agg


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_tokens(n: int) -> str:
    """Format a token count with commas."""
    return f"{n:,}"


def format_cost(cost: float) -> str:
    """Format a cost value as USD."""
    return f"${cost:.2f}"


def format_session_detail(usage: dict, costs: dict, mtime: datetime | None = None) -> str:
    """
    Format a single session's usage for display.

    Returns a multi-line string with token breakdown and costs.
    """
    lines = []
    sid = usage.get("session_id", "unknown")
    model = usage.get("model", DEFAULT_MODEL)

    header_parts = [f"Session: {sid}"]
    if mtime:
        header_parts.append(mtime.strftime("%Y-%m-%d %H:%M"))
    header_parts.append(f"Model: {model}")
    lines.append("  |  ".join(header_parts))

    lines.append(
        f"  Input:  {format_tokens(usage['input_tokens'])} tokens "
        f"({format_cost(costs['input_cost'])})"
    )
    lines.append(
        f"  Output: {format_tokens(usage['output_tokens'])} tokens "
        f"({format_cost(costs['output_cost'])})"
    )
    lines.append(
        f"  Cache:  {format_tokens(usage['cache_read_tokens'])} read "
        f"({format_cost(costs['cache_read_cost'])}) + "
        f"{format_tokens(usage['cache_create_tokens'])} create "
        f"({format_cost(costs['cache_create_cost'])})"
    )
    lines.append(
        f"  Total:  {format_tokens(usage['total_tokens'])} tokens  |  "
        f"Est. cost: {format_cost(costs['total'])}"
    )
    lines.append(f"  Turns:  {usage['turn_count']} total, {usage['assistant_turns']} with usage")

    return "\n".join(lines)


def format_session_row(session: dict) -> str:
    """Format a single session as a compact one-line row for table display."""
    sid = session["session_id"][:12]
    mtime = session["file_mtime"].strftime("%Y-%m-%d %H:%M")
    model = session["model"][:6]
    tokens = format_tokens(session["total_tokens"])
    cost = format_cost(session["costs"]["total"])
    return f"  {sid:<14} {mtime:<18} {model:<8} {tokens:>12}   {cost:>8}"


def format_sessions_table(sessions: list[dict], title: str = "Sessions") -> str:
    """Format a list of sessions as a table with header and totals."""
    lines = []
    lines.append(f"\n{title}")
    lines.append("=" * 72)
    lines.append(f"  {'Session':<14} {'Date':<18} {'Model':<8} {'Tokens':>12}   {'Cost':>8}")
    lines.append("-" * 72)

    for s in sessions:
        lines.append(format_session_row(s))

    lines.append("-" * 72)

    agg = aggregate_sessions(sessions)
    lines.append(
        f"  {'TOTAL':<14} {agg['session_count']} sessions{'':<8} "
        f"{format_tokens(agg['total_tokens']):>12}   {format_cost(agg['total_cost']):>8}"
    )

    if len(agg["by_model"]) > 1:
        lines.append("")
        lines.append("  By model:")
        for model, data in sorted(agg["by_model"].items()):
            lines.append(
                f"    {model:<8} {data['session_count']} sessions  "
                f"{format_tokens(data['total_tokens']):>12}   {format_cost(data['total_cost']):>8}"
            )

    lines.append("")
    return "\n".join(lines)


def format_aggregate(agg: dict, title: str = "Aggregate Usage") -> str:
    """Format an aggregate dict for display."""
    lines = []
    lines.append(f"\n{title}")
    lines.append("=" * 50)
    lines.append(f"  Sessions:      {agg['session_count']}")
    lines.append(f"  Input tokens:  {format_tokens(agg['input_tokens'])}")
    lines.append(f"  Output tokens: {format_tokens(agg['output_tokens'])}")
    lines.append(f"  Cache read:    {format_tokens(agg['cache_read_tokens'])}")
    lines.append(f"  Cache create:  {format_tokens(agg['cache_create_tokens'])}")
    lines.append(f"  Total tokens:  {format_tokens(agg['total_tokens'])}")
    lines.append(f"  Est. cost:     {format_cost(agg['total_cost'])}")

    if agg["by_model"]:
        lines.append("")
        lines.append("  By model:")
        for model, data in sorted(agg["by_model"].items()):
            lines.append(
                f"    {model:<8} {data['session_count']} sessions  "
                f"{format_tokens(data['total_tokens']):>12}   {format_cost(data['total_cost']):>8}"
            )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_sessions(args: argparse.Namespace) -> None:
    """List recent sessions with token counts and estimated cost."""
    project_dir = os.path.abspath(args.project)
    sessions = list_sessions(project_dir, limit=args.limit)
    if not sessions:
        print(f"No sessions found for project: {project_dir}")
        return
    print(format_sessions_table(sessions, title=f"Recent Sessions — {project_dir}"))


def cmd_session(args: argparse.Namespace) -> None:
    """Detailed breakdown for one session."""
    project_dir = os.path.abspath(args.project)
    transcript_dir = get_project_transcript_dir(project_dir)
    session_id = args.session_id

    # Try exact match first, then prefix match
    jsonl_path = transcript_dir / f"{session_id}.jsonl"
    if not jsonl_path.exists():
        # Try prefix match
        matches = list(transcript_dir.glob(f"{session_id}*.jsonl"))
        if len(matches) == 1:
            jsonl_path = matches[0]
        elif len(matches) > 1:
            print(f"Ambiguous session ID '{session_id}'. Matches:")
            for m in matches:
                print(f"  {m.stem}")
            return
        else:
            print(f"No session found matching '{session_id}' in {transcript_dir}")
            return

    usage = extract_session_usage(jsonl_path)
    costs = cost_for_tokens(
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cache_read=usage["cache_read_tokens"],
        cache_create=usage["cache_create_tokens"],
        model=usage["model"],
    )

    try:
        mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        mtime = None

    print()
    print(format_session_detail(usage, costs, mtime))
    print()


def cmd_today(args: argparse.Namespace) -> None:
    """Aggregate usage for today."""
    project_dir = os.path.abspath(args.project)
    now = datetime.now(tz=timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = list_sessions(project_dir, since=start_of_day)
    if not sessions:
        print(f"No sessions today for project: {project_dir}")
        return
    print(format_sessions_table(sessions, title=f"Today's Sessions — {project_dir}"))


def cmd_week(args: argparse.Namespace) -> None:
    """Aggregate usage for this week (last 7 days)."""
    project_dir = os.path.abspath(args.project)
    now = datetime.now(tz=timezone.utc)
    start_of_week = now - timedelta(days=7)
    sessions = list_sessions(project_dir, since=start_of_week)
    if not sessions:
        print(f"No sessions this week for project: {project_dir}")
        return
    print(format_sessions_table(sessions, title=f"This Week's Sessions — {project_dir}"))


def cmd_project(args: argparse.Namespace) -> None:
    """Show all usage for a project."""
    project_dir = os.path.abspath(args.path)
    sessions = list_sessions(project_dir)
    if not sessions:
        print(f"No sessions found for project: {project_dir}")
        return
    agg = aggregate_sessions(sessions)
    print(format_aggregate(agg, title=f"Project Usage — {project_dir}"))
    print(format_sessions_table(sessions, title="All Sessions"))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser."""
    parser = argparse.ArgumentParser(
        prog="usage_counter",
        description="Token/cost counter for Claude Code sessions",
    )
    parser.add_argument(
        "--project",
        default=os.getcwd(),
        help="Project directory (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # sessions
    sp_sessions = subparsers.add_parser("sessions", help="List recent sessions")
    sp_sessions.add_argument(
        "--limit", type=int, default=20, help="Max sessions to show (default: 20)"
    )
    sp_sessions.set_defaults(func=cmd_sessions)

    # session <id>
    sp_session = subparsers.add_parser("session", help="Detailed view of one session")
    sp_session.add_argument("session_id", help="Session ID (or prefix)")
    sp_session.set_defaults(func=cmd_session)

    # today
    sp_today = subparsers.add_parser("today", help="Today's usage")
    sp_today.set_defaults(func=cmd_today)

    # week
    sp_week = subparsers.add_parser("week", help="This week's usage")
    sp_week.set_defaults(func=cmd_week)

    # project
    sp_project = subparsers.add_parser("project", help="All usage for a project")
    sp_project.add_argument(
        "path", nargs="?", default=os.getcwd(), help="Project path (default: cwd)"
    )
    sp_project.set_defaults(func=cmd_project)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
