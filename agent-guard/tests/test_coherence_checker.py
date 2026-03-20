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
    RuleExtractor,
    RuleComplianceCheck,
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


class TestRuleExtractor(unittest.TestCase):
    """Test CLAUDE.md rule extraction."""

    def test_extracts_rules_from_non_negotiable_section(self):
        content = """# Module Rules

## Non-Negotiable Rules
- **No blocking in WARN mode** — never prevent work when name is unset
- **Lock files must be released on session end** — Stop hook releases all locks
- **Zero dependencies beyond Python stdlib** — must work without installing anything
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertTrue(len(rules) >= 3)

    def test_extracts_stdlib_only_rule(self):
        content = """# Rules
## Non-Negotiable Rules
- **Zero dependencies beyond Python stdlib + fnmatch** — must work without installing anything
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        stdlib_rules = [r for r in rules if r["type"] == "stdlib_only"]
        self.assertEqual(len(stdlib_rules), 1)

    def test_extracts_generic_rules(self):
        content = """# Module Rules
## Architecture Rules
- Ownership is per-session by default
- Agent name is set as an environment variable
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertTrue(len(rules) >= 2)

    def test_empty_content_returns_empty(self):
        extractor = RuleExtractor()
        rules = extractor.extract("")
        self.assertEqual(rules, [])

    def test_no_rules_section_returns_empty(self):
        content = "# Just a title\n\nSome text without rules.\n"
        extractor = RuleExtractor()
        rules = extractor.extract("")
        self.assertEqual(rules, [])

    def test_extracts_never_patterns(self):
        content = """# Rules
## Non-Negotiable Rules
- **Never log API keys** — security risk
- Never modify system files
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        never_rules = [r for r in rules if r["type"] == "forbidden"]
        self.assertTrue(len(never_rules) >= 1)

    def test_rule_has_text_field(self):
        content = """# Rules
## Non-Negotiable Rules
- **No blocking** — never block anything
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertTrue(all("text" in r for r in rules))

    def test_extracts_from_multiple_rule_sections(self):
        content = """# Module
## Non-Negotiable Rules
- Rule A from non-negotiable

## Architecture Rules
- Rule B from architecture
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertTrue(len(rules) >= 2)


class TestRuleComplianceCheck(unittest.TestCase):
    """Test code compliance against extracted CLAUDE.md rules."""

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

    def test_stdlib_only_violation_detected(self):
        """Code importing external packages violates stdlib-only rule."""
        rules = [{"type": "stdlib_only", "text": "Zero dependencies beyond Python stdlib"}]
        code_path = self._write_file("mod.py", "import requests\nimport os\n\ndef fetch():\n    pass\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules)
        self.assertTrue(any("requests" in i for i in issues))

    def test_stdlib_imports_pass(self):
        """Code using only stdlib should not trigger violations."""
        rules = [{"type": "stdlib_only", "text": "Zero dependencies beyond Python stdlib"}]
        code_path = self._write_file("mod.py", "import os\nimport json\nimport sys\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules)
        self.assertEqual(len(issues), 0)

    def test_local_imports_pass_stdlib_rule(self):
        """Local project imports should not trigger stdlib-only violations."""
        rules = [{"type": "stdlib_only", "text": "Zero dependencies beyond Python stdlib"}]
        code_path = self._write_file("mod.py", "from satd_detector import SATDDetector\nimport os\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules, local_modules={"satd_detector"})
        self.assertEqual(len(issues), 0)

    def test_no_rules_no_issues(self):
        """No rules means no compliance issues."""
        code_path = self._write_file("mod.py", "import requests\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, [])
        self.assertEqual(len(issues), 0)

    def test_file_not_found_no_crash(self):
        """Missing file should not crash."""
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        checker = RuleComplianceCheck()
        issues = checker.check("/nonexistent/file.py", rules)
        self.assertEqual(len(issues), 0)

    def test_non_python_file_skipped(self):
        """Non-Python files should be skipped for import checks."""
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        code_path = self._write_file("readme.md", "import requests\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules)
        self.assertEqual(len(issues), 0)

    def test_multiple_external_imports_all_flagged(self):
        """Multiple external imports should each be flagged."""
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        code_path = self._write_file("mod.py", "import requests\nimport flask\nimport pandas\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules)
        self.assertTrue(len(issues) >= 3)

    def test_allowed_exceptions_in_stdlib_rule(self):
        """Packages explicitly mentioned in the rule text should be allowed."""
        rules = [{"type": "stdlib_only", "text": "Zero dependencies beyond Python stdlib + anthropic", "allowed": ["anthropic"]}]
        code_path = self._write_file("mod.py", "import anthropic\nimport os\n")
        checker = RuleComplianceCheck()
        issues = checker.check(code_path, rules)
        self.assertEqual(len(issues), 0)


class TestCoherenceCheckerWithRules(unittest.TestCase):
    """Test that CoherenceChecker integrates rule compliance."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_rule_violations_appear_in_report(self):
        """Rule violations from CLAUDE.md should appear in the coherence report."""
        # Create a module with a CLAUDE.md containing stdlib-only rule
        mod_dir = os.path.join(self.tmpdir, "my-mod")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n## Non-Negotiable Rules\n- **Zero dependencies beyond Python stdlib** — no external packages\n")
        with open(os.path.join(mod_dir, "bad.py"), "w") as f:
            f.write('"""Bad module."""\nimport requests\n\ndef fetch():\n    pass\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["my-mod"])
        rule_issues = [i for i in report.issues if "rule" in i.lower() or "stdlib" in i.lower() or "requests" in i.lower()]
        self.assertTrue(len(rule_issues) > 0)

    def test_compliant_code_no_rule_violations(self):
        """Code that follows CLAUDE.md rules should produce no rule violations."""
        mod_dir = os.path.join(self.tmpdir, "good-mod")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n## Non-Negotiable Rules\n- **Zero dependencies beyond Python stdlib** — no external packages\n")
        with open(os.path.join(mod_dir, "good.py"), "w") as f:
            f.write('"""Good module."""\nimport os\nimport json\n\ndef run():\n    pass\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["good-mod"])
        rule_issues = [i for i in report.issues if "rule" in i.lower() or "stdlib" in i.lower()]
        self.assertEqual(len(rule_issues), 0)


class TestProjectRootRuleCompliance(unittest.TestCase):
    """Test that project-root CLAUDE.md rules apply to all modules."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_root_claude_md_rules_apply_to_all_modules(self):
        """Rules in root CLAUDE.md should be checked against all module files."""
        # Root CLAUDE.md with stdlib-only rule
        with open(os.path.join(self.tmpdir, "CLAUDE.md"), "w") as f:
            f.write("# Project Rules\n## Architecture Rules\n- **Stdlib-first: no external packages by default** — keep it simple\n")

        # Module A — compliant
        mod_a = os.path.join(self.tmpdir, "mod-a")
        os.makedirs(os.path.join(mod_a, "tests"))
        with open(os.path.join(mod_a, "CLAUDE.md"), "w") as f:
            f.write("# Mod A\n")
        with open(os.path.join(mod_a, "clean.py"), "w") as f:
            f.write('"""Clean."""\nimport os\n')

        # Module B — violating root rule
        mod_b = os.path.join(self.tmpdir, "mod-b")
        os.makedirs(os.path.join(mod_b, "tests"))
        with open(os.path.join(mod_b, "CLAUDE.md"), "w") as f:
            f.write("# Mod B\n")
        with open(os.path.join(mod_b, "bad.py"), "w") as f:
            f.write('"""Bad."""\nimport flask\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check()
        root_violations = [i for i in report.issues if "flask" in i]
        self.assertTrue(len(root_violations) > 0)

    def test_no_root_claude_md_no_crash(self):
        """Projects without root CLAUDE.md should work fine."""
        mod = os.path.join(self.tmpdir, "my-mod")
        os.makedirs(os.path.join(mod, "tests"))
        with open(os.path.join(mod, "CLAUDE.md"), "w") as f:
            f.write("# Mod\n")
        with open(os.path.join(mod, "code.py"), "w") as f:
            f.write('"""Code."""\nimport flask\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check()
        # Should not crash — module-level CLAUDE.md has no stdlib rule
        self.assertIsInstance(report, CoherenceReport)

    def test_root_rules_dont_double_count_with_module_rules(self):
        """If module CLAUDE.md has the same rule as root, don't flag twice."""
        # Both root and module say stdlib-only
        with open(os.path.join(self.tmpdir, "CLAUDE.md"), "w") as f:
            f.write("# Root\n## Architecture Rules\n- **No external packages** — stdlib only\n")
        mod = os.path.join(self.tmpdir, "my-mod")
        os.makedirs(os.path.join(mod, "tests"))
        with open(os.path.join(mod, "CLAUDE.md"), "w") as f:
            f.write("# Mod\n## Non-Negotiable Rules\n- **Zero dependencies beyond Python stdlib** — no ext\n")
        with open(os.path.join(mod, "bad.py"), "w") as f:
            f.write('"""Bad."""\nimport requests\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check()
        req_issues = [i for i in report.issues if "requests" in i]
        # Should have issues but check they're not massively duplicated
        self.assertTrue(len(req_issues) >= 1)
        self.assertTrue(len(req_issues) <= 4)  # At most 2 rules x 2 import patterns


if __name__ == "__main__":
    unittest.main()
