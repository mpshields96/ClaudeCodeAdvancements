#!/usr/bin/env python3
"""
Tests for daily_snapshot.py — Daily state snapshots for CCA progress tracking.
Run: python3 design-skills/tests/test_daily_snapshot.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import daily_snapshot as ds


class TestCountTestMethods(unittest.TestCase):
    def test_counts_test_defs(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test_foo(): pass\ndef test_bar(): pass\ndef helper(): pass\n")
            f.flush()
            self.assertEqual(ds._count_test_methods(f.name), 2)
        os.unlink(f.name)

    def test_no_tests(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def helper(): pass\nclass Foo: pass\n")
            f.flush()
            self.assertEqual(ds._count_test_methods(f.name), 0)
        os.unlink(f.name)

    def test_nonexistent_file(self):
        self.assertEqual(ds._count_test_methods("/nonexistent/path.py"), 0)

    def test_indented_test_methods(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class TestFoo:\n    def test_one(self): pass\n    def test_two(self): pass\n")
            f.flush()
            self.assertEqual(ds._count_test_methods(f.name), 2)
        os.unlink(f.name)


class TestCountPythonLoc(unittest.TestCase):
    def test_counts_non_test_files(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "module.py").write_text("line1\nline2\nline3\n")
            Path(d, "test_module.py").write_text("test1\ntest2\n")
            self.assertEqual(ds._count_python_loc(d), 3)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ds._count_python_loc(d), 0)

    def test_nonexistent_dir(self):
        self.assertEqual(ds._count_python_loc("/nonexistent/dir"), 0)

    def test_nested_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d, "sub")
            sub.mkdir()
            Path(d, "a.py").write_text("1\n2\n")
            Path(sub, "b.py").write_text("3\n4\n5\n")
            self.assertEqual(ds._count_python_loc(d), 5)


class TestReadFile(unittest.TestCase):
    def test_reads_existing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            # Need to patch PROJECT_ROOT
            with patch.object(ds, "PROJECT_ROOT", os.path.dirname(f.name)):
                result = ds._read_file(os.path.basename(f.name))
                self.assertEqual(result, "hello world")
        os.unlink(f.name)

    def test_nonexistent_returns_empty(self):
        with patch.object(ds, "PROJECT_ROOT", "/nonexistent"):
            self.assertEqual(ds._read_file("nope.txt"), "")


class TestSaveAndLoadSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_save_creates_file(self):
        snap = {"date": "2026-03-20", "totals": {"tests": 100}}
        path = ds.save_snapshot(snap, self.tmpdir)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith("2026-03-20.json"))

    def test_load_returns_saved_data(self):
        snap = {"date": "2026-03-20", "totals": {"tests": 100, "suites": 10}}
        ds.save_snapshot(snap, self.tmpdir)
        loaded = ds.load_snapshot("2026-03-20", self.tmpdir)
        self.assertEqual(loaded["totals"]["tests"], 100)
        self.assertEqual(loaded["totals"]["suites"], 10)

    def test_load_nonexistent_returns_none(self):
        self.assertIsNone(ds.load_snapshot("1999-01-01", self.tmpdir))

    def test_save_creates_dir_if_missing(self):
        subdir = os.path.join(self.tmpdir, "nested", "deep")
        snap = {"date": "2026-03-20"}
        ds.save_snapshot(snap, subdir)
        self.assertTrue(os.path.exists(os.path.join(subdir, "2026-03-20.json")))


class TestListSnapshots(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_empty_dir(self):
        self.assertEqual(ds.list_snapshots(self.tmpdir), [])

    def test_nonexistent_dir(self):
        self.assertEqual(ds.list_snapshots("/nonexistent"), [])

    def test_lists_sorted_newest_first(self):
        for d in ["2026-03-18", "2026-03-20", "2026-03-19"]:
            Path(self.tmpdir, f"{d}.json").write_text("{}")
        result = ds.list_snapshots(self.tmpdir)
        self.assertEqual(result, ["2026-03-20", "2026-03-19", "2026-03-18"])

    def test_ignores_non_json(self):
        Path(self.tmpdir, "notes.txt").write_text("hi")
        Path(self.tmpdir, "2026-03-20.json").write_text("{}")
        result = ds.list_snapshots(self.tmpdir)
        self.assertEqual(result, ["2026-03-20"])


class TestFindPreviousSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for d in ["2026-03-18", "2026-03-19", "2026-03-20"]:
            Path(self.tmpdir, f"{d}.json").write_text("{}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_finds_previous(self):
        result = ds.find_previous_snapshot("2026-03-20", self.tmpdir)
        self.assertEqual(result, "2026-03-19")

    def test_finds_two_back(self):
        result = ds.find_previous_snapshot("2026-03-19", self.tmpdir)
        self.assertEqual(result, "2026-03-18")

    def test_no_previous(self):
        result = ds.find_previous_snapshot("2026-03-18", self.tmpdir)
        self.assertIsNone(result)

    def test_no_previous_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ds.find_previous_snapshot("2026-03-20", d))


class TestDiffSnapshots(unittest.TestCase):
    def _make_snap(self, date, tests=100, suites=10, loc=500, py_files=20,
                   session=74, modules=None, test_suites=None):
        snap = {
            "date": date,
            "totals": {
                "tests": tests, "suites": suites, "loc": loc,
                "py_files": py_files, "session_number": session,
            },
            "modules": modules or {},
            "tests": {"suites": test_suites or []},
        }
        return snap

    def test_basic_totals_delta(self):
        old = self._make_snap("2026-03-19", tests=100, loc=500)
        new = self._make_snap("2026-03-20", tests=120, loc=600)
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(diff["totals_delta"]["tests"]["delta"], 20)
        self.assertEqual(diff["totals_delta"]["loc"]["delta"], 100)

    def test_no_change(self):
        old = self._make_snap("2026-03-19")
        new = self._make_snap("2026-03-20")
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(diff["totals_delta"]["tests"]["delta"], 0)

    def test_negative_delta(self):
        old = self._make_snap("2026-03-19", tests=200)
        new = self._make_snap("2026-03-20", tests=180)
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(diff["totals_delta"]["tests"]["delta"], -20)

    def test_module_deltas(self):
        old = self._make_snap("2026-03-19", modules={
            "Agent Guard": {"tests": 50, "loc": 300, "py_files": 5},
        })
        new = self._make_snap("2026-03-20", modules={
            "Agent Guard": {"tests": 60, "loc": 350, "py_files": 6},
        })
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(len(diff["module_deltas"]), 1)
        self.assertEqual(diff["module_deltas"][0]["name"], "Agent Guard")
        self.assertEqual(diff["module_deltas"][0]["tests_delta"], 10)
        self.assertEqual(diff["module_deltas"][0]["loc_delta"], 50)

    def test_new_module_shows_delta(self):
        old = self._make_snap("2026-03-19", modules={})
        new = self._make_snap("2026-03-20", modules={
            "New Module": {"tests": 30, "loc": 200, "py_files": 3},
        })
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(len(diff["module_deltas"]), 1)
        self.assertEqual(diff["module_deltas"][0]["tests_delta"], 30)

    def test_unchanged_module_excluded(self):
        mods = {"Agent Guard": {"tests": 50, "loc": 300, "py_files": 5}}
        old = self._make_snap("2026-03-19", modules=mods)
        new = self._make_snap("2026-03-20", modules=mods)
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(len(diff["module_deltas"]), 0)

    def test_new_test_suites(self):
        old = self._make_snap("2026-03-19", test_suites=[
            {"file": "tests/test_a.py", "count": 10},
        ])
        new = self._make_snap("2026-03-20", test_suites=[
            {"file": "tests/test_a.py", "count": 10},
            {"file": "tests/test_b.py", "count": 15},
        ])
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(len(diff["new_suites"]), 1)
        self.assertEqual(diff["new_suites"][0]["file"], "tests/test_b.py")
        self.assertEqual(diff["new_suites"][0]["count"], 15)

    def test_removed_test_suites(self):
        old = self._make_snap("2026-03-19", test_suites=[
            {"file": "tests/test_a.py", "count": 10},
            {"file": "tests/test_b.py", "count": 15},
        ])
        new = self._make_snap("2026-03-20", test_suites=[
            {"file": "tests/test_a.py", "count": 10},
        ])
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(len(diff["removed_suites"]), 1)
        self.assertEqual(diff["removed_suites"][0]["file"], "tests/test_b.py")

    def test_date_range(self):
        old = self._make_snap("2026-03-19")
        new = self._make_snap("2026-03-20")
        diff = ds.diff_snapshots(old, new)
        self.assertEqual(diff["date_range"]["from"], "2026-03-19")
        self.assertEqual(diff["date_range"]["to"], "2026-03-20")

    def test_empty_snapshots(self):
        diff = ds.diff_snapshots({}, {})
        self.assertEqual(diff["date_range"]["from"], "?")
        self.assertEqual(diff["totals_delta"]["tests"]["delta"], 0)


class TestFormatDiffText(unittest.TestCase):
    def _make_diff(self, test_delta=20, loc_delta=100, module_deltas=None,
                   new_suites=None, removed_suites=None):
        return {
            "date_range": {"from": "2026-03-19", "to": "2026-03-20"},
            "totals_delta": {
                "tests": {"old": 100, "new": 120, "delta": test_delta},
                "suites": {"old": 10, "new": 10, "delta": 0},
                "loc": {"old": 500, "new": 600, "delta": loc_delta},
                "py_files": {"old": 20, "new": 20, "delta": 0},
                "session_number": {"old": 73, "new": 74, "delta": 1},
            },
            "module_deltas": module_deltas or [],
            "new_suites": new_suites or [],
            "removed_suites": removed_suites or [],
        }

    def test_shows_date_range(self):
        text = ds.format_diff_text(self._make_diff())
        self.assertIn("2026-03-19 -> 2026-03-20", text)

    def test_shows_positive_deltas(self):
        text = ds.format_diff_text(self._make_diff(test_delta=20))
        self.assertIn("+20", text)

    def test_shows_negative_deltas(self):
        text = ds.format_diff_text(self._make_diff(test_delta=-5, loc_delta=-50))
        self.assertIn("-5", text)
        self.assertIn("-50", text)

    def test_no_changes_message(self):
        diff = self._make_diff(test_delta=0, loc_delta=0)
        diff["totals_delta"]["session_number"]["delta"] = 0
        text = ds.format_diff_text(diff)
        self.assertIn("No changes", text)

    def test_module_changes_shown(self):
        md = [{"name": "Agent Guard", "tests_delta": 10, "loc_delta": 50, "files_delta": 1}]
        text = ds.format_diff_text(self._make_diff(module_deltas=md))
        self.assertIn("Agent Guard", text)
        self.assertIn("+10", text)

    def test_new_suites_shown(self):
        ns = [{"file": "tests/test_new.py", "count": 25}]
        text = ds.format_diff_text(self._make_diff(new_suites=ns))
        self.assertIn("test_new.py", text)
        self.assertIn("25 tests", text)

    def test_removed_suites_shown(self):
        rs = [{"file": "tests/test_old.py"}]
        text = ds.format_diff_text(self._make_diff(removed_suites=rs))
        self.assertIn("test_old.py", text)


class TestFormatDiffMarkdown(unittest.TestCase):
    def _make_diff(self):
        return {
            "date_range": {"from": "2026-03-19", "to": "2026-03-20"},
            "totals_delta": {
                "tests": {"old": 100, "new": 120, "delta": 20},
                "suites": {"old": 10, "new": 11, "delta": 1},
                "loc": {"old": 500, "new": 600, "delta": 100},
                "py_files": {"old": 20, "new": 20, "delta": 0},
                "session_number": {"old": 73, "new": 74, "delta": 1},
            },
            "module_deltas": [
                {"name": "Agent Guard", "tests_delta": 10, "loc_delta": 50, "files_delta": 1},
            ],
            "new_suites": [
                {"file": "tests/test_new.py", "count": 25},
            ],
            "removed_suites": [],
        }

    def test_markdown_table_header(self):
        md = ds.format_diff_markdown(self._make_diff())
        self.assertIn("| Metric |", md)
        self.assertIn("| Previous |", md)
        self.assertIn("| Delta |", md)

    def test_markdown_module_changes(self):
        md = ds.format_diff_markdown(self._make_diff())
        self.assertIn("**Agent Guard**", md)

    def test_markdown_new_suites(self):
        md = ds.format_diff_markdown(self._make_diff())
        self.assertIn("`tests/test_new.py`", md)

    def test_zero_delta_excluded_from_table(self):
        md = ds.format_diff_markdown(self._make_diff())
        # py_files has delta=0, should not appear
        self.assertNotIn("Python Files", md)


class TestCaptureSnapshot(unittest.TestCase):
    """Integration test — captures a real snapshot of the CCA project."""

    def test_capture_returns_dict_with_required_keys(self):
        snap = ds.capture_snapshot("2026-03-20")
        self.assertEqual(snap["date"], "2026-03-20")
        self.assertIn("captured_at", snap)
        self.assertIn("tests", snap)
        self.assertIn("modules", snap)
        self.assertIn("totals", snap)
        self.assertIn("git", snap)

    def test_capture_finds_tests(self):
        snap = ds.capture_snapshot()
        self.assertGreater(snap["totals"]["tests"], 0)
        self.assertGreater(snap["totals"]["suites"], 0)

    def test_capture_finds_modules(self):
        snap = ds.capture_snapshot()
        self.assertGreater(len(snap["modules"]), 0)

    def test_capture_finds_loc(self):
        snap = ds.capture_snapshot()
        self.assertGreater(snap["totals"]["loc"], 0)

    def test_capture_finds_session_number(self):
        snap = ds.capture_snapshot()
        self.assertIn("session_number", snap["totals"])

    def test_test_suites_have_file_and_count(self):
        snap = ds.capture_snapshot()
        for suite in snap["tests"]["suites"]:
            self.assertIn("file", suite)
            self.assertIn("count", suite)
            self.assertGreaterEqual(suite["count"], 0)


class TestEndToEnd(unittest.TestCase):
    """Full round-trip: capture, save, load, diff."""

    def test_full_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            # Create a "yesterday" snapshot
            old = {
                "date": "2026-03-19",
                "totals": {"tests": 2900, "suites": 72, "loc": 15000,
                           "py_files": 80, "session_number": 73},
                "modules": {
                    "Agent Guard": {"tests": 400, "loc": 3000, "py_files": 10},
                },
                "tests": {"suites": [
                    {"file": "agent-guard/tests/test_bash_guard.py", "count": 50},
                ]},
            }
            ds.save_snapshot(old, d)

            # Create "today" snapshot
            new = {
                "date": "2026-03-20",
                "totals": {"tests": 2980, "suites": 74, "loc": 15500,
                           "py_files": 82, "session_number": 74},
                "modules": {
                    "Agent Guard": {"tests": 420, "loc": 3200, "py_files": 11},
                    "Design Skills": {"tests": 40, "loc": 800, "py_files": 5},
                },
                "tests": {"suites": [
                    {"file": "agent-guard/tests/test_bash_guard.py", "count": 50},
                    {"file": "design-skills/tests/test_daily_snapshot.py", "count": 30},
                ]},
            }
            ds.save_snapshot(new, d)

            # Load and diff
            loaded_old = ds.load_snapshot("2026-03-19", d)
            loaded_new = ds.load_snapshot("2026-03-20", d)
            diff = ds.diff_snapshots(loaded_old, loaded_new)

            # Verify diff
            self.assertEqual(diff["totals_delta"]["tests"]["delta"], 80)
            self.assertEqual(diff["totals_delta"]["suites"]["delta"], 2)
            self.assertEqual(len(diff["module_deltas"]), 2)
            self.assertEqual(len(diff["new_suites"]), 1)
            self.assertEqual(diff["new_suites"][0]["file"],
                           "design-skills/tests/test_daily_snapshot.py")

            # Verify formatting doesn't crash
            text = ds.format_diff_text(diff)
            self.assertIn("+80", text)
            md = ds.format_diff_markdown(diff)
            self.assertIn("| Tests |", md)


if __name__ == "__main__":
    unittest.main()
