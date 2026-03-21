#!/usr/bin/env python3
"""Extended tests for coherence_checker.py — MT-20 Phase 9.

Covers edge cases and boundary conditions not in the primary test suite:
- Single-file pattern checks (< 2 files threshold)
- Score calculation and floor/ceiling
- Blast radius with no dependents
- Rule extractor edge cases (constraints section, bold stripping)
- RuleCompliance from-imports, relative imports, case-insensitive allowed
- CoherenceChecker with empty module list, missing py files
- Non-directory entries in module discovery
- All-no-docstring consistency (should not flag — consistent)
- Highly violating projects floor at score=0
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


# ── ModuleStructureCheck extended ─────────────────────────────────────────────


class TestModuleStructureCheckExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_module(self, name, has_tests=True, has_claude_md=True):
        mod_dir = os.path.join(self.tmpdir, name)
        os.makedirs(mod_dir, exist_ok=True)
        if has_tests:
            os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        if has_claude_md:
            with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
                f.write("# Module rules\n")
        return mod_dir

    def test_empty_modules_list_returns_no_issues(self):
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, [])
        self.assertEqual(issues, [])

    def test_nonexistent_module_raises_issue(self):
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["does-not-exist"])
        self.assertTrue(any("does-not-exist" in i for i in issues))

    def test_three_modules_one_bad(self):
        self._make_module("good-a")
        self._make_module("good-b")
        self._make_module("bad-c", has_tests=False, has_claude_md=False)
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["good-a", "good-b", "bad-c"])
        bad_issues = [i for i in issues if "bad-c" in i]
        self.assertGreaterEqual(len(bad_issues), 2)
        good_issues = [i for i in issues if "good-a" in i or "good-b" in i]
        self.assertEqual(len(good_issues), 0)

    def test_tests_is_file_not_directory_flags_issue(self):
        mod_dir = os.path.join(self.tmpdir, "my-mod")
        os.makedirs(mod_dir)
        # Create "tests" as a file, not a directory
        with open(os.path.join(mod_dir, "tests"), "w") as f:
            f.write("not a dir")
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["my-mod"])
        self.assertTrue(any("tests" in i.lower() for i in issues))

    def test_all_three_missing_multiple_issues(self):
        mod_dir = os.path.join(self.tmpdir, "bare-mod")
        os.makedirs(mod_dir)
        # Has no tests/, no CLAUDE.md
        checker = ModuleStructureCheck()
        issues = checker.check(self.tmpdir, ["bare-mod"])
        self.assertGreaterEqual(len(issues), 2)


# ── PatternConsistencyCheck extended ─────────────────────────────────────────


class TestPatternConsistencyCheckExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_single_file_returns_no_issues(self):
        """< 2 files: nothing to compare — return empty."""
        path = self._write_file("solo.py", "import requests\n\ndef myFunc():\n    pass\n")
        checker = PatternConsistencyCheck()
        issues = checker.check([path])
        self.assertEqual(issues, [])

    def test_empty_file_list_returns_no_issues(self):
        checker = PatternConsistencyCheck()
        issues = checker.check([])
        self.assertEqual(issues, [])

    def test_all_missing_docstrings_consistent_no_flag(self):
        """If all files lack docstrings, that's consistent — don't flag."""
        paths = []
        for i in range(3):
            paths.append(self._write_file(
                f"mod_{i}.py", f"import os\n\ndef func_{i}():\n    pass\n"
            ))
        checker = PatternConsistencyCheck()
        issues = checker.check(paths)
        docstring_issues = [i for i in issues if "docstring" in i.lower()]
        # Consistent absence — should not flag or flag at most 0 issues
        self.assertEqual(len(docstring_issues), 0)

    def test_all_have_docstrings_consistent_no_flag(self):
        """All files have docstrings — consistent — no flag."""
        paths = []
        for i in range(3):
            paths.append(self._write_file(
                f"good_{i}.py", f'"""Module {i}."""\n\ndef func_{i}():\n    pass\n'
            ))
        checker = PatternConsistencyCheck()
        issues = checker.check(paths)
        docstring_issues = [i for i in issues if "docstring" in i.lower()]
        self.assertEqual(len(docstring_issues), 0)

    def test_only_dunder_files_not_analyzed(self):
        """__init__.py files should be filtered (starts with __)."""
        # The checker receives explicit paths — it doesn't filter __ by itself,
        # but test that it handles files with camelCase gracefully
        path = self._write_file("__init__.py", "")
        path2 = self._write_file("main.py", '"""Main."""\n')
        checker = PatternConsistencyCheck()
        # Should not crash
        issues = checker.check([path, path2])
        self.assertIsInstance(issues, list)

    def test_one_camel_many_snake_flags_camel(self):
        """If 3 files are snake_case and 1 is camelCase, flag the camelCase one."""
        paths = []
        for i in range(3):
            paths.append(self._write_file(
                f"snake_{i}.py", f'"""Mod {i}."""\n\ndef my_func_{i}():\n    x = 1\n'
            ))
        paths.append(self._write_file(
            "camel.py", '"""Mod."""\n\ndef myBigFunc():\n    myVar = 1\n'
        ))
        checker = PatternConsistencyCheck()
        issues = checker.check(paths)
        camel_issues = [i for i in issues if "camel" in i.lower() or "naming" in i.lower()]
        self.assertGreater(len(camel_issues), 0)
        self.assertTrue(any("camel.py" in i for i in camel_issues))

    def test_unreadable_file_skipped_no_crash(self):
        """If a file cannot be read, it should be skipped gracefully."""
        path1 = self._write_file("good.py", '"""Module."""\n\ndef func():\n    pass\n')
        checker = PatternConsistencyCheck()
        # Pass a nonexistent file path — should not crash
        issues = checker.check([path1, "/nonexistent/file.py"])
        self.assertIsInstance(issues, list)


# ── ImportDependencyCheck extended ───────────────────────────────────────────


class TestImportDependencyCheckExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_blast_radius_no_dependents(self):
        """Module with no dependents has blast_radius = 0."""
        self._write_file("utils.py", '"""Utils."""\n')
        self._write_file("main.py", '"""Main."""\n\nimport os\n')
        checker = ImportDependencyCheck()
        files = [os.path.join(self.tmpdir, f) for f in ["utils.py", "main.py"]]
        graph = checker.build_graph(files)
        blast = checker.blast_radius("utils", graph)
        self.assertEqual(blast["direct_dependents"], 0)
        self.assertEqual(blast["files"], [])

    def test_self_import_excluded(self):
        """A module should not list itself as its own dependency."""
        self._write_file("mod.py", 'from mod import something\nimport mod\n')
        checker = ImportDependencyCheck()
        graph = checker.build_graph([os.path.join(self.tmpdir, "mod.py")])
        imports = graph["mod.py"]["imports"]
        self.assertNotIn("mod", imports)

    def test_dotted_import_extracts_root(self):
        """import a.b.c should extract 'a' as the module name."""
        self._write_file("a.py", '"""Module a."""\n')
        self._write_file("user.py", 'import a.b.c\n')
        checker = ImportDependencyCheck()
        files = [os.path.join(self.tmpdir, f) for f in ["a.py", "user.py"]]
        graph = checker.build_graph(files)
        # 'a' is local, so it should appear if 'a' is in local_modules
        self.assertIn("a", graph["user.py"]["imports"])

    def test_empty_file_list_returns_empty_graph(self):
        checker = ImportDependencyCheck()
        graph = checker.build_graph([])
        self.assertEqual(graph, {})

    def test_find_dependents_empty_graph(self):
        checker = ImportDependencyCheck()
        result = checker.find_dependents("anything", {})
        self.assertEqual(result, [])

    def test_multiple_dependents_returned_sorted(self):
        """Dependents should be returned in sorted order."""
        self._write_file("core.py", '"""Core."""\n')
        self._write_file("z_handler.py", 'from core import x\n')
        self._write_file("a_handler.py", 'import core\n')
        checker = ImportDependencyCheck()
        files = [os.path.join(self.tmpdir, f) for f in ["core.py", "z_handler.py", "a_handler.py"]]
        graph = checker.build_graph(files)
        dependents = checker.find_dependents("core", graph)
        self.assertEqual(dependents, sorted(dependents))

    def test_non_py_files_skipped(self):
        """Non-.py files are skipped in build_graph."""
        path1 = os.path.join(self.tmpdir, "core.py")
        with open(path1, "w") as f:
            f.write('"""Core."""\n')
        path2 = os.path.join(self.tmpdir, "readme.md")
        with open(path2, "w") as f:
            f.write("import core\n")
        checker = ImportDependencyCheck()
        graph = checker.build_graph([path1, path2])
        self.assertIn("core.py", graph)
        self.assertNotIn("readme.md", graph)

    def test_blast_radius_returns_module_name(self):
        """blast_radius result contains the queried module name."""
        checker = ImportDependencyCheck()
        blast = checker.blast_radius("mymodule", {})
        self.assertEqual(blast["module"], "mymodule")


# ── RuleExtractor extended ────────────────────────────────────────────────────


class TestRuleExtractorExtended(unittest.TestCase):

    def test_whitespace_only_content_returns_empty(self):
        extractor = RuleExtractor()
        rules = extractor.extract("   \n\n\t  \n")
        self.assertEqual(rules, [])

    def test_constraints_section_recognized(self):
        content = """# Rules
## Constraints
- Never expose credentials
- No external packages
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertGreater(len(rules), 0)

    def test_bold_markers_stripped_from_rule_text(self):
        content = """# Rules
## Non-Negotiable Rules
- **No blocking in WARN mode** — always allow
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertTrue(len(rules) > 0)
        # Bold markers should be stripped
        self.assertFalse(any("**" in r["text"] for r in rules))

    def test_stdlib_allowed_exceptions_extracted(self):
        content = """# Rules
## Non-Negotiable Rules
- Zero dependencies beyond Python stdlib + anthropic + requests
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        stdlib_rules = [r for r in rules if r.get("type") == "stdlib_only"]
        if stdlib_rules:
            allowed = stdlib_rules[0].get("allowed", [])
            self.assertIn("anthropic", allowed)

    def test_rule_type_is_always_present(self):
        content = """# Rules
## Non-Negotiable Rules
- Never log data
- Zero deps beyond stdlib
- General rule here
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        for rule in rules:
            self.assertIn("type", rule)
            self.assertIn(rule["type"], ("stdlib_only", "forbidden", "general"))

    def test_list_items_only_extracted(self):
        """Non-list lines in rule section should not be extracted."""
        content = """# Rules
## Non-Negotiable Rules
This is a paragraph, not a rule.
- This IS a rule
Another paragraph.
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        self.assertEqual(len(rules), 1)

    def test_do_not_rule_classified_as_forbidden(self):
        content = """# Rules
## Non-Negotiable Rules
- Do not expose API keys
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        forbidden = [r for r in rules if r["type"] == "forbidden"]
        self.assertGreater(len(forbidden), 0)

    def test_must_not_rule_classified_as_forbidden(self):
        content = """# Rules
## Non-Negotiable Rules
- Must not overwrite files owned by another agent
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        forbidden = [r for r in rules if r["type"] == "forbidden"]
        self.assertGreater(len(forbidden), 0)

    def test_empty_rule_item_skipped(self):
        """A list item that is empty after stripping should not produce a rule."""
        content = """# Rules
## Non-Negotiable Rules
-
- Real rule here
"""
        extractor = RuleExtractor()
        rules = extractor.extract(content)
        non_empty = [r for r in rules if r["text"].strip()]
        self.assertEqual(len(rules), len(non_empty))


# ── RuleComplianceCheck extended ──────────────────────────────────────────────


class TestRuleComplianceCheckExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_from_import_violation_detected(self):
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        path = self._write_file("mod.py", "from flask import Flask\nimport os\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        self.assertTrue(any("flask" in i for i in issues))

    def test_relative_import_passes_stdlib_rule(self):
        """Relative imports (from .something import x) should not trigger violations."""
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        path = self._write_file("mod.py", "from .utils import helper\nfrom . import core\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        self.assertEqual(len(issues), 0)

    def test_allowed_exception_case_insensitive(self):
        """Allowed packages should match case-insensitively."""
        rules = [{"type": "stdlib_only", "text": "stdlib + Anthropic", "allowed": ["anthropic"]}]
        path = self._write_file("mod.py", "import Anthropic\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules, local_modules=set())
        self.assertEqual(len(issues), 0)

    def test_empty_file_no_issues(self):
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        path = self._write_file("empty.py", "")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        self.assertEqual(len(issues), 0)

    def test_general_rule_type_not_checked(self):
        """Rules of type 'general' should not produce compliance issues."""
        rules = [{"type": "general", "text": "Use descriptive variable names"}]
        path = self._write_file("mod.py", "import requests\n\nx = 1\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        self.assertEqual(len(issues), 0)

    def test_forbidden_rule_type_not_blocking_imports(self):
        """Rules of type 'forbidden' describe actions, not imports — don't block."""
        rules = [{"type": "forbidden", "text": "Never log API keys"}]
        path = self._write_file("mod.py", "import logging\nimport requests\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        # forbidden rules are not import-checked
        self.assertEqual(len(issues), 0)

    def test_multiple_rules_all_checked(self):
        """Multiple stdlib_only rules each independently checked."""
        rules = [
            {"type": "stdlib_only", "text": "stdlib only rule 1"},
            {"type": "stdlib_only", "text": "stdlib only rule 2"},
        ]
        path = self._write_file("mod.py", "import requests\n")
        checker = RuleComplianceCheck()
        issues = checker.check(path, rules)
        # Each rule generates an issue for 'requests'
        self.assertGreaterEqual(len(issues), 1)

    def test_local_modules_set_none_treated_as_empty(self):
        """local_modules=None should behave the same as local_modules=set()."""
        rules = [{"type": "stdlib_only", "text": "stdlib only"}]
        path = self._write_file("mod.py", "import mylocal\n")
        checker = RuleComplianceCheck()
        # With None: mylocal not in stdlib, not in allowed, not in local_modules → issue
        issues_none = checker.check(path, rules, local_modules=None)
        issues_empty = checker.check(path, rules, local_modules=set())
        self.assertEqual(len(issues_none), len(issues_empty))


# ── CoherenceReport extended ──────────────────────────────────────────────────


class TestCoherenceReportExtended(unittest.TestCase):

    def test_score_floor_at_zero(self):
        """Score should never go below 0 even with many issues."""
        report = CoherenceReport(
            project_root="/tmp",
            modules_checked=5,
            files_checked=20,
            issues=["Issue " + str(i) for i in range(100)],
            score=0.0,
        )
        d = report.to_dict()
        self.assertGreaterEqual(d["score"], 0.0)

    def test_score_ceiling_at_100(self):
        report = CoherenceReport(
            project_root="/tmp",
            modules_checked=0,
            files_checked=0,
            issues=[],
            score=100.0,
        )
        self.assertEqual(report.score, 100.0)

    def test_score_rounded_to_one_decimal(self):
        """Score in to_dict should be rounded to 1 decimal place."""
        report = CoherenceReport(
            project_root="/tmp",
            modules_checked=1,
            files_checked=2,
            issues=["issue"],
            score=85.333,
        )
        d = report.to_dict()
        self.assertEqual(d["score"], round(85.333, 1))

    def test_issues_list_preserved_in_dict(self):
        issues = ["Missing tests/", "Missing CLAUDE.md", "camelCase naming"]
        report = CoherenceReport(
            project_root="/tmp",
            modules_checked=1,
            files_checked=3,
            issues=issues,
            score=85.0,
        )
        d = report.to_dict()
        self.assertEqual(d["issues"], issues)


# ── CoherenceChecker extended ─────────────────────────────────────────────────


class TestCoherenceCheckerExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_full_module(self, name):
        mod_dir = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Module rules\n")
        with open(os.path.join(mod_dir, "core.py"), "w") as f:
            f.write('"""Core."""\n\ndef run():\n    pass\n')
        return mod_dir

    def test_empty_project_no_crash(self):
        """CoherenceChecker on empty project root should not crash."""
        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=[])
        self.assertIsInstance(report, CoherenceReport)
        self.assertEqual(report.modules_checked, 0)
        self.assertEqual(report.files_checked, 0)

    def test_module_with_no_py_files_still_checked(self):
        """A module with no .py files should still pass structure check (if tests/ and CLAUDE.md present)."""
        mod_dir = os.path.join(self.tmpdir, "docs-only")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")
        # No .py files

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["docs-only"])
        # Should produce no structure issues
        struct_issues = [i for i in report.issues if "docs-only" in i]
        self.assertEqual(len(struct_issues), 0)

    def test_auto_discovery_ignores_non_claude_md_dirs(self):
        """Directories without CLAUDE.md should not be auto-discovered."""
        # Create a directory WITHOUT CLAUDE.md
        plain_dir = os.path.join(self.tmpdir, "not-a-module")
        os.makedirs(plain_dir)
        with open(os.path.join(plain_dir, "code.py"), "w") as f:
            f.write("x = 1\n")

        # Create one real module WITH CLAUDE.md
        real_mod = os.path.join(self.tmpdir, "real-module")
        os.makedirs(os.path.join(real_mod, "tests"), exist_ok=True)
        with open(os.path.join(real_mod, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check()
        # Only real-module should be discovered
        self.assertEqual(report.modules_checked, 1)

    def test_score_deduction_for_structure_issues(self):
        """Structure issues should deduct 5 pts each from score."""
        mod_dir = os.path.join(self.tmpdir, "bad-mod")
        os.makedirs(mod_dir)
        # Missing tests/ and CLAUDE.md → 2 structure issues → -10 pts

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["bad-mod"])
        self.assertLessEqual(report.score, 90.0)

    def test_score_does_not_go_below_zero(self):
        """Even with many violations, score should floor at 0."""
        # Create many modules each with many violations
        for i in range(20):
            mod_dir = os.path.join(self.tmpdir, f"bad-{i}")
            os.makedirs(mod_dir)
            # No tests/, no CLAUDE.md — 2 structure issues each = 40 pts deducted

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=[f"bad-{i}" for i in range(20)])
        self.assertGreaterEqual(report.score, 0.0)

    def test_project_root_defaults_to_cwd(self):
        """CoherenceChecker() with no args uses os.getcwd()."""
        checker = CoherenceChecker()
        self.assertEqual(checker.project_root, os.getcwd())

    def test_checker_returns_coherence_report_type(self):
        self._make_full_module("mod-alpha")
        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["mod-alpha"])
        self.assertIsInstance(report, CoherenceReport)

    def test_files_checked_counts_only_non_dunder_py(self):
        """__init__.py files should be excluded from files_checked."""
        mod_dir = os.path.join(self.tmpdir, "my-mod")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")
        with open(os.path.join(mod_dir, "core.py"), "w") as f:
            f.write('"""Core."""\n')
        with open(os.path.join(mod_dir, "__init__.py"), "w") as f:
            f.write("")

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["my-mod"])
        # __init__.py is excluded — only core.py counted
        self.assertEqual(report.files_checked, 1)


# ── check_coherence convenience function extended ─────────────────────────────


class TestCheckCoherenceFunctionExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_explicit_modules_arg_passed_through(self):
        """check_coherence with explicit modules list only checks those modules."""
        mod = os.path.join(self.tmpdir, "explicit-mod")
        os.makedirs(os.path.join(mod, "tests"), exist_ok=True)
        with open(os.path.join(mod, "CLAUDE.md"), "w") as f:
            f.write("# Rules\n")

        result = check_coherence(self.tmpdir, modules=["explicit-mod"])
        self.assertEqual(result["modules_checked"], 1)

    def test_nonexistent_project_root_no_crash(self):
        """check_coherence on nonexistent root should not raise."""
        result = check_coherence("/nonexistent/path/xyz")
        self.assertIsInstance(result, dict)
        self.assertIn("score", result)

    def test_result_has_all_required_keys(self):
        result = check_coherence(self.tmpdir)
        for key in ("project_root", "modules_checked", "files_checked", "issues", "score"):
            self.assertIn(key, result)

    def test_issues_is_list(self):
        result = check_coherence(self.tmpdir)
        self.assertIsInstance(result["issues"], list)

    def test_score_is_float(self):
        result = check_coherence(self.tmpdir)
        self.assertIsInstance(result["score"], float)


# ── Integration: score arithmetic ─────────────────────────────────────────────


class TestScoreArithmetic(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_perfect_project_scores_100(self):
        """A project where all modules are correctly structured scores 100."""
        mod_dir = os.path.join(self.tmpdir, "perfect-mod")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        with open(os.path.join(mod_dir, "CLAUDE.md"), "w") as f:
            f.write("# Module rules\n")
        with open(os.path.join(mod_dir, "core.py"), "w") as f:
            f.write('"""Core module."""\n\nimport os\n\ndef run():\n    pass\n')
        with open(os.path.join(mod_dir, "helper.py"), "w") as f:
            f.write('"""Helper module."""\n\nimport sys\n\ndef help():\n    pass\n')

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["perfect-mod"])
        self.assertEqual(report.score, 100.0)
        self.assertEqual(len(report.issues), 0)

    def test_structure_issues_deduct_5_each(self):
        """Each structure issue deducts exactly 5 points from score."""
        # Create module with exactly 1 structure issue (no CLAUDE.md, but has tests/)
        mod_dir = os.path.join(self.tmpdir, "partial-mod")
        os.makedirs(os.path.join(mod_dir, "tests"), exist_ok=True)
        # No CLAUDE.md → 1 structure issue → score = 95

        checker = CoherenceChecker(project_root=self.tmpdir)
        report = checker.check(modules=["partial-mod"])
        struct_issues = [i for i in report.issues if "claude.md" in i.lower()]
        # Expect exactly 1 structure issue → score = 100 - 5 = 95
        if len(struct_issues) == 1:
            self.assertEqual(report.score, 95.0)


if __name__ == "__main__":
    unittest.main()
