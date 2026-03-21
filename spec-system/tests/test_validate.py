#!/usr/bin/env python3
"""Tests for spec-system/hooks/validate.py — PreToolUse spec validation hook."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add spec-system/hooks to path
_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
_SPEC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS_DIR))
sys.path.insert(0, str(_SPEC_DIR))

from validate import (
    _find_spec_file,
    _is_approved,
    _spec_status,
    _should_check,
    _build_warning,
    _check_freshness_context,
    _CODE_EXTENSIONS,
    _ALWAYS_ALLOWED_NAMES,
    _WRITE_TOOLS,
)


class TestFindSpecFile(unittest.TestCase):
    """Test _find_spec_file — walks up directories to find spec files."""

    def test_finds_file_in_current_dir(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "requirements.md"
            spec.write_text("test", encoding="utf-8")
            result = _find_spec_file(td, "requirements.md")
            self.assertIsNotNone(result)
            self.assertEqual(result.name, "requirements.md")

    def test_finds_file_in_parent_dir(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "requirements.md"
            spec.write_text("test", encoding="utf-8")
            child = Path(td) / "subdir"
            child.mkdir()
            result = _find_spec_file(str(child), "requirements.md")
            self.assertIsNotNone(result)

    def test_returns_none_if_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            result = _find_spec_file(td, "nonexistent.md")
            self.assertIsNone(result)

    def test_stops_at_filesystem_root(self):
        # Searching from a dir without the file should eventually return None
        result = _find_spec_file("/tmp", "unlikely_spec_file_99999.md")
        self.assertIsNone(result)

    def test_finds_design_md(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "design.md"
            spec.write_text("test", encoding="utf-8")
            result = _find_spec_file(td, "design.md")
            self.assertIsNotNone(result)

    def test_finds_tasks_md(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "tasks.md"
            spec.write_text("test", encoding="utf-8")
            result = _find_spec_file(td, "tasks.md")
            self.assertIsNotNone(result)


class TestIsApproved(unittest.TestCase):
    """Test _is_approved — checks for 'Status: APPROVED' in spec files."""

    def test_approved_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Requirements\nStatus: APPROVED\n## Content")
            f.flush()
            self.assertTrue(_is_approved(Path(f.name)))
            os.unlink(f.name)

    def test_not_approved_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Requirements\nStatus: DRAFT\n## Content")
            f.flush()
            self.assertFalse(_is_approved(Path(f.name)))
            os.unlink(f.name)

    def test_missing_file(self):
        self.assertFalse(_is_approved(Path("/nonexistent/path.md")))

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            f.flush()
            self.assertFalse(_is_approved(Path(f.name)))
            os.unlink(f.name)

    def test_approved_anywhere_in_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("lots of content\nmore content\nStatus: APPROVED\nfooter")
            f.flush()
            self.assertTrue(_is_approved(Path(f.name)))
            os.unlink(f.name)


class TestSpecStatus(unittest.TestCase):
    """Test _spec_status — returns dict of spec file states."""

    def test_no_specs(self):
        with tempfile.TemporaryDirectory() as td:
            status = _spec_status(td)
            self.assertFalse(status["has_requirements"])
            self.assertFalse(status["has_design"])
            self.assertFalse(status["has_tasks"])

    def test_requirements_only(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "requirements.md").write_text("Status: APPROVED")
            status = _spec_status(td)
            self.assertTrue(status["has_requirements"])
            self.assertTrue(status["requirements_approved"])
            self.assertFalse(status["has_design"])

    def test_all_approved(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ["requirements.md", "design.md", "tasks.md"]:
                (Path(td) / name).write_text(f"# {name}\nStatus: APPROVED")
            status = _spec_status(td)
            self.assertTrue(status["requirements_approved"])
            self.assertTrue(status["design_approved"])
            self.assertTrue(status["tasks_approved"])

    def test_requirements_draft(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "requirements.md").write_text("Status: DRAFT")
            status = _spec_status(td)
            self.assertTrue(status["has_requirements"])
            self.assertFalse(status["requirements_approved"])


class TestShouldCheck(unittest.TestCase):
    """Test _should_check — determines if spec guard should fire."""

    def test_write_python_file(self):
        self.assertTrue(_should_check("Write", "module.py"))

    def test_edit_python_file(self):
        self.assertTrue(_should_check("Edit", "module.py"))

    def test_notebook_edit(self):
        self.assertTrue(_should_check("NotebookEdit", "notebook.py"))

    def test_non_write_tool(self):
        self.assertFalse(_should_check("Read", "module.py"))
        self.assertFalse(_should_check("Bash", "module.py"))
        self.assertFalse(_should_check("Glob", "module.py"))

    def test_allowed_names(self):
        for name in _ALWAYS_ALLOWED_NAMES:
            self.assertFalse(_should_check("Write", name),
                           f"Should allow {name}")

    def test_non_code_extension(self):
        self.assertFalse(_should_check("Write", "notes.md"))
        self.assertFalse(_should_check("Write", "data.json"))
        self.assertFalse(_should_check("Write", "config.yaml"))
        self.assertFalse(_should_check("Write", "style.css"))

    def test_code_extensions(self):
        for ext in [".py", ".js", ".ts", ".go", ".rs", ".swift", ".java"]:
            self.assertTrue(_should_check("Write", f"file{ext}"),
                          f"Should check {ext}")

    def test_test_files_allowed(self):
        self.assertFalse(_should_check("Write", "test_module.py"))
        self.assertFalse(_should_check("Write", "module_test.py"))

    def test_empty_tool_name(self):
        self.assertFalse(_should_check("", "module.py"))

    def test_empty_file_path(self):
        # Empty path has no suffix or name match
        self.assertFalse(_should_check("Write", ""))


class TestBuildWarning(unittest.TestCase):
    """Test _build_warning — generates warning messages."""

    def test_no_requirements(self):
        status = {
            "has_requirements": False, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "module.py", "warn")
        self.assertIn("spec-guard", warning)
        self.assertIn("requirements.md", warning)
        self.assertIn("warn-only", warning)

    def test_requirements_not_approved(self):
        status = {
            "has_requirements": True, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "module.py", "warn")
        self.assertIn("approval", warning)

    def test_requirements_approved_no_design(self):
        status = {
            "has_requirements": True, "requirements_approved": True,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "module.py", "warn")
        self.assertIn("design.md", warning)

    def test_all_approved_no_warning(self):
        status = {
            "has_requirements": True, "requirements_approved": True,
            "has_design": True, "design_approved": True,
            "has_tasks": True, "tasks_approved": True,
        }
        warning = _build_warning(status, "module.py", "warn")
        self.assertEqual(warning, "")

    def test_block_mode(self):
        status = {
            "has_requirements": False, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "module.py", "block")
        self.assertIn("BLOCKED", warning)

    def test_warn_mode(self):
        status = {
            "has_requirements": False, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "module.py", "warn")
        self.assertIn("warn-only", warning)
        self.assertNotIn("BLOCKED", warning)

    def test_file_name_in_warning(self):
        status = {
            "has_requirements": False, "requirements_approved": False,
            "has_design": False, "design_approved": False,
            "has_tasks": False, "tasks_approved": False,
        }
        warning = _build_warning(status, "/path/to/my_module.py", "warn")
        self.assertIn("my_module.py", warning)


class TestCheckFreshnessContext(unittest.TestCase):
    """Test _check_freshness_context — spec staleness detection."""

    def test_returns_empty_when_no_specs(self):
        with tempfile.TemporaryDirectory() as td:
            result = _check_freshness_context(td)
            self.assertEqual(result, "")

    def test_returns_empty_on_import_error(self):
        # If spec_freshness isn't importable, should return empty
        with patch.dict(sys.modules, {"spec_freshness": None}):
            result = _check_freshness_context("/nonexistent")
            self.assertEqual(result, "")


class TestMainHookIntegration(unittest.TestCase):
    """Integration tests — run validate.py as subprocess with hook JSON input."""

    def _run_hook(self, hook_input: dict, env_override: dict = None) -> tuple:
        """Run validate.py as subprocess, return (stdout, returncode)."""
        env = os.environ.copy()
        if env_override:
            env.update(env_override)

        hook_path = str(_HOOKS_DIR / "validate.py")
        proc = subprocess.run(
            [sys.executable, hook_path],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        return proc.stdout.strip(), proc.returncode

    def test_non_pretooluse_exits_silently(self):
        stdout, rc = self._run_hook({
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "module.py"},
            "cwd": "/tmp",
        })
        self.assertEqual(rc, 0)
        self.assertEqual(stdout, "")

    def test_read_tool_exits_silently(self):
        stdout, rc = self._run_hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "module.py"},
            "cwd": "/tmp",
        })
        self.assertEqual(rc, 0)
        self.assertEqual(stdout, "")

    def test_write_code_without_spec_warns(self):
        with tempfile.TemporaryDirectory() as td:
            stdout, rc = self._run_hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{td}/new_module.py"},
                "cwd": td,
            })
            self.assertEqual(rc, 0)
            if stdout:
                result = json.loads(stdout)
                decision = result["hookSpecificOutput"]["permissionDecision"]
                self.assertEqual(decision, "allow")
                self.assertIn("spec-guard", result["hookSpecificOutput"]["additionalContext"])

    def test_write_code_in_block_mode_denies(self):
        with tempfile.TemporaryDirectory() as td:
            stdout, rc = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": f"{td}/new_module.py"},
                    "cwd": td,
                },
                env_override={"SPEC_GUARD_MODE": "block"},
            )
            self.assertEqual(rc, 0)
            if stdout:
                result = json.loads(stdout)
                decision = result["hookSpecificOutput"]["permissionDecision"]
                self.assertEqual(decision, "deny")

    def test_write_test_file_always_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            stdout, rc = self._run_hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{td}/test_module.py"},
                "cwd": td,
            })
            self.assertEqual(rc, 0)
            self.assertEqual(stdout, "")

    def test_write_readme_always_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            stdout, rc = self._run_hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{td}/README.md"},
                "cwd": td,
            })
            self.assertEqual(rc, 0)
            self.assertEqual(stdout, "")

    def test_write_with_approved_specs_silent(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ["requirements.md", "design.md", "tasks.md"]:
                (Path(td) / name).write_text(f"# {name}\nStatus: APPROVED")
            stdout, rc = self._run_hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": f"{td}/module.py"},
                "cwd": td,
            })
            self.assertEqual(rc, 0)
            # With all specs approved, should exit silently (no warning)
            # or check compliance/freshness (allow with possible context)
            if stdout:
                result = json.loads(stdout)
                self.assertEqual(
                    result["hookSpecificOutput"]["permissionDecision"], "allow"
                )

    def test_empty_stdin(self):
        hook_path = str(_HOOKS_DIR / "validate.py")
        proc = subprocess.run(
            [sys.executable, hook_path],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_invalid_json_stdin(self):
        hook_path = str(_HOOKS_DIR / "validate.py")
        proc = subprocess.run(
            [sys.executable, hook_path],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


class TestConstants(unittest.TestCase):
    """Test that constants are properly defined."""

    def test_code_extensions_are_lowercase(self):
        for ext in _CODE_EXTENSIONS:
            self.assertTrue(ext.startswith("."), f"{ext} should start with .")
            self.assertEqual(ext, ext.lower(), f"{ext} should be lowercase")

    def test_write_tools_includes_write_and_edit(self):
        self.assertIn("Write", _WRITE_TOOLS)
        self.assertIn("Edit", _WRITE_TOOLS)

    def test_always_allowed_includes_spec_files(self):
        self.assertIn("requirements.md", _ALWAYS_ALLOWED_NAMES)
        self.assertIn("design.md", _ALWAYS_ALLOWED_NAMES)
        self.assertIn("tasks.md", _ALWAYS_ALLOWED_NAMES)

    def test_always_allowed_includes_doc_files(self):
        self.assertIn("CLAUDE.md", _ALWAYS_ALLOWED_NAMES)
        self.assertIn("README.md", _ALWAYS_ALLOWED_NAMES)
        self.assertIn("SESSION_STATE.md", _ALWAYS_ALLOWED_NAMES)


if __name__ == "__main__":
    unittest.main()
