"""Tests for RedAgent — Pokemon Red variant of the agent loop.

Tests that RedAgent properly uses Red-specific RAM addresses,
memory reader, text reader, and collision reader.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from game_state import MapPosition
import memory_reader_red as mrr


class TestRedAgentConstruction(unittest.TestCase):
    """Test RedAgent can be constructed with Red-specific components."""

    def test_imports_successfully(self):
        from red_agent import RedAgent
        self.assertTrue(callable(RedAgent))

    def test_constructs_with_mock_emulator(self):
        from red_agent import RedAgent
        emu = EmulatorControl.mock(ram_size=0x10000)
        agent = RedAgent(emulator=emu)
        self.assertIsNotNone(agent)
        self.assertIsNotNone(agent.reader)
        self.assertIsNotNone(agent.text_reader)
        self.assertIsNotNone(agent.navigator)

    def test_uses_red_memory_reader(self):
        from red_agent import RedAgent
        from memory_reader_red import MemoryReaderRed
        emu = EmulatorControl.mock(ram_size=0x10000)
        agent = RedAgent(emulator=emu)
        self.assertIsInstance(agent.reader, MemoryReaderRed)

    def test_uses_red_text_reader(self):
        from red_agent import RedAgent
        from text_reader_red import TextReaderRed
        emu = EmulatorControl.mock(ram_size=0x10000)
        agent = RedAgent(emulator=emu)
        self.assertIsInstance(agent.text_reader, TextReaderRed)

    def test_navigator_has_warps_loaded(self):
        from red_agent import RedAgent
        emu = EmulatorControl.mock(ram_size=0x10000)
        agent = RedAgent(emulator=emu)
        self.assertGreater(len(agent.navigator._warps), 0)
        self.assertGreater(len(agent.navigator._connections), 0)

    def test_has_collision_reader(self):
        from red_agent import RedAgent
        from collision_reader_red import CollisionReaderRed
        emu = EmulatorControl.mock(ram_size=0x10000)
        agent = RedAgent(emulator=emu)
        self.assertIsInstance(agent.collision_reader, CollisionReaderRed)


class TestRedAgentStep(unittest.TestCase):
    """Test RedAgent step execution (offline mode, no LLM)."""

    def setUp(self):
        from red_agent import RedAgent
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        # Set up minimal Red game state
        self.emu.write_byte(mrr.MAP_ID, 0)  # Pallet Town
        self.emu.write_byte(mrr.PLAYER_X, 5)
        self.emu.write_byte(mrr.PLAYER_Y, 5)
        self.emu.write_byte(mrr.PARTY_COUNT, 1)
        base = mrr.PARTY_BASE_ADDRS[0]
        self.emu.write_byte(base + mrr.OFF_SPECIES, 0xB0)  # Charmander
        self.emu.write_byte(base + mrr.OFF_LEVEL, 5)
        self.emu.write_byte(base + mrr.OFF_HP_LO, 20)
        self.emu.write_byte(base + mrr.OFF_MAX_HP_LO, 20)
        self.agent = RedAgent(emulator=self.emu)

    def test_step_returns_result(self):
        result = self.agent.step()
        self.assertEqual(result.step_number, 1)
        self.assertIsNotNone(result.state)

    def test_step_reads_red_position(self):
        result = self.agent.step()
        self.assertEqual(result.state.position.map_id, 0)
        self.assertEqual(result.state.position.x, 5)
        self.assertEqual(result.state.position.y, 5)

    def test_step_increments_counter(self):
        self.agent.step()
        self.agent.step()
        self.assertEqual(self.agent.step_count, 2)

    def test_offline_mode_presses_a(self):
        """Without LLM, agent should press A (title screen / dialog advance)."""
        result = self.agent.step()
        self.assertIn("offline", result.llm_text)

    def test_run_multiple_steps(self):
        results = self.agent.run(num_steps=5)
        self.assertEqual(len(results), 5)
        self.assertEqual(self.agent.step_count, 5)


class TestRedAgentAutoAdvance(unittest.TestCase):
    """Test dialog auto-advance works with Red RAM addresses."""

    def setUp(self):
        from red_agent import RedAgent
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.emu.write_byte(mrr.MAP_ID, 0)
        self.emu.write_byte(mrr.PLAYER_X, 5)
        self.emu.write_byte(mrr.PLAYER_Y, 5)
        self.emu.write_byte(mrr.PARTY_COUNT, 0)
        self.agent = RedAgent(emulator=self.emu)

    def test_auto_advance_in_dialog(self):
        """When JOY_DISABLED bit 5 is set (dialog), should auto-press A."""
        self.emu.write_byte(mrr.JOY_DISABLED, 0x20)  # Bit 5 = dialog
        result = self.agent.step()
        # Should be auto-advance, not LLM call
        self.assertEqual(result.step_number, 1)


class TestRedAgentScreenDetection(unittest.TestCase):
    """Test screen transition detection with Red RAM addresses."""

    def setUp(self):
        from red_agent import RedAgent
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.emu.write_byte(mrr.MAP_ID, 0)
        self.emu.write_byte(mrr.PLAYER_X, 5)
        self.emu.write_byte(mrr.PLAYER_Y, 5)
        self.emu.write_byte(mrr.PARTY_COUNT, 0)
        self.agent = RedAgent(emulator=self.emu)

    def test_normal_state_step(self):
        """In normal gameplay state, step should work."""
        result = self.agent.step()
        self.assertIsNotNone(result)

    def test_battle_state_detected(self):
        """When in battle, should detect it in game state."""
        self.emu.write_byte(mrr.BATTLE_MODE, 1)  # Wild battle
        self.emu.write_byte(mrr.PARTY_COUNT, 1)
        base = mrr.PARTY_BASE_ADDRS[0]
        self.emu.write_byte(base + mrr.OFF_SPECIES, 0xB0)
        self.emu.write_byte(base + mrr.OFF_LEVEL, 5)
        self.emu.write_byte(base + mrr.OFF_HP_LO, 20)
        self.emu.write_byte(base + mrr.OFF_MAX_HP_LO, 20)
        result = self.agent.step()
        self.assertTrue(result.state.battle.in_battle)


if __name__ == "__main__":
    unittest.main()
