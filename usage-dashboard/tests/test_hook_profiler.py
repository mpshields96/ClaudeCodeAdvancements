#!/usr/bin/env python3
"""
Tests for hook_profiler.py — Hook Chain Profiler.
Run: python3 usage-dashboard/tests/test_hook_profiler.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import hook_profiler as hp


class TestHookResult(unittest.TestCase):
    def test_avg_ms_single(self):
        r = hp.HookResult(path="test.py", event="PreToolUse(*)")
        r.times_ms = [25.0]
        self.assertAlmostEqual(r.avg_ms, 25.0)

    def test_avg_ms_multiple(self):
        r = hp.HookResult(path="test.py", event="PreToolUse(*)")
        r.times_ms = [20.0, 30.0, 25.0]
        self.assertAlmostEqual(r.avg_ms, 25.0)

    def test_avg_ms_empty(self):
        r = hp.HookResult(path="test.py", event="PreToolUse(*)")
        self.assertEqual(r.avg_ms, 0.0)

    def test_min_max(self):
        r = hp.HookResult(path="test.py", event="PreToolUse(*)")
        r.times_ms = [10.0, 50.0, 30.0]
        self.assertAlmostEqual(r.min_ms, 10.0)
        self.assertAlmostEqual(r.max_ms, 50.0)

    def test_min_max_empty(self):
        r = hp.HookResult(path="test.py", event="PreToolUse(*)")
        self.assertEqual(r.min_ms, 0.0)
        self.assertEqual(r.max_ms, 0.0)


class TestLoadHooksFromSettings(unittest.TestCase):
    def test_loads_hooks_from_valid_settings(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command", "command": "python3 /path/to/hook1.py"},
                            {"type": "command", "command": "python3 /path/to/hook2.py"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        hooks = hp.load_hooks_from_settings(path)
        self.assertEqual(len(hooks), 2)
        self.assertEqual(hooks[0], ("PreToolUse", "", "python3 /path/to/hook1.py"))
        Path(path).unlink()

    def test_loads_hooks_with_matcher(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "python3 /path/to/bash_hook.py"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        hooks = hp.load_hooks_from_settings(path)
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0][1], "Bash")
        Path(path).unlink()

    def test_empty_settings_returns_empty(self):
        settings = {}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        hooks = hp.load_hooks_from_settings(path)
        self.assertEqual(hooks, [])
        Path(path).unlink()

    def test_missing_file_returns_empty(self):
        hooks = hp.load_hooks_from_settings("/nonexistent/path.json")
        self.assertEqual(hooks, [])

    def test_multiple_events(self):
        settings = {
            "hooks": {
                "PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 a.py"}]}],
                "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 b.py"}]}],
                "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 c.py"}]}],
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        hooks = hp.load_hooks_from_settings(path)
        self.assertEqual(len(hooks), 3)
        events = {h[0] for h in hooks}
        self.assertEqual(events, {"PreToolUse", "PostToolUse", "Stop"})
        Path(path).unlink()

    def test_skips_non_command_types(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "webhook", "url": "https://example.com"},
                            {"type": "command", "command": "python3 real.py"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        hooks = hp.load_hooks_from_settings(path)
        self.assertEqual(len(hooks), 1)
        Path(path).unlink()


class TestMakePayload(unittest.TestCase):
    def test_pretooluse_payload(self):
        payload = json.loads(hp._make_payload("PreToolUse", ""))
        self.assertEqual(payload["hook_event_name"], "PreToolUse")
        self.assertEqual(payload["tool_name"], "Read")
        self.assertIn("file_path", payload["tool_input"])

    def test_pretooluse_with_matcher(self):
        payload = json.loads(hp._make_payload("PreToolUse", "Bash"))
        self.assertEqual(payload["tool_name"], "Bash")

    def test_posttooluse_payload(self):
        payload = json.loads(hp._make_payload("PostToolUse", ""))
        self.assertEqual(payload["hook_event_name"], "PostToolUse")
        self.assertIn("tool_output", payload)

    def test_userpromptsubmit_payload(self):
        payload = json.loads(hp._make_payload("UserPromptSubmit", ""))
        self.assertEqual(payload["hook_event_name"], "UserPromptSubmit")
        self.assertIn("user_prompt", payload)

    def test_stop_payload(self):
        payload = json.loads(hp._make_payload("Stop", ""))
        self.assertEqual(payload["hook_event_name"], "Stop")
        self.assertIn("last_assistant_message", payload)

    def test_postcompact_payload(self):
        payload = json.loads(hp._make_payload("PostCompact", ""))
        self.assertEqual(payload["hook_event_name"], "PostCompact")

    def test_unknown_event_still_produces_valid_json(self):
        payload = json.loads(hp._make_payload("FutureEvent", ""))
        self.assertEqual(payload["hook_event_name"], "FutureEvent")


class TestProfileHook(unittest.TestCase):
    def test_profiles_true_command(self):
        elapsed, error = hp.profile_hook("python3 -c pass", "{}")
        self.assertGreater(elapsed, 0)
        self.assertIsNone(error)

    def test_profiles_failing_command(self):
        elapsed, error = hp.profile_hook("python3 -c 'import sys; sys.exit(1)'", "{}")
        self.assertGreater(elapsed, 0)
        # No stderr = no error reported even on non-zero exit
        # This is correct: hooks often exit(0) with no output

    def test_timeout_returns_error(self):
        elapsed, error = hp.profile_hook("sleep 10", "{}", timeout=0.1)
        self.assertEqual(error, "TIMEOUT")

    def test_nonexistent_command_returns_error(self):
        elapsed, error = hp.profile_hook("/nonexistent/command/xyz", "{}")
        self.assertIsNotNone(error)


class TestChainOverhead(unittest.TestCase):
    def test_groups_by_event(self):
        results = [
            hp.HookResult(path="a.py", event="PreToolUse(*)", times_ms=[20.0]),
            hp.HookResult(path="b.py", event="PreToolUse(*)", times_ms=[30.0]),
            hp.HookResult(path="c.py", event="PostToolUse(*)", times_ms=[15.0]),
        ]
        overhead = hp.chain_overhead(results)
        self.assertAlmostEqual(overhead["PreToolUse"], 50.0)
        self.assertAlmostEqual(overhead["PostToolUse"], 15.0)

    def test_empty_results(self):
        overhead = hp.chain_overhead([])
        self.assertEqual(overhead, {})


class TestFormatReport(unittest.TestCase):
    def test_empty_results(self):
        report = hp.format_report([])
        self.assertIn("No hooks found", report)

    def test_single_run_format(self):
        results = [
            hp.HookResult(path="alert.py", event="PreToolUse(*)", times_ms=[20.0]),
        ]
        report = hp.format_report(results, repeat=1)
        self.assertIn("alert.py", report)
        self.assertIn("20.0ms", report)
        self.assertIn("Chain overhead", report)

    def test_multi_run_format(self):
        results = [
            hp.HookResult(path="alert.py", event="PreToolUse(*)", times_ms=[15.0, 20.0, 25.0]),
        ]
        report = hp.format_report(results, repeat=3)
        self.assertIn("Avg", report)
        self.assertIn("Min", report)
        self.assertIn("Max", report)

    def test_error_shown(self):
        results = [
            hp.HookResult(path="broken.py", event="PreToolUse(*)", times_ms=[100.0], error="ImportError"),
        ]
        report = hp.format_report(results)
        self.assertIn("ERRORS", report)
        self.assertIn("ImportError", report)

    def test_slow_warning(self):
        results = [
            hp.HookResult(path="slow.py", event="PreToolUse(*)", times_ms=[150.0]),
        ]
        report = hp.format_report(results)
        self.assertIn("WARNING", report)
        self.assertIn("slow.py", report)


class TestProfileAll(unittest.TestCase):
    def test_with_real_hooks_settings(self):
        """Integration test: profile against a minimal settings file with a fast command."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command", "command": "python3 -c pass"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        results = hp.profile_all(settings_path=path, repeat=1)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0].avg_ms, 0)
        Path(path).unlink()

    def test_slow_threshold_filters(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command", "command": "python3 -c pass"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        # Set threshold very high — should filter out the fast command
        results = hp.profile_all(settings_path=path, slow_threshold_ms=10000)
        self.assertEqual(len(results), 0)
        Path(path).unlink()

    def test_repeat_produces_multiple_times(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command", "command": "python3 -c pass"},
                        ]
                    }
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(settings, f)
            path = f.name

        results = hp.profile_all(settings_path=path, repeat=3)
        self.assertEqual(len(results[0].times_ms), 3)
        Path(path).unlink()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
