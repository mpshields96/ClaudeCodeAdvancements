"""
Tests for CTX-1: context meter hook.
TDD — tests written first.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import meter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_transcript(path: Path, entries: list[dict]):
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _make_user_turn(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def _make_assistant_turn(text: str, input_tokens: int = 0, output_tokens: int = 0) -> dict:
    entry = {"role": "assistant", "content": [{"type": "text", "text": text}]}
    if input_tokens or output_tokens:
        entry["usage"] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    return entry


def _make_usage_entry(input_tokens: int, output_tokens: int) -> dict:
    """Standalone usage entry (some transcript formats have these)."""
    return {"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}


def _make_claude_code_assistant_turn(
    input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict:
    """Real Claude Code transcript format: usage is nested inside 'message'."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "response"}],
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens,
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "output_tokens": output_tokens,
            },
        },
        "sessionId": "test-session",
    }


# ---------------------------------------------------------------------------
# Token estimation from transcript
# ---------------------------------------------------------------------------

class TestTokenEstimation(unittest.TestCase):

    def test_empty_transcript_returns_zero(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            pass
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(Path(f.name))
            self.assertEqual(tokens, 0)
            self.assertEqual(turns, 0)
        finally:
            os.unlink(f.name)

    def test_nonexistent_transcript_returns_zero(self):
        tokens, turns = meter.estimate_tokens_from_transcript(Path("/tmp/nonexistent_ctx_test.jsonl"))
        self.assertEqual(tokens, 0)
        self.assertEqual(turns, 0)

    def test_uses_input_tokens_when_present(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_assistant_turn("Hello", input_tokens=1500, output_tokens=50),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            # Should use input_tokens (1500) as it represents full context at that turn
            self.assertEqual(tokens, 1500)
            self.assertEqual(turns, 1)
        finally:
            os.unlink(str(path))

    def test_uses_max_input_tokens_across_turns(self):
        """input_tokens grows each turn — we want the latest (largest) value."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_assistant_turn("Turn 1", input_tokens=500, output_tokens=20),
            _make_assistant_turn("Turn 2", input_tokens=1200, output_tokens=30),
            _make_assistant_turn("Turn 3", input_tokens=2800, output_tokens=50),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 2800)  # Latest/max input_tokens
            self.assertEqual(turns, 3)
        finally:
            os.unlink(str(path))

    def test_falls_back_to_char_counting_when_no_usage(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        # 400 chars of content across turns → ~100 tokens
        _write_transcript(path, [
            _make_user_turn("A" * 200),
            _make_assistant_turn("B" * 200),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 100)  # 400 chars / 4
            self.assertEqual(turns, 2)
        finally:
            os.unlink(str(path))

    def test_prefers_usage_over_char_count_when_mixed(self):
        """If some turns have usage and some don't, use usage when available."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_user_turn("X" * 1000),  # No usage
            _make_assistant_turn("Y" * 100, input_tokens=3000, output_tokens=80),  # Has usage
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 3000)  # Usage wins
        finally:
            os.unlink(str(path))

    def test_handles_malformed_lines_gracefully(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
            f.write("not json\n")
            f.write('{"role": "user", "content": "hello"}\n')
            f.write("{bad json\n")
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            # Should parse the one valid entry and skip the bad ones
            self.assertGreaterEqual(turns, 0)
        finally:
            os.unlink(str(path))

    def test_handles_string_content(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            {"role": "user", "content": "A" * 400},  # String, not list
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 100)  # 400 / 4
        finally:
            os.unlink(str(path))

    def test_handles_empty_lines(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
            f.write("\n\n")
            f.write(json.dumps(_make_user_turn("hello")) + "\n")
            f.write("\n")
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(turns, 1)
        finally:
            os.unlink(str(path))

    def test_claude_code_format_nested_usage(self):
        """Real Claude Code transcripts: usage is at entry['message']['usage']."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_claude_code_assistant_turn(input_tokens=100, cache_read_input_tokens=0),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 100)
            self.assertEqual(turns, 1)
        finally:
            os.unlink(str(path))

    def test_claude_code_format_includes_cache_tokens(self):
        """Total tokens = input + cache_read + cache_creation."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_claude_code_assistant_turn(
                input_tokens=1,
                cache_read_input_tokens=61000,
                cache_creation_input_tokens=3000,
            ),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 64001)
        finally:
            os.unlink(str(path))

    def test_claude_code_format_uses_max_across_turns(self):
        """Max total prompt tokens across all assistant turns."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_transcript(path, [
            _make_claude_code_assistant_turn(input_tokens=100, cache_read_input_tokens=5000),
            _make_claude_code_assistant_turn(input_tokens=50, cache_read_input_tokens=80000),
        ])
        try:
            tokens, turns = meter.estimate_tokens_from_transcript(path)
            self.assertEqual(tokens, 80050)  # second turn total
        finally:
            os.unlink(str(path))


# ---------------------------------------------------------------------------
# Context percentage calculation
# ---------------------------------------------------------------------------

class TestContextPercentage(unittest.TestCase):

    def test_percentage_normal(self):
        pct = meter.compute_context_percentage(50000, 200000)
        self.assertAlmostEqual(pct, 25.0)

    def test_percentage_full(self):
        pct = meter.compute_context_percentage(200000, 200000)
        self.assertAlmostEqual(pct, 100.0)

    def test_percentage_capped_at_100(self):
        pct = meter.compute_context_percentage(250000, 200000)
        self.assertAlmostEqual(pct, 100.0)

    def test_percentage_zero(self):
        pct = meter.compute_context_percentage(0, 200000)
        self.assertAlmostEqual(pct, 0.0)

    def test_percentage_rounds_to_one_decimal(self):
        pct = meter.compute_context_percentage(33333, 200000)
        self.assertEqual(pct, round(33333 / 200000 * 100, 1))

    def test_zero_window_returns_zero(self):
        pct = meter.compute_context_percentage(100, 0)
        self.assertEqual(pct, 0.0)


# ---------------------------------------------------------------------------
# Health zone classification
# ---------------------------------------------------------------------------

class TestHealthZone(unittest.TestCase):

    def test_green(self):
        self.assertEqual(meter.classify_health_zone(0.0), "green")
        self.assertEqual(meter.classify_health_zone(30.0), "green")
        self.assertEqual(meter.classify_health_zone(49.9), "green")

    def test_yellow(self):
        self.assertEqual(meter.classify_health_zone(50.0), "yellow")
        self.assertEqual(meter.classify_health_zone(60.0), "yellow")
        self.assertEqual(meter.classify_health_zone(69.9), "yellow")

    def test_red(self):
        self.assertEqual(meter.classify_health_zone(70.0), "red")
        self.assertEqual(meter.classify_health_zone(80.0), "red")
        self.assertEqual(meter.classify_health_zone(84.9), "red")

    def test_critical(self):
        self.assertEqual(meter.classify_health_zone(85.0), "critical")
        self.assertEqual(meter.classify_health_zone(95.0), "critical")
        self.assertEqual(meter.classify_health_zone(100.0), "critical")

    def test_custom_thresholds(self):
        thresholds = {"yellow": 40, "red": 60, "critical": 80}
        self.assertEqual(meter.classify_health_zone(35.0, thresholds), "green")
        self.assertEqual(meter.classify_health_zone(45.0, thresholds), "yellow")
        self.assertEqual(meter.classify_health_zone(65.0, thresholds), "red")
        self.assertEqual(meter.classify_health_zone(85.0, thresholds), "critical")


# ---------------------------------------------------------------------------
# Adaptive thresholds for large context windows
# ---------------------------------------------------------------------------

class TestAdaptiveThresholds(unittest.TestCase):
    """
    For 1M context windows, quality degrades at 250-500k absolute tokens
    (community-validated across nuclear scan posts). Percentage thresholds
    must adapt: yellow at 25%, red at 40%, critical at 60% for 1M windows.
    For 200k windows, standard thresholds (50/70/85) should be unchanged.
    """

    def test_200k_window_unchanged(self):
        """Standard 200k window: thresholds remain at 50/70/85%."""
        t = meter.adaptive_thresholds(200_000)
        self.assertEqual(t["yellow"], 50)
        self.assertEqual(t["red"], 70)
        self.assertEqual(t["critical"], 85)

    def test_1m_window_tightens_thresholds(self):
        """1M window: thresholds drop to reflect quality ceiling at 250-500k tokens."""
        t = meter.adaptive_thresholds(1_000_000)
        # Yellow should start at 250k/1M = 25%
        self.assertEqual(t["yellow"], 25)
        # Red should start at 400k/1M = 40%
        self.assertEqual(t["red"], 40)
        # Critical at 600k/1M = 60%
        self.assertEqual(t["critical"], 60)

    def test_500k_window_intermediate(self):
        """500k window: thresholds between standard and 1M."""
        t = meter.adaptive_thresholds(500_000)
        # Yellow = min(50, 250k/500k*100=50) = 50
        self.assertEqual(t["yellow"], 50)
        # Red = min(70, 400k/500k*100=80) = 70
        self.assertEqual(t["red"], 70)
        # Critical = min(85, 600k/500k*100=120) = 85
        self.assertEqual(t["critical"], 85)

    def test_small_window_uses_standard(self):
        """Windows smaller than quality ceilings use standard percentages."""
        t = meter.adaptive_thresholds(100_000)
        self.assertEqual(t["yellow"], 50)
        self.assertEqual(t["red"], 70)
        self.assertEqual(t["critical"], 85)

    def test_800k_window(self):
        """800k window: absolute ceilings start to bite."""
        t = meter.adaptive_thresholds(800_000)
        # Yellow = min(50, 250/800*100=31.25) = 31
        self.assertEqual(t["yellow"], 31)
        # Red = min(70, 400/800*100=50) = 50
        self.assertEqual(t["red"], 50)
        # Critical = min(85, 600/800*100=75) = 75
        self.assertEqual(t["critical"], 75)

    def test_thresholds_always_have_required_keys(self):
        """Result always has yellow, red, critical keys."""
        for window in [100_000, 200_000, 500_000, 800_000, 1_000_000]:
            t = meter.adaptive_thresholds(window)
            self.assertIn("yellow", t)
            self.assertIn("red", t)
            self.assertIn("critical", t)

    def test_thresholds_maintain_ordering(self):
        """yellow < red < critical for any valid window."""
        for window in [100_000, 200_000, 500_000, 800_000, 1_000_000, 2_000_000]:
            t = meter.adaptive_thresholds(window)
            self.assertLess(t["yellow"], t["red"],
                            f"yellow >= red at {window}")
            self.assertLess(t["red"], t["critical"],
                            f"red >= critical at {window}")

    def test_zero_window_returns_standard(self):
        """Zero or negative window returns standard thresholds."""
        t = meter.adaptive_thresholds(0)
        self.assertEqual(t["yellow"], 50)
        self.assertEqual(t["red"], 70)
        self.assertEqual(t["critical"], 85)

    def test_adaptive_disabled_returns_standard(self):
        """When adaptive is explicitly disabled, return standard thresholds."""
        t = meter.adaptive_thresholds(1_000_000, adaptive=False)
        self.assertEqual(t["yellow"], 50)
        self.assertEqual(t["red"], 70)
        self.assertEqual(t["critical"], 85)


# ---------------------------------------------------------------------------
# State file includes thresholds
# ---------------------------------------------------------------------------

class TestStateFileThresholds(unittest.TestCase):
    """State file should record which thresholds are active."""

    def test_state_includes_thresholds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.write_state_file(
                state_path, 30.0, "green", 60000, 5, "s1",
                window=200000,
                thresholds={"yellow": 50, "red": 70, "critical": 85},
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertIn("thresholds", data)
            self.assertEqual(data["thresholds"]["yellow"], 50)

    def test_state_thresholds_for_1m_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.write_state_file(
                state_path, 25.0, "yellow", 250000, 10, "s1",
                window=1_000_000,
                thresholds={"yellow": 25, "red": 40, "critical": 60},
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["thresholds"]["yellow"], 25)
            self.assertEqual(data["window"], 1_000_000)


# ---------------------------------------------------------------------------
# Integration: meter with adaptive thresholds
# ---------------------------------------------------------------------------

class TestMeterAdaptiveIntegration(unittest.TestCase):

    def test_1m_window_250k_tokens_is_yellow(self):
        """250k tokens in a 1M window should be yellow (not green)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("x", input_tokens=250000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            result = meter.run_meter("s1", transcript_path, state_path, window=1_000_000)
            self.assertEqual(result["zone"], "yellow")
            self.assertAlmostEqual(result["pct"], 25.0)

    def test_1m_window_400k_tokens_is_red(self):
        """400k tokens in a 1M window should be red."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("x", input_tokens=400000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            result = meter.run_meter("s1", transcript_path, state_path, window=1_000_000)
            self.assertEqual(result["zone"], "red")

    def test_1m_window_600k_tokens_is_critical(self):
        """600k tokens in a 1M window should be critical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("x", input_tokens=600000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            result = meter.run_meter("s1", transcript_path, state_path, window=1_000_000)
            self.assertEqual(result["zone"], "critical")

    def test_200k_window_80k_still_green(self):
        """80k tokens in 200k window should still be green (40%)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("x", input_tokens=80000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            result = meter.run_meter("s1", transcript_path, state_path, window=200_000)
            self.assertEqual(result["zone"], "green")

    def test_state_file_records_thresholds(self):
        """State file includes thresholds so downstream consumers can read them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("x", input_tokens=100000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            meter.run_meter("s1", transcript_path, state_path, window=1_000_000)
            with open(state_path) as f:
                data = json.load(f)
            self.assertIn("thresholds", data)
            self.assertEqual(data["thresholds"]["yellow"], 25)


# ---------------------------------------------------------------------------
# State file writing
# ---------------------------------------------------------------------------

class TestStateFileWrite(unittest.TestCase):

    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx-health.json"
            meter.write_state_file(
                path=state_path,
                pct=45.2,
                zone="yellow",
                tokens=90400,
                turns=12,
                session_id="test-session-123",
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["pct"], 45.2)
            self.assertEqual(data["zone"], "yellow")
            self.assertEqual(data["tokens"], 90400)
            self.assertEqual(data["turns"], 12)
            self.assertEqual(data["session_id"], "test-session-123")
            self.assertIn("updated_at", data)

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nested" / "dirs" / "ctx-health.json"
            meter.write_state_file(state_path, 10.0, "green", 5000, 3, "s1")
            self.assertTrue(state_path.exists())

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx-health.json"
            meter.write_state_file(state_path, 20.0, "green", 10000, 5, "s1")
            meter.write_state_file(state_path, 75.0, "red", 150000, 10, "s2")
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["pct"], 75.0)
            self.assertEqual(data["zone"], "red")

    def test_state_has_window_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.write_state_file(state_path, 50.0, "yellow", 100000, 8, "s1", window=200000)
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["window"], 200000)


# ---------------------------------------------------------------------------
# Transcript path derivation
# ---------------------------------------------------------------------------

class TestTranscriptPathDerivation(unittest.TestCase):

    def test_derives_path_from_session_id(self):
        """transcript is at ~/.claude/projects/<project_hash>/<session_id>.jsonl"""
        path = meter.derive_transcript_path(
            session_id="abc-123",
            project_dir="/Users/test/Projects/MyProject",
        )
        self.assertTrue(str(path).endswith("abc-123.jsonl"))
        self.assertIn("-Users-test-Projects-MyProject", str(path))

    def test_handles_trailing_slash(self):
        path = meter.derive_transcript_path(
            session_id="xyz",
            project_dir="/Users/test/Projects/MyProject/",
        )
        self.assertIn("-Users-test-Projects-MyProject", str(path))

    def test_uses_home_directory(self):
        path = meter.derive_transcript_path(
            session_id="sid",
            project_dir="/foo/bar",
        )
        self.assertTrue(str(path).startswith(str(Path.home())))


# ---------------------------------------------------------------------------
# Hook input parsing
# ---------------------------------------------------------------------------

class TestHookInputParsing(unittest.TestCase):

    def test_parses_session_id(self):
        payload = {
            "hook_event_id": "evt-1",
            "session_id": "session-abc-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/foo/bar.py"},
            "tool_response": "content here",
        }
        session_id, tool_name = meter.parse_hook_input(payload)
        self.assertEqual(session_id, "session-abc-123")
        self.assertEqual(tool_name, "Read")

    def test_handles_missing_session_id(self):
        payload = {"tool_name": "Bash"}
        session_id, tool_name = meter.parse_hook_input(payload)
        self.assertEqual(session_id, "")
        self.assertEqual(tool_name, "Bash")


# ---------------------------------------------------------------------------
# Integration: full meter run
# ---------------------------------------------------------------------------

class TestMeterIntegration(unittest.TestCase):

    def test_full_run_writes_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Create a fake transcript
            session_id = "test-session-456"
            transcript_path = tmp / "transcript.jsonl"
            _write_transcript(transcript_path, [
                _make_user_turn("Hello, how are you?"),
                _make_assistant_turn("I'm good, thanks!", input_tokens=50000, output_tokens=20),
                _make_user_turn("Great, let's build something."),
                _make_assistant_turn("Sure!", input_tokens=80000, output_tokens=40),
            ])

            state_path = tmp / "ctx-health.json"

            meter.run_meter(
                session_id=session_id,
                transcript_path=transcript_path,
                state_path=state_path,
                window=200000,
            )

            with open(state_path) as f:
                data = json.load(f)

            self.assertEqual(data["tokens"], 80000)
            self.assertAlmostEqual(data["pct"], 40.0)
            self.assertEqual(data["zone"], "green")

    def test_full_run_yellow_zone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("y", input_tokens=120000, output_tokens=100),
            ])
            state_path = tmp / "ctx.json"
            meter.run_meter("s1", transcript_path, state_path, window=200000)
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["zone"], "yellow")

    def test_full_run_critical_zone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transcript_path = tmp / "t.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("z", input_tokens=180000, output_tokens=200),
            ])
            state_path = tmp / "ctx.json"
            meter.run_meter("s1", transcript_path, state_path, window=200000)
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["zone"], "critical")

    def test_missing_transcript_writes_unknown_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.run_meter(
                session_id="s1",
                transcript_path=Path("/tmp/does_not_exist_ctx123.jsonl"),
                state_path=state_path,
                window=200000,
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["zone"], "unknown")
            self.assertEqual(data["tokens"], 0)


class TestAutocompactAwareness(unittest.TestCase):
    """Test CLAUDE_AUTOCOMPACT_PCT_OVERRIDE awareness in context meter.

    When users set CLAUDE_AUTOCOMPACT_PCT_OVERRIDE (e.g., 30 for 30%),
    it changes when Claude Code fires auto-compaction. The meter should
    include this in state output so downstream consumers can show
    proximity to compaction threshold.
    """

    def test_get_autocompact_threshold_from_env(self):
        """Should read CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from environment."""
        with patch.dict(os.environ, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "30"}):
            self.assertEqual(meter.get_autocompact_pct(), 30)

    def test_get_autocompact_threshold_default(self):
        """Default autocompact threshold is None (not set = use CC default)."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(meter.get_autocompact_pct())

    def test_get_autocompact_threshold_invalid(self):
        """Invalid values should return None."""
        with patch.dict(os.environ, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "abc"}):
            self.assertIsNone(meter.get_autocompact_pct())

    def test_get_autocompact_threshold_zero(self):
        """Zero is valid — means autocompact at 0%."""
        with patch.dict(os.environ, {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "0"}):
            self.assertEqual(meter.get_autocompact_pct(), 0)

    def test_state_file_includes_autocompact(self):
        """State file should include autocompact_pct when set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.write_state_file(
                path=state_path,
                pct=45.0,
                zone="green",
                tokens=90000,
                turns=20,
                session_id="s1",
                window=200000,
                autocompact_pct=30,
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["autocompact_pct"], 30)

    def test_state_file_autocompact_null_when_unset(self):
        """State file should have null autocompact_pct when not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ctx.json"
            meter.write_state_file(
                path=state_path,
                pct=45.0,
                zone="green",
                tokens=90000,
                turns=20,
                session_id="s1",
                window=200000,
                autocompact_pct=None,
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertIsNone(data["autocompact_pct"])

    def test_approaching_autocompact_threshold(self):
        """compute_autocompact_proximity returns how close to compaction."""
        # 45% used, autocompact at 50% → 5% away
        prox = meter.compute_autocompact_proximity(pct=45.0, autocompact_pct=50)
        self.assertEqual(prox, 5.0)

    def test_past_autocompact_threshold(self):
        """If already past autocompact, proximity is 0 (compaction imminent/active)."""
        prox = meter.compute_autocompact_proximity(pct=55.0, autocompact_pct=50)
        self.assertEqual(prox, 0.0)

    def test_autocompact_proximity_none_when_unset(self):
        """No proximity when autocompact not configured."""
        prox = meter.compute_autocompact_proximity(pct=45.0, autocompact_pct=None)
        self.assertIsNone(prox)

    def test_run_meter_includes_autocompact(self):
        """run_meter should include autocompact info in state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "session.jsonl"
            _write_transcript(transcript_path, [
                _make_assistant_turn("test", input_tokens=90000),
            ])
            state_path = Path(tmpdir) / "ctx.json"
            meter.run_meter(
                session_id="s1",
                transcript_path=transcript_path,
                state_path=state_path,
                window=200000,
                autocompact_pct=30,
            )
            with open(state_path) as f:
                data = json.load(f)
            self.assertEqual(data["autocompact_pct"], 30)
            self.assertIn("autocompact_proximity", data)


if __name__ == "__main__":
    unittest.main()
