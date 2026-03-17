"""
Tests for CTX-5: compaction anchor hook.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import compact_anchor


def _write_state(path: Path, zone: str, pct: float, turns: int = 100, tokens: int = 50000) -> None:
    state = {"zone": zone, "pct": pct, "tokens": tokens, "turns": turns, "window": 200000}
    with open(path, "w") as f:
        json.dump(state, f)


class TestLoadState(unittest.TestCase):

    def test_loads_valid_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"zone": "red", "pct": 72.0, "turns": 150}, f)
            path = Path(f.name)
        try:
            state = compact_anchor.load_state(path)
            self.assertEqual(state["zone"], "red")
            self.assertEqual(state["turns"], 150)
        finally:
            os.unlink(str(path))

    def test_returns_empty_for_missing_file(self):
        state = compact_anchor.load_state(Path("/tmp/no_such_anchor_state.json"))
        self.assertEqual(state, {})


class TestLoadAnchorTurnCount(unittest.TestCase):

    def test_returns_zero_for_missing_file(self):
        count = compact_anchor.load_anchor_turn_count(Path("/tmp/no_such_anchor_ctx5.md"))
        self.assertEqual(count, 0)

    def test_parses_turn_count_from_anchor(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("<!-- COMPACT ANCHOR -->\n")
            f.write("<!-- turn_count: 42 -->\n")
            f.write("other content\n")
            path = Path(f.name)
        try:
            count = compact_anchor.load_anchor_turn_count(path)
            self.assertEqual(count, 42)
        finally:
            os.unlink(str(path))

    def test_returns_zero_for_malformed_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("no turn count here\n")
            path = Path(f.name)
        try:
            count = compact_anchor.load_anchor_turn_count(path)
            self.assertEqual(count, 0)
        finally:
            os.unlink(str(path))


class TestShouldWrite(unittest.TestCase):

    def test_writes_at_turn_zero(self):
        self.assertTrue(compact_anchor.should_write(0, write_every=10))

    def test_writes_at_multiples_of_write_every(self):
        self.assertTrue(compact_anchor.should_write(10, write_every=10))
        self.assertTrue(compact_anchor.should_write(20, write_every=10))
        self.assertTrue(compact_anchor.should_write(100, write_every=10))

    def test_does_not_write_between_multiples(self):
        self.assertFalse(compact_anchor.should_write(5, write_every=10))
        self.assertFalse(compact_anchor.should_write(11, write_every=10))
        self.assertFalse(compact_anchor.should_write(99, write_every=10))

    def test_disabled_when_write_every_is_zero(self):
        self.assertFalse(compact_anchor.should_write(0, write_every=0))
        self.assertFalse(compact_anchor.should_write(10, write_every=0))

    def test_works_with_different_intervals(self):
        self.assertTrue(compact_anchor.should_write(5, write_every=5))
        self.assertFalse(compact_anchor.should_write(7, write_every=5))
        self.assertTrue(compact_anchor.should_write(50, write_every=25))


class TestBuildAnchorContent(unittest.TestCase):

    def test_contains_zone_and_pct(self):
        state = {"zone": "red", "pct": 75.0, "tokens": 150000, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Bash", 100, "abc123")
        self.assertIn("red", content)
        self.assertIn("75%", content)

    def test_contains_tool_name(self):
        state = {"zone": "green", "pct": 30.0, "tokens": 60000, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "WebSearch", 50, "sess1")
        self.assertIn("WebSearch", content)

    def test_contains_session_id_prefix(self):
        state = {"zone": "green", "pct": 30.0, "tokens": 0, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Read", 10, "abcdef12")
        self.assertIn("abcdef12", content)

    def test_contains_turn_count_comment(self):
        state = {"zone": "yellow", "pct": 55.0, "tokens": 0, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Edit", 42, "sess")
        self.assertIn("turn_count: 42", content)

    def test_handles_empty_state(self):
        content = compact_anchor.build_anchor_content({}, "Read", 0, "")
        self.assertIn("unknown", content)

    def test_handles_missing_session_id(self):
        state = {"zone": "green", "pct": 10.0, "tokens": 0, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Glob", 5, "")
        # Should not raise, should contain 'unknown'
        self.assertIn("unknown", content)

    def test_roundtrip_turn_count_parseable(self):
        """The turn_count written by build_anchor_content should be parsed back correctly."""
        state = {"zone": "green", "pct": 20.0, "tokens": 0, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Glob", 77, "sess")
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            count = compact_anchor.load_anchor_turn_count(path)
            self.assertEqual(count, 77)
        finally:
            os.unlink(str(path))


class TestWriteAnchor(unittest.TestCase):

    def test_writes_content_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            anchor_path = Path(tmpdir) / "anchor.md"
            compact_anchor.write_anchor(anchor_path, "# Test Anchor\n")
            self.assertTrue(anchor_path.exists())
            self.assertEqual(anchor_path.read_text(), "# Test Anchor\n")

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            anchor_path = Path(tmpdir) / "anchor.md"
            anchor_path.write_text("old content")
            compact_anchor.write_anchor(anchor_path, "new content")
            self.assertEqual(anchor_path.read_text(), "new content")

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            anchor_path = Path(tmpdir) / "subdir" / "anchor.md"
            compact_anchor.write_anchor(anchor_path, "# Anchor")
            self.assertTrue(anchor_path.exists())


class TestIntegration(unittest.TestCase):

    def test_full_write_cycle(self):
        """State file → build content → write anchor → parse turn count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            anchor_path = Path(tmpdir) / "anchor.md"
            _write_state(state_path, "red", 74.0, turns=50)
            state = compact_anchor.load_state(state_path)
            turns = state.get("turns", 0)
            self.assertTrue(compact_anchor.should_write(turns, write_every=10))
            content = compact_anchor.build_anchor_content(state, "Agent", turns, "sess-abc")
            compact_anchor.write_anchor(anchor_path, content)
            parsed = compact_anchor.load_anchor_turn_count(anchor_path)
            self.assertEqual(parsed, 50)

    def test_no_write_when_not_on_interval(self):
        """Should not write when turn count is not a multiple of write_every."""
        state = {"zone": "green", "pct": 20.0, "turns": 17, "tokens": 0, "window": 200000}
        self.assertFalse(compact_anchor.should_write(state["turns"], write_every=10))


class TestAutocompactInAnchor(unittest.TestCase):
    """Tests for autocompact proximity display in compact anchor."""

    def test_anchor_includes_autocompact_proximity(self):
        state = {
            "zone": "yellow", "pct": 55.0, "tokens": 110000, "window": 200000,
            "autocompact_pct": 60, "autocompact_proximity": 5.0,
        }
        content = compact_anchor.build_anchor_content(state, "Agent", 50, "sess1")
        self.assertIn("auto-compact", content.lower().replace("autocompact", "auto-compact"))
        self.assertIn("5", content)

    def test_anchor_without_autocompact_no_crash(self):
        state = {"zone": "green", "pct": 30.0, "tokens": 60000, "window": 200000}
        content = compact_anchor.build_anchor_content(state, "Read", 10, "sess1")
        # Should not contain autocompact line
        self.assertNotIn("Auto-compact", content)

    def test_anchor_autocompact_zero_proximity(self):
        state = {
            "zone": "red", "pct": 72.0, "tokens": 144000, "window": 200000,
            "autocompact_pct": 70, "autocompact_proximity": 0.0,
        }
        content = compact_anchor.build_anchor_content(state, "Bash", 70, "sess1")
        self.assertIn("IMMINENT", content)


if __name__ == "__main__":
    unittest.main()
