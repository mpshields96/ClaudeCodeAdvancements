"""Tests for memory_reader.py — Pokemon Crystal RAM reader."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from game_state import Badges, BattleState, GameState, MapPosition, MenuState, Party, Pokemon
from memory_reader import (
    BATTLE_MODE,
    ENEMY_MON_HP_HI,
    ENEMY_MON_HP_LO,
    ENEMY_MON_HP_MAX_HI,
    ENEMY_MON_HP_MAX_LO,
    ENEMY_MON_LEVEL,
    ENEMY_MON_SPECIES,
    ENEMY_MON_STATUS,
    JOHTO_BADGES,
    JOY_DISABLED,
    MAP_GROUP,
    MAP_NUMBER,
    MART_POINTER,
    MONEY_ADDR,
    PARTY_COUNT,
    PARTY_DATA_START,
    PARTY_MON_SIZE,
    PARTY_NICKNAMES_START,
    PARTY_PP_START,
    PLAY_TIME_HOURS,
    PLAY_TIME_MINUTES,
    PLAYER_X,
    TEXT_BOX_FLAGS,
    WINDOW_STACK_SIZE,
    PLAYER_Y,
    STEP_COUNT,
    MemoryReader,
    OFF_ATTACK_HI,
    OFF_ATTACK_LO,
    OFF_DEFENSE_HI,
    OFF_DEFENSE_LO,
    OFF_HELD_ITEM,
    OFF_HP_HI,
    OFF_HP_LO,
    OFF_HP_MAX_HI,
    OFF_HP_MAX_LO,
    OFF_LEVEL,
    OFF_MOVE1,
    OFF_SPECIES,
    OFF_SP_ATK_HI,
    OFF_SP_ATK_LO,
    OFF_SP_DEF_HI,
    OFF_SP_DEF_LO,
    OFF_SPEED_HI,
    OFF_SPEED_LO,
    OFF_STATUS,
    decode_bcd,
    decode_status,
    decode_text,
)


class TestDecodeStatus(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(decode_status(0x00), "healthy")

    def test_asleep(self):
        self.assertEqual(decode_status(0x03), "asleep")

    def test_poisoned(self):
        self.assertEqual(decode_status(0x08), "poisoned")

    def test_burned(self):
        self.assertEqual(decode_status(0x10), "burned")

    def test_frozen(self):
        self.assertEqual(decode_status(0x20), "frozen")

    def test_paralyzed(self):
        self.assertEqual(decode_status(0x40), "paralyzed")


class TestDecodeText(unittest.TestCase):
    def test_simple_name(self):
        # "ASH" in Pokemon encoding: 0x80=A, 0x92=S, 0x87=H, 0x50=terminator
        data = bytes([0x80, 0x92, 0x87, 0x50, 0x00, 0x00])
        self.assertEqual(decode_text(data), "ASH")

    def test_empty_terminated(self):
        data = bytes([0x50])
        self.assertEqual(decode_text(data), "")

    def test_lowercase(self):
        # "abc" = 0xA0, 0xA1, 0xA2
        data = bytes([0xA0, 0xA1, 0xA2, 0x50])
        self.assertEqual(decode_text(data), "abc")

    def test_unknown_chars(self):
        data = bytes([0x80, 0x01, 0x80, 0x50])  # A, unknown, A
        self.assertEqual(decode_text(data), "A?A")


class TestDecodeBCD(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(decode_bcd(bytes([0x00, 0x00, 0x00])), 0)

    def test_simple(self):
        # 0x01, 0x23, 0x45 = 12345
        self.assertEqual(decode_bcd(bytes([0x01, 0x23, 0x45])), 12345)

    def test_max_money(self):
        # 0x99, 0x99, 0x99 = 999999
        self.assertEqual(decode_bcd(bytes([0x99, 0x99, 0x99])), 999999)

    def test_small(self):
        # 0x00, 0x00, 0x50 = 50
        self.assertEqual(decode_bcd(bytes([0x00, 0x00, 0x50])), 50)


class TestMemoryReaderParty(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def _write_pokemon(self, slot: int, species: int, level: int, hp: int, hp_max: int):
        """Helper to write a Pokemon into RAM at the given slot."""
        base = PARTY_DATA_START + (slot * PARTY_MON_SIZE)
        self.emu.write_byte(base + OFF_SPECIES, species)
        self.emu.write_byte(base + OFF_LEVEL, level)
        # HP (big-endian)
        self.emu.write_byte(base + OFF_HP_HI, (hp >> 8) & 0xFF)
        self.emu.write_byte(base + OFF_HP_LO, hp & 0xFF)
        self.emu.write_byte(base + OFF_HP_MAX_HI, (hp_max >> 8) & 0xFF)
        self.emu.write_byte(base + OFF_HP_MAX_LO, hp_max & 0xFF)
        # Stats
        for off in [OFF_ATTACK_HI, OFF_DEFENSE_HI, OFF_SPEED_HI, OFF_SP_ATK_HI, OFF_SP_DEF_HI]:
            self.emu.write_byte(base + off, 0)
            self.emu.write_byte(base + off + 1, 50)

    def test_empty_party(self):
        self.emu.write_byte(PARTY_COUNT, 0)
        party = self.reader.read_party()
        self.assertEqual(party.size(), 0)

    def test_one_pokemon(self):
        self.emu.write_byte(PARTY_COUNT, 1)
        self._write_pokemon(0, species=155, level=5, hp=20, hp_max=20)
        party = self.reader.read_party()
        self.assertEqual(party.size(), 1)
        lead = party.lead()
        self.assertEqual(lead.species, "Cyndaquil")
        self.assertEqual(lead.level, 5)
        self.assertEqual(lead.hp, 20)
        self.assertEqual(lead.hp_max, 20)

    def test_party_count_capped_at_six(self):
        self.emu.write_byte(PARTY_COUNT, 255)
        party = self.reader.read_party()
        self.assertEqual(party.size(), 6)

    def test_pokemon_with_status(self):
        self.emu.write_byte(PARTY_COUNT, 1)
        self._write_pokemon(0, species=25, level=10, hp=30, hp_max=30)
        base = PARTY_DATA_START
        self.emu.write_byte(base + OFF_STATUS, 0x08)  # poisoned
        mon = self.reader.read_pokemon(0)
        self.assertEqual(mon.status, "poisoned")

    def test_pokemon_with_moves(self):
        self.emu.write_byte(PARTY_COUNT, 1)
        self._write_pokemon(0, species=155, level=5, hp=20, hp_max=20)
        base = PARTY_DATA_START
        self.emu.write_byte(base + OFF_MOVE1, 33)  # Tackle
        self.emu.write_byte(base + OFF_MOVE1 + 1, 52)  # Ember
        # Write PP
        pp_base = PARTY_PP_START
        self.emu.write_byte(pp_base, 35)  # Tackle PP
        self.emu.write_byte(pp_base + 1, 25)  # Ember PP
        mon = self.reader.read_pokemon(0)
        self.assertEqual(len(mon.moves), 2)
        self.assertEqual(mon.moves[0].name, "Tackle")
        self.assertEqual(mon.moves[0].pp, 35)
        self.assertEqual(mon.moves[1].name, "Ember")

    def test_pokemon_with_held_item(self):
        self.emu.write_byte(PARTY_COUNT, 1)
        self._write_pokemon(0, species=25, level=10, hp=30, hp_max=30)
        base = PARTY_DATA_START
        self.emu.write_byte(base + OFF_HELD_ITEM, 77)
        mon = self.reader.read_pokemon(0)
        self.assertEqual(mon.held_item, "item#77")

    def test_pokemon_no_held_item(self):
        self.emu.write_byte(PARTY_COUNT, 1)
        self._write_pokemon(0, species=25, level=10, hp=30, hp_max=30)
        mon = self.reader.read_pokemon(0)
        self.assertEqual(mon.held_item, "")

    def test_full_party(self):
        self.emu.write_byte(PARTY_COUNT, 6)
        species = [155, 16, 41, 74, 92, 133]
        for i, sp in enumerate(species):
            self._write_pokemon(i, species=sp, level=10 + i, hp=30, hp_max=30)
        party = self.reader.read_party()
        self.assertEqual(party.size(), 6)
        self.assertEqual(party.pokemon[0].species, "Cyndaquil")
        self.assertEqual(party.pokemon[5].species, "Eevee")


class TestMemoryReaderPosition(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_read_position(self):
        self.emu.write_byte(MAP_GROUP, 3)
        self.emu.write_byte(MAP_NUMBER, 7)
        self.emu.write_byte(PLAYER_X, 10)
        self.emu.write_byte(PLAYER_Y, 5)
        pos = self.reader.read_position()
        self.assertEqual(pos.map_id, (3 << 8) | 7)
        self.assertEqual(pos.x, 10)
        self.assertEqual(pos.y, 5)


class TestMemoryReaderBattle(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_not_in_battle(self):
        self.emu.write_byte(BATTLE_MODE, 0)
        battle = self.reader.read_battle_state()
        self.assertFalse(battle.in_battle)

    def test_wild_battle(self):
        self.emu.write_byte(BATTLE_MODE, 1)
        self.emu.write_byte(ENEMY_MON_SPECIES, 19)  # Rattata
        self.emu.write_byte(ENEMY_MON_LEVEL, 3)
        self.emu.write_byte(ENEMY_MON_HP_HI, 0)
        self.emu.write_byte(ENEMY_MON_HP_LO, 12)
        self.emu.write_byte(ENEMY_MON_HP_MAX_HI, 0)
        self.emu.write_byte(ENEMY_MON_HP_MAX_LO, 12)
        battle = self.reader.read_battle_state()
        self.assertTrue(battle.in_battle)
        self.assertTrue(battle.is_wild)
        self.assertFalse(battle.is_trainer)
        self.assertEqual(battle.enemy.species, "Rattata")
        self.assertEqual(battle.enemy.level, 3)
        self.assertEqual(battle.enemy.hp, 12)

    def test_trainer_battle(self):
        self.emu.write_byte(BATTLE_MODE, 2)
        self.emu.write_byte(ENEMY_MON_SPECIES, 16)  # Pidgey
        self.emu.write_byte(ENEMY_MON_LEVEL, 9)
        self.emu.write_byte(ENEMY_MON_HP_HI, 0)
        self.emu.write_byte(ENEMY_MON_HP_LO, 28)
        self.emu.write_byte(ENEMY_MON_HP_MAX_HI, 0)
        self.emu.write_byte(ENEMY_MON_HP_MAX_LO, 28)
        battle = self.reader.read_battle_state()
        self.assertTrue(battle.in_battle)
        self.assertFalse(battle.is_wild)
        self.assertTrue(battle.is_trainer)


class TestMemoryReaderBadges(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_no_badges(self):
        self.emu.write_byte(JOHTO_BADGES, 0x00)
        badges = self.reader.read_badges()
        self.assertEqual(badges.count(), 0)

    def test_first_badge(self):
        self.emu.write_byte(JOHTO_BADGES, 0x01)
        badges = self.reader.read_badges()
        self.assertTrue(badges.zephyr)
        self.assertFalse(badges.hive)
        self.assertEqual(badges.count(), 1)

    def test_all_badges(self):
        self.emu.write_byte(JOHTO_BADGES, 0xFF)
        badges = self.reader.read_badges()
        self.assertTrue(badges.all_johto())
        self.assertEqual(badges.count(), 8)

    def test_specific_badges(self):
        # Zephyr + Plain + Storm = 0x01 | 0x04 | 0x10 = 0x15
        self.emu.write_byte(JOHTO_BADGES, 0x15)
        badges = self.reader.read_badges()
        self.assertTrue(badges.zephyr)
        self.assertFalse(badges.hive)
        self.assertTrue(badges.plain)
        self.assertFalse(badges.fog)
        self.assertTrue(badges.storm)
        self.assertEqual(badges.count(), 3)


class TestMemoryReaderMoney(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_zero_money(self):
        for i in range(3):
            self.emu.write_byte(MONEY_ADDR + i, 0x00)
        self.assertEqual(self.reader.read_money(), 0)

    def test_starter_money(self):
        # 3000 = BCD 0x00, 0x30, 0x00
        self.emu.write_byte(MONEY_ADDR, 0x00)
        self.emu.write_byte(MONEY_ADDR + 1, 0x30)
        self.emu.write_byte(MONEY_ADDR + 2, 0x00)
        self.assertEqual(self.reader.read_money(), 3000)

    def test_max_money(self):
        for i in range(3):
            self.emu.write_byte(MONEY_ADDR + i, 0x99)
        self.assertEqual(self.reader.read_money(), 999999)


class TestMemoryReaderPlayTime(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_zero_time(self):
        self.emu.write_byte(PLAY_TIME_HOURS, 0)
        self.emu.write_byte(PLAY_TIME_HOURS + 1, 0)
        self.emu.write_byte(PLAY_TIME_MINUTES, 0)
        self.assertEqual(self.reader.read_play_time_minutes(), 0)

    def test_one_hour(self):
        self.emu.write_byte(PLAY_TIME_HOURS, 1)  # low byte
        self.emu.write_byte(PLAY_TIME_HOURS + 1, 0)  # high byte
        self.emu.write_byte(PLAY_TIME_MINUTES, 30)
        self.assertEqual(self.reader.read_play_time_minutes(), 90)


class TestMemoryReaderFullState(unittest.TestCase):
    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = MemoryReader(self.emu)

    def tearDown(self):
        self.emu.close()

    def test_read_game_state(self):
        # Set up minimal state
        self.emu.write_byte(PARTY_COUNT, 1)
        base = PARTY_DATA_START
        self.emu.write_byte(base + OFF_SPECIES, 155)  # Cyndaquil
        self.emu.write_byte(base + OFF_LEVEL, 5)
        self.emu.write_byte(base + OFF_HP_HI, 0)
        self.emu.write_byte(base + OFF_HP_LO, 20)
        self.emu.write_byte(base + OFF_HP_MAX_HI, 0)
        self.emu.write_byte(base + OFF_HP_MAX_LO, 20)
        self.emu.write_byte(BATTLE_MODE, 0)
        self.emu.write_byte(JOHTO_BADGES, 0x00)
        self.emu.write_byte(STEP_COUNT, 42)

        state = self.reader.read_game_state()
        self.assertIsInstance(state, GameState)
        self.assertEqual(state.party.size(), 1)
        self.assertEqual(state.party.lead().species, "Cyndaquil")
        self.assertFalse(state.is_in_battle())
        self.assertEqual(state.badges.count(), 0)
        self.assertEqual(state.step_count, 42)

    def test_full_state_returns_all_fields(self):
        self.emu.write_byte(PARTY_COUNT, 0)
        self.emu.write_byte(BATTLE_MODE, 0)
        state = self.reader.read_game_state()
        self.assertIsNotNone(state.party)
        self.assertIsNotNone(state.position)
        self.assertIsNotNone(state.battle)
        self.assertIsNotNone(state.badges)
        self.assertIsInstance(state.money, int)
        self.assertIsInstance(state.play_time_minutes, int)
        self.assertIsInstance(state.step_count, int)


class TestMenuStateDetection(unittest.TestCase):
    """Test menu/UI state detection from RAM."""

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.reader = MemoryReader(self.emu)

    def test_overworld_default(self):
        """All flags zero = overworld."""
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.OVERWORLD)

    def test_battle_detected(self):
        """BATTLE_MODE > 0 = battle."""
        self.emu.write_byte(BATTLE_MODE, 1)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.BATTLE)

    def test_trainer_battle_detected(self):
        """BATTLE_MODE = 2 = trainer battle."""
        self.emu.write_byte(BATTLE_MODE, 2)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.BATTLE)

    def test_shop_detected(self):
        """MART_POINTER > 0 = shop."""
        self.emu.write_byte(MART_POINTER, 5)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.SHOP)

    def test_joy_disabled_is_overworld_in_crystal(self):
        """JOY_DISABLED has non-zero values during normal Crystal overworld (S208 finding)."""
        self.emu.write_byte(JOY_DISABLED, 146)  # Normal Crystal overworld value
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.OVERWORLD)

    def test_window_stack_is_overworld_in_crystal(self):
        """WINDOW_STACK_SIZE has non-zero values during normal Crystal overworld (S208 finding)."""
        self.emu.write_byte(WINDOW_STACK_SIZE, 10)
        self.emu.write_byte(TEXT_BOX_FLAGS, 190)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.OVERWORLD)

    def test_window_stack_alone_is_overworld(self):
        """Window stack alone does not trigger menu — unreliable in Crystal."""
        self.emu.write_byte(WINDOW_STACK_SIZE, 1)
        self.emu.write_byte(TEXT_BOX_FLAGS, 0)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.OVERWORLD)

    def test_battle_takes_priority_over_shop(self):
        """Battle mode overrides shop flag."""
        self.emu.write_byte(BATTLE_MODE, 1)
        self.emu.write_byte(MART_POINTER, 5)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.BATTLE)

    def test_shop_takes_priority_over_menu(self):
        """Shop overrides window/menu flags."""
        self.emu.write_byte(MART_POINTER, 3)
        self.emu.write_byte(WINDOW_STACK_SIZE, 1)
        state = self.reader.read_menu_state()
        self.assertEqual(state, MenuState.SHOP)

    def test_game_state_includes_menu(self):
        """read_game_state includes menu_state field."""
        self.emu.write_byte(PARTY_COUNT, 0)
        state = self.reader.read_game_state()
        self.assertEqual(state.menu_state, MenuState.OVERWORLD)

    def test_game_state_window_flags_are_overworld(self):
        """read_game_state returns overworld even with window flags set (S208 Crystal fix)."""
        self.emu.write_byte(PARTY_COUNT, 0)
        self.emu.write_byte(WINDOW_STACK_SIZE, 2)
        self.emu.write_byte(TEXT_BOX_FLAGS, 1)
        state = self.reader.read_game_state()
        self.assertEqual(state.menu_state, MenuState.OVERWORLD)


if __name__ == "__main__":
    unittest.main()
