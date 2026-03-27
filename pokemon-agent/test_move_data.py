"""Tests for move_data.py — Gen 1 move database.

Validates that the move lookup table returns correct type, power,
accuracy, and category for known Pokemon Red moves.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))


class TestMoveDataLookup(unittest.TestCase):
    """Test move data lookups by move ID."""

    def test_import(self):
        from move_data import get_move_data
        self.assertTrue(callable(get_move_data))

    def test_scratch_data(self):
        """Scratch (0x0A): Normal, 40 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x0A)
        self.assertIsNotNone(data)
        self.assertEqual(data["type"], "Normal")
        self.assertEqual(data["power"], 40)
        self.assertEqual(data["accuracy"], 100)

    def test_ember_data(self):
        """Ember (0x34): Fire, 40 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x34)
        self.assertEqual(data["type"], "Fire")
        self.assertEqual(data["power"], 40)

    def test_water_gun_data(self):
        """Water Gun (0x37): Water, 40 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x37)
        self.assertEqual(data["type"], "Water")
        self.assertEqual(data["power"], 40)

    def test_thunderbolt_data(self):
        """Thunderbolt (0x55): Electric, 95 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x55)
        self.assertEqual(data["type"], "Electric")
        self.assertEqual(data["power"], 95)

    def test_psychic_data(self):
        """Psychic (0x5E): Psychic, 90 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x5E)
        self.assertEqual(data["type"], "Psychic")
        self.assertEqual(data["power"], 90)

    def test_earthquake_data(self):
        """Earthquake (0x59): Ground, 100 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x59)
        self.assertEqual(data["type"], "Ground")
        self.assertEqual(data["power"], 100)

    def test_unknown_move_returns_none(self):
        """Unknown move IDs should return None."""
        from move_data import get_move_data
        self.assertIsNone(get_move_data(0))
        self.assertIsNone(get_move_data(255))

    def test_status_move_has_zero_power(self):
        """Status moves like Growl (0x2D) should have 0 power."""
        from move_data import get_move_data
        data = get_move_data(0x2D)
        self.assertIsNotNone(data)
        self.assertEqual(data["power"], 0)

    def test_all_moves_have_required_fields(self):
        """Every move entry should have type, power, accuracy, category."""
        from move_data import MOVE_DATA
        for move_id, data in MOVE_DATA.items():
            self.assertIn("type", data, f"Move {move_id:#x} missing type")
            self.assertIn("power", data, f"Move {move_id:#x} missing power")
            self.assertIn("accuracy", data, f"Move {move_id:#x} missing accuracy")
            self.assertIn("category", data, f"Move {move_id:#x} missing category")

    def test_coverage_starter_moves(self):
        """All three starter Pokemon's initial moves should be present."""
        from move_data import get_move_data
        # Tackle (0x21), Scratch (0x0A), Tail Whip (0x27), Growl (0x2D)
        for move_id in [0x21, 0x0A, 0x27, 0x2D]:
            self.assertIsNotNone(get_move_data(move_id),
                                 f"Starter move {move_id:#x} missing")

    def test_hyper_beam(self):
        """Hyper Beam (0x3F): Normal, 150 power, 90 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x3F)
        self.assertEqual(data["type"], "Normal")
        self.assertEqual(data["power"], 150)
        self.assertEqual(data["accuracy"], 90)

    def test_surf(self):
        """Surf (0x39): Water, 95 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x39)
        self.assertEqual(data["type"], "Water")
        self.assertEqual(data["power"], 95)

    def test_flamethrower(self):
        """Flamethrower (0x35): Fire, 95 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x35)
        self.assertEqual(data["type"], "Fire")
        self.assertEqual(data["power"], 95)

    def test_ice_beam(self):
        """Ice Beam (0x3A): Ice, 95 power, 100 accuracy."""
        from move_data import get_move_data
        data = get_move_data(0x3A)
        self.assertEqual(data["type"], "Ice")
        self.assertEqual(data["power"], 95)


class TestMoveDataIntegration(unittest.TestCase):
    """Test move data integration with memory reader."""

    def test_move_names_coverage(self):
        """Every move in MOVE_NAMES should have a MOVE_DATA entry."""
        from memory_reader_red import MOVE_NAMES
        from move_data import MOVE_DATA
        missing = []
        for move_id in MOVE_NAMES:
            if move_id not in MOVE_DATA:
                missing.append(f"{move_id:#x}: {MOVE_NAMES[move_id]}")
        self.assertEqual(len(missing), 0,
                         f"Moves in MOVE_NAMES but not MOVE_DATA: {missing}")


if __name__ == "__main__":
    unittest.main()
