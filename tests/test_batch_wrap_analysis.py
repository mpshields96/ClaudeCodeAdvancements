#!/usr/bin/env python3
"""Tests for batch_wrap_analysis.py — consolidated wrap Steps 6b-6h."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import batch_wrap_analysis as bwa


class TestStepFunctions(unittest.TestCase):
    """Test individual analysis steps."""

    def test_step_6b_reflect_brief_runs(self):
        result = bwa.step_6b_reflect_brief()
        self.assertEqual(result["step"], "6b_reflect")
        self.assertIn("ok", result)
        self.assertIn("output", result)

    def test_step_6c_escalate_no_learnings(self):
        with patch.object(bwa, "LEARNINGS_PATH", Path("/nonexistent/LEARNINGS.md")):
            result = bwa.step_6c_escalate_check()
        self.assertTrue(result["ok"])
        self.assertIn("No LEARNINGS.md", result["output"])

    def test_step_6c_escalate_with_learnings(self):
        """Test escalation check with mock LEARNINGS.md content."""
        import tempfile
        content = """# LEARNINGS

### Test Pattern — Severity: 3 — Count: 4
- Anti-pattern: doing bad thing
- Fix: do good thing
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            with patch.object(bwa, "LEARNINGS_PATH", Path(f.name)):
                with patch.object(bwa, "RULES_DIR", Path("/nonexistent")):
                    result = bwa.step_6c_escalate_check()
        os.unlink(f.name)
        self.assertTrue(result["ok"])
        self.assertIn("PROMOTE TO RULE", result["output"])

    def test_step_6c_no_promotion_needed(self):
        """Low severity entries don't trigger promotion."""
        import tempfile
        content = """# LEARNINGS

### Minor Issue — Severity: 1 — Count: 1
- Anti-pattern: small thing
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            with patch.object(bwa, "LEARNINGS_PATH", Path(f.name)):
                result = bwa.step_6c_escalate_check()
        os.unlink(f.name)
        self.assertIn("No learnings qualify", result["output"])

    def test_step_6e_no_changelog(self):
        with patch.object(bwa, "CHANGELOG_PATH", Path("/nonexistent/CHANGELOG.md")):
            result = bwa.step_6e_recurring_antipatterns(240)
        self.assertTrue(result["ok"])
        self.assertIn("No CHANGELOG.md", result["output"])

    def test_step_6f_no_skillbook(self):
        with patch.object(bwa, "SKILLBOOK_PATH", Path("/nonexistent/SKILLBOOK.md")):
            result = bwa.step_6f_skillbook_evolution(240, "B", ["win1"], ["loss1"])
        self.assertTrue(result["ok"])
        self.assertIn("No SKILLBOOK.md", result["output"])

    def test_step_6g5_sentinel_runs(self):
        result = bwa.step_6g5_sentinel()
        self.assertEqual(result["step"], "6g5_sentinel")
        self.assertIn("ok", result)

    def test_step_6h_validate_runs(self):
        result = bwa.step_6h_validate()
        self.assertEqual(result["step"], "6h_validate")
        self.assertIn("ok", result)


class TestRunAll(unittest.TestCase):
    """Test the batch runner."""

    def test_run_all_returns_7_results(self):
        results = bwa.run_all(240, "B", ["win1"], ["loss1"])
        self.assertEqual(len(results), 7)

    def test_run_all_step_names(self):
        results = bwa.run_all(240, "A", ["win"], [])
        step_names = [r["step"] for r in results]
        self.assertEqual(step_names, [
            "6b_reflect", "6c_escalate", "6d_apply",
            "6e_antipatterns", "6f_skillbook", "6g5_sentinel", "6h_validate",
        ])


class TestFormatSummary(unittest.TestCase):
    """Test output formatting."""

    def test_format_summary_header(self):
        results = [
            {"step": "test_step", "ok": True, "output": "all good"},
        ]
        text = bwa.format_summary(results)
        self.assertIn("SESSION LEARNING (batch_wrap_analysis):", text)
        self.assertIn("[OK] test_step", text)
        self.assertIn("1 OK, 0 failed", text)

    def test_format_summary_failure(self):
        results = [
            {"step": "bad_step", "ok": False, "output": "something broke"},
        ]
        text = bwa.format_summary(results)
        self.assertIn("[FAIL] bad_step", text)
        self.assertIn("0 OK, 1 failed", text)

    def test_format_truncates_long_output(self):
        results = [
            {"step": "verbose", "ok": True, "output": "x" * 500},
        ]
        text = bwa.format_summary(results)
        # Output should be capped at 200 chars
        self.assertTrue(len(text) < 500)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_runs(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "batch_wrap_analysis.py"),
             "--session", "999", "--grade", "A",
             "--wins", "test_win", "--losses", "test_loss"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("SESSION LEARNING", result.stdout)

    def test_cli_json_output(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "batch_wrap_analysis.py"),
             "--session", "999", "--grade", "B", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 7)

    def test_cli_rejects_invalid_grade(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "batch_wrap_analysis.py"),
             "--session", "999", "--grade", "F"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)


class TestRunScript(unittest.TestCase):
    """Test the _run_script helper."""

    def test_run_nonexistent_script(self):
        ok, output = bwa._run_script(["/nonexistent/script.py"], "test")
        self.assertFalse(ok)

    def test_run_valid_script(self):
        ok, output = bwa._run_script(["-c", "print('hello')"], "test")
        self.assertTrue(ok)
        self.assertIn("hello", output)


if __name__ == "__main__":
    unittest.main()
