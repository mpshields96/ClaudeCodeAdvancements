"""Tests for emulator_control.py — Pokemon emulator abstraction layer."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import (
    BUTTONS,
    DIRECTIONS,
    EmulatorControl,
    InputSequence,
    MockBackend,
)


class TestMockBackend(unittest.TestCase):
    """Test the mock backend directly."""

    def test_press_valid_button(self):
        mock = MockBackend()
        mock.press("a")
        self.assertEqual(mock.button_history, ["a"])

    def test_press_invalid_button(self):
        mock = MockBackend()
        with self.assertRaises(ValueError):
            mock.press("x")

    def test_tick_advances_frames(self):
        mock = MockBackend()
        mock.tick(60)
        self.assertEqual(mock.frames, 60)

    def test_read_write_byte(self):
        mock = MockBackend()
        mock.write_byte(0x1234, 0xAB)
        self.assertEqual(mock.read_byte(0x1234), 0xAB)

    def test_write_byte_masks_to_8bit(self):
        mock = MockBackend()
        mock.write_byte(0x100, 0x1FF)
        self.assertEqual(mock.read_byte(0x100), 0xFF)

    def test_read_bytes(self):
        mock = MockBackend()
        mock.write_byte(0x10, 0x01)
        mock.write_byte(0x11, 0x02)
        mock.write_byte(0x12, 0x03)
        self.assertEqual(mock.read_bytes(0x10, 3), b"\x01\x02\x03")

    def test_save_load_state(self):
        mock = MockBackend()
        mock.write_byte(0x100, 42)
        mock.save_state("test_state")
        mock.write_byte(0x100, 99)
        self.assertEqual(mock.read_byte(0x100), 99)
        mock.load_state("test_state")
        self.assertEqual(mock.read_byte(0x100), 42)

    def test_load_nonexistent_state(self):
        mock = MockBackend()
        with self.assertRaises(FileNotFoundError):
            mock.load_state("does_not_exist")

    def test_screenshot(self):
        mock = MockBackend()
        mock.screenshot("/tmp/test.png")
        self.assertEqual(mock._screenshots, ["/tmp/test.png"])

    def test_close(self):
        mock = MockBackend()
        self.assertFalse(mock.is_closed)
        mock.close()
        self.assertTrue(mock.is_closed)

    def test_release_valid_button(self):
        mock = MockBackend()
        mock.release("a")  # should not raise

    def test_release_invalid_button(self):
        mock = MockBackend()
        with self.assertRaises(ValueError):
            mock.release("x")


class TestEmulatorControlBasic(unittest.TestCase):
    """Test EmulatorControl with mock backend."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def tearDown(self):
        self.emu.close()

    def test_mock_creation(self):
        self.assertIsInstance(self.emu._backend, MockBackend)

    def test_press_button(self):
        self.emu.press("a")
        mock = self.emu._backend
        self.assertIn("a", mock.button_history)

    def test_press_with_timing(self):
        self.emu.press("a", hold_frames=4, wait_frames=8)
        mock = self.emu._backend
        # 4 hold + 8 wait = 12 frames
        self.assertEqual(mock.frames, 12)

    def test_tick(self):
        self.emu.tick(30)
        self.assertEqual(self.emu._backend.frames, 30)

    def test_wait_seconds(self):
        self.emu.wait(1.0)
        self.assertEqual(self.emu._backend.frames, 60)

    def test_wait_half_second(self):
        self.emu.wait(0.5)
        self.assertEqual(self.emu._backend.frames, 30)


class TestEmulatorControlMovement(unittest.TestCase):
    """Test movement operations."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def tearDown(self):
        self.emu.close()

    def test_move_up(self):
        self.emu.move("up", steps=3)
        mock = self.emu._backend
        up_presses = [b for b in mock.button_history if b == "up"]
        self.assertEqual(len(up_presses), 3)

    def test_move_invalid_direction(self):
        with self.assertRaises(ValueError):
            self.emu.move("diagonal")

    def test_move_path(self):
        self.emu.move_path([("right", 2), ("up", 1)])
        mock = self.emu._backend
        rights = [b for b in mock.button_history if b == "right"]
        ups = [b for b in mock.button_history if b == "up"]
        self.assertEqual(len(rights), 2)
        self.assertEqual(len(ups), 1)

    def test_all_directions_valid(self):
        for d in DIRECTIONS:
            self.emu.move(d, steps=1)


class TestEmulatorControlMenus(unittest.TestCase):
    """Test menu and text operations."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def tearDown(self):
        self.emu.close()

    def test_mash_a(self):
        self.emu.mash_a(times=5)
        mock = self.emu._backend
        a_presses = [b for b in mock.button_history if b == "a"]
        self.assertEqual(len(a_presses), 5)

    def test_mash_b(self):
        self.emu.mash_b(times=3)
        mock = self.emu._backend
        b_presses = [b for b in mock.button_history if b == "b"]
        self.assertEqual(len(b_presses), 3)

    def test_advance_text(self):
        self.emu.advance_text(presses=10)
        mock = self.emu._backend
        a_presses = [b for b in mock.button_history if b == "a"]
        self.assertEqual(len(a_presses), 10)

    def test_open_menu(self):
        self.emu.open_menu()
        mock = self.emu._backend
        self.assertIn("start", mock.button_history)

    def test_close_menu(self):
        self.emu.close_menu()
        mock = self.emu._backend
        b_presses = [b for b in mock.button_history if b == "b"]
        self.assertEqual(len(b_presses), 3)


class TestEmulatorControlRAM(unittest.TestCase):
    """Test RAM read/write operations."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def tearDown(self):
        self.emu.close()

    def test_read_byte(self):
        self.emu._backend.write_byte(0xD163, 0x05)
        self.assertEqual(self.emu.read_byte(0xD163), 0x05)

    def test_read_bytes(self):
        for i, v in enumerate([0x10, 0x20, 0x30]):
            self.emu._backend.write_byte(0xD100 + i, v)
        self.assertEqual(self.emu.read_bytes(0xD100, 3), b"\x10\x20\x30")

    def test_read_word_little_endian(self):
        self.emu._backend.write_byte(0x100, 0x34)  # low byte
        self.emu._backend.write_byte(0x101, 0x12)  # high byte
        self.assertEqual(self.emu.read_word(0x100), 0x1234)

    def test_read_word_big_endian(self):
        self.emu._backend.write_byte(0x100, 0x12)  # high byte
        self.emu._backend.write_byte(0x101, 0x34)  # low byte
        self.assertEqual(self.emu.read_word_be(0x100), 0x1234)

    def test_write_byte(self):
        self.emu.write_byte(0x200, 0xFF)
        self.assertEqual(self.emu.read_byte(0x200), 0xFF)


class TestEmulatorControlState(unittest.TestCase):
    """Test state management."""

    def setUp(self):
        self.emu = EmulatorControl.mock()

    def tearDown(self):
        self.emu.close()

    def test_save_and_load_state(self):
        self.emu.write_byte(0x100, 42)
        self.emu.save_state("checkpoint")
        self.emu.write_byte(0x100, 99)
        self.emu.load_state("checkpoint")
        self.assertEqual(self.emu.read_byte(0x100), 42)

    def test_state_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.emu.set_state_dir(td)
            path = self.emu._state_path("test")
            self.assertTrue(path.startswith(td))
            self.assertTrue(path.endswith(".state"))

    def test_screenshot_path(self):
        with tempfile.TemporaryDirectory() as td:
            self.emu.set_state_dir(td)
            path = self.emu._state_path("screen", ext=".png")
            self.assertTrue(path.endswith(".png"))


class TestInputSequence(unittest.TestCase):
    """Test InputSequence helper."""

    def test_from_list(self):
        seq = InputSequence.from_list(["a", "b", "a"])
        self.assertEqual(len(seq.steps), 3)
        self.assertEqual(seq.steps[0], ("a", 4, 8))

    def test_custom_timing(self):
        seq = InputSequence.from_list(["a"], hold=10, wait=20)
        self.assertEqual(seq.steps[0], ("a", 10, 20))

    def test_run_sequence(self):
        emu = EmulatorControl.mock()
        seq = InputSequence.from_list(["a", "b", "start"])
        emu.run_sequence(seq)
        mock = emu._backend
        self.assertEqual(mock.button_history, ["a", "b", "start"])
        emu.close()

    def test_press_many(self):
        emu = EmulatorControl.mock()
        emu.press_many(["up", "up", "a"])
        mock = emu._backend
        self.assertEqual(mock.button_history, ["up", "up", "a"])
        emu.close()


class TestContextManager(unittest.TestCase):
    """Test context manager protocol."""

    def test_with_statement(self):
        with EmulatorControl.mock() as emu:
            emu.press("a")
            self.assertIn("a", emu._backend.button_history)
        self.assertTrue(emu._backend.is_closed)


class TestLoadStatePaths(unittest.TestCase):
    """Test load_state handles both bare names and full paths."""

    def test_load_state_bare_name(self):
        """Bare name goes through _state_path (existing behavior)."""
        emu = EmulatorControl.mock()
        emu.write_byte(0x100, 42)
        emu.save_state("test_bare")
        emu.write_byte(0x100, 0)
        emu.load_state("test_bare")
        self.assertEqual(emu.read_byte(0x100), 42)
        emu.close()

    def test_load_state_with_extension(self):
        """Name ending in .state is used directly (no double extension)."""
        emu = EmulatorControl.mock()
        with tempfile.TemporaryDirectory() as td:
            emu.set_state_dir(td)
            # Save normally
            emu.write_byte(0x100, 77)
            path = emu.save_state("direct_test")
            # Load via full path with .state extension
            emu.write_byte(0x100, 0)
            emu.load_state(path)  # e.g. "/tmp/xxx/direct_test.state"
            self.assertEqual(emu.read_byte(0x100), 77)
        emu.close()

    def test_load_state_with_separator(self):
        """Path with directory separator is used directly."""
        emu = EmulatorControl.mock()
        with tempfile.TemporaryDirectory() as td:
            emu.set_state_dir(td)
            emu.write_byte(0x100, 55)
            path = emu.save_state("sep_test")
            emu.write_byte(0x100, 0)
            # Pass path that contains os.sep
            emu.load_state(path)
            self.assertEqual(emu.read_byte(0x100), 55)
        emu.close()


class TestConstants(unittest.TestCase):
    """Test module-level constants."""

    def test_all_buttons_defined(self):
        expected = {"a", "b", "start", "select", "up", "down", "left", "right"}
        self.assertEqual(set(BUTTONS.keys()), expected)

    def test_directions_subset_of_buttons(self):
        self.assertTrue(DIRECTIONS.issubset(set(BUTTONS.keys())))


if __name__ == "__main__":
    unittest.main()
