#!/usr/bin/env python3
"""Automated session handoff file generator.

Generates standardized SESSION_HANDOFF_S{N}.md files for multi-chat launches.
Proven pattern from S114/S115 trial runs — now automated.

Reads SESSION_STATE.md, git log, and test counts to produce a self-contained
briefing file that the next session can use immediately.

Usage:
    # Generate handoff for next session (3-chat mode)
    python3 handoff_generator.py generate --session 116 --mode 3chat \
        --worker-task "Build StackedAreaChart" \
        --worker-task "Build GroupedBarChart" \
        --desktop-focus "self-learning improvements"

    # Generate handoff for solo session
    python3 handoff_generator.py generate --session 116 --mode solo

    # Preview without writing
    python3 handoff_generator.py preview --session 116 --mode 2chat

CLI:
    python3 handoff_generator.py generate --session N [--mode MODE] [--worker-task TASK]...
    python3 handoff_generator.py preview --session N [--mode MODE]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass
class HandoffConfig:
    """Configuration for handoff file generation."""
    current_session: int
    next_session: int = 0  # auto-computed
    mode: str = "solo"  # solo, 2chat, 3chat
    worker_tasks: list = field(default_factory=list)
    desktop_focus: str = ""
    model: str = "Opus 4.6"
    kalshi_running: bool = False  # True for 3chat
    trial_run_number: int = 0  # 0 = not a trial run

    def __post_init__(self):
        if self.next_session == 0:
            self.next_session = self.current_session + 1
        if self.mode not in ("solo", "2chat", "3chat"):
            raise ValueError(f"Invalid mode: {self.mode}. Must be solo, 2chat, or 3chat.")
        if self.mode == "3chat":
            self.kalshi_running = True


@dataclass
class SessionSummary:
    """Extracted data from SESSION_STATE.md and git."""
    session_number: int = 0
    date: str = ""
    what_was_done: str = ""
    test_count: int = 0
    suite_count: int = 0
    commit_count: int = 0
    pending_manual: list = field(default_factory=list)
    next_priorities: list = field(default_factory=list)
    recent_commits: list = field(default_factory=list)


def parse_session_state(path: Optional[Path] = None) -> SessionSummary:
    """Extract session summary from SESSION_STATE.md."""
    if path is None:
        path = PROJECT_ROOT / "SESSION_STATE.md"

    summary = SessionSummary()

    if not path.exists():
        return summary

    content = path.read_text()

    # Extract session number
    m = re.search(r'Session\s+(\d+)', content)
    if m:
        summary.session_number = int(m.group(1))

    # Extract date
    m = re.search(r'(\d{4}-\d{2}-\d{2})', content)
    if m:
        summary.date = m.group(1)

    # Extract test count
    m = re.search(r'~?(\d{4,})\s+(?:passing|tests)', content)
    if m:
        summary.test_count = int(m.group(1))

    # Extract suite count
    m = re.search(r'~?(\d+)\s+suites', content)
    if m:
        summary.suite_count = int(m.group(1))

    # Extract "What was done" section (first occurrence only)
    m = re.search(
        r'\*\*What was done this session.*?\*\*\s*\n(.*?)(?=\n\*\*(?:Next|Still|What was done|Matthew|CAUTION))',
        content, re.DOTALL
    )
    if m:
        summary.what_was_done = m.group(1).strip()

    # Extract pending manual items
    pending_section = re.search(
        r'\*\*Still pending.*?\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)',
        content, re.DOTALL
    )
    if pending_section:
        for line in pending_section.group(1).strip().split('\n'):
            line = line.strip()
            if line.startswith('-'):
                summary.pending_manual.append(line[1:].strip())

    # Extract next priorities
    next_section = re.search(
        r'\*\*Next \(prioritized\):\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)',
        content, re.DOTALL
    )
    if next_section:
        for line in next_section.group(1).strip().split('\n'):
            line = line.strip()
            if re.match(r'^\d+\.', line):
                summary.next_priorities.append(re.sub(r'^\d+\.\s*', '', line))

    return summary


def get_recent_commits(count: int = 10) -> list:
    """Get recent git commit messages."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT)
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def count_session_commits(session_label: str) -> int:
    """Count commits for a session by searching git log for session label."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--all", f"--grep={session_label}"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT)
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
            return len(lines)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return 0


def generate_handoff(config: HandoffConfig, summary: Optional[SessionSummary] = None) -> str:
    """Generate the full handoff markdown content."""
    if summary is None:
        summary = parse_session_state()

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []

    # ── Header ────────────────────────────────────────────────────────────
    lines.append(f"# SESSION HANDOFF — S{config.current_session} -> S{config.next_session}")
    lines.append(f"# Generated {today} by S{config.current_session} ({_mode_label(config.mode)}, {config.model})")
    if config.trial_run_number > 0:
        lines.append(f"# 3-CHAT TRIAL RUN #{config.trial_run_number + 1}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Resume prompt ─────────────────────────────────────────────────────
    lines.append(f"## RESUME PROMPT FOR S{config.next_session}")
    lines.append("")
    mode_desc = _mode_label(config.mode)
    lines.append(
        f"Run /cca-init. Last session was S{config.current_session} on {today}. {mode_desc}."
    )
    lines.append("")

    # What was shipped
    if summary.what_was_done:
        # Truncate to first 3 bullet points for conciseness
        done_lines = [l for l in summary.what_was_done.split('\n') if l.strip().startswith('-')]
        done_preview = '; '.join(
            l.strip().lstrip('-').strip()[:80] for l in done_lines[:4]
        )
        lines.append(f"**S{config.current_session} shipped:** {done_preview}")
        lines.append("")

    # Test counts
    if summary.test_count > 0:
        tc = f"{summary.test_count} tests"
        if summary.suite_count > 0:
            tc += f" / {summary.suite_count} suites"
        lines.append(f"**Tests:** {tc}")
        lines.append("")

    # Pending manual items
    if summary.pending_manual:
        lines.append("**Still pending (Matthew manual):**")
        for item in summary.pending_manual:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── Multi-chat layout ─────────────────────────────────────────────────
    if config.mode in ("2chat", "3chat"):
        lines.append(f"## {'3' if config.mode == '3chat' else '2'}-CHAT LAYOUT")
        lines.append("")
        lines.append("| Chat | Role | Status |")
        lines.append("|------|------|--------|")
        lines.append("| **This chat** (CCA Desktop) | Coordinator | YOU ARE HERE |")
        lines.append("| **CCA CLI Worker** (Terminal) | Worker | YOU MUST LAUNCH IT |")
        if config.mode == "3chat":
            lines.append("| **Kalshi Main** (Terminal) | Independent | ALREADY RUNNING — DO NOT interfere |")
        lines.append("")

    # ── Worker tasks ──────────────────────────────────────────────────────
    if config.worker_tasks:
        lines.append("## WORKER TASK ASSIGNMENT")
        lines.append("")
        lines.append("Queue all tasks at launch via `cca_comm.py task cli1 \"...\"`. Worker loops on inbox.")
        lines.append("")
        for i, task in enumerate(config.worker_tasks, 1):
            priority = "PRIMARY" if i == 1 else ("SECONDARY" if i == 2 else "TERTIARY")
            lines.append(f"{i}. **{priority}**: {task}")
        lines.append("")

    # ── Desktop focus ─────────────────────────────────────────────────────
    if config.desktop_focus:
        lines.append("## DESKTOP FOCUS")
        lines.append("")
        lines.append(f"- {config.desktop_focus}")
        lines.append("- Coordination rounds every ~15 min")
        lines.append("- Update shared docs when worker reports")
        lines.append("")

    # ── Safety rules ──────────────────────────────────────────────────────
    if config.mode in ("2chat", "3chat"):
        lines.append("## SAFETY RULES")
        lines.append("")
        lines.append("1. DO NOT rush. Correctness > speed.")
        lines.append("2. DO NOT spawn expensive agents (no /gsd:plan-phase, no parallel agent dispatches).")
        lines.append("3. Verify the worker actually starts before assigning tasks.")
        lines.append("4. If anything goes wrong, STOP and tell Matthew.")
        lines.append("5. AUTH FIX may be pending — if worker fails with API billing errors, tell Matthew.")
        lines.append("6. Peak hours awareness: fewer tokens during 8AM-2PM ET weekdays.")
        lines.append("7. One coordination round every ~15 minutes.")
        lines.append("")

    # ── Success criteria ──────────────────────────────────────────────────
    lines.append("## SUCCESS CRITERIA")
    lines.append("")
    if config.mode == "solo":
        lines.append("- All tests pass at start and end")
        lines.append("- Meaningful progress on prioritized tasks")
        lines.append("- Clean wrap with all docs updated")
    elif config.mode == "2chat":
        lines.append("- Worker completes assigned tasks")
        lines.append("- No scope conflicts between desktop and worker")
        lines.append("- No errors, no broken tests")
        lines.append("- Clean wrap with all docs updated")
    else:  # 3chat
        lines.append("- Worker completes 2-3 tasks (not just 1)")
        lines.append("- Desktop does meaningful work in parallel on a different module")
        lines.append("- No scope conflicts, no errors, no broken tests")
        lines.append("- Kalshi chat runs undisturbed")
        lines.append("- Clean wrap with all docs updated")
    lines.append("")

    # ── Key files ─────────────────────────────────────────────────────────
    lines.append("## KEY FILES")
    lines.append("")
    lines.append("Standard /cca-init reads + this file.")
    if config.mode in ("2chat", "3chat"):
        lines.append("Also read: HIVEMIND_ROLLOUT.md")
    lines.append("")

    # ── Recent commits ────────────────────────────────────────────────────
    commits = get_recent_commits(8)
    if commits:
        lines.append("## RECENT COMMITS")
        lines.append("")
        for c in commits[:8]:
            lines.append(f"- {c}")
        lines.append("")

    return '\n'.join(lines)


def _mode_label(mode: str) -> str:
    """Human-readable mode label."""
    return {
        "solo": "Solo CCA",
        "2chat": "2-chat (desktop + worker)",
        "3chat": "3-chat (desktop + worker + Kalshi)",
    }.get(mode, mode)


def write_handoff(config: HandoffConfig, content: str) -> Path:
    """Write handoff to file and return the path."""
    filename = f"SESSION_HANDOFF_S{config.current_session}.md"
    path = PROJECT_ROOT / filename
    path.write_text(content)
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate session handoff files")
    sub = parser.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", help="Generate and write handoff file")
    gen.add_argument("--session", type=int, required=True, help="Current session number")
    gen.add_argument("--mode", choices=["solo", "2chat", "3chat"], default="solo")
    gen.add_argument("--worker-task", action="append", default=[], dest="worker_tasks",
                     help="Worker task (can specify multiple)")
    gen.add_argument("--desktop-focus", default="", help="Desktop focus area")
    gen.add_argument("--model", default="Opus 4.6")
    gen.add_argument("--trial-run", type=int, default=0, help="Trial run number (0=not a trial)")

    # preview
    prev = sub.add_parser("preview", help="Preview handoff without writing")
    prev.add_argument("--session", type=int, required=True)
    prev.add_argument("--mode", choices=["solo", "2chat", "3chat"], default="solo")
    prev.add_argument("--worker-task", action="append", default=[], dest="worker_tasks")
    prev.add_argument("--desktop-focus", default="")
    prev.add_argument("--model", default="Opus 4.6")
    prev.add_argument("--trial-run", type=int, default=0)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = HandoffConfig(
        current_session=args.session,
        mode=args.mode,
        worker_tasks=args.worker_tasks,
        desktop_focus=args.desktop_focus,
        model=args.model,
        trial_run_number=args.trial_run,
    )

    content = generate_handoff(config)

    if args.command == "preview":
        print(content)
    elif args.command == "generate":
        path = write_handoff(config, content)
        print(f"Handoff written to: {path}")
        print(f"Size: {len(content)} chars, {content.count(chr(10))} lines")


if __name__ == "__main__":
    main()
