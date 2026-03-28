"""Pokemon Crystal RAM memory reader.

Reads game state from emulator RAM addresses and converts to GameState
dataclasses. This is the bridge between raw emulator bytes and the
structured game_state.py types.

RAM addresses sourced from:
- pokecrystal disassembly: https://github.com/pret/pokecrystal
- Crystal RAM map: wram.asm / hram.asm

Usage:
    from emulator_control import EmulatorControl
    from memory_reader import MemoryReader

    emu = EmulatorControl.from_rom("crystal.gbc")
    reader = MemoryReader(emu)
    state = reader.read_game_state()
    print(state.party.lead().species)

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import List, Optional

from emulator_control import EmulatorControl
from game_state import (
    Badges,
    BattleState,
    GameState,
    MapPosition,
    MenuState,
    Move,
    Party,
    Pokemon,
)


# ── Pokemon Crystal RAM Addresses ────────────────────────────────────────────
# Source: pret/pokecrystal wram.asm

# Party data
PARTY_COUNT = 0xDCD7
PARTY_SPECIES_START = 0xDCD8  # 6 bytes, one per slot
PARTY_DATA_START = 0xDCDF     # 48 bytes per Pokemon, 6 slots

# Party Pokemon struct offsets (within each 48-byte block)
OFF_SPECIES = 0
OFF_HELD_ITEM = 1
OFF_MOVE1 = 2
OFF_MOVE2 = 3
OFF_MOVE3 = 4
OFF_MOVE4 = 5
OFF_LEVEL = 31
OFF_STATUS = 32
OFF_HP_HI = 34
OFF_HP_LO = 35
OFF_HP_MAX_HI = 36
OFF_HP_MAX_LO = 37
OFF_ATTACK_HI = 38
OFF_ATTACK_LO = 39
OFF_DEFENSE_HI = 40
OFF_DEFENSE_LO = 41
OFF_SPEED_HI = 42
OFF_SPEED_LO = 43
OFF_SP_ATK_HI = 44
OFF_SP_ATK_LO = 45
OFF_SP_DEF_HI = 46
OFF_SP_DEF_LO = 47
PARTY_MON_SIZE = 48

# PP (separate block after main party data)
PARTY_PP_START = 0xDD17  # 4 bytes per mon (PP for moves 1-4)
PARTY_PP_MON_SIZE = 4

# Nicknames
PARTY_NICKNAMES_START = 0xDE41  # 11 bytes per nickname, 6 slots
NICKNAME_SIZE = 11

# Map / position
MAP_GROUP = 0xDCB5
MAP_NUMBER = 0xDCB6
PLAYER_X = 0xDCB8
PLAYER_Y = 0xDCB7

# Battle state
BATTLE_MODE = 0xD22D    # 0 = not in battle, 1 = wild, 2 = trainer
ENEMY_MON_SPECIES = 0xD206
ENEMY_MON_LEVEL = 0xD213
ENEMY_MON_HP_HI = 0xD214
ENEMY_MON_HP_LO = 0xD215
ENEMY_MON_HP_MAX_HI = 0xD216
ENEMY_MON_HP_MAX_LO = 0xD217
ENEMY_MON_STATUS = 0xD218

# Badges
JOHTO_BADGES = 0xD57C   # bit flags: bit 0 = Zephyr, bit 7 = Rising

# Money (3 bytes, BCD)
MONEY_ADDR = 0xD84E  # 3 bytes, big-endian BCD

# Play time
PLAY_TIME_HOURS = 0xD4C4    # 2 bytes, little-endian
PLAY_TIME_MINUTES = 0xD4C6  # 1 byte

# Step counter
STEP_COUNT = 0xD4C7  # 1 byte (wraps at 256)

# Menu / UI state detection
# Source: pret/pokecrystal wram.asm
WINDOW_STACK_SIZE = 0xCF85  # >0 when a text/menu window is open
TEXT_BOX_FLAGS = 0xCF86      # Text box state flags
MART_POINTER = 0xD100        # Non-zero when in mart/shop
JOY_DISABLED = 0xCFA0        # Joypad disable flags (set during transitions/healing)


# ── Character encoding (Pokemon text → ASCII) ───────────────────────────────

# Pokemon Crystal uses a custom character encoding, not ASCII
# This is a partial map covering common characters
CHAR_MAP = {
    0x50: "\0",  # string terminator
    0x7F: " ",
    0x80: "A", 0x81: "B", 0x82: "C", 0x83: "D", 0x84: "E",
    0x85: "F", 0x86: "G", 0x87: "H", 0x88: "I", 0x89: "J",
    0x8A: "K", 0x8B: "L", 0x8C: "M", 0x8D: "N", 0x8E: "O",
    0x8F: "P", 0x90: "Q", 0x91: "R", 0x92: "S", 0x93: "T",
    0x94: "U", 0x95: "V", 0x96: "W", 0x97: "X", 0x98: "Y",
    0x99: "Z",
    0xA0: "a", 0xA1: "b", 0xA2: "c", 0xA3: "d", 0xA4: "e",
    0xA5: "f", 0xA6: "g", 0xA7: "h", 0xA8: "i", 0xA9: "j",
    0xAA: "k", 0xAB: "l", 0xAC: "m", 0xAD: "n", 0xAE: "o",
    0xAF: "p", 0xB0: "q", 0xB1: "r", 0xB2: "s", 0xB3: "t",
    0xB4: "u", 0xB5: "v", 0xB6: "w", 0xB7: "x", 0xB8: "y",
    0xB9: "z",
    0xE0: "'",
    0xE3: "-",
    0xF2: "0", 0xF3: "1", 0xF4: "2", 0xF5: "3", 0xF6: "4",
    0xF7: "5", 0xF8: "6", 0xF9: "7", 0xFA: "8", 0xFB: "9",
}


# ── Data tables (complete — ported from reference repos, S218) ────────────────
# All 251 species, 251 moves, Crystal items, map names, move data
# Source: crystal_data.py (ported from pokemon-agent reference repo + Gen 2 extension)

from crystal_data import (
    SPECIES_NAMES, MOVE_NAMES, MOVE_DATA, ITEM_NAMES, TYPE_NAMES,
    MAP_NAMES, get_move_info, get_map_name,
)


# ── Status condition decoding ────────────────────────────────────────────────

def decode_status(status_byte: int) -> str:
    """Decode Pokemon status condition from RAM byte."""
    if status_byte == 0:
        return "healthy"
    if status_byte & 0x07:  # bits 0-2: sleep counter
        return "asleep"
    if status_byte & 0x08:
        return "poisoned"
    if status_byte & 0x10:
        return "burned"
    if status_byte & 0x20:
        return "frozen"
    if status_byte & 0x40:
        return "paralyzed"
    return "healthy"


def decode_text(data: bytes) -> str:
    """Decode Pokemon text encoding to ASCII string."""
    result = []
    for b in data:
        if b == 0x50:  # terminator
            break
        ch = CHAR_MAP.get(b, "?")
        result.append(ch)
    return "".join(result).strip()


def decode_bcd(data: bytes) -> int:
    """Decode BCD-encoded bytes to integer (big-endian)."""
    result = 0
    for b in data:
        result = result * 100 + ((b >> 4) * 10) + (b & 0x0F)
    return result


# ── MemoryReader ─────────────────────────────────────────────────────────────


class MemoryReader:
    """Reads Pokemon Crystal game state from emulator RAM."""

    def __init__(self, emu: EmulatorControl):
        self._emu = emu

    def read_party_count(self) -> int:
        """Number of Pokemon in the party (0-6)."""
        count = self._emu.read_byte(PARTY_COUNT)
        return min(count, 6)

    def read_pokemon(self, slot: int) -> Pokemon:
        """Read a party Pokemon from RAM (slot 0-5)."""
        base = PARTY_DATA_START + (slot * PARTY_MON_SIZE)

        species_id = self._emu.read_byte(base + OFF_SPECIES)
        species_name = SPECIES_NAMES.get(species_id, f"Pokemon#{species_id}")

        # Read nickname
        nick_base = PARTY_NICKNAMES_START + (slot * NICKNAME_SIZE)
        nick_bytes = self._emu.read_bytes(nick_base, NICKNAME_SIZE)
        nickname = decode_text(nick_bytes)

        # Read stats (big-endian 16-bit values)
        level = self._emu.read_byte(base + OFF_LEVEL)
        hp = self._emu.read_word_be(base + OFF_HP_HI)
        hp_max = self._emu.read_word_be(base + OFF_HP_MAX_HI)
        attack = self._emu.read_word_be(base + OFF_ATTACK_HI)
        defense = self._emu.read_word_be(base + OFF_DEFENSE_HI)
        speed = self._emu.read_word_be(base + OFF_SPEED_HI)
        sp_atk = self._emu.read_word_be(base + OFF_SP_ATK_HI)
        sp_def = self._emu.read_word_be(base + OFF_SP_DEF_HI)

        # Status
        status = decode_status(self._emu.read_byte(base + OFF_STATUS))

        # Held item (full name from crystal_data — ported S218)
        held_item_id = self._emu.read_byte(base + OFF_HELD_ITEM)
        held_item = ITEM_NAMES.get(held_item_id, f"item#{held_item_id}") if held_item_id > 0 else ""

        # Moves (with full data from crystal_data — ported S218)
        moves = []
        pp_base = PARTY_PP_START + (slot * PARTY_PP_MON_SIZE)
        for i in range(4):
            move_id = self._emu.read_byte(base + OFF_MOVE1 + i)
            if move_id == 0:
                continue
            pp = self._emu.read_byte(pp_base + i) & 0x3F  # lower 6 bits = current PP
            name, mtype, power, acc, cat = get_move_info(move_id)
            moves.append(Move(
                name=name,
                move_type=mtype,
                power=power,
                accuracy=acc,
                pp=pp,
                pp_max=pp,
                category=cat,
            ))

        return Pokemon(
            species=species_name,
            nickname=nickname,
            level=level,
            hp=hp,
            hp_max=hp_max,
            attack=attack,
            defense=defense,
            speed=speed,
            sp_attack=sp_atk,
            sp_defense=sp_def,
            moves=moves,
            status=status,
            held_item=held_item,
        )

    def read_party(self) -> Party:
        """Read the full party from RAM."""
        count = self.read_party_count()
        pokemon = [self.read_pokemon(i) for i in range(count)]
        return Party(pokemon=pokemon)

    def read_position(self) -> MapPosition:
        """Read player map position (with map name from crystal_data)."""
        map_group = self._emu.read_byte(MAP_GROUP)
        map_number = self._emu.read_byte(MAP_NUMBER)
        x = self._emu.read_byte(PLAYER_X)
        y = self._emu.read_byte(PLAYER_Y)
        # Composite ID for unique map identification
        map_id = (map_group << 8) | map_number
        return MapPosition(
            map_id=map_id,
            map_group=map_group,
            map_number=map_number,
            x=x,
            y=y,
            map_name=get_map_name(map_group, map_number),
        )

    def read_battle_state(self) -> BattleState:
        """Read current battle state."""
        mode = self._emu.read_byte(BATTLE_MODE)
        if mode == 0:
            return BattleState(in_battle=False)

        enemy_species_id = self._emu.read_byte(ENEMY_MON_SPECIES)
        enemy_name = SPECIES_NAMES.get(enemy_species_id, f"Pokemon#{enemy_species_id}")
        enemy_level = self._emu.read_byte(ENEMY_MON_LEVEL)
        enemy_hp = self._emu.read_word_be(ENEMY_MON_HP_HI)
        enemy_hp_max = self._emu.read_word_be(ENEMY_MON_HP_MAX_HI)
        enemy_status = decode_status(self._emu.read_byte(ENEMY_MON_STATUS))

        enemy = Pokemon(
            species=enemy_name,
            nickname=enemy_name,
            level=enemy_level,
            hp=enemy_hp,
            hp_max=enemy_hp_max,
            attack=0, defense=0, speed=0, sp_attack=0, sp_defense=0,
            status=enemy_status,
        )

        return BattleState(
            in_battle=True,
            is_wild=(mode == 1),
            is_trainer=(mode == 2),
            enemy=enemy,
        )

    def read_badges(self) -> Badges:
        """Read gym badge flags."""
        flags = self._emu.read_byte(JOHTO_BADGES)
        return Badges(
            zephyr=bool(flags & 0x01),
            hive=bool(flags & 0x02),
            plain=bool(flags & 0x04),
            fog=bool(flags & 0x08),
            storm=bool(flags & 0x10),
            mineral=bool(flags & 0x20),
            glacier=bool(flags & 0x40),
            rising=bool(flags & 0x80),
        )

    def read_money(self) -> int:
        """Read player's money (BCD encoded, 3 bytes)."""
        data = self._emu.read_bytes(MONEY_ADDR, 3)
        return decode_bcd(data)

    def read_play_time_minutes(self) -> int:
        """Read total play time in minutes."""
        hours = self._emu.read_word(PLAY_TIME_HOURS)
        minutes = self._emu.read_byte(PLAY_TIME_MINUTES)
        return hours * 60 + minutes

    def read_menu_state(self) -> MenuState:
        """Detect current UI mode from RAM flags.

        Priority: battle > shop > overworld (default).

        Note: WINDOW_STACK_SIZE (0xCF85), TEXT_BOX_FLAGS (0xCF86), and
        JOY_DISABLED (0xCFA0) have non-zero values during normal Crystal
        overworld gameplay. They cannot reliably distinguish dialog/menu
        from overworld. Only battle mode is reliably detectable from RAM.
        """
        battle_mode = self._emu.read_byte(BATTLE_MODE)
        if battle_mode > 0:
            return MenuState.BATTLE

        # Shop detection — mart pointer is reliable
        mart_ptr = self._emu.read_byte(MART_POINTER)
        if mart_ptr > 0:
            return MenuState.SHOP

        # Default to overworld — unreliable flags removed (S208 finding:
        # JOY_DISABLED=146 and WINDOW_STACK=10 are normal overworld values)
        return MenuState.OVERWORLD

    def read_game_state(self) -> GameState:
        """Read complete game state snapshot from RAM."""
        return GameState(
            party=self.read_party(),
            position=self.read_position(),
            battle=self.read_battle_state(),
            badges=self.read_badges(),
            money=self.read_money(),
            play_time_minutes=self.read_play_time_minutes(),
            step_count=self._emu.read_byte(STEP_COUNT),
            menu_state=self.read_menu_state(),
        )
