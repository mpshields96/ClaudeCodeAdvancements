#!/usr/bin/env python3
"""
plan_compliance.py — Spec Plan Compliance Reviewer (SPEC-6)

Detects implementation drift and scope creep by comparing code files being
written against the tasks.md spec. Inspired by Google Conductor's automated
5-point review — adapted for individual Claude Code sessions.

Problem: After tasks.md is approved, implementation can silently drift.
Files get written that weren't in the plan, or work jumps ahead to future
tasks. By the time you notice, the spec and code diverge.

Solution: Before writing a code file, check it against tasks.md:
  - Is there an approved tasks.md?
  - Is there an active (in-progress or next-pending) task?
  - Is the file mentioned in the active task's scope?
  - If not, is it in a future task? (warn: out of order)
  - If not in any task at all: scope creep alert

Usage (standalone CLI):
    python3 spec-system/plan_compliance.py <file_path> [tasks_md_path]

Usage (library):
    from plan_compliance import compliance_report, ComplianceStatus
    result = compliance_report("path/to/file.py", tasks_md_text)

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ── Enums ─────────────────────────────────────────────────────────────────────

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ComplianceStatus(Enum):
    COMPLIANT = "compliant"           # File matches active task scope
    FUTURE_TASK = "future_task"       # File is in spec but a later task
    SCOPE_CREEP = "scope_creep"       # File not mentioned in any task
    NO_SPEC = "no_spec"               # tasks.md not found / not provided
    NOT_APPROVED = "not_approved"     # tasks.md exists but lacks "Status: APPROVED"
    NO_ACTIVE_TASK = "no_active_task" # All tasks done or list is empty


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class Task:
    title: str
    status: TaskStatus
    body: str


@dataclass
class ComplianceResult:
    status: ComplianceStatus
    message: str
    active_task: str | None = None  # Title of the active task, if any
    matched_task: str | None = None  # Title of the matching task (may be future)


# ── Task Parsing ─────────────────────────────────────────────────────────────

# Matches "## Task N — Title" or "## Task N — Title [IN PROGRESS]" etc.
_TASK_HEADER_RE = re.compile(
    r"^##\s+(?:Task\s+\d+\s+[—–-]+\s+)?(.+?)(?:\s+\[(IN PROGRESS|DONE|COMPLETE)\])?\s*$",
    re.IGNORECASE,
)


def _parse_status_from_header(header_line: str) -> TaskStatus:
    """Detect [IN PROGRESS] / [DONE] tags in the header line."""
    line_upper = header_line.upper()
    if "[IN PROGRESS]" in line_upper:
        return TaskStatus.IN_PROGRESS
    if "[DONE]" in line_upper or "[COMPLETE]" in line_upper:
        return TaskStatus.DONE
    return TaskStatus.PENDING


def _parse_status_from_body(body: str) -> TaskStatus:
    """
    Infer status from checkbox state in the task body.
    If all items are [x], the task is DONE.
    If any item is [x] and any is [ ], it's IN PROGRESS.
    """
    checked = len(re.findall(r"\[x\]", body, re.IGNORECASE))
    unchecked = len(re.findall(r"\[ \]", body))

    if checked > 0 and unchecked == 0:
        return TaskStatus.DONE
    if checked > 0 and unchecked > 0:
        return TaskStatus.IN_PROGRESS
    return TaskStatus.PENDING


def load_tasks(tasks_md: str) -> list[Task]:
    """
    Parse a tasks.md string into a list of Task objects.

    Extracts ## headings as task titles, reads their body text,
    and infers status from [IN PROGRESS]/[DONE] tags or checkbox state.
    """
    tasks: list[Task] = []
    lines = tasks_md.splitlines()

    current_title: str | None = None
    current_status: TaskStatus = TaskStatus.PENDING
    current_body_lines: list[str] = []

    def _flush():
        if current_title is not None:
            body = "\n".join(current_body_lines).strip()
            # Header tag takes precedence; fall back to checkbox heuristic
            status = current_status
            if status == TaskStatus.PENDING and body:
                inferred = _parse_status_from_body(body)
                if inferred != TaskStatus.PENDING:
                    status = inferred
            tasks.append(Task(title=current_title, status=status, body=body))

    for line in lines:
        if line.startswith("## "):
            _flush()
            current_title = None
            current_body_lines = []

            # Strip "Task N — " prefix if present
            title_raw = line[3:].strip()
            # Remove [IN PROGRESS] / [DONE] suffix for title
            title_clean = re.sub(
                r"\s*\[(IN PROGRESS|DONE|COMPLETE)\]\s*$", "", title_raw, flags=re.IGNORECASE
            ).strip()
            # Remove "Task N — " prefix
            title_clean = re.sub(r"^Task\s+\d+\s+[—–-]+\s+", "", title_clean).strip()
            if title_clean:
                current_title = title_clean
                current_status = _parse_status_from_header(title_raw)

        elif current_title is not None:
            current_body_lines.append(line)

    _flush()
    return tasks


# ── Active Task Selection ──────────────────────────────────────────────────────

def extract_active_task(tasks: list[Task]) -> Task | None:
    """
    Return the most relevant task to work on right now.
    Priority: IN_PROGRESS > first PENDING > None (if all DONE).
    """
    # First pass: explicit IN_PROGRESS
    for task in tasks:
        if task.status == TaskStatus.IN_PROGRESS:
            return task
    # Second pass: first pending
    for task in tasks:
        if task.status == TaskStatus.PENDING:
            return task
    return None


# ── File Scope Checking ────────────────────────────────────────────────────────

def _normalize_filename(path_str: str) -> str:
    """Extract lowercase basename from a path string."""
    return Path(path_str).name.lower()


def _stem(path_str: str) -> str:
    """Return the lowercase stem (filename without extension)."""
    return Path(path_str).stem.lower()


def check_file_in_scope(file_path: str, task: Task) -> bool:
    """
    Return True if file_path is mentioned in the task's scope.

    Matching strategy (any of these suffices):
    1. Full path substring match (case-insensitive)
    2. Basename match (case-insensitive)
    3. For test files: check if the implementation module is mentioned
       (e.g., test_memory_store.py matches when memory_store.py is in scope)
    """
    if not task.body:
        return False

    body_lower = task.body.lower()
    file_lower = file_path.lower()
    basename_lower = _normalize_filename(file_path)

    # 1. Full path in body
    if file_lower in body_lower:
        return True

    # 2. Basename in body
    if basename_lower in body_lower:
        return True

    # 3. Test file heuristic: test_foo.py → look for foo.py in body
    if basename_lower.startswith("test_"):
        impl_name = basename_lower[5:]  # strip "test_"
        if impl_name in body_lower:
            return True
        impl_stem = _stem(impl_name)
        if impl_stem and impl_stem in body_lower:
            return True

    return False


def check_scope_creep(file_path: str, tasks: list[Task]) -> bool:
    """
    Return True if file_path is not mentioned in ANY task in the list.
    (i.e., it was never planned — this is scope creep.)
    """
    for task in tasks:
        if check_file_in_scope(file_path, task):
            return False
    return True


# ── Approval Check ────────────────────────────────────────────────────────────

def _is_approved(tasks_md: str) -> bool:
    """Return True if tasks.md contains 'Status: APPROVED'."""
    return "Status: APPROVED" in tasks_md


# ── Main Compliance Report ────────────────────────────────────────────────────

def compliance_report(file_path: str, tasks_md: str | None) -> ComplianceResult:
    """
    Full compliance check for a file against a tasks.md string.

    Args:
        file_path: Path to the file being written (used for scope matching).
        tasks_md: Full text of tasks.md, or None if not found.

    Returns:
        ComplianceResult with status, message, and optional task context.
    """
    basename = Path(file_path).name

    # No spec
    if tasks_md is None:
        return ComplianceResult(
            status=ComplianceStatus.NO_SPEC,
            message=(
                f"[plan-compliance] No tasks.md found. "
                f"Writing {basename} without an approved plan. "
                f"Run /spec:tasks to generate one."
            ),
        )

    # Not approved
    if not _is_approved(tasks_md):
        return ComplianceResult(
            status=ComplianceStatus.NOT_APPROVED,
            message=(
                f"[plan-compliance] tasks.md exists but is not approved. "
                f"Add 'Status: APPROVED' after reviewing the plan."
            ),
        )

    tasks = load_tasks(tasks_md)
    active_task = extract_active_task(tasks)

    # No active task
    if active_task is None:
        return ComplianceResult(
            status=ComplianceStatus.NO_ACTIVE_TASK,
            message=(
                f"[plan-compliance] All tasks appear complete. "
                f"Writing {basename} — consider updating tasks.md if this is new work."
            ),
        )

    active_title = active_task.title

    # Check if file is in the active task scope
    if check_file_in_scope(file_path, active_task):
        return ComplianceResult(
            status=ComplianceStatus.COMPLIANT,
            message=(
                f"[plan-compliance] {basename} matches active task: '{active_title}'."
            ),
            active_task=active_title,
            matched_task=active_title,
        )

    # Not in active task — check future tasks
    future_tasks = [
        t for t in tasks
        if t is not active_task and t.status != TaskStatus.DONE
    ]
    for future_task in future_tasks:
        if check_file_in_scope(file_path, future_task):
            return ComplianceResult(
                status=ComplianceStatus.FUTURE_TASK,
                message=(
                    f"[plan-compliance] {basename} belongs to future task "
                    f"'{future_task.title}', not the current task '{active_title}'. "
                    f"Consider finishing the active task first."
                ),
                active_task=active_title,
                matched_task=future_task.title,
            )

    # Not in any task — scope creep
    return ComplianceResult(
        status=ComplianceStatus.SCOPE_CREEP,
        message=(
            f"[plan-compliance] {basename} ({file_path}) is not mentioned in any task. "
            f"This may be scope creep. "
            f"Current task: '{active_title}'. "
            f"Update tasks.md if this file is intentional."
        ),
        active_task=active_title,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _find_tasks_md(start_dir: str) -> str | None:
    """Walk up from start_dir looking for tasks.md."""
    current = Path(start_dir).resolve()
    for _ in range(10):
        candidate = current / "tasks.md"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError:
                return None
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python3 plan_compliance.py <file_path> [tasks_md_path]\n"
            "       or: pipe tasks.md path as second arg, or auto-discover from cwd."
        )
        sys.exit(1)

    file_path = sys.argv[1]

    tasks_md: str | None
    if len(sys.argv) >= 3:
        try:
            tasks_md = Path(sys.argv[2]).read_text(encoding="utf-8")
        except OSError as e:
            print(f"Error reading tasks.md: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        tasks_md = _find_tasks_md(str(Path(file_path).parent))

    result = compliance_report(file_path, tasks_md)

    icon = {
        ComplianceStatus.COMPLIANT: "✓",
        ComplianceStatus.FUTURE_TASK: "⚠",
        ComplianceStatus.SCOPE_CREEP: "✗",
        ComplianceStatus.NO_SPEC: "?",
        ComplianceStatus.NOT_APPROVED: "!",
        ComplianceStatus.NO_ACTIVE_TASK: "~",
    }.get(result.status, "?")

    print(f"{icon} {result.message}")

    if result.status in (ComplianceStatus.SCOPE_CREEP, ComplianceStatus.FUTURE_TASK):
        sys.exit(2)


if __name__ == "__main__":
    main()
