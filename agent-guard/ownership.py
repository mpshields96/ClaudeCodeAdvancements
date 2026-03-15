"""
AG-2: Ownership Manifest

Generates a file ownership map from git history, showing which session last
modified each file and flagging files at risk of multi-agent conflicts.

Use this before starting a parallel agent run to understand which files are
currently "in flight" from other recent sessions.

Usage:
  python3 agent-guard/ownership.py                      # Recent file activity
  python3 agent-guard/ownership.py --commits 10         # Last 10 commits
  python3 agent-guard/ownership.py --hours 24           # Files changed in 24h
  python3 agent-guard/ownership.py --output OWNERSHIP.md  # Write to file
  python3 agent-guard/ownership.py --conflicts-only     # Only show conflict risks

Output: Markdown table with columns: File, Last Session, Date, Commit Message
Conflict detection: files appearing in 2+ commits within the lookback window.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Git data extraction (pure output — no side effects beyond subprocess)
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a git command. Returns (returncode, stdout)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return result.returncode, result.stdout
    except FileNotFoundError:
        return 1, ""


def is_git_repo(cwd: str) -> bool:
    code, _ = _run_git(["rev-parse", "--git-dir"], cwd=cwd)
    return code == 0


def get_recent_commits(cwd: str, max_commits: int = 20) -> list[dict]:
    """
    Return list of commit dicts with keys: hash, author, date_iso, subject.
    Sorted newest-first.
    """
    fmt = "%H\x1f%an\x1f%ai\x1f%s"
    code, out = _run_git(
        ["log", f"--max-count={max_commits}", f"--pretty=format:{fmt}"],
        cwd=cwd,
    )
    if code != 0 or not out.strip():
        return []

    commits = []
    for line in out.strip().splitlines():
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue
        commits.append({
            "hash": parts[0][:8],
            "author": parts[1],
            "date_iso": parts[2],
            "subject": parts[3],
        })
    return commits


def get_files_for_commit(commit_hash: str, cwd: str) -> list[str]:
    """Return list of files changed in a specific commit."""
    code, out = _run_git(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash],
        cwd=cwd,
    )
    if code != 0:
        return []
    return [f.strip() for f in out.strip().splitlines() if f.strip()]


def get_uncommitted_files(cwd: str) -> list[str]:
    """Return files currently modified (staged or unstaged)."""
    code, out = _run_git(["status", "--porcelain"], cwd=cwd)
    if code != 0:
        return []
    files = []
    for line in out.strip().splitlines():
        if len(line) >= 4:
            path = line[3:].strip()
            if " -> " in path:  # Renamed: old -> new
                path = path.split(" -> ")[-1]
            files.append(path)
    return files


# ---------------------------------------------------------------------------
# Ownership analysis (pure functions)
# ---------------------------------------------------------------------------

def extract_session_label(subject: str) -> str:
    """
    Extract a short session/agent label from the commit subject.
    Examples:
      "AG-1: iPhone mobile approver hook" → "AG-1"
      "Session 6: browse-url skill" → "Session 6"
      "fix: typo in README" → "(fix)"
    """
    # Match patterns like "AG-1:", "CTX-3:", "MEM-5:", "Session N:"
    patterns = [
        r"^((?:AG|CTX|MEM|SPEC|USAGE)-\d+)",
        r"^(Session\s+\d+)",
        r"^([A-Z][A-Z0-9\-]+-\d+)",  # Generic prefix-number
    ]
    for pat in patterns:
        m = re.match(pat, subject, re.IGNORECASE)
        if m:
            return m.group(1)
    # Fall back to first word of subject (capped at 15 chars)
    first_word = subject.split(":")[0].strip()[:15]
    return f"({first_word})"


def parse_date(date_iso: str) -> datetime | None:
    """Parse ISO 8601 date string to datetime."""
    try:
        # Handle both "2026-03-08 22:41:55 +0000" and "2026-03-08T22:41:55+00:00"
        date_iso = date_iso.replace(" ", "T", 1)
        # Handle "+HHMM" format (no colon in offset)
        if re.search(r'[+-]\d{4}$', date_iso):
            date_iso = date_iso[:-2] + ":" + date_iso[-2:]
        return datetime.fromisoformat(date_iso)
    except (ValueError, TypeError):
        return None


def build_ownership_map(
    commits: list[dict],
    cwd: str,
    since_dt: datetime | None = None,
) -> dict[str, list[dict]]:
    """
    Build {filepath: [commit_record, ...]} where commits are sorted newest-first.
    Optionally filter to commits since since_dt.
    """
    ownership: dict[str, list[dict]] = {}

    for commit in commits:
        if since_dt:
            commit_dt = parse_date(commit["date_iso"])
            if commit_dt and commit_dt < since_dt:
                continue

        files = get_files_for_commit(commit["hash"], cwd)
        for f in files:
            if f not in ownership:
                ownership[f] = []
            ownership[f].append(commit)

    return ownership


def find_conflict_risks(ownership: dict[str, list[dict]]) -> list[str]:
    """
    Return list of files that appear in 2+ different commits — potential conflicts.
    """
    return [f for f, commits in ownership.items() if len(commits) >= 2]


def format_date_short(date_iso: str) -> str:
    """Format date as YYYY-MM-DD HH:MM."""
    dt = parse_date(date_iso)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M")
    return date_iso[:16]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(
    ownership: dict[str, list[dict]],
    uncommitted: list[str],
    conflict_risks: list[str],
    cwd: str,
    conflicts_only: bool = False,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Ownership Manifest",
        f"_Generated: {now} | Project: {Path(cwd).name}_",
        "",
    ]

    # Uncommitted changes section
    if uncommitted:
        lines.append("## ⚠ Uncommitted Changes (in-flight this session)")
        for f in sorted(uncommitted):
            lines.append(f"- `{f}`")
        lines.append("")

    # Conflict risk section
    if conflict_risks:
        lines.append("## Conflict Risk Files (modified in 2+ recent commits)")
        lines.append("These files were touched by multiple sessions. Coordinate before editing.")
        lines.append("")
        lines.append("| File | Sessions | Last Modified |")
        lines.append("|------|----------|---------------|")
        for f in sorted(conflict_risks):
            commits = ownership[f]
            sessions = ", ".join(
                sorted({extract_session_label(c["subject"]) for c in commits})
            )
            last = format_date_short(commits[0]["date_iso"])
            lines.append(f"| `{f}` | {sessions} | {last} |")
        lines.append("")

    if conflicts_only:
        return "\n".join(lines)

    # Full ownership table
    if ownership:
        lines.append("## Recent File Activity")
        lines.append("")
        lines.append("| File | Last Session | Date | Commit |")
        lines.append("|------|-------------|------|--------|")
        for f in sorted(ownership.keys()):
            last_commit = ownership[f][0]
            session = extract_session_label(last_commit["subject"])
            date = format_date_short(last_commit["date_iso"])
            subject = last_commit["subject"][:50]
            lines.append(f"| `{f}` | {session} | {date} | {subject} |")
        lines.append("")
    else:
        lines.append("_No file activity found in the lookback window._")
        lines.append("")

    if not uncommitted and not conflict_risks:
        lines.append("_No uncommitted changes. No conflict risks detected._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python3 agent-guard/ownership.py",
        description="Generate file ownership manifest from git history",
    )
    parser.add_argument(
        "--commits", type=int, default=20,
        help="Number of recent commits to analyze (default: 20)"
    )
    parser.add_argument(
        "--hours", type=float, default=0,
        help="Only show files modified in the last N hours (0 = no time filter)"
    )
    parser.add_argument(
        "--output", metavar="PATH",
        help="Write OWNERSHIP.md to this path (default: print to stdout)"
    )
    parser.add_argument(
        "--conflicts-only", action="store_true",
        help="Only show conflict risk files"
    )
    parser.add_argument(
        "--dir", metavar="PATH",
        help="Project directory (default: cwd)"
    )
    args = parser.parse_args()

    cwd = args.dir or os.getcwd()

    if not is_git_repo(cwd):
        print(f"Not a git repository: {cwd}", file=sys.stderr)
        return 1

    since_dt = None
    if args.hours > 0:
        since_dt = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    commits = get_recent_commits(cwd, max_commits=args.commits)
    if not commits:
        print("No commits found.", file=sys.stderr)
        return 0

    ownership = build_ownership_map(commits, cwd, since_dt=since_dt)
    uncommitted = get_uncommitted_files(cwd)
    conflict_risks = find_conflict_risks(ownership)

    report = build_report(
        ownership=ownership,
        uncommitted=uncommitted,
        conflict_risks=conflict_risks,
        cwd=cwd,
        conflicts_only=args.conflicts_only,
    )

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Written to {args.output}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
