"""Tests for enemy move/stat reading from battle RAM.

Verifies that memory_reader_red reads enemy moves, stats, and types
correctly from battle RAM addresses, including fallback to species_types.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
import memory_reader_red as mrr


def _setup_battle(emu, enemy_species=0xA5, enemy_level=5, enemy_hp=20,
                  enemy_type1=0x00, enemy_type2=0x00, enemy_moves=None,
                  party_species=0xB0, party_level=10, party_hp=30):
    """Set up mock RAM for a wild battle."""
    # Player party (minimal)
    emu.write_byte(mrr.MAP_ID, 0)
    emu.write_byte(mrr.PLAYER_X, 5)
    emu.write_byte(mrr.PLAYER_Y, 5)
    emu.write_byte(mrr.PARTY_COUNT, 1)
    base = mrr.PARTY_BASE_ADDRS[0]
    emu.write_byte(base + mrr.OFF_SPECIES, party_species)
    emu.write_byte(base + mrr.OFF_LEVEL, party_level)
    emu.write_byte(base + mrr.OFF_HP_LO, party_hp)
    emu.write_byte(base + mrr.OFF_MAX_HP_LO, party_hp)
    emu.write_byte(base + mrr.OFF_TYPE1, 0x14)  # Fire
    emu.write_byte(base + mrr.OFF_TYPE2, 0x14)  # Fire
    emu.write_byte(base + mrr.OFF_MOVE1, 0x0A)  # Scratch
    emu.write_byte(base + mrr.OFF_PP1, 35)

    # Battle active
    emu.write_byte(mrr.BATTLE_MODE, 1)  # Wild

    # Enemy
    emu.write_byte(mrr.ENEMY_MON_SPECIES, enemy_species)
    emu.write_byte(mrr.ENEMY_MON_LEVEL, enemy_level)
    emu.write_byte(mrr.ENEMY_MON_HP_LO, enemy_hp)
    emu.write_byte(mrr.ENEMY_MON_MAX_HP_LO, enemy_hp)
    emu.write_byte(mrr.ENEMY_MON_STATUS, 0)
    emu.write_byte(mrr.ENEMY_MON_TYPE1, enemy_type1)
    emu.write_byte(mrr.ENEMY_MON_TYPE2, enemy_type2)

    # Enemy stats
    emu.write_byte(mrr.ENEMY_MON_ATTACK_LO, 25)
    emu.write_byte(mrr.ENEMY_MON_DEFENSE_LO, 20)
    emu.write_byte(mrr.ENEMY_MON_SPEED_LO, 30)
    emu.write_byte(mrr.ENEMY_MON_SPECIAL_LO, 15)

    # Enemy moves
    if enemy_moves:
        for j, mid in enumerate(enemy_moves[:4]):
            emu.write_byte(mrr.ENEMY_MON_MOVE1 + j, mid)


class TestEnemyMoveReading(unittest.TestCase):
    """Test enemy move reading from battle RAM."""

    def test_enemy_has_moves(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x21, 0x27])  # Tackle, Tail Whip
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertTrue(state.battle.in_battle)
        self.assertGreater(len(state.battle.enemy.moves), 0)

    def test_enemy_move_names(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x21, 0x27])  # Tackle, Tail Whip
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        names = [m.name for m in state.battle.enemy.moves]
        self.assertIn("TACKLE", names)
        self.assertIn("TAIL WHIP", names)

    def test_enemy_move_types(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x34])  # Ember
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.moves[0].move_type, "Fire")

    def test_enemy_move_power(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x21])  # Tackle = power 35
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertGreater(state.battle.enemy.moves[0].power, 0)

    def test_enemy_four_moves(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x21, 0x34, 0x37, 0x2D])
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(len(state.battle.enemy.moves), 4)

    def test_enemy_no_moves_when_zero(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[])  # All move slots = 0
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(len(state.battle.enemy.moves), 0)

    def test_enemy_pp_set_to_available(self):
        """Enemy PP is unknown — should be set to available (nonzero)."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_moves=[0x21])
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertGreater(state.battle.enemy.moves[0].pp, 0)


class TestEnemyStatReading(unittest.TestCase):
    """Test enemy stat reading from battle RAM."""

    def test_enemy_attack_read(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.attack, 25)

    def test_enemy_defense_read(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.defense, 20)

    def test_enemy_speed_read(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.speed, 30)

    def test_enemy_special_read(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.sp_attack, 15)
        self.assertEqual(state.battle.enemy.sp_defense, 15)


class TestEnemyTypeFallback(unittest.TestCase):
    """Test type fallback to species_types when RAM has invalid type IDs."""

    def test_valid_ram_types_preferred(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_species=0xB0, enemy_type1=0x14, enemy_type2=0x14)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.pokemon_type, ["Fire"])

    def test_fallback_to_species_table(self):
        """When RAM type IDs aren't in TYPE_NAMES, use species_types."""
        emu = EmulatorControl.mock(ram_size=0x10000)
        # Use 0xFF which is not a valid type ID
        _setup_battle(emu, enemy_species=0xB0, enemy_type1=0xFF, enemy_type2=0xFF)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        # Should fall back to Charmander's type from species_types
        self.assertEqual(state.battle.enemy.pokemon_type, ["Fire"])

    def test_dual_type_from_ram(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu, enemy_species=0x99,  # Bulbasaur
                      enemy_type1=0x16, enemy_type2=0x03)  # Grass/Poison
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.battle.enemy.pokemon_type, ["Grass", "Poison"])


class TestPartyXPReading(unittest.TestCase):
    """Test party Pokemon XP reading from RAM."""

    def test_xp_read_basic(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        base = mrr.PARTY_BASE_ADDRS[0]
        # Set XP to 1000 (0x0003E8)
        emu.write_byte(base + mrr.OFF_EXP_HI, 0x00)
        emu.write_byte(base + mrr.OFF_EXP_MID, 0x03)
        emu.write_byte(base + mrr.OFF_EXP_LO, 0xE8)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.party.pokemon[0].xp, 1000)

    def test_xp_zero(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.party.pokemon[0].xp, 0)

    def test_xp_large_value(self):
        emu = EmulatorControl.mock(ram_size=0x10000)
        _setup_battle(emu)
        base = mrr.PARTY_BASE_ADDRS[0]
        # Set XP to 100000 (0x0186A0)
        emu.write_byte(base + mrr.OFF_EXP_HI, 0x01)
        emu.write_byte(base + mrr.OFF_EXP_MID, 0x86)
        emu.write_byte(base + mrr.OFF_EXP_LO, 0xA0)
        reader = mrr.MemoryReaderRed(emu)
        state = reader.read_game_state()
        self.assertEqual(state.party.pokemon[0].xp, 100000)

    def test_xp_in_pokemon_dataclass(self):
        from game_state import Pokemon
        p = Pokemon(species="Test", nickname="Test", level=5,
                    hp=20, hp_max=20, attack=10, defense=10,
                    speed=10, sp_attack=10, sp_defense=10, xp=500)
        self.assertEqual(p.xp, 500)


if __name__ == "__main__":
    unittest.main()
