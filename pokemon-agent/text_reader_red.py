"""Pokemon Red text reader — reads dialog from tilemap buffer.

Reads on-screen text (dialog boxes, menus, signs) directly from emulator
RAM tilemap buffer. Gives the LLM text context alongside screenshots.

Pokemon Red tilemap buffer: 0xC3A0-0xC507 (271 bytes).
Text is rendered as tile indices. Border chars (0x7C) delimit lines.
Double borders mark line breaks. 10+ consecutive spaces end a line.

RAM addresses from pret/pokered wram.asm and ClaudePlaysPokemonStarter.

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import List

from emulator_control import EmulatorControl
from memory_reader_red import decode_text

# ── RAM addresses ───────────────────────────────────────────────────────────

TILEMAP_START = 0xC3A0
TILEMAP_END = 0xC507
TILEMAP_SIZE = TILEMAP_END - TILEMAP_START  # 359 bytes

JOY_DISABLED_ADDR = 0xD730   # bit 5 = joypad disabled (dialog active)
PLAYER_NAME_ADDR = 0xD158    # 11 bytes (0x50 terminated)
RIVAL_NAME_ADDR = 0xD34A     # 7 bytes (0x50 terminated)
NAME_MAX_LENGTH = 11

# Border character — used as line delimiter in dialog boxes
BORDER_CHAR = 0x7C
SPACE_CHAR = 0x7F
SPACE_THRESHOLD = 10  # 10+ consecutive spaces = end of line


def _is_text_char(b: int) -> bool:
    """Check if a byte is a printable text character in Gen 1 encoding."""
    return (
        (0x80 <= b <= 0x99)       # Uppercase A-Z
        or (0x9A <= b <= 0x9F)    # Punctuation
        or (0xA0 <= b <= 0xB9)    # Lowercase a-z
        or (0xBA <= b <= 0xBF)    # Contractions (e.g., 'd, 'l, 's, 't, 'v)
        or (0xE0 <= b <= 0xEF)    # Special chars (', -, ?, !, ., etc.)
        or (0xF0 <= b <= 0xF5)    # Symbols (¥, ×, /, ,, ♀, ♂)
        or (0xF6 <= b <= 0xFF)    # Numbers 0-9
        or b == 0x4E              # Line break
        or b == SPACE_CHAR        # Space
    )


class TextReaderRed:
    """Reads text from Pokemon Red RAM tilemap buffer."""

    def __init__(self, emu: EmulatorControl):
        self._emu = emu

    def read_dialog_lines(self) -> List[str]:
        """Read dialog text from the tilemap buffer.

        Scans the tilemap buffer (0xC3A0-0xC507) for text characters.
        Uses border chars (0x7C) as line delimiters and 10+ spaces as
        line breaks. Returns a list of non-empty text lines.
        """
        raw = self._emu.read_bytes(TILEMAP_START, TILEMAP_SIZE)

        lines: List[str] = []
        current_line: List[int] = []
        space_count = 0
        last_was_border = False

        for b in raw:
            if b == BORDER_CHAR:
                if last_was_border:
                    # Double border = line break
                    text = decode_text(bytes(current_line)).strip()
                    if text:
                        lines.append(text)
                    current_line = []
                    space_count = 0
                last_was_border = True
            elif b == SPACE_CHAR:
                space_count += 1
                current_line.append(b)
                last_was_border = False
            elif _is_text_char(b):
                space_count = 0
                current_line.append(b)
                last_was_border = (0x79 <= b <= 0x7E)
            else:
                last_was_border = False

            # Long space run = end of line
            if space_count > SPACE_THRESHOLD and current_line:
                text = decode_text(bytes(current_line)).strip()
                if text:
                    lines.append(text)
                current_line = []
                space_count = 0
                last_was_border = False

        # Flush remaining
        if current_line:
            text = decode_text(bytes(current_line)).strip()
            if text:
                lines.append(text)

        return lines

    def is_text_active(self) -> bool:
        """Check if a dialog box is currently displayed.

        Uses the JOY_DISABLED flag (bit 5 of 0xD730) — set when the game
        disables joypad input during dialog/text display.
        """
        joy_flags = self._emu.read_byte(JOY_DISABLED_ADDR)
        if not (joy_flags & 0x20):
            return False

        # Verify there's actual text content in the tilemap
        sample = self._emu.read_bytes(TILEMAP_START, 20)
        return any(_is_text_char(b) and b != SPACE_CHAR for b in sample)

    def format_for_prompt(self) -> str:
        """Format current dialog text for LLM prompt.

        Returns empty string if no dialog is active.
        """
        lines = self.read_dialog_lines()
        if not lines:
            return ""

        return "[DIALOG]\n" + "\n".join(lines)

    def read_player_name(self) -> str:
        """Read the player's name from RAM."""
        data = self._emu.read_bytes(PLAYER_NAME_ADDR, NAME_MAX_LENGTH)
        return decode_text(data)

    def read_rival_name(self) -> str:
        """Read the rival's name from RAM."""
        data = self._emu.read_bytes(RIVAL_NAME_ADDR, NAME_MAX_LENGTH)
        return decode_text(data)
