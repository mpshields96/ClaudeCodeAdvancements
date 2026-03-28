#!/usr/bin/env python3
"""Generate a Codex-native wrap prompt for ClaudeCodeAdvancements.

This is the Codex-side analogue of `/cca-wrap-desktop`: it inspects the
current repo state and emits a ready-to-paste prompt that tells Codex how to
close out the session safely and consistently.

Usage:
  python3 codex_wrap.py
  python3 codex_wrap.py --write CODEX_WRAP_PROMPT.md
  python3 codex_wrap.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from codex_init import normalize_cli_root


DEFAULT_REPO_ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
DEFAULT_OUTPUT_FILE = "CODEX_WRAP_PROMPT.md"

RUNTIME_PREFIXES = (
    ".session_pids/",
)

RUNTIME_PATHS = {
    ".queue_hook_last_check",
    "CODEX_WRAP_PROMPT.md",
    "cca_internal_queue.jsonl",
    "self-learning/journal.jsonl",
    "session_timings.jsonl",
}


@dataclass
class GitStatusEntry:
    code: str
    path: str


@dataclass
class WrapSnapshot:
    branch: str
    substantive: list[GitStatusEntry]
    runtime: list[GitStatusEntry]
    recent_commits: list[str]


def _run_git(root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def parse_git_status(output: str) -> list[GitStatusEntry]:
    entries: list[GitStatusEntry] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        code = raw_line[:2]
        path = raw_line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append(GitStatusEntry(code=code, path=path))
    return entries


def is_runtime_path(path: str) -> bool:
    if path in RUNTIME_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in RUNTIME_PREFIXES)


def collect_snapshot(root: str) -> WrapSnapshot:
    branch = _run_git(root, "branch", "--show-current").strip() or "DETACHED"
    status_entries = parse_git_status(_run_git(root, "status", "--short"))
    recent_raw = _run_git(root, "log", "--oneline", "-3")
    recent_commits = [line for line in recent_raw.splitlines() if line.strip()]

    substantive = [entry for entry in status_entries if not is_runtime_path(entry.path)]
    runtime = [entry for entry in status_entries if is_runtime_path(entry.path)]

    return WrapSnapshot(
        branch=branch,
        substantive=substantive,
        runtime=runtime,
        recent_commits=recent_commits,
    )


def _format_entries(entries: list[GitStatusEntry]) -> list[str]:
    if not entries:
        return ["- none"]
    return [f"- [{entry.code}] {entry.path}" for entry in entries]


def build_wrap_prompt(root: str, snapshot: WrapSnapshot) -> str:
    lines = [
        f"Use $cca-desktop-workflow in wrap mode for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Substantive git changes to account for:",
        *_format_entries(snapshot.substantive),
        "",
        "Runtime/generated session artifacts to ignore unless explicitly asked:",
        *_format_entries(snapshot.runtime),
        "",
        "Recent commits for context:",
    ]

    if snapshot.recent_commits:
        lines.extend(f"- {line}" for line in snapshot.recent_commits)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Wrap checklist:",
            "1. Run the most relevant validation for the substantive changes.",
            "2. Summarize what changed, what passed, and any remaining risks.",
            "3. Commit if there are substantive changes ready to land.",
            "4. Leave runtime/session files alone unless the task explicitly includes them.",
            "5. If the result matters inside CCA, send a direct queue note from codex to desktop and leave a durable note in CODEX_TO_CLAUDE.md when useful.",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def write_prompt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex wrap prompt for CCA.")
    parser.add_argument("--root", default=DEFAULT_REPO_ROOT, help="Repo root to inspect.")
    parser.add_argument(
        "--write",
        nargs="?",
        const=DEFAULT_OUTPUT_FILE,
        help="Write the generated prompt to a file instead of only printing it.",
    )
    args = parser.parse_args(argv)

    root, override_notice = normalize_cli_root(args.root, canonical_root=DEFAULT_REPO_ROOT)
    if override_notice:
        print(override_notice, file=sys.stderr)
    snapshot = collect_snapshot(root)
    prompt = build_wrap_prompt(root, snapshot)

    if args.write:
        out_path = args.write
        if not os.path.isabs(out_path):
            out_path = os.path.join(root, out_path)
        write_prompt(out_path, prompt)
        print(out_path)
        return 0

    sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
