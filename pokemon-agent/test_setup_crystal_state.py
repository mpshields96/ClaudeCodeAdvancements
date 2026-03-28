"""Tests for setup_crystal_state.py — Crystal save state bootstrapping."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from setup_crystal_state import STARTERS, inject_starter, PARTY_COUNT


class TestStarters(unittest.TestCase):
    """Test starter definitions."""

    def test_all_starters_defined(self):
        self.assertEqual(set(STARTERS.keys()), {"cyndaquil", "totodile", "chikorita"})

    def test_starter_has_required_fields(self):
        for name, data in STARTERS.items():
            self.assertIn("species", data, f"{name} missing species")
            self.assertIn("moves", data, f"{name} missing moves")
            self.assertIn("stats", data, f"{name} missing stats")
            self.assertGreater(data["species"], 0)
            self.assertGreater(len(data["moves"]), 0)
            for stat in ("hp", "atk", "def", "spd", "spatk", "spdef"):
                self.assertIn(stat, data["stats"], f"{name} missing {stat}")

    def test_species_ids_are_gen2_starters(self):
        self.assertEqual(STARTERS["chikorita"]["species"], 152)
        self.assertEqual(STARTERS["cyndaquil"]["species"], 155)
        self.assertEqual(STARTERS["totodile"]["species"], 158)


class TestInjectStarter(unittest.TestCase):
    """Test RAM injection of starter Pokemon."""

    def test_inject_cyndaquil(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        info = inject_starter(emu, "cyndaquil")
        self.assertEqual(info["name"], "cyndaquil")
        self.assertEqual(info["species_id"], 155)
        self.assertEqual(info["level"], 5)
        # Verify party count
        self.assertEqual(emu.read_byte(PARTY_COUNT), 1)
        emu.close()

    def test_inject_totodile(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        info = inject_starter(emu, "totodile")
        self.assertEqual(info["species_id"], 158)
        self.assertEqual(emu.read_byte(PARTY_COUNT), 1)
        emu.close()

    def test_inject_chikorita(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        info = inject_starter(emu, "chikorita")
        self.assertEqual(info["species_id"], 152)
        self.assertEqual(emu.read_byte(PARTY_COUNT), 1)
        emu.close()

    def test_species_terminator_set(self):
        """Party species list must be terminated with 0xFF."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        from setup_crystal_state import PARTY_SPECIES_START
        inject_starter(emu, "cyndaquil")
        self.assertEqual(emu.read_byte(PARTY_SPECIES_START), 155)
        self.assertEqual(emu.read_byte(PARTY_SPECIES_START + 1), 0xFF)
        emu.close()

    def test_hp_set_correctly(self):
        """Starter should have HP = max HP."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        from setup_crystal_state import PARTY_DATA_START
        inject_starter(emu, "cyndaquil")
        base = PARTY_DATA_START
        hp = emu.read_byte(base + 35)
        max_hp = emu.read_byte(base + 37)
        self.assertEqual(hp, max_hp)
        self.assertGreater(hp, 0)
        emu.close()

    def test_moves_set(self):
        """Starter should have at least one move."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        from setup_crystal_state import PARTY_DATA_START
        inject_starter(emu, "cyndaquil")
        base = PARTY_DATA_START
        move1 = emu.read_byte(base + 2)  # Tackle = 33
        self.assertEqual(move1, 33)
        emu.close()

    def test_pp_set(self):
        """Starter moves should have PP."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        from setup_crystal_state import PARTY_PP_START
        inject_starter(emu, "cyndaquil")
        pp1 = emu.read_byte(PARTY_PP_START)
        self.assertGreater(pp1, 0)
        emu.close()


if __name__ == "__main__":
    unittest.main()
