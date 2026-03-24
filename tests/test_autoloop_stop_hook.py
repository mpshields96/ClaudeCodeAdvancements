#!/usr/bin/env python3
"""Tests for autoloop_stop_hook.py — Stop hook that ensures autoloop trigger fires
even when context exhaustion kills /cca-wrap before Step 10.

TDD: These tests written BEFORE the implementation (S150).
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestShouldTrigger(unittest.TestCase):
    """Test the decision logic for whether to fire the autoloop trigger."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook
        self.tmpdir = tempfile.mkdtemp()
        self.resume_file = os.path.join(self.tmpdir, "SESSION_RESUME.md")
        self.breadcrumb = os.path.join(self.tmpdir, "autoloop-fired")
        self.audit_log = os.path.join(self.tmpdir, "trigger.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_resume(self, content="Resume", age_seconds=0):
        with open(self.resume_file, "w") as f:
            f.write(content)
        if age_seconds > 0:
            mtime = time.time() - age_seconds
            os.utime(self.resume_file, (mtime, mtime))

    def _write_breadcrumb(self, age_seconds=0):
        with open(self.breadcrumb, "w") as f:
            f.write(str(time.time() - age_seconds))
        if age_seconds > 0:
            mtime = time.time() - age_seconds
            os.utime(self.breadcrumb, (mtime, mtime))

    def test_should_trigger_when_all_conditions_met(self):
        """Trigger fires when: autoloop enabled, resume fresh, no breadcrumb."""
        self._write_resume("Resume content", age_seconds=60)
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
        )
        self.assertTrue(result)

    def test_no_trigger_when_disabled(self):
        """Don't trigger when autoloop is disabled."""
        self._write_resume("Resume content")
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=False,
            max_resume_age_seconds=600,
        )
        self.assertFalse(result)

    def test_no_trigger_when_no_resume(self):
        """Don't trigger when SESSION_RESUME.md doesn't exist."""
        result = self.mod.should_trigger(
            resume_path=os.path.join(self.tmpdir, "nonexistent.md"),
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
        )
        self.assertFalse(result)

    def test_no_trigger_when_resume_empty(self):
        """Don't trigger when SESSION_RESUME.md is empty."""
        self._write_resume("")
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
        )
        self.assertFalse(result)

    def test_no_trigger_when_resume_stale(self):
        """Don't trigger when SESSION_RESUME.md is too old (not from this session)."""
        self._write_resume("Old resume", age_seconds=3600)  # 1 hour old
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,  # 10 min max
        )
        self.assertFalse(result)

    def test_no_trigger_when_breadcrumb_fresh(self):
        """Don't trigger when breadcrumb exists (trigger already fired this cycle)."""
        self._write_resume("Resume content")
        self._write_breadcrumb(age_seconds=30)  # 30 seconds ago
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
        )
        self.assertFalse(result)

    def test_trigger_when_breadcrumb_stale(self):
        """Trigger when breadcrumb is old enough (from a previous cycle)."""
        self._write_resume("Resume content", age_seconds=60)
        self._write_breadcrumb(age_seconds=1800)  # 30 min old — previous cycle
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
            breadcrumb_max_age_seconds=600,  # 10 min max
        )
        self.assertTrue(result)

    def test_resume_freshness_boundary(self):
        """Resume exactly at max age boundary should still trigger."""
        self._write_resume("Resume", age_seconds=599)
        result = self.mod.should_trigger(
            resume_path=self.resume_file,
            breadcrumb_path=self.breadcrumb,
            autoloop_enabled=True,
            max_resume_age_seconds=600,
        )
        self.assertTrue(result)


class TestWriteBreadcrumb(unittest.TestCase):
    """Test breadcrumb file writing."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_breadcrumb_file(self):
        path = os.path.join(self.tmpdir, "breadcrumb")
        self.mod.write_breadcrumb(path)
        self.assertTrue(os.path.exists(path))

    def test_breadcrumb_contains_timestamp(self):
        path = os.path.join(self.tmpdir, "breadcrumb")
        before = time.time()
        self.mod.write_breadcrumb(path)
        after = time.time()
        with open(path) as f:
            ts = float(f.read().strip())
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_overwrites_existing_breadcrumb(self):
        path = os.path.join(self.tmpdir, "breadcrumb")
        with open(path, "w") as f:
            f.write("old")
        self.mod.write_breadcrumb(path)
        with open(path) as f:
            content = f.read()
        self.assertNotEqual(content.strip(), "old")


class TestFireTrigger(unittest.TestCase):
    """Test the subprocess-based trigger firing."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook

    @patch("subprocess.Popen")
    def test_fires_subprocess(self, mock_popen):
        """fire_trigger spawns autoloop_trigger.py as background process."""
        self.mod.fire_trigger(dry_run=False)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertIn("autoloop_trigger.py", " ".join(cmd))

    @patch("subprocess.Popen")
    def test_dry_run_fires_with_flag(self, mock_popen):
        """dry_run passes --dry-run to the trigger script."""
        self.mod.fire_trigger(dry_run=True)
        cmd = mock_popen.call_args[0][0]
        self.assertIn("--dry-run", cmd)

    @patch("subprocess.Popen")
    def test_subprocess_is_detached(self, mock_popen):
        """The subprocess should not block session exit."""
        self.mod.fire_trigger(dry_run=False)
        # Check that start_new_session=True is set (process group detach)
        kwargs = mock_popen.call_args[1]
        self.assertTrue(kwargs.get("start_new_session", False))

    @patch("subprocess.Popen", side_effect=OSError("spawn failed"))
    def test_handles_spawn_failure_gracefully(self, mock_popen):
        """If subprocess fails to spawn, don't crash — just return False."""
        result = self.mod.fire_trigger(dry_run=False)
        self.assertFalse(result)


class TestHookMain(unittest.TestCase):
    """Test the main hook entry point (reads stdin JSON, outputs JSON)."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook

    def test_outputs_valid_json(self):
        """Hook must output valid JSON to stdout."""
        hook_input = json.dumps({"hook_type": "Stop"})
        with patch.object(self.mod, "should_trigger", return_value=False):
            result = self.mod.process_hook(hook_input)
        parsed = json.loads(result)
        # Stop hooks should never block
        self.assertNotIn("block", str(parsed.get("decision", "")))

    def test_fires_trigger_when_should(self):
        """When should_trigger returns True, fire_trigger is called."""
        hook_input = json.dumps({"hook_type": "Stop"})
        with patch.object(self.mod, "should_trigger", return_value=True), \
             patch.object(self.mod, "fire_trigger", return_value=True) as mock_fire, \
             patch.object(self.mod, "write_breadcrumb"):
            self.mod.process_hook(hook_input)
        mock_fire.assert_called_once()

    def test_does_not_fire_when_should_not(self):
        """When should_trigger returns False, fire_trigger is NOT called."""
        hook_input = json.dumps({"hook_type": "Stop"})
        with patch.object(self.mod, "should_trigger", return_value=False), \
             patch.object(self.mod, "fire_trigger") as mock_fire:
            self.mod.process_hook(hook_input)
        mock_fire.assert_not_called()

    def test_writes_breadcrumb_after_firing(self):
        """After successful trigger, breadcrumb is written."""
        hook_input = json.dumps({"hook_type": "Stop"})
        with patch.object(self.mod, "should_trigger", return_value=True), \
             patch.object(self.mod, "fire_trigger", return_value=True), \
             patch.object(self.mod, "write_breadcrumb") as mock_bc:
            self.mod.process_hook(hook_input)
        mock_bc.assert_called_once()

    def test_no_breadcrumb_on_fire_failure(self):
        """If trigger fails to fire, don't write breadcrumb (allow retry next time)."""
        hook_input = json.dumps({"hook_type": "Stop"})
        with patch.object(self.mod, "should_trigger", return_value=True), \
             patch.object(self.mod, "fire_trigger", return_value=False), \
             patch.object(self.mod, "write_breadcrumb") as mock_bc:
            self.mod.process_hook(hook_input)
        mock_bc.assert_not_called()


class TestAutoloopEnabledDetection(unittest.TestCase):
    """Test how autoloop enabled state is detected."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook

    def test_enabled_via_env_var(self):
        with patch.dict(os.environ, {"CCA_AUTOLOOP_ENABLED": "1"}):
            self.assertTrue(self.mod.is_autoloop_enabled())

    def test_disabled_via_env_var(self):
        with patch.dict(os.environ, {"CCA_AUTOLOOP_ENABLED": "0"}, clear=False):
            self.assertFalse(self.mod.is_autoloop_enabled())

    def test_disabled_when_no_env_var(self):
        """Default: disabled (opt-in, not opt-out)."""
        env = {k: v for k, v in os.environ.items() if k != "CCA_AUTOLOOP_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(self.mod.is_autoloop_enabled())

    def test_enabled_via_flag_file(self):
        """Flag file ~/.cca-autoloop-enabled acts as persistent enable."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            flag_path = f.name
        try:
            env = {k: v for k, v in os.environ.items() if k != "CCA_AUTOLOOP_ENABLED"}
            with patch.dict(os.environ, env, clear=True), \
                 patch.object(self.mod, "AUTOLOOP_FLAG_FILE", flag_path):
                self.assertTrue(self.mod.is_autoloop_enabled())
        finally:
            os.unlink(flag_path)


class TestCCAProjectDetection(unittest.TestCase):
    """Test that the hook only fires for CCA sessions."""

    def setUp(self):
        import autoloop_stop_hook
        self.mod = autoloop_stop_hook

    def test_detects_cca_project(self):
        """When CWD is CCA project, is_cca_session returns True."""
        with patch("os.getcwd", return_value="/Users/matthewshields/Projects/ClaudeCodeAdvancements"):
            self.assertTrue(self.mod.is_cca_session())

    def test_rejects_other_project(self):
        """When CWD is not CCA project, is_cca_session returns False."""
        with patch("os.getcwd", return_value="/Users/matthewshields/Projects/polymarket-bot"):
            self.assertFalse(self.mod.is_cca_session())

    def test_detects_cca_subdirectory(self):
        """Works even when CWD is a CCA subdirectory."""
        with patch("os.getcwd", return_value="/Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning"):
            self.assertTrue(self.mod.is_cca_session())


if __name__ == "__main__":
    unittest.main()
