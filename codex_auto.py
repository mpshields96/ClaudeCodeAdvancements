#!/usr/bin/env python3
"""Generate a Codex-native auto-work prompt for ClaudeCodeAdvancements.

This is the Codex-side analogue of `/cca-auto`: it selects the next task from
live repo state and emits a ready-to-paste prompt for a focused Codex work
cycle that can later be stacked under bounded autoloop behavior.

Usage:
  python3 codex_auto.py
  python3 codex_auto.py --task "Build codex_auto.py"
  python3 codex_auto.py --write CODEX_AUTO_PROMPT.md
"""

from __future__ import annotations

import argparse
import os
import sys

from codex_init import (
    DEFAULT_REPO_ROOT,
    GitStatusEntry,
    InitSnapshot,
    collect_snapshot,
    normalize_cli_root,
    suggest_reasoning_level,
)


DEFAULT_OUTPUT_FILE = "CODEX_AUTO_PROMPT.md"


def pick_auto_task(snapshot: InitSnapshot, task_override: str | None = None) -> tuple[str, str]:
    if not snapshot.validation.passed:
        return ("Fix failing baseline validation before starting new work.", "validation")
    if task_override:
        return (task_override.strip(), "override")
    if snapshot.todos:
        return (snapshot.todos[0], "todays_tasks")
    if snapshot.resume_priorities:
        return (snapshot.resume_priorities[0], "session_resume")
    if snapshot.priority_recommendation:
        return (snapshot.priority_recommendation, "priority_picker")
    if snapshot.session.next_items:
        return (snapshot.session.next_items[0], "session_state")
    if snapshot.inbox_subjects:
        return (snapshot.inbox_subjects[0], "inbox")
    return ("Pick the next narrow CCA deliverable.", "fallback")


def _format_entries(entries: list[GitStatusEntry]) -> list[str]:
    if not entries:
        return ["- none"]
    return [f"- [{entry.code}] {entry.path}" for entry in entries]


def _format_lines(items: list[str]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def build_auto_prompt(
    root: str,
    snapshot: InitSnapshot,
    task_override: str | None = None,
    max_deliverables: int = 1,
) -> str:
    task, source = pick_auto_task(snapshot, task_override=task_override)
    reasoning_level = suggest_reasoning_level(task)
    deliverable_word = "deliverable" if max_deliverables == 1 else "deliverables"

    lines = [
        f"Use $cca-desktop-workflow in auto mode for {root}.",
        f"Current branch: {snapshot.branch}.",
        "",
        "Auto target:",
        f"- Selected task: {task}",
        f"- Task source: {source}",
        f"- Suggested reasoning level: {reasoning_level}",
        f"- Stop after {max_deliverables} meaningful {deliverable_word}, then re-check tasks/comms before continuing.",
        "",
        "Start-of-loop validation:",
        f"- {snapshot.validation.summary or 'No validation output.'}",
        "",
        "Substantive git changes to account for:",
        *_format_entries(snapshot.substantive),
        "",
        "Runtime/generated files to ignore unless explicitly asked:",
        *_format_entries(snapshot.runtime),
        "",
        "Unread Codex inbox items:",
        *_format_lines(snapshot.inbox_subjects),
        "",
        "SESSION_RESUME priorities in play:",
        *_format_lines(snapshot.resume_priorities),
        "",
        "Cross-agent coordination to keep in view:",
        *_format_lines(snapshot.coordination_notes),
        "",
        "CCA self-learning signals to honor:",
        f"- Wrap trend: {snapshot.wrap_trend or 'none'}",
        f"- Pending tips: {snapshot.pending_tips or 'none'}",
        f"- Session insights: {snapshot.session_insights or 'none'}",
        f"- Recent corrections: {snapshot.recent_corrections or 'none'}",
        "",
        "CCA optimization signals to honor:",
        f"- Priority briefing: {snapshot.priority_briefing or 'none'}",
        f"- Priority recommendation: {snapshot.priority_recommendation or 'none'}",
        f"- MT proposals: {snapshot.mt_proposals or 'none'}",
        f"- Session timeline: {snapshot.session_timeline or 'none'}",
        f"- Hivemind status: {snapshot.hivemind_status or 'none'}",
        "",
        "Latest Claude -> Codex notes:",
        *_format_lines(snapshot.claude_notes),
        "",
        "Recent commits for context:",
        *_format_lines(snapshot.recent_commits),
        "",
        "Execution loop:",
        "1. Re-read TODAYS_TASKS.md, SESSION_RESUME.md, CLAUDE_TO_CODEX.md, and the learning/optimization signals above before starting if the task target has drifted.",
        "2. Work the selected task in narrow scope with TDD when the change is non-trivial.",
        "3. Test before and after edits when practical.",
        "4. Commit once the deliverable is ready.",
        "5. Run `python3 bridge_status.py` as the first coordination-round check so stale lanes and likely relay gaps are explicit.",
        "6. Check Codex inbox, SESSION_STATE.md next items, relevant bridge notes, and whether the self-learning signals changed.",
        "7. Use CCA comms directly if coordination matters; do not use Matthew as a relay.",
    ]
    return "\n".join(lines).strip() + "\n"


def write_prompt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex auto prompt for CCA.")
    parser.add_argument("--root", default=DEFAULT_REPO_ROOT, help="Repo root to inspect.")
    parser.add_argument("--task", default=None, help="Explicit task override for this auto cycle.")
    parser.add_argument(
        "--write",
        nargs="?",
        const=DEFAULT_OUTPUT_FILE,
        help="Write the generated prompt to a file instead of only printing it.",
    )
    args = parser.parse_args(argv)

    root, override_notice = normalize_cli_root(args.root)
    if override_notice:
        print(override_notice, file=sys.stderr)
    snapshot = collect_snapshot(root)
    prompt = build_auto_prompt(root, snapshot, task_override=args.task)

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
