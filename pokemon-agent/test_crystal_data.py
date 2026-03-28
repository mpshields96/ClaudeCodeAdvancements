"""Tests for crystal_data.py — complete Crystal data tables.

Validates the ported data tables (S218 STEAL CODE directive):
- All 251 species names
- All 251 move names with type/power/accuracy
- Crystal item names
- Map name lookup
- Move info helper
"""
import unittest

from crystal_data import (
    SPECIES_NAMES, MOVE_NAMES, MOVE_DATA, ITEM_NAMES, TYPE_NAMES,
    MAP_NAMES, BADGE_NAMES, KANTO_BADGE_NAMES,
    get_move_info, get_move_category, get_map_name,
)


class TestSpeciesNames(unittest.TestCase):
    """All 251 species must be present and correctly named."""

    def test_all_251_species_present(self):
        # 0 is "(none)", 1-251 are real Pokemon
        for i in range(1, 252):
            self.assertIn(i, SPECIES_NAMES, f"Species #{i} missing")

    def test_gen1_starters(self):
        self.assertEqual(SPECIES_NAMES[1], "Bulbasaur")
        self.assertEqual(SPECIES_NAMES[4], "Charmander")
        self.assertEqual(SPECIES_NAMES[7], "Squirtle")

    def test_gen2_starters(self):
        self.assertEqual(SPECIES_NAMES[152], "Chikorita")
        self.assertEqual(SPECIES_NAMES[155], "Cyndaquil")
        self.assertEqual(SPECIES_NAMES[158], "Totodile")

    def test_legendaries(self):
        self.assertEqual(SPECIES_NAMES[243], "Raikou")
        self.assertEqual(SPECIES_NAMES[244], "Entei")
        self.assertEqual(SPECIES_NAMES[245], "Suicune")
        self.assertEqual(SPECIES_NAMES[249], "Lugia")
        self.assertEqual(SPECIES_NAMES[250], "Ho-Oh")
        self.assertEqual(SPECIES_NAMES[251], "Celebi")

    def test_gen2_evolutions(self):
        self.assertEqual(SPECIES_NAMES[169], "Crobat")
        self.assertEqual(SPECIES_NAMES[196], "Espeon")
        self.assertEqual(SPECIES_NAMES[197], "Umbreon")
        self.assertEqual(SPECIES_NAMES[208], "Steelix")
        self.assertEqual(SPECIES_NAMES[212], "Scizor")
        self.assertEqual(SPECIES_NAMES[233], "Porygon2")

    def test_none_species(self):
        self.assertEqual(SPECIES_NAMES[0], "(none)")


class TestMoveNames(unittest.TestCase):
    """All 251 moves must be present."""

    def test_all_251_moves_present(self):
        for i in range(1, 252):
            self.assertIn(i, MOVE_NAMES, f"Move #{i} missing")

    def test_gen1_moves(self):
        self.assertEqual(MOVE_NAMES[1], "Pound")
        self.assertEqual(MOVE_NAMES[33], "Tackle")
        self.assertEqual(MOVE_NAMES[85], "Thunderbolt")
        self.assertEqual(MOVE_NAMES[89], "Earthquake")
        self.assertEqual(MOVE_NAMES[94], "Psychic")
        self.assertEqual(MOVE_NAMES[165], "Struggle")

    def test_gen2_moves(self):
        self.assertEqual(MOVE_NAMES[172], "Flame Wheel")
        self.assertEqual(MOVE_NAMES[188], "Sludge Bomb")
        self.assertEqual(MOVE_NAMES[200], "Outrage")
        self.assertEqual(MOVE_NAMES[221], "Sacred Fire")
        self.assertEqual(MOVE_NAMES[247], "Shadow Ball")
        self.assertEqual(MOVE_NAMES[251], "Beat Up")


class TestMoveData(unittest.TestCase):
    """Move data (type, power, accuracy) must be present and sensible."""

    def test_thunderbolt(self):
        mtype, power, acc = MOVE_DATA[85]
        self.assertEqual(mtype, "Electric")
        self.assertEqual(power, 95)
        self.assertEqual(acc, 100)

    def test_earthquake(self):
        mtype, power, acc = MOVE_DATA[89]
        self.assertEqual(mtype, "Ground")
        self.assertEqual(power, 100)
        self.assertEqual(acc, 100)

    def test_sacred_fire(self):
        mtype, power, acc = MOVE_DATA[221]
        self.assertEqual(mtype, "Fire")
        self.assertEqual(power, 100)
        self.assertEqual(acc, 95)

    def test_shadow_ball(self):
        mtype, power, acc = MOVE_DATA[247]
        self.assertEqual(mtype, "Ghost")
        self.assertEqual(power, 80)
        self.assertEqual(acc, 100)

    def test_status_move_swords_dance(self):
        mtype, power, acc = MOVE_DATA[14]
        self.assertEqual(mtype, "Normal")
        self.assertEqual(power, 0)
        self.assertEqual(acc, 0)


class TestGetMoveInfo(unittest.TestCase):
    """get_move_info helper returns (name, type, power, acc, category)."""

    def test_physical_move(self):
        name, mtype, power, acc, cat = get_move_info(89)  # Earthquake
        self.assertEqual(name, "Earthquake")
        self.assertEqual(mtype, "Ground")
        self.assertEqual(power, 100)
        self.assertEqual(cat, "physical")

    def test_special_move(self):
        name, mtype, power, acc, cat = get_move_info(85)  # Thunderbolt
        self.assertEqual(name, "Thunderbolt")
        self.assertEqual(mtype, "Electric")
        self.assertEqual(cat, "special")

    def test_status_move(self):
        name, mtype, power, acc, cat = get_move_info(14)  # Swords Dance
        self.assertEqual(cat, "status")

    def test_unknown_move(self):
        name, mtype, power, acc, cat = get_move_info(999)
        self.assertEqual(name, "move#999")
        self.assertEqual(mtype, "Normal")

    def test_gen2_move(self):
        name, mtype, power, acc, cat = get_move_info(200)  # Outrage
        self.assertEqual(name, "Outrage")
        self.assertEqual(mtype, "Dragon")
        self.assertEqual(power, 90)


class TestMoveCategory(unittest.TestCase):
    """Gen 2 physical/special split is type-based."""

    def test_physical_types(self):
        for t in ["Normal", "Fighting", "Flying", "Poison", "Ground",
                   "Rock", "Bug", "Ghost", "Steel"]:
            self.assertEqual(get_move_category(t), "physical")

    def test_special_types(self):
        for t in ["Fire", "Water", "Grass", "Electric", "Psychic",
                   "Ice", "Dragon", "Dark"]:
            self.assertEqual(get_move_category(t), "special")


class TestItemNames(unittest.TestCase):
    """Crystal items must have names."""

    def test_pokeballs(self):
        self.assertEqual(ITEM_NAMES[1], "Master Ball")
        self.assertEqual(ITEM_NAMES[2], "Ultra Ball")
        self.assertEqual(ITEM_NAMES[4], "Great Ball")
        self.assertEqual(ITEM_NAMES[5], "Poke Ball")

    def test_potions(self):
        self.assertEqual(ITEM_NAMES[14], "Full Restore")
        self.assertEqual(ITEM_NAMES[15], "Max Potion")
        self.assertEqual(ITEM_NAMES[16], "Hyper Potion")
        self.assertEqual(ITEM_NAMES[17], "Super Potion")
        self.assertEqual(ITEM_NAMES[18], "Potion")

    def test_crystal_unique_items(self):
        self.assertEqual(ITEM_NAMES[66], "Red Scale")
        self.assertEqual(ITEM_NAMES[70], "Clear Bell")
        self.assertEqual(ITEM_NAMES[71], "Silver Wing")
        self.assertEqual(ITEM_NAMES[180], "Rainbow Wing")

    def test_tms(self):
        self.assertEqual(ITEM_NAMES[191], "TM01")
        self.assertEqual(ITEM_NAMES[240], "TM50")
        self.assertEqual(ITEM_NAMES[243], "HM01")


class TestTypeNames(unittest.TestCase):
    """Crystal type IDs must map correctly (including Steel/Dark)."""

    def test_gen2_types(self):
        self.assertEqual(TYPE_NAMES[9], "Steel")
        self.assertEqual(TYPE_NAMES[27], "Dark")

    def test_standard_types(self):
        self.assertEqual(TYPE_NAMES[0], "Normal")
        self.assertEqual(TYPE_NAMES[20], "Fire")
        self.assertEqual(TYPE_NAMES[21], "Water")


class TestMapNames(unittest.TestCase):
    """Crystal map lookup."""

    def test_new_bark_town(self):
        self.assertEqual(get_map_name(3, 1), "New Bark Town")

    def test_elms_lab(self):
        self.assertEqual(get_map_name(3, 2), "Elm's Lab")

    def test_route_29(self):
        self.assertEqual(get_map_name(10, 1), "Route 29")

    def test_unknown_map(self):
        self.assertEqual(get_map_name(99, 99), "Map(99,99)")


class TestBadgeNames(unittest.TestCase):

    def test_johto_badges(self):
        self.assertEqual(len(BADGE_NAMES), 8)
        self.assertEqual(BADGE_NAMES[0], "Zephyr")
        self.assertEqual(BADGE_NAMES[7], "Rising")

    def test_kanto_badges(self):
        self.assertEqual(len(KANTO_BADGE_NAMES), 8)
        self.assertEqual(KANTO_BADGE_NAMES[0], "Boulder")


if __name__ == "__main__":
    unittest.main()
