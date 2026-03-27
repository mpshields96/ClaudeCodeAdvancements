"""Emulator control abstraction for Pokemon Crystal.

Provides a clean interface for button input, frame advance, and RAM reads.
Backend: PyBoy (Game Boy / Game Boy Color emulator, pip install pyboy).

The EmulatorControl class abstracts raw emulator operations so the decision
engine never touches PyBoy directly. This makes it possible to swap backends
(e.g., mGBA) or run in headless mode for testing.

Usage:
    from emulator_control import EmulatorControl

    emu = EmulatorControl("pokemon_crystal.gbc")
    emu.press("a")
    emu.tick(60)  # advance 60 frames (~1 second)
    value = emu.read_byte(0xD163)  # read RAM
    emu.save_state("before_gym")
    emu.close()

Stdlib + pyboy only. No other external dependencies.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol


# ── Button mapping ───────────────────────────────────────────────────────────

BUTTONS = {
    "a": "a",
    "b": "b",
    "start": "start",
    "select": "select",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}

# Direction shortcuts
DIRECTIONS = {"up", "down", "left", "right"}


# ── Emulator interface (protocol for swappable backends) ─────────────────────


class EmulatorBackend(Protocol):
    """Protocol for emulator backends. PyBoy is the default implementation."""

    def press(self, button: str) -> None: ...
    def release(self, button: str) -> None: ...
    def tick(self, frames: int) -> None: ...
    def read_byte(self, address: int) -> int: ...
    def read_bytes(self, address: int, length: int) -> bytes: ...
    def write_byte(self, address: int, value: int) -> None: ...
    def save_state(self, path: str) -> None: ...
    def load_state(self, path: str) -> None: ...
    def screenshot(self, path: str) -> None: ...
    def close(self) -> None: ...


# ── PyBoy backend ───────────────────────────────────────────────────────────


class PyBoyBackend:
    """PyBoy-based emulator backend for Game Boy / Game Boy Color."""

    def __init__(self, rom_path: str, headless: bool = False, speed: int = 0):
        """Initialize PyBoy with a ROM.

        Args:
            rom_path: Path to .gb or .gbc ROM file.
            headless: Run without display (for testing/CI).
            speed: 0 = uncapped, 1 = normal, N = Nx speed.
        """
        try:
            from pyboy import PyBoy
        except ImportError:
            raise ImportError(
                "PyBoy not installed. Run: pip install pyboy"
            )

        if not os.path.exists(rom_path):
            raise FileNotFoundError(f"ROM not found: {rom_path}")

        window = "null" if headless else "SDL2"
        self._pyboy = PyBoy(rom_path, window=window)
        if speed > 0:
            self._pyboy.set_emulation_speed(speed)
        else:
            self._pyboy.set_emulation_speed(0)  # uncapped

        self._button_map = {
            "a": "a",
            "b": "b",
            "start": "start",
            "select": "select",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
        }

    def press(self, button: str) -> None:
        btn = self._button_map.get(button.lower())
        if btn is None:
            raise ValueError(f"Unknown button: {button}")
        self._pyboy.button_press(btn)

    def release(self, button: str) -> None:
        btn = self._button_map.get(button.lower())
        if btn is None:
            raise ValueError(f"Unknown button: {button}")
        self._pyboy.button_release(btn)

    def tick(self, frames: int = 1) -> None:
        for _ in range(frames):
            self._pyboy.tick(count=1, render=True)

    def read_byte(self, address: int) -> int:
        return self._pyboy.memory[address]

    def read_bytes(self, address: int, length: int) -> bytes:
        return bytes(self._pyboy.memory[address + i] for i in range(length))

    def write_byte(self, address: int, value: int) -> None:
        self._pyboy.memory[address] = value

    def save_state(self, path: str) -> None:
        with open(path, "wb") as f:
            self._pyboy.save_state(f)

    def load_state(self, path: str) -> None:
        with open(path, "rb") as f:
            self._pyboy.load_state(f)

    def screenshot(self, path: str) -> None:
        self._pyboy.screen.image.save(path)

    def close(self) -> None:
        self._pyboy.stop()


# ── Mock backend (for testing without PyBoy/ROM) ────────────────────────────


class MockBackend:
    """In-memory mock backend for testing without a real emulator."""

    def __init__(self, ram_size: int = 0x10000):
        self._ram = bytearray(ram_size)
        self._frames_advanced = 0
        self._buttons_pressed: List[str] = []
        self._states: Dict[str, bytes] = {}
        self._screenshots: List[str] = []
        self._closed = False

    def press(self, button: str) -> None:
        if button.lower() not in BUTTONS:
            raise ValueError(f"Unknown button: {button}")
        self._buttons_pressed.append(button.lower())

    def release(self, button: str) -> None:
        if button.lower() not in BUTTONS:
            raise ValueError(f"Unknown button: {button}")

    def tick(self, frames: int = 1) -> None:
        self._frames_advanced += frames

    def read_byte(self, address: int) -> int:
        return self._ram[address]

    def read_bytes(self, address: int, length: int) -> bytes:
        return bytes(self._ram[address:address + length])

    def write_byte(self, address: int, value: int) -> None:
        self._ram[address] = value & 0xFF

    def save_state(self, path: str) -> None:
        self._states[path] = bytes(self._ram)

    def load_state(self, path: str) -> None:
        if path not in self._states:
            raise FileNotFoundError(f"No saved state: {path}")
        self._ram = bytearray(self._states[path])

    def screenshot(self, path: str) -> None:
        self._screenshots.append(path)

    def close(self) -> None:
        self._closed = True

    # Test helpers
    @property
    def frames(self) -> int:
        return self._frames_advanced

    @property
    def button_history(self) -> List[str]:
        return list(self._buttons_pressed)

    @property
    def is_closed(self) -> bool:
        return self._closed


# ── EmulatorControl (high-level API) ─────────────────────────────────────────


@dataclass
class InputSequence:
    """A sequence of button presses with timing."""
    steps: List[tuple]  # (button, hold_frames, wait_frames)

    @classmethod
    def from_list(cls, buttons: List[str], hold: int = 4, wait: int = 8) -> "InputSequence":
        """Create a sequence from a list of button names."""
        return cls(steps=[(b, hold, wait) for b in buttons])


class EmulatorControl:
    """High-level emulator control for Pokemon bot.

    Wraps a backend (PyBoy or Mock) with convenience methods for
    common Pokemon operations: menu navigation, text advancing,
    directional movement, and state management.
    """

    def __init__(self, backend: EmulatorBackend):
        self._backend = backend
        self._state_dir = ""

    @classmethod
    def from_rom(cls, rom_path: str, headless: bool = False, speed: int = 0) -> "EmulatorControl":
        """Create from a ROM file using PyBoy backend."""
        backend = PyBoyBackend(rom_path, headless=headless, speed=speed)
        return cls(backend)

    @classmethod
    def mock(cls, ram_size: int = 0x10000) -> "EmulatorControl":
        """Create with a mock backend for testing."""
        return cls(MockBackend(ram_size=ram_size))

    # ── Basic operations ──

    def press(self, button: str, hold_frames: int = 10, wait_frames: int = 120) -> None:
        """Press and release a button with timing.

        Args:
            button: Button name (a, b, start, select, up, down, left, right).
            hold_frames: Frames to hold the button (default 10 — matches
                ClaudePlaysPokemonStarter proven timing).
            wait_frames: Frames to wait after release (default 120 — critical
                for Pokemon Red/Crystal to process movement. The official
                starter uses 120. Values <120 cause missed inputs).
        """
        self._backend.press(button)
        self._backend.tick(hold_frames)
        self._backend.release(button)
        self._backend.tick(wait_frames)

    def tick(self, frames: int = 1) -> None:
        """Advance the emulator by N frames."""
        self._backend.tick(frames)

    def wait(self, seconds: float) -> None:
        """Wait by advancing frames (60 fps)."""
        self._backend.tick(int(seconds * 60))

    # ── Input sequences ──

    def run_sequence(self, seq: InputSequence) -> None:
        """Execute a sequence of button presses."""
        for button, hold, wait in seq.steps:
            self.press(button, hold_frames=hold, wait_frames=wait)

    def press_many(self, buttons: List[str], hold: int = 4, wait: int = 8) -> None:
        """Press multiple buttons in sequence."""
        self.run_sequence(InputSequence.from_list(buttons, hold, wait))

    # ── Common Pokemon operations ──

    def mash_a(self, times: int = 1, wait: int = 16) -> None:
        """Press A repeatedly (for advancing text, confirming dialogs)."""
        for _ in range(times):
            self.press("a", hold_frames=4, wait_frames=wait)

    def mash_b(self, times: int = 1, wait: int = 16) -> None:
        """Press B repeatedly (for canceling, exiting menus)."""
        for _ in range(times):
            self.press("b", hold_frames=4, wait_frames=wait)

    def advance_text(self, presses: int = 10) -> None:
        """Advance through text dialog by mashing A."""
        self.mash_a(times=presses, wait=20)

    def open_menu(self) -> None:
        """Open the start menu."""
        self.press("start")

    def close_menu(self) -> None:
        """Close any open menu."""
        self.mash_b(times=3)

    def move(self, direction: str, steps: int = 1) -> None:
        """Move in a direction for N steps.

        Each step = press direction + wait for movement animation.
        """
        if direction.lower() not in DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}")
        for _ in range(steps):
            self.press(direction.lower(), hold_frames=8, wait_frames=8)

    def move_path(self, path: List[tuple]) -> None:
        """Move along a path of (direction, steps) tuples.

        Example: [("right", 5), ("up", 3), ("left", 1)]
        """
        for direction, steps in path:
            self.move(direction, steps)

    # ── RAM access ──

    def read_byte(self, address: int) -> int:
        """Read a single byte from RAM."""
        return self._backend.read_byte(address)

    def read_bytes(self, address: int, length: int) -> bytes:
        """Read multiple bytes from RAM."""
        return self._backend.read_bytes(address, length)

    def read_word(self, address: int) -> int:
        """Read a 16-bit little-endian word from RAM."""
        lo = self._backend.read_byte(address)
        hi = self._backend.read_byte(address + 1)
        return (hi << 8) | lo

    def read_word_be(self, address: int) -> int:
        """Read a 16-bit big-endian word from RAM."""
        hi = self._backend.read_byte(address)
        lo = self._backend.read_byte(address + 1)
        return (hi << 8) | lo

    def write_byte(self, address: int, value: int) -> None:
        """Write a byte to RAM."""
        self._backend.write_byte(address, value)

    # ── State management ──

    def save_state(self, name: str) -> str:
        """Save emulator state to a file.

        Returns the path to the saved state file.
        """
        path = self._state_path(name)
        self._backend.save_state(path)
        return path

    def load_state(self, name: str) -> None:
        """Load a previously saved emulator state."""
        path = self._state_path(name)
        self._backend.load_state(path)

    def screenshot(self, name: str) -> str:
        """Take a screenshot. Returns the path."""
        path = self._state_path(name, ext=".png")
        self._backend.screenshot(path)
        return path

    def _state_path(self, name: str, ext: str = ".state") -> str:
        """Build a state file path."""
        if self._state_dir:
            return os.path.join(self._state_dir, f"{name}{ext}")
        return f"{name}{ext}"

    def set_state_dir(self, directory: str) -> None:
        """Set the directory for save states and screenshots."""
        os.makedirs(directory, exist_ok=True)
        self._state_dir = directory

    def close(self) -> None:
        """Shut down the emulator."""
        self._backend.close()

    # ── Context manager ──

    def __enter__(self) -> "EmulatorControl":
        return self

    def __exit__(self, *args) -> None:
        self.close()
