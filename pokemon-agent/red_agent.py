"""Pokemon Red autonomous agent — Red-specific variant of the agent loop.

Subclasses CrystalAgent with Pokemon Red RAM addresses, memory reader,
text reader, and collision reader. All game-agnostic logic (step loop,
LLM communication, stuck detection, auto-advance) is inherited.

Usage:
    from red_agent import RedAgent
    from emulator_control import EmulatorControl

    emu = EmulatorControl.from_rom("pokemon_red.gb")
    agent = RedAgent(emulator=emu)
    agent.run(num_steps=100)

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

import os
from typing import Optional

import logging

from agent import CrystalAgent, LLMClient
from boot_sequence import run_boot_sequence
from checkpoint import CheckpointManager
from collision_reader_red import CollisionReaderRed
from config import (
    MAX_HISTORY, SAVE_INTERVAL, STATE_DIR, STUCK_THRESHOLD,
)
from emulator_control import EmulatorControl
from memory_reader_red import MemoryReaderRed
from navigation import Navigator
from text_reader_red import TextReaderRed
from warp_data_red import WARP_TABLE, CONNECTION_TABLE
import memory_reader_red as mrr

logger = logging.getLogger("red_agent")


class RedAgent(CrystalAgent):
    """Autonomous Pokemon Red agent.

    Inherits the full step loop from CrystalAgent but uses Red-specific
    components: MemoryReaderRed, TextReaderRed, CollisionReaderRed,
    and Red warp/connection tables for cross-map navigation.
    """

    def __init__(
        self,
        emulator: EmulatorControl,
        llm: Optional[LLMClient] = None,
        max_history: int = MAX_HISTORY,
        save_interval: int = SAVE_INTERVAL,
        stuck_threshold: int = STUCK_THRESHOLD,
        auto_boot: bool = False,
    ):
        # Build Red-specific components
        reader = MemoryReaderRed(emulator)
        navigator = Navigator()
        collision_reader = CollisionReaderRed(emulator)

        # Load warps and connections for cross-map A*
        for warp in WARP_TABLE:
            navigator.add_warp(warp)
        for conn in CONNECTION_TABLE:
            navigator.add_connection(conn)

        # Initialize parent with Red reader and navigator
        super().__init__(
            emulator=emulator,
            reader=reader,
            llm=llm,
            navigator=navigator,
            max_history=max_history,
            save_interval=save_interval,
            stuck_threshold=stuck_threshold,
        )

        # Override Crystal-specific components
        self.text_reader = TextReaderRed(emulator)
        self.collision_reader = collision_reader

        # Replace Crystal gym checkpoints with Red gym checkpoints
        self.checkpoint_mgr = CheckpointManager(emulator, state_dir=STATE_DIR)
        self._register_red_gyms()

        # Boot sequence state
        self.boot_result: Optional[dict] = None
        if auto_boot:
            self.boot()

    def boot(self) -> dict:
        """Run the boot sequence to automate the Pokemon Red intro.

        Clears opening dialog, navigates Red's House, exits to Pallet Town.
        Stores result in self.boot_result for inspection.
        """
        logger.info("Running boot sequence...")
        self.boot_result = run_boot_sequence(self.emulator, self.reader)
        if self.boot_result["success"]:
            logger.info("Boot complete: %s", self.boot_result["phases_completed"])
        else:
            logger.warning("Boot partial: %s", self.boot_result["phases_completed"])
        return self.boot_result

    def _register_red_gyms(self) -> None:
        """Register Pokemon Red gym map IDs for auto-checkpointing."""
        red_gym_maps = [44, 52, 59, 153, 160, 190]  # Viridian through Saffron
        for map_id in red_gym_maps:
            self.checkpoint_mgr.register_gym_map(map_id)

    def _screen_detection_addresses(self) -> dict:
        """Return Red-specific RAM addresses for screen detection.

        Pokemon Red uses different addresses than Crystal for
        joy disable. Red has no WINDOW_STACK_SIZE equivalent,
        so we use a known-zero address as a safe no-op.
        """
        return {
            "joy_disabled": mrr.JOY_DISABLED,
            "battle_mode": mrr.BATTLE_MODE,
            "window_stack": 0x0000,  # Safe fallback: reads 0 = no window
        }

    def _save_state(self) -> None:
        """Save emulator state with Red-specific naming."""
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            name = f"red_step_{self.step_count}"
            path = self.emulator.save_state(name)
        except Exception:
            pass  # Non-critical

    def _capture_screenshot(self) -> Optional[str]:
        """Capture screenshot with Red-specific naming."""
        try:
            from prompts import encode_screenshot_b64
            self.emulator.screenshot("red_screenshot")
            path = self.emulator._state_path("red_screenshot", ext=".png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                return encode_screenshot_b64(data)
        except Exception:
            pass
        return None
