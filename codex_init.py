#!/usr/bin/env python3
"""Generate a Codex-native init prompt for ClaudeCodeAdvancements.

This is the Codex-side analogue of `/cca-init`: it inspects the current repo
state, runs a lightweight baseline validation, and emits a ready-to-paste init
prompt plus briefing for the desktop workflow.

Usage:
  python3 codex_init.py
  python3 codex_init.py --write CODEX_INIT_PROMPT.md
  python3 codex_init.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field


DEFAULT_REPO_ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
DEFAULT_OUTPUT_FILE = "CODEX_INIT_PROMPT.md"

RUNTIME_PREFIXES = (
    ".session_pids/",
)

RUNTIME_PATHS = {
    ".queue_hook_last_check",
    "CODEX_INIT_PROMPT.md",
    "CODEX_WRAP_PROMPT.md",
    "cca_internal_queue.jsonl",
    "self-learning/journal.jsonl",
    "session_timings.jsonl",
}

HIGH_REASONING_KEYWORDS = (
    "architecture",
    "autoloop",
    "coordination",
    "framework",
    "multi-agent",
    "orchestration",
    "refactor",
)


@dataclass
class GitStatusEntry:
    code: str
    path: str


@dataclass
class SessionSummary:
    session_num: int | None = None
    session_date: str = ""
    phase: str = ""
    next_items: list[str] = field(default_factory=list)


@dataclass
class InboxSummary:
    unread_count: int = 0
    subjects: list[str] = field(default_factory=list)


@dataclass
class ValidationSummary:
    mode: str
    passed: bool
    summary: str


@dataclass
class InitSnapshot:
    branch: str
    substantive: list[GitStatusEntry]
    runtime: list[GitStatusEntry]
    recent_commits: list[str]
    session: SessionSummary
    todos: list[str]
    inbox_subjects: list[str]
    unread_count: int
    claude_notes: list[str]
    validation: ValidationSummary


def _run_git(root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def _run_python(root: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )


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


def parse_session_state(content: str) -> SessionSummary:
    session_num = None
    session_date = ""
    phase = ""
    next_items: list[str] = []

    match = re.search(r"Session\s+(\d+)\s*(?:—|-)\s*(\d{4}-\d{2}-\d{2})", content)
    if match:
        session_num = int(match.group(1))
        session_date = match.group(2)
    else:
        match = re.search(r"Session\s+(\d+)", content)
        if match:
            session_num = int(match.group(1))

    phase_match = re.search(r"^\*\*Phase:\*\*\s*(.+)$", content, re.MULTILINE)
    if phase_match:
        phase = phase_match.group(1).strip()

    in_next = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("**Next:") or stripped.startswith("**Next ("):
            in_next = True
            continue
        if in_next:
            if re.match(r"^\d+\.\s+", stripped):
                next_items.append(re.sub(r"^\d+\.\s*", "", stripped))
                continue
            if not stripped:
                if next_items:
                    break
                continue
            if stripped.startswith("**") or stripped.startswith("---"):
                break

    return SessionSummary(
        session_num=session_num,
        session_date=session_date,
        phase=phase,
        next_items=next_items,
    )


def parse_todays_tasks(content: str) -> list[str]:
    todos: list[str] = []
    for raw_line in content.splitlines():
        if "[TODO]" not in raw_line:
            continue
        cleaned = raw_line.strip().lstrip("#").strip()
        cleaned = cleaned.replace("[TODO]", "").strip()
        todos.append(cleaned)
    return todos


def parse_codex_inbox(output: str) -> InboxSummary:
    if "No unread messages" in output:
        return InboxSummary()

    count_match = re.search(r"\((\d+)\s+unread\)", output)
    unread_count = int(count_match.group(1)) if count_match else 0
    subjects = []

    for line in output.splitlines():
        match = re.match(r"\s+\[[A-Z]+\]\s+(.+)", line)
        if match:
            subjects.append(match.group(1).strip())

    return InboxSummary(unread_count=unread_count, subjects=subjects)


def parse_claude_to_codex(content: str) -> list[str]:
    pattern = re.compile(r"^##\s+\[(.+?)\]\s+—\s+(.+?)\s+—\s+(.+)$", re.MULTILINE)
    entries = []
    for timestamp, label, title in pattern.findall(content):
        entries.append(f"[{timestamp}] — {label} — {title}")
    return entries


def _read_if_exists(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def run_validation(root: str) -> ValidationSummary:
    summary_proc = _run_python(root, "init_cache.py", "summary")
    summary_output = (summary_proc.stdout or summary_proc.stderr).strip()
    lowered = summary_output.lower()

    if summary_proc.returncode == 0 and "stale" not in lowered and "no test cache" not in lowered:
        return ValidationSummary(mode="cache", passed=True, summary=summary_output)

    smoke_proc = _run_python(root, "init_cache.py", "smoke")
    smoke_output = (smoke_proc.stdout or smoke_proc.stderr).strip()
    match = re.search(r"Smoke:\s*(\d+)/(\d+)\s*passed", smoke_output)
    if match:
        passed = match.group(1) == match.group(2)
        return ValidationSummary(mode="smoke", passed=passed, summary=smoke_output)

    return ValidationSummary(
        mode="smoke",
        passed=smoke_proc.returncode == 0,
        summary=smoke_output or "Smoke test did not produce output.",
    )


def select_top_task(todos: list[str], session_next: list[str]) -> str:
    if todos:
        return todos[0]
    if session_next:
        return session_next[0]
    return ""


def suggest_reasoning_level(task: str) -> str:
    lowered = task.lower()
    if any(keyword in lowered for keyword in HIGH_REASONING_KEYWORDS):
        return "high recommended"
    return "default"


def determine_next_step(snapshot: InitSnapshot, top_task: str) -> str:
    if snapshot.unread_count:
        return "Review unread Codex inbox items before starting new work."
    if snapshot.todos and top_task:
        return f"Start the first remaining daily task: {top_task}."
    if snapshot.session.next_items and top_task:
        return f"Start the first session-state next item: {top_task}."
    if snapshot.substantive:
        return "Account for the existing substantive git changes before starting a new task."
    return "Pick the next narrow CCA deliverable in auto mode."


def collect_snapshot(root: str) -> InitSnapshot:
    branch = _run_git(root, "branch", "--show-current").strip() or "DETACHED"
    status_entries = parse_git_status(_run_git(root, "status", "--short"))
    recent_raw = _run_git(root, "log", "--oneline", "-3")
    recent_commits = [line for line in recent_raw.splitlines() if line.strip()]

    substantive = [entry for entry in status_entries if not is_runtime_path(entry.path)]
    runtime = [entry for entry in status_entries if is_runtime_path(entry.path)]

    session_path = os.path.join(root, "SESSION_STATE.md")
    todays_tasks_path = os.path.join(root, "TODAYS_TASKS.md")
    claude_to_codex_path = os.path.join(root, "CLAUDE_TO_CODEX.md")

    session = parse_session_state(_read_if_exists(session_path))
    todos = parse_todays_tasks(_read_if_exists(todays_tasks_path))
    claude_notes = parse_claude_to_codex(_read_if_exists(claude_to_codex_path))[-3:]

    inbox_proc = _run_python(root, "cca_comm.py", "inbox", "codex")
    inbox = parse_codex_inbox((inbox_proc.stdout or inbox_proc.stderr).strip())

    validation = run_validation(root)

    return InitSnapshot(
        branch=branch,
        substantive=substantive,
        runtime=runtime,
        recent_commits=recent_commits,
        session=session,
        todos=todos,
        inbox_subjects=inbox.subjects,
        unread_count=inbox.unread_count,
        claude_notes=claude_notes,
        validation=validation,
    )


def _format_entries(entries: list[GitStatusEntry]) -> list[str]:
    if not entries:
        return ["- none"]
    return [f"- [{entry.code}] {entry.path}" for entry in entries]


def _format_lines(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def build_init_prompt(root: str, snapshot: InitSnapshot) -> str:
    top_task = select_top_task(snapshot.todos, snapshot.session.next_items)
    reasoning_level = suggest_reasoning_level(top_task)
    next_step = determine_next_step(snapshot, top_task)
    phase_line = snapshot.session.phase or "No phase summary found."
    session_bits = []
    if snapshot.session.session_num is not None:
        session_bits.append(f"Session {snapshot.session.session_num}")
    if snapshot.session.session_date:
        session_bits.append(snapshot.session.session_date)
    session_line = " — ".join(session_bits) if session_bits else "Unknown session"

    lines = [
        f"Use $cca-desktop-workflow in init mode for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Init briefing:",
        f"- Last session: {session_line}",
        f"- Current phase: {phase_line}",
        f"- Top task: {top_task or 'No explicit task found from TODAYS_TASKS.md or SESSION_STATE.md.'}",
        f"- Suggested reasoning level: {reasoning_level}",
        f"- Immediate next step: {next_step}",
        "",
        "Substantive git changes to account for:",
        *_format_entries(snapshot.substantive),
        "",
        "Runtime/generated files worth ignoring unless explicitly asked:",
        *_format_entries(snapshot.runtime),
        "",
        "Baseline validation:",
        f"- {snapshot.validation.summary or 'No validation output.'}",
        "",
        "Codex inbox:",
        *_format_lines(snapshot.inbox_subjects or (["No unread messages"] if snapshot.unread_count == 0 else [])),
        "",
        "Latest Claude -> Codex notes:",
        *_format_lines(snapshot.claude_notes),
        "",
        "Recent commits for context:",
        *_format_lines(snapshot.recent_commits),
        "",
        "Init checklist:",
        "1. Read AGENTS.md, SESSION_STATE.md, TODAYS_TASKS.md, SESSION_RESUME.md, and CLAUDE_TO_CODEX.md.",
        "2. Respect the runtime/generated files above unless the task explicitly includes them.",
        "3. Prefer today's tasks first; otherwise fall through to the session state's next item.",
        "4. Use CCA comms directly if coordination matters.",
    ]
    return "\n".join(lines).strip() + "\n"


def write_prompt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex init prompt for CCA.")
    parser.add_argument("--root", default=DEFAULT_REPO_ROOT, help="Repo root to inspect.")
    parser.add_argument(
        "--write",
        nargs="?",
        const=DEFAULT_OUTPUT_FILE,
        help="Write the generated prompt to a file instead of only printing it.",
    )
    args = parser.parse_args(argv)

    root = os.path.abspath(os.path.expanduser(args.root))
    snapshot = collect_snapshot(root)
    prompt = build_init_prompt(root, snapshot)

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
