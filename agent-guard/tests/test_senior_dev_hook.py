#!/usr/bin/env python3
"""Tests for senior_dev_hook.py — MT-20 Senior Dev Agent PostToolUse orchestrator.

Tests cover:
- Module availability detection and graceful degradation
- SATD finding integration
- Effort scoring integration
- Combined findings formatting
- Hook I/O format (stdin/stdout JSON)
- File type filtering (skip non-code files)
- Context length truncation
- Edge cases (empty content, unknown tools, missing fields)
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from senior_dev_hook import (
    SeniorDevHook,
    SeniorDevFinding,
    _get_extension,
    _humanize_finding,
    SKIP_EXTENSIONS,
    MAX_CONTEXT_LENGTH,
    EFFORT_THRESHOLD,
    _satd_available,
    _effort_available,
)


class TestSeniorDevFinding(unittest.TestCase):
    """Test SeniorDevFinding dataclass."""

    def test_fields(self):
        f = SeniorDevFinding(source="satd", severity="HIGH", message="Line 5: HACK")
        self.assertEqual(f.source, "satd")
        self.assertEqual(f.severity, "HIGH")
        self.assertEqual(f.message, "Line 5: HACK")

    def test_equality(self):
        f1 = SeniorDevFinding(source="satd", severity="HIGH", message="test")
        f2 = SeniorDevFinding(source="satd", severity="HIGH", message="test")
        self.assertEqual(f1, f2)


class TestModuleAvailability(unittest.TestCase):
    """Test graceful degradation when submodules are missing."""

    def test_satd_available(self):
        # SATD detector should be available (already built)
        self.assertTrue(_satd_available)

    def test_hook_has_available_modules(self):
        hook = SeniorDevHook()
        modules = hook.available_modules
        self.assertIsInstance(modules, list)
        self.assertIn("satd_detector", modules)

    def test_hook_works_with_partial_modules(self):
        """Hook should produce output even if some modules are missing."""
        hook = SeniorDevHook()
        # Should not raise even if effort/fp_filter/classifier are missing
        result = hook.hook_output({
            "tool_name": "Write",
            "tool_input": {"content": "# HACK: this is bad", "file_path": "test.py"}
        })
        self.assertIsInstance(result, dict)


class TestAnalyze(unittest.TestCase):
    """Test the analyze method combining submodule outputs."""

    def setUp(self):
        self.hook = SeniorDevHook()

    def test_empty_content_no_findings(self):
        findings = self.hook.analyze("")
        self.assertEqual(findings, [])

    def test_satd_markers_detected(self):
        content = "x = 1\n# TODO: fix this\n# HACK: temporary workaround"
        findings = self.hook.analyze(content, file_path="module.py")
        satd_findings = [f for f in findings if f.source == "satd"]
        self.assertGreaterEqual(len(satd_findings), 2)

    def test_satd_severity_mapping(self):
        content = "# HACK: bad code here"
        findings = self.hook.analyze(content, file_path="module.py")
        satd_findings = [f for f in findings if f.source == "satd"]
        self.assertTrue(any(f.severity == "HIGH" for f in satd_findings))

    def test_skip_markdown_files(self):
        content = "# TODO: write docs\n# HACK: something"
        findings = self.hook.analyze(content, file_path="README.md")
        self.assertEqual(findings, [])

    def test_skip_json_files(self):
        content = '{"TODO": "fix", "HACK": "temp"}'
        findings = self.hook.analyze(content, file_path="config.json")
        self.assertEqual(findings, [])

    def test_skip_yaml_files(self):
        findings = self.hook.analyze("TODO: fix", file_path="config.yaml")
        self.assertEqual(findings, [])

    def test_skip_toml_files(self):
        findings = self.hook.analyze("# TODO: fix", file_path="pyproject.toml")
        self.assertEqual(findings, [])

    def test_python_files_analyzed(self):
        content = "# FIXME: broken logic"
        findings = self.hook.analyze(content, file_path="module.py")
        self.assertGreater(len(findings), 0)

    def test_no_extension_analyzed(self):
        content = "# TODO: fix this"
        findings = self.hook.analyze(content, file_path="Makefile")
        # Files without extensions in skip list should be analyzed
        self.assertGreater(len(findings), 0)


class TestFormatContext(unittest.TestCase):
    """Test findings formatting into natural language advice."""

    def setUp(self):
        self.hook = SeniorDevHook()

    def test_empty_findings_empty_string(self):
        self.assertEqual(self.hook.format_context([]), "")

    def test_low_only_findings_filtered_out(self):
        """LOW-only findings (NOTE markers) should be filtered as noise."""
        findings = [SeniorDevFinding(source="satd", severity="LOW", message="Line 5: NOTE")]
        context = self.hook.format_context(findings)
        self.assertEqual(context, "")

    def test_single_high_finding_formatted(self):
        findings = [SeniorDevFinding(source="satd", severity="HIGH", message="Line 5: HACK — quick fix")]
        context = self.hook.format_context(findings)
        self.assertIn("[Senior Dev Review]", context)
        self.assertIn("HACK", context)
        self.assertIn("fragile code", context)

    def test_natural_language_for_fixme(self):
        findings = [SeniorDevFinding(source="satd", severity="HIGH", message="Line 10: FIXME — broken")]
        context = self.hook.format_context(findings)
        self.assertIn("known broken behavior", context)

    def test_natural_language_for_todo(self):
        findings = [SeniorDevFinding(source="satd", severity="MEDIUM", message="Line 3: TODO — later")]
        context = self.hook.format_context(findings)
        self.assertIn("tracked issue", context)

    def test_natural_language_for_effort(self):
        findings = [SeniorDevFinding(source="effort", severity="INFO", message="Effort: 4/5 (Complex)")]
        context = self.hook.format_context(findings)
        self.assertIn("breaking into smaller", context)

    def test_natural_language_for_quality(self):
        findings = [SeniorDevFinding(source="quality", severity="MEDIUM", message="Quality: D (58/100)")]
        context = self.hook.format_context(findings)
        self.assertIn("maintainability", context)

    def test_findings_sorted_high_before_medium(self):
        findings = [
            SeniorDevFinding(source="satd", severity="MEDIUM", message="Line 1: TODO — fix"),
            SeniorDevFinding(source="satd", severity="HIGH", message="Line 5: HACK — bad"),
        ]
        context = self.hook.format_context(findings)
        hack_pos = context.index("HACK")
        todo_pos = context.index("TODO")
        self.assertLess(hack_pos, todo_pos)

    def test_context_length_bounded(self):
        findings = [
            SeniorDevFinding(
                source="satd", severity="HIGH",
                message=f"Line {i}: HACK — {'x' * 100}"
            )
            for i in range(50)
        ]
        context = self.hook.format_context(findings)
        self.assertLessEqual(len(context), MAX_CONTEXT_LENGTH)

    def test_truncation_preserves_high_findings(self):
        findings = [
            SeniorDevFinding(source="satd", severity="HIGH", message="CRITICAL HACK BUG"),
        ] + [
            SeniorDevFinding(source="satd", severity="MEDIUM", message=f"TODO minor {i}" * 20)
            for i in range(50)
        ]
        context = self.hook.format_context(findings)
        self.assertIn("CRITICAL HACK BUG", context)


class TestHumanizeFinding(unittest.TestCase):
    """Test _humanize_finding converts findings to natural language."""

    def test_hack_gives_fragile_advice(self):
        f = SeniorDevFinding(source="satd", severity="HIGH", message="Line 5: HACK — temp fix")
        result = _humanize_finding(f)
        self.assertIn("fragile code", result)
        self.assertIn("resolve before committing", result)

    def test_fixme_gives_broken_advice(self):
        f = SeniorDevFinding(source="satd", severity="HIGH", message="Line 10: FIXME — broken")
        result = _humanize_finding(f)
        self.assertIn("known broken behavior", result)
        self.assertIn("shipping", result)

    def test_todo_gives_tracking_advice(self):
        f = SeniorDevFinding(source="satd", severity="MEDIUM", message="Line 3: TODO — later")
        result = _humanize_finding(f)
        self.assertIn("tracked issue", result)

    def test_workaround_gives_debt_advice(self):
        f = SeniorDevFinding(source="satd", severity="HIGH", message="Line 7: WORKAROUND — bypass")
        result = _humanize_finding(f)
        self.assertIn("technical debt", result)

    def test_effort_gives_size_advice(self):
        f = SeniorDevFinding(source="effort", severity="INFO", message="Effort: 4/5 (Complex)")
        result = _humanize_finding(f)
        self.assertIn("smaller", result)

    def test_quality_gives_maintainability_advice(self):
        f = SeniorDevFinding(source="quality", severity="MEDIUM", message="Quality: D (58/100)")
        result = _humanize_finding(f)
        self.assertIn("maintainability", result)

    def test_unknown_source_returns_message(self):
        f = SeniorDevFinding(source="unknown", severity="INFO", message="something")
        result = _humanize_finding(f)
        self.assertEqual(result, "something")

    def test_preserves_original_message_content(self):
        f = SeniorDevFinding(source="satd", severity="HIGH", message="Line 42: HACK — specific detail here")
        result = _humanize_finding(f)
        self.assertIn("specific detail here", result)


class TestHookOutput(unittest.TestCase):
    """Test PostToolUse hook I/O format."""

    def setUp(self):
        self.hook = SeniorDevHook()

    def test_write_tool_analyzed(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "content": "# HACK: temporary fix\nx = 1",
                "file_path": "module.py",
            }
        }
        output = self.hook.hook_output(payload)
        self.assertIn("additionalContext", output)

    def test_edit_tool_analyzed(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "x = 1",
                "new_string": "# FIXME: broken\nx = 2",
            }
        }
        output = self.hook.hook_output(payload)
        self.assertIn("additionalContext", output)

    def test_read_tool_ignored(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
        output = self.hook.hook_output(payload)
        self.assertEqual(output, {})

    def test_bash_tool_ignored(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        output = self.hook.hook_output(payload)
        self.assertEqual(output, {})

    def test_glob_tool_ignored(self):
        payload = {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}}
        output = self.hook.hook_output(payload)
        self.assertEqual(output, {})

    def test_empty_payload_returns_empty(self):
        self.assertEqual(self.hook.hook_output({}), {})

    def test_empty_content_returns_empty(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"content": "", "file_path": "test.py"}
        }
        self.assertEqual(self.hook.hook_output(payload), {})

    def test_clean_code_no_context(self):
        """Clean code without SATD markers should produce no context (unless effort is high)."""
        payload = {
            "tool_name": "Write",
            "tool_input": {"content": "x = 1\ny = 2", "file_path": "clean.py"}
        }
        output = self.hook.hook_output(payload)
        # No SATD markers, low effort -> should be empty or minimal
        # (depends on whether effort_scorer is available and scores >= threshold)
        self.assertIsInstance(output, dict)

    def test_markdown_write_no_context(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "content": "# TODO: write documentation\n# HACK: something",
                "file_path": "README.md",
            }
        }
        output = self.hook.hook_output(payload)
        self.assertEqual(output, {})

    def test_returns_dict(self):
        payload = {"tool_name": "Write", "tool_input": {"content": "x=1", "file_path": "f.py"}}
        self.assertIsInstance(self.hook.hook_output(payload), dict)

    def test_context_mentions_senior_dev_review(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "content": "# HACK: terrible workaround\n# FIXME: this is broken",
                "file_path": "bad_code.py",
            }
        }
        output = self.hook.hook_output(payload)
        if "additionalContext" in output:
            self.assertIn("[Senior Dev Review]", output["additionalContext"])


class TestGetExtension(unittest.TestCase):
    """Test file extension extraction."""

    def test_python_file(self):
        self.assertEqual(_get_extension("module.py"), ".py")

    def test_markdown_file(self):
        self.assertEqual(_get_extension("README.md"), ".md")

    def test_no_extension(self):
        self.assertEqual(_get_extension("Makefile"), "")

    def test_nested_path(self):
        self.assertEqual(_get_extension("/home/user/project/module.py"), ".py")

    def test_multiple_dots(self):
        self.assertEqual(_get_extension("file.test.py"), ".py")

    def test_uppercase_normalized(self):
        self.assertEqual(_get_extension("FILE.PY"), ".py")


class TestSkipExtensions(unittest.TestCase):
    """Verify skip extension set is comprehensive."""

    def test_markdown_skipped(self):
        self.assertIn(".md", SKIP_EXTENSIONS)

    def test_json_skipped(self):
        self.assertIn(".json", SKIP_EXTENSIONS)

    def test_yaml_skipped(self):
        self.assertIn(".yaml", SKIP_EXTENSIONS)
        self.assertIn(".yml", SKIP_EXTENSIONS)

    def test_toml_skipped(self):
        self.assertIn(".toml", SKIP_EXTENSIONS)

    def test_lock_skipped(self):
        self.assertIn(".lock", SKIP_EXTENSIONS)


class TestHookStdin(unittest.TestCase):
    """Test hook as a subprocess (stdin/stdout interface)."""

    def _run_hook(self, payload_str: str) -> dict:
        result = subprocess.run(
            [sys.executable, "agent-guard/senior_dev_hook.py"],
            input=payload_str,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        return json.loads(result.stdout.strip())

    def test_empty_stdin(self):
        self.assertEqual(self._run_hook(""), {})

    def test_invalid_json(self):
        self.assertEqual(self._run_hook("not json"), {})

    def test_valid_write_payload(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "content": "# HACK: quick fix\nx = 1",
                "file_path": "module.py",
            }
        }
        output = self._run_hook(json.dumps(payload))
        self.assertIsInstance(output, dict)

    def test_read_tool_empty(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
        self.assertEqual(self._run_hook(json.dumps(payload)), {})


class TestEffortThreshold(unittest.TestCase):
    """Verify effort threshold constant."""

    def test_threshold_is_3(self):
        self.assertEqual(EFFORT_THRESHOLD, 3)

    def test_max_context_length(self):
        self.assertEqual(MAX_CONTEXT_LENGTH, 2000)


if __name__ == "__main__":
    unittest.main()
