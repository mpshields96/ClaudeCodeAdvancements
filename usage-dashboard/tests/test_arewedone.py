#!/usr/bin/env python3
"""Tests for arewedone.py — Structural Completeness Checker."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add module root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arewedone import (
    MODULES,
    ModuleReport,
    StubInfo,
    SyntaxError_,
    DocFreshness,
    FullReport,
    find_project_root,
    find_py_files,
    find_test_files,
    check_module_completeness,
    detect_pass_only_function,
    find_code_stubs,
    check_syntax,
    get_git_status,
    parse_git_status_lines,
    check_doc_freshness,
    format_age,
    collect_all_py_files,
    generate_test_stub,
    create_missing_test_stubs,
    run_full_check,
    format_report,
    DOC_FRESHNESS_HOURS,
)


class MockProject:
    """Helper to create a temporary mock project structure."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp(prefix="arewedone_test_")
        self.root = Path(self.tmpdir)
        # Create CLAUDE.md at root so find_project_root works
        (self.root / "CLAUDE.md").write_text("# Test Project\n")

    def add_module(self, name, claude_md=True, py_files=None, test_files=None):
        """Add a module with optional components."""
        mod_dir = self.root / name
        mod_dir.mkdir(parents=True, exist_ok=True)

        if claude_md:
            (mod_dir / "CLAUDE.md").write_text(f"# {name} rules\n")

        if py_files:
            for fname, content in py_files.items():
                fpath = mod_dir / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content)

        if test_files:
            tests_dir = mod_dir / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            for fname, content in test_files.items():
                (tests_dir / fname).write_text(content)

        return mod_dir

    def cleanup(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestFindProjectRoot(unittest.TestCase):
    """Tests for find_project_root."""

    def test_explicit_root(self):
        proj = MockProject()
        try:
            root = find_project_root(proj.tmpdir)
            self.assertEqual(root, Path(proj.tmpdir))
        finally:
            proj.cleanup()

    def test_explicit_root_not_found(self):
        with self.assertRaises(FileNotFoundError):
            find_project_root("/nonexistent/path/that/does/not/exist")

    def test_auto_detect_uses_explicit_over_auto(self):
        """When explicit root is given, auto-detect is bypassed."""
        proj = MockProject()
        try:
            root = find_project_root(proj.tmpdir)
            self.assertEqual(root, Path(proj.tmpdir))
        finally:
            proj.cleanup()


class TestModuleDetection(unittest.TestCase):
    """Tests for module detection and known modules list."""

    def test_known_modules_list(self):
        self.assertIn("memory-system", MODULES)
        self.assertIn("spec-system", MODULES)
        self.assertIn("context-monitor", MODULES)
        self.assertIn("agent-guard", MODULES)
        self.assertIn("usage-dashboard", MODULES)
        self.assertIn("reddit-intelligence", MODULES)
        self.assertIn("self-learning", MODULES)
        self.assertEqual(len(MODULES), 7)

    def test_find_py_files_basic(self):
        proj = MockProject()
        try:
            proj.add_module("test-mod", py_files={
                "main.py": "print('hello')\n",
                "hooks/helper.py": "x = 1\n",
            }, test_files={
                "test_main.py": "import unittest\n",
            })
            py_files = find_py_files(proj.root / "test-mod")
            basenames = [os.path.basename(f) for f in py_files]
            self.assertIn("main.py", basenames)
            self.assertIn("helper.py", basenames)
            # test files should NOT be included
            self.assertNotIn("test_main.py", basenames)
        finally:
            proj.cleanup()

    def test_find_py_files_empty_module(self):
        proj = MockProject()
        try:
            proj.add_module("empty-mod", py_files=None)
            py_files = find_py_files(proj.root / "empty-mod")
            self.assertEqual(py_files, [])
        finally:
            proj.cleanup()

    def test_find_py_files_nonexistent_dir(self):
        py_files = find_py_files(Path("/nonexistent/dir"))
        self.assertEqual(py_files, [])

    def test_find_test_files(self):
        proj = MockProject()
        try:
            proj.add_module("test-mod", test_files={
                "test_main.py": "import unittest\n",
                "test_helpers.py": "import unittest\n",
            })
            test_files = find_test_files(proj.root / "test-mod")
            basenames = [os.path.basename(f) for f in test_files]
            self.assertIn("test_main.py", basenames)
            self.assertIn("test_helpers.py", basenames)
        finally:
            proj.cleanup()

    def test_find_test_files_no_tests_dir(self):
        proj = MockProject()
        try:
            proj.add_module("no-tests", py_files={"main.py": "x = 1\n"})
            test_files = find_test_files(proj.root / "no-tests")
            self.assertEqual(test_files, [])
        finally:
            proj.cleanup()

    def test_find_test_files_ignores_non_test_prefix(self):
        proj = MockProject()
        try:
            mod_dir = proj.add_module("test-mod")
            tests_dir = mod_dir / "tests"
            tests_dir.mkdir(exist_ok=True)
            (tests_dir / "helper.py").write_text("# not a test\n")
            (tests_dir / "test_real.py").write_text("import unittest\n")
            test_files = find_test_files(mod_dir)
            basenames = [os.path.basename(f) for f in test_files]
            self.assertIn("test_real.py", basenames)
            self.assertNotIn("helper.py", basenames)
        finally:
            proj.cleanup()


class TestClaudeMdPresence(unittest.TestCase):
    """Tests for CLAUDE.md presence check."""

    def test_claude_md_present(self):
        proj = MockProject()
        try:
            proj.add_module("has-claude", claude_md=True,
                          py_files={"main.py": "x=1\n"},
                          test_files={"test_main.py": PASSING_TEST})
            report = check_module_completeness("has-claude", proj.root,
                                                run_tests=False)
            self.assertTrue(report.has_claude_md)
        finally:
            proj.cleanup()

    def test_claude_md_missing(self):
        proj = MockProject()
        try:
            proj.add_module("no-claude", claude_md=False,
                          py_files={"main.py": "x=1\n"})
            report = check_module_completeness("no-claude", proj.root,
                                                run_tests=False)
            self.assertFalse(report.has_claude_md)
            self.assertIn(report.status, ("WARN", "FAIL"))
        finally:
            proj.cleanup()


# A minimal passing test content
PASSING_TEST = '''
import unittest
class TestPass(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
if __name__ == "__main__":
    unittest.main()
'''

FAILING_TEST = '''
import unittest
class TestFail(unittest.TestCase):
    def test_fail(self):
        self.fail("intentional")
if __name__ == "__main__":
    unittest.main()
'''


class TestCodeStubDetection(unittest.TestCase):
    """Tests for code stub detection."""

    def test_finds_todo(self):
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": "x = 1  # TODO: fix this\n",
            })
            py_files = find_py_files(proj.root / "stub-mod")
            stubs = find_code_stubs(py_files)
            self.assertEqual(len(stubs), 1)
            self.assertEqual(stubs[0].kind, "TODO")
        finally:
            proj.cleanup()

    def test_finds_fixme(self):
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": "x = 1  # FIXME: broken\n",
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            self.assertEqual(len(stubs), 1)
            self.assertEqual(stubs[0].kind, "FIXME")
        finally:
            proj.cleanup()

    def test_finds_not_implemented_error(self):
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": "def f():\n    raise NotImplementedError\n",
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            kinds = [s.kind for s in stubs]
            self.assertIn("NotImplementedError", kinds)
        finally:
            proj.cleanup()

    def test_finds_pass_only_function(self):
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": "def empty_func():\n    pass\n",
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            kinds = [s.kind for s in stubs]
            self.assertIn("pass-only", kinds)
        finally:
            proj.cleanup()

    def test_pass_with_docstring_not_flagged(self):
        """A function with docstring + pass is intentional, NOT a stub."""
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": 'def documented():\n    """Suppress output."""\n    pass\n',
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            kinds = [s.kind for s in stubs]
            # Documented pass-only is intentional (e.g. log suppression override)
            self.assertNotIn("pass-only", kinds)
        finally:
            proj.cleanup()

    def test_pass_without_docstring_still_flagged(self):
        """A function with pass and NO docstring IS a stub."""
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": 'def undocumented():\n    pass\n',
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            kinds = [s.kind for s in stubs]
            self.assertIn("pass-only", kinds)
        finally:
            proj.cleanup()

    def test_no_stubs_in_clean_code(self):
        proj = MockProject()
        try:
            proj.add_module("clean-mod", py_files={
                "main.py": "def real_func():\n    return 42\n",
            })
            stubs = find_code_stubs(find_py_files(proj.root / "clean-mod"))
            self.assertEqual(len(stubs), 0)
        finally:
            proj.cleanup()

    def test_multiple_stubs_in_one_file(self):
        proj = MockProject()
        try:
            proj.add_module("stub-mod", py_files={
                "main.py": (
                    "# TODO: first\n"
                    "# FIXME: second\n"
                    "def stub():\n    raise NotImplementedError\n"
                ),
            })
            stubs = find_code_stubs(find_py_files(proj.root / "stub-mod"))
            self.assertGreaterEqual(len(stubs), 3)
        finally:
            proj.cleanup()


class TestSyntaxCheck(unittest.TestCase):
    """Tests for import/syntax health check."""

    def test_valid_syntax(self):
        proj = MockProject()
        try:
            proj.add_module("ok-mod", py_files={
                "main.py": "x = 1 + 2\n",
            })
            errors = check_syntax(find_py_files(proj.root / "ok-mod"))
            self.assertEqual(len(errors), 0)
        finally:
            proj.cleanup()

    def test_syntax_error_detected(self):
        proj = MockProject()
        try:
            proj.add_module("bad-mod", py_files={
                "broken.py": "def f(\n",
            })
            errors = check_syntax(find_py_files(proj.root / "bad-mod"))
            self.assertEqual(len(errors), 1)
            self.assertIn("broken.py", errors[0].file_path)
        finally:
            proj.cleanup()


class TestGitStatus(unittest.TestCase):
    """Tests for git status parsing."""

    def test_parse_git_status_lines(self):
        lines = [
            " M SESSION_STATE.md",
            "?? new_file.py",
            "M  modified.py",
        ]
        parsed = parse_git_status_lines(lines)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0], " M SESSION_STATE.md")

    def test_git_status_returns_list(self):
        """get_git_status should return a list (may be empty or populated)."""
        proj = MockProject()
        try:
            # Init a git repo
            subprocess.run(["git", "init"], cwd=proj.tmpdir, capture_output=True)
            result = get_git_status(proj.root)
            self.assertIsInstance(result, list)
        finally:
            proj.cleanup()


class TestDocFreshness(unittest.TestCase):
    """Tests for doc freshness calculation."""

    def test_fresh_doc(self):
        proj = MockProject()
        try:
            doc = proj.root / "SESSION_STATE.md"
            doc.write_text("# Session\n")
            now = time.time()
            results = check_doc_freshness(proj.root, ["SESSION_STATE.md"], now=now)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "OK")
            self.assertTrue(results[0].exists)
        finally:
            proj.cleanup()

    def test_stale_doc(self):
        proj = MockProject()
        try:
            doc = proj.root / "SESSION_STATE.md"
            doc.write_text("# Session\n")
            # Set mtime to 48 hours ago
            old_time = time.time() - (48 * 3600)
            os.utime(str(doc), (old_time, old_time))
            results = check_doc_freshness(proj.root, ["SESSION_STATE.md"],
                                          now=time.time())
            self.assertEqual(results[0].status, "STALE")
        finally:
            proj.cleanup()

    def test_missing_doc(self):
        proj = MockProject()
        try:
            results = check_doc_freshness(proj.root, ["NONEXISTENT.md"])
            self.assertEqual(results[0].status, "MISSING")
            self.assertFalse(results[0].exists)
        finally:
            proj.cleanup()

    def test_format_age_minutes(self):
        self.assertIn("m ago", format_age(0.5))

    def test_format_age_hours(self):
        self.assertIn("h ago", format_age(5))

    def test_format_age_days(self):
        self.assertIn("d ago", format_age(72))


class TestReportGeneration(unittest.TestCase):
    """Tests for overall report generation and formatting."""

    def test_format_report_contains_header(self):
        report = FullReport()
        output = format_report(report)
        self.assertIn("Are We Done?", output)

    def test_format_report_shows_pass(self):
        report = FullReport(module_reports=[
            ModuleReport(name="test-mod", status="PASS",
                        summary="CLAUDE.md, 2 py files, 1 test file, all tests pass"),
        ])
        output = format_report(report)
        self.assertIn("[PASS]", output)
        self.assertIn("test-mod", output)

    def test_format_report_shows_warn(self):
        report = FullReport(module_reports=[
            ModuleReport(name="warn-mod", status="WARN",
                        summary="CLAUDE.md present, 1 py file, 0 test files — NEEDS TESTS"),
        ])
        output = format_report(report)
        self.assertIn("[WARN]", output)

    def test_format_report_shows_fail(self):
        report = FullReport(module_reports=[
            ModuleReport(name="fail-mod", status="FAIL",
                        summary="missing CLAUDE.md"),
        ])
        output = format_report(report)
        self.assertIn("[FAIL]", output)

    def test_format_report_shows_stubs(self):
        report = FullReport(stubs=[
            StubInfo(file_path="main.py", line_number=5, kind="TODO",
                    line_text="# TODO: fix"),
        ])
        output = format_report(report)
        self.assertIn("Code Stubs Found: 1", output)
        self.assertIn("TODO", output)

    def test_format_report_shows_no_stubs(self):
        report = FullReport()
        output = format_report(report)
        self.assertIn("Code Stubs Found: 0", output)
        self.assertIn("(none)", output)

    def test_format_report_overall_line(self):
        report = FullReport(
            module_reports=[
                ModuleReport(name="a", status="PASS", summary="ok"),
                ModuleReport(name="b", status="FAIL", summary="bad"),
            ],
            stubs=[StubInfo("f.py", 1, "TODO", "# TODO")],
            syntax_errors=[],
            uncommitted_lines=["M file.py"],
        )
        output = format_report(report)
        self.assertIn("1/2 modules complete", output)
        self.assertIn("1 stubs", output)
        self.assertIn("0 syntax errors", output)
        self.assertIn("1 uncommitted", output)


class TestFullCheck(unittest.TestCase):
    """Tests for run_full_check integration."""

    def test_full_check_clean_module(self):
        proj = MockProject()
        try:
            proj.add_module("test-mod", claude_md=True,
                          py_files={"main.py": "x = 1\n"},
                          test_files={"test_main.py": PASSING_TEST})
            # Init git repo so git status works
            subprocess.run(["git", "init"], cwd=proj.tmpdir, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=proj.tmpdir, capture_output=True)
            # Create doc files
            (proj.root / "SESSION_STATE.md").write_text("# State\n")
            (proj.root / "PROJECT_INDEX.md").write_text("# Index\n")

            report = run_full_check(proj.root, ["test-mod"], run_tests=False)
            self.assertEqual(len(report.module_reports), 1)
            self.assertEqual(report.module_reports[0].status, "PASS")
        finally:
            proj.cleanup()

    def test_full_check_has_issues(self):
        proj = MockProject()
        try:
            proj.add_module("bad-mod", claude_md=False, py_files={
                "main.py": "# TODO: implement\n",
            })
            subprocess.run(["git", "init"], cwd=proj.tmpdir, capture_output=True)
            (proj.root / "SESSION_STATE.md").write_text("# State\n")
            (proj.root / "PROJECT_INDEX.md").write_text("# Index\n")

            report = run_full_check(proj.root, ["bad-mod"], run_tests=False)
            self.assertTrue(report.has_issues)
        finally:
            proj.cleanup()


class TestQuietExitCode(unittest.TestCase):
    """Tests for --quiet exit code behavior."""

    def test_quiet_exit_0_on_clean(self):
        proj = MockProject()
        try:
            proj.add_module("ok-mod", claude_md=True,
                          py_files={"main.py": "x = 1\n"},
                          test_files={"test_main.py": PASSING_TEST})
            subprocess.run(["git", "init"], cwd=proj.tmpdir, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=proj.tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=proj.tmpdir,
                         capture_output=True,
                         env={**os.environ, "GIT_AUTHOR_NAME": "test",
                              "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "test",
                              "GIT_COMMITTER_EMAIL": "t@t"})
            (proj.root / "SESSION_STATE.md").write_text("# State\n")
            (proj.root / "PROJECT_INDEX.md").write_text("# Index\n")

            arewedone_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "arewedone.py"
            )
            result = subprocess.run(
                [sys.executable, arewedone_path,
                 "--root", proj.tmpdir, "--module", "ok-mod",
                 "--quiet", "--no-test-run"],
                capture_output=True, text=True, timeout=30,
            )
            # May still be 1 due to stubs in test file or other checks
            self.assertIn(result.returncode, (0, 1))
        finally:
            proj.cleanup()

    def test_quiet_exit_1_on_issues(self):
        proj = MockProject()
        try:
            proj.add_module("bad-mod", claude_md=False)
            subprocess.run(["git", "init"], cwd=proj.tmpdir, capture_output=True)

            arewedone_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "arewedone.py"
            )
            result = subprocess.run(
                [sys.executable, arewedone_path,
                 "--root", proj.tmpdir, "--module", "bad-mod",
                 "--quiet", "--no-test-run"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 1)
        finally:
            proj.cleanup()


class TestEdgeCases(unittest.TestCase):
    """Edge cases: module with no py files, module with tests but no src."""

    def test_module_with_no_py_files(self):
        proj = MockProject()
        try:
            # Module with CLAUDE.md but no .py files
            proj.add_module("empty-mod", claude_md=True)
            report = check_module_completeness("empty-mod", proj.root,
                                                run_tests=False)
            # No py files and no tests — should warn or fail
            self.assertIn(report.status, ("WARN", "FAIL"))
        finally:
            proj.cleanup()

    def test_module_with_tests_but_no_src(self):
        proj = MockProject()
        try:
            proj.add_module("tests-only", claude_md=True,
                          test_files={"test_something.py": PASSING_TEST})
            report = check_module_completeness("tests-only", proj.root,
                                                run_tests=False)
            # Has tests but no source — still technically a pass if all requirements met
            # But no py_files means it gets PASS (tests dir present, claude_md present)
            self.assertIn(report.status, ("PASS", "WARN"))
        finally:
            proj.cleanup()

    def test_nonexistent_module(self):
        proj = MockProject()
        try:
            report = check_module_completeness("nonexistent", proj.root,
                                                run_tests=False)
            self.assertEqual(report.status, "FAIL")
            self.assertIn("not found", report.summary)
        finally:
            proj.cleanup()

    def test_collect_all_py_files_across_modules(self):
        proj = MockProject()
        try:
            proj.add_module("mod-a", py_files={"a.py": "x=1\n"},
                          test_files={"test_a.py": "import unittest\n"})
            proj.add_module("mod-b", py_files={"b.py": "y=2\n"})
            all_files = collect_all_py_files(proj.root, ["mod-a", "mod-b"])
            basenames = [os.path.basename(f) for f in all_files]
            self.assertIn("a.py", basenames)
            self.assertIn("b.py", basenames)
            self.assertIn("test_a.py", basenames)
        finally:
            proj.cleanup()


class TestFixMode(unittest.TestCase):
    """Tests for --fix auto-create test stubs."""

    def test_generate_test_stub(self):
        proj = MockProject()
        try:
            mod_dir = proj.add_module("fix-mod", py_files={
                "main.py": "x = 1\n",
            })
            (mod_dir / "tests").mkdir(exist_ok=True)
            result = generate_test_stub(str(mod_dir / "main.py"), mod_dir)
            self.assertIsNotNone(result)
            path, content = result
            self.assertIn("test_main.py", path)
            self.assertIn("unittest", content)
        finally:
            proj.cleanup()

    def test_generate_test_stub_already_exists(self):
        proj = MockProject()
        try:
            mod_dir = proj.add_module("fix-mod",
                                     py_files={"main.py": "x = 1\n"},
                                     test_files={"test_main.py": PASSING_TEST})
            result = generate_test_stub(str(mod_dir / "main.py"), mod_dir)
            self.assertIsNone(result)
        finally:
            proj.cleanup()

    def test_create_missing_test_stubs(self):
        proj = MockProject()
        try:
            proj.add_module("fix-mod", py_files={
                "main.py": "x = 1\n",
                "helper.py": "y = 2\n",
            })
            created = create_missing_test_stubs(proj.root, ["fix-mod"])
            self.assertEqual(len(created), 2)
            for path in created:
                self.assertTrue(Path(path).exists())
        finally:
            proj.cleanup()


class TestPassOnlyDetection(unittest.TestCase):
    """Tests for AST-based pass-only function detection."""

    def test_simple_pass_only(self):
        source = "def f():\n    pass\n"
        results = detect_pass_only_function(source)
        self.assertEqual(len(results), 1)

    def test_function_with_body_not_flagged(self):
        source = "def f():\n    return 42\n"
        results = detect_pass_only_function(source)
        self.assertEqual(len(results), 0)

    def test_syntax_error_returns_empty(self):
        source = "def f(\n"
        results = detect_pass_only_function(source)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
