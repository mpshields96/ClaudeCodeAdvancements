"""Tests for RAM text extraction — reading on-screen text from emulator RAM.

Pokemon Crystal stores text in a tilemap buffer and a separate text buffer.
The text_reader module extracts readable text from these RAM locations so
the LLM gets text context alongside (or instead of) screenshots.

Uses MockBackend so no ROM/PyBoy needed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from memory_reader import CHAR_MAP
from text_reader import TextReader


class TestTextReader(unittest.TestCase):
    """Test RAM text extraction."""

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.reader = TextReader(self.emu)

    def _write_pokemon_text(self, addr, text):
        """Write a string in Pokemon text encoding to RAM."""
        reverse_map = {v: k for k, v in CHAR_MAP.items() if v != "\0"}
        for i, ch in enumerate(text):
            byte = reverse_map.get(ch, 0x7F)  # space for unknown
            self.emu.write_byte(addr + i, byte)
        # Write terminator
        self.emu.write_byte(addr + len(text), 0x50)

    def test_read_empty_text_buffer(self):
        """Empty RAM returns empty string."""
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "")

    def test_read_text_buffer_with_content(self):
        """Written text is read back correctly."""
        self._write_pokemon_text(self.reader.TEXT_BUFFER_START, "Hello")
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "Hello")

    def test_read_text_buffer_strips_whitespace(self):
        self._write_pokemon_text(self.reader.TEXT_BUFFER_START, "  Hi  ")
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "Hi")

    def test_read_text_with_numbers(self):
        self._write_pokemon_text(self.reader.TEXT_BUFFER_START, "Route 29")
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "Route 29")

    def test_read_text_with_special_chars(self):
        self._write_pokemon_text(self.reader.TEXT_BUFFER_START, "it's")
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "it's")

    def test_max_length_respected(self):
        """Text buffer read stops at max_length even without terminator."""
        # Fill 200 bytes with 'A' (no terminator)
        for i in range(200):
            self.emu.write_byte(self.reader.TEXT_BUFFER_START + i, 0x80)  # 'A'
        text = self.reader.read_text_buffer(max_length=50)
        self.assertEqual(len(text), 50)

    def test_read_dialog_lines(self):
        """Read multi-line dialog from the text box area."""
        # Line 1
        self._write_pokemon_text(self.reader.TEXT_LINE1_START, "PROF ELM")
        # Line 2
        self._write_pokemon_text(self.reader.TEXT_LINE2_START, "Go see MR")
        lines = self.reader.read_dialog_lines()
        self.assertGreaterEqual(len(lines), 1)
        self.assertIn("PROF ELM", lines[0])

    def test_dialog_lines_empty_when_no_text(self):
        lines = self.reader.read_dialog_lines()
        self.assertEqual(lines, [])

    def test_is_text_active_false_when_empty(self):
        self.assertFalse(self.reader.is_text_active())

    def test_is_text_active_true_with_content(self):
        self._write_pokemon_text(self.reader.TEXT_BUFFER_START, "Hello")
        # Also set the window stack to indicate text box is open
        from memory_reader import WINDOW_STACK_SIZE
        self.emu.write_byte(WINDOW_STACK_SIZE, 1)
        self.assertTrue(self.reader.is_text_active())

    def test_read_player_name(self):
        """Read player name from RAM."""
        self._write_pokemon_text(self.reader.PLAYER_NAME_ADDR, "GOLD")
        name = self.reader.read_player_name()
        self.assertEqual(name, "GOLD")

    def test_read_rival_name(self):
        self._write_pokemon_text(self.reader.RIVAL_NAME_ADDR, "SILVER")
        name = self.reader.read_rival_name()
        self.assertEqual(name, "SILVER")

    def test_format_for_prompt_empty(self):
        """No active text = empty prompt string."""
        result = self.reader.format_for_prompt()
        self.assertEqual(result, "")

    def test_format_for_prompt_with_dialog(self):
        """Active dialog produces a prompt-ready string."""
        from memory_reader import WINDOW_STACK_SIZE
        self.emu.write_byte(WINDOW_STACK_SIZE, 1)
        self._write_pokemon_text(self.reader.TEXT_LINE1_START, "Welcome")
        result = self.reader.format_for_prompt()
        self.assertIn("Welcome", result)
        self.assertIn("TEXT", result)  # Should have some label


class TestTextReaderEdgeCases(unittest.TestCase):
    """Edge cases for text reading."""

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.reader = TextReader(self.emu)

    def test_all_zeros_returns_empty(self):
        """All-zero RAM (fresh state) returns empty text."""
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "")

    def test_unmapped_bytes_become_question_marks(self):
        """Bytes not in CHAR_MAP become '?'."""
        self.emu.write_byte(self.reader.TEXT_BUFFER_START, 0x01)  # Not in CHAR_MAP
        self.emu.write_byte(self.reader.TEXT_BUFFER_START + 1, 0x50)  # Terminator
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "?")

    def test_terminator_at_start_returns_empty(self):
        self.emu.write_byte(self.reader.TEXT_BUFFER_START, 0x50)
        text = self.reader.read_text_buffer()
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
