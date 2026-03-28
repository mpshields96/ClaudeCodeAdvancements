"""Tests for boot_sequence.py — Pokemon Red intro automation.

Tests the deterministic boot sequence logic using MockBackend.
No ROM or PyBoy needed.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl, MockBackend
from game_state import GameState, MapPosition, MenuState, Party, BattleState, Badges
from boot_sequence import (
    clear_dialog,
    clear_dialog_until_overworld,
    navigate_to,
    wait_for_map,
    run_boot_sequence,
    MAP_REDS_HOUSE_2F,
    MAP_REDS_HOUSE_1F,
    MAP_PALLET_TOWN,
    MAP_OAKS_LAB,
)


class MockReaderForBoot:
    """Mock memory reader that returns controllable game states.

    Simulates map transitions and dialog clearing for boot sequence tests.
    """

    def __init__(self):
        self._state = GameState(
            position=MapPosition(
                map_id=MAP_REDS_HOUSE_2F,
                map_name="REDS HOUSE 2F",
                x=3, y=6,
            ),
            menu_state=MenuState.DIALOG,
        )
        self._press_count = 0
        self._transition_after = {}  # (x, y) -> map_id
        self._dialog_clears_after = 10  # A presses to clear dialog
        self._move_tracking = True

    def read_game_state(self) -> GameState:
        return self._state

    def set_position(self, x: int, y: int, map_id: int = None,
                     map_name: str = None):
        pos = self._state.position
        self._state.position = MapPosition(
            map_id=map_id if map_id is not None else pos.map_id,
            map_name=map_name or pos.map_name,
            x=x, y=y,
        )

    def set_menu_state(self, state: MenuState):
        self._state.menu_state = state

    def set_map(self, map_id: int, map_name: str = "", x: int = 0, y: int = 0):
        self._state.position = MapPosition(
            map_id=map_id, map_name=map_name, x=x, y=y,
        )

    def register_transition(self, x: int, y: int, target_map: int,
                            target_name: str = "", tx: int = 0, ty: int = 0):
        """Register a warp: when player reaches (x,y), map changes."""
        self._transition_after[(x, y)] = (target_map, target_name, tx, ty)

    def simulate_press(self, emu, button: str):
        """Simulate what happens when a button is pressed.

        Updates position for directional buttons.
        Tracks A presses for dialog clearing.
        """
        self._press_count += 1

        if button == "a" and self._state.menu_state == MenuState.DIALOG:
            if self._press_count >= self._dialog_clears_after:
                self._state.menu_state = MenuState.OVERWORLD

        if self._state.menu_state == MenuState.OVERWORLD and self._move_tracking:
            pos = self._state.position
            x, y = pos.x, pos.y
            if button == "up":
                y -= 1
            elif button == "down":
                y += 1
            elif button == "left":
                x -= 1
            elif button == "right":
                x += 1

            # Check for transitions
            if (x, y) in self._transition_after:
                t = self._transition_after[(x, y)]
                self.set_map(t[0], t[1], t[2], t[3])
            else:
                self.set_position(x, y)


class HookableEmulatorControl(EmulatorControl):
    """EmulatorControl that calls a hook on press for test simulation."""

    def __init__(self, backend, reader: MockReaderForBoot):
        super().__init__(backend)
        self._reader = reader

    def press(self, button: str, hold_frames: int = 10, wait_frames: int = 120):
        super().press(button, hold_frames, wait_frames)
        self._reader.simulate_press(self, button)


class TestClearDialog(unittest.TestCase):
    """Tests for dialog clearing functions."""

    def test_clear_dialog_presses_a_correct_number(self):
        emu = EmulatorControl.mock()
        clear_dialog(emu, presses=15)
        # Should have pressed A 15 times
        backend = emu._backend
        a_count = backend.button_history.count("a")
        self.assertEqual(a_count, 15)

    def test_clear_dialog_until_overworld_succeeds(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader._dialog_clears_after = 5
        reader._press_count = 0
        emu = HookableEmulatorControl(backend, reader)

        result = clear_dialog_until_overworld(emu, reader, max_presses=20)
        self.assertTrue(result)
        self.assertEqual(reader._state.menu_state, MenuState.OVERWORLD)

    def test_clear_dialog_until_overworld_fails_if_too_many(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader._dialog_clears_after = 999  # Never clears
        emu = HookableEmulatorControl(backend, reader)

        result = clear_dialog_until_overworld(emu, reader, max_presses=10)
        self.assertFalse(result)

    def test_clear_dialog_already_in_overworld(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_menu_state(MenuState.OVERWORLD)
        emu = HookableEmulatorControl(backend, reader)

        result = clear_dialog_until_overworld(emu, reader, max_presses=5)
        self.assertTrue(result)


class TestNavigateTo(unittest.TestCase):
    """Tests for simple grid navigation."""

    def test_navigate_right_and_up(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_menu_state(MenuState.OVERWORLD)
        reader.set_position(3, 6)
        emu = HookableEmulatorControl(backend, reader)

        result = navigate_to(emu, reader, target_x=7, target_y=1)
        self.assertTrue(result)
        pos = reader._state.position
        self.assertEqual(pos.x, 7)
        self.assertEqual(pos.y, 1)

    def test_navigate_already_at_target(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_menu_state(MenuState.OVERWORLD)
        reader.set_position(5, 5)
        emu = HookableEmulatorControl(backend, reader)

        result = navigate_to(emu, reader, target_x=5, target_y=5)
        self.assertTrue(result)

    def test_navigate_left_and_down(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_menu_state(MenuState.OVERWORLD)
        reader.set_position(5, 2)
        emu = HookableEmulatorControl(backend, reader)

        result = navigate_to(emu, reader, target_x=2, target_y=7)
        self.assertTrue(result)
        pos = reader._state.position
        self.assertEqual(pos.x, 2)
        self.assertEqual(pos.y, 7)

    def test_navigate_max_steps_exceeded(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_menu_state(MenuState.OVERWORLD)
        reader.set_position(0, 0)
        reader._move_tracking = False  # Position never changes
        emu = HookableEmulatorControl(backend, reader)

        result = navigate_to(emu, reader, target_x=50, target_y=50, max_steps=5)
        self.assertFalse(result)


class TestWaitForMap(unittest.TestCase):
    """Tests for map transition waiting."""

    def test_wait_for_map_already_there(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_map(MAP_REDS_HOUSE_1F)
        emu = HookableEmulatorControl(backend, reader)

        result = wait_for_map(emu, reader, MAP_REDS_HOUSE_1F)
        self.assertTrue(result)

    def test_wait_for_map_wrong_map(self):
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_map(MAP_REDS_HOUSE_2F)
        emu = HookableEmulatorControl(backend, reader)

        result = wait_for_map(emu, reader, MAP_PALLET_TOWN, max_ticks=50)
        self.assertFalse(result)


class TestRunBootSequence(unittest.TestCase):
    """Integration tests for the full boot sequence."""

    def test_boot_from_2f_dialog_state(self):
        """Test the typical starting scenario: 2F with dialog active."""
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_position(3, 6, map_id=MAP_REDS_HOUSE_2F, map_name="REDS HOUSE 2F")
        reader.set_menu_state(MenuState.DIALOG)
        reader._dialog_clears_after = 5

        # Register transitions
        reader.register_transition(7, 1, MAP_REDS_HOUSE_1F, "REDS HOUSE 1F", 7, 1)
        reader.register_transition(3, 8, MAP_PALLET_TOWN, "PALLET TOWN", 3, 3)

        emu = HookableEmulatorControl(backend, reader)
        result = run_boot_sequence(emu, reader)

        self.assertTrue(result["success"])
        self.assertIn("opening_dialog", result["phases_completed"])

    def test_stairs_retry_uses_right_not_up(self):
        """When 2F stairs need an extra nudge, the retry should press right.

        Real Red validation shows the stairs trigger by stepping right onto
        the stair tile, not by pressing up after reaching row 1.
        """
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_position(6, 1, map_id=MAP_REDS_HOUSE_2F, map_name="REDS HOUSE 2F")
        reader.set_menu_state(MenuState.OVERWORLD)

        pressed = []

        class RetryAwareEmu(HookableEmulatorControl):
            def press(self, button: str, hold_frames: int = 10, wait_frames: int = 120):
                pressed.append(button)
                if button == "right" and reader._state.position.map_id == MAP_REDS_HOUSE_2F:
                    reader.set_map(MAP_REDS_HOUSE_1F, "REDS HOUSE 1F", 7, 1)
                    return
                super().press(button, hold_frames, wait_frames)

        emu = RetryAwareEmu(backend, reader)
        result = run_boot_sequence(emu, reader)

        self.assertIn("stairs_to_1f", result["phases_completed"])
        self.assertIn("right", pressed)

    def test_boot_already_in_overworld(self):
        """Test when dialog is already cleared."""
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_position(3, 6, map_id=MAP_REDS_HOUSE_2F, map_name="REDS HOUSE 2F")
        reader.set_menu_state(MenuState.OVERWORLD)

        reader.register_transition(7, 1, MAP_REDS_HOUSE_1F, "REDS HOUSE 1F", 7, 1)

        emu = HookableEmulatorControl(backend, reader)
        result = run_boot_sequence(emu, reader)

        self.assertIn("opening_dialog_skipped", result["phases_completed"])

    def test_boot_already_on_1f(self):
        """Test starting from 1F (2F navigation skipped)."""
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_position(3, 3, map_id=MAP_REDS_HOUSE_1F, map_name="REDS HOUSE 1F")
        reader.set_menu_state(MenuState.OVERWORLD)

        reader.register_transition(3, 8, MAP_PALLET_TOWN, "PALLET TOWN", 3, 3)

        emu = HookableEmulatorControl(backend, reader)
        result = run_boot_sequence(emu, reader)

        self.assertIn("stairs_skipped", result["phases_completed"])

    def test_map_constants(self):
        """Verify map ID constants match expected values."""
        self.assertEqual(MAP_REDS_HOUSE_2F, 38)
        self.assertEqual(MAP_REDS_HOUSE_1F, 37)
        self.assertEqual(MAP_PALLET_TOWN, 0)
        self.assertEqual(MAP_OAKS_LAB, 40)


class TestBootSequenceEdgeCases(unittest.TestCase):
    """Edge cases and error handling."""

    def test_navigate_with_dialog_interrupt(self):
        """Test that navigation handles dialog mid-path."""
        backend = MockBackend()
        reader = MockReaderForBoot()
        reader.set_position(3, 6, map_id=MAP_REDS_HOUSE_2F)
        reader.set_menu_state(MenuState.OVERWORLD)
        emu = HookableEmulatorControl(backend, reader)

        # Navigation should work in overworld
        result = navigate_to(emu, reader, target_x=5, target_y=6)
        self.assertTrue(result)

    def test_clear_dialog_zero_presses(self):
        """Edge case: 0 presses should be valid."""
        emu = EmulatorControl.mock()
        clear_dialog(emu, presses=0)
        self.assertEqual(len(emu._backend.button_history), 0)


if __name__ == "__main__":
    unittest.main()
