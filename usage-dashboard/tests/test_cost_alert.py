"""Tests for USAGE-3: Cost Threshold Alert Hook (PreToolUse)."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from cost_alert import (
    get_warn_threshold,
    get_block_threshold,
    is_block_enabled,
    is_disabled,
    should_check,
    get_session_cost_from_otel,
    get_session_cost_from_transcript,
    get_session_cost,
    build_warn_output,
    build_block_output,
    build_allow_output,
    CHEAP_TOOLS,
    EXPENSIVE_TOOLS,
    DEFAULT_WARN_THRESHOLD,
    DEFAULT_BLOCK_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------

class TestConfiguration(unittest.TestCase):

    def test_default_warn_threshold(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_COST_WARN_THRESHOLD", None)
            self.assertEqual(get_warn_threshold(), DEFAULT_WARN_THRESHOLD)

    def test_custom_warn_threshold(self):
        with patch.dict(os.environ, {"CLAUDE_COST_WARN_THRESHOLD": "10.50"}):
            self.assertAlmostEqual(get_warn_threshold(), 10.50)

    def test_invalid_warn_threshold_uses_default(self):
        with patch.dict(os.environ, {"CLAUDE_COST_WARN_THRESHOLD": "notanumber"}):
            self.assertEqual(get_warn_threshold(), DEFAULT_WARN_THRESHOLD)

    def test_default_block_threshold(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_COST_BLOCK_THRESHOLD", None)
            self.assertEqual(get_block_threshold(), DEFAULT_BLOCK_THRESHOLD)

    def test_custom_block_threshold(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_THRESHOLD": "50.00"}):
            self.assertAlmostEqual(get_block_threshold(), 50.00)

    def test_block_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_COST_BLOCK_ENABLED", None)
            self.assertFalse(is_block_enabled())

    def test_block_enabled(self):
        with patch.dict(os.environ, {"CLAUDE_COST_BLOCK_ENABLED": "1"}):
            self.assertTrue(is_block_enabled())

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_COST_ALERT_DISABLED", None)
            self.assertFalse(is_disabled())

    def test_disabled_when_set(self):
        with patch.dict(os.environ, {"CLAUDE_COST_ALERT_DISABLED": "1"}):
            self.assertTrue(is_disabled())


# ---------------------------------------------------------------------------
# Tool classification tests
# ---------------------------------------------------------------------------

class TestShouldCheck(unittest.TestCase):

    def test_cheap_tools_skipped(self):
        for tool in CHEAP_TOOLS:
            self.assertFalse(should_check(tool), f"{tool} should be skipped")

    def test_expensive_tools_checked(self):
        for tool in EXPENSIVE_TOOLS:
            self.assertTrue(should_check(tool), f"{tool} should be checked")

    def test_unknown_tool_checked(self):
        self.assertTrue(should_check("SomeNewTool"))

    def test_empty_tool_checked(self):
        self.assertTrue(should_check(""))


# ---------------------------------------------------------------------------
# OTel cost source tests
# ---------------------------------------------------------------------------

class TestOtelCostSource(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_storage_dir(self):
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent"}):
            self.assertIsNone(get_session_cost_from_otel())

    def test_no_today_file(self):
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            self.assertIsNone(get_session_cost_from_otel())

    def test_reads_cost_metric(self):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        records = [
            {"metric": "claude_code.cost.usage", "value": 2.50, "resource": {"session.id": "sess-1"}},
            {"metric": "claude_code.cost.usage", "value": 1.25, "resource": {"session.id": "sess-1"}},
            {"metric": "claude_code.token.usage", "value": 5000, "resource": {}},  # Not cost
        ]
        with open(daily_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 3.75)

    def test_filters_by_session(self):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        records = [
            {"metric": "claude_code.cost.usage", "value": 2.00, "resource": {"session.id": "sess-A"}},
            {"metric": "claude_code.cost.usage", "value": 3.00, "resource": {"session.id": "sess-B"}},
        ]
        with open(daily_file, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel(session_id="sess-A")
            self.assertAlmostEqual(cost, 2.00)

    def test_empty_file_returns_none(self):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        daily_file.touch()

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            self.assertIsNone(get_session_cost_from_otel())

    def test_invalid_json_lines_skipped(self):
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"metric": "claude_code.cost.usage", "value": 1.0, "resource": {}}) + "\n")

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            cost = get_session_cost_from_otel()
            self.assertAlmostEqual(cost, 1.0)


# ---------------------------------------------------------------------------
# Transcript cost source tests
# ---------------------------------------------------------------------------

class TestTranscriptCostSource(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_transcript_path(self):
        self.assertIsNone(get_session_cost_from_transcript("sess-1"))

    def test_missing_transcript_file(self):
        self.assertIsNone(get_session_cost_from_transcript("sess-1", "/nonexistent.jsonl"))

    def test_reads_transcript_usage(self):
        transcript = Path(self.tmpdir) / "test.jsonl"
        entries = [
            {
                "type": "assistant",
                "model": "claude-sonnet-4-6",
                "message": {
                    "model": "claude-sonnet-4-6",
                    "usage": {
                        "input_tokens": 10000,
                        "output_tokens": 2000,
                        "cache_read_input_tokens": 5000,
                        "cache_creation_input_tokens": 1000,
                    }
                }
            }
        ]
        with open(transcript, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        cost = get_session_cost_from_transcript("sess-1", str(transcript))
        self.assertIsNotNone(cost)
        # Sonnet: 10k * $3/M + 2k * $15/M + 5k * $0.30/M + 1k * $3.75/M
        # = 0.03 + 0.03 + 0.0015 + 0.00375 = 0.06525
        self.assertAlmostEqual(cost, 0.0653, places=3)

    def test_detects_opus_model(self):
        transcript = Path(self.tmpdir) / "test.jsonl"
        entries = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-6",
                    "usage": {
                        "input_tokens": 10000,
                        "output_tokens": 2000,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    }
                }
            }
        ]
        with open(transcript, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        cost = get_session_cost_from_transcript("sess-1", str(transcript))
        # Opus: 10k * $15/M + 2k * $75/M = 0.15 + 0.15 = 0.30
        self.assertAlmostEqual(cost, 0.30, places=2)

    def test_empty_transcript_returns_none(self):
        transcript = Path(self.tmpdir) / "test.jsonl"
        transcript.touch()
        self.assertIsNone(get_session_cost_from_transcript("sess-1", str(transcript)))


# ---------------------------------------------------------------------------
# Combined cost source tests
# ---------------------------------------------------------------------------

class TestGetSessionCost(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_prefers_otel_over_transcript(self):
        # Set up OTel data
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            f.write(json.dumps({"metric": "claude_code.cost.usage", "value": 7.50, "resource": {}}) + "\n")

        # Set up transcript data
        transcript = Path(self.tmpdir) / "transcript.jsonl"
        with open(transcript, "w") as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 100000, "output_tokens": 50000, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}
            }) + "\n")

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            hook_input = {"session_id": "sess-1", "transcript_path": str(transcript)}
            cost = get_session_cost(hook_input)
            # Should return OTel value (7.50), not transcript value
            self.assertAlmostEqual(cost, 7.50)

    def test_falls_back_to_transcript(self):
        transcript = Path(self.tmpdir) / "transcript.jsonl"
        with open(transcript, "w") as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 1000000, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}
            }) + "\n")

        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent"}):
            hook_input = {"session_id": "sess-1", "transcript_path": str(transcript)}
            cost = get_session_cost(hook_input)
            # Sonnet: 1M * $3/M = $3.00
            self.assertAlmostEqual(cost, 3.00, places=1)

    def test_no_data_returns_none(self):
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent"}):
            hook_input = {"session_id": "sess-1"}
            self.assertIsNone(get_session_cost(hook_input))


# ---------------------------------------------------------------------------
# Output building tests
# ---------------------------------------------------------------------------

class TestOutputBuilding(unittest.TestCase):

    def test_warn_output_format(self):
        output = build_warn_output("Agent", 6.50, 5.00)
        self.assertIn("hookSpecificOutput", output)
        self.assertIn("additionalContext", output["hookSpecificOutput"])
        self.assertIn("$6.50", output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("$5.00", output["hookSpecificOutput"]["additionalContext"])
        # Should NOT have permissionDecision (non-blocking)
        self.assertNotIn("permissionDecision", output["hookSpecificOutput"])

    def test_block_output_format(self):
        output = build_block_output("Bash", 25.00, 20.00)
        self.assertIn("hookSpecificOutput", output)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("$25.00", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_allow_output(self):
        self.assertEqual(build_allow_output(), {})

    def test_warn_output_valid_json(self):
        output = build_warn_output("Write", 5.50, 5.00)
        serialized = json.dumps(output)
        parsed = json.loads(serialized)
        self.assertEqual(parsed, output)

    def test_block_output_valid_json(self):
        output = build_block_output("Edit", 21.00, 20.00)
        serialized = json.dumps(output)
        parsed = json.loads(serialized)
        self.assertEqual(parsed, output)


# ---------------------------------------------------------------------------
# Integration: full hook simulation
# ---------------------------------------------------------------------------

class TestFullHookFlow(unittest.TestCase):
    """Simulate the complete hook decision flow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _setup_otel_cost(self, cost_value: float):
        """Write an OTel cost record for today."""
        now = datetime.now(tz=timezone.utc)
        daily_file = Path(self.tmpdir) / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with open(daily_file, "w") as f:
            f.write(json.dumps({
                "metric": "claude_code.cost.usage",
                "value": cost_value,
                "resource": {},
            }) + "\n")

    def test_cheap_tool_always_allowed(self):
        """Read/Glob/Grep should never trigger alerts regardless of cost."""
        self._setup_otel_cost(100.00)
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": self.tmpdir}):
            self.assertFalse(should_check("Read"))
            self.assertFalse(should_check("Glob"))
            self.assertFalse(should_check("Grep"))

    def test_under_threshold_allowed(self):
        """Cost under warn threshold = silent allow."""
        self._setup_otel_cost(2.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_WARN_THRESHOLD": "5.00",
        }):
            hook_input = {"session_id": "", "tool_name": "Bash"}
            cost = get_session_cost(hook_input)
            self.assertAlmostEqual(cost, 2.00)
            self.assertLess(cost, get_warn_threshold())

    def test_warn_threshold_triggers_warning(self):
        """Cost at/above warn threshold = warning context injected."""
        self._setup_otel_cost(6.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_WARN_THRESHOLD": "5.00",
        }):
            hook_input = {"session_id": "", "tool_name": "Agent"}
            cost = get_session_cost(hook_input)
            self.assertGreaterEqual(cost, get_warn_threshold())
            output = build_warn_output("Agent", cost, get_warn_threshold())
            self.assertIn("additionalContext", output["hookSpecificOutput"])

    def test_block_threshold_without_block_enabled(self):
        """Cost above block threshold but blocking disabled = warn only."""
        self._setup_otel_cost(25.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_WARN_THRESHOLD": "5.00",
            "CLAUDE_COST_BLOCK_THRESHOLD": "20.00",
        }, clear=False):
            os.environ.pop("CLAUDE_COST_BLOCK_ENABLED", None)
            self.assertFalse(is_block_enabled())
            hook_input = {"session_id": "", "tool_name": "Bash"}
            cost = get_session_cost(hook_input)
            # Should warn, not block
            output = build_warn_output("Bash", cost, get_warn_threshold())
            self.assertNotIn("permissionDecision", output.get("hookSpecificOutput", {}))

    def test_block_threshold_with_block_enabled(self):
        """Cost above block threshold + blocking enabled = deny."""
        self._setup_otel_cost(25.00)
        with patch.dict(os.environ, {
            "CLAUDE_OTEL_STORAGE_DIR": self.tmpdir,
            "CLAUDE_COST_BLOCK_ENABLED": "1",
            "CLAUDE_COST_BLOCK_THRESHOLD": "20.00",
        }):
            hook_input = {"session_id": "", "tool_name": "Write"}
            cost = get_session_cost(hook_input)
            self.assertGreaterEqual(cost, get_block_threshold())
            output = build_block_output("Write", cost, get_block_threshold())
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_no_cost_data_silently_allows(self):
        """When no cost data is available, allow everything."""
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": "/nonexistent"}):
            hook_input = {"session_id": "sess-1", "tool_name": "Bash"}
            cost = get_session_cost(hook_input)
            self.assertIsNone(cost)

    def test_disabled_allows_everything(self):
        """CLAUDE_COST_ALERT_DISABLED=1 bypasses all checks."""
        with patch.dict(os.environ, {"CLAUDE_COST_ALERT_DISABLED": "1"}):
            self.assertTrue(is_disabled())


if __name__ == "__main__":
    unittest.main()
