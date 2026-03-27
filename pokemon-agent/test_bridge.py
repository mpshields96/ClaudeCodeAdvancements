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

# Red-specific imports for e2e mGBA path tests
import memory_reader_red as mrr
from text_reader_red import TextReaderRed


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


class TestBridgeRedStateWrite(unittest.TestCase):
    """Test bridge.write_state with Pokemon Red readers (mGBA backend path).

    Exercises the same bridge functions as Crystal tests but with
    MemoryReaderRed + TextReaderRed using Gen 1 RAM layout.
    """

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.reader = mrr.MemoryReaderRed(self.emu)
        self.text_reader = TextReaderRed(self.emu)
        self.tmpdir = tempfile.mkdtemp()
        bridge.BRIDGE_DIR = self.tmpdir
        bridge.STATE_FILE = os.path.join(self.tmpdir, "state.json")
        bridge.SCREENSHOT_FILE = os.path.join(self.tmpdir, "screenshot.png")
        bridge.READY_FILE = os.path.join(self.tmpdir, ".ready")

        # Set up a Charmander in Gen 1 RAM layout
        self.emu.write_byte(mrr.PARTY_COUNT, 1)
        base = mrr.PARTY_BASE_ADDRS[0]
        self.emu.write_byte(base + mrr.OFF_SPECIES, 0xB0)  # Charmander
        self.emu.write_byte(base + mrr.OFF_LEVEL, 5)
        self.emu.write_byte(base + mrr.OFF_HP_HI, 0)
        self.emu.write_byte(base + mrr.OFF_HP_LO, 20)
        self.emu.write_byte(base + mrr.OFF_MAX_HP_HI, 0)
        self.emu.write_byte(base + mrr.OFF_MAX_HP_LO, 20)
        self.emu.write_byte(base + mrr.OFF_MOVE1, 0x0A)  # SCRATCH
        self.emu.write_byte(base + mrr.OFF_PP1, 35)
        self.emu.write_byte(base + mrr.OFF_MOVE2, 0x2D)  # GROWL
        self.emu.write_byte(base + mrr.OFF_PP2, 40)
        # Set position — Pallet Town
        self.emu.write_byte(mrr.MAP_ID, 0)  # PALLET TOWN
        self.emu.write_byte(mrr.PLAYER_X, 3)
        self.emu.write_byte(mrr.PLAYER_Y, 4)

    def test_write_state_creates_json(self):
        state = bridge.write_state(self.reader, self.emu, step=1, text_reader=self.text_reader)
        self.assertTrue(os.path.exists(bridge.STATE_FILE))
        with open(bridge.STATE_FILE) as f:
            data = json.load(f)
        self.assertEqual(data["step"], 1)

    def test_state_has_charmander(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(len(state["party"]), 1)
        self.assertEqual(state["party"][0]["species"], "CHARMANDER")
        self.assertEqual(state["party"][0]["level"], 5)
        self.assertEqual(state["party"][0]["hp"], 20)
        self.assertEqual(state["party"][0]["hp_max"], 20)

    def test_state_has_red_position(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["position"]["x"], 3)
        self.assertEqual(state["position"]["y"], 4)
        self.assertEqual(state["position"]["map_name"], "PALLET TOWN")
        # Red uses flat map IDs (map_group=0)
        self.assertEqual(state["position"]["map_group"], 0)

    def test_state_has_moves(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        moves = state["party"][0]["moves"]
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0]["name"], "SCRATCH")
        self.assertEqual(moves[0]["pp"], 35)
        self.assertEqual(moves[1]["name"], "GROWL")

    def test_state_no_battle(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertIsNone(state["battle"])

    def test_state_battle_wild(self):
        """Test that wild battle state reads correctly."""
        self.emu.write_byte(mrr.BATTLE_MODE, 1)  # Wild battle
        self.emu.write_byte(mrr.ENEMY_MON_SPECIES, 0xA5)  # RATTATA
        self.emu.write_byte(mrr.ENEMY_MON_LEVEL, 3)
        self.emu.write_byte(mrr.ENEMY_MON_HP_HI, 0)
        self.emu.write_byte(mrr.ENEMY_MON_HP_LO, 12)
        self.emu.write_byte(mrr.ENEMY_MON_MAX_HP_HI, 0)
        self.emu.write_byte(mrr.ENEMY_MON_MAX_HP_LO, 12)
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertIsNotNone(state["battle"])
        self.assertEqual(state["battle"]["type"], "wild")
        self.assertEqual(state["battle"]["enemy_species"], "RATTATA")
        self.assertEqual(state["battle"]["enemy_level"], 3)

    def test_state_badges_empty(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["badges"], 0)

    def test_state_badges_boulder(self):
        self.emu.write_byte(mrr.BADGES_ADDR, 0x01)  # Boulder Badge
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["badges"], 1)

    def test_state_money_bcd(self):
        """Test BCD money decoding."""
        # Set money to $3000 — BCD: 0x03, 0x00, 0x00
        self.emu.write_byte(mrr.MONEY_ADDR, 0x00)
        self.emu.write_byte(mrr.MONEY_ADDR + 1, 0x30)
        self.emu.write_byte(mrr.MONEY_ADDR + 2, 0x00)
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["money"], 3000)

    def test_text_reader_no_dialog(self):
        """TextReaderRed returns empty when no dialog active."""
        state = bridge.write_state(self.reader, self.emu, step=1, text_reader=self.text_reader)
        # No dialog flags set, should be empty
        self.assertEqual(state["text_on_screen"], "")

    def test_menu_state_overworld(self):
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["menu_state"], "overworld")

    def test_menu_state_battle(self):
        self.emu.write_byte(mrr.BATTLE_MODE, 1)
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["menu_state"], "battle")

    def test_menu_state_dialog(self):
        self.emu.write_byte(mrr.JOY_DISABLED, 0x20)  # Bit 5 set
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(state["menu_state"], "dialog")

    def test_ready_file_created(self):
        bridge.write_state(self.reader, self.emu, step=1, text_reader=self.text_reader)
        self.assertTrue(os.path.exists(bridge.READY_FILE))

    def test_full_party_six_pokemon(self):
        """Test reading a full 6-pokemon party."""
        self.emu.write_byte(mrr.PARTY_COUNT, 6)
        species = [0xB0, 0x24, 0xA5, 0x54, 0x6C, 0x7B]  # Charmander, Pidgey, Rattata, Pikachu, Zubat, Caterpie
        for i, sp in enumerate(species):
            base = mrr.PARTY_BASE_ADDRS[i]
            self.emu.write_byte(base + mrr.OFF_SPECIES, sp)
            self.emu.write_byte(base + mrr.OFF_LEVEL, 5 + i)
            self.emu.write_byte(base + mrr.OFF_HP_LO, 20)
            self.emu.write_byte(base + mrr.OFF_MAX_HP_LO, 20)
        state = bridge.write_state(self.reader, self.emu, step=1)
        self.assertEqual(len(state["party"]), 6)
        self.assertEqual(state["party"][0]["species"], "CHARMANDER")
        self.assertEqual(state["party"][3]["species"], "PIKACHU")

    def test_execute_direction_movement(self):
        """Test that directional movement executes through bridge."""
        action = {"type": "press_buttons", "buttons": ["up", "right", "down", "left"]}
        result = bridge.execute_action(self.emu, action)
        self.assertEqual(result["executed"], "press_buttons")
        self.assertEqual(result["buttons"], ["up", "right", "down", "left"])


class TestBridgeNavigateAction(unittest.TestCase):
    """Test the navigate action type using A* pathfinding."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        from collision_reader_red import CollisionReaderRed, MAP_HEIGHT, MAP_WIDTH
        from navigation import Navigator
        self.collision_reader = CollisionReaderRed(self.emu)
        self.nav = Navigator()
        # Set up a 4x4 tile map (2x2 blocks)
        self.emu.write_byte(MAP_HEIGHT, 2)
        self.emu.write_byte(MAP_WIDTH, 2)
        self.emu.write_byte(mrr.MAP_ID, 0)
        # Player at (1, 1)
        self.emu.write_byte(mrr.PLAYER_X, 1)
        self.emu.write_byte(mrr.PLAYER_Y, 1)

    def test_navigate_finds_path(self):
        action = {"type": "navigate", "x": 3, "y": 1}
        result = bridge.execute_action(
            self.emu, action, nav=self.nav, collision_reader=self.collision_reader
        )
        self.assertEqual(result["executed"], "navigate")
        self.assertIn("steps", result)
        self.assertGreater(result["steps"], 0)
        self.assertEqual(result["to"], (3, 1))

    def test_navigate_already_there(self):
        action = {"type": "navigate", "x": 1, "y": 1}
        result = bridge.execute_action(
            self.emu, action, nav=self.nav, collision_reader=self.collision_reader
        )
        self.assertEqual(result["executed"], "navigate")
        self.assertTrue(result.get("already_there"))

    def test_navigate_missing_coords(self):
        action = {"type": "navigate"}
        result = bridge.execute_action(
            self.emu, action, nav=self.nav, collision_reader=self.collision_reader
        )
        self.assertIn("error", result)

    def test_navigate_without_collision_reader(self):
        action = {"type": "navigate", "x": 3, "y": 1}
        result = bridge.execute_action(self.emu, action)
        self.assertIn("error", result)

    def test_navigate_returns_path_directions(self):
        action = {"type": "navigate", "x": 3, "y": 1}
        result = bridge.execute_action(
            self.emu, action, nav=self.nav, collision_reader=self.collision_reader
        )
        if result.get("path"):
            for d in result["path"]:
                self.assertIn(d, ("up", "down", "left", "right"))


class TestMGBABackendImport(unittest.TestCase):
    """Test that mGBA backend class exists and has correct interface."""

    def test_mgba_backend_class_exists(self):
        from emulator_control import MGBABackend
        self.assertTrue(hasattr(MGBABackend, 'press'))
        self.assertTrue(hasattr(MGBABackend, 'release'))
        self.assertTrue(hasattr(MGBABackend, 'tick'))
        self.assertTrue(hasattr(MGBABackend, 'read_byte'))
        self.assertTrue(hasattr(MGBABackend, 'read_bytes'))
        self.assertTrue(hasattr(MGBABackend, 'write_byte'))
        self.assertTrue(hasattr(MGBABackend, 'save_state'))
        self.assertTrue(hasattr(MGBABackend, 'load_state'))
        self.assertTrue(hasattr(MGBABackend, 'screenshot'))
        self.assertTrue(hasattr(MGBABackend, 'close'))

    def test_from_rom_default_backend_is_mgba(self):
        """Verify from_rom defaults to mGBA backend."""
        from emulator_control import EmulatorControl
        import inspect
        sig = inspect.signature(EmulatorControl.from_rom)
        self.assertEqual(sig.parameters['backend'].default, 'mgba')

    def test_mock_backend_used_for_testing(self):
        """Verify mock backend works as stand-in for mGBA."""
        emu = EmulatorControl.mock()
        emu.write_byte(0x1000, 42)
        self.assertEqual(emu.read_byte(0x1000), 42)
        emu.press("a")
        emu.tick(10)
        emu.close()


if __name__ == "__main__":
    unittest.main()
