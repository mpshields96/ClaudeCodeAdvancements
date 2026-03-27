"""RAM text extraction for Pokemon Crystal.

Reads on-screen text (dialog boxes, menus, signs) directly from emulator
RAM. This gives the LLM text context alongside or instead of screenshots,
which is more reliable than OCR on pixel-art fonts.

Pokemon Crystal text locations (from pret/pokecrystal wram.asm):
- Text buffer: temporary buffer where text is composed before display
- Dialog lines: the visible text box area (2 lines, 18 chars each)
- Player/rival names: fixed RAM locations

Usage:
    from text_reader import TextReader
    reader = TextReader(emulator)
    if reader.is_text_active():
        lines = reader.read_dialog_lines()
        prompt_text = reader.format_for_prompt()

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import List

from emulator_control import EmulatorControl
from memory_reader import CHAR_MAP, WINDOW_STACK_SIZE, decode_text


class TextReader:
    """Reads text from Pokemon Crystal RAM."""

    # Text buffer — where text is composed before rendering to screen
    # Source: pret/pokecrystal wram.asm wStringBuffer1
    TEXT_BUFFER_START = 0xD073
    TEXT_BUFFER_MAX = 80

    # Dialog text box lines (visible on screen)
    # Crystal text box: 2 lines of 18 characters each
    # Source: pret/pokecrystal TileMap area for text box
    TEXT_LINE1_START = 0xC4E1  # Tilemap row for dialog line 1
    TEXT_LINE2_START = 0xC505  # Tilemap row for dialog line 2
    TEXT_LINE_LENGTH = 18

    # Player and rival names
    PLAYER_NAME_ADDR = 0xD47D  # 11 bytes (Pokemon text encoding)
    RIVAL_NAME_ADDR = 0xD493   # 11 bytes
    NAME_LENGTH = 11

    def __init__(self, emu: EmulatorControl):
        self._emu = emu

    def read_text_buffer(self, max_length: int = 0) -> str:
        """Read the text composition buffer.

        Returns decoded text, stripped of whitespace. Empty if no text.
        """
        length = max_length if max_length > 0 else self.TEXT_BUFFER_MAX
        data = self._emu.read_bytes(self.TEXT_BUFFER_START, length)

        # Check for all-zeros (empty buffer)
        if all(b == 0 for b in data):
            return ""

        return decode_text(data).strip()

    def read_dialog_lines(self) -> List[str]:
        """Read the visible dialog box text (2 lines).

        Returns a list of non-empty lines currently displayed.
        Dialog uses tilemap encoding — tiles 0x60-0xBA map to text chars.
        """
        lines = []

        for start_addr in (self.TEXT_LINE1_START, self.TEXT_LINE2_START):
            data = self._emu.read_bytes(start_addr, self.TEXT_LINE_LENGTH)

            # Tilemap text uses the same encoding as text buffer
            # but tiles < 0x60 are typically blank/graphics
            text = decode_text(data).strip()
            if text and text != "?" * len(text):
                lines.append(text)

        return lines

    def is_text_active(self) -> bool:
        """Check if a text box is currently displayed.

        Uses the window stack size flag — non-zero when text/menu is open.
        Also checks that the text buffer has actual content.
        """
        window_stack = self._emu.read_byte(WINDOW_STACK_SIZE)
        if window_stack == 0:
            return False

        # Verify there's actual text content
        data = self._emu.read_bytes(self.TEXT_BUFFER_START, 4)
        has_content = any(b != 0 and b != 0x50 for b in data)

        # Also check dialog lines
        if not has_content:
            lines = self.read_dialog_lines()
            has_content = len(lines) > 0

        return has_content

    def read_player_name(self) -> str:
        """Read the player's name from RAM."""
        data = self._emu.read_bytes(self.PLAYER_NAME_ADDR, self.NAME_LENGTH)
        return decode_text(data).strip()

    def read_rival_name(self) -> str:
        """Read the rival's name from RAM."""
        data = self._emu.read_bytes(self.RIVAL_NAME_ADDR, self.NAME_LENGTH)
        return decode_text(data).strip()

    def format_for_prompt(self) -> str:
        """Format current text state for inclusion in the LLM prompt.

        Returns empty string if no text is active. Otherwise returns
        a labeled block with dialog lines and/or buffer text.
        """
        if not self.is_text_active():
            return ""

        parts = []

        # Dialog lines (most useful — what the player sees)
        lines = self.read_dialog_lines()
        if lines:
            parts.append("TEXT BOX: " + " / ".join(lines))

        # Buffer text (fallback — may have more context)
        buf = self.read_text_buffer()
        if buf and buf not in " / ".join(lines):
            parts.append("TEXT BUFFER: " + buf)

        return " | ".join(parts) if parts else ""
