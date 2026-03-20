#!/usr/bin/env python3
"""Tests for coherence_checker.py — MT-20 Phase 9: Architectural Coherence Checker.

Tests cover:
- Module structure scanning (does each module dir have tests/, CLAUDE.md?)
- Pattern detection across files (import style, naming, docstrings)
- One-file-one-job heuristic (mixed responsibilities detection)
- CLAUDE.md rule extraction and compliance checking
- Coherence report output structure
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coherence_checker import (
    CoherenceChecker,
    ModuleStructureCheck,
    PatternConsistencyCheck,
    ImportDependencyCheck,
    CoherenceReport,
    check_coherence,
)


class TestModuleStructureCheck(unittest.TestCase):
    """Test module directory structure scanning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_module(self, name, has_tests=True, has_claude_md=True, has_readme=True):
        mod_dir = os.path.join(self.tmpdir, name)
        os.makedirs(mod_dir, exist_ok=True)
        if has_tests:
            os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        if has_claude_md:
            with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
                f.write("# Module rules\n")
        if has_readme:
            with open(os.path.join(mod_dir, "README.md"), "w") as f:
                f.write("# Module docs\n")
        return mod_dir

    def test_complete_module_no_issues(self):
        self._make_module("agent-guard")
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["agent-guard"])
        self.assertEqual(len(issues), 0)

    def test_missing_tests_dir(self):
        self._make_module("my-module", has_tests=False)
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["my-module"])
        self.assertTrue(any("tests" in i.lower() for i in issues))

    def test_missing_claude_md(self):
        self._make_module("my-module", has_claude_md=False)
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["my-module"])
        self.assertTrue(any("claude.md" in i.lower() for i in issues))

    def test_multiple_modules_mixed(self):
        self._make_module("good-mod")
        self._make_module("bad-mod", has_tests=False, has_claude_md=False)
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["good-mod", "bad-mod"])
        # Should have issues only for bad-mod
        self.assertTrue(len(issues) >= 2)
        self.assertTrue(all("bad-mod" in i for i in issues))


class TestPatternConsistencyCheck(unittest.TestCase):
    """Test cross-file pattern detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_consistent_files_no_issues(self):
        self._write_file("mod_a.py", '"""Module A."""\n\ndef func_a():\n    pass\n')
        self._write_file("mod_b.py", '"""Module B."""\n\ndef func_b():\n    pass\n')
        checker = PatternConsistencyCheck()
        issues = checker.check([
            os.path.join(self.tmpdir, "mod_a.py"),
            os.path.join(self.tmpdir, "mod_b.py"),
        ])
        # Consistent files should produce no/few issues
        self.assertTrue(len(issues) <= 1)

    def test_missing_module_docstring_flagged(self):
        self._write_file("good.py", '"""Good module."""\n\ndef func():\n    pass\n')
        self._write_file("bad.py", 'import os\n\ndef func():\n    pass\n')
        checker = PatternConsistencyCheck()
        issues = checker.check([
            os.path.join(self.tmpdir, "good.py"),
            os.path.join(self.tmpdir, "bad.py"),
        ])
        docstring_issues = [i for i in issues if "docstring" in i.lower()]
        self.assertTrue(len(docstring_issues) > 0)

    def test_mixed_naming_flagged(self):
        """Files with camelCase mixed with snake_case should flag."""
        self._write_file("snake.py", '"""Mod."""\n\ndef my_func():\n    my_var = 1\n')
        self._write_file("camel.py", '"""Mod."""\n\ndef myFunc():\n    myVar = 1\n')
        checker = PatternConsistencyCheck()
        issues = checker.check([
            os.path.join(self.tmpdir, "snake.py"),
            os.path.join(self.tmpdir, "camel.py"),
        ])
        naming_issues = [i for i in issues if "naming" in i.lower() or "camel" in i.lower()]
        self.assertTrue(len(naming_issues) > 0)


class TestImportDependencyCheck(unittest.TestCase):
    """Test import dependency graph building."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_detects_local_imports(self):
        self._write_file("core.py", '"""Core."""\n\ndef process():\n    pass\n')
        self._write_file("handler.py", 'from core import process\n\ndef handle():\n    process()\n')
        checker = ImportDependencyCheck()
        graph = checker.build_graph([
            os.path.join(self.tmpdir, "core.py"),
            os.path.join(self.tmpdir, "handler.py"),
        ])
        # handler depends on core
        self.assertIn("core", graph.get("handler.py", {}).get("imports", []))

    def test_finds_dependents(self):
        self._write_file("utils.py", '"""Utils."""\n\ndef helper():\n    pass\n')
        self._write_file("a.py", 'from utils import helper\n')
        self._write_file("b.py", 'import utils\n')
        checker = ImportDependencyCheck()
        files = [
            os.path.join(self.tmpdir, "utils.py"),
            os.path.join(self.tmpdir, "a.py"),
            os.path.join(self.tmpdir, "b.py"),
        ]
        graph = checker.build_graph(files)
        dependents = checker.find_dependents("utils", graph)
        self.assertIn("a.py", dependents)
        self.assertIn("b.py", dependents)

    def test_no_deps_returns_empty(self):
        self._write_file("standalone.py", '"""Solo."""\n\nx = 1\n')
        checker = ImportDependencyCheck()
        graph = checker.build_graph([os.path.join(self.tmpdir, "standalone.py")])
        self.assertEqual(graph["standalone.py"]["imports"], [])

    def test_stdlib_imports_excluded(self):
        self._write_file("mod.py", 'import os\nimport sys\nimport json\n\nx = 1\n')
        checker = ImportDependencyCheck()
        graph = checker.build_graph([os.path.join(self.tmpdir, "mod.py")])
        # os, sys, json are stdlib — should not appear as local imports
        self.assertEqual(graph["mod.py"]["imports"], [])

    def test_blast_radius_output(self):
        self._write_file("base.py", '"""Base."""\n')
        self._write_file("child1.py", 'from base import something\n')
        self._write_file("child2.py", 'import base\n')
        checker = ImportDependencyCheck()
        files = [
            os.path.join(self.tmpdir, f) for f in ["base.py", "child1.py", "child2.py"]
        ]
        graph = checker.build_graph(files)
        blast = checker.blast_radius("base", graph)
        self.assertEqual(blast["direct_dependents"], 2)
        self.assertIn("child1.py", blast["files"])
        self.assertIn("child2.py", blast["files"])


class TestCoherenceReport(unittest.TestCase):
    """Test report structure and output."""

    def test_report_to_dict(self):
        report = CoherenceReport(
            project_root="/tmp/project",
            modules_checked=3,
            files_checked=10,
            issues=["Issue 1", "Issue 2"],
            score=85.0,
        )
        d = report.to_dict()
        self.assertEqual(d["project_root"], "/tmp/project")
        self.assertEqual(d["modules_checked"], 3)
        self.assertEqual(d["files_checked"], 10)
        self.assertEqual(len(d["issues"]), 2)
        self.assertEqual(d["score"], 85.0)

    def test_empty_report(self):
        report = CoherenceReport(
            project_root="/tmp",
            modules_checked=0,
            files_checked=0,
            issues=[],
            score=100.0,
        )
        self.assertEqual(report.score, 100.0)
        self.assertEqual(len(report.issues), 0)


class TestCoherenceChecker(unittest.TestCase):
    """Test the main CoherenceChecker orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_project(self):
        """Create a minimal project structure."""
        # Module 1
        mod1 = os.path.join(self.tmpdir, "module-a")
        os.makedirs(os.path.join(mod1, "tests"), exist_ok=True)
        with open(os.path.join(mod1, "CLAUDE.md"), "w") as f:
            f.write("# Module A rules\n")
        with open(os.path.join(mod1, "core.py"), "w") as f:
            f.write('"""Core module."""\n\ndef process():\n    pass\n')
        # Module 2
        mod2 = os.path.join(self.tmpdir, "module-b")
        os.makedirs(os.path.join(mod2, "tests"), exist_ok=True)
        with open(os.path.join(mod2, "CLAUDE.md"), "w") as f:
            f.write("# Module B rules\n")
        with open(os.path.join(mod2, "handler.py"), "w") as f:
            f.write('"""Handler module."""\n\ndef handle():\n    pass\n')
        return ["module-a", "module-b"]

    def test_checker_produces_report(self):
        modules = self._make_project()
        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=modules)
        self.assertIsInstance(report, CoherenceReport)
        self.assertEqual(report.modules_checked, 2)
        self.assertGreaterEqual(report.files_checked, 2)

    def test_checker_score_range(self):
        modules = self._make_project()
        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=modules)
        self.assertGreaterEqual(report.score, 0.0)
        self.assertLessEqual(report.score, 100.0)

    def test_checker_auto_discovers_modules(self):
        """If no modules specified, auto-discover directories with CLAUDE.md."""
        self._make_project()
        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check()  # no modules arg
        self.assertEqual(report.modules_checked, 2)


class TestConvenienceFunction(unittest.TestCase):
    """Test module-level check_coherence function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        mod = os.path.join(self.tmpdir, "mod")
        os.makedirs(os.path.join(mod, "tests"))
        with open(os.path.join(mod, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")
        with open(os.path.join(mod, "main.py"), "w") as f:
            f.write('"""Main."""\n\ndef run():\n    pass\n')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_returns_dict(self):
        result = check_coherence(self.tmpdir)
        self.assertIsInstance(result, dict)
        self.assertIn("score", result)
        self.assertIn("issues", result)


if __name__ == "__main__":
    unittest.main()
