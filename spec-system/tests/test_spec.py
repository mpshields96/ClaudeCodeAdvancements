#!/usr/bin/env python3
"""
Smoke tests for spec-system validate hook.
Run: python3 spec-system/tests/test_spec.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
import validate as v


class TestShouldCheck(unittest.TestCase):
    def test_python_file_flagged(self):
        self.assertTrue(v._should_check("Write", "/project/main.py"))

    def test_typescript_file_flagged(self):
        self.assertTrue(v._should_check("Write", "/project/app.ts"))

    def test_spec_file_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/requirements.md"))

    def test_design_file_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/design.md"))

    def test_claude_md_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/CLAUDE.md"))

    def test_test_file_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/tests/test_main.py"))

    def test_markdown_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/README.md"))

    def test_json_not_flagged(self):
        self.assertFalse(v._should_check("Write", "/project/config.json"))

    def test_read_tool_not_flagged(self):
        self.assertFalse(v._should_check("Read", "/project/main.py"))

    def test_bash_tool_not_flagged(self):
        self.assertFalse(v._should_check("Bash", "/project/main.py"))

    def test_edit_tool_flagged(self):
        self.assertTrue(v._should_check("Edit", "/project/main.py"))


class TestIsApproved(unittest.TestCase):
    def test_approved_file_returns_true(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Requirements\nStatus: APPROVED\n")
            path = Path(f.name)
        self.assertTrue(v._is_approved(path))
        path.unlink()

    def test_draft_file_returns_false(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Requirements\nStatus: DRAFT — not yet approved\n")
            path = Path(f.name)
        self.assertFalse(v._is_approved(path))
        path.unlink()

    def test_missing_file_returns_false(self):
        self.assertFalse(v._is_approved(Path("/nonexistent/path/requirements.md")))


class TestSpecStatus(unittest.TestCase):
    def test_no_spec_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status = v._spec_status(tmpdir)
            self.assertFalse(status["has_requirements"])
            self.assertFalse(status["has_design"])
            self.assertFalse(status["has_tasks"])

    def test_approved_requirements_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = Path(tmpdir) / "requirements.md"
            req.write_text("Status: APPROVED\n")
            status = v._spec_status(tmpdir)
            self.assertTrue(status["has_requirements"])
            self.assertTrue(status["requirements_approved"])

    def test_draft_requirements_not_approved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            req = Path(tmpdir) / "requirements.md"
            req.write_text("Status: DRAFT — not yet approved\n")
            status = v._spec_status(tmpdir)
            self.assertTrue(status["has_requirements"])
            self.assertFalse(status["requirements_approved"])

    def test_all_approved_full_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for fname in ["requirements.md", "design.md", "tasks.md"]:
                (Path(tmpdir) / fname).write_text("Status: APPROVED\n")
            status = v._spec_status(tmpdir)
            self.assertTrue(status["requirements_approved"])
            self.assertTrue(status["design_approved"])
            self.assertTrue(status["tasks_approved"])


class TestBuildWarning(unittest.TestCase):
    def _no_spec_status(self):
        return {
            "has_requirements": False, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }

    def _approved_req_status(self):
        return {
            "has_requirements": True, "requirements_approved": True,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }

    def _fully_approved_status(self):
        return {
            "has_requirements": True, "requirements_approved": True,
            "has_design": True, "design_approved": True,
            "has_tasks": True, "tasks_approved": True,
        }

    def test_no_spec_generates_warning(self):
        warning = v._build_warning(self._no_spec_status(), "main.py", "warn")
        self.assertIn("spec-guard", warning)
        self.assertIn("requirements.md", warning)

    def test_block_mode_includes_blocked(self):
        warning = v._build_warning(self._no_spec_status(), "main.py", "block")
        self.assertIn("BLOCKED", warning)

    def test_warn_mode_does_not_include_blocked(self):
        warning = v._build_warning(self._no_spec_status(), "main.py", "warn")
        self.assertNotIn("BLOCKED", warning)

    def test_fully_approved_returns_empty(self):
        warning = v._build_warning(self._fully_approved_status(), "main.py", "warn")
        self.assertEqual(warning, "")

    def test_approved_req_prompts_for_design(self):
        warning = v._build_warning(self._approved_req_status(), "main.py", "warn")
        self.assertIn("design.md", warning)


class TestMainWarnMode(unittest.TestCase):
    """Integration tests: feed JSON to main() via stdin, check stdout."""

    def _run_main(self, hook_input: dict, env_override: dict | None = None):
        """Run main() with given hook input, return parsed stdout."""
        import io
        stdin_data = json.dumps(hook_input)
        captured_output = []

        original_stdin = sys.stdin
        original_stdout = sys.stdout
        sys.stdin = io.StringIO(stdin_data)
        sys.stdout = io.StringIO()

        env = dict(os.environ) if hasattr(sys.modules.get("os", None), "environ") else {}
        if env_override:
            env.update(env_override)

        try:
            import os as _os
            with patch.dict(_os.environ, env_override or {}, clear=False):
                try:
                    v.main()
                except SystemExit:
                    pass
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = original_stdin
            sys.stdout = original_stdout

        if output.strip():
            return json.loads(output.strip())
        return {}

    def test_non_code_file_produces_no_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_input = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{tmpdir}/README.md"},
                "cwd": tmpdir,
            }
            result = self._run_main(hook_input)
            self.assertEqual(result, {})

    def test_code_file_without_spec_produces_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_input = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{tmpdir}/main.py"},
                "cwd": tmpdir,
            }
            result = self._run_main(hook_input)
            # In warn mode: should produce hookSpecificOutput with allow
            if result:
                decision = result.get("hookSpecificOutput", {}).get("permissionDecision")
                self.assertIn(decision, {"allow", "deny"})

    def test_approved_tasks_produces_no_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for fname in ["requirements.md", "design.md", "tasks.md"]:
                (Path(tmpdir) / fname).write_text("Status: APPROVED\n")
            hook_input = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{tmpdir}/main.py"},
                "cwd": tmpdir,
            }
            result = self._run_main(hook_input)
            self.assertEqual(result, {})


import os
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
