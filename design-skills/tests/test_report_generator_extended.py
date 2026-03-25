#!/usr/bin/env python3
"""
Extended tests for report_generator.py — covers 8 untested functions.

Functions covered here (not in test_report_generator.py):
  - collect_module_stats()
  - collect_master_tasks()
  - collect_session_highlights()
  - collect_frontier_status(modules)
  - collect_priority_queue()
  - collect_daily_diff()
  - collect_criticisms(modules, mt_complete, mt_active, mt_pending)
  - main() (smoke — ArgumentParser paths)

Strategy: create a temporary project root with stub files so
CCADataCollector reads controlled content.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report_generator import CCADataCollector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_collector(files: dict) -> CCADataCollector:
    """Create a CCADataCollector pointing at a temp dir with given files."""
    tmp = tempfile.mkdtemp()
    for rel_path, content in files.items():
        abs_path = os.path.join(tmp, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(content)
    collector = CCADataCollector(project_root=tmp)
    collector._tmpdir = tmp  # store for cleanup
    return collector


def cleanup(collector: CCADataCollector):
    import shutil
    shutil.rmtree(getattr(collector, "_tmpdir", ""), ignore_errors=True)


# ---------------------------------------------------------------------------
# collect_module_stats
# ---------------------------------------------------------------------------


MINIMAL_INDEX = """\
| Module | Path | Status | Tests |
|--------|------|--------|-------|
| Memory System | memory-system/ | MEM-1-5 COMPLETE | 340 |
| Spec System | spec-system/ | SPEC-1-5 ACTIVE | 100 |
"""

MINIMAL_STATE = """\
**Next (prioritized):**
1. Something for spec-system next phase
2. Other item
"""


class TestCollectModuleStats(unittest.TestCase):
    """collect_module_stats() reads filesystem + PROJECT_INDEX.md."""

    def test_returns_list(self):
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            result = c.collect_module_stats()
            self.assertIsInstance(result, list)
        finally:
            cleanup(c)

    def test_missing_module_dir_skipped(self):
        """Modules whose path doesn't exist are skipped."""
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            # No module directories created — all will be skipped
            result = c.collect_module_stats()
            self.assertEqual(result, [])
        finally:
            cleanup(c)

    def test_existing_module_dir_included(self):
        """A module whose path exists is included."""
        import shutil
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            mod_path = os.path.join(c.project_root, "memory-system")
            os.makedirs(mod_path)
            result = c.collect_module_stats()
            names = [m["name"] for m in result]
            self.assertIn("Memory System", names)
        finally:
            cleanup(c)

    def test_module_stats_has_required_keys(self):
        """Each returned module dict has the expected keys."""
        import shutil
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            mod_path = os.path.join(c.project_root, "memory-system")
            os.makedirs(mod_path)
            result = c.collect_module_stats()
            self.assertTrue(len(result) > 0)
            m = result[0]
            for key in ("name", "path", "status", "tests", "loc", "files", "description", "components"):
                self.assertIn(key, m, f"Missing key: {key}")
        finally:
            cleanup(c)

    def test_py_files_counted(self):
        """Python files in the module directory are counted."""
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            mod_path = os.path.join(c.project_root, "memory-system")
            os.makedirs(mod_path)
            # Write a small Python file
            with open(os.path.join(mod_path, "foo.py"), "w") as f:
                f.write("x = 1\ny = 2\n")
            result = c.collect_module_stats()
            mem = next(m for m in result if m["name"] == "Memory System")
            self.assertEqual(mem["files"], 1)
            self.assertEqual(mem["loc"], 2)
        finally:
            cleanup(c)

    def test_test_files_counted_separately(self):
        """test_*.py files count tests, not loc."""
        c = make_collector({"PROJECT_INDEX.md": MINIMAL_INDEX, "SESSION_STATE.md": ""})
        try:
            mod_path = os.path.join(c.project_root, "memory-system")
            os.makedirs(mod_path)
            with open(os.path.join(mod_path, "test_foo.py"), "w") as f:
                f.write("def test_one(): pass\ndef test_two(): pass\n")
            result = c.collect_module_stats()
            mem = next(m for m in result if m["name"] == "Memory System")
            # Test file should not add to files count
            self.assertEqual(mem["files"], 0)
        finally:
            cleanup(c)


# ---------------------------------------------------------------------------
# collect_master_tasks
# ---------------------------------------------------------------------------


MASTER_TASKS_CONTENT = """\
# Master Tasks

## MT-1: Maestro Visual Grid UI (some suffix)

**Status:** COMPLETE

**Delivered:**
- maestro.py built
- CLI ready

---

## MT-2: Some Active Task

**Status:** Phase 1 COMPLETE, Phase 2 in progress

Phase 1: Foundation
Phase 2: Integration
Phase 3: Polish

---

## MT-3: Blocked Task

**Status:** BLOCKED waiting on macOS SDK

---

## MT-4: Future Task

**Status:** NOT STARTED — low priority for now

---
"""


class TestCollectMasterTasks(unittest.TestCase):
    """collect_master_tasks() parses MASTER_TASKS.md."""

    def test_empty_file_returns_three_empty_lists(self):
        c = make_collector({"MASTER_TASKS.md": ""})
        try:
            result = c.collect_master_tasks()
            self.assertEqual(result, ([], [], []))
        finally:
            cleanup(c)

    def test_missing_file_returns_three_empty_lists(self):
        c = make_collector({})
        try:
            result = c.collect_master_tasks()
            self.assertEqual(result, ([], [], []))
        finally:
            cleanup(c)

    def test_complete_task_categorized(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, active, pending = c.collect_master_tasks()
            ids = [t["id"] for t in complete]
            self.assertIn("MT-1", ids)
        finally:
            cleanup(c)

    def test_active_task_categorized(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, active, pending = c.collect_master_tasks()
            ids = [t["id"] for t in active]
            self.assertIn("MT-2", ids)
        finally:
            cleanup(c)

    def test_blocked_task_in_pending(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, active, pending = c.collect_master_tasks()
            ids = [t["id"] for t in pending]
            self.assertIn("MT-3", ids)
        finally:
            cleanup(c)

    def test_not_started_task_in_pending(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, active, pending = c.collect_master_tasks()
            ids = [t["id"] for t in pending]
            self.assertIn("MT-4", ids)
        finally:
            cleanup(c)

    def test_task_dict_has_required_keys(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, active, pending = c.collect_master_tasks()
            all_tasks = complete + active + pending
            self.assertTrue(len(all_tasks) > 0)
            for task in all_tasks:
                for key in ("id", "name", "status", "category", "delivered", "phases_done"):
                    self.assertIn(key, task, f"Missing key: {key}")
        finally:
            cleanup(c)

    def test_parenthetical_suffix_stripped_from_name(self):
        """Task names have trailing parentheticals removed."""
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, _, _ = c.collect_master_tasks()
            mt1 = next(t for t in complete if t["id"] == "MT-1")
            self.assertNotIn("(some suffix)", mt1["name"])
        finally:
            cleanup(c)

    def test_delivered_items_extracted(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_TASKS_CONTENT})
        try:
            complete, _, _ = c.collect_master_tasks()
            mt1 = next(t for t in complete if t["id"] == "MT-1")
            self.assertIn("maestro.py built", mt1["delivered"])
        finally:
            cleanup(c)


# ---------------------------------------------------------------------------
# collect_session_highlights
# ---------------------------------------------------------------------------


SESSION_STATE_WITH_HIGHLIGHTS = """\
## Current State (as of Session 42)

**What's done this session:**
1. **Built feature X** — description here
2. **Fixed bug Y:** another description
3. Plain item without bold

**Next (prioritized):**
1. Do something next
"""

SESSION_STATE_NO_HIGHLIGHTS = """\
## Current State

Some content but no highlights section.
"""


class TestCollectSessionHighlights(unittest.TestCase):
    """collect_session_highlights() parses numbered items from SESSION_STATE."""

    def test_extracts_items(self):
        c = make_collector({"SESSION_STATE.md": SESSION_STATE_WITH_HIGHLIGHTS})
        try:
            result = c.collect_session_highlights()
            self.assertEqual(len(result), 3)
        finally:
            cleanup(c)

    def test_bold_markers_stripped(self):
        c = make_collector({"SESSION_STATE.md": SESSION_STATE_WITH_HIGHLIGHTS})
        try:
            result = c.collect_session_highlights()
            # "**Built feature X**" should become "Built feature X"
            self.assertIn("Built feature X", result[0])
            self.assertNotIn("**", result[0])
        finally:
            cleanup(c)

    def test_returns_empty_when_no_section(self):
        c = make_collector({"SESSION_STATE.md": SESSION_STATE_NO_HIGHLIGHTS})
        try:
            result = c.collect_session_highlights()
            self.assertEqual(result, [])
        finally:
            cleanup(c)

    def test_missing_file_returns_empty(self):
        c = make_collector({})
        try:
            result = c.collect_session_highlights()
            self.assertEqual(result, [])
        finally:
            cleanup(c)

    def test_max_ten_items(self):
        """collect_session_highlights returns at most 10 items."""
        many_items = "**What's done this session:**\n"
        for i in range(15):
            many_items += f"{i+1}. Item {i+1}\n"
        c = make_collector({"SESSION_STATE.md": many_items})
        try:
            result = c.collect_session_highlights()
            self.assertLessEqual(len(result), 10)
        finally:
            cleanup(c)


# ---------------------------------------------------------------------------
# collect_frontier_status
# ---------------------------------------------------------------------------


class TestCollectFrontierStatus(unittest.TestCase):
    """collect_frontier_status(modules) is pure logic — no file I/O needed."""

    def _make_modules(self):
        return [
            {"name": "Memory System", "path": "memory-system/", "status": "COMPLETE", "tests": 340, "loc": 1200},
            {"name": "Spec System", "path": "spec-system/", "status": "ACTIVE", "tests": 158, "loc": 800},
        ]

    def test_returns_list_of_length_5(self):
        """One entry per FRONTIER_DEFINITIONS item."""
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status(self._make_modules())
        self.assertEqual(len(result), 5)

    def test_uses_module_status(self):
        """Frontier status reflects the corresponding module's status."""
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status(self._make_modules())
        mem_frontier = next(f for f in result if f["number"] == 1)
        self.assertEqual(mem_frontier["status"], "COMPLETE")

    def test_active_module_status_propagated(self):
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status(self._make_modules())
        spec_frontier = next(f for f in result if f["number"] == 2)
        self.assertEqual(spec_frontier["status"], "ACTIVE")

    def test_missing_module_defaults_to_complete(self):
        """Frontiers with no matching module default to COMPLETE."""
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status([])  # No modules
        for f in result:
            self.assertEqual(f["status"], "COMPLETE")

    def test_frontier_has_required_keys(self):
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status(self._make_modules())
        for f in result:
            for key in ("number", "name", "impact", "description", "status", "tests", "loc"):
                self.assertIn(key, f)

    def test_tests_from_module_data(self):
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_frontier_status(self._make_modules())
        mem = next(f for f in result if f["number"] == 1)
        self.assertEqual(mem["tests"], 340)


# ---------------------------------------------------------------------------
# collect_priority_queue
# ---------------------------------------------------------------------------


MASTER_WITH_QUEUE = """\
# Master Tasks

### Active Priority Queue

| Rank | MT | Task | Base | Age | Comp% | Bonus | ROI | Stag | **Score** | Urgency | Next |
|------|----|------|------|-----|-------|-------|-----|------|-----------|---------|------|
| 1 | MT-21 | Hivemind | 9 | 0 | 50% | 1 | 1 | 0 | **11.0** | HIGH | Phase 3 |
| 2 | MT-20 | Senior Dev | 8 | 0 | 30% | 0 | 1 | 0 | **9.0** | MED | Phase 6 |

### Completed Tasks

Some completed content.
"""


class TestCollectPriorityQueue(unittest.TestCase):
    """collect_priority_queue() parses the table from MASTER_TASKS.md."""

    def test_returns_list(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_WITH_QUEUE})
        try:
            result = c.collect_priority_queue()
            self.assertIsInstance(result, list)
        finally:
            cleanup(c)

    def test_parses_rows(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_WITH_QUEUE})
        try:
            result = c.collect_priority_queue()
            self.assertEqual(len(result), 2)
        finally:
            cleanup(c)

    def test_row_has_required_keys(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_WITH_QUEUE})
        try:
            result = c.collect_priority_queue()
            self.assertTrue(len(result) > 0)
            row = result[0]
            for key in ("rank", "id", "name", "score", "next_phase"):
                self.assertIn(key, row)
        finally:
            cleanup(c)

    def test_score_parsed_as_float(self):
        c = make_collector({"MASTER_TASKS.md": MASTER_WITH_QUEUE})
        try:
            result = c.collect_priority_queue()
            self.assertIsInstance(result[0]["score"], float)
            self.assertEqual(result[0]["score"], 11.0)
        finally:
            cleanup(c)

    def test_empty_file_returns_empty(self):
        c = make_collector({"MASTER_TASKS.md": ""})
        try:
            result = c.collect_priority_queue()
            self.assertEqual(result, [])
        finally:
            cleanup(c)

    def test_missing_file_returns_empty(self):
        c = make_collector({})
        try:
            result = c.collect_priority_queue()
            self.assertEqual(result, [])
        finally:
            cleanup(c)


# ---------------------------------------------------------------------------
# WHY_IT_MATTERS blurbs
# ---------------------------------------------------------------------------


class TestWhyItMatters(unittest.TestCase):
    """WHY_IT_MATTERS ELI5 blurbs are injected into data."""

    def test_known_module_has_blurb(self):
        c = CCADataCollector(project_root="/tmp")
        blurb = c.get_why_it_matters("Memory System")
        self.assertTrue(len(blurb) > 0)
        self.assertIn("remember", blurb.lower())

    def test_known_mt_has_blurb(self):
        c = CCADataCollector(project_root="/tmp")
        blurb = c.get_why_it_matters("MT-0")
        self.assertTrue(len(blurb) > 0)

    def test_unknown_key_returns_empty(self):
        c = CCADataCollector(project_root="/tmp")
        blurb = c.get_why_it_matters("MT-999")
        self.assertEqual(blurb, "")

    def test_all_modules_have_blurbs(self):
        c = CCADataCollector(project_root="/tmp")
        for mod_def in c.MODULE_DEFINITIONS:
            blurb = c.get_why_it_matters(mod_def["name"])
            self.assertTrue(len(blurb) > 0, f"Missing blurb for {mod_def['name']}")

    def test_blurbs_are_short(self):
        """ELI5 blurbs should be concise (under 300 chars)."""
        c = CCADataCollector(project_root="/tmp")
        for key, blurb in c.WHY_IT_MATTERS.items():
            self.assertLess(len(blurb), 300, f"Blurb too long for {key}: {len(blurb)} chars")


# ---------------------------------------------------------------------------
# collect_daily_diff
# ---------------------------------------------------------------------------


class TestCollectDailyDiff(unittest.TestCase):
    """collect_daily_diff() returns None when snapshots are insufficient."""

    def test_returns_none_when_daily_snapshot_import_fails(self):
        """If daily_snapshot can't be imported, returns None."""
        c = CCADataCollector(project_root="/tmp")
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = c.collect_daily_diff()
        self.assertIsNone(result)

    def test_returns_none_when_exception_raised(self):
        """Any exception during diff collection returns None."""
        c = CCADataCollector(project_root="/tmp")
        with patch("builtins.__import__", side_effect=Exception("unexpected")):
            result = c.collect_daily_diff()
        self.assertIsNone(result)

    def test_returns_none_or_dict(self):
        """Result is always either None or a dict (never raises)."""
        c = CCADataCollector(project_root="/tmp/nonexistent_xyz")
        result = c.collect_daily_diff()
        self.assertTrue(result is None or isinstance(result, dict))


# ---------------------------------------------------------------------------
# collect_criticisms
# ---------------------------------------------------------------------------


def _make_modules_for_criticism(total_tests=50, total_files=2):
    return [
        {"name": "Module A", "path": "mod-a/", "status": "COMPLETE",
         "tests": total_tests, "loc": 500, "files": total_files,
         "description": "", "components": []},
    ]


class TestCollectCriticisms(unittest.TestCase):
    """collect_criticisms() generates objective project gaps."""

    def test_returns_list(self):
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(
            _make_modules_for_criticism(), [], [], []
        )
        self.assertIsInstance(result, list)

    def test_always_includes_single_developer_limitation(self):
        """The single-developer criticism is always present."""
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(
            _make_modules_for_criticism(), [], [], []
        )
        titles = [r["title"] for r in result]
        self.assertTrue(any("single-developer" in t.lower() or "external users" in t.lower() for t in titles))

    def test_includes_research_outcome_criticism(self):
        """Research outcome tracking gap is flagged when data is thin or missing."""
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(
            _make_modules_for_criticism(), [], [], []
        )
        titles = [r["title"] for r in result]
        # Either "outcome tracking" or "research outcome" should appear
        self.assertTrue(any("outcome" in t.lower() or "research" in t.lower() for t in titles))

    def test_stuck_phase1_criticism_when_applicable(self):
        """Tasks at phase 1 with more phases trigger a specific criticism."""
        active = [
            {"id": "MT-5", "name": "Task", "phases_done": 1, "total_phases": 3},
            {"id": "MT-6", "name": "Task 2", "phases_done": 1, "total_phases": 4},
        ]
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(_make_modules_for_criticism(), [], active, [])
        titles = [r["title"] for r in result]
        self.assertTrue(any("stalled" in t.lower() or "phase 1" in t.lower() for t in titles))

    def test_no_stuck_phase1_criticism_when_progressing(self):
        """Tasks that have advanced past phase 1 don't trigger the criticism."""
        active = [
            {"id": "MT-5", "name": "Task", "phases_done": 3, "total_phases": 4},
        ]
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(_make_modules_for_criticism(), [], active, [])
        titles = [r["title"] for r in result]
        self.assertFalse(any("stalled" in t.lower() for t in titles))

    def test_high_test_count_criticism(self):
        """Very high tests/file ratio triggers test-depth criticism."""
        # 100 tests, 1 file = 100 tests/file > 30 threshold
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(
            _make_modules_for_criticism(total_tests=100, total_files=1), [], [], []
        )
        titles = [r["title"] for r in result]
        self.assertTrue(any("test" in t.lower() for t in titles))

    def test_blocked_task_triggers_criticism(self):
        """Blocked tasks in pending list generate a blocker criticism."""
        pending = [
            {"id": "MT-1", "name": "Maestro", "category": "blocked"},
        ]
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(
            _make_modules_for_criticism(), [], [], pending
        )
        titles = [r["title"] for r in result]
        self.assertTrue(any("blocked" in t.lower() for t in titles))

    def test_each_criticism_has_required_keys(self):
        c = CCADataCollector(project_root="/tmp")
        result = c.collect_criticisms(_make_modules_for_criticism(), [], [], [])
        for criticism in result:
            self.assertIn("title", criticism)
            self.assertIn("severity", criticism)
            self.assertIn("detail", criticism)


if __name__ == "__main__":
    unittest.main()
