#!/usr/bin/env python3
"""Tests for cca_autoloop.py — MT-30 Phase 6: CCA-only auto-loop.

Tests the loop that reads SESSION_RESUME.md and spawns new Claude sessions.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cca_autoloop import (
    AutoLoopConfig,
    AutoLoopState,
    AutoLoopRunner,
    build_claude_command,
    read_resume_prompt,
    select_model,
    write_desktop_wrapper,
    wait_for_sentinel,
    spawn_desktop_session,
    close_desktop_window,
    desktop_window_title,
    check_no_other_cca_sessions,
)


class TestAutoLoopConfig(unittest.TestCase):
    """Test configuration loading and defaults."""

    def test_default_config(self):
        cfg = AutoLoopConfig()
        self.assertEqual(cfg.max_iterations, 50)
        self.assertEqual(cfg.cooldown_seconds, 15)
        self.assertEqual(cfg.project_dir, "/Users/matthewshields/Projects/ClaudeCodeAdvancements")
        self.assertTrue(cfg.resume_file.endswith("SESSION_RESUME.md"))
        self.assertFalse(cfg.dry_run)

    def test_custom_config(self):
        cfg = AutoLoopConfig(
            max_iterations=5,
            cooldown_seconds=30,
            project_dir="/tmp/test",
            dry_run=True,
        )
        self.assertEqual(cfg.max_iterations, 5)
        self.assertEqual(cfg.cooldown_seconds, 30)
        self.assertEqual(cfg.project_dir, "/tmp/test")
        self.assertTrue(cfg.dry_run)
        self.assertEqual(cfg.resume_file, "/tmp/test/SESSION_RESUME.md")

    def test_resume_file_derived_from_project_dir(self):
        cfg = AutoLoopConfig(project_dir="/foo/bar")
        self.assertEqual(cfg.resume_file, "/foo/bar/SESSION_RESUME.md")

    def test_custom_resume_file_overrides(self):
        cfg = AutoLoopConfig(
            project_dir="/foo/bar",
            resume_file="/custom/resume.md",
        )
        self.assertEqual(cfg.resume_file, "/custom/resume.md")

    def test_max_iterations_minimum(self):
        """Max iterations must be at least 1."""
        cfg = AutoLoopConfig(max_iterations=0)
        self.assertEqual(cfg.max_iterations, 1)

    def test_cooldown_minimum(self):
        """Cooldown must be at least 5 seconds."""
        cfg = AutoLoopConfig(cooldown_seconds=1)
        self.assertEqual(cfg.cooldown_seconds, 5)

    def test_from_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "max_iterations": 10,
                "cooldown_seconds": 20,
                "project_dir": "/tmp/test",
            }, f)
            f.flush()
            cfg = AutoLoopConfig.from_json(f.name)
        os.unlink(f.name)
        self.assertEqual(cfg.max_iterations, 10)
        self.assertEqual(cfg.cooldown_seconds, 20)

    def test_from_json_missing_file_uses_defaults(self):
        cfg = AutoLoopConfig.from_json("/nonexistent/config.json")
        self.assertEqual(cfg.max_iterations, 50)

    def test_default_model_strategy(self):
        cfg = AutoLoopConfig()
        self.assertEqual(cfg.model_strategy, "round-robin")

    def test_custom_model_strategy(self):
        cfg = AutoLoopConfig(model_strategy="opus-primary")
        self.assertEqual(cfg.model_strategy, "opus-primary")

    def test_invalid_model_strategy_falls_back(self):
        cfg = AutoLoopConfig(model_strategy="invalid-strategy")
        self.assertEqual(cfg.model_strategy, "round-robin")

    def test_from_json_with_model_strategy(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"model_strategy": "sonnet-primary"}, f)
            f.flush()
            cfg = AutoLoopConfig.from_json(f.name)
        os.unlink(f.name)
        self.assertEqual(cfg.model_strategy, "sonnet-primary")


class TestAutoLoopState(unittest.TestCase):
    """Test runtime state tracking."""

    def test_initial_state(self):
        state = AutoLoopState()
        self.assertEqual(state.iteration, 0)
        self.assertEqual(state.total_sessions, 0)
        self.assertEqual(state.total_crashes, 0)
        self.assertIsNone(state.last_exit_code)
        self.assertFalse(state.should_stop)

    def test_record_session_clean(self):
        state = AutoLoopState()
        state.record_session(exit_code=0, duration=120.5)
        self.assertEqual(state.iteration, 1)
        self.assertEqual(state.total_sessions, 1)
        self.assertEqual(state.total_crashes, 0)
        self.assertEqual(state.last_exit_code, 0)

    def test_record_session_crash(self):
        state = AutoLoopState()
        state.record_session(exit_code=1, duration=10.0)
        self.assertEqual(state.total_sessions, 1)
        self.assertEqual(state.total_crashes, 1)
        self.assertEqual(state.last_exit_code, 1)

    def test_consecutive_crashes_trigger_stop(self):
        state = AutoLoopState()
        for _ in range(3):
            state.record_session(exit_code=1, duration=5.0)
        self.assertTrue(state.should_stop)
        self.assertEqual(state.stop_reason, "3_consecutive_crashes")

    def test_clean_session_resets_crash_streak(self):
        state = AutoLoopState()
        state.record_session(exit_code=1, duration=5.0)
        state.record_session(exit_code=1, duration=5.0)
        state.record_session(exit_code=0, duration=120.0)
        self.assertFalse(state.should_stop)
        # Another crash doesn't trigger stop (streak was reset)
        state.record_session(exit_code=1, duration=5.0)
        self.assertFalse(state.should_stop)

    def test_max_iterations_triggers_stop(self):
        state = AutoLoopState(max_iterations=3)
        for _ in range(3):
            state.record_session(exit_code=0, duration=60.0)
        self.assertTrue(state.should_stop)
        self.assertEqual(state.stop_reason, "max_iterations_reached")

    def test_very_short_sessions_trigger_stop(self):
        """If 3 sessions in a row last < 30 seconds, something is wrong."""
        state = AutoLoopState()
        for _ in range(3):
            state.record_session(exit_code=0, duration=10.0)
        self.assertTrue(state.should_stop)
        self.assertEqual(state.stop_reason, "3_consecutive_short_sessions")

    def test_normal_short_session_no_stop(self):
        """A single short session is fine."""
        state = AutoLoopState()
        state.record_session(exit_code=0, duration=10.0)
        self.assertFalse(state.should_stop)

    def test_record_session_with_model(self):
        state = AutoLoopState()
        state.record_session(exit_code=0, duration=120.0, model="opus")
        state.record_session(exit_code=0, duration=180.0, model="sonnet")
        self.assertEqual(state._models_used, ["opus", "sonnet"])

    def test_to_dict_includes_models(self):
        state = AutoLoopState()
        state.record_session(exit_code=0, duration=60.0, model="sonnet")
        d = state.to_dict()
        self.assertIn("models_used", d)
        self.assertEqual(d["models_used"], ["sonnet"])

    def test_summary(self):
        state = AutoLoopState()
        state.record_session(exit_code=0, duration=120.0)
        state.record_session(exit_code=0, duration=180.0)
        summary = state.summary()
        self.assertIn("2", summary)  # iteration count
        self.assertIn("0", summary)  # crash count


class TestReadResumePrompt(unittest.TestCase):
    """Test reading SESSION_RESUME.md."""

    def test_reads_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Run /cca-init. Last session was S125.")
            f.flush()
            prompt = read_resume_prompt(f.name)
        os.unlink(f.name)
        self.assertEqual(prompt, "Run /cca-init. Last session was S125.")

    def test_missing_file_returns_fallback(self):
        prompt = read_resume_prompt("/nonexistent/file.md")
        self.assertIn("/cca-init", prompt)
        self.assertIn("/cca-auto", prompt)

    def test_empty_file_returns_fallback(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            f.flush()
            prompt = read_resume_prompt(f.name)
        os.unlink(f.name)
        self.assertIn("/cca-init", prompt)

    def test_whitespace_only_returns_fallback(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("   \n\n  ")
            f.flush()
            prompt = read_resume_prompt(f.name)
        os.unlink(f.name)
        self.assertIn("/cca-init", prompt)

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("  Resume prompt here.  \n")
            f.flush()
            prompt = read_resume_prompt(f.name)
        os.unlink(f.name)
        self.assertEqual(prompt, "Resume prompt here.")


class TestSelectModel(unittest.TestCase):
    """Test model alternation logic."""

    def test_round_robin_odd_is_sonnet(self):
        self.assertEqual(select_model("round-robin", 1), "sonnet")
        self.assertEqual(select_model("round-robin", 3), "sonnet")
        self.assertEqual(select_model("round-robin", 5), "sonnet")

    def test_round_robin_even_is_opus(self):
        self.assertEqual(select_model("round-robin", 2), "opus")
        self.assertEqual(select_model("round-robin", 4), "opus")
        self.assertEqual(select_model("round-robin", 6), "opus")

    def test_opus_primary_always_opus(self):
        for i in range(1, 6):
            self.assertEqual(select_model("opus-primary", i), "opus")

    def test_sonnet_primary_always_sonnet(self):
        for i in range(1, 6):
            self.assertEqual(select_model("sonnet-primary", i), "sonnet")

    def test_unknown_strategy_defaults_to_round_robin(self):
        # Unknown falls through to else (round-robin behavior)
        self.assertEqual(select_model("unknown", 1), "sonnet")
        self.assertEqual(select_model("unknown", 2), "opus")

    def test_round_robin_sequence(self):
        """Verify the full alternation pattern."""
        models = [select_model("round-robin", i) for i in range(1, 7)]
        self.assertEqual(models, ["sonnet", "opus", "sonnet", "opus", "sonnet", "opus"])


class TestBuildClaudeCommand(unittest.TestCase):
    """Test Claude CLI command construction."""

    def test_basic_command(self):
        cmd = build_claude_command(
            resume_prompt="Run /cca-init. Last session S125.",
            project_dir="/Users/matthewshields/Projects/ClaudeCodeAdvancements",
        )
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], "claude")
        # The prompt argument should contain /cca-init and /cca-auto
        prompt_arg = cmd[-1]
        self.assertIn("/cca-init", prompt_arg)
        self.assertIn("/cca-auto", prompt_arg)
        self.assertIn("S125", prompt_arg)

    def test_command_includes_resume_prompt(self):
        cmd = build_claude_command(
            resume_prompt="Custom resume text here.",
            project_dir="/tmp",
        )
        prompt_arg = cmd[-1]
        self.assertIn("Custom resume text here.", prompt_arg)

    def test_command_unsets_api_key_not_in_args(self):
        """API key handling is done via env, not in claude args."""
        cmd = build_claude_command(
            resume_prompt="test",
            project_dir="/tmp",
        )
        joined = " ".join(cmd)
        self.assertNotIn("ANTHROPIC_API_KEY", joined)

    def test_command_has_no_shell_injection(self):
        """Resume prompt with special chars shouldn't cause issues."""
        cmd = build_claude_command(
            resume_prompt='Test with "quotes" and $variables and `backticks`',
            project_dir="/tmp",
        )
        # Should be a list (not a string), so shell injection isn't possible
        self.assertIsInstance(cmd, list)
        # The special chars should be in the prompt arg literally
        prompt_arg = cmd[-1]
        self.assertIn('"quotes"', prompt_arg)
        self.assertIn("$variables", prompt_arg)

    def test_fallback_prompt_when_empty(self):
        cmd = build_claude_command(resume_prompt="", project_dir="/tmp")
        prompt_arg = cmd[-1]
        self.assertIn("/cca-init", prompt_arg)
        self.assertIn("/cca-auto", prompt_arg)

    def test_command_with_model_opus(self):
        cmd = build_claude_command("Resume", "/tmp", model="opus")
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertIn("--model", cmd)
        model_idx = cmd.index("--model")
        self.assertEqual(cmd[model_idx + 1], "opus")
        self.assertIn("Resume", cmd[-1])

    def test_command_with_model_sonnet(self):
        cmd = build_claude_command("Resume", "/tmp", model="sonnet")
        model_idx = cmd.index("--model")
        self.assertEqual(cmd[model_idx + 1], "sonnet")

    def test_command_without_model(self):
        cmd = build_claude_command("Resume", "/tmp", model=None)
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertNotIn("--model", cmd)

    def test_command_model_none_default(self):
        """No model arg by default (backward compat)."""
        cmd = build_claude_command("Resume", "/tmp")
        self.assertNotIn("--model", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)


class TestAutoLoopRunner(unittest.TestCase):
    """Test the main loop runner."""

    def _make_runner(self, **kwargs):
        cfg = AutoLoopConfig(
            project_dir="/tmp/test_autoloop",
            dry_run=True,
            max_iterations=3,
            cooldown_seconds=5,
            **kwargs,
        )
        return AutoLoopRunner(cfg)

    def test_init(self):
        runner = self._make_runner()
        self.assertIsNotNone(runner.config)
        self.assertIsNotNone(runner.state)

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_dry_run_does_not_spawn(self, mock_sleep, mock_run, mock_read):
        """In dry run mode, no subprocess is spawned."""
        mock_read.return_value = "Test resume"
        runner = self._make_runner()
        runner.run_one_iteration()
        mock_run.assert_not_called()

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_spawns_claude_subprocess(self, mock_sleep, mock_run, mock_read):
        """Non-dry-run spawns a real subprocess."""
        mock_read.return_value = "Test resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=False,
            max_iterations=1,
            cooldown_seconds=5,
        )
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()
        mock_run.assert_called_once()

        # Verify the command starts with "claude"
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        self.assertEqual(cmd[0], "claude")

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_env_unsets_api_key(self, mock_sleep, mock_run, mock_read):
        """Subprocess env should NOT contain ANTHROPIC_API_KEY."""
        mock_read.return_value = "Test resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=False,
            max_iterations=1,
        )
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()

        call_kwargs = mock_run.call_args[1] if mock_run.call_args[1] else {}
        env = call_kwargs.get("env", {})
        if env:
            self.assertNotIn("ANTHROPIC_API_KEY", env)

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_records_clean_exit(self, mock_sleep, mock_run, mock_read):
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(project_dir="/tmp/test", dry_run=False, max_iterations=2)
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()
        self.assertEqual(runner.state.total_sessions, 1)
        self.assertEqual(runner.state.total_crashes, 0)

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_records_crash(self, mock_sleep, mock_run, mock_read):
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=1)

        cfg = AutoLoopConfig(project_dir="/tmp/test", dry_run=False, max_iterations=2)
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()
        self.assertEqual(runner.state.total_crashes, 1)

    @patch("cca_autoloop.check_no_other_cca_sessions", return_value=(True, "ok"))
    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_run_loop_stops_at_max_iterations(self, mock_sleep, mock_run, mock_read, mock_check):
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=False,
            max_iterations=3,
            cooldown_seconds=5,
        )
        runner = AutoLoopRunner(cfg)
        # Simulate that sessions last > 30s so short-session guard doesn't trip
        original_record = runner.state.record_session
        def fake_record(exit_code, duration, model=""):
            original_record(exit_code=exit_code, duration=max(duration, 60.0), model=model)
        runner.state.record_session = fake_record

        runner.run()
        self.assertEqual(mock_run.call_count, 3)

    @patch("cca_autoloop.check_no_other_cca_sessions", return_value=(True, "ok"))
    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_run_loop_stops_on_consecutive_crashes(self, mock_sleep, mock_run, mock_read, mock_check):
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=1)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=False,
            max_iterations=10,
            cooldown_seconds=5,
        )
        runner = AutoLoopRunner(cfg)
        runner.run()
        # Should stop after 3 consecutive crashes, not 10
        self.assertEqual(mock_run.call_count, 3)

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_dry_run_loop(self, mock_sleep, mock_read):
        mock_read.return_value = "Resume"

        runner = self._make_runner()
        runner.run()
        # Should complete 3 iterations (max_iterations=3)
        self.assertEqual(runner.state.iteration, 3)

    def test_audit_log_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "autoloop.log")
            cfg = AutoLoopConfig(
                project_dir=tmpdir,
                dry_run=True,
                max_iterations=1,
                log_file=log_path,
            )
            runner = AutoLoopRunner(cfg)
            runner.run()

            self.assertTrue(os.path.exists(log_path))
            with open(log_path) as f:
                lines = f.readlines()
            self.assertGreater(len(lines), 0)
            entry = json.loads(lines[0])
            self.assertIn("event", entry)
            self.assertIn("ts", entry)

    def test_state_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "autoloop_state.json")
            cfg = AutoLoopConfig(
                project_dir=tmpdir,
                dry_run=True,
                max_iterations=2,
                state_file=state_path,
            )
            runner = AutoLoopRunner(cfg)
            runner.run()

            self.assertTrue(os.path.exists(state_path))
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["total_sessions"], 2)


class TestAutoLoopRunnerModel(unittest.TestCase):
    """Test that runner uses model selection."""

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_dry_run_records_models(self, mock_sleep, mock_read):
        mock_read.return_value = "Resume"
        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=True,
            max_iterations=4,
            model_strategy="round-robin",
        )
        runner = AutoLoopRunner(cfg)
        runner.run()
        # dry runs are near-instant (<30s) so short session guard stops at 3
        # round-robin: iter1=sonnet, iter2=opus, iter3=sonnet
        self.assertEqual(runner.state._models_used, ["sonnet", "opus", "sonnet"])

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_opus_primary_all_opus(self, mock_sleep, mock_read):
        mock_read.return_value = "Resume"
        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=True,
            max_iterations=3,
            model_strategy="opus-primary",
        )
        runner = AutoLoopRunner(cfg)
        runner.run()
        self.assertEqual(runner.state._models_used, ["opus", "opus", "opus"])

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_model_passed_to_subprocess(self, mock_sleep, mock_run, mock_read):
        """Verify --model flag is in the subprocess command."""
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=False,
            max_iterations=1,
            model_strategy="opus-primary",
        )
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()

        call_args = mock_run.call_args[0][0]
        self.assertIn("--model", call_args)
        model_idx = call_args.index("--model")
        self.assertEqual(call_args[model_idx + 1], "opus")

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_iteration_result_includes_model(self, mock_sleep, mock_read):
        mock_read.return_value = "Resume"
        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            dry_run=True,
            max_iterations=1,
        )
        runner = AutoLoopRunner(cfg)
        result = runner.run_one_iteration()
        self.assertIn("model", result)
        self.assertIn(result["model"], ("opus", "sonnet"))


class TestAutoLoopRunnerCWD(unittest.TestCase):
    """Test that runner sets correct working directory."""

    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_subprocess_cwd_is_project_dir(self, mock_sleep, mock_run, mock_read):
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(
            project_dir="/tmp/test_project",
            dry_run=False,
            max_iterations=1,
        )
        runner = AutoLoopRunner(cfg)
        runner.run_one_iteration()

        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs["cwd"], "/tmp/test_project")


class TestDesktopMode(unittest.TestCase):
    """Test desktop mode (Terminal.app window spawning)."""

    def test_config_desktop_mode_default_false(self):
        cfg = AutoLoopConfig()
        self.assertFalse(cfg.desktop_mode)

    def test_config_desktop_mode_true(self):
        cfg = AutoLoopConfig(desktop_mode=True)
        self.assertTrue(cfg.desktop_mode)

    def test_write_desktop_wrapper_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sentinel = os.path.join(tmpdir, "sentinel")
            prompt = os.path.join(tmpdir, "prompt.txt")
            with open(prompt, "w") as f:
                f.write("test prompt")

            wrapper = write_desktop_wrapper(
                project_dir=tmpdir,
                model="opus",
                model_strategy="opus-primary",
                iteration=1,
                prompt_file=prompt,
                sentinel_file=sentinel,
            )
            self.assertTrue(os.path.exists(wrapper))
            # Should be executable
            self.assertTrue(os.access(wrapper, os.X_OK))
            # Cleanup
            os.unlink(wrapper)

    def test_desktop_window_title(self):
        self.assertEqual(desktop_window_title(1), "CCA-AutoLoop-Iter-1")
        self.assertEqual(desktop_window_title(42), "CCA-AutoLoop-Iter-42")

    def test_write_desktop_wrapper_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sentinel = os.path.join(tmpdir, "sentinel")
            prompt = os.path.join(tmpdir, "prompt.txt")
            with open(prompt, "w") as f:
                f.write("test")

            wrapper = write_desktop_wrapper(
                project_dir="/tmp/project",
                model="sonnet",
                model_strategy="round-robin",
                iteration=3,
                prompt_file=prompt,
                sentinel_file=sentinel,
            )
            with open(wrapper) as f:
                content = f.read()
            self.assertIn("cd \"/tmp/project\"", content)
            self.assertIn("--model \"sonnet\"", content)
            self.assertIn("Iteration 3", content)
            self.assertIn("round-robin", content)
            self.assertIn(sentinel, content)
            self.assertIn("unset ANTHROPIC_API_KEY", content)
            # Window title and auto-close
            self.assertIn("CCA-AutoLoop-Iter-3", content)
            self.assertIn("printf", content)  # title escape sequence
            self.assertIn("close w", content)  # auto-close osascript
            os.unlink(wrapper)

    def test_write_desktop_wrapper_valid_bash(self):
        """Wrapper script must pass bash syntax check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sentinel = os.path.join(tmpdir, "sentinel")
            prompt = os.path.join(tmpdir, "prompt.txt")
            with open(prompt, "w") as f:
                f.write("test")

            wrapper = write_desktop_wrapper(
                project_dir="/tmp/project",
                model="opus",
                model_strategy="opus-primary",
                iteration=1,
                prompt_file=prompt,
                sentinel_file=sentinel,
            )
            result = subprocess.run(
                ["bash", "-n", wrapper], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"Bash syntax error: {result.stderr}")
            os.unlink(wrapper)

    def test_wait_for_sentinel_success(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sentinel", delete=False) as f:
            f.write("0\n")
            f.flush()
            result = wait_for_sentinel(f.name, poll_interval=0.01)
        os.unlink(f.name)
        self.assertEqual(result, 0)

    def test_wait_for_sentinel_nonzero_exit(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sentinel", delete=False) as f:
            f.write("1\n")
            f.flush()
            result = wait_for_sentinel(f.name, poll_interval=0.01)
        os.unlink(f.name)
        self.assertEqual(result, 1)

    def test_wait_for_sentinel_timeout(self):
        """Should return 1 on timeout."""
        result = wait_for_sentinel(
            "/nonexistent/sentinel",
            poll_interval=0.01,
            timeout=0.03,
        )
        self.assertEqual(result, 1)

    def test_wait_for_sentinel_delayed_creation(self):
        """Sentinel created after polling starts."""
        import threading
        with tempfile.TemporaryDirectory() as tmpdir:
            sentinel = os.path.join(tmpdir, "sentinel")

            def write_later():
                time.sleep(0.05)
                with open(sentinel, "w") as f:
                    f.write("0\n")

            t = threading.Thread(target=write_later)
            t.start()
            result = wait_for_sentinel(sentinel, poll_interval=0.02, timeout=2.0)
            t.join()
            self.assertEqual(result, 0)

    @patch("cca_autoloop.subprocess.run")
    def test_spawn_desktop_session_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = spawn_desktop_session("/tmp/wrapper.sh")
        self.assertTrue(result)
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "osascript")

    @patch("cca_autoloop.subprocess.run", side_effect=OSError("no osascript"))
    def test_spawn_desktop_session_failure(self, mock_run):
        result = spawn_desktop_session("/tmp/wrapper.sh")
        self.assertFalse(result)

    @patch("cca_autoloop.subprocess.run")
    def test_close_desktop_window_no_crash(self, mock_run):
        """close_desktop_window should not raise even if window doesn't exist."""
        mock_run.return_value = MagicMock(returncode=0)
        close_desktop_window(1)  # Should not raise
        mock_run.assert_called_once()

    @patch("cca_autoloop.subprocess.run", side_effect=OSError("no osascript"))
    def test_close_desktop_window_handles_error(self, mock_run):
        """close_desktop_window should swallow errors."""
        close_desktop_window(99)  # Should not raise

    @patch("cca_autoloop.spawn_desktop_session")
    @patch("cca_autoloop.wait_for_sentinel")
    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_runner_desktop_mode_calls_spawn(self, mock_sleep, mock_read, mock_wait, mock_spawn):
        """Runner in desktop mode should use spawn_desktop_session."""
        mock_read.return_value = "Resume"
        mock_spawn.return_value = True
        mock_wait.return_value = 0

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            desktop_mode=True,
            max_iterations=1,
        )
        runner = AutoLoopRunner(cfg)
        result = runner.run_one_iteration()

        mock_spawn.assert_called_once()
        mock_wait.assert_called_once()
        self.assertEqual(result["exit_code"], 0)

    @patch("cca_autoloop.spawn_desktop_session")
    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.time.sleep")
    def test_runner_desktop_mode_spawn_failure(self, mock_sleep, mock_read, mock_spawn):
        """If osascript fails, exit code should be 1."""
        mock_read.return_value = "Resume"
        mock_spawn.return_value = False

        cfg = AutoLoopConfig(
            project_dir="/tmp/test",
            desktop_mode=True,
            max_iterations=1,
        )
        runner = AutoLoopRunner(cfg)
        result = runner.run_one_iteration()
        self.assertEqual(result["exit_code"], 1)


class TestAutoLoopCLI(unittest.TestCase):
    """Test CLI interface."""

    @patch("cca_autoloop.AutoLoopRunner")
    def test_cli_default(self, mock_runner_cls):
        from cca_autoloop import cli_main
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        cli_main(["start"])
        mock_runner.run.assert_called_once()

    @patch("cca_autoloop.AutoLoopRunner")
    def test_cli_dry_run(self, mock_runner_cls):
        from cca_autoloop import cli_main
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        cli_main(["start", "--dry-run"])
        # Config should have dry_run=True
        cfg = mock_runner_cls.call_args[0][0]
        self.assertTrue(cfg.dry_run)

    @patch("cca_autoloop.AutoLoopRunner")
    def test_cli_max_iterations(self, mock_runner_cls):
        from cca_autoloop import cli_main
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        cli_main(["start", "--max-iterations", "5"])
        cfg = mock_runner_cls.call_args[0][0]
        self.assertEqual(cfg.max_iterations, 5)

class TestSessionDedup(unittest.TestCase):
    """Test session de-duplication (one CCA session at a time)."""

    @patch("cca_autoloop.subprocess.run")
    def test_no_sessions_is_safe(self, mock_run):
        mock_run.return_value = MagicMock(stdout="  PID COMMAND\n  123 /bin/bash\n")
        safe, msg = check_no_other_cca_sessions()
        self.assertTrue(safe)

    @patch("cca_autoloop.subprocess.run")
    def test_existing_cca_cli_blocks(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="  PID COMMAND\n  999 claude --dangerously-skip-permissions CCA/ClaudeCodeAdvancements\n"
        )
        safe, msg = check_no_other_cca_sessions()
        self.assertFalse(safe)
        self.assertIn("1", msg)

    @patch("cca_autoloop.subprocess.run", side_effect=OSError("no ps"))
    def test_ps_failure_allows_launch(self, mock_run):
        """If ps fails, don't block — fail open."""
        safe, msg = check_no_other_cca_sessions()
        self.assertTrue(safe)

    @patch("cca_autoloop.check_no_other_cca_sessions", return_value=(False, "1 session running"))
    @patch("cca_autoloop.read_resume_prompt")
    @patch("cca_autoloop.subprocess.run")
    @patch("cca_autoloop.time.sleep")
    def test_runner_blocked_by_dedup(self, mock_sleep, mock_run, mock_read, mock_check):
        """Runner should refuse to start if dedup check fails."""
        mock_read.return_value = "Resume"
        mock_run.return_value = MagicMock(returncode=0)

        cfg = AutoLoopConfig(project_dir="/tmp/test", dry_run=False, max_iterations=3)
        runner = AutoLoopRunner(cfg)
        runner.run()
        # Should not have spawned any sessions
        mock_run.assert_not_called()


    @patch("cca_autoloop.AutoLoopRunner")
    def test_cli_desktop(self, mock_runner_cls):
        from cca_autoloop import cli_main
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        cli_main(["start", "--desktop"])
        cfg = mock_runner_cls.call_args[0][0]
        self.assertTrue(cfg.desktop_mode)

    @patch("cca_autoloop.AutoLoopRunner")
    def test_cli_model_strategy(self, mock_runner_cls):
        from cca_autoloop import cli_main
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        cli_main(["start", "--model-strategy", "opus-primary"])
        cfg = mock_runner_cls.call_args[0][0]
        self.assertEqual(cfg.model_strategy, "opus-primary")

    def test_cli_status(self):
        from cca_autoloop import cli_main
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")
            with open(state_path, "w") as f:
                json.dump({"iteration": 5, "total_sessions": 5, "total_crashes": 1}, f)
            # Should not raise
            cli_main(["status", "--state-file", state_path])


if __name__ == "__main__":
    unittest.main()
