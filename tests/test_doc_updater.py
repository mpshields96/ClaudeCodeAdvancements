#!/usr/bin/env python3
"""Tests for doc_updater.py — batch doc updates for /cca-wrap optimization.

Replaces 3-4 separate Read/Edit cycles with one subprocess call.
"""
import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from doc_updater import (
    update_session_state,
    append_changelog,
    append_learnings,
    add_to_project_index,
    batch_update,
    SessionData,
)


class TestSessionData(unittest.TestCase):
    """SessionData dataclass construction and validation."""

    def test_create_minimal(self):
        sd = SessionData(session=158, grade="B", summary="Did stuff")
        self.assertEqual(sd.session, 158)
        self.assertEqual(sd.grade, "B")
        self.assertEqual(sd.summary, "Did stuff")
        self.assertEqual(sd.wins, [])
        self.assertEqual(sd.losses, [])

    def test_create_full(self):
        sd = SessionData(
            session=158, grade="A",
            summary="Built doc updater",
            wins=["Built doc_updater.py", "Fixed color sync"],
            losses=["Spent time deliberating colors"],
            next_items=["Continue wrap optimization"],
            test_count=8970,
            test_suites=224,
            new_files=["doc_updater.py"],
            learnings=[],
            date="2026-03-24",
        )
        self.assertEqual(len(sd.wins), 2)
        self.assertEqual(sd.test_count, 8970)

    def test_from_dict(self):
        d = {"session": 158, "grade": "B", "summary": "test"}
        sd = SessionData.from_dict(d)
        self.assertEqual(sd.session, 158)

    def test_from_json_string(self):
        j = '{"session": 158, "grade": "B", "summary": "test"}'
        sd = SessionData.from_json(j)
        self.assertEqual(sd.session, 158)


class TestUpdateSessionState(unittest.TestCase):
    """SESSION_STATE.md update logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "SESSION_STATE.md")

    def _write_state(self, content):
        with open(self.state_path, "w") as f:
            f.write(content)

    def test_creates_file_if_missing(self):
        sd = SessionData(session=158, grade="B", summary="Test session")
        result = update_session_state(sd, self.state_path)
        self.assertTrue(os.path.exists(self.state_path))
        content = open(self.state_path).read()
        self.assertIn("Session 158", content)
        self.assertTrue(result)

    def test_preserves_previous_state(self):
        self._write_state("""# ClaudeCodeAdvancements — Session State

---

## Current State (as of Session 156 — 2026-03-24)

**Phase:** Session 156 COMPLETE. Did things.

**What was done this session (S156):**
- Built stuff

**Next:**
1. Build more stuff

---

## Previous State (Session 155 — 2026-03-24)

Old stuff here.
""")
        sd = SessionData(
            session=157, grade="A", summary="More things",
            wins=["Win 1"], next_items=["Next thing"],
            test_count=8959, date="2026-03-24"
        )
        update_session_state(sd, self.state_path)
        content = open(self.state_path).read()
        # New state should be at top
        self.assertIn("Session 157", content)
        # Old state should be preserved as Previous
        self.assertIn("Session 156", content)
        # Very old state should be preserved
        self.assertIn("Session 155", content)

    def test_includes_wins_and_losses(self):
        sd = SessionData(
            session=158, grade="B+",
            summary="Mixed session",
            wins=["Built doc_updater.py", "Fixed colors"],
            losses=["Slow deliberation"],
        )
        update_session_state(sd, self.state_path)
        content = open(self.state_path).read()
        self.assertIn("Built doc_updater.py", content)
        self.assertIn("Fixed colors", content)

    def test_includes_test_count(self):
        sd = SessionData(
            session=158, grade="A", summary="Tests",
            test_count=8970, test_suites=224,
        )
        update_session_state(sd, self.state_path)
        content = open(self.state_path).read()
        self.assertIn("8970", content)

    def test_includes_next_items(self):
        sd = SessionData(
            session=158, grade="B", summary="Done",
            next_items=["Fix wrap time", "Continue K2"],
        )
        update_session_state(sd, self.state_path)
        content = open(self.state_path).read()
        self.assertIn("Fix wrap time", content)

    def test_demotes_current_to_previous(self):
        self._write_state("""# ClaudeCodeAdvancements — Session State

---

## Current State (as of Session 156 — 2026-03-24)

**Phase:** S156 done.

---

## Previous State (Session 155 — 2026-03-24)

**What was done:** S155 stuff.
""")
        sd = SessionData(session=157, grade="A", summary="New work")
        update_session_state(sd, self.state_path)
        content = open(self.state_path).read()
        # Should have Current = 157, Previous = 156, Previous = 155
        self.assertIn("Current State (as of Session 157", content)
        self.assertIn("Previous State (Session 156", content)
        self.assertIn("Previous State (Session 155", content)


class TestAppendChangelog(unittest.TestCase):
    """CHANGELOG.md append logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.changelog_path = os.path.join(self.tmpdir, "CHANGELOG.md")

    def test_creates_file_if_missing(self):
        sd = SessionData(
            session=158, grade="B", summary="First entry",
            wins=["Built something"],
        )
        append_changelog(sd, self.changelog_path)
        self.assertTrue(os.path.exists(self.changelog_path))
        content = open(self.changelog_path).read()
        self.assertIn("Session 158", content)
        self.assertIn("Built something", content)

    def test_appends_to_existing(self):
        with open(self.changelog_path, "w") as f:
            f.write("# Changelog\n\n## Session 156\nOld entry\n")
        sd = SessionData(
            session=158, grade="A", summary="New entry",
            wins=["New win"], test_count=8970, test_suites=224,
        )
        append_changelog(sd, self.changelog_path)
        content = open(self.changelog_path).read()
        self.assertIn("Session 158", content)
        self.assertIn("Session 156", content)
        self.assertIn("New win", content)

    def test_includes_test_count(self):
        sd = SessionData(
            session=158, grade="B", summary="Tests",
            wins=["tests"], test_count=8970, test_suites=224,
        )
        append_changelog(sd, self.changelog_path)
        content = open(self.changelog_path).read()
        self.assertIn("8970", content)

    def test_never_overwrites(self):
        with open(self.changelog_path, "w") as f:
            f.write("# Changelog\n\nPrecious data\n")
        sd = SessionData(session=158, grade="B", summary="New")
        append_changelog(sd, self.changelog_path)
        content = open(self.changelog_path).read()
        self.assertIn("Precious data", content)

    def test_includes_date(self):
        sd = SessionData(
            session=158, grade="B", summary="Test",
            date="2026-03-24",
        )
        append_changelog(sd, self.changelog_path)
        content = open(self.changelog_path).read()
        self.assertIn("2026-03-24", content)


class TestAppendLearnings(unittest.TestCase):
    """LEARNINGS.md append logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.learnings_path = os.path.join(self.tmpdir, "LEARNINGS.md")

    def test_skips_when_no_learnings(self):
        sd = SessionData(session=158, grade="B", summary="No learnings")
        result = append_learnings(sd, self.learnings_path)
        self.assertFalse(result)
        self.assertFalse(os.path.exists(self.learnings_path))

    def test_creates_file_with_header(self):
        sd = SessionData(
            session=158, grade="B", summary="With learning",
            learnings=[{"title": "Test learning", "severity": 1,
                       "anti_pattern": "Did X", "fix": "Do Y"}],
        )
        result = append_learnings(sd, self.learnings_path)
        self.assertTrue(result)
        content = open(self.learnings_path).read()
        self.assertIn("Test learning", content)
        self.assertIn("Severity: 1", content)

    def test_appends_to_existing(self):
        with open(self.learnings_path, "w") as f:
            f.write("# Learnings\n\n### Old pattern — Severity: 2\n")
        sd = SessionData(
            session=158, grade="B", summary="New learning",
            learnings=[{"title": "New pattern", "severity": 1,
                       "anti_pattern": "Bad thing", "fix": "Good thing"}],
        )
        append_learnings(sd, self.learnings_path)
        content = open(self.learnings_path).read()
        self.assertIn("Old pattern", content)
        self.assertIn("New pattern", content)


class TestAddToProjectIndex(unittest.TestCase):
    """PROJECT_INDEX.md update logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "PROJECT_INDEX.md")

    def test_skips_when_no_new_files(self):
        sd = SessionData(session=158, grade="B", summary="No files")
        result = add_to_project_index(sd, self.index_path)
        self.assertFalse(result)

    def test_appends_new_file_entries(self):
        with open(self.index_path, "w") as f:
            f.write("# Project Index\n\nExisting content\n")
        sd = SessionData(
            session=158, grade="B", summary="New file",
            new_files=[("doc_updater.py", "Batch doc updates for wrap optimization")],
        )
        result = add_to_project_index(sd, self.index_path)
        self.assertTrue(result)
        content = open(self.index_path).read()
        self.assertIn("doc_updater.py", content)

    def test_handles_string_files(self):
        """When new_files are just strings (no description)."""
        with open(self.index_path, "w") as f:
            f.write("# Project Index\n\nExisting content\n")
        sd = SessionData(
            session=158, grade="B", summary="New file",
            new_files=["doc_updater.py"],
        )
        result = add_to_project_index(sd, self.index_path)
        self.assertTrue(result)
        content = open(self.index_path).read()
        self.assertIn("doc_updater.py", content)


class TestBatchUpdate(unittest.TestCase):
    """End-to-end batch update."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.paths = {
            "session_state": os.path.join(self.tmpdir, "SESSION_STATE.md"),
            "changelog": os.path.join(self.tmpdir, "CHANGELOG.md"),
            "learnings": os.path.join(self.tmpdir, "LEARNINGS.md"),
            "project_index": os.path.join(self.tmpdir, "PROJECT_INDEX.md"),
        }
        # Create minimal existing files
        with open(self.paths["session_state"], "w") as f:
            f.write("# Session State\n\n## Current State (as of Session 156 — 2026-03-24)\n\nOld state.\n")
        with open(self.paths["changelog"], "w") as f:
            f.write("# Changelog\n")
        with open(self.paths["project_index"], "w") as f:
            f.write("# Project Index\n")

    def test_updates_all_docs(self):
        sd = SessionData(
            session=158, grade="A", summary="Full batch test",
            wins=["Win 1", "Win 2"], losses=["Loss 1"],
            next_items=["Next 1"], test_count=8970, test_suites=224,
            date="2026-03-24",
        )
        results = batch_update(sd, self.paths)
        self.assertTrue(results["session_state"])
        self.assertTrue(results["changelog"])
        self.assertFalse(results["learnings"])  # no learnings provided
        self.assertFalse(results["project_index"])  # no new files

    def test_returns_summary(self):
        sd = SessionData(
            session=158, grade="B", summary="Summary test",
            wins=["Win"],
        )
        results = batch_update(sd, self.paths)
        self.assertIn("session_state", results)
        self.assertIn("changelog", results)

    def test_from_json_cli(self):
        """Simulate CLI usage with JSON input."""
        data = {
            "session": 158, "grade": "A",
            "summary": "CLI test",
            "wins": ["CLI win"],
            "test_count": 8970,
            "test_suites": 224,
        }
        sd = SessionData.from_dict(data)
        results = batch_update(sd, self.paths)
        self.assertTrue(results["session_state"])

    def test_idempotent_on_failure(self):
        """If one doc update fails, others should still succeed."""
        sd = SessionData(session=158, grade="B", summary="Partial")
        # Make changelog read-only to simulate failure
        with open(self.paths["changelog"], "w") as f:
            f.write("# CL\n")
        os.chmod(self.paths["changelog"], 0o444)
        try:
            results = batch_update(sd, self.paths)
            # session_state should still succeed
            self.assertTrue(results["session_state"])
        finally:
            os.chmod(self.paths["changelog"], 0o644)


if __name__ == "__main__":
    unittest.main()
