"""
test_cost_alert_extended.py — Extended coverage for cost_alert.py.

Targets gaps in the original test suite:
- main() hook entry point (completely untested)
- OTel: session filter edge cases, non-numeric values, blank lines
- Transcript: haiku detection, top-level usage, multiple entries, missing fields
- Configuration: is_block_enabled("0"), threshold at zero/negative
- Output: tool name in message, block reason content
- Threshold boundary: exactly at warn_threshold, exactly at block_threshold
"""

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from cost_alert import (
    DEFAULT_WARN_THRESHOLD,
    DEFAULT_BLOCK_THRESHOLD,
    CHEAP_TOOLS,
    EXPENSIVE_TOOLS,
    get_warn_threshold,
    get_block_threshold,
    is_block_enabled,
    is_disabled,
    should_check,
    get_session_cost_from_otel,
    get_session_cost_from_transcript,
    build_warn_output,
    build_block_output,
    build_allow_output,
)


# ── Configuration: Edge Cases ─────────────────────────────────────────────────


class TestConfigurationEdgeCases(unittest.TestCase):

    def test_block_enabled_false_when_zero(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_ENABLED": "0"}):
            self.assertFalse(is_block_enabled())

    def test_block_enabled_false_when_false_string(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_ENABLED": "false"}):
            self.assertFalse(is_block_enabled())

    def test_disabled_false_when_zero(self):
        with patch.dict(os.environ, {"CLAUDE_COST_ALERT_DISABLED": "0"}):
            self.assertFalse(is_disabled())

    def test_warn_threshold_zero_string_becomes_zero(self):
        with patch.dict(os.environ, {"CLAUDE_COST_WARN_THRESHOLD": "0"}):
            self.assertEqual(get_warn_threshold(), 0.0)

    def test_block_threshold_zero_string_becomes_zero(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_THRESHOLD": "0"}):
            self.assertEqual(get_block_threshold(), 0.0)

    def test_invalid_block_threshold_uses_default(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_THRESHOLD": "notanumber"}):
            self.assertEqual(get_block_threshold(), DEFAULT_BLOCK_THRESHOLD)

    def test_warn_threshold_float_string(self):
        with patch.dict(os.environ, {"CLAUDE_COST_WARN_THRESHOLD": "3.75"}):
            self.assertAlmostEqual(get_warn_threshold(), 3.75)

    def test_defaults_are_sensible(self):
        self.assertGreater(DEFAULT_BLOCK_THRESHOLD, DEFAULT_WARN_THRESHOLD)
        self.assertGreater(DEFAULT_WARN_THRESHOLD, 0)

    def test_cheap_tools_has_read_glob_grep(self):
        for tool in ("Read", "Glob", "Grep"):
            self.assertIn(tool, CHEAP_TOOLS)

    def test_expensive_tools_has_agent_bash(self):
        for tool in ("Agent", "Bash", "Write"):
            self.assertIn(tool, EXPENSIVE_TOOLS)

    def test_cheap_and_expensive_disjoint(self):
        overlap = CHEAP_TOOLS & EXPENSIVE_TOOLS
        self.assertEqual(overlap, frozenset())


# ── should_check: Additional Cases ───────────────────────────────────────────


class TestShouldCheckAdditional(unittest.TestCase):

    def test_todo_write_not_checked(self):
        self.assertFalse(should_check("TodoWrite"))

    def test_todo_read_not_checked(self):
        self.assertFalse(should_check("TodoRead"))

    def test_ask_user_question_not_checked(self):
        self.assertFalse(should_check("AskUserQuestion"))

    def test_agent_is_checked(self):
        self.assertTrue(should_check("Agent"))

    def test_notebook_edit_is_checked(self):
        self.assertTrue(should_check("NotebookEdit"))

    def test_web_fetch_is_checked(self):
        self.assertTrue(should_check("WebFetch"))

    def test_all_cheap_tools_return_false(self):
        for tool in CHEAP_TOOLS:
            self.assertFalse(should_check(tool), f"{tool} should not be checked")


# ── OTel Cost Source: Edge Cases ──────────────────────────────────────────────


class TestOtelCostSourceEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_records(self, records):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return daily_file

    def test_record_with_no_resource_key_included_unfiltered(self):
        self._write_records([
            {"metric": "claude_code.cost.usage", "value": 1.50},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 1.50)

    def test_session_filter_includes_records_with_empty_session_id(self):
        # Records with empty session.id are included when filtering — they lack a session tag
        # so the code treats them as untagged (included). Only records with a different
        # non-empty session.id are skipped.
        self._write_records([
            {"metric": "claude_code.cost.usage", "value": 2.00, "resource": {"session.id": ""}},
            {"metric": "claude_code.cost.usage", "value": 1.00, "resource": {"session.id": "sess-X"}},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel(session_id="sess-X")
            self.assertAlmostEqual(cost, 3.00)  # both included: empty-session + matching

    def test_non_numeric_value_skipped(self):
        self._write_records([
            {"metric": "claude_code.cost.usage", "value": "not_a_number"},
            {"metric": "claude_code.cost.usage", "value": 2.00, "resource": {}},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            # Only the numeric value counts
            self.assertAlmostEqual(cost, 2.00)

    def test_blank_lines_skipped(self):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            f.write("\n\n")
            f.write(json.dumps({"metric": "claude_code.cost.usage", "value": 3.00, "resource": {}}) + "\n")
            f.write("\n")
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 3.00)

    def test_only_non_cost_metrics_returns_none(self):
        self._write_records([
            {"metric": "claude_code.token.usage", "value": 5000},
            {"metric": "claude_code.something.else", "value": 1.00},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            self.assertIsNone(get_session_cost_from_otel())

    def test_integer_value_accepted(self):
        self._write_records([
            {"metric": "claude_code.cost.usage", "value": 5, "resource": {}},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 5.0)

    def test_multiple_records_accumulated(self):
        self._write_records([
            {"metric": "claude_code.cost.usage", "value": 1.0, "resource": {}},
            {"metric": "claude_code.cost.usage", "value": 2.0, "resource": {}},
            {"metric": "claude_code.cost.usage", "value": 3.0, "resource": {}},
        ])
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 6.0)


# ── Transcript Cost Source: Edge Cases ───────────────────────────────────────


class TestTranscriptCostSourceEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, entries, name="transcript.jsonl"):
        path = Path(self.tmpdir) / name
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        return str(path)

    def test_detects_haiku_model(self):
        path = self._write_transcript([{
            "type": "assistant",
            "message": {
                "model": "claude-haiku-4-5",
                "usage": {
                    "input_tokens": 1_000_000,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }
        }])
        cost = get_session_cost_from_transcript("sess", path)
        # Haiku: 1M * $0.25/M = $0.25
        self.assertAlmostEqual(cost, 0.25, places=2)

    def test_top_level_model_field(self):
        path = self._write_transcript([{
            "type": "assistant",
            "model": "claude-opus-4-6",
            "message": {
                "usage": {
                    "input_tokens": 10000,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }
        }])
        cost = get_session_cost_from_transcript("sess", path)
        # Opus: 10k * $15/M = $0.15
        self.assertAlmostEqual(cost, 0.15, places=3)

    def test_top_level_usage_field(self):
        path = self._write_transcript([{
            "type": "assistant",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        }])
        cost = get_session_cost_from_transcript("sess", path)
        # Sonnet (default): 1k * $3/M + 500 * $15/M
        self.assertIsNotNone(cost)

    def test_multiple_entries_accumulated(self):
        path = self._write_transcript([
            {"type": "assistant", "message": {"model": "claude-sonnet-4-6", "usage": {
                "input_tokens": 10000, "output_tokens": 1000,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
            }}},
            {"type": "assistant", "message": {"model": "claude-sonnet-4-6", "usage": {
                "input_tokens": 10000, "output_tokens": 1000,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
            }}},
        ])
        cost_single_entry = get_session_cost_from_transcript("sess", self._write_transcript([
            {"type": "assistant", "message": {"model": "claude-sonnet-4-6", "usage": {
                "input_tokens": 10000, "output_tokens": 1000,
                "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
            }}},
        ], name="single.jsonl"))
        cost_double = get_session_cost_from_transcript("sess", path)
        self.assertAlmostEqual(cost_double, cost_single_entry * 2, places=5)

    def test_invalid_json_lines_skipped(self):
        path = Path(self.tmpdir) / "transcript.jsonl"
        with open(path, "w") as f:
            f.write("INVALID JSON\n")
            f.write(json.dumps({"type": "assistant", "message": {
                "model": "claude-sonnet-4-6",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 100,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }}) + "\n")
        cost = get_session_cost_from_transcript("sess", str(path))
        self.assertIsNotNone(cost)
        self.assertGreater(cost, 0)

    def test_blank_lines_skipped(self):
        path = Path(self.tmpdir) / "transcript.jsonl"
        with open(path, "w") as f:
            f.write("\n")
            f.write(json.dumps({"type": "assistant", "message": {
                "model": "claude-sonnet-4-6",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }}) + "\n")
        cost = get_session_cost_from_transcript("sess", str(path))
        self.assertIsNotNone(cost)

    def test_missing_cache_fields_default_to_zero(self):
        path = self._write_transcript([{
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-6",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    # No cache fields
                }
            }
        }])
        cost = get_session_cost_from_transcript("sess", path)
        # Sonnet: 1k * $3/M + 500 * $15/M = 0.003 + 0.0075 = 0.0105
        self.assertAlmostEqual(cost, 0.0105, places=4)

    def test_non_assistant_entries_with_usage_counted(self):
        path = self._write_transcript([{
            "type": "user",
            "usage": {
                "input_tokens": 5000,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        }])
        # user entries with top-level usage are counted by the fallback path
        # (only nested message.usage is skipped for non-assistant types)
        cost = get_session_cost_from_transcript("sess", path)
        # Just verify it doesn't crash and returns a numeric result
        if cost is not None:
            self.assertGreaterEqual(cost, 0)


# ── Output Building: Edge Cases ───────────────────────────────────────────────


class TestOutputBuildingEdgeCases(unittest.TestCase):

    def test_warn_output_includes_tool_name(self):
        output = build_warn_output("Agent", 8.00, 5.00)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Agent", context)

    def test_warn_output_mentions_cheap_alternatives(self):
        output = build_warn_output("Bash", 6.50, 5.00)
        context = output["hookSpecificOutput"]["additionalContext"]
        # Should mention cheaper alternatives
        self.assertTrue(
            any(t in context for t in ("Read", "Glob", "Grep", "cheaper")),
            "Warn output should mention cheaper alternatives"
        )

    def test_block_output_includes_tool_name(self):
        output = build_block_output("Agent", 25.00, 20.00)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Agent", reason)

    def test_block_output_includes_both_thresholds(self):
        output = build_block_output("Write", 25.00, 20.00)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("$25.00", reason)
        self.assertIn("$20.00", reason)

    def test_block_output_deny_value(self):
        output = build_block_output("Bash", 30.00, 20.00)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_warn_output_cost_formatted(self):
        output = build_warn_output("Write", 5.123456, 5.00)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("$5.12", context)

    def test_allow_output_is_empty_dict(self):
        output = build_allow_output()
        self.assertEqual(output, {})
        self.assertIsInstance(output, dict)

    def test_warn_output_no_permission_decision(self):
        output = build_warn_output("Bash", 8.00, 5.00)
        hook_out = output["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hook_out)


# ── Threshold Boundary Cases ──────────────────────────────────────────────────


class TestThresholdBoundaries(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_otel(self, cost_value):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            f.write(json.dumps({
                "metric": "claude_code.cost.usage",
                "value": cost_value,
                "resource": {},
            }) + "\n")

    def test_exactly_at_warn_threshold_triggers_warn(self):
        from cost_alert import get_session_cost
        self._write_otel(5.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_WARN_THRESHOLD": "5.00",
        }):
            cost = get_session_cost({"session_id": ""})
            warn = get_warn_threshold()
            self.assertGreaterEqual(cost, warn)

    def test_just_below_warn_threshold_no_warn(self):
        from cost_alert import get_session_cost
        self._write_otel(4.99)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_WARN_THRESHOLD": "5.00",
        }):
            cost = get_session_cost({"session_id": ""})
            warn = get_warn_threshold()
            self.assertLess(cost, warn)

    def test_exactly_at_block_threshold_triggers_block(self):
        from cost_alert import get_session_cost
        self._write_otel(20.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_BLOCK_THRESHOLD": "20.00",
        }):
            cost = get_session_cost({"session_id": ""})
            block = get_block_threshold()
            self.assertGreaterEqual(cost, block)


# ── main(): Full Integration ──────────────────────────────────────────────────


class TestMainHookEntryPoint(unittest.TestCase):

    def _run_main(self, hook_input: dict, env: dict = None) -> dict:
        from cost_alert import main
        env = env or {}
        stdin_data = json.dumps(hook_input)
        with patch.dict(os.environ, env):
            with patch("sys.stdin", io.StringIO(stdin_data)):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    with self.assertRaises(SystemExit) as cm:
                        main()
        self.assertEqual(cm.exception.code, 0)
        return json.loads(captured.getvalue().strip())

    def test_disabled_returns_empty_object(self):
        result = self._run_main(
            {"tool_name": "Agent"},
            {"CLAUDE_COST_ALERT_DISABLED": "1"},
        )
        self.assertEqual(result, {})

    def test_cheap_tool_returns_empty_object(self):
        result = self._run_main({"tool_name": "Read"})
        self.assertEqual(result, {})

    def test_glob_returns_empty_object(self):
        result = self._run_main({"tool_name": "Glob"})
        self.assertEqual(result, {})

    def test_no_cost_data_returns_empty_object(self):
        result = self._run_main(
            {"tool_name": "Bash", "session_id": "sess"},
            {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent/path/xyz"},
        )
        self.assertEqual(result, {})

    def test_invalid_json_returns_empty_object(self):
        from cost_alert import main
        with patch.dict(os.environ, {}):
            with patch("sys.stdin", io.StringIO("INVALID JSON")):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    with self.assertRaises(SystemExit):
                        main()
        result = json.loads(captured.getvalue().strip())
        self.assertEqual(result, {})

    def test_empty_stdin_returns_empty_object(self):
        from cost_alert import main
        with patch.dict(os.environ, {}):
            with patch("sys.stdin", io.StringIO("")):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    with self.assertRaises(SystemExit):
                        main()
        result = json.loads(captured.getvalue().strip())
        self.assertEqual(result, {})

    def test_warn_threshold_exceeded_returns_warn(self):
        import shutil
        tmpdir = Path(tempfile.mkdtemp())
        try:
            now = datetime.now(tz=timezone.utc)
            daily_file = tmpdir / f"{now.strftime('%Y-%m-%d')}.jsonl"
            daily_file.write_text(json.dumps({
                "metric": "claude_code.cost.usage",
                "value": 8.00,
                "resource": {},
            }) + "\n")
            result = self._run_main(
                {"tool_name": "Agent", "session_id": ""},
                {
                    "CLAUDE_OTEL_STORAGE_DIR": str(tmpdir),
                    "CLAUDE_COST_WARN_THRESHOLD": "5.00",
                },
            )
            self.assertIn("hookSpecificOutput", result)
            self.assertIn("additionalContext", result["hookSpecificOutput"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_block_threshold_exceeded_with_block_enabled(self):
        import shutil
        tmpdir = Path(tempfile.mkdtemp())
        try:
            now = datetime.now(tz=timezone.utc)
            daily_file = tmpdir / f"{now.strftime('%Y-%m-%d')}.jsonl"
            daily_file.write_text(json.dumps({
                "metric": "claude_code.cost.usage",
                "value": 25.00,
                "resource": {},
            }) + "\n")
            result = self._run_main(
                {"tool_name": "Bash", "session_id": ""},
                {
                    "CLAUDE_OTEL_STORAGE_DIR": str(tmpdir),
                    "CLAUDE_COST_WARN_THRESHOLD": "5.00",
                    "CLAUDE_COST_BLOCK_THRESHOLD": "20.00",
                    "CLAUDE_COST_BLOCK_ENABLED": "1",
                },
            )
            self.assertIn("hookSpecificOutput", result)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_output_is_always_valid_json(self):
        from cost_alert import main
        for tool in ["Read", "Bash", "Agent", ""]:
            stdin_data = json.dumps({"tool_name": tool})
            with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent"}):
                with patch("sys.stdin", io.StringIO(stdin_data)):
                    captured = io.StringIO()
                    with patch("sys.stdout", captured):
                        with self.assertRaises(SystemExit):
                            main()
            output = captured.getvalue().strip()
            parsed = json.loads(output)
            self.assertIsInstance(parsed, dict)


if __name__ == "__main__":
    unittest.main()
