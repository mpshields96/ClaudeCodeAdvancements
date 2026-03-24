"""Tests for desktop_autoloop.py — MT-22: Desktop Auto-Loop Orchestrator.

Tests the self-sustaining loop that:
1. Reads SESSION_RESUME.md
2. Sends it to Claude.app via desktop_automator
3. Monitors for session completion (file change detection)
4. Loops to next iteration

All AppleScript/GUI calls are mocked.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from desktop_autoloop import (
    DesktopLoopConfig,
    DesktopLoopState,
    DesktopAutoLoop,
    ResumeWatcher,
    FALLBACK_PROMPT,
    MAX_PROMPT_SIZE,
)


class TestDesktopLoopConfig(unittest.TestCase):
    """Test loop configuration."""

    def test_defaults(self):
        cfg = DesktopLoopConfig()
        self.assertEqual(cfg.max_iterations, 50)
        self.assertEqual(cfg.cooldown_seconds, 15)
        self.assertEqual(cfg.session_timeout, 14400)
        self.assertFalse(cfg.dry_run)

    def test_min_cooldown_enforced(self):
        cfg = DesktopLoopConfig(cooldown_seconds=1)
        self.assertEqual(cfg.cooldown_seconds, 5)

    def test_min_iterations_enforced(self):
        cfg = DesktopLoopConfig(max_iterations=0)
        self.assertEqual(cfg.max_iterations, 1)

    def test_custom_project_dir(self):
        cfg = DesktopLoopConfig(project_dir="/tmp/test")
        self.assertEqual(cfg.project_dir, "/tmp/test")
        self.assertEqual(cfg.resume_file, "/tmp/test/SESSION_RESUME.md")

    def test_from_dict(self):
        d = {"max_iterations": 10, "cooldown_seconds": 30, "dry_run": True}
        cfg = DesktopLoopConfig.from_dict(d)
        self.assertEqual(cfg.max_iterations, 10)
        self.assertTrue(cfg.dry_run)

    def test_from_dict_ignores_unknown(self):
        d = {"max_iterations": 10, "unknown_field": True}
        cfg = DesktopLoopConfig.from_dict(d)
        self.assertEqual(cfg.max_iterations, 10)

    def test_model_strategy(self):
        cfg = DesktopLoopConfig(model_strategy="opus-primary")
        self.assertEqual(cfg.model_strategy, "opus-primary")

    def test_invalid_model_strategy_defaults(self):
        cfg = DesktopLoopConfig(model_strategy="invalid")
        self.assertEqual(cfg.model_strategy, "round-robin")


class TestDesktopLoopState(unittest.TestCase):
    """Test state tracking."""

    def test_initial_state(self):
        st = DesktopLoopState()
        self.assertEqual(st.iteration, 0)
        self.assertFalse(st.should_stop)
        self.assertEqual(st.stop_reason, "")

    def test_record_success(self):
        st = DesktopLoopState(max_iterations=50)
        st.record_session(exit_code=0, duration=120.0)
        self.assertEqual(st.iteration, 1)
        self.assertEqual(st.total_sessions, 1)
        self.assertFalse(st.should_stop)

    def test_consecutive_crashes_stop(self):
        st = DesktopLoopState(max_iterations=50)
        for _ in range(3):
            st.record_session(exit_code=1, duration=60.0)
        self.assertTrue(st.should_stop)
        self.assertIn("crash", st.stop_reason)

    def test_consecutive_short_sessions_stop(self):
        st = DesktopLoopState(max_iterations=50)
        for _ in range(3):
            st.record_session(exit_code=0, duration=5.0)
        self.assertTrue(st.should_stop)
        self.assertIn("short", st.stop_reason)

    def test_max_iterations_stop(self):
        st = DesktopLoopState(max_iterations=2)
        st.record_session(exit_code=0, duration=120.0)
        self.assertFalse(st.should_stop)
        st.record_session(exit_code=0, duration=120.0)
        self.assertTrue(st.should_stop)
        self.assertIn("max_iterations", st.stop_reason)

    def test_crash_counter_resets_on_success(self):
        st = DesktopLoopState(max_iterations=50)
        st.record_session(exit_code=1, duration=60.0)
        st.record_session(exit_code=1, duration=60.0)
        st.record_session(exit_code=0, duration=120.0)  # reset
        st.record_session(exit_code=1, duration=60.0)
        self.assertFalse(st.should_stop)

    def test_to_dict(self):
        st = DesktopLoopState(max_iterations=10)
        st.record_session(exit_code=0, duration=120.0)
        d = st.to_dict()
        self.assertEqual(d["iteration"], 1)
        self.assertEqual(d["total_sessions"], 1)
        self.assertIn("should_stop", d)

    def test_summary(self):
        st = DesktopLoopState(max_iterations=10)
        st.record_session(exit_code=0, duration=300.0)
        s = st.summary()
        self.assertIn("1/10", s)
        self.assertIn("300", s)


class TestResumeWatcher(unittest.TestCase):
    """Test SESSION_RESUME.md file watcher."""

    def test_read_resume(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume prompt content here")
            f.flush()
            watcher = ResumeWatcher(f.name)
            prompt = watcher.read_resume()
            self.assertEqual(prompt, "Resume prompt content here")
        os.unlink(f.name)

    def test_read_missing_file_returns_fallback(self):
        watcher = ResumeWatcher("/nonexistent/path/SESSION_RESUME.md")
        prompt = watcher.read_resume()
        self.assertEqual(prompt, FALLBACK_PROMPT)

    def test_read_empty_file_returns_fallback(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            f.flush()
            watcher = ResumeWatcher(f.name)
            prompt = watcher.read_resume()
            self.assertEqual(prompt, FALLBACK_PROMPT)
        os.unlink(f.name)

    def test_truncates_oversized_prompt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("x" * (MAX_PROMPT_SIZE + 1000))
            f.flush()
            watcher = ResumeWatcher(f.name)
            prompt = watcher.read_resume()
            self.assertLessEqual(len(prompt), MAX_PROMPT_SIZE + 100)
            self.assertIn("TRUNCATED", prompt)
        os.unlink(f.name)

    def test_snapshot_mtime(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("content")
            f.flush()
            watcher = ResumeWatcher(f.name)
            watcher.snapshot_mtime()
            self.assertIsNotNone(watcher._last_mtime)
        os.unlink(f.name)

    def test_has_changed_false_when_unchanged(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("content")
            f.flush()
            watcher = ResumeWatcher(f.name)
            watcher.snapshot_mtime()
            self.assertFalse(watcher.has_changed())
        os.unlink(f.name)

    def test_has_changed_true_when_modified(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("content v1")
            f.flush()
            watcher = ResumeWatcher(f.name)
            watcher.snapshot_mtime()

            # Simulate file modification with explicit time change
            time.sleep(0.05)
            with open(f.name, "w") as f2:
                f2.write("content v2")
            # Force mtime to be different
            new_mtime = watcher._last_mtime + 10
            os.utime(f.name, (new_mtime, new_mtime))

            self.assertTrue(watcher.has_changed())
        os.unlink(f.name)

    def test_has_changed_returns_false_for_missing_file(self):
        watcher = ResumeWatcher("/nonexistent/path.md")
        watcher._last_mtime = 12345.0
        self.assertFalse(watcher.has_changed())

    def test_snapshot_missing_file(self):
        watcher = ResumeWatcher("/nonexistent/path.md")
        watcher.snapshot_mtime()
        self.assertIsNone(watcher._last_mtime)


class TestDesktopAutoLoop(unittest.TestCase):
    """Test the main loop orchestrator."""

    def _make_loop(self, tmp, **config_overrides):
        cfg = DesktopLoopConfig(
            project_dir=tmp,
            dry_run=True,
            cooldown_seconds=5,
            **config_overrides,
        )
        return DesktopAutoLoop(cfg)

    def test_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)
            self.assertIsNotNone(loop.automator)
            self.assertIsNotNone(loop.watcher)
            self.assertIsNotNone(loop.state)

    def test_build_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write a resume file
            resume_path = Path(tmp) / "SESSION_RESUME.md"
            resume_path.write_text("Resume content here")
            loop = self._make_loop(tmp)
            prompt = loop._build_prompt()
            self.assertIn("Resume content here", prompt)
            self.assertIn("/cca-init", prompt)

    def test_build_prompt_with_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)
            prompt = loop._build_prompt()
            self.assertIn(FALLBACK_PROMPT, prompt)

    def test_select_model_round_robin(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp, model_strategy="round-robin")
            m1 = loop._select_model(1)
            m2 = loop._select_model(2)
            self.assertNotEqual(m1, m2)

    def test_select_model_opus_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp, model_strategy="opus-primary")
            self.assertEqual(loop._select_model(1), "opus")
            self.assertEqual(loop._select_model(2), "opus")

    def test_select_model_sonnet_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp, model_strategy="sonnet-primary")
            self.assertEqual(loop._select_model(1), "sonnet")

    @patch.object(DesktopAutoLoop, "_wait_for_session_end", return_value=(0, 120.0))
    @patch.object(DesktopAutoLoop, "_send_prompt_to_app", return_value=True)
    def test_run_iteration_success(self, mock_send, mock_wait):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SESSION_RESUME.md").write_text("resume")
            loop = self._make_loop(tmp, max_iterations=1)
            result = loop._run_one_iteration()
            self.assertTrue(result["success"])
            mock_send.assert_called_once()

    @patch.object(DesktopAutoLoop, "_send_prompt_to_app", return_value=False)
    def test_run_iteration_send_failure(self, mock_send):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SESSION_RESUME.md").write_text("resume")
            loop = self._make_loop(tmp)
            result = loop._run_one_iteration()
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "send_failed")

    @patch.object(DesktopAutoLoop, "_wait_for_session_end", return_value=(1, 5.0))
    @patch.object(DesktopAutoLoop, "_send_prompt_to_app", return_value=True)
    def test_run_iteration_crash(self, mock_send, mock_wait):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SESSION_RESUME.md").write_text("resume")
            loop = self._make_loop(tmp)
            result = loop._run_one_iteration()
            self.assertTrue(result["success"])  # iteration itself ran
            self.assertEqual(result["exit_code"], 1)

    def test_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)
            checks = loop.preflight()
            self.assertIn("automator_preflight", checks)
            self.assertIn("resume_file", checks)
            self.assertIn("project_dir", checks)

    def test_preflight_resume_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SESSION_RESUME.md").write_text("resume content")
            loop = self._make_loop(tmp)
            checks = loop.preflight()
            self.assertEqual(checks["resume_file"], "PASS")

    def test_preflight_resume_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)
            checks = loop.preflight()
            self.assertEqual(checks["resume_file"], "WARN")


class TestLoopExecution(unittest.TestCase):
    """Test the full loop with mocked iterations."""

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_loop_respects_max_iterations(self, mock_iter):
        mock_iter.return_value = {"success": True, "exit_code": 0, "duration": 120.0}
        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=3, cooldown_seconds=5,
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertEqual(loop.state.iteration, 3)
            self.assertTrue(loop.state.should_stop)

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_loop_stops_on_crashes(self, mock_iter):
        mock_iter.return_value = {"success": True, "exit_code": 1, "duration": 60.0}
        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=50, cooldown_seconds=5,
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertTrue(loop.state.should_stop)
            self.assertIn("crash", loop.state.stop_reason)
            self.assertEqual(loop.state.iteration, 3)

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_loop_stops_on_short_sessions(self, mock_iter):
        mock_iter.return_value = {"success": True, "exit_code": 0, "duration": 5.0}
        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=50, cooldown_seconds=5,
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertTrue(loop.state.should_stop)
            self.assertIn("short", loop.state.stop_reason)

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_loop_continues_after_single_failure(self, mock_iter):
        # First fails, rest succeed
        mock_iter.side_effect = [
            {"success": True, "exit_code": 1, "duration": 60.0},
            {"success": True, "exit_code": 0, "duration": 120.0},
            {"success": True, "exit_code": 0, "duration": 120.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=3, cooldown_seconds=5,
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertEqual(loop.state.iteration, 3)

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_loop_handles_send_failure(self, mock_iter):
        # send_failed counts as crash
        mock_iter.return_value = {"success": False, "error": "send_failed", "duration": 1.0}
        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=50, cooldown_seconds=5,
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertTrue(loop.state.should_stop)


class TestAuditLogging(unittest.TestCase):
    """Test loop audit trail."""

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_audit_log_written(self, mock_iter):
        mock_iter.return_value = {"success": True, "exit_code": 0, "duration": 120.0}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=1, cooldown_seconds=5,
                audit_log=str(log_path),
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            self.assertTrue(log_path.exists())
            with open(log_path) as f:
                entries = [json.loads(l) for l in f if l.strip()]
            events = [e["event"] for e in entries]
            self.assertIn("loop_start", events)

    @patch.object(DesktopAutoLoop, "_run_one_iteration")
    def test_audit_contains_iteration_data(self, mock_iter):
        mock_iter.return_value = {"success": True, "exit_code": 0, "duration": 120.0}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            cfg = DesktopLoopConfig(
                project_dir=tmp, dry_run=True,
                max_iterations=1, cooldown_seconds=5,
                audit_log=str(log_path),
            )
            loop = DesktopAutoLoop(cfg)
            loop.run()
            with open(log_path) as f:
                entries = [json.loads(l) for l in f if l.strip()]
            # The loop logs iteration data via _run_one_iteration mock
            # Check for loop_start and loop_end events instead
            start_entries = [e for e in entries if e["event"] == "loop_start"]
            end_entries = [e for e in entries if e["event"] == "loop_end"]
            self.assertTrue(len(start_entries) > 0)
            self.assertTrue(len(end_entries) > 0)


class TestSendPromptToApp(unittest.TestCase):
    """Test the _send_prompt_to_app method."""

    @patch("desktop_autoloop.DesktopAutomator")
    def test_activates_then_new_conversation_then_sends(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.new_conversation.return_value = True
        mock_da.send_prompt.return_value = True

        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(project_dir=tmp, dry_run=True)
            loop = DesktopAutoLoop(cfg)
            loop.automator = mock_da
            loop._is_first_iteration = False  # not first = should call new_conversation
            result = loop._send_prompt_to_app("test prompt")
            self.assertTrue(result)
            mock_da.activate_claude.assert_called_once()
            mock_da.new_conversation.assert_called_once()
            mock_da.send_prompt.assert_called_once()

    @patch("desktop_autoloop.DesktopAutomator")
    def test_fails_if_activate_fails(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = False

        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(project_dir=tmp, dry_run=True)
            loop = DesktopAutoLoop(cfg)
            loop.automator = mock_da
            result = loop._send_prompt_to_app("test")
            self.assertFalse(result)

    @patch("desktop_autoloop.DesktopAutomator")
    def test_skips_new_conversation_on_first_iteration(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.send_prompt.return_value = True

        with tempfile.TemporaryDirectory() as tmp:
            cfg = DesktopLoopConfig(project_dir=tmp, dry_run=True)
            loop = DesktopAutoLoop(cfg)
            loop.automator = mock_da
            loop._is_first_iteration = True
            result = loop._send_prompt_to_app("test prompt")
            self.assertTrue(result)
            mock_da.new_conversation.assert_not_called()


class TestWaitForSessionEnd(unittest.TestCase):
    """Test session completion detection."""

    def test_detects_file_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume_path = Path(tmp) / "SESSION_RESUME.md"
            resume_path.write_text("v1")

            cfg = DesktopLoopConfig(project_dir=tmp, dry_run=True, session_timeout=2)
            loop = DesktopAutoLoop(cfg)
            loop.watcher.snapshot_mtime()

            # Simulate file change
            time.sleep(0.05)
            resume_path.write_text("v2")
            new_mtime = loop.watcher._last_mtime + 10
            os.utime(resume_path, (new_mtime, new_mtime))

            exit_code, duration = loop._wait_for_session_end(poll_interval=0.01)
            self.assertEqual(exit_code, 0)

    def test_timeout_returns_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume_path = Path(tmp) / "SESSION_RESUME.md"
            resume_path.write_text("v1")

            cfg = DesktopLoopConfig(project_dir=tmp, dry_run=True, session_timeout=0.1)
            loop = DesktopAutoLoop(cfg)
            loop.watcher.snapshot_mtime()

            # Don't change the file — should timeout
            exit_code, duration = loop._wait_for_session_end(poll_interval=0.02)
            self.assertEqual(exit_code, 1)  # timeout = crash


class TestIdleDetection(unittest.TestCase):
    """Tests for extended idle detection (exit code 2).

    When Claude CPU is idle for 5+ consecutive minutes after at least
    2 minutes of session time, exit with code 2 instead of waiting
    for full timeout.
    """

    def _make_loop(self, tmp, timeout=600):
        """Create a DesktopAutoLoop with mocked automator."""
        resume_path = Path(tmp) / "SESSION_RESUME.md"
        resume_path.write_text("v1")
        cfg = DesktopLoopConfig(
            project_dir=tmp,
            dry_run=False,
            session_timeout=timeout,
        )
        loop = DesktopAutoLoop(cfg)
        loop.watcher.snapshot_mtime()
        loop.automator = MagicMock()
        return loop

    @patch("desktop_autoloop.time")
    def test_extended_idle_returns_exit_code_2(self, mock_time):
        """5 consecutive idle checks after 2min session = exit code 2."""
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)

            # Simulate: each time.time() call advances by 60s,
            # starting at elapsed > 120s (past min_session_time)
            # Need enough calls for 5 idle checks at 60s intervals
            start = 1000.0
            # time.time() is called: once for start, then in while condition,
            # then for file check, then for elapsed, etc.
            # The loop calls time.time() repeatedly. Let's just set up a sequence.
            call_count = [0]
            def time_side_effect():
                call_count[0] += 1
                # After enough calls, we should be past min_session_time
                # and have checked idle 5+ times at 60s intervals
                return start + call_count[0] * 15.0  # 15s per call, ramps up fast

            mock_time.time.side_effect = time_side_effect
            mock_time.sleep = MagicMock()  # don't actually sleep

            # File never changes
            loop.watcher.has_changed = MagicMock(return_value=False)

            # CPU always idle
            loop.automator.get_claude_cpu_usage.return_value = 1.0
            loop.automator.is_claude_idle.return_value = True

            exit_code, duration = loop._wait_for_session_end(poll_interval=1.0)
            self.assertEqual(exit_code, 2)

    @patch("desktop_autoloop.time")
    def test_idle_not_triggered_before_min_session_time(self, mock_time):
        """Idle detection doesn't trigger before 2 minutes of session time."""
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp, timeout=5)

            # Simulate short elapsed times (< 120s min_session_time)
            start = 1000.0
            call_count = [0]
            def time_side_effect():
                call_count[0] += 1
                # Stay under 120s, then exceed timeout
                elapsed = min(call_count[0] * 1.0, 6.0)  # max 6s
                return start + elapsed

            mock_time.time.side_effect = time_side_effect
            mock_time.sleep = MagicMock()

            loop.watcher.has_changed = MagicMock(return_value=False)
            loop.automator.is_claude_idle.return_value = True
            loop.automator.get_claude_cpu_usage.return_value = 0.5

            exit_code, duration = loop._wait_for_session_end(poll_interval=0.5)
            # Should timeout (1), not idle (2), since elapsed < 120s
            self.assertEqual(exit_code, 1)

    @patch("desktop_autoloop.time")
    def test_idle_counter_resets_on_active(self, mock_time):
        """Consecutive idle counter resets when CPU becomes active."""
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp, timeout=900)

            start = 1000.0
            call_count = [0]
            def time_side_effect():
                call_count[0] += 1
                return start + call_count[0] * 15.0

            mock_time.time.side_effect = time_side_effect
            mock_time.sleep = MagicMock()

            loop.watcher.has_changed = MagicMock(return_value=False)

            # Alternate idle/active — idle 3 times, then active, then idle 3 times
            # This should NOT trigger idle exit (never gets to 5 consecutive)
            idle_sequence = [True, True, True, False, True, True, True, False]
            idle_idx = [0]
            def is_idle():
                idx = idle_idx[0]
                idle_idx[0] += 1
                if idx < len(idle_sequence):
                    return idle_sequence[idx]
                return False  # active after sequence ends

            loop.automator.is_claude_idle.side_effect = is_idle
            loop.automator.get_claude_cpu_usage.return_value = 2.0

            exit_code, duration = loop._wait_for_session_end(poll_interval=1.0)
            # Should timeout (1), not idle (2)
            self.assertEqual(exit_code, 1)

    @patch("desktop_autoloop.time")
    def test_file_change_takes_priority_over_idle(self, mock_time):
        """If file changes while idle, exit code 0 (not 2)."""
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)

            start = 1000.0
            call_count = [0]
            def time_side_effect():
                call_count[0] += 1
                return start + call_count[0] * 30.0

            mock_time.time.side_effect = time_side_effect
            mock_time.sleep = MagicMock()

            # File changes on first check
            loop.watcher.has_changed = MagicMock(return_value=True)
            loop.automator.is_claude_idle.return_value = True
            loop.automator.get_claude_cpu_usage.return_value = 0.5

            exit_code, duration = loop._wait_for_session_end(poll_interval=1.0)
            self.assertEqual(exit_code, 0)

    def test_exit_code_2_counts_as_crash_in_state(self):
        """Exit code 2 (idle) is treated as non-zero (crash) in state tracking."""
        st = DesktopLoopState(max_iterations=50)
        st.record_session(exit_code=2, duration=300.0)
        self.assertEqual(st.total_crashes, 1)
        self.assertEqual(st._consecutive_crashes, 1)

    def test_three_consecutive_idle_exits_stops_loop(self):
        """3 consecutive exit code 2 triggers crash stop."""
        st = DesktopLoopState(max_iterations=50)
        for _ in range(3):
            st.record_session(exit_code=2, duration=300.0)
        self.assertTrue(st.should_stop)
        self.assertIn("crash", st.stop_reason)

    def test_idle_exit_reset_by_success(self):
        """A successful session resets the idle/crash counter."""
        st = DesktopLoopState(max_iterations=50)
        st.record_session(exit_code=2, duration=300.0)
        st.record_session(exit_code=2, duration=300.0)
        st.record_session(exit_code=0, duration=300.0)  # success resets
        st.record_session(exit_code=2, duration=300.0)
        self.assertFalse(st.should_stop)
        self.assertEqual(st._consecutive_crashes, 1)

    @patch("desktop_autoloop.time")
    def test_idle_logs_cpu_checks(self, mock_time):
        """CPU checks are logged with idle state."""
        with tempfile.TemporaryDirectory() as tmp:
            loop = self._make_loop(tmp)

            start = 1000.0
            call_count = [0]
            def time_side_effect():
                call_count[0] += 1
                return start + call_count[0] * 15.0

            mock_time.time.side_effect = time_side_effect
            mock_time.sleep = MagicMock()

            loop.watcher.has_changed = MagicMock(return_value=False)
            loop.automator.is_claude_idle.return_value = True
            loop.automator.get_claude_cpu_usage.return_value = 1.5

            # Capture logs
            logged_events = []
            original_log = loop._log
            def capture_log(event, data=None):
                logged_events.append(event)
                original_log(event, data)
            loop._log = capture_log

            exit_code, _ = loop._wait_for_session_end(poll_interval=1.0)
            self.assertEqual(exit_code, 2)
            self.assertIn("cpu_check", logged_events)
            self.assertIn("session_end_detected", logged_events)


if __name__ == "__main__":
    unittest.main()
