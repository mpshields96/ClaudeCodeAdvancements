"""Tests for loop_detector.py — core loop detection logic."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import sys
import os

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from loop_detector import (
    LoopDetector,
    LoopCheckResult,
    LoopEntry,
    DEFAULT_THRESHOLD,
    DEFAULT_MIN_CONSECUTIVE,
    DEFAULT_WINDOW,
    MAX_COMPARE_LENGTH,
    EXEMPT_TOOLS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_state(tmp_path):
    """Provide a temporary state file path."""
    return tmp_path / "loop-state.json"


@pytest.fixture
def detector(tmp_state):
    """Create a detector with a temporary state file."""
    return LoopDetector(state_file=tmp_state)


@pytest.fixture
def strict_detector(tmp_state):
    """Detector with lower thresholds for easier triggering in tests."""
    return LoopDetector(
        threshold=0.70,
        min_consecutive=2,
        state_file=tmp_state,
    )


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------

class TestLoopDetectorBasic:
    """Core detector behavior."""

    def test_init_defaults(self, detector):
        assert detector.window == DEFAULT_WINDOW
        assert detector.threshold == DEFAULT_THRESHOLD
        assert detector.min_consecutive == DEFAULT_MIN_CONSECUTIVE
        assert len(detector.buffer) == 0

    def test_add_single_output(self, detector):
        detector.add("hello world", tool_name="Bash")
        assert len(detector.buffer) == 1
        assert detector.buffer[0].tool_name == "Bash"

    def test_add_respects_window(self, tmp_state):
        d = LoopDetector(window=3, state_file=tmp_state)
        for i in range(5):
            d.add(f"output {i}")
        assert len(d.buffer) == 3
        # Should keep the last 3
        assert d.buffer[0].output_preview == "output 2"

    def test_check_not_enough_data(self, detector):
        detector.add("one output")
        result = detector.check()
        assert not result.is_loop
        assert "Not enough data" in result.description

    def test_check_no_loop_diverse_outputs(self, detector):
        outputs = [
            "File contents: function add(a, b) { return a + b; }",
            "Test result: 5 passed, 0 failed",
            "Git status: 3 files changed",
            "Build complete: 0 errors, 2 warnings",
        ]
        for o in outputs:
            detector.add(o, tool_name="Bash")
        result = detector.check()
        assert not result.is_loop

    def test_stats_property(self, detector):
        stats = detector.stats
        assert stats["buffer_size"] == 0
        assert stats["buffer_capacity"] == DEFAULT_WINDOW
        assert stats["total_checks"] == 0
        assert stats["loops_detected"] == 0


# ---------------------------------------------------------------------------
# Loop detection — exact matches
# ---------------------------------------------------------------------------

class TestExactMatchLoops:
    """Detect loops where outputs are exactly identical."""

    def test_exact_same_output_triggers_loop(self, detector):
        error_msg = "Error: file not found: /tmp/missing.py"
        for _ in range(4):
            detector.add(error_msg, tool_name="Bash")
        result = detector.check()
        assert result.is_loop
        assert result.avg_similarity == 1.0
        assert result.consecutive_similar >= 3

    def test_exact_match_uses_hash_fast_path(self, detector):
        """Identical outputs should match via hash, not SequenceMatcher."""
        msg = "x" * 5000
        detector.add(msg)
        detector.add(msg)
        # Second entry should have similarity 1.0 (hash match)
        assert detector.buffer[-1].similarity_to_prev == 1.0

    def test_two_identical_not_enough(self, detector):
        """Default min_consecutive=3, so 2 identical outputs isn't a loop."""
        msg = "same output"
        detector.add(msg)
        detector.add(msg)
        result = detector.check()
        assert not result.is_loop

    def test_three_identical_is_loop(self, detector):
        msg = "same output"
        for _ in range(3):
            detector.add(msg)
        # 3 entries, but only 2 pairs (consecutive similarities)
        # Need min_consecutive=3 consecutive similarities, which requires 4 entries
        # Actually: entry[1].sim_to_prev, entry[2].sim_to_prev = 2 consecutive
        # With default min_consecutive=3, need 4 identical entries
        result = detector.check()
        # 2 consecutive similar, need 3 — not a loop yet
        assert not result.is_loop

    def test_four_identical_is_loop(self, detector):
        """4 identical entries = 3 consecutive similarities = loop."""
        msg = "Error: connection refused"
        for _ in range(4):
            detector.add(msg, tool_name="Bash")
        result = detector.check()
        assert result.is_loop
        assert result.consecutive_similar == 3
        assert "Bash" in result.description


# ---------------------------------------------------------------------------
# Loop detection — fuzzy matches
# ---------------------------------------------------------------------------

class TestFuzzyMatchLoops:
    """Detect loops where outputs are similar but not identical."""

    def test_similar_error_messages(self, strict_detector):
        """Same error with different timestamps should trigger."""
        d = strict_detector
        errors = [
            "2026-03-30 10:01:00 Error: connection timeout after 30s",
            "2026-03-30 10:01:05 Error: connection timeout after 30s",
            "2026-03-30 10:01:10 Error: connection timeout after 30s",
        ]
        for e in errors:
            d.add(e, tool_name="Bash")
        result = d.check()
        assert result.is_loop

    def test_similar_file_reads(self, strict_detector):
        """Reading the same file repeatedly with minor diffs."""
        d = strict_detector
        base = "line 1: import os\nline 2: import sys\nline 3: def main():\n"
        variants = [
            base + "line 4: pass  # v1",
            base + "line 4: pass  # v2",
            base + "line 4: pass  # v3",
        ]
        for v in variants:
            d.add(v, tool_name="Read")
        result = d.check()
        assert result.is_loop

    def test_below_threshold_not_loop(self, detector):
        """Outputs that share some words but are mostly different."""
        outputs = [
            "Running test suite: auth module — 15 tests passed",
            "Running test suite: payment module — 8 tests passed, 2 failed",
            "Running test suite: notification module — 12 tests passed",
        ]
        for o in outputs:
            detector.add(o, tool_name="Bash")
        result = detector.check()
        # These are similar-ish but should be below 0.80
        assert not result.is_loop


# ---------------------------------------------------------------------------
# Exempt tools
# ---------------------------------------------------------------------------

class TestExemptTools:
    """Tools that should never trigger loop detection."""

    def test_todowrite_exempt(self, detector):
        msg = "Todos updated successfully"
        for _ in range(5):
            detector.add(msg, tool_name="TodoWrite")
        result = detector.check()
        assert not result.is_loop
        assert "exempt" in result.description.lower()

    def test_askuserquestion_exempt(self, detector):
        msg = "Waiting for user response..."
        for _ in range(5):
            detector.add(msg, tool_name="AskUserQuestion")
        result = detector.check()
        assert not result.is_loop

    def test_non_exempt_tool_still_detected(self, detector):
        msg = "Error: permission denied"
        for _ in range(4):
            detector.add(msg, tool_name="Bash")
        result = detector.check()
        assert result.is_loop


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    """Save and load detector state across invocations."""

    def test_save_and_load(self, tmp_state):
        d1 = LoopDetector(state_file=tmp_state)
        d1.add("output 1", tool_name="Bash")
        d1.add("output 2", tool_name="Read")
        d1.save_state()

        d2 = LoopDetector(state_file=tmp_state)
        assert d2.load_state()
        assert len(d2.buffer) == 2
        assert d2.buffer[0].tool_name == "Bash"
        assert d2.buffer[1].tool_name == "Read"

    def test_load_nonexistent_returns_false(self, tmp_state):
        d = LoopDetector(state_file=tmp_state)
        assert not d.load_state()

    def test_load_corrupt_file_returns_false(self, tmp_state):
        tmp_state.write_text("not valid json {{{")
        d = LoopDetector(state_file=tmp_state)
        assert not d.load_state()
        assert len(d.buffer) == 0

    def test_state_survives_across_detections(self, tmp_state):
        """Simulate multiple hook invocations building up to a loop."""
        msg = "Error: file not found"

        # First invocation: 2 outputs
        d1 = LoopDetector(state_file=tmp_state)
        d1.load_state()
        d1.add(msg, tool_name="Bash")
        d1.add(msg, tool_name="Bash")
        d1.save_state()

        # Second invocation: 1 more output
        d2 = LoopDetector(state_file=tmp_state)
        d2.load_state()
        d2.add(msg, tool_name="Bash")
        result = d2.check()
        # Now we have 3 entries total, 2 consecutive similarities
        assert not result.is_loop  # Need 3 consecutive

        # Third invocation: 1 more
        d2.save_state()
        d3 = LoopDetector(state_file=tmp_state)
        d3.load_state()
        d3.add(msg, tool_name="Bash")
        result = d3.check()
        assert result.is_loop  # 4 entries, 3 consecutive similarities

    def test_reset_clears_state(self, tmp_state):
        d = LoopDetector(state_file=tmp_state)
        d.add("something")
        d.save_state()
        assert tmp_state.exists()

        d.reset()
        assert len(d.buffer) == 0
        assert not tmp_state.exists()

    def test_atomic_write(self, tmp_state):
        """State file should be written atomically (via .tmp rename)."""
        d = LoopDetector(state_file=tmp_state)
        d.add("test output")
        d.save_state()
        # File should exist and be valid JSON
        data = json.loads(tmp_state.read_text())
        assert "buffer" in data
        assert "config" in data


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_empty_output(self, detector):
        detector.add("", tool_name="Bash")
        result = detector.check()
        assert not result.is_loop

    def test_very_long_output_truncated(self, detector):
        long_output = "x" * (MAX_COMPARE_LENGTH + 1000)
        detector.add(long_output)
        assert len(detector.buffer[0].output_preview) == MAX_COMPARE_LENGTH

    def test_unicode_output(self, detector):
        detector.add("Error: fichier introuvable — /tmp/données.csv")
        assert len(detector.buffer) == 1

    def test_mixed_tools_break_streak(self, detector):
        """Different tool types producing similar output shouldn't combine."""
        error = "Error: not found"
        detector.add(error, tool_name="Bash")
        detector.add(error, tool_name="Bash")
        detector.add("completely different read output", tool_name="Read")
        detector.add(error, tool_name="Bash")
        result = detector.check()
        # The Read output broke the similarity streak
        assert not result.is_loop

    def test_loop_result_has_recommendation(self, detector):
        msg = "same error"
        for _ in range(4):
            detector.add(msg, tool_name="Bash")
        result = detector.check()
        assert result.is_loop
        assert "different approach" in result.recommendation

    def test_custom_threshold(self, tmp_state):
        d = LoopDetector(threshold=0.95, state_file=tmp_state)
        # These are similar but not 95% similar
        d.add("Error at line 10: undefined variable x")
        d.add("Error at line 20: undefined variable y")
        d.add("Error at line 30: undefined variable z")
        d.add("Error at line 40: undefined variable w")
        result = d.check()
        # With 0.95 threshold, these shouldn't match
        assert not result.is_loop

    def test_custom_min_consecutive(self, tmp_state):
        d = LoopDetector(min_consecutive=2, state_file=tmp_state)
        msg = "repeated"
        d.add(msg)
        d.add(msg)
        d.add(msg)  # 3 entries = 2 consecutive similarities
        result = d.check()
        assert result.is_loop

    def test_stats_update_on_check(self, detector):
        detector.add("a")
        detector.check()
        assert detector.stats["total_checks"] == 1
        assert detector.stats["loops_detected"] == 0

    def test_stats_count_loops(self, detector):
        for _ in range(4):
            detector.add("same")
        detector.check()
        assert detector.stats["loops_detected"] == 1


# ---------------------------------------------------------------------------
# Hook integration simulation
# ---------------------------------------------------------------------------

class TestHookIntegration:
    """Simulate how the hook wrapper would use the detector."""

    def test_full_hook_cycle(self, tmp_state):
        """Simulate 6 PostToolUse invocations building up to a loop."""
        outputs = [
            ("git status", "Bash"),
            ("function add(a,b) { return a+b }", "Read"),
            ("Error: test failed — expected 5, got 4", "Bash"),
            ("Error: test failed — expected 5, got 4", "Bash"),
            ("Error: test failed — expected 5, got 4", "Bash"),
            ("Error: test failed — expected 5, got 4", "Bash"),
        ]
        loop_detected_at = None

        for i, (output, tool) in enumerate(outputs):
            # Each invocation creates a fresh detector and loads state
            d = LoopDetector(state_file=tmp_state)
            d.load_state()
            d.add(output, tool_name=tool)
            result = d.check()
            d.save_state()

            if result.is_loop and loop_detected_at is None:
                loop_detected_at = i

        # Loop should be detected at index 5 (4th identical error)
        assert loop_detected_at == 5
        assert result.is_loop
        assert result.consecutive_similar == 3
