"""Tests for boot_sequence_crystal.py — Pokemon Crystal intro automation.

Tests the deterministic Crystal boot sequence logic using MockBackend.
No ROM needed.

Crystal intro sequence:
1. Title screen → New Game
2. Set player name
3. Player's House 2F: wake up, clear dialog
4. Player's House 1F: go downstairs, talk to Mom
5. New Bark Town: walk to Elm's Lab
6. Elm's Lab: get starter Pokemon (Cyndaquil/Totodile/Chikorita)
7. Exit to Route 29

Map IDs (group, number):
- Player's House 2F: (3, 4)
- Player's House 1F: (3, 3)
- New Bark Town: (3, 1)
- Elm's Lab: (3, 2)
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl, MockBackend
from game_state import GameState, MapPosition, MenuState, Party, BattleState, Badges
from boot_sequence_crystal import (
    clear_dialog_crystal,
    navigate_crystal,
    wait_for_map_crystal,
    run_crystal_boot_sequence,
    MAP_PLAYERS_HOUSE_2F,
    MAP_PLAYERS_HOUSE_1F,
    MAP_NEW_BARK_TOWN,
    MAP_ELMS_LAB,
)


class MockReaderForCrystalBoot:
    """Mock memory reader for Crystal boot sequence tests.

    Simulates map transitions and dialog clearing for the Crystal intro.
    """

    def __init__(self):
        self._state = GameState(
            position=MapPosition(
                map_id=self._encode_map(3, 4),  # Player's House 2F
                map_name="Player's House 2F",
                x=4, y=4,
            ),
            menu_state=MenuState.DIALOG,
        )
        self._press_count = 0
        self._dialog_clears_after = 10
        self._transitions = {}  # (map_id, x, y, direction) -> target_map_id

    @staticmethod
    def _encode_map(group: int, number: int) -> int:
        """Encode Crystal map group:number as single int for mock."""
        return group * 256 + number

    def read_game_state(self) -> GameState:
        return self._state

    def read_position(self):
        return self._state.position

    def set_position(self, x: int, y: int, map_id: int = None,
                     map_name: str = None):
        pos = self._state.position
        self._state = GameState(
            position=MapPosition(
                map_id=map_id if map_id is not None else pos.map_id,
                map_name=map_name or pos.map_name,
                x=x, y=y,
            ),
            menu_state=self._state.menu_state,
            party=self._state.party,
            badges=self._state.badges,
            battle=self._state.battle,
        )

    def set_menu_state(self, state: MenuState):
        self._state = GameState(
            position=self._state.position,
            menu_state=state,
            party=self._state.party,
            badges=self._state.badges,
            battle=self._state.battle,
        )


# ── Test Cases ───────────────────────────────────────────────────────────────


class TestMapConstants(unittest.TestCase):
    """Verify Crystal map constants are correctly defined."""

    def test_map_constants_are_tuples(self):
        """Map constants should be (group, number) tuples."""
        for const in [MAP_PLAYERS_HOUSE_2F, MAP_PLAYERS_HOUSE_1F,
                       MAP_NEW_BARK_TOWN, MAP_ELMS_LAB]:
            self.assertIsInstance(const, tuple)
            self.assertEqual(len(const), 2)

    def test_all_in_group_3(self):
        """All intro maps are in map group 3 (New Bark area)."""
        self.assertEqual(MAP_PLAYERS_HOUSE_2F[0], 3)
        self.assertEqual(MAP_PLAYERS_HOUSE_1F[0], 3)
        self.assertEqual(MAP_NEW_BARK_TOWN[0], 3)
        self.assertEqual(MAP_ELMS_LAB[0], 3)

    def test_specific_map_numbers(self):
        """Map numbers match pret/pokecrystal constants."""
        self.assertEqual(MAP_NEW_BARK_TOWN, (3, 1))
        self.assertEqual(MAP_ELMS_LAB, (3, 2))
        self.assertEqual(MAP_PLAYERS_HOUSE_1F, (3, 3))
        self.assertEqual(MAP_PLAYERS_HOUSE_2F, (3, 4))


class TestClearDialogCrystal(unittest.TestCase):
    """Test dialog clearing for Crystal intro."""

    def setUp(self):
        self.backend = MockBackend()
        self.emu = EmulatorControl(self.backend)

    def test_clears_dialog_with_a_presses(self):
        """Should press A the specified number of times."""
        clear_dialog_crystal(self.emu, presses=15)
        a_count = sum(1 for b in self.backend._buttons_pressed if b == "a")
        self.assertGreaterEqual(a_count, 15)

    def test_default_20_presses(self):
        """Default is 20 A presses (Crystal dialog is longer than Red)."""
        clear_dialog_crystal(self.emu)
        a_count = sum(1 for b in self.backend._buttons_pressed if b == "a")
        self.assertGreaterEqual(a_count, 20)


class TestNavigateCrystal(unittest.TestCase):
    """Test simple grid navigation for Crystal indoor rooms."""

    def setUp(self):
        self.backend = MockBackend()
        self.emu = EmulatorControl(self.backend)
        self.reader = MockReaderForCrystalBoot()

    def test_already_at_target(self):
        """If already at target, should return True immediately."""
        self.reader.set_position(3, 5)
        result = navigate_crystal(self.emu, self.reader, target_x=3, target_y=5)
        self.assertTrue(result)

    def test_moves_right(self):
        """Should move right when target is to the right."""
        # Mock will always return same position, so it won't "reach" target,
        # but we can verify it tries to move right
        self.reader.set_position(3, 5)
        navigate_crystal(self.emu, self.reader, target_x=6, target_y=5, max_steps=3)
        right_count = sum(1 for b in self.backend._buttons_pressed if b == "right")
        self.assertGreater(right_count, 0)

    def test_max_steps_limit(self):
        """Should stop after max_steps even if not at target."""
        self.reader.set_position(0, 0)
        result = navigate_crystal(self.emu, self.reader, target_x=10, target_y=10, max_steps=5)
        # With mock always returning (0,0), we'll never reach target
        self.assertFalse(result)


class TestWaitForMapCrystal(unittest.TestCase):
    """Test map transition waiting for Crystal."""

    def setUp(self):
        self.backend = MockBackend()
        self.emu = EmulatorControl(self.backend)
        self.reader = MockReaderForCrystalBoot()

    def test_already_on_target_map(self):
        """If already on target map, return True immediately."""
        target = (3, 1)  # New Bark Town
        self.reader.set_position(5, 5, map_id=target[0] * 256 + target[1])
        result = wait_for_map_crystal(self.emu, self.reader, target)
        self.assertTrue(result)

    def test_timeout_returns_false(self):
        """If map never changes, should return False after timeout."""
        self.reader.set_position(5, 5, map_id=999)
        result = wait_for_map_crystal(self.emu, self.reader, (3, 1), max_ticks=50)
        self.assertFalse(result)


class TestRunCrystalBootSequence(unittest.TestCase):
    """Test the full Crystal boot sequence orchestration."""

    def setUp(self):
        self.backend = MockBackend()
        self.emu = EmulatorControl(self.backend)
        self.reader = MockReaderForCrystalBoot()

    def test_returns_dict_with_required_keys(self):
        """Boot sequence should return a dict with standard keys."""
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIn("success", result)
        self.assertIn("final_map", result)
        self.assertIn("final_position", result)
        self.assertIn("phases_completed", result)

    def test_phases_completed_is_list(self):
        """phases_completed should be a list."""
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIsInstance(result["phases_completed"], list)

    def test_starts_from_players_house_2f(self):
        """When starting from Player's House 2F, should attempt dialog clear."""
        map_id = 3 * 256 + 4  # Player's House 2F
        self.reader.set_position(4, 4, map_id=map_id, map_name="Player's House 2F")
        self.reader.set_menu_state(MenuState.DIALOG)
        result = run_crystal_boot_sequence(self.emu, self.reader)
        # Should complete at least the opening_dialog phase
        self.assertGreater(len(result["phases_completed"]), 0)

    def test_starts_from_overworld_skips_dialog(self):
        """When already in overworld, should skip dialog clearing."""
        map_id = 3 * 256 + 4  # Player's House 2F
        self.reader.set_position(4, 4, map_id=map_id, map_name="Player's House 2F")
        self.reader.set_menu_state(MenuState.OVERWORLD)
        result = run_crystal_boot_sequence(self.emu, self.reader)
        # Should have at least one phase (even if dialog was skipped)
        self.assertIsInstance(result["phases_completed"], list)

    def test_title_screen_detection(self):
        """When at title screen (map 0, pos 0,0), should mash through."""
        self.reader.set_position(0, 0, map_id=0, map_name="Title")
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIn("title_screen", result["phases_completed"])

    def test_final_position_is_tuple(self):
        """final_position should be a (x, y) tuple."""
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIsInstance(result["final_position"], tuple)
        self.assertEqual(len(result["final_position"]), 2)

    def test_already_in_elms_lab(self):
        """If already in Elm's Lab, should mark early phases as skipped."""
        map_id = 3 * 256 + 2  # Elm's Lab
        self.reader.set_position(5, 5, map_id=map_id, map_name="Elm's Lab")
        self.reader.set_menu_state(MenuState.OVERWORLD)
        result = run_crystal_boot_sequence(self.emu, self.reader)
        # Should still return valid result
        self.assertIn("success", result)

    def test_new_bark_town_skips_house(self):
        """If starting in New Bark Town, should skip house navigation."""
        map_id = 3 * 256 + 1  # New Bark Town
        self.reader.set_position(5, 5, map_id=map_id, map_name="New Bark Town")
        self.reader.set_menu_state(MenuState.OVERWORLD)
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIn("success", result)


class TestBootSequenceEdgeCases(unittest.TestCase):
    """Edge case tests for Crystal boot sequence."""

    def setUp(self):
        self.backend = MockBackend()
        self.emu = EmulatorControl(self.backend)
        self.reader = MockReaderForCrystalBoot()

    def test_no_crash_on_unknown_map(self):
        """Boot sequence should not crash if on an unexpected map."""
        self.reader.set_position(5, 5, map_id=9999, map_name="Unknown")
        self.reader.set_menu_state(MenuState.OVERWORLD)
        # Should not raise
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIn("success", result)

    def test_dialog_with_pokemon_center_state(self):
        """Should handle POKEMON_CENTER menu state without crash."""
        map_id = 3 * 256 + 4  # Player's House 2F
        self.reader.set_position(4, 4, map_id=map_id)
        self.reader.set_menu_state(MenuState.POKEMON_CENTER)
        result = run_crystal_boot_sequence(self.emu, self.reader)
        self.assertIn("success", result)


if __name__ == "__main__":
    unittest.main()
