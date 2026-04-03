#!/usr/bin/env python3
"""Repo-aware Codex terminal workflow dispatcher.

Provides a single entry point for repo-local Codex workflows so shell helpers
can expose commands like:

  codex init
  codex auto
  codex wrap
  codex chat

For ClaudeCodeAdvancements, this reuses the richer `codex_init.py`,
`codex_auto.py`, and `codex_wrap.py` prompt builders.

For polymarket-bot, it generates lighter-weight prompts from local state files.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from codex_auto import build_auto_prompt as build_cca_auto_prompt
from codex_auto import collect_snapshot as collect_cca_init_snapshot
from codex_auto import pick_auto_task
from codex_init import build_init_prompt as build_cca_init_prompt
from codex_init import normalize_cli_root as normalize_cca_root
from codex_wrap import build_wrap_prompt as build_cca_wrap_prompt
from codex_wrap import collect_snapshot as collect_cca_wrap_snapshot


CCA_ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
POLYBOT_ROOT = os.path.expanduser("~/Projects/polymarket-bot")
DEFAULT_CODEX_BIN = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_REASONING = 'model_reasoning_effort="high"'
DEFAULT_PROMPT_FILES = {
    "init": "CODEX_INIT_PROMPT.md",
    "auto": "CODEX_AUTO_PROMPT.md",
    "next": "CODEX_AUTO_PROMPT.md",
    "wrap": "CODEX_WRAP_PROMPT.md",
}


@dataclass
class PolybotSnapshot:
    branch: str
    substantive: list[str]
    runtime: list[str]
    recent_commits: list[str]
    pending_tasks: list[str]
    bot_state: list[str]


def _run_git(root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def _git_top_level(cwd: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def detect_repo_root(cwd: str | None = None) -> str:
    cwd = os.path.abspath(cwd or os.getcwd())
    top = _git_top_level(cwd)
    if top:
        return top
    if cwd.startswith(os.path.abspath(CCA_ROOT)):
        return os.path.abspath(CCA_ROOT)
    if cwd.startswith(os.path.abspath(POLYBOT_ROOT)):
        return os.path.abspath(POLYBOT_ROOT)
    return cwd


def detect_repo_type(root: str) -> str:
    norm = os.path.abspath(os.path.expanduser(root))
    if norm == os.path.abspath(os.path.expanduser(CCA_ROOT)):
        return "cca"
    if norm == os.path.abspath(os.path.expanduser(POLYBOT_ROOT)):
        return "polybot"
    return "unknown"


def normalize_root(root: str | None = None) -> tuple[str, str]:
    detected = detect_repo_root(root or os.getcwd())
    repo_type = detect_repo_type(detected)
    if repo_type == "cca":
        normalized, _notice = normalize_cca_root(detected, canonical_root=CCA_ROOT)
        return normalized, "cca"
    return detected, repo_type


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _parse_polybot_pending_tasks(content: str) -> list[str]:
    tasks: list[str] = []
    in_pending = False
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("## PENDING TASKS"):
            in_pending = True
            continue
        if in_pending and stripped.startswith("## "):
            break
        if in_pending and re.match(r"^\d+\.\s+", stripped):
            tasks.append(re.sub(r"^\d+\.\s*", "", stripped))
    return tasks


def _parse_polybot_state(content: str) -> list[str]:
    state: list[str] = []
    in_state = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## BOT STATE"):
            in_state = True
            continue
        if in_state and stripped.startswith("## "):
            break
        if in_state and stripped:
            state.append(stripped)
    return state[:8]


def _is_runtime_path(path: str) -> bool:
    runtime_paths = {
        ".queue_hook_last_check",
        "bot.pid",
        "SESSION_HANDOFF.md.bak",
    }
    runtime_prefixes = (
        "logs/",
        ".session_pids/",
        "__pycache__/",
    )
    if path in runtime_paths:
        return True
    return any(path.startswith(prefix) for prefix in runtime_prefixes)


def collect_polybot_snapshot(root: str) -> PolybotSnapshot:
    handoff = _read_text(os.path.join(root, "SESSION_HANDOFF.md"))
    branch = _run_git(root, "branch", "--show-current").strip() or "DETACHED"
    status_lines = [line for line in _run_git(root, "status", "--short").splitlines() if line.strip()]
    recent_commits = [line for line in _run_git(root, "log", "--oneline", "-5").splitlines() if line.strip()]
    substantive: list[str] = []
    runtime: list[str] = []
    for line in status_lines:
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if _is_runtime_path(path):
            runtime.append(line)
        else:
            substantive.append(line)
    return PolybotSnapshot(
        branch=branch,
        substantive=substantive,
        runtime=runtime,
        recent_commits=recent_commits,
        pending_tasks=_parse_polybot_pending_tasks(handoff),
        bot_state=_parse_polybot_state(handoff),
    )


def _fmt_lines(items: list[str], empty: str = "- none") -> list[str]:
    if not items:
        return [empty]
    return [f"- {item}" for item in items]


def build_polybot_init_prompt(root: str, snapshot: PolybotSnapshot) -> str:
    lines = [
        f"Use this as the Codex init prompt for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Read first:",
        "- AGENTS.md",
        "- SESSION_HANDOFF.md",
        "- CLAUDE.md",
        "",
        "Current bot state snapshot:",
        *_fmt_lines(snapshot.bot_state),
        "",
        "Pending tasks from SESSION_HANDOFF.md:",
        *_fmt_lines(snapshot.pending_tasks),
        "",
        "Substantive git changes to account for:",
        *_fmt_lines(snapshot.substantive),
        "",
        "Runtime/generated files to ignore unless explicitly asked:",
        *_fmt_lines(snapshot.runtime),
        "",
        "Recent commits:",
        *_fmt_lines(snapshot.recent_commits),
        "",
        "Init checklist:",
        "1. Confirm the live bot state before making changes.",
        "2. Check kill-switch and bankroll constraints before touching trading behavior.",
        "3. Pick one narrow task from SESSION_HANDOFF.md and work it end-to-end.",
        "4. Prefer tests first for risky trading logic.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_polybot_auto_prompt(root: str, snapshot: PolybotSnapshot, task_override: str | None = None) -> str:
    task = task_override.strip() if task_override else (
        snapshot.pending_tasks[0] if snapshot.pending_tasks else "Pick the next narrow polymarket-bot deliverable."
    )
    lines = [
        f"Use this as the Codex auto prompt for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Auto target:",
        f"- Selected task: {task}",
        "- Stop after 1 meaningful deliverable, then reassess SESSION_HANDOFF.md.",
        "",
        "Current bot state snapshot:",
        *_fmt_lines(snapshot.bot_state),
        "",
        "Substantive git changes to account for:",
        *_fmt_lines(snapshot.substantive),
        "",
        "Runtime/generated files to ignore unless explicitly asked:",
        *_fmt_lines(snapshot.runtime),
        "",
        "Execution loop:",
        "1. Work one narrow task from SESSION_HANDOFF.md.",
        "2. Run the smallest relevant validation before and after edits.",
        "3. Keep live-money safety rules ahead of convenience.",
        "4. Commit clearly when the deliverable is ready.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_polybot_wrap_prompt(root: str, snapshot: PolybotSnapshot) -> str:
    lines = [
        f"Use this as the Codex wrap prompt for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Substantive git changes to account for:",
        *_fmt_lines(snapshot.substantive),
        "",
        "Runtime/generated files to ignore unless explicitly asked:",
        *_fmt_lines(snapshot.runtime),
        "",
        "Recent commits:",
        *_fmt_lines(snapshot.recent_commits),
        "",
        "Wrap checklist:",
        "1. Run the most relevant tests/verification.",
        "2. Summarize what changed and any remaining trading risk.",
        "3. Commit if the work is ready.",
        "4. Update SESSION_HANDOFF.md only if the task changed real operator state.",
    ]
    return "\n".join(lines).strip() + "\n"


def find_codex_bin() -> str | None:
    env_bin = os.environ.get("CODEX_BIN", "").strip()
    if env_bin and os.path.exists(env_bin):
        return env_bin
    if os.path.exists(DEFAULT_CODEX_BIN):
        return DEFAULT_CODEX_BIN
    return shutil.which("codex")


def launch_codex(prompt: str, root: str, repo_type: str) -> int:
    codex_bin = find_codex_bin()
    if not codex_bin:
        print("Codex binary not found. Set CODEX_BIN or install Codex CLI.", file=sys.stderr)
        return 127

    env = os.environ.copy()
    if repo_type in {"cca", "polybot"}:
        env["CCA_CHAT_ID"] = "codex"

    cmd = [
        codex_bin,
        "-m", "gpt-5.4",
        "-c", DEFAULT_REASONING,
        "-s", "danger-full-access",
        "-a", "never",
        prompt,
    ]
    return subprocess.run(cmd, cwd=root, env=env).returncode


def write_prompt(path: str, prompt: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(prompt)


def build_prompt(mode: str, root: str, repo_type: str, task: str | None = None) -> str:
    if mode == "next":
        mode = "auto"
    if repo_type == "cca":
        if mode == "init":
            snapshot = collect_cca_init_snapshot(root)
            return build_cca_init_prompt(root, snapshot)
        if mode == "auto":
            snapshot = collect_cca_init_snapshot(root)
            return build_cca_auto_prompt(root, snapshot, task_override=task)
        if mode == "wrap":
            snapshot = collect_cca_wrap_snapshot(root)
            return build_cca_wrap_prompt(root, snapshot)
        raise ValueError(f"Unsupported mode for CCA: {mode}")

    if repo_type == "polybot":
        snapshot = collect_polybot_snapshot(root)
        if mode == "init":
            return build_polybot_init_prompt(root, snapshot)
        if mode == "auto":
            return build_polybot_auto_prompt(root, snapshot, task_override=task)
        if mode == "wrap":
            return build_polybot_wrap_prompt(root, snapshot)
        raise ValueError(f"Unsupported mode for polymarket-bot: {mode}")

    raise ValueError(f"Unsupported repo for workflow mode '{mode}': {root}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repo-aware Codex workflow dispatcher.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "auto", "next", "wrap"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--root", default=None, help="Repo root. Defaults to current git top-level.")
        sub.add_argument("--write", default=None, help="Optional output file for the generated prompt.")
        sub.add_argument("--launch", action="store_true", help="Launch Codex with the generated prompt.")
        if name in {"auto", "next"}:
            sub.add_argument("--task", default=None, help="Explicit task override.")

    chat = subparsers.add_parser("chat")
    chat.add_argument("--root", default=None, help="Repo root. Defaults to current git top-level.")
    chat.add_argument("prompt", nargs="?", default="", help="Optional direct startup prompt.")

    args = parser.parse_args(argv)
    root, repo_type = normalize_root(args.root)

    if args.command == "chat":
        return launch_codex(args.prompt, root, repo_type)

    if args.command == "next":
        print("`codex next` is a legacy alias for `codex auto`.", file=sys.stderr)

    prompt = build_prompt(args.command, root, repo_type, task=getattr(args, "task", None))
    default_prompt_name = DEFAULT_PROMPT_FILES.get(args.command)

    if getattr(args, "write", None):
        out_path = args.write
        if not os.path.isabs(out_path):
            out_path = os.path.join(root, out_path)
        write_prompt(out_path, prompt)
        print(out_path)
        return 0

    if getattr(args, "launch", False):
        if default_prompt_name:
            write_prompt(os.path.join(root, default_prompt_name), prompt)
        return launch_codex(prompt, root, repo_type)

    sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
