"""Tests for boot_sequence wiring into RedAgent, bridge.py, and main.py.

Verifies that:
1. RedAgent can auto-boot via boot() method
2. RedAgent auto_boot=True calls boot on construction
3. bridge.py runs boot_sequence for Red games when no saved state
4. main.py selects RedAgent for .gb ROMs
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl, MockBackend
from game_state import GameState, MapPosition, MenuState, Party, BattleState, Badges
import memory_reader_red as mrr
from boot_sequence import MAP_REDS_HOUSE_2F, MAP_REDS_HOUSE_1F, MAP_PALLET_TOWN


class TestRedAgentBootMethod(unittest.TestCase):
    """Test RedAgent.boot() method."""

    def _make_agent(self, auto_boot=False):
        from red_agent import RedAgent
        emu = EmulatorControl.mock(ram_size=0x10000)
        emu.write_byte(mrr.MAP_ID, MAP_REDS_HOUSE_2F)
        emu.write_byte(mrr.PLAYER_X, 3)
        emu.write_byte(mrr.PLAYER_Y, 6)
        emu.write_byte(mrr.PARTY_COUNT, 0)
        return RedAgent(emulator=emu, auto_boot=auto_boot), emu

    def test_boot_method_exists(self):
        from red_agent import RedAgent
        self.assertTrue(hasattr(RedAgent, 'boot'))

    def test_boot_method_calls_run_boot_sequence(self):
        agent, emu = self._make_agent()
        with patch('red_agent.run_boot_sequence') as mock_boot:
            mock_boot.return_value = {
                "success": True,
                "final_map": MAP_PALLET_TOWN,
                "final_position": (3, 3),
                "phases_completed": ["opening_dialog", "stairs_to_1f", "exit_house"],
            }
            result = agent.boot()
            mock_boot.assert_called_once_with(emu, agent.reader)
            self.assertTrue(result["success"])

    def test_boot_returns_result_dict(self):
        agent, emu = self._make_agent()
        with patch('red_agent.run_boot_sequence') as mock_boot:
            mock_boot.return_value = {
                "success": True,
                "final_map": 0,
                "final_position": (3, 3),
                "phases_completed": ["opening_dialog"],
            }
            result = agent.boot()
            self.assertIn("success", result)
            self.assertIn("phases_completed", result)

    def test_boot_stores_result(self):
        agent, emu = self._make_agent()
        with patch('red_agent.run_boot_sequence') as mock_boot:
            mock_boot.return_value = {
                "success": True,
                "final_map": 0,
                "final_position": (3, 3),
                "phases_completed": ["opening_dialog"],
            }
            agent.boot()
            self.assertIsNotNone(agent.boot_result)
            self.assertTrue(agent.boot_result["success"])

    def test_boot_result_none_before_boot(self):
        agent, _ = self._make_agent()
        self.assertIsNone(agent.boot_result)

    def test_auto_boot_true_runs_boot_on_init(self):
        """auto_boot=True should call boot() during __init__."""
        with patch('red_agent.run_boot_sequence') as mock_boot:
            mock_boot.return_value = {
                "success": True,
                "final_map": 0,
                "final_position": (3, 3),
                "phases_completed": ["opening_dialog"],
            }
            agent, _ = self._make_agent(auto_boot=True)
            mock_boot.assert_called_once()
            self.assertIsNotNone(agent.boot_result)

    def test_auto_boot_false_does_not_boot(self):
        """auto_boot=False (default) should NOT call boot()."""
        with patch('red_agent.run_boot_sequence') as mock_boot:
            agent, _ = self._make_agent(auto_boot=False)
            mock_boot.assert_not_called()
            self.assertIsNone(agent.boot_result)

    def test_boot_failure_does_not_crash(self):
        """Boot failure should be logged, not raise."""
        agent, _ = self._make_agent()
        with patch('red_agent.run_boot_sequence') as mock_boot:
            mock_boot.return_value = {
                "success": False,
                "final_map": MAP_REDS_HOUSE_2F,
                "final_position": (3, 6),
                "phases_completed": [],
            }
            result = agent.boot()
            self.assertFalse(result["success"])


class TestMainPyRedSelection(unittest.TestCase):
    """Test main.py uses RedAgent for .gb ROMs."""

    def test_parse_args_accepts_red_rom(self):
        from main import parse_args
        args = parse_args(["--rom", "pokemon_red.gb", "--offline", "--steps", "1"])
        self.assertEqual(args.rom, "pokemon_red.gb")

    def test_detect_game_type_from_extension(self):
        """main.py should detect game type from ROM extension."""
        from main import detect_game_type
        self.assertEqual(detect_game_type("pokemon_red.gb"), "red")
        self.assertEqual(detect_game_type("pokemon_crystal.gbc"), "crystal")
        self.assertEqual(detect_game_type("pokemon_firered.gba"), "firered")
        self.assertEqual(detect_game_type("unknown.bin"), "red")  # Default


class TestBridgeBootIntegration(unittest.TestCase):
    """Test bridge.py boot_sequence integration for Red games."""

    def test_bridge_has_boot_option(self):
        """bridge.py should accept --no-boot flag."""
        import bridge
        parser = bridge.build_parser()
        args = parser.parse_args(["--rom", "pokemon_red.gb", "--no-boot"])
        self.assertTrue(args.no_boot)

    def test_bridge_boot_default_true_for_red(self):
        """By default, bridge should boot for Red games."""
        import bridge
        parser = bridge.build_parser()
        args = parser.parse_args(["--rom", "pokemon_red.gb"])
        self.assertFalse(args.no_boot)


class TestBridgeViewerServer(unittest.TestCase):
    """Test bridge.py viewer HTTP server."""

    def test_bridge_has_serve_port_option(self):
        """bridge.py should accept --port flag for viewer server."""
        import bridge
        parser = bridge.build_parser()
        args = parser.parse_args(["--rom", "pokemon_red.gb", "--port", "8765"])
        self.assertEqual(args.port, 8765)

    def test_bridge_default_port(self):
        """Default port should be 8000."""
        import bridge
        parser = bridge.build_parser()
        args = parser.parse_args(["--rom", "pokemon_red.gb"])
        self.assertEqual(args.port, 8000)

    def test_bridge_no_serve_flag(self):
        """--no-serve should disable the viewer server."""
        import bridge
        parser = bridge.build_parser()
        args = parser.parse_args(["--rom", "pokemon_red.gb", "--no-serve"])
        self.assertTrue(args.no_serve)

    def test_start_viewer_server_function_exists(self):
        """start_viewer_server should be importable."""
        from bridge import start_viewer_server
        self.assertTrue(callable(start_viewer_server))

    def test_start_viewer_server_returns_thread(self):
        """start_viewer_server should return a daemon thread."""
        import threading
        from bridge import start_viewer_server
        server_thread = start_viewer_server(port=0)  # port=0 picks random
        self.assertIsInstance(server_thread, threading.Thread)
        self.assertTrue(server_thread.daemon)
        # Thread should be alive
        self.assertTrue(server_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
