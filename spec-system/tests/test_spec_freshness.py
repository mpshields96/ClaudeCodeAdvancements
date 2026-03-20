#!/usr/bin/env python3
"""
Tests for spec_freshness.py — Spec Rot / Staleness Detector (Frontier 2).

Detects when spec files (requirements.md, design.md, tasks.md) have become
stale relative to the code they describe. Prevents the "two conflicting
sources of truth" problem identified in community research.

Run: python3 spec-system/tests/test_spec_freshness.py
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import spec_freshness as sf


class TestSpecFileDetection(unittest.TestCase):
    """Detect which spec files exist in a directory."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_finds_all_three_specs(self):
        for name in ["requirements.md", "design.md", "tasks.md"]:
            Path(self.tmpdir, name).write_text(f"# {name}\nStatus: APPROVED\n")
        specs = sf.find_spec_files(self.tmpdir)
        self.assertEqual(len(specs), 3)

    def test_finds_partial_specs(self):
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")
        specs = sf.find_spec_files(self.tmpdir)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "requirements.md")

    def test_no_specs_empty_list(self):
        specs = sf.find_spec_files(self.tmpdir)
        self.assertEqual(specs, [])

    def test_ignores_non_spec_md(self):
        Path(self.tmpdir, "README.md").write_text("# Readme\n")
        Path(self.tmpdir, "CHANGELOG.md").write_text("# Log\n")
        specs = sf.find_spec_files(self.tmpdir)
        self.assertEqual(specs, [])


class TestCodeFileDetection(unittest.TestCase):
    """Find code files in a directory tree."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_finds_python_files(self):
        Path(self.tmpdir, "main.py").write_text("print('hello')\n")
        Path(self.tmpdir, "utils.py").write_text("def foo(): pass\n")
        code_files = sf.find_code_files(self.tmpdir)
        self.assertEqual(len(code_files), 2)

    def test_finds_nested_code(self):
        sub = Path(self.tmpdir, "src")
        sub.mkdir()
        Path(sub, "app.py").write_text("pass\n")
        code_files = sf.find_code_files(self.tmpdir)
        self.assertEqual(len(code_files), 1)

    def test_ignores_test_files(self):
        Path(self.tmpdir, "test_main.py").write_text("pass\n")
        Path(self.tmpdir, "main.py").write_text("pass\n")
        code_files = sf.find_code_files(self.tmpdir)
        self.assertEqual(len(code_files), 1)
        self.assertEqual(code_files[0].name, "main.py")

    def test_ignores_non_code_files(self):
        Path(self.tmpdir, "notes.md").write_text("# notes\n")
        Path(self.tmpdir, "config.json").write_text("{}\n")
        code_files = sf.find_code_files(self.tmpdir)
        self.assertEqual(code_files, [])

    def test_no_files_empty_list(self):
        code_files = sf.find_code_files(self.tmpdir)
        self.assertEqual(code_files, [])


class TestFreshnessScore(unittest.TestCase):
    """Compute freshness of a spec relative to code files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_fresh_when_spec_newer_than_code(self):
        code = Path(self.tmpdir, "main.py")
        code.write_text("pass\n")
        time.sleep(0.05)
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\n")

        result = sf.check_freshness(spec, [code])
        self.assertEqual(result["status"], "FRESH")

    def test_stale_when_code_newer_than_spec(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\n")
        time.sleep(0.05)
        code = Path(self.tmpdir, "main.py")
        code.write_text("pass\n")

        result = sf.check_freshness(spec, [code])
        self.assertEqual(result["status"], "STALE")

    def test_stale_count_tracks_newer_files(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\n")
        time.sleep(0.05)
        Path(self.tmpdir, "a.py").write_text("pass\n")
        Path(self.tmpdir, "b.py").write_text("pass\n")

        result = sf.check_freshness(
            spec,
            [Path(self.tmpdir, "a.py"), Path(self.tmpdir, "b.py")]
        )
        self.assertEqual(result["newer_code_files"], 2)

    def test_no_code_files_is_fresh(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\n")

        result = sf.check_freshness(spec, [])
        self.assertEqual(result["status"], "FRESH")

    def test_result_has_required_fields(self):
        spec = Path(self.tmpdir, "design.md")
        spec.write_text("# Design\n")
        code = Path(self.tmpdir, "main.py")
        code.write_text("pass\n")

        result = sf.check_freshness(spec, [code])
        self.assertIn("spec_file", result)
        self.assertIn("status", result)
        self.assertIn("newer_code_files", result)
        self.assertIn("spec_mtime", result)
        self.assertIn("newest_code_mtime", result)


class TestRetiredDetection(unittest.TestCase):
    """Detect if a spec has been explicitly retired."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_retired_marker_detected(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\nStatus: RETIRED\n")
        self.assertTrue(sf.is_retired(spec))

    def test_approved_not_retired(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\nStatus: APPROVED\n")
        self.assertFalse(sf.is_retired(spec))

    def test_no_status_not_retired(self):
        spec = Path(self.tmpdir, "requirements.md")
        spec.write_text("# Requirements\nSome content\n")
        self.assertFalse(sf.is_retired(spec))


class TestProjectFreshness(unittest.TestCase):
    """Full project freshness report."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_report_with_all_fresh(self):
        Path(self.tmpdir, "main.py").write_text("pass\n")
        time.sleep(0.05)
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")
        Path(self.tmpdir, "design.md").write_text("# Design\n")

        report = sf.project_freshness(self.tmpdir)
        self.assertEqual(report["summary"], "FRESH")
        self.assertEqual(len(report["specs"]), 2)

    def test_report_with_stale(self):
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")
        time.sleep(0.05)
        Path(self.tmpdir, "main.py").write_text("pass\n")

        report = sf.project_freshness(self.tmpdir)
        self.assertEqual(report["summary"], "STALE")

    def test_report_no_specs_is_none(self):
        Path(self.tmpdir, "main.py").write_text("pass\n")
        report = sf.project_freshness(self.tmpdir)
        self.assertEqual(report["summary"], "NO_SPECS")

    def test_retired_specs_excluded_from_staleness(self):
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\nStatus: RETIRED\n")
        time.sleep(0.05)
        Path(self.tmpdir, "main.py").write_text("pass\n")

        report = sf.project_freshness(self.tmpdir)
        # Retired specs don't count toward staleness
        self.assertEqual(report["summary"], "NO_SPECS")

    def test_report_has_directory(self):
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")
        report = sf.project_freshness(self.tmpdir)
        self.assertEqual(report["directory"], self.tmpdir)


class TestHumanReport(unittest.TestCase):
    """Test human-readable report generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_fresh_report(self):
        Path(self.tmpdir, "main.py").write_text("pass\n")
        time.sleep(0.05)
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")

        text = sf.freshness_report(self.tmpdir)
        self.assertIn("FRESH", text)

    def test_stale_report_includes_file_names(self):
        Path(self.tmpdir, "requirements.md").write_text("# Requirements\n")
        time.sleep(0.05)
        Path(self.tmpdir, "main.py").write_text("pass\n")

        text = sf.freshness_report(self.tmpdir)
        self.assertIn("STALE", text)
        self.assertIn("requirements.md", text)

    def test_no_specs_report(self):
        text = sf.freshness_report(self.tmpdir)
        self.assertIn("NO_SPECS", text)


if __name__ == "__main__":
    unittest.main()
