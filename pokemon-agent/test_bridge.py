"""Tests for the Claude Code bridge — emulator <-> file <-> Claude Code."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from memory_reader import MemoryReader, PARTY_COUNT, PARTY_DATA_START, OFF_SPECIES, OFF_LEVEL, OFF_HP_HI, OFF_HP_LO, OFF_HP_MAX_HI, OFF_HP_MAX_LO, MAP_GROUP, MAP_NUMBER, PLAYER_X, PLAYER_Y
from text_reader import TextReader
from checkpoint import CheckpointReason
import bridge


class TestBridgeStateWrite(unittest.TestCase):
    """Test state.json writing."""

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.reader = MemoryReader(self.emu)
        self.text_reader = TextReader(self.emu)
        self.tmpdir = tempfile.mkdtemp()
        # Override bridge paths
        bridge.BRIDGE_DIR = self.tmpdir
        bridge.STATE_FILE = os.path.join(self.tmpdir, "state.json")
        bridge.SCREENSHOT_FILE = os.path.join(self.tmpdir, "screenshot.png")
        bridge.READY_FILE = os.path.join(self.tmpdir, ".ready")

        # Set up a Cyndaquil
        self.emu.write_byte(PARTY_COUNT, 1)
        self.emu.write_byte(PARTY_DATA_START + OFF_SPECIES, 155)
        self.emu.write_byte(PARTY_DATA_START + OFF_LEVEL, 5)
        self.emu.write_byte(PARTY_DATA_START + OFF_HP_LO, 22)
        self.emu.write_byte(PARTY_DATA_START + OFF_HP_MAX_LO, 22)
        self.emu.write_byte(MAP_GROUP, 3)
        self.emu.write_byte(MAP_NUMBER, 1)
        self.emu.write_byte(PLAYER_X, 5)
        self.emu.write_byte(PLAYER_Y, 3)

    def test_write_state_creates_json(self):
        state = bridge.write_state(self.reader, self.emu, step=1, text_reader=self.text_reader)
        self.assertTrue(os.path.exists(bridge.STATE_FILE))
        with open(bridge.STATE_FILE) as f:
            data = json.load(f)
        self.assertEqual(data["step"], 1)

    def test_state_has_party(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(len(state["party"]), 1)
        self.assertEqual(state["party"][0]["species"], "Cyndaquil")
        self.assertEqual(state["party"][0]["level"], 5)

    def test_state_has_position(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["position"]["x"], 5)
        self.assertEqual(state["position"]["y"], 3)

    def test_ready_file_created(self):
        bridge.write_state(self.reader, self.emu, step=1)
        self.assertTrue(os.path.exists(bridge.READY_FILE))

    def test_state_has_menu_state(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["menu_state"], "overworld")

    def test_state_has_badges(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["badges"], 0)

    def test_state_no_battle(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertIsNone(state["battle"])


class TestBridgeActionRead(unittest.TestCase):
    """Test action.json reading."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        bridge.ACTION_FILE = os.path.join(self.tmpdir, "action.json")

    def test_no_action_returns_none(self):
        self.assertIsNone(bridge.read_action())

    def test_read_action_returns_dict(self):
        action = {"type": "press_buttons", "buttons": ["a"]}
        with open(bridge.ACTION_FILE, "w") as f:
            json.dump(action, f)
        result = bridge.read_action()
        self.assertEqual(result["type"], "press_buttons")
        self.assertEqual(result["buttons"], ["a"])

    def test_action_consumed_after_read(self):
        action = {"type": "press_buttons", "buttons": ["b"]}
        with open(bridge.ACTION_FILE, "w") as f:
            json.dump(action, f)
        bridge.read_action()
        self.assertFalse(os.path.exists(bridge.ACTION_FILE))

    def test_invalid_json_returns_none(self):
        with open(bridge.ACTION_FILE, "w") as f:
            f.write("not json{{{")
        self.assertIsNone(bridge.read_action())


class TestBridgeActionExec(unittest.TestCase):
    """Test action execution on mock emulator."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def test_press_buttons(self):
        action = {"type": "press_buttons", "buttons": ["a", "b"]}
        result = bridge.execute_action(self.emu, action)
        self.assertEqual(result["executed"], "press_buttons")
        self.assertEqual(result["buttons"], ["a", "b"])

    def test_wait(self):
        result = bridge.execute_action(self.emu, {"type": "wait", "frames": 30})
        self.assertEqual(result["executed"], "wait")
        self.assertEqual(result["frames"], 30)

    def test_unknown_action(self):
        result = bridge.execute_action(self.emu, {"type": "fly_to_moon"})
        self.assertIn("error", result)

    def test_invalid_buttons_skipped(self):
        action = {"type": "press_buttons", "buttons": ["a", "INVALID", "b"]}
        result = bridge.execute_action(self.emu, action)
        self.assertEqual(result["executed"], "press_buttons")

    def test_save_action(self):
        self.emu.set_state_dir(tempfile.mkdtemp())
        result = bridge.execute_action(self.emu, {"type": "save", "name": "test_save"})
        self.assertEqual(result["executed"], "save")

    def test_load_nonexistent(self):
        self.emu.set_state_dir(tempfile.mkdtemp())
        result = bridge.execute_action(self.emu, {"type": "load", "name": "nope"})
        self.assertIn("error", result)


class TestBridgeLog(unittest.TestCase):
    """Test step logging."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        bridge.LOG_FILE = os.path.join(self.tmpdir, "log.jsonl")

    def test_log_creates_file(self):
        bridge.log_step(1, {"position": {"x": 5}}, {"type": "press_buttons"}, {"ok": True})
        self.assertTrue(os.path.exists(bridge.LOG_FILE))

    def test_log_appends(self):
        bridge.log_step(1, {}, {}, {})
        bridge.log_step(2, {}, {}, {})
        with open(bridge.LOG_FILE) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    def test_log_valid_json(self):
        bridge.log_step(1, {"pos": "here"}, {"type": "a"}, {"done": True})
        with open(bridge.LOG_FILE) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["step"], 1)


class TestBridgeCheckpointing(unittest.TestCase):
    """Checkpoint transitions should compare real previous and current states."""

    def test_first_state_never_checkpoints(self):
        mgr = Mock()
        reasons = bridge.maybe_checkpoint(None, object(), mgr, step=1)
        self.assertEqual(reasons, [])
        mgr.should_checkpoint.assert_not_called()
        mgr.save_checkpoint.assert_not_called()

    def test_checkpoint_uses_previous_and_current_state(self):
        prev_state = object()
        curr_state = object()
        mgr = Mock()
        mgr.should_checkpoint.return_value = [CheckpointReason.MAP_TRANSITION]

        reasons = bridge.maybe_checkpoint(prev_state, curr_state, mgr, step=7)

        self.assertEqual(reasons, ["map_transition"])
        mgr.should_checkpoint.assert_called_once_with(
            prev_state,
            curr_state,
            current_step=7,
        )
        mgr.save_checkpoint.assert_called_once()

    def test_no_reasons_skips_save(self):
        mgr = Mock()
        mgr.should_checkpoint.return_value = []

        reasons = bridge.maybe_checkpoint(object(), object(), mgr, step=3)

        self.assertEqual(reasons, [])
        mgr.save_checkpoint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
