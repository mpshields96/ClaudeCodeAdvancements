#!/usr/bin/env python3
"""Tests for doc_drift_checker.py — documentation accuracy verification."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doc_drift_checker import (
    TestCountMismatch,
    DriftReport,
    parse_module_test_counts,
    parse_total_test_count,
    parse_suite_count,
    parse_roadmap_test_table,
    parse_roadmap_total,
    count_tests_in_file,
    count_module_tests,
    count_test_suites,
    extract_backtick_paths,
    extract_module_files,
    check_paths_exist,
    run_drift_check,
    find_project_root,
    DEFAULT_MODULES,
)


class TestParseModuleTestCounts(unittest.TestCase):
    """Test parsing module test counts from PROJECT_INDEX.md table."""

    def test_parses_standard_row(self):
        content = "| Memory System | `memory-system/` | MEM-1-5 | 340 |"
        result = parse_module_test_counts(content)
        self.assertEqual(result["memory-system"], 340)

    def test_parses_multiple_rows(self):
        content = (
            "| Memory System | `memory-system/` | COMPLETE | 340 |\n"
            "| Spec System | `spec-system/` | SPEC-1-6 | 158 |\n"
            "| Agent Guard | `agent-guard/` | AG-1-9 | 893 |"
        )
        result = parse_module_test_counts(content)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["memory-system"], 340)
        self.assertEqual(result["spec-system"], 158)
        self.assertEqual(result["agent-guard"], 893)

    def test_ignores_non_table_lines(self):
        content = "Some random text\n**Total: 4000 tests**\n| header | header |"
        result = parse_module_test_counts(content)
        self.assertEqual(len(result), 0)

    def test_empty_content(self):
        result = parse_module_test_counts("")
        self.assertEqual(len(result), 0)


class TestParseTotalTestCount(unittest.TestCase):
    """Test parsing total test count."""

    def test_parses_standard_format(self):
        content = "**Total: 4130 tests (104 suites). All must pass.**"
        result = parse_total_test_count(content)
        self.assertEqual(result, 4130)

    def test_parses_tilde_format(self):
        content = "**Total: ~4130 tests (104 suites).**"
        result = parse_total_test_count(content)
        self.assertEqual(result, 4130)

    def test_parses_without_tilde(self):
        content = "**Total: 4050 tests (103 suites).**"
        result = parse_total_test_count(content)
        self.assertEqual(result, 4050)

    def test_returns_none_if_not_found(self):
        result = parse_total_test_count("No total here")
        self.assertIsNone(result)

    def test_empty_content(self):
        result = parse_total_test_count("")
        self.assertIsNone(result)


class TestParseSuiteCount(unittest.TestCase):
    """Test parsing suite count."""

    def test_parses_standard_format(self):
        content = "**Total: ~4130 tests (104 suites). All must pass.**"
        result = parse_suite_count(content)
        self.assertEqual(result, 104)

    def test_parses_singular(self):
        content = "(1 suite)"
        result = parse_suite_count(content)
        self.assertEqual(result, 1)

    def test_returns_none_if_not_found(self):
        result = parse_suite_count("No suites here")
        self.assertIsNone(result)


class TestParseRoadmapTestTable(unittest.TestCase):
    """Test parsing ROADMAP.md test table."""

    def test_parses_standard_row(self):
        content = "| memory-system | 229 |"
        result = parse_roadmap_test_table(content)
        self.assertEqual(result["memory-system"], 229)

    def test_skips_bold_total(self):
        content = (
            "| memory-system | 229 |\n"
            "| **Total** | **2260** |"
        )
        result = parse_roadmap_test_table(content)
        self.assertNotIn("**Total**", result)
        self.assertEqual(len(result), 1)

    def test_empty_content(self):
        result = parse_roadmap_test_table("")
        self.assertEqual(len(result), 0)


class TestParseRoadmapTotal(unittest.TestCase):
    """Test parsing ROADMAP.md total row."""

    def test_parses_bold_total(self):
        content = "| **Total** | **2260** |"
        result = parse_roadmap_total(content)
        self.assertEqual(result, 2260)

    def test_returns_none_if_not_found(self):
        result = parse_roadmap_total("No total here")
        self.assertIsNone(result)


class TestCountTestsInFile(unittest.TestCase):
    """Test AST-based test method counting."""

    def test_counts_test_methods(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                "import unittest\n"
                "class TestFoo(unittest.TestCase):\n"
                "    def test_one(self): pass\n"
                "    def test_two(self): pass\n"
                "    def helper(self): pass\n"
            )
            f.flush()
            self.assertEqual(count_tests_in_file(f.name), 2)
            os.unlink(f.name)

    def test_counts_async_test_methods(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                "class TestAsync:\n"
                "    async def test_async_one(self): pass\n"
                "    def test_sync_one(self): pass\n"
            )
            f.flush()
            self.assertEqual(count_tests_in_file(f.name), 2)
            os.unlink(f.name)

    def test_zero_for_no_tests(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def helper(): pass\ndef main(): pass\n")
            f.flush()
            self.assertEqual(count_tests_in_file(f.name), 0)
            os.unlink(f.name)

    def test_zero_for_missing_file(self):
        self.assertEqual(count_tests_in_file("/nonexistent/file.py"), 0)

    def test_zero_for_syntax_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(:\n")
            f.flush()
            self.assertEqual(count_tests_in_file(f.name), 0)
            os.unlink(f.name)

    def test_counts_standalone_test_functions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test_standalone(): pass\ndef test_another(): pass\n")
            f.flush()
            self.assertEqual(count_tests_in_file(f.name), 2)
            os.unlink(f.name)


class TestCountModuleTests(unittest.TestCase):
    """Test counting tests in a module directory."""

    def test_counts_tests_in_tests_dir(self):
        with tempfile.TemporaryDirectory() as td:
            tests_dir = Path(td) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_foo.py").write_text(
                "def test_one(): pass\ndef test_two(): pass\n"
            )
            self.assertEqual(count_module_tests(Path(td)), 2)

    def test_zero_if_no_tests_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(count_module_tests(Path(td)), 0)

    def test_ignores_non_test_files(self):
        with tempfile.TemporaryDirectory() as td:
            tests_dir = Path(td) / "tests"
            tests_dir.mkdir()
            (tests_dir / "helper.py").write_text("def test_hidden(): pass\n")
            self.assertEqual(count_module_tests(Path(td)), 0)

    def test_multiple_test_files(self):
        with tempfile.TemporaryDirectory() as td:
            tests_dir = Path(td) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("def test_1(): pass\n")
            (tests_dir / "test_b.py").write_text("def test_2(): pass\ndef test_3(): pass\n")
            self.assertEqual(count_module_tests(Path(td)), 3)


class TestCountTestSuites(unittest.TestCase):
    """Test counting test suite files."""

    def test_counts_suites(self):
        with tempfile.TemporaryDirectory() as td:
            mod_dir = Path(td) / "mymod" / "tests"
            mod_dir.mkdir(parents=True)
            (mod_dir / "test_a.py").write_text("")
            (mod_dir / "test_b.py").write_text("")
            self.assertEqual(count_test_suites(Path(td), ["mymod"]), 2)

    def test_includes_top_level_tests(self):
        with tempfile.TemporaryDirectory() as td:
            top_tests = Path(td) / "tests"
            top_tests.mkdir()
            (top_tests / "test_integration.py").write_text("")
            self.assertEqual(count_test_suites(Path(td), []), 1)

    def test_zero_for_empty_project(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(count_test_suites(Path(td), []), 0)


class TestExtractBacktickPaths(unittest.TestCase):
    """Test extracting file paths from markdown backticks."""

    def test_extracts_python_files(self):
        content = "- `hooks/capture_hook.py` — description"
        paths = extract_backtick_paths(content)
        self.assertIn("hooks/capture_hook.py", paths)

    def test_ignores_directories(self):
        content = "`memory-system/` — description"
        paths = extract_backtick_paths(content)
        self.assertEqual(len(paths), 0)

    def test_ignores_slash_commands(self):
        content = "`/spec:requirements`"
        paths = extract_backtick_paths(content)
        self.assertEqual(len(paths), 0)

    def test_empty_content(self):
        paths = extract_backtick_paths("")
        self.assertEqual(len(paths), 0)


class TestExtractModuleFiles(unittest.TestCase):
    """Test extracting per-module file paths from PROJECT_INDEX."""

    def test_extracts_files_under_module(self):
        content = (
            "**memory-system/** — Persistent memory\n"
            "- `hooks/capture_hook.py` — capture\n"
            "- `memory_store.py` — storage\n"
        )
        result = extract_module_files(content)
        self.assertIn("memory-system", result)
        self.assertEqual(len(result["memory-system"]), 2)
        self.assertIn("hooks/capture_hook.py", result["memory-system"])

    def test_multiple_modules(self):
        content = (
            "**memory-system/** — desc\n"
            "- `store.py` — storage\n"
            "\n"
            "**spec-system/** — desc\n"
            "- `validate.py` — validation\n"
        )
        result = extract_module_files(content)
        self.assertEqual(len(result), 2)

    def test_empty_content(self):
        result = extract_module_files("")
        self.assertEqual(len(result), 0)


class TestCheckPathsExist(unittest.TestCase):
    """Test file existence checking."""

    def test_finds_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "exists.py").write_text("")
            existing, missing = check_paths_exist(["exists.py"], Path(td))
            self.assertEqual(existing, ["exists.py"])
            self.assertEqual(missing, [])

    def test_detects_missing_files(self):
        with tempfile.TemporaryDirectory() as td:
            existing, missing = check_paths_exist(["nope.py"], Path(td))
            self.assertEqual(existing, [])
            self.assertEqual(missing, ["nope.py"])

    def test_mixed_existing_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "exists.py").write_text("")
            existing, missing = check_paths_exist(
                ["exists.py", "nope.py"], Path(td)
            )
            self.assertEqual(len(existing), 1)
            self.assertEqual(len(missing), 1)


class TestDriftReport(unittest.TestCase):
    """Test DriftReport dataclass."""

    def test_no_drift(self):
        report = DriftReport()
        self.assertFalse(report.has_drift)

    def test_has_drift_with_mismatches(self):
        report = DriftReport(
            test_mismatches=[TestCountMismatch("PI", "mod", 10, 15)]
        )
        self.assertTrue(report.has_drift)

    def test_has_drift_with_missing_files(self):
        report = DriftReport(missing_files=["gone.py"])
        self.assertTrue(report.has_drift)

    def test_format_clean(self):
        report = DriftReport(total_actual=100, suite_actual=10)
        formatted = report.format()
        self.assertIn("No drift", formatted)
        self.assertIn("100", formatted)

    def test_format_with_mismatches(self):
        report = DriftReport(
            test_mismatches=[TestCountMismatch("PI", "mod", 10, 15)]
        )
        formatted = report.format()
        self.assertIn("MISMATCH", formatted)
        self.assertIn("+5", formatted)

    def test_format_with_missing_files(self):
        report = DriftReport(missing_files=["mod/gone.py"])
        formatted = report.format()
        self.assertIn("MISSING", formatted)
        self.assertIn("gone.py", formatted)

    def test_to_dict(self):
        report = DriftReport(
            test_mismatches=[TestCountMismatch("PI", "mod", 10, 15)],
            missing_files=["gone.py"],
            total_claimed=100,
            total_actual=105,
        )
        d = report.to_dict()
        self.assertTrue(d["has_drift"])
        self.assertEqual(len(d["test_mismatches"]), 1)
        self.assertEqual(d["total_claimed"], 100)


class TestRunDriftCheck(unittest.TestCase):
    """Integration test for run_drift_check."""

    def test_runs_on_empty_project(self):
        with tempfile.TemporaryDirectory() as td:
            report = run_drift_check(Path(td), modules=[])
            self.assertIsInstance(report, DriftReport)

    def test_runs_with_project_index(self):
        with tempfile.TemporaryDirectory() as td:
            pi = Path(td) / "PROJECT_INDEX.md"
            pi.write_text(
                "| Test Module | `testmod/` | DONE | 5 |\n"
                "**Total: 5 tests (1 suites).**\n"
            )
            # Create actual test module
            tests_dir = Path(td) / "testmod" / "tests"
            tests_dir.mkdir(parents=True)
            (tests_dir / "test_foo.py").write_text(
                "def test_1(): pass\ndef test_2(): pass\n"
            )
            report = run_drift_check(Path(td), modules=["testmod"])
            # Should detect mismatch: claimed 5, actual 2
            self.assertTrue(report.has_drift)

    def test_clean_project(self):
        with tempfile.TemporaryDirectory() as td:
            tests_dir = Path(td) / "mymod" / "tests"
            tests_dir.mkdir(parents=True)
            (tests_dir / "test_one.py").write_text(
                "def test_a(): pass\ndef test_b(): pass\n"
            )
            pi = Path(td) / "PROJECT_INDEX.md"
            pi.write_text(
                "| My Module | `mymod/` | DONE | 2 |\n"
                "**Total: 2 tests (1 suites).**\n"
            )
            report = run_drift_check(Path(td), modules=["mymod"])
            # Counts should match
            mismatches = [m for m in report.test_mismatches if m.module == "mymod"]
            self.assertEqual(len(mismatches), 0)


class TestFindProjectRoot(unittest.TestCase):
    """Test project root detection."""

    def test_explicit_root(self):
        with tempfile.TemporaryDirectory() as td:
            result = find_project_root(td)
            self.assertEqual(result, Path(td))

    def test_explicit_root_not_found(self):
        with self.assertRaises(FileNotFoundError):
            find_project_root("/nonexistent/path/12345")

    def test_finds_real_project_root(self):
        # Should find the CCA project root from usage-dashboard/
        real_root = Path(__file__).resolve().parent.parent.parent
        if (real_root / "CLAUDE.md").exists():
            result = find_project_root(str(real_root))
            self.assertTrue(result.is_dir())


class TestDefaultModules(unittest.TestCase):
    """Test that DEFAULT_MODULES are properly defined."""

    def test_includes_all_frontiers(self):
        self.assertIn("memory-system", DEFAULT_MODULES)
        self.assertIn("spec-system", DEFAULT_MODULES)
        self.assertIn("context-monitor", DEFAULT_MODULES)
        self.assertIn("agent-guard", DEFAULT_MODULES)
        self.assertIn("usage-dashboard", DEFAULT_MODULES)

    def test_includes_research_modules(self):
        self.assertIn("reddit-intelligence", DEFAULT_MODULES)
        self.assertIn("self-learning", DEFAULT_MODULES)
        self.assertIn("design-skills", DEFAULT_MODULES)


if __name__ == "__main__":
    unittest.main()
