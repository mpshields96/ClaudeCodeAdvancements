"""Pokemon Red RAM memory reader.

Reads game state from emulator RAM addresses and converts to GameState
dataclasses. Adapted from ClaudePlaysPokemonStarter's PokemonRedReader
with our GameState interface.

RAM addresses sourced from:
- pokered disassembly: https://github.com/pret/pokered
- ClaudePlaysPokemonStarter/agent/memory_reader.py

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import List, Optional

from emulator_control import EmulatorControl
from move_data import get_move_data
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

# ── Pokemon Red RAM Addresses ────────────────────────────────────────────
# Source: pret/pokered wram.asm

# Player
PLAYER_NAME = 0xD158       # 11 bytes (0x50 terminated)
RIVAL_NAME = 0xD34A        # 7 bytes
MONEY_ADDR = 0xD347        # 3 bytes BCD (MSB first)
BADGES_ADDR = 0xD356       # 1 byte, 8 bits
PLAY_TIME_HOURS_H = 0xDA40
PLAY_TIME_HOURS_L = 0xDA41
PLAY_TIME_MINUTES = 0xDA42
PLAY_TIME_SECONDS = 0xDA44

# Map / Position
MAP_ID = 0xD35E            # Current map number
MAP_TILESET = 0xD367       # Tileset ID
PLAYER_Y = 0xD361          # Y coordinate on map
PLAYER_X = 0xD362          # X coordinate on map
PLAYER_DIR = 0xD52A        # Facing direction (0=down, 4=up, 8=left, 0xC=right)

# Party
PARTY_COUNT = 0xD163       # Number of Pokemon in party
PARTY_BASE_ADDRS = [0xD16B, 0xD197, 0xD1C3, 0xD1EF, 0xD21B, 0xD247]
PARTY_NICK_ADDRS = [0xD2B5, 0xD2C0, 0xD2CB, 0xD2D6, 0xD2E1, 0xD2EC]

# Party Pokemon struct offsets (Gen 1 — 44 bytes per Pokemon)
OFF_SPECIES = 0
OFF_HP_HI = 1
OFF_HP_LO = 2
OFF_STATUS = 4
OFF_TYPE1 = 5
OFF_TYPE2 = 6
OFF_MOVE1 = 8
OFF_MOVE2 = 9
OFF_MOVE3 = 10
OFF_MOVE4 = 11
OFF_TRAINER_ID_HI = 12
OFF_TRAINER_ID_LO = 13
OFF_EXP_HI = 0x1A
OFF_EXP_MID = 0x1B
OFF_EXP_LO = 0x1C
OFF_PP1 = 0x1D
OFF_PP2 = 0x1E
OFF_PP3 = 0x1F
OFF_PP4 = 0x20
OFF_LEVEL = 0x21
OFF_MAX_HP_HI = 0x22
OFF_MAX_HP_LO = 0x23
OFF_ATTACK_HI = 0x24
OFF_ATTACK_LO = 0x25
OFF_DEFENSE_HI = 0x26
OFF_DEFENSE_LO = 0x27
OFF_SPEED_HI = 0x28
OFF_SPEED_LO = 0x29
OFF_SPECIAL_HI = 0x2A  # Gen 1: unified Special stat
OFF_SPECIAL_LO = 0x2B

# Battle
BATTLE_MODE = 0xD057       # 0=none, 1=wild, 2=trainer (wIsInBattle)
ENEMY_MON_SPECIES = 0xCFE5  # Active enemy species
ENEMY_MON_HP_HI = 0xCFE6
ENEMY_MON_HP_LO = 0xCFE7
ENEMY_MON_LEVEL = 0xCFF3
ENEMY_MON_MAX_HP_HI = 0xCFF4
ENEMY_MON_MAX_HP_LO = 0xCFF5
ENEMY_MON_STATUS = 0xCFE9

# Menu / Dialog
TEXTBOX_ID = 0xD125        # 0 = no text box
JOY_DISABLED = 0xD730      # bit 0 = joypad disabled (dialog active)

# Items
ITEM_COUNT = 0xD31D
ITEM_START = 0xD31E        # pairs of (item_id, quantity)

# ── Text encoding (Gen 1 charset) ────────────────────────────────────────

def decode_text(data: bytes | list) -> str:
    """Decode Pokemon Red text encoding to ASCII."""
    result = []
    for b in data:
        if b == 0x50:  # String terminator
            break
        elif b == 0x7F:
            result.append(" ")
        elif 0x80 <= b <= 0x99:  # A-Z
            result.append(chr(b - 0x80 + ord("A")))
        elif 0xA0 <= b <= 0xB9:  # a-z
            result.append(chr(b - 0xA0 + ord("a")))
        elif 0xF6 <= b <= 0xFF:  # 0-9
            result.append(str(b - 0xF6))
        elif b == 0xE0:
            result.append("'")
        elif b == 0xE3:
            result.append("-")
        elif b == 0xE6:
            result.append("?")
        elif b == 0xE7:
            result.append("!")
        elif b == 0xE8:
            result.append(".")
        elif b == 0xF3:
            result.append("/")
        elif b == 0xF4:
            result.append(",")
        elif b == 0xBA:
            result.append("e")  # é simplified
        elif b == 0x4E:
            result.append(" ")  # newline -> space
    return "".join(result).strip()


# ── Species ID → Name (Gen 1 internal order) ─────────────────────────────

SPECIES_NAMES = {
    0x01: "RHYDON", 0x02: "KANGASKHAN", 0x03: "NIDORAN_M", 0x04: "CLEFAIRY",
    0x05: "SPEAROW", 0x06: "VOLTORB", 0x07: "NIDOKING", 0x08: "SLOWBRO",
    0x09: "IVYSAUR", 0x0A: "EXEGGUTOR", 0x0B: "LICKITUNG", 0x0C: "EXEGGCUTE",
    0x0D: "GRIMER", 0x0E: "GENGAR", 0x0F: "NIDORAN_F", 0x10: "NIDOQUEEN",
    0x11: "CUBONE", 0x12: "RHYHORN", 0x13: "LAPRAS", 0x14: "ARCANINE",
    0x15: "MEW", 0x16: "GYARADOS", 0x17: "SHELLDER", 0x18: "TENTACOOL",
    0x19: "GASTLY", 0x1A: "SCYTHER", 0x1B: "STARYU", 0x1C: "BLASTOISE",
    0x1D: "PINSIR", 0x1E: "TANGELA", 0x21: "GROWLITHE", 0x22: "ONIX",
    0x23: "FEAROW", 0x24: "PIDGEY", 0x25: "SLOWPOKE", 0x26: "KADABRA",
    0x27: "GRAVELER", 0x28: "CHANSEY", 0x29: "MACHOKE", 0x2A: "MR_MIME",
    0x2B: "HITMONLEE", 0x2C: "HITMONCHAN", 0x2D: "ARBOK", 0x2E: "PARASECT",
    0x2F: "PSYDUCK", 0x30: "DROWZEE", 0x31: "GOLEM", 0x33: "MAGMAR",
    0x35: "ELECTABUZZ", 0x36: "MAGNETON", 0x37: "KOFFING", 0x39: "MANKEY",
    0x3A: "SEEL", 0x3B: "DIGLETT", 0x3C: "TAUROS", 0x40: "FARFETCHD",
    0x41: "VENONAT", 0x42: "DRAGONITE", 0x46: "DODUO", 0x47: "POLIWAG",
    0x48: "JYNX", 0x49: "MOLTRES", 0x4A: "ARTICUNO", 0x4B: "ZAPDOS",
    0x4C: "DITTO", 0x4D: "MEOWTH", 0x4E: "KRABBY", 0x52: "VULPIX",
    0x53: "NINETALES", 0x54: "PIKACHU", 0x55: "RAICHU", 0x58: "DRATINI",
    0x59: "DRAGONAIR", 0x5A: "KABUTO", 0x5B: "KABUTOPS", 0x5C: "HORSEA",
    0x5D: "SEADRA", 0x60: "SANDSHREW", 0x61: "SANDSLASH", 0x62: "OMANYTE",
    0x63: "OMASTAR", 0x65: "JIGGLYPUFF", 0x66: "WIGGLYTUFF",
    0x67: "EEVEE", 0x68: "FLAREON", 0x69: "JOLTEON", 0x6A: "VAPOREON",
    0x6B: "MACHOP", 0x6C: "ZUBAT", 0x6D: "EKANS", 0x6E: "PARAS",
    0x6F: "POLIWHIRL", 0x70: "POLIWRATH", 0x71: "WEEDLE", 0x72: "KAKUNA",
    0x73: "BEEDRILL", 0x76: "DODRIO", 0x77: "PRIMEAPE", 0x78: "DUGTRIO",
    0x79: "VENOMOTH", 0x7A: "DEWGONG", 0x7B: "CATERPIE", 0x7C: "METAPOD",
    0x7D: "BUTTERFREE", 0x7E: "MACHAMP", 0x80: "GOLDUCK", 0x81: "HYPNO",
    0x82: "GOLBAT", 0x83: "MEWTWO", 0x84: "SNORLAX", 0x85: "MAGIKARP",
    0x88: "MUK", 0x8A: "KINGLER", 0x8B: "CLOYSTER", 0x8D: "ELECTRODE",
    0x8E: "CLEFABLE", 0x8F: "WEEZING", 0x90: "PERSIAN", 0x91: "MAROWAK",
    0x93: "HAUNTER", 0x94: "ABRA", 0x95: "ALAKAZAM", 0x96: "PIDGEOTTO",
    0x97: "PIDGEOT", 0x98: "STARMIE", 0x99: "BULBASAUR", 0x9A: "VENUSAUR",
    0x9B: "TENTACRUEL", 0x9D: "GOLDEEN", 0x9E: "SEAKING",
    0xA3: "PONYTA", 0xA4: "RAPIDASH", 0xA5: "RATTATA", 0xA6: "RATICATE",
    0xA7: "NIDORINO", 0xA8: "NIDORINA", 0xA9: "GEODUDE",
    0xAA: "PORYGON", 0xAB: "AERODACTYL", 0xAD: "MAGNEMITE",
    0xB0: "CHARMANDER", 0xB1: "SQUIRTLE", 0xB2: "CHARMELEON",
    0xB3: "WARTORTLE", 0xB4: "CHARIZARD", 0xB9: "ODDISH",
    0xBA: "GLOOM", 0xBB: "VILEPLUME", 0xBC: "BELLSPROUT",
    0xBD: "WEEPINBELL", 0xBE: "VICTREEBEL",
}

# ── Move ID → Name (Gen 1) ───────────────────────────────────────────────

MOVE_NAMES = {
    0x01: "POUND", 0x02: "KARATE CHOP", 0x03: "DOUBLE SLAP", 0x04: "COMET PUNCH",
    0x05: "MEGA PUNCH", 0x06: "PAY DAY", 0x07: "FIRE PUNCH", 0x08: "ICE PUNCH",
    0x09: "THUNDER PUNCH", 0x0A: "SCRATCH", 0x0B: "VICE GRIP", 0x0C: "GUILLOTINE",
    0x0D: "RAZOR WIND", 0x0E: "SWORDS DANCE", 0x0F: "CUT", 0x10: "GUST",
    0x11: "WING ATTACK", 0x12: "WHIRLWIND", 0x13: "FLY", 0x14: "BIND",
    0x15: "SLAM", 0x16: "VINE WHIP", 0x17: "STOMP", 0x18: "DOUBLE KICK",
    0x19: "MEGA KICK", 0x1A: "JUMP KICK", 0x1B: "ROLLING KICK",
    0x1C: "SAND ATTACK", 0x1D: "HEADBUTT", 0x1E: "HORN ATTACK",
    0x1F: "FURY ATTACK", 0x20: "HORN DRILL", 0x21: "TACKLE", 0x22: "BODY SLAM",
    0x23: "WRAP", 0x24: "TAKE DOWN", 0x25: "THRASH", 0x26: "DOUBLE EDGE",
    0x27: "TAIL WHIP", 0x28: "POISON STING", 0x29: "TWINEEDLE",
    0x2A: "PIN MISSILE", 0x2B: "LEER", 0x2C: "BITE", 0x2D: "GROWL",
    0x2E: "ROAR", 0x2F: "SING", 0x30: "SUPERSONIC", 0x31: "SONIC BOOM",
    0x32: "DISABLE", 0x33: "ACID", 0x34: "EMBER", 0x35: "FLAMETHROWER",
    0x36: "MIST", 0x37: "WATER GUN", 0x38: "HYDRO PUMP", 0x39: "SURF",
    0x3A: "ICE BEAM", 0x3B: "BLIZZARD", 0x3C: "PSYBEAM", 0x3D: "BUBBLE BEAM",
    0x3E: "AURORA BEAM", 0x3F: "HYPER BEAM", 0x40: "PECK", 0x41: "DRILL PECK",
    0x42: "SUBMISSION", 0x43: "LOW KICK", 0x44: "COUNTER", 0x45: "SEISMIC TOSS",
    0x46: "STRENGTH", 0x47: "ABSORB", 0x48: "MEGA DRAIN", 0x49: "LEECH SEED",
    0x4A: "GROWTH", 0x4B: "RAZOR LEAF", 0x4C: "SOLAR BEAM",
    0x4D: "POISON POWDER", 0x4E: "STUN SPORE", 0x4F: "SLEEP POWDER",
    0x50: "PETAL DANCE", 0x51: "STRING SHOT", 0x52: "DRAGON RAGE",
    0x53: "FIRE SPIN", 0x54: "THUNDER SHOCK", 0x55: "THUNDERBOLT",
    0x56: "THUNDER WAVE", 0x57: "THUNDER", 0x58: "ROCK THROW",
    0x59: "EARTHQUAKE", 0x5A: "FISSURE", 0x5B: "DIG", 0x5C: "TOXIC",
    0x5D: "CONFUSION", 0x5E: "PSYCHIC", 0x5F: "HYPNOSIS", 0x60: "MEDITATE",
    0x61: "AGILITY", 0x62: "QUICK ATTACK", 0x63: "RAGE", 0x64: "TELEPORT",
    0x65: "NIGHT SHADE", 0x66: "MIMIC", 0x67: "SCREECH", 0x68: "DOUBLE TEAM",
    0x69: "RECOVER", 0x6A: "HARDEN", 0x6B: "MINIMIZE", 0x6C: "SMOKESCREEN",
    0x6D: "CONFUSE RAY", 0x6E: "WITHDRAW", 0x6F: "DEFENSE CURL",
    0x70: "BARRIER", 0x71: "LIGHT SCREEN", 0x72: "HAZE", 0x73: "REFLECT",
    0x74: "FOCUS ENERGY", 0x75: "BIDE", 0x76: "METRONOME",
    0x77: "MIRROR MOVE", 0x78: "SELF DESTRUCT", 0x79: "EGG BOMB",
    0x7A: "LICK", 0x7B: "SMOG", 0x7C: "SLUDGE", 0x7D: "BONE CLUB",
    0x7E: "FIRE BLAST", 0x7F: "WATERFALL", 0x80: "CLAMP", 0x81: "SWIFT",
    0x82: "SKULL BASH", 0x83: "SPIKE CANNON", 0x84: "CONSTRICT",
    0x85: "AMNESIA", 0x86: "KINESIS", 0x87: "SOFT BOILED", 0x88: "HI JUMP KICK",
    0x89: "GLARE", 0x8A: "DREAM EATER", 0x8B: "POISON GAS",
    0x8C: "BARRAGE", 0x8D: "LEECH LIFE", 0x8E: "LOVELY KISS",
    0x8F: "SKY ATTACK", 0x90: "TRANSFORM", 0x91: "BUBBLE",
    0x92: "DIZZY PUNCH", 0x93: "SPORE", 0x94: "FLASH", 0x95: "PSYWAVE",
    0x96: "SPLASH", 0x97: "ACID ARMOR", 0x98: "CRABHAMMER",
    0x99: "EXPLOSION", 0x9A: "FURY SWIPES", 0x9B: "BONEMERANG",
    0x9C: "REST", 0x9D: "ROCK SLIDE", 0x9E: "HYPER FANG",
    0x9F: "SHARPEN", 0xA0: "CONVERSION", 0xA1: "TRI ATTACK",
    0xA2: "SUPER FANG", 0xA3: "SLASH", 0xA4: "SUBSTITUTE",
    0xA5: "STRUGGLE",
}

# ── Map ID → Name (Gen 1 — 256 maps) ─────────────────────────────────────

MAP_NAMES = {
    0: "PALLET TOWN", 1: "VIRIDIAN CITY", 2: "PEWTER CITY",
    3: "CERULEAN CITY", 4: "LAVENDER TOWN", 5: "VERMILION CITY",
    6: "CELADON CITY", 7: "FUCHSIA CITY", 8: "CINNABAR ISLAND",
    9: "INDIGO PLATEAU", 10: "SAFFRON CITY", 12: "ROUTE 1",
    13: "ROUTE 2", 14: "ROUTE 3", 15: "ROUTE 4", 16: "ROUTE 5",
    17: "ROUTE 6", 18: "ROUTE 7", 19: "ROUTE 8", 20: "ROUTE 9",
    21: "ROUTE 10", 22: "ROUTE 11", 23: "ROUTE 12", 24: "ROUTE 13",
    25: "ROUTE 14", 26: "ROUTE 15", 27: "ROUTE 16", 28: "ROUTE 17",
    29: "ROUTE 18", 30: "ROUTE 19", 31: "ROUTE 20", 32: "ROUTE 21",
    33: "ROUTE 22", 34: "ROUTE 23", 35: "ROUTE 24", 36: "ROUTE 25",
    37: "REDS HOUSE 1F", 38: "REDS HOUSE 2F", 39: "BLUES HOUSE",
    40: "OAKS LAB", 41: "VIRIDIAN POKECENTER", 42: "VIRIDIAN MART",
    43: "VIRIDIAN SCHOOL", 44: "VIRIDIAN GYM",
    45: "DIGLETTS CAVE ENTRANCE", 46: "VIRIDIAN FOREST ENTRANCE",
    47: "ROUTE 2 GATE", 48: "VIRIDIAN FOREST EXIT",
    49: "ROUTE 2 EAST", 50: "PEWTER MUSEUM 1F", 51: "PEWTER MUSEUM 2F",
    52: "PEWTER GYM", 53: "PEWTER MART", 54: "PEWTER POKECENTER",
    55: "MT MOON 1F", 56: "MT MOON B1F", 57: "MT MOON B2F",
    58: "CERULEAN POKECENTER", 59: "CERULEAN GYM", 60: "CERULEAN BIKE SHOP",
    61: "CERULEAN MART", 62: "MT MOON POKECENTER",
    63: "CERULEAN TRASHED HOUSE", 64: "CERULEAN ROBBED HOUSE",
    68: "ROUTE 5 GATE", 70: "UNDERGROUND ENTRANCE R5",
    71: "DAYCARE", 72: "ROUTE 6 GATE", 74: "UNDERGROUND ENTRANCE R6",
    76: "ROUTE 7 GATE", 78: "UNDERGROUND ENTRANCE R7",
    82: "ROUTE 8 GATE", 83: "UNDERGROUND ENTRANCE R8",
    84: "ROCK TUNNEL POKECENTER", 85: "ROCK TUNNEL 1F",
    86: "POWER PLANT", 87: "ROUTE 11 GATE 1F", 88: "DIGLETTS CAVE EXIT",
    89: "ROUTE 11 GATE 2F", 90: "ROUTE 12 GATE 1F",
    92: "ROUTE 12 GATE 2F",
    # Vermilion
    94: "SS ANNE 1F", 95: "SS ANNE 2F", 96: "SS ANNE 3F",
    97: "SS ANNE B1F", 98: "SS ANNE DECK", 99: "SS ANNE KITCHEN",
    100: "SS ANNE CAPTAINS ROOM", 101: "SS ANNE 1F ROOMS",
    102: "SS ANNE 2F ROOMS", 103: "SS ANNE B1F ROOMS",
    108: "VICTORY ROAD 1F",
    # Lavender
    133: "POKEMON TOWER 1F", 134: "POKEMON TOWER 2F",
    135: "POKEMON TOWER 3F", 136: "POKEMON TOWER 4F",
    137: "POKEMON TOWER 5F", 138: "POKEMON TOWER 6F",
    139: "POKEMON TOWER 7F",
    # Celadon
    141: "CELADON MART 1F", 142: "CELADON MART 2F",
    143: "CELADON MART 3F", 144: "CELADON MART 4F",
    145: "CELADON MART 5F", 146: "CELADON MART ROOF",
    147: "CELADON MART ELEVATOR", 148: "CELADON MANSION 1F",
    149: "CELADON MANSION 2F", 150: "CELADON MANSION 3F",
    151: "CELADON MANSION ROOF", 152: "CELADON POKECENTER",
    153: "CELADON GYM", 154: "GAME CORNER", 155: "GAME CORNER PRIZE",
    156: "CELADON DINER", 157: "CELADON CHIEF HOUSE",
    158: "CELADON HOTEL",
    # Fuchsia
    159: "SAFARI ZONE ENTRANCE", 160: "FUCHSIA GYM",
    # Saffron
    178: "SILPH CO 1F", 179: "SILPH CO 2F", 180: "SILPH CO 3F",
    181: "SILPH CO 4F", 182: "SILPH CO 5F", 183: "SILPH CO 6F",
    184: "SILPH CO 7F", 185: "SILPH CO 8F", 186: "SILPH CO 9F",
    187: "SILPH CO 10F", 188: "SILPH CO 11F",
    190: "SAFFRON GYM", 191: "SAFFRON POKECENTER",
    193: "FIGHTING DOJO",
    # Elite Four / Indigo
    243: "INDIGO PLATEAU LOBBY", 244: "LORELEI", 245: "BRUNO",
    246: "AGATHA", 247: "LANCE", 248: "HALL OF FAME",
}

# ── Gen 1 type names ──────────────────────────────────────────────────────

TYPE_NAMES = {
    0x00: "Normal", 0x01: "Fighting", 0x02: "Flying", 0x03: "Poison",
    0x04: "Ground", 0x05: "Rock", 0x07: "Bug", 0x08: "Ghost",
    0x14: "Fire", 0x15: "Water", 0x16: "Grass", 0x17: "Electric",
    0x18: "Psychic", 0x19: "Ice", 0x1A: "Dragon",
}

# ── Status conditions ─────────────────────────────────────────────────────

def decode_status(status_byte: int) -> str:
    """Decode Gen 1 status byte to human-readable string."""
    if status_byte == 0:
        return "healthy"
    if status_byte & 0b111:  # Bits 0-2: sleep counter
        return "asleep"
    if status_byte & 0b1000:  # Bit 3
        return "poisoned"
    if status_byte & 0b10000:  # Bit 4
        return "burned"
    if status_byte & 0b100000:  # Bit 5
        return "frozen"
    if status_byte & 0b1000000:  # Bit 6
        return "paralyzed"
    return "healthy"


class MemoryReaderRed:
    """Reads Pokemon Red game state from emulator RAM.

    Conforms to the same interface as MemoryReader (Crystal) — returns
    GameState objects that bridge.py and agent.py can consume.
    """

    def __init__(self, emu: EmulatorControl):
        self.emu = emu

    def _mem(self, addr: int) -> int:
        """Read a single byte from RAM."""
        return self.emu.read_byte(addr)

    def _mem_range(self, start: int, length: int) -> list:
        """Read a range of bytes from RAM."""
        return list(self.emu.read_bytes(start, length))

    def _read_money(self) -> int:
        """Read money in BCD format."""
        b3 = self._mem(MONEY_ADDR)      # MSB
        b2 = self._mem(MONEY_ADDR + 1)
        b1 = self._mem(MONEY_ADDR + 2)  # LSB
        return (
            ((b3 >> 4) * 100000) + ((b3 & 0xF) * 10000)
            + ((b2 >> 4) * 1000) + ((b2 & 0xF) * 100)
            + ((b1 >> 4) * 10) + (b1 & 0xF)
        )

    def _read_badges(self) -> Badges:
        """Read Red/Blue badges."""
        b = self._mem(BADGES_ADDR)
        badges = Badges()
        # Map Crystal badge names to Red badge bits for compatibility
        badges.zephyr = bool(b & 0x01)    # Boulder Badge
        badges.hive = bool(b & 0x02)      # Cascade Badge
        badges.plain = bool(b & 0x04)     # Thunder Badge
        badges.fog = bool(b & 0x08)       # Rainbow Badge
        badges.storm = bool(b & 0x10)     # Soul Badge
        badges.mineral = bool(b & 0x20)   # Marsh Badge
        badges.glacier = bool(b & 0x40)   # Volcano Badge
        badges.rising = bool(b & 0x80)    # Earth Badge
        return badges

    def _read_position(self) -> MapPosition:
        """Read current map and coordinates."""
        map_id = self._mem(MAP_ID)
        x = self._mem(PLAYER_X)
        y = self._mem(PLAYER_Y)
        map_name = MAP_NAMES.get(map_id, f"Map {map_id}")
        return MapPosition(
            map_id=map_id,
            map_group=0,       # Red has flat map IDs (no groups)
            map_number=map_id,
            map_name=map_name,
            x=x,
            y=y,
        )

    def _read_party(self) -> Party:
        """Read all Pokemon in the party."""
        count = min(self._mem(PARTY_COUNT), 6)
        pokemon_list = []

        for i in range(count):
            addr = PARTY_BASE_ADDRS[i]
            species_id = self._mem(addr + OFF_SPECIES)
            species_name = SPECIES_NAMES.get(species_id, f"Pokemon_{species_id}")

            # Read stats
            hp = (self._mem(addr + OFF_HP_HI) << 8) + self._mem(addr + OFF_HP_LO)
            hp_max = (self._mem(addr + OFF_MAX_HP_HI) << 8) + self._mem(addr + OFF_MAX_HP_LO)
            level = self._mem(addr + OFF_LEVEL)
            attack = (self._mem(addr + OFF_ATTACK_HI) << 8) + self._mem(addr + OFF_ATTACK_LO)
            defense = (self._mem(addr + OFF_DEFENSE_HI) << 8) + self._mem(addr + OFF_DEFENSE_LO)
            speed = (self._mem(addr + OFF_SPEED_HI) << 8) + self._mem(addr + OFF_SPEED_LO)
            special = (self._mem(addr + OFF_SPECIAL_HI) << 8) + self._mem(addr + OFF_SPECIAL_LO)
            status = decode_status(self._mem(addr + OFF_STATUS))

            # Types
            type1_id = self._mem(addr + OFF_TYPE1)
            type2_id = self._mem(addr + OFF_TYPE2)
            types = [TYPE_NAMES.get(type1_id, "???")]
            if type2_id != type1_id:
                types.append(TYPE_NAMES.get(type2_id, "???"))

            # Moves (with full data from move_data.py)
            moves = []
            for j in range(4):
                move_id = self._mem(addr + OFF_MOVE1 + j)
                pp = self._mem(addr + OFF_PP1 + j)
                if move_id != 0:
                    move_name = MOVE_NAMES.get(move_id, f"Move_{move_id}")
                    mdata = get_move_data(move_id)
                    if mdata:
                        move_type = mdata["type"]
                        power = mdata["power"]
                        accuracy = mdata["accuracy"]
                        category = mdata["category"]
                    else:
                        move_type = "Normal"
                        power = 0
                        accuracy = 100
                        category = "physical"
                    moves.append(Move(
                        name=move_name,
                        move_type=move_type,
                        power=power,
                        accuracy=accuracy,
                        pp=pp,
                        pp_max=pp,  # Approximation
                        category=category,
                    ))

            # Nickname
            nick_data = self._mem_range(PARTY_NICK_ADDRS[i], 11)
            nickname = decode_text(nick_data)

            pokemon_list.append(Pokemon(
                species=species_name,
                nickname=nickname or species_name,
                level=level,
                hp=hp,
                hp_max=hp_max,
                attack=attack,
                defense=defense,
                speed=speed,
                sp_attack=special,   # Gen 1: same Special stat
                sp_defense=special,
                pokemon_type=types,
                moves=moves,
                status=status,
                held_item="",  # Gen 1: no held items
            ))

        return Party(pokemon=pokemon_list)

    def _read_battle(self) -> BattleState:
        """Read battle state."""
        mode = self._mem(BATTLE_MODE)
        if mode == 0:
            return BattleState(in_battle=False)

        enemy_species_id = self._mem(ENEMY_MON_SPECIES)
        enemy_name = SPECIES_NAMES.get(enemy_species_id, f"Pokemon_{enemy_species_id}")
        enemy_hp = (self._mem(ENEMY_MON_HP_HI) << 8) + self._mem(ENEMY_MON_HP_LO)
        enemy_max_hp = (self._mem(ENEMY_MON_MAX_HP_HI) << 8) + self._mem(ENEMY_MON_MAX_HP_LO)
        enemy_level = self._mem(ENEMY_MON_LEVEL)
        enemy_status = decode_status(self._mem(ENEMY_MON_STATUS))

        enemy = Pokemon(
            species=enemy_name,
            nickname=enemy_name,
            level=enemy_level,
            hp=enemy_hp,
            hp_max=enemy_max_hp,
            attack=0, defense=0, speed=0, sp_attack=0, sp_defense=0,
            status=enemy_status,
        )

        return BattleState(
            in_battle=True,
            is_wild=(mode == 1),
            is_trainer=(mode == 2),
            enemy=enemy,
        )

    def _read_menu_state(self) -> MenuState:
        """Detect current menu/dialog state from RAM flags.

        Uses JOY_DISABLED bit 5 (0x20) as primary dialog indicator per pokered
        disassembly and reference repos. TEXTBOX_ID (0xD125) retains stale
        values after dialog ends and is unreliable for active-dialog detection.
        """
        joy_disabled = self._mem(JOY_DISABLED)
        battle_mode = self._mem(BATTLE_MODE)

        if battle_mode != 0:
            return MenuState.BATTLE
        if joy_disabled & 0x20:
            return MenuState.DIALOG
        return MenuState.OVERWORLD

    def _read_play_time(self) -> int:
        """Read play time in minutes."""
        hours = (self._mem(PLAY_TIME_HOURS_H) << 8) + self._mem(PLAY_TIME_HOURS_L)
        minutes = self._mem(PLAY_TIME_MINUTES)
        return hours * 60 + minutes

    def read_game_state(self) -> GameState:
        """Read complete game state from RAM."""
        return GameState(
            party=self._read_party(),
            position=self._read_position(),
            battle=self._read_battle(),
            badges=self._read_badges(),
            money=self._read_money(),
            play_time_minutes=self._read_play_time(),
            menu_state=self._read_menu_state(),
        )
