#!/usr/bin/env python3
"""Tests for resume_generator.py — cca-loop hardening: auto-generate SESSION_RESUME.md.

Prevents stale resume prompt from degrading loop sessions.
Generates a fresh resume prompt from SESSION_STATE.md when SESSION_RESUME.md
is stale (not updated since last session start).

Tests cover:
- Staleness detection (file mtime vs threshold)
- Resume content extraction from SESSION_STATE.md
- Test count extraction from PROJECT_INDEX.md
- Fallback generation when SESSION_STATE is missing
- Generated prompt format validation
- CLI interface
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from resume_generator import ResumeGenerator, is_stale, generate_resume


class TestStalenessDetection(unittest.TestCase):
    """Test staleness detection for SESSION_RESUME.md."""

    def test_nonexistent_file_is_stale(self):
        self.assertTrue(is_stale("/nonexistent/path/SESSION_RESUME.md", max_age_hours=1))

    def test_fresh_file_is_not_stale(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            self.assertFalse(is_stale(path, max_age_hours=1))
        finally:
            os.unlink(path)

    def test_old_file_is_stale(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"old content")
            path = f.name
        try:
            # Set mtime to 25 hours ago
            old_time = time.time() - (25 * 3600)
            os.utime(path, (old_time, old_time))
            self.assertTrue(is_stale(path, max_age_hours=24))
        finally:
            os.unlink(path)

    def test_custom_max_age(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            # 2 hours old
            two_hours_ago = time.time() - (2 * 3600)
            os.utime(path, (two_hours_ago, two_hours_ago))
            # 1-hour threshold: stale
            self.assertTrue(is_stale(path, max_age_hours=1))
            # 4-hour threshold: fresh
            self.assertFalse(is_stale(path, max_age_hours=4))
        finally:
            os.unlink(path)


class TestResumeGenerator(unittest.TestCase):
    """Test ResumeGenerator class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = ResumeGenerator(cca_root=self.tmpdir)

    def _write(self, filename, content):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_fallback_when_no_session_state(self):
        result = self.gen.generate()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_uses_session_state_when_present(self):
        self._write("SESSION_STATE.md", """# State
## Current State (as of Session 42 — 2026-03-20)

**Phase:** Session 42 COMPLETE. Tests: 1234/1234 passing (50 suites).
**Next:** Build the widget system.
""")
        result = self.gen.generate()
        self.assertIn("42", result)

    def test_extracts_next_from_session_state(self):
        self._write("SESSION_STATE.md", """## Current State (as of Session 15)

**Phase:** Complete.
**Next:** (1) Fix the auth bug. (2) Add rate limiting.
""")
        result = self.gen.generate()
        # Should mention what's next
        self.assertTrue("auth" in result.lower() or "next" in result.lower())

    def test_extracts_test_count_from_project_index(self):
        self._write("PROJECT_INDEX.md", """# Project Index

**Total: 2849 tests (70 suites).**
""")
        result = self.gen.generate()
        self.assertIn("2849", result)

    def test_generates_cca_init_instruction(self):
        result = self.gen.generate()
        self.assertIn("cca-init", result)

    def test_generates_cca_auto_instruction(self):
        result = self.gen.generate()
        self.assertIn("cca-auto", result)

    def test_output_is_under_500_chars(self):
        result = self.gen.generate()
        self.assertLess(len(result), 500)

    def test_output_is_single_paragraph(self):
        result = self.gen.generate()
        # Should be short, concise — not a multi-page document
        lines = [l for l in result.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 10)

    def test_extracts_session_number(self):
        self._write("SESSION_STATE.md", """## Current State (as of Session 99 — 2026-03-20)
**Phase:** Done.
""")
        result = self.gen.generate()
        self.assertIn("99", result)


class TestGenerateResumeFn(unittest.TestCase):
    """Test the module-level generate_resume() convenience function."""

    def test_returns_string(self):
        result = generate_resume(cca_root=tempfile.mkdtemp())
        self.assertIsInstance(result, str)

    def test_with_real_cca_root(self):
        # Test with the actual CCA directory if it exists
        cca_root = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
        if os.path.exists(cca_root):
            result = generate_resume(cca_root=cca_root)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 10)


class TestResumeGeneratorCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_main_exits_cleanly(self):
        import subprocess
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resume_generator.py")
        result = subprocess.run(
            [sys.executable, script, "--print"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(result.returncode, 0)
        self.assertGreater(len(result.stdout.strip()), 0)

    def test_main_with_check_flag(self):
        import subprocess
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resume_generator.py")
        result = subprocess.run(
            [sys.executable, script, "--check"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        # Should exit 0 (fresh) or 1 (stale) — both are valid
        self.assertIn(result.returncode, [0, 1])


if __name__ == "__main__":
    unittest.main()
