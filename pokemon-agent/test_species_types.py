"""Tests for species_types.py — Gen 1 species-to-type lookup table.

Verifies the SPECIES_TYPES mapping covers all 151 Gen 1 Pokemon and
returns correct types. This table provides type info without reading
RAM, useful for reasoning about encounters and team composition.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


class TestSpeciesTypes(unittest.TestCase):
    """Test species type table completeness and correctness."""

    def test_import(self):
        from species_types import SPECIES_TYPES, get_species_types
        self.assertIsInstance(SPECIES_TYPES, dict)

    def test_all_species_covered(self):
        """Every species in SPECIES_NAMES should have a type entry."""
        from memory_reader_red import SPECIES_NAMES
        from species_types import SPECIES_TYPES
        for sid, name in SPECIES_NAMES.items():
            self.assertIn(sid, SPECIES_TYPES, f"Missing type for {name} (0x{sid:02X})")

    def test_types_are_valid(self):
        """All type strings should be from the Gen 1 TYPE_NAMES set."""
        from memory_reader_red import TYPE_NAMES
        from species_types import SPECIES_TYPES
        valid_types = set(TYPE_NAMES.values())
        for sid, types in SPECIES_TYPES.items():
            self.assertIsInstance(types, list, f"Species 0x{sid:02X} types not a list")
            self.assertGreaterEqual(len(types), 1, f"Species 0x{sid:02X} has no types")
            self.assertLessEqual(len(types), 2, f"Species 0x{sid:02X} has >2 types")
            for t in types:
                self.assertIn(t, valid_types, f"Invalid type '{t}' for 0x{sid:02X}")

    def test_known_pokemon_types(self):
        """Spot-check well-known Pokemon types."""
        from species_types import get_species_types
        # Starters
        self.assertEqual(get_species_types(0xB0), ["Fire"])  # CHARMANDER
        self.assertEqual(get_species_types(0xB1), ["Water"])  # SQUIRTLE
        self.assertEqual(get_species_types(0x99), ["Grass", "Poison"])  # BULBASAUR
        # Pikachu
        self.assertEqual(get_species_types(0x54), ["Electric"])  # PIKACHU
        # Dual types
        self.assertEqual(get_species_types(0xB4), ["Fire", "Flying"])  # CHARIZARD
        self.assertEqual(get_species_types(0x16), ["Water", "Flying"])  # GYARADOS
        self.assertEqual(get_species_types(0x42), ["Dragon", "Flying"])  # DRAGONITE
        self.assertEqual(get_species_types(0x0E), ["Ghost", "Poison"])  # GENGAR
        # Psychic
        self.assertEqual(get_species_types(0x83), ["Psychic"])  # MEWTWO
        self.assertEqual(get_species_types(0x15), ["Psychic"])  # MEW

    def test_get_species_types_unknown(self):
        """Unknown species IDs return empty list."""
        from species_types import get_species_types
        self.assertEqual(get_species_types(0xFF), [])
        self.assertEqual(get_species_types(0x00), [])

    def test_no_duplicate_types(self):
        """Single-type Pokemon shouldn't have the same type listed twice."""
        from species_types import SPECIES_TYPES
        for sid, types in SPECIES_TYPES.items():
            if len(types) == 2:
                self.assertNotEqual(types[0], types[1],
                                    f"Species 0x{sid:02X} has duplicate type {types[0]}")

    def test_type_consistency_with_type_names(self):
        """The type ID values used by TYPE_NAMES match what we'd encode."""
        from memory_reader_red import TYPE_NAMES
        from species_types import SPECIES_TYPES
        # Just verify our string types are a subset of TYPE_NAMES values
        all_used_types = set()
        for types in SPECIES_TYPES.values():
            all_used_types.update(types)
        valid = set(TYPE_NAMES.values())
        self.assertTrue(all_used_types.issubset(valid),
                        f"Unknown types used: {all_used_types - valid}")


if __name__ == "__main__":
    unittest.main()
