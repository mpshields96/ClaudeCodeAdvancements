"""
Tests for the 4 context-monitor advisory signals (Chat 35, BUILD #12 adjacent).

Signal 1: Cache ratio bust detection (meter.py)
Signal 2: --resume flag detection (session_start.py)
Signal 3: CLAUDE.md size warning (session_start.py)
Signal 4: CLAUDE_CODE_DISABLE_1M_CONTEXT tip in red/critical (alert.py)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import meter
import alert
import session_start


# ---------------------------------------------------------------------------
# Signal 1: Cache ratio bust detection
# ---------------------------------------------------------------------------

def _make_usage_entry(input_tok: int, cache_read: int, cache_create: int) -> dict:
    return {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": input_tok,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            }
        },
    }


def _write_transcript(path: Path, entries: list[dict]) -> None:
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestCacheRatioDetection(unittest.TestCase):

    def test_no_bust_first_turn(self):
        """First usage-bearing turn never triggers bust even with low cache_read."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transcript.jsonl"
            _write_transcript(path, [
                _make_usage_entry(1000, 0, 5000),   # first turn: no cache_read yet
            ])
            bust, ratio = meter.detect_cache_bust(0, 5000, turns_with_usage=1)
            self.assertFalse(bust)

    def test_bust_detected_second_turn_low_ratio(self):
        """Cache bust fires when ratio < 0.5 on turns_with_usage > 1."""
        # cache_read=100, cache_create=9900 → ratio=0.01
        bust, ratio = meter.detect_cache_bust(100, 9900, turns_with_usage=2)
        self.assertTrue(bust)
        self.assertAlmostEqual(ratio, 0.01, places=2)

    def test_no_bust_healthy_ratio(self):
        """Ratio >= 0.5 on non-first turn: no bust."""
        bust, ratio = meter.detect_cache_bust(8000, 2000, turns_with_usage=3)
        self.assertFalse(bust)
        self.assertAlmostEqual(ratio, 0.8, places=2)

    def test_no_bust_zero_cache_tokens(self):
        """No cache tokens at all → ratio is None, no bust."""
        bust, ratio = meter.detect_cache_bust(0, 0, turns_with_usage=5)
        self.assertFalse(bust)
        self.assertIsNone(ratio)

    def test_compute_cache_ratio_boundary(self):
        """Exactly 50% cache read → ratio=0.5, no bust (threshold is <0.5)."""
        bust, ratio = meter.detect_cache_bust(500, 500, turns_with_usage=2)
        self.assertFalse(bust)  # 0.5 is not < 0.5
        self.assertAlmostEqual(ratio, 0.5, places=2)

    def test_newly_busted_flag_in_run_meter(self):
        """run_meter returns newly_busted=True when bust transitions False→True."""
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            state_path = Path(tmp) / "health.json"
            # Turn 1: high cache (healthy)
            # Turn 2: low cache (bust)
            _write_transcript(transcript, [
                _make_usage_entry(1000, 8000, 500),   # turn 1: ratio=0.94
                _make_usage_entry(1000, 100, 9900),   # turn 2: ratio=0.01
            ])
            result = meter.run_meter(
                session_id="test-session",
                transcript_path=transcript,
                state_path=state_path,
                window=200_000,
            )
            self.assertTrue(result["cache_bust_detected"])
            self.assertTrue(result["newly_busted"])

    def test_not_newly_busted_when_already_in_state(self):
        """newly_busted=False when state file already has cache_bust_detected=True."""
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            state_path = Path(tmp) / "health.json"
            # Write previous state with bust already True
            state_path.write_text(json.dumps({"cache_bust_detected": True}))
            _write_transcript(transcript, [
                _make_usage_entry(1000, 8000, 500),
                _make_usage_entry(1000, 100, 9900),
            ])
            result = meter.run_meter(
                session_id="test-session",
                transcript_path=transcript,
                state_path=state_path,
                window=200_000,
            )
            self.assertTrue(result["cache_bust_detected"])
            self.assertFalse(result["newly_busted"])  # already was busted

    def test_bust_clears_when_ratio_recovers(self):
        """cache_bust_detected=False when ratio recovers above threshold."""
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "t.jsonl"
            state_path = Path(tmp) / "health.json"
            _write_transcript(transcript, [
                _make_usage_entry(1000, 8000, 500),   # healthy
                _make_usage_entry(1000, 9000, 100),   # also healthy: ratio=0.99
            ])
            result = meter.run_meter(
                session_id="s",
                transcript_path=transcript,
                state_path=state_path,
                window=200_000,
            )
            self.assertFalse(result["cache_bust_detected"])


# ---------------------------------------------------------------------------
# Signal 2: --resume detection
# ---------------------------------------------------------------------------

class TestResumeDetection(unittest.TestCase):

    def test_no_advisory_when_env_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_RESUME"}
        with patch.dict(os.environ, env, clear=True):
            msg = session_start._check_resume_flag()
        self.assertIsNone(msg)

    def test_advisory_when_env_set(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_RESUME": "1"}):
            msg = session_start._check_resume_flag()
        self.assertIsNotNone(msg)
        self.assertIn("--resume", msg)
        self.assertIn("Caching is disabled", msg)

    def test_advisory_any_truthy_value(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_RESUME": "true"}):
            msg = session_start._check_resume_flag()
        self.assertIsNotNone(msg)


# ---------------------------------------------------------------------------
# Signal 3: CLAUDE.md size warning
# ---------------------------------------------------------------------------

class TestClaudeMdSizeWarning(unittest.TestCase):

    def test_no_warning_when_files_small(self):
        with tempfile.TemporaryDirectory() as tmp_home, \
             tempfile.TemporaryDirectory() as tmp_cwd:
            # Create small local CLAUDE.md (100 bytes)
            (Path(tmp_cwd) / "CLAUDE.md").write_text("x" * 100)
            # Global ~/.claude/CLAUDE.md is absent in tmp_home
            with patch.object(Path, "home", return_value=Path(tmp_home)):
                msg = session_start._check_claude_md_size(tmp_cwd)
        self.assertIsNone(msg)

    def test_warning_when_project_claude_md_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_md = Path(tmp) / "CLAUDE.md"
            claude_md.write_text("x" * 4096)  # 4KB — exceeds 3KB threshold
            msg = session_start._check_claude_md_size(tmp)
        self.assertIsNotNone(msg)
        self.assertIn("CLAUDE.md", msg)
        self.assertIn("re-sends on every interaction", msg)

    def test_no_warning_exactly_at_threshold(self):
        """3072 bytes exactly: no warning (threshold is >3072)."""
        with tempfile.TemporaryDirectory() as tmp:
            claude_md = Path(tmp) / "CLAUDE.md"
            claude_md.write_text("x" * 3072)
            msg = session_start._check_claude_md_size(tmp)
        self.assertIsNone(msg)

    def test_warning_just_above_threshold(self):
        """3073 bytes: warning fires."""
        with tempfile.TemporaryDirectory() as tmp:
            claude_md = Path(tmp) / "CLAUDE.md"
            claude_md.write_text("x" * 3073)
            msg = session_start._check_claude_md_size(tmp)
        self.assertIsNotNone(msg)

    def test_no_warning_when_no_claude_md_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg = session_start._check_claude_md_size(tmp)
        self.assertIsNone(msg)


# ---------------------------------------------------------------------------
# Signal 4: CLAUDE_CODE_DISABLE_1M_CONTEXT tip in red/critical
# ---------------------------------------------------------------------------

class TestDisable1MContextTip(unittest.TestCase):

    def test_tip_present_in_red_message(self):
        msg = alert.build_message("red", 75.0, "Agent", blocking=False)
        self.assertIn("CLAUDE_CODE_DISABLE_1M_CONTEXT", msg)

    def test_tip_present_in_critical_message(self):
        msg = alert.build_message("critical", 90.0, "Agent", blocking=False)
        self.assertIn("CLAUDE_CODE_DISABLE_1M_CONTEXT", msg)

    def test_tip_absent_in_yellow_message(self):
        # Yellow with autocompact proximity to trigger a message
        msg = alert.build_message("yellow", 55.0, "Agent", blocking=False,
                                  autocompact_proximity=5.0)
        self.assertNotIn("CLAUDE_CODE_DISABLE_1M_CONTEXT", msg)

    def test_tip_not_in_green_zone(self):
        # Green zone returns empty string from build_message
        msg = alert.build_message("green", 30.0, "Agent", blocking=False)
        self.assertEqual(msg, "")

    def test_tip_content_is_actionable(self):
        msg = alert.build_message("critical", 88.0, "Write", blocking=False)
        self.assertIn("200k context window", msg)
        self.assertIn("cache expiry", msg)


if __name__ == "__main__":
    unittest.main()
