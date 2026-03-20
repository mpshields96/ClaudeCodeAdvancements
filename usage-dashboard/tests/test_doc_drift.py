#!/usr/bin/env python3
"""Tests for doc_drift_checker.py — Automated doc accuracy verification.

Verifies that PROJECT_INDEX.md and ROADMAP.md test counts, module lists,
and file paths match the actual codebase state.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParseProjectIndex(unittest.TestCase):
    """Test parsing claimed test counts from PROJECT_INDEX.md."""

    def test_parse_module_test_counts(self):
        from doc_drift_checker import parse_module_test_counts
        content = textwrap.dedent("""\
            ## Module Map

            | Module | Path | Status | Tests |
            |--------|------|--------|-------|
            | Memory System | `memory-system/` | COMPLETE | 228 |
            | Spec System | `spec-system/` | COMPLETE | 158 |
            | Context Monitor | `context-monitor/` | CTX-1-7 | 266 |
        """)
        result = parse_module_test_counts(content)
        self.assertEqual(result["memory-system"], 228)
        self.assertEqual(result["spec-system"], 158)
        self.assertEqual(result["context-monitor"], 266)

    def test_parse_total_test_count(self):
        from doc_drift_checker import parse_total_test_count
        content = "**Total: 2279 tests (54 suites). All must pass before any work.**"
        result = parse_total_test_count(content)
        self.assertEqual(result, 2279)

    def test_parse_total_test_count_missing(self):
        from doc_drift_checker import parse_total_test_count
        content = "No total line here."
        result = parse_total_test_count(content)
        self.assertIsNone(result)

    def test_parse_module_test_counts_empty(self):
        from doc_drift_checker import parse_module_test_counts
        result = parse_module_test_counts("No table here.")
        self.assertEqual(result, {})

    def test_parse_module_test_counts_handles_extra_columns(self):
        from doc_drift_checker import parse_module_test_counts
        content = textwrap.dedent("""\
            | Module | Path | Status | Tests |
            |--------|------|--------|-------|
            | Agent Guard | `agent-guard/` | AG-1-9 + Edit Guard + Bash Guard | 378 |
        """)
        result = parse_module_test_counts(content)
        self.assertEqual(result["agent-guard"], 378)


class TestParseRoadmap(unittest.TestCase):
    """Test parsing claimed counts from ROADMAP.md."""

    def test_parse_roadmap_test_table(self):
        from doc_drift_checker import parse_roadmap_test_table
        content = textwrap.dedent("""\
            ## Total Test Coverage

            | Module | Tests |
            |--------|-------|
            | memory-system | 229 |
            | spec-system | 153 |
            | context-monitor | 266 |
            | **Total** | **2260** |
        """)
        result = parse_roadmap_test_table(content)
        self.assertEqual(result["memory-system"], 229)
        self.assertEqual(result["spec-system"], 153)
        self.assertEqual(result["context-monitor"], 266)
        self.assertNotIn("**Total**", result)

    def test_parse_roadmap_total(self):
        from doc_drift_checker import parse_roadmap_total
        content = "| **Total** | **2260** |"
        result = parse_roadmap_total(content)
        self.assertEqual(result, 2260)

    def test_parse_roadmap_total_missing(self):
        from doc_drift_checker import parse_roadmap_total
        result = parse_roadmap_total("no total here")
        self.assertIsNone(result)


class TestCountActualTests(unittest.TestCase):
    """Test counting actual test methods in test files."""

    def test_count_tests_in_file(self):
        from doc_drift_checker import count_tests_in_file
        content = textwrap.dedent("""\
            import unittest

            class TestFoo(unittest.TestCase):
                def test_one(self):
                    pass
                def test_two(self):
                    pass
                def helper_not_a_test(self):
                    pass

            class TestBar(unittest.TestCase):
                def test_three(self):
                    pass
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            try:
                result = count_tests_in_file(f.name)
                self.assertEqual(result, 3)
            finally:
                os.unlink(f.name)

    def test_count_tests_empty_file(self):
        from doc_drift_checker import count_tests_in_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# empty\n")
            f.flush()
            try:
                result = count_tests_in_file(f.name)
                self.assertEqual(result, 0)
            finally:
                os.unlink(f.name)

    def test_count_tests_syntax_error(self):
        from doc_drift_checker import count_tests_in_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")
            f.flush()
            try:
                result = count_tests_in_file(f.name)
                self.assertEqual(result, 0)
            finally:
                os.unlink(f.name)


class TestCountModuleTests(unittest.TestCase):
    """Test counting all tests in a module directory."""

    def test_count_module_with_tests_dir(self):
        from doc_drift_checker import count_module_tests
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_foo.py").write_text(textwrap.dedent("""\
                import unittest
                class TestFoo(unittest.TestCase):
                    def test_a(self): pass
                    def test_b(self): pass
            """))
            (tests_dir / "test_bar.py").write_text(textwrap.dedent("""\
                import unittest
                class TestBar(unittest.TestCase):
                    def test_c(self): pass
            """))
            # Non-test file should be ignored
            (tests_dir / "helper.py").write_text("x = 1\n")
            result = count_module_tests(Path(tmpdir))
            self.assertEqual(result, 3)

    def test_count_module_no_tests_dir(self):
        from doc_drift_checker import count_module_tests
        with tempfile.TemporaryDirectory() as tmpdir:
            result = count_module_tests(Path(tmpdir))
            self.assertEqual(result, 0)


class TestCheckFilePaths(unittest.TestCase):
    """Test verifying that file paths mentioned in docs actually exist."""

    def test_extract_backtick_paths(self):
        from doc_drift_checker import extract_backtick_paths
        content = textwrap.dedent("""\
            - `hooks/capture_hook.py` — PostToolUse + Stop capture
            - `memory_store.py` — SQLite+FTS5 storage backend
            - `cli.py` — CLI viewer
        """)
        result = extract_backtick_paths(content)
        self.assertIn("hooks/capture_hook.py", result)
        self.assertIn("memory_store.py", result)
        self.assertIn("cli.py", result)

    def test_extract_backtick_paths_ignores_non_files(self):
        from doc_drift_checker import extract_backtick_paths
        content = textwrap.dedent("""\
            - `memory-system/` — Module directory
            - `COMPLETE` — just a word
            - `/spec:requirements` — slash command
            - `hooks/capture_hook.py` — real file
        """)
        result = extract_backtick_paths(content)
        # Should include .py files
        self.assertIn("hooks/capture_hook.py", result)
        # Should not include directories, status words, or commands
        self.assertNotIn("memory-system/", result)
        self.assertNotIn("COMPLETE", result)
        self.assertNotIn("/spec:requirements", result)

    def test_check_paths_exist(self):
        from doc_drift_checker import check_paths_exist
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "real.py").write_text("x = 1\n")
            existing, missing = check_paths_exist(
                ["real.py", "fake.py"], Path(tmpdir)
            )
            self.assertEqual(existing, ["real.py"])
            self.assertEqual(missing, ["fake.py"])


class TestDriftReport(unittest.TestCase):
    """Test the drift report generation."""

    def test_no_drift(self):
        from doc_drift_checker import DriftReport
        report = DriftReport()
        self.assertFalse(report.has_drift)

    def test_test_count_mismatch(self):
        from doc_drift_checker import DriftReport, TestCountMismatch
        report = DriftReport()
        report.test_mismatches.append(
            TestCountMismatch(
                source="PROJECT_INDEX.md",
                module="memory-system",
                claimed=228,
                actual=230,
            )
        )
        self.assertTrue(report.has_drift)

    def test_missing_file_drift(self):
        from doc_drift_checker import DriftReport
        report = DriftReport()
        report.missing_files.append("memory-system/nonexistent.py")
        self.assertTrue(report.has_drift)

    def test_format_report_clean(self):
        from doc_drift_checker import DriftReport
        report = DriftReport()
        text = report.format()
        self.assertIn("No drift detected", text)

    def test_format_report_with_issues(self):
        from doc_drift_checker import DriftReport, TestCountMismatch
        report = DriftReport()
        report.test_mismatches.append(
            TestCountMismatch("PROJECT_INDEX.md", "memory-system", 228, 235)
        )
        report.missing_files.append("spec-system/missing.py")
        text = report.format()
        self.assertIn("memory-system", text)
        self.assertIn("228", text)
        self.assertIn("235", text)
        self.assertIn("missing.py", text)


class TestParseProjectIndexFilePaths(unittest.TestCase):
    """Test extracting module-specific file paths from PROJECT_INDEX.md."""

    def test_extract_module_files(self):
        from doc_drift_checker import extract_module_files
        content = textwrap.dedent("""\
            **memory-system/** --- Persistent cross-session memory
            - `hooks/capture_hook.py` --- PostToolUse + Stop capture
            - `mcp_server.py` --- MCP server for memory queries
            - `memory_store.py` --- SQLite+FTS5 storage

            **spec-system/** --- Spec-driven development workflow
            - `commands/` --- Slash commands
            - `hooks/validate.py` --- PreToolUse spec guard
        """).replace("---", "\u2014")
        result = extract_module_files(content)
        self.assertIn("memory-system", result)
        self.assertIn("hooks/capture_hook.py", result["memory-system"])
        self.assertIn("mcp_server.py", result["memory-system"])
        self.assertIn("spec-system", result)
        self.assertIn("hooks/validate.py", result["spec-system"])


class TestSuiteCountFromOutput(unittest.TestCase):
    """Test extracting suite count from PROJECT_INDEX.md."""

    def test_parse_suite_count(self):
        from doc_drift_checker import parse_suite_count
        content = "**Total: 2279 tests (54 suites). All must pass before any work.**"
        result = parse_suite_count(content)
        self.assertEqual(result, 54)

    def test_parse_suite_count_missing(self):
        from doc_drift_checker import parse_suite_count
        result = parse_suite_count("no suite count")
        self.assertIsNone(result)


class TestCountActualSuites(unittest.TestCase):
    """Test counting actual test suite files."""

    def test_count_suites(self):
        from doc_drift_checker import count_test_suites
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = Path(tmpdir) / "mod" / "tests"
            mod.mkdir(parents=True)
            (mod / "test_a.py").write_text("pass\n")
            (mod / "test_b.py").write_text("pass\n")
            (mod / "helper.py").write_text("pass\n")  # not a test
            result = count_test_suites(Path(tmpdir), ["mod"])
            self.assertEqual(result, 2)


class TestRunCheck(unittest.TestCase):
    """Test the full drift check orchestration."""

    def test_run_with_mock_project(self):
        from doc_drift_checker import run_drift_check
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create PROJECT_INDEX.md
            (root / "PROJECT_INDEX.md").write_text(textwrap.dedent("""\
                ## Module Map

                | Module | Path | Status | Tests |
                |--------|------|--------|-------|
                | Test Module | `test-mod/` | COMPLETE | 5 |

                **Total: 5 tests (1 suites). All must pass.**

                **test-mod/** — Test module
                - `main.py` — main file
            """))
            # Create ROADMAP.md
            (root / "ROADMAP.md").write_text(textwrap.dedent("""\
                ## Total Test Coverage

                | Module | Tests |
                |--------|-------|
                | test-mod | 5 |
                | **Total** | **5** |
            """))
            # Create module with actual tests
            mod_dir = root / "test-mod"
            mod_dir.mkdir()
            tests_dir = mod_dir / "tests"
            tests_dir.mkdir()
            (mod_dir / "main.py").write_text("x = 1\n")
            (tests_dir / "test_main.py").write_text(textwrap.dedent("""\
                import unittest
                class TestMain(unittest.TestCase):
                    def test_1(self): pass
                    def test_2(self): pass
                    def test_3(self): pass
                    def test_4(self): pass
                    def test_5(self): pass
            """))

            report = run_drift_check(root, ["test-mod"])
            self.assertFalse(report.has_drift)

    def test_run_detects_count_mismatch(self):
        from doc_drift_checker import run_drift_check
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "PROJECT_INDEX.md").write_text(textwrap.dedent("""\
                ## Module Map

                | Module | Path | Status | Tests |
                |--------|------|--------|-------|
                | Test Module | `test-mod/` | COMPLETE | 10 |

                **Total: 10 tests (1 suites). All must pass.**
            """))
            (root / "ROADMAP.md").write_text("")
            mod_dir = root / "test-mod"
            mod_dir.mkdir()
            tests_dir = mod_dir / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_main.py").write_text(textwrap.dedent("""\
                import unittest
                class TestMain(unittest.TestCase):
                    def test_1(self): pass
                    def test_2(self): pass
            """))

            report = run_drift_check(root, ["test-mod"])
            self.assertTrue(report.has_drift)
            self.assertTrue(len(report.test_mismatches) > 0)


class TestJsonOutput(unittest.TestCase):
    """Test JSON output mode."""

    def test_json_serializable(self):
        from doc_drift_checker import DriftReport, TestCountMismatch
        report = DriftReport()
        report.test_mismatches.append(
            TestCountMismatch("PROJECT_INDEX.md", "memory-system", 228, 235)
        )
        report.missing_files.append("fake.py")
        data = report.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(data)
        self.assertIn("memory-system", json_str)
        self.assertIn("fake.py", json_str)

    def test_json_has_expected_fields(self):
        from doc_drift_checker import DriftReport
        report = DriftReport()
        data = report.to_dict()
        self.assertIn("has_drift", data)
        self.assertIn("test_mismatches", data)
        self.assertIn("missing_files", data)
        self.assertIn("total_claimed", data)
        self.assertIn("total_actual", data)


class TestTopLevelTestPaths(unittest.TestCase):
    """Test handling of test files in the top-level tests/ directory."""

    def test_count_includes_toplevel_tests(self):
        from doc_drift_checker import count_test_suites
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Module tests
            mod_tests = root / "mod" / "tests"
            mod_tests.mkdir(parents=True)
            (mod_tests / "test_a.py").write_text("pass\n")
            # Top-level tests
            top_tests = root / "tests"
            top_tests.mkdir()
            (top_tests / "test_b.py").write_text("pass\n")
            (top_tests / "test_c.py").write_text("pass\n")
            result = count_test_suites(root, ["mod"])
            self.assertEqual(result, 3)


class TestRootModuleFilePaths(unittest.TestCase):
    """Test that 'root' module files are checked at project root, not root/ subdir."""

    def test_root_module_files_found_at_project_root(self):
        """Files documented under **root/** should be checked at project root."""
        from doc_drift_checker import run_drift_check
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create PROJECT_INDEX.md with a root module section
            (root / "PROJECT_INDEX.md").write_text(textwrap.dedent("""\
                ## Module Map

                | Module | Path | Status | Tests |
                |--------|------|--------|-------|

                **Total: 0 tests (0 suites). All must pass.**

                **root/** \u2014 Root-level coordination
                - `resume_generator.py` \u2014 auto-generate resume
                - `cca_comm.py` \u2014 communication helper
            """))
            (root / "ROADMAP.md").write_text("")
            # Create the files at project root (NOT in root/ subdir)
            (root / "resume_generator.py").write_text("x = 1\n")
            (root / "cca_comm.py").write_text("x = 1\n")

            report = run_drift_check(root, [])
            # Should NOT report these as missing
            missing_names = [os.path.basename(m) for m in report.missing_files]
            self.assertNotIn("resume_generator.py", missing_names)
            self.assertNotIn("cca_comm.py", missing_names)

    def test_root_module_missing_file_detected(self):
        """Files documented under root/ that don't exist should still be reported."""
        from doc_drift_checker import run_drift_check
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "PROJECT_INDEX.md").write_text(textwrap.dedent("""\
                ## Module Map

                | Module | Path | Status | Tests |
                |--------|------|--------|-------|

                **Total: 0 tests (0 suites). All must pass.**

                **root/** \u2014 Root-level coordination
                - `actually_missing.py` \u2014 does not exist
            """))
            (root / "ROADMAP.md").write_text("")

            report = run_drift_check(root, [])
            missing_names = [os.path.basename(m) for m in report.missing_files]
            self.assertIn("actually_missing.py", missing_names)


if __name__ == "__main__":
    unittest.main()
