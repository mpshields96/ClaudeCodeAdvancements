"""Tests for Pokemon Red text reader."""
import unittest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))


class TestTextReaderRed(unittest.TestCase):
    """Test TextReaderRed reads dialog from tilemap buffer."""

    def _make_reader(self, memory_bytes=None):
        """Create a TextReaderRed with a mock emulator."""
        from text_reader_red import TextReaderRed

        emu = MagicMock()
        if memory_bytes is None:
            memory_bytes = {}

        def read_byte(addr):
            return memory_bytes.get(addr, 0)

        def read_bytes(addr, length):
            return bytes(memory_bytes.get(addr + i, 0) for i in range(length))

        emu.read_byte = read_byte
        emu.read_bytes = read_bytes
        return TextReaderRed(emu)

    # ── Dialog line reading ─────────────────────────────────────────────

    def test_empty_buffer_returns_empty(self):
        """All zeros in tilemap → no text."""
        reader = self._make_reader({})
        lines = reader.read_dialog_lines()
        self.assertEqual(lines, [])

    def test_read_simple_text(self):
        """Uppercase text in tilemap buffer → decoded."""
        from text_reader_red import TILEMAP_START
        # "HELLO" = H(0x87) E(0x84) L(0x8B) L(0x8B) O(0x8E)
        mem = {}
        # Place a border char, then text, then border, then 10+ spaces
        mem[TILEMAP_START] = 0x7C  # border
        mem[TILEMAP_START + 1] = 0x87  # H
        mem[TILEMAP_START + 2] = 0x84  # E
        mem[TILEMAP_START + 3] = 0x8B  # L
        mem[TILEMAP_START + 4] = 0x8B  # L
        mem[TILEMAP_START + 5] = 0x8E  # O
        mem[TILEMAP_START + 6] = 0x7C  # border
        # Fill with spaces to trigger line end
        for i in range(7, 20):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        lines = reader.read_dialog_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "HELLO")

    def test_read_two_lines(self):
        """Two lines separated by border chars."""
        from text_reader_red import TILEMAP_START
        mem = {}
        offset = 0
        # Line 1: "OAK"
        mem[TILEMAP_START + offset] = 0x7C; offset += 1
        mem[TILEMAP_START + offset] = 0x8E; offset += 1  # O
        mem[TILEMAP_START + offset] = 0x80; offset += 1  # A
        mem[TILEMAP_START + offset] = 0x8A; offset += 1  # K
        mem[TILEMAP_START + offset] = 0x7C; offset += 1  # border (end of line)
        mem[TILEMAP_START + offset] = 0x7C; offset += 1  # double border = newline
        # Line 2: "HI"
        mem[TILEMAP_START + offset] = 0x87; offset += 1  # H
        mem[TILEMAP_START + offset] = 0x88; offset += 1  # I
        mem[TILEMAP_START + offset] = 0x7C; offset += 1  # border
        # Spaces to trigger end
        for i in range(offset, offset + 15):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        lines = reader.read_dialog_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "OAK")
        self.assertEqual(lines[1], "HI")

    def test_lowercase_text(self):
        """Lowercase chars decoded correctly."""
        from text_reader_red import TILEMAP_START
        mem = {}
        # "hello" = h(0xA7) e(0xA4) l(0xAB) l(0xAB) o(0xAE)
        mem[TILEMAP_START] = 0x7C
        mem[TILEMAP_START + 1] = 0xA7
        mem[TILEMAP_START + 2] = 0xA4
        mem[TILEMAP_START + 3] = 0xAB
        mem[TILEMAP_START + 4] = 0xAB
        mem[TILEMAP_START + 5] = 0xAE
        mem[TILEMAP_START + 6] = 0x7C
        for i in range(7, 20):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        lines = reader.read_dialog_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "hello")

    def test_numbers_decoded(self):
        """Numbers F6-FF decoded correctly."""
        from text_reader_red import TILEMAP_START
        mem = {}
        mem[TILEMAP_START] = 0x7C
        mem[TILEMAP_START + 1] = 0xF6  # 0
        mem[TILEMAP_START + 2] = 0xF7  # 1
        mem[TILEMAP_START + 3] = 0xFE  # 8
        mem[TILEMAP_START + 4] = 0xFF  # 9
        mem[TILEMAP_START + 5] = 0x7C
        for i in range(6, 20):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        lines = reader.read_dialog_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "0189")

    def test_special_chars(self):
        """Punctuation chars decoded."""
        from text_reader_red import TILEMAP_START
        mem = {}
        mem[TILEMAP_START] = 0x7C
        mem[TILEMAP_START + 1] = 0xE6  # ?
        mem[TILEMAP_START + 2] = 0xE7  # !
        mem[TILEMAP_START + 3] = 0xE8  # .
        mem[TILEMAP_START + 4] = 0x7C
        for i in range(5, 20):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        lines = reader.read_dialog_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "?!.")

    # ── is_text_active ──────────────────────────────────────────────────

    def test_text_active_when_joy_disabled(self):
        """Joy disabled bit 5 + text content → text active."""
        from text_reader_red import TILEMAP_START, JOY_DISABLED_ADDR
        mem = {}
        mem[JOY_DISABLED_ADDR] = 0x20  # bit 5 set
        # Some text in tilemap
        mem[TILEMAP_START] = 0x7C
        mem[TILEMAP_START + 1] = 0x87  # H
        mem[TILEMAP_START + 2] = 0x88  # I
        mem[TILEMAP_START + 3] = 0x7C
        reader = self._make_reader(mem)
        self.assertTrue(reader.is_text_active())

    def test_text_not_active_when_joy_enabled(self):
        """Joy enabled (bit 5 clear) → not active."""
        from text_reader_red import JOY_DISABLED_ADDR
        mem = {}
        mem[JOY_DISABLED_ADDR] = 0x00
        reader = self._make_reader(mem)
        self.assertFalse(reader.is_text_active())

    # ── format_for_prompt ───────────────────────────────────────────────

    def test_format_for_prompt_empty(self):
        """No text → empty string."""
        reader = self._make_reader({})
        self.assertEqual(reader.format_for_prompt(), "")

    def test_format_for_prompt_with_text(self):
        """Text present → formatted string."""
        from text_reader_red import TILEMAP_START, JOY_DISABLED_ADDR
        mem = {}
        mem[JOY_DISABLED_ADDR] = 0x20
        mem[TILEMAP_START] = 0x7C
        mem[TILEMAP_START + 1] = 0x87  # H
        mem[TILEMAP_START + 2] = 0x88  # I
        mem[TILEMAP_START + 3] = 0x7C
        for i in range(4, 18):
            mem[TILEMAP_START + i] = 0x7F
        reader = self._make_reader(mem)
        result = reader.format_for_prompt()
        self.assertIn("HI", result)

    # ── read_player_name / read_rival_name ──────────────────────────────

    def test_read_player_name(self):
        """Player name decoded from RAM."""
        from text_reader_red import PLAYER_NAME_ADDR
        mem = {}
        # "RED" = R(0x91) E(0x84) D(0x83) terminator(0x50)
        mem[PLAYER_NAME_ADDR] = 0x91
        mem[PLAYER_NAME_ADDR + 1] = 0x84
        mem[PLAYER_NAME_ADDR + 2] = 0x83
        mem[PLAYER_NAME_ADDR + 3] = 0x50
        reader = self._make_reader(mem)
        self.assertEqual(reader.read_player_name(), "RED")

    def test_read_rival_name(self):
        """Rival name decoded from RAM."""
        from text_reader_red import RIVAL_NAME_ADDR
        mem = {}
        # "BLUE" = B(0x81) L(0x8B) U(0x94) E(0x84) terminator(0x50)
        mem[RIVAL_NAME_ADDR] = 0x81
        mem[RIVAL_NAME_ADDR + 1] = 0x8B
        mem[RIVAL_NAME_ADDR + 2] = 0x94
        mem[RIVAL_NAME_ADDR + 3] = 0x84
        mem[RIVAL_NAME_ADDR + 4] = 0x50
        reader = self._make_reader(mem)
        self.assertEqual(reader.read_rival_name(), "BLUE")


if __name__ == "__main__":
    unittest.main()
