#!/usr/bin/env python3
"""Tests for autoloop_pause.py — Pause/resume the CCA desktop autoloop (MT-35 Phase 4)."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import autoloop_pause


class TestPauseResume(unittest.TestCase):
    """Test pause/resume toggle mechanics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pause_file = os.path.join(self.tmpdir, "paused")
        self._orig = autoloop_pause.PAUSE_FILE
        autoloop_pause.PAUSE_FILE = self.pause_file

    def tearDown(self):
        autoloop_pause.PAUSE_FILE = self._orig
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_initially_not_paused(self):
        self.assertFalse(autoloop_pause.is_paused())

    def test_pause_creates_file(self):
        autoloop_pause.pause()
        self.assertTrue(os.path.exists(self.pause_file))
        self.assertTrue(autoloop_pause.is_paused())

    def test_resume_removes_file(self):
        autoloop_pause.pause()
        autoloop_pause.resume()
        self.assertFalse(os.path.exists(self.pause_file))
        self.assertFalse(autoloop_pause.is_paused())

    def test_resume_when_not_paused(self):
        """Resume when already running is a no-op."""
        result = autoloop_pause.resume()
        self.assertTrue(result)
        self.assertFalse(autoloop_pause.is_paused())

    def test_toggle_pauses_when_running(self):
        now_paused = autoloop_pause.toggle()
        self.assertTrue(now_paused)
        self.assertTrue(autoloop_pause.is_paused())

    def test_toggle_resumes_when_paused(self):
        autoloop_pause.pause()
        now_paused = autoloop_pause.toggle()
        self.assertFalse(now_paused)
        self.assertFalse(autoloop_pause.is_paused())

    def test_double_toggle_returns_to_original(self):
        autoloop_pause.toggle()
        autoloop_pause.toggle()
        self.assertFalse(autoloop_pause.is_paused())

    def test_pause_file_contains_timestamp(self):
        before = time.time()
        autoloop_pause.pause()
        after = time.time()
        with open(self.pause_file) as f:
            ts = float(f.read().strip())
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)


class TestStatus(unittest.TestCase):
    """Test status reporting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pause_file = os.path.join(self.tmpdir, "paused")
        self.enabled_file = os.path.join(self.tmpdir, "enabled")
        self._orig_pause = autoloop_pause.PAUSE_FILE
        self._orig_enabled = autoloop_pause.ENABLED_FILE
        autoloop_pause.PAUSE_FILE = self.pause_file
        autoloop_pause.ENABLED_FILE = self.enabled_file

    def tearDown(self):
        autoloop_pause.PAUSE_FILE = self._orig_pause
        autoloop_pause.ENABLED_FILE = self._orig_enabled
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_status_disabled_not_paused(self):
        env = {k: v for k, v in os.environ.items() if k != "CCA_AUTOLOOP_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            s = autoloop_pause.status()
        self.assertFalse(s["enabled"])
        self.assertFalse(s["paused"])
        self.assertFalse(s["effective"])

    def test_status_enabled_not_paused(self):
        with open(self.enabled_file, "w") as f:
            f.write("1")
        env = {k: v for k, v in os.environ.items() if k != "CCA_AUTOLOOP_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            s = autoloop_pause.status()
        self.assertTrue(s["enabled"])
        self.assertFalse(s["paused"])
        self.assertTrue(s["effective"])

    def test_status_enabled_and_paused(self):
        with open(self.enabled_file, "w") as f:
            f.write("1")
        autoloop_pause.pause()
        env = {k: v for k, v in os.environ.items() if k != "CCA_AUTOLOOP_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            s = autoloop_pause.status()
        self.assertTrue(s["enabled"])
        self.assertTrue(s["paused"])
        self.assertFalse(s["effective"])
        self.assertIsNotNone(s["pause_since"])

    def test_status_env_var_overrides_flag(self):
        with patch.dict(os.environ, {"CCA_AUTOLOOP_ENABLED": "1"}):
            s = autoloop_pause.status()
        self.assertTrue(s["enabled"])


class TestStopHookPauseIntegration(unittest.TestCase):
    """Test that the stop hook respects pause state."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook
        self.tmpdir = tempfile.mkdtemp()
        self.resume_file = os.path.join(self.tmpdir, "SESSION_RESUME.md")
        self.breadcrumb = os.path.join(self.tmpdir, "autoloop-fired")
        self.pause_file = os.path.join(self.tmpdir, "paused")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_should_trigger_false_when_paused(self):
        """Even with all other conditions met, pause blocks trigger."""
        with open(self.resume_file, "w") as f:
            f.write("Resume content")
        # Create pause file
        with open(self.pause_file, "w") as f:
            f.write(str(time.time()))
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
            pause_path=self.pause_file,
        )
        self.assertFalse(result)

    def test_should_trigger_true_when_not_paused(self):
        """When not paused and all conditions met, trigger fires."""
        with open(self.resume_file, "w") as f:
            f.write("Resume content")
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
            pause_path=self.pause_file,
        )
        self.assertTrue(result)


class TestCLI(unittest.TestCase):
    """Test CLI commands."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pause_file = os.path.join(self.tmpdir, "paused")
        self._orig = autoloop_pause.PAUSE_FILE
        autoloop_pause.PAUSE_FILE = self.pause_file

    def tearDown(self):
        autoloop_pause.PAUSE_FILE = self._orig
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cli_toggle(self):
        with patch("sys.argv", ["autoloop_pause.py", "toggle"]):
            autoloop_pause.main()
        self.assertTrue(autoloop_pause.is_paused())

    def test_cli_pause(self):
        with patch("sys.argv", ["autoloop_pause.py", "pause"]):
            autoloop_pause.main()
        self.assertTrue(autoloop_pause.is_paused())

    def test_cli_resume(self):
        autoloop_pause.pause()
        with patch("sys.argv", ["autoloop_pause.py", "resume"]):
            autoloop_pause.main()
        self.assertFalse(autoloop_pause.is_paused())

    def test_cli_status(self):
        with patch("sys.argv", ["autoloop_pause.py", "status"]):
            autoloop_pause.main()  # Should not raise

    def test_cli_unknown_command(self):
        with patch("sys.argv", ["autoloop_pause.py", "foobar"]):
            with self.assertRaises(SystemExit):
                autoloop_pause.main()


if __name__ == "__main__":
    unittest.main()
