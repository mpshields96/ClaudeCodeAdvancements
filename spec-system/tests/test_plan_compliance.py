#!/usr/bin/env python3
"""
Tests for spec-system/plan_compliance.py — Plan Compliance Review
TDD: tests written BEFORE implementation.
"""

import sys
import unittest
from pathlib import Path

# Ensure spec-system is importable
_SPEC_DIR = Path(__file__).resolve().parent.parent
if str(_SPEC_DIR) not in sys.path:
    sys.path.insert(0, str(_SPEC_DIR))

from plan_compliance import (
    Task,
    TaskStatus,
    load_tasks,
    extract_active_task,
    check_file_in_scope,
    check_scope_creep,
    compliance_report,
    ComplianceResult,
    ComplianceStatus,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

TASKS_MD_FULL = """
# Tasks

Status: APPROVED

## Task 1 — Build memory_store.py
- [ ] Implement SQLite schema
- Write `memory-system/memory_store.py`
- Write `memory-system/tests/test_memory_store.py`

## Task 2 — Build capture_hook.py [IN PROGRESS]
- [x] Write PostToolUse handler
- [ ] Write Stop handler
- Write `memory-system/hooks/capture_hook.py`

## Task 3 — Build mcp_server.py
- [ ] Implement MCP protocol
- Write `memory-system/mcp_server.py`
""".strip()

TASKS_MD_NO_ACTIVE = """
# Tasks

Status: APPROVED

## Task 1 — Build memory_store.py [DONE]
- [x] Implement SQLite schema
- [x] Write `memory-system/memory_store.py`
""".strip()

TASKS_MD_UNAPPROVED = """
# Tasks

Status: DRAFT

## Task 1 — Build something
- [ ] Do a thing
""".strip()

TASKS_MD_EMPTY = """
# Tasks

Status: APPROVED
""".strip()

TASKS_MD_CHECKLIST = """
# Tasks

Status: APPROVED

## Task 1 — Refactor agent_guard.py
- [ ] Move credential check to own function
- [ ] Write `agent-guard/hooks/credential_guard.py`
- [ ] Update `agent-guard/tests/test_credential_guard.py`
""".strip()


# ── load_tasks ────────────────────────────────────────────────────────────────

class TestLoadTasks(unittest.TestCase):

    def test_load_tasks_returns_list_of_task_objects(self):
        tasks = load_tasks(TASKS_MD_FULL)
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0)
        for t in tasks:
            self.assertIsInstance(t, Task)

    def test_load_tasks_correct_count(self):
        tasks = load_tasks(TASKS_MD_FULL)
        self.assertEqual(len(tasks), 3)

    def test_load_tasks_extracts_titles(self):
        tasks = load_tasks(TASKS_MD_FULL)
        titles = [t.title for t in tasks]
        self.assertIn("Build memory_store.py", titles)
        self.assertIn("Build capture_hook.py", titles)
        self.assertIn("Build mcp_server.py", titles)

    def test_load_tasks_detects_in_progress(self):
        tasks = load_tasks(TASKS_MD_FULL)
        statuses = {t.title: t.status for t in tasks}
        self.assertEqual(statuses["Build capture_hook.py"], TaskStatus.IN_PROGRESS)

    def test_load_tasks_detects_done(self):
        tasks = load_tasks(TASKS_MD_NO_ACTIVE)
        self.assertEqual(tasks[0].status, TaskStatus.DONE)

    def test_load_tasks_default_status_is_pending(self):
        tasks = load_tasks(TASKS_MD_FULL)
        statuses = {t.title: t.status for t in tasks}
        self.assertEqual(statuses["Build memory_store.py"], TaskStatus.PENDING)
        self.assertEqual(statuses["Build mcp_server.py"], TaskStatus.PENDING)

    def test_load_tasks_extracts_body(self):
        tasks = load_tasks(TASKS_MD_FULL)
        task2 = next(t for t in tasks if "capture_hook" in t.title)
        self.assertIn("capture_hook.py", task2.body)

    def test_load_tasks_empty_tasks_section(self):
        tasks = load_tasks(TASKS_MD_EMPTY)
        self.assertEqual(tasks, [])

    def test_load_tasks_no_tasks_header(self):
        tasks = load_tasks("# Some other document\nNo tasks here.")
        self.assertEqual(tasks, [])

    def test_load_tasks_single_task(self):
        md = "# Tasks\nStatus: APPROVED\n## Task 1 — Do thing\n- [ ] step"
        tasks = load_tasks(md)
        self.assertEqual(len(tasks), 1)


# ── extract_active_task ────────────────────────────────────────────────────────

class TestExtractActiveTask(unittest.TestCase):

    def test_returns_in_progress_task_first(self):
        tasks = load_tasks(TASKS_MD_FULL)
        active = extract_active_task(tasks)
        self.assertIsNotNone(active)
        self.assertEqual(active.title, "Build capture_hook.py")

    def test_returns_first_pending_if_no_in_progress(self):
        tasks = load_tasks(TASKS_MD_CHECKLIST)
        active = extract_active_task(tasks)
        self.assertIsNotNone(active)
        self.assertEqual(active.status, TaskStatus.PENDING)

    def test_returns_none_if_all_done(self):
        tasks = load_tasks(TASKS_MD_NO_ACTIVE)
        active = extract_active_task(tasks)
        self.assertIsNone(active)

    def test_returns_none_for_empty_task_list(self):
        active = extract_active_task([])
        self.assertIsNone(active)

    def test_prefers_in_progress_over_pending(self):
        md = """# Tasks
Status: APPROVED
## Task 1 — First
- [ ] step
## Task 2 — Second [IN PROGRESS]
- [ ] step
"""
        tasks = load_tasks(md)
        active = extract_active_task(tasks)
        self.assertEqual(active.title, "Second")


# ── check_file_in_scope ────────────────────────────────────────────────────────

class TestCheckFileInScope(unittest.TestCase):

    def test_file_mentioned_in_task_body_is_in_scope(self):
        task = Task(
            title="Build capture_hook.py",
            status=TaskStatus.IN_PROGRESS,
            body="Write `memory-system/hooks/capture_hook.py`\nAnd tests.",
        )
        self.assertTrue(check_file_in_scope("memory-system/hooks/capture_hook.py", task))

    def test_unrelated_file_is_not_in_scope(self):
        task = Task(
            title="Build capture_hook.py",
            status=TaskStatus.IN_PROGRESS,
            body="Write `memory-system/hooks/capture_hook.py`",
        )
        self.assertFalse(check_file_in_scope("agent-guard/hooks/credential_guard.py", task))

    def test_filename_only_match_counts(self):
        """File basename match is sufficient even if path differs."""
        task = Task(
            title="Build capture_hook.py",
            status=TaskStatus.IN_PROGRESS,
            body="Write capture_hook.py and wire it up.",
        )
        self.assertTrue(check_file_in_scope("memory-system/hooks/capture_hook.py", task))

    def test_empty_body_is_never_in_scope(self):
        task = Task(title="Do thing", status=TaskStatus.IN_PROGRESS, body="")
        self.assertFalse(check_file_in_scope("some_file.py", task))

    def test_test_file_matching_impl_file_is_in_scope(self):
        """test_memory_store.py is in scope when memory_store.py is mentioned."""
        task = Task(
            title="Build store",
            status=TaskStatus.IN_PROGRESS,
            body="Write `memory-system/memory_store.py`",
        )
        # test file matching the impl module is considered in scope
        self.assertTrue(check_file_in_scope("memory-system/tests/test_memory_store.py", task))

    def test_case_insensitive_match(self):
        task = Task(
            title="Build something",
            status=TaskStatus.IN_PROGRESS,
            body="Write `Memory_Store.py`",
        )
        self.assertTrue(check_file_in_scope("memory_store.py", task))


# ── check_scope_creep ──────────────────────────────────────────────────────────

class TestCheckScopeCreep(unittest.TestCase):

    def test_file_in_any_task_is_not_scope_creep(self):
        tasks = load_tasks(TASKS_MD_FULL)
        creep = check_scope_creep("memory-system/memory_store.py", tasks)
        self.assertFalse(creep)

    def test_completely_unmentioned_file_is_scope_creep(self):
        tasks = load_tasks(TASKS_MD_FULL)
        creep = check_scope_creep("some_new_module_not_in_spec.py", tasks)
        self.assertTrue(creep)

    def test_empty_task_list_means_everything_is_scope_creep(self):
        creep = check_scope_creep("any_file.py", [])
        self.assertTrue(creep)

    def test_file_from_future_task_is_not_scope_creep(self):
        """Files from future tasks are technically in-spec even if not the active task."""
        tasks = load_tasks(TASKS_MD_FULL)
        # mcp_server.py is Task 3 (future), but still in spec
        creep = check_scope_creep("memory-system/mcp_server.py", tasks)
        self.assertFalse(creep)


# ── compliance_report ──────────────────────────────────────────────────────────

class TestComplianceReport(unittest.TestCase):

    def test_no_tasks_md_returns_no_spec(self):
        result = compliance_report("some_file.py", None)
        self.assertEqual(result.status, ComplianceStatus.NO_SPEC)

    def test_unapproved_tasks_returns_not_approved(self):
        result = compliance_report("some_file.py", TASKS_MD_UNAPPROVED)
        self.assertEqual(result.status, ComplianceStatus.NOT_APPROVED)

    def test_all_done_returns_no_active_task(self):
        result = compliance_report("some_file.py", TASKS_MD_NO_ACTIVE)
        self.assertEqual(result.status, ComplianceStatus.NO_ACTIVE_TASK)

    def test_file_in_active_task_returns_compliant(self):
        result = compliance_report(
            "memory-system/hooks/capture_hook.py", TASKS_MD_FULL
        )
        self.assertEqual(result.status, ComplianceStatus.COMPLIANT)

    def test_file_in_future_task_returns_future_task_warning(self):
        result = compliance_report("memory-system/mcp_server.py", TASKS_MD_FULL)
        self.assertEqual(result.status, ComplianceStatus.FUTURE_TASK)

    def test_file_not_in_any_task_returns_scope_creep(self):
        result = compliance_report("some_unplanned_module.py", TASKS_MD_FULL)
        self.assertEqual(result.status, ComplianceStatus.SCOPE_CREEP)

    def test_result_has_message(self):
        result = compliance_report("some_unplanned_module.py", TASKS_MD_FULL)
        self.assertIsInstance(result.message, str)
        self.assertGreater(len(result.message), 0)

    def test_compliant_result_has_active_task_info(self):
        result = compliance_report(
            "memory-system/hooks/capture_hook.py", TASKS_MD_FULL
        )
        self.assertIsNotNone(result.active_task)
        self.assertIn("capture_hook", result.active_task)

    def test_scope_creep_message_contains_filename(self):
        result = compliance_report("some_unplanned_module.py", TASKS_MD_FULL)
        self.assertIn("some_unplanned_module.py", result.message)

    def test_future_task_message_names_the_task(self):
        result = compliance_report("memory-system/mcp_server.py", TASKS_MD_FULL)
        self.assertIn("mcp_server", result.message.lower())


# ── Task dataclass ────────────────────────────────────────────────────────────

class TestTaskDataclass(unittest.TestCase):

    def test_task_has_required_fields(self):
        task = Task(title="Do something", status=TaskStatus.PENDING, body="body text")
        self.assertEqual(task.title, "Do something")
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.body, "body text")

    def test_task_status_enum_values(self):
        self.assertEqual(TaskStatus.PENDING.value, "pending")
        self.assertEqual(TaskStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(TaskStatus.DONE.value, "done")

    def test_compliance_status_enum_values(self):
        statuses = {s.value for s in ComplianceStatus}
        self.assertIn("compliant", statuses)
        self.assertIn("scope_creep", statuses)
        self.assertIn("future_task", statuses)
        self.assertIn("no_spec", statuses)
        self.assertIn("not_approved", statuses)
        self.assertIn("no_active_task", statuses)


if __name__ == "__main__":
    unittest.main(verbosity=2)
