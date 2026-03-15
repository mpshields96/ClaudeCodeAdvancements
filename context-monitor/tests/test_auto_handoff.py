"""
Tests for CTX-4: auto-handoff Stop hook.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import auto_handoff


def _write_state(path: Path, zone: str, pct: float) -> None:
    state = {"zone": zone, "pct": pct, "tokens": 0, "turns": 0, "window": 200000}
    with open(path, "w") as f:
        json.dump(state, f)


class TestLoadState(unittest.TestCase):

    def test_loads_valid_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"zone": "critical", "pct": 88.0}, f)
            path = Path(f.name)
        try:
            state = auto_handoff.load_state(path)
            self.assertEqual(state["zone"], "critical")
            self.assertAlmostEqual(state["pct"], 88.0)
        finally:
            os.unlink(str(path))

    def test_returns_empty_for_missing_file(self):
        state = auto_handoff.load_state(Path("/tmp/no_such_handoff_state.json"))
        self.assertEqual(state, {})

    def test_returns_empty_for_bad_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not valid json")
            path = Path(f.name)
        try:
            state = auto_handoff.load_state(path)
            self.assertEqual(state, {})
        finally:
            os.unlink(str(path))


class TestHandoffIsFresh(unittest.TestCase):

    def test_returns_false_when_file_missing(self):
        self.assertFalse(auto_handoff.handoff_is_fresh(Path("/tmp/no_handoff.md"), 5))

    def test_returns_true_for_recently_written_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Handoff")
            path = Path(f.name)
        try:
            # File was just created — should be fresh for any reasonable max_age
            self.assertTrue(auto_handoff.handoff_is_fresh(path, max_age_minutes=5))
        finally:
            os.unlink(str(path))

    def test_returns_false_for_old_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Handoff")
            path = Path(f.name)
        try:
            # Backdate the file mtime by 10 minutes
            old_time = time.time() - 600
            os.utime(str(path), (old_time, old_time))
            self.assertFalse(auto_handoff.handoff_is_fresh(path, max_age_minutes=5))
        finally:
            os.unlink(str(path))

    def test_returns_true_for_file_within_max_age(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Handoff")
            path = Path(f.name)
        try:
            # File is 1 minute old — well within 5-minute window
            one_min_ago = time.time() - 60
            os.utime(str(path), (one_min_ago, one_min_ago))
            self.assertTrue(auto_handoff.handoff_is_fresh(path, max_age_minutes=5))
        finally:
            os.unlink(str(path))


class TestShouldBlock(unittest.TestCase):

    def test_blocks_on_critical_zone(self):
        self.assertTrue(auto_handoff.should_block("critical", handoff_fresh=False))

    def test_does_not_block_when_handoff_fresh(self):
        self.assertFalse(auto_handoff.should_block("critical", handoff_fresh=True))

    def test_does_not_block_on_red_by_default(self):
        self.assertFalse(auto_handoff.should_block("red", handoff_fresh=False, block_on_red=False))

    def test_blocks_on_red_when_flag_set(self):
        self.assertTrue(auto_handoff.should_block("red", handoff_fresh=False, block_on_red=True))

    def test_does_not_block_on_green(self):
        self.assertFalse(auto_handoff.should_block("green", handoff_fresh=False))

    def test_does_not_block_on_yellow(self):
        self.assertFalse(auto_handoff.should_block("yellow", handoff_fresh=False))

    def test_does_not_block_on_unknown(self):
        self.assertFalse(auto_handoff.should_block("unknown", handoff_fresh=False))

    def test_red_fresh_handoff_does_not_block_even_with_flag(self):
        self.assertFalse(auto_handoff.should_block("red", handoff_fresh=True, block_on_red=True))


class TestShouldWarn(unittest.TestCase):

    def test_warns_on_red_zone(self):
        self.assertTrue(auto_handoff.should_warn("red", handoff_fresh=False))

    def test_no_warn_when_handoff_fresh(self):
        self.assertFalse(auto_handoff.should_warn("red", handoff_fresh=True))

    def test_no_warn_on_green(self):
        self.assertFalse(auto_handoff.should_warn("green", handoff_fresh=False))

    def test_no_warn_on_critical(self):
        # Critical → block, not warn
        self.assertFalse(auto_handoff.should_warn("critical", handoff_fresh=False))


class TestMessages(unittest.TestCase):

    def test_block_message_contains_pct_and_zone(self):
        msg = auto_handoff.build_block_message("critical", 88.0)
        self.assertIn("88%", msg)
        self.assertIn("critical", msg)
        self.assertIn("/handoff", msg)

    def test_warn_message_contains_pct(self):
        msg = auto_handoff.build_warn_message("red", 74.0)
        self.assertIn("74%", msg)
        self.assertIn("red", msg)


class TestResponseFormats(unittest.TestCase):

    def test_allow_response_is_empty_dict(self):
        resp = auto_handoff._allow_response()
        self.assertEqual(resp, {})

    def test_block_response_has_decision_and_reason(self):
        resp = auto_handoff._block_response("Save your work!")
        self.assertEqual(resp["decision"], "block")
        self.assertIn("Save your work!", resp["reason"])


class TestIntegration(unittest.TestCase):
    """Integration: state file + handoff file → correct action."""

    def test_critical_no_handoff_returns_block(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as sf:
            state_path = Path(sf.name)
        _write_state(state_path, "critical", 90.0)
        try:
            state = auto_handoff.load_state(state_path)
            zone = state.get("zone", "unknown")
            pct = float(state.get("pct", 0))
            fresh = auto_handoff.handoff_is_fresh(Path("/tmp/no_such_handoff_ctxtest.md"), 5)
            block = auto_handoff.should_block(zone, fresh)
            self.assertTrue(block)
            resp = auto_handoff._block_response(auto_handoff.build_block_message(zone, pct))
            self.assertEqual(resp["decision"], "block")
        finally:
            os.unlink(str(state_path))

    def test_critical_with_fresh_handoff_returns_allow(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as sf:
            state_path = Path(sf.name)
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as hf:
            handoff_path = Path(hf.name)
            hf.write("# Handoff")
        _write_state(state_path, "critical", 91.0)
        try:
            state = auto_handoff.load_state(state_path)
            zone = state.get("zone", "unknown")
            fresh = auto_handoff.handoff_is_fresh(handoff_path, 5)
            block = auto_handoff.should_block(zone, fresh)
            self.assertFalse(block)  # Handoff is fresh — don't block
        finally:
            os.unlink(str(state_path))
            os.unlink(str(handoff_path))

    def test_green_zone_always_allows(self):
        state = {"zone": "green", "pct": 30.0}
        zone = state.get("zone", "unknown")
        fresh = False
        self.assertFalse(auto_handoff.should_block(zone, fresh))
        self.assertFalse(auto_handoff.should_warn(zone, fresh))

    def test_red_zone_no_block_but_warns(self):
        state = {"zone": "red", "pct": 75.0}
        zone = state.get("zone")
        fresh = False
        self.assertFalse(auto_handoff.should_block(zone, fresh, block_on_red=False))
        self.assertTrue(auto_handoff.should_warn(zone, fresh))


if __name__ == "__main__":
    unittest.main()
