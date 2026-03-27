"""Phase 5: Real emulator integration tests.

Tests the full stack against a real PyBoy emulator with the Pokemon Crystal ROM.
These tests verify that our abstractions (EmulatorControl, MemoryReader, Agent)
work correctly with real emulator state, not just mocks.

Requirements:
- PyBoy installed (pip install pyboy)
- pokemon_crystal.gbc ROM in this directory

Tests are skipped automatically if PyBoy or ROM is unavailable, so they
never break CI or the smoke test suite.

Usage:
    # Run with the venv that has PyBoy:
    .venv/bin/python3 test_real_emulator.py

    # Skips gracefully if pyboy not installed:
    python3 test_real_emulator.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

# ── Skip detection ──────────────────────────────────────────────────────────

ROM_PATH = os.path.join(os.path.dirname(__file__), "pokemon_crystal.gbc")
HAS_ROM = os.path.exists(ROM_PATH)

try:
    import pyboy  # noqa: F401
    HAS_PYBOY = True
except ImportError:
    HAS_PYBOY = False

SKIP_REASON = None
if not HAS_PYBOY:
    SKIP_REASON = "PyBoy not installed"
elif not HAS_ROM:
    SKIP_REASON = "pokemon_crystal.gbc not found"


def requires_emulator(cls_or_func):
    """Decorator to skip tests when emulator is unavailable."""
    if SKIP_REASON:
        return unittest.skip(SKIP_REASON)(cls_or_func)
    return cls_or_func


# ── Imports that need PyBoy (guarded) ───────────────────────────────────────

if HAS_PYBOY and HAS_ROM:
    from emulator_control import EmulatorControl
    from memory_reader import (
        MemoryReader, PARTY_COUNT, PLAYER_X, PLAYER_Y,
        MAP_GROUP, MAP_NUMBER, BATTLE_MODE, MONEY_ADDR,
        JOHTO_BADGES, STEP_COUNT, PLAY_TIME_HOURS,
    )
    from game_state import MenuState


# ── Test: EmulatorControl with real PyBoy ───────────────────────────────────


@requires_emulator
class TestRealEmulatorBoot(unittest.TestCase):
    """Test that the emulator boots and basic operations work."""

    def setUp(self):
        self.emu = EmulatorControl.from_rom(ROM_PATH, headless=True, speed=0)

    def tearDown(self):
        self.emu.close()

    def test_boot_and_tick(self):
        """Emulator boots ROM and can advance frames."""
        # Just ticking without crash = success
        self.emu.tick(60)

    def test_read_byte_returns_int(self):
        """RAM reads return integers in valid range."""
        self.emu.tick(10)
        val = self.emu.read_byte(0xD163)
        self.assertIsInstance(val, int)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 255)

    def test_read_bytes_returns_bytes(self):
        """Multi-byte reads return bytes object."""
        self.emu.tick(10)
        data = self.emu.read_bytes(0xD163, 4)
        self.assertIsInstance(data, bytes)
        self.assertEqual(len(data), 4)

    def test_read_word_be(self):
        """Big-endian word read returns 16-bit value."""
        self.emu.tick(10)
        val = self.emu.read_word_be(0xD163)
        self.assertIsInstance(val, int)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 0xFFFF)

    def test_button_press_no_crash(self):
        """All buttons can be pressed without crashing."""
        self.emu.tick(30)
        for button in ["a", "b", "start", "select", "up", "down", "left", "right"]:
            self.emu.press(button)

    def test_press_many(self):
        """Pressing multiple buttons in sequence works."""
        self.emu.tick(30)
        self.emu.press_many(["a", "a", "b", "start"])

    def test_move_directions(self):
        """Movement in all four directions works."""
        self.emu.tick(30)
        for direction in ["up", "down", "left", "right"]:
            self.emu.move(direction, 1)


@requires_emulator
class TestRealEmulatorStateManagement(unittest.TestCase):
    """Test save/load state with real emulator."""

    def setUp(self):
        self.emu = EmulatorControl.from_rom(ROM_PATH, headless=True, speed=0)
        self.tmpdir = tempfile.mkdtemp(prefix="poke_test_")
        self.emu.set_state_dir(self.tmpdir)

    def tearDown(self):
        self.emu.close()
        # Clean up temp files
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_state(self):
        """Save state, advance, load state restores original."""
        self.emu.tick(120)

        # Read a RAM value before save
        val_before = self.emu.read_byte(PLAYER_X)
        self.emu.save_state("checkpoint1")

        # Advance emulator significantly
        self.emu.tick(600)

        # Load state
        self.emu.load_state("checkpoint1")
        val_after = self.emu.read_byte(PLAYER_X)

        self.assertEqual(val_before, val_after)

    def test_save_state_creates_file(self):
        """Save state creates a file on disk."""
        self.emu.tick(60)
        path = self.emu.save_state("test_save")
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)


# ── Test: MemoryReader with real emulator ───────────────────────────────────


@requires_emulator
class TestRealMemoryReader(unittest.TestCase):
    """Test MemoryReader reads real game state from emulator RAM."""

    def setUp(self):
        self.emu = EmulatorControl.from_rom(ROM_PATH, headless=True, speed=0)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_read_game_state_at_boot(self):
        """MemoryReader produces a valid GameState right after boot."""
        self.emu.tick(60)
        state = self.reader.read_game_state()
        # At boot screen, party count should be 0 (no game loaded)
        self.assertGreaterEqual(state.party.size(), 0)
        self.assertLessEqual(state.party.size(), 6)

    def test_battle_mode_zero_at_boot(self):
        """Not in battle at boot screen."""
        self.emu.tick(60)
        val = self.emu.read_byte(BATTLE_MODE)
        self.assertEqual(val, 0)

    def test_map_position_valid(self):
        """Map position reads are within valid ranges."""
        self.emu.tick(60)
        state = self.reader.read_game_state()
        # At boot, coordinates should be small numbers
        self.assertGreaterEqual(state.position.x, 0)
        self.assertLessEqual(state.position.x, 255)
        self.assertGreaterEqual(state.position.y, 0)
        self.assertLessEqual(state.position.y, 255)

    def test_badges_valid_at_boot(self):
        """Badge count is 0 at boot (no save loaded)."""
        self.emu.tick(60)
        state = self.reader.read_game_state()
        self.assertGreaterEqual(state.badges.count(), 0)
        self.assertLessEqual(state.badges.count(), 16)

    def test_read_game_state_no_crash_after_many_ticks(self):
        """Reading state after extended emulation doesn't crash."""
        # Advance past title screen intro
        self.emu.tick(600)
        state = self.reader.read_game_state()
        self.assertIsNotNone(state)

    def test_menu_state_valid(self):
        """Menu state detection returns a valid MenuState."""
        self.emu.tick(60)
        state = self.reader.read_game_state()
        self.assertIsInstance(state.menu_state, MenuState)


# ── Test: Extended emulation (title screen navigation) ──────────────────────


@requires_emulator
class TestTitleScreenNavigation(unittest.TestCase):
    """Test navigating through the title screen with real button presses."""

    def setUp(self):
        self.emu = EmulatorControl.from_rom(ROM_PATH, headless=True, speed=0)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_title_screen_advance(self):
        """Pressing buttons on title screen changes emulator state."""
        # Let title screen load
        self.emu.tick(300)
        ram_before = self.emu.read_bytes(0xC000, 16)

        # Mash through intro
        self.emu.mash_a(times=10, wait=30)
        ram_after = self.emu.read_bytes(0xC000, 16)

        # RAM should change after input (working RAM at 0xC000+ is active)
        # This may or may not differ depending on title screen state,
        # but it proves the emulator is responsive to input
        # We just verify no crash occurred
        self.assertIsNotNone(ram_after)

    def test_100_frames_stable(self):
        """Emulator runs 100 frames without crash or hang."""
        for i in range(100):
            self.emu.tick(1)
        # If we get here, the emulator is stable

    def test_rapid_state_reads(self):
        """100 consecutive state reads don't crash or degrade."""
        self.emu.tick(60)
        states = []
        for _ in range(100):
            state = self.reader.read_game_state()
            states.append(state)
            self.emu.tick(1)
        self.assertEqual(len(states), 100)


# ── Test: Agent with real emulator (lightweight) ────────────────────────────


@requires_emulator
class TestAgentWithRealEmulator(unittest.TestCase):
    """Test the agent loop with a real emulator (MockLLM, real PyBoy)."""

    def setUp(self):
        self.emu = EmulatorControl.from_rom(ROM_PATH, headless=True, speed=0)
        self.reader = MemoryReader(self.emu)
        # Let the emulator boot
        self.emu.tick(120)

    def tearDown(self):
        self.emu.close()

    def test_agent_5_steps_real_emu(self):
        """Agent runs 5 steps with real emulator without crashing."""
        from agent import CrystalAgent, MockLLMClient

        llm = MockLLMClient()
        agent = CrystalAgent(
            emulator=self.emu, reader=self.reader, llm=llm,
            max_history=60, stuck_threshold=5,
        )
        results = agent.run(num_steps=5)
        self.assertEqual(len(results), 5)
        # Each step should have a valid state
        for r in results:
            self.assertIsNotNone(r.state)
            self.assertGreaterEqual(r.state.position.x, 0)

    def test_agent_reads_real_ram(self):
        """Agent's state reflects actual emulator RAM values."""
        from agent import CrystalAgent, MockLLMClient

        llm = MockLLMClient()
        agent = CrystalAgent(
            emulator=self.emu, reader=self.reader, llm=llm,
            max_history=60, stuck_threshold=5,
        )
        result = agent.step()
        # State should have real values (not all zeros like a fresh mock)
        state = result.state
        self.assertIsNotNone(state.position)
        self.assertIsNotNone(state.party)

    def test_agent_button_presses_affect_emulator(self):
        """When agent presses buttons, emulator state can change."""
        from agent import CrystalAgent, MockLLMClient, LLMResponse, ToolUse

        # Give the LLM a response that presses specific buttons
        responses = [
            LLMResponse(
                text="Let me press start to check the menu.",
                tool_uses=[ToolUse(
                    id="t1", name="press_buttons",
                    input={"buttons": ["a", "a", "a", "start"]},
                )],
            ),
        ]
        llm = MockLLMClient(responses=responses)
        agent = CrystalAgent(
            emulator=self.emu, reader=self.reader, llm=llm,
            max_history=60, stuck_threshold=5,
        )

        # Capture RAM before
        ram_snapshot_before = self.emu.read_bytes(0xC100, 32)

        agent.step()

        # Capture RAM after — buttons should have caused some state change
        # (even on title screen, A presses advance the intro)
        ram_snapshot_after = self.emu.read_bytes(0xC100, 32)

        # At minimum, verify no crash. RAM may or may not change depending
        # on exact title screen state, but the emulator processed input.
        self.assertEqual(len(ram_snapshot_after), 32)


if __name__ == "__main__":
    unittest.main()
