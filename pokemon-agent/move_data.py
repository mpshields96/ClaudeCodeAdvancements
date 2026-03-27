"""Pokemon Red Gen 1 move data table.

Maps move IDs (0x01-0xA5) to type, power, accuracy, and category.
Data sourced from pokered disassembly (pret/pokered) and Bulbapedia.

Usage:
    from move_data import get_move_data
    data = get_move_data(0x0A)  # Scratch
    # {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"}

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from typing import Optional


# ── Gen 1 Move Data ─────────────────────────────────────────────────────
# Format: move_id -> {"type", "power", "accuracy", "category"}
# power=0 means status/non-damaging move
# accuracy=0 means always-hit (Swift, etc.)
# category: "physical", "special", or "status"
# In Gen 1, category is determined by type: all Fire/Water/Grass/Electric/
# Ice/Psychic/Dragon moves are special; rest are physical.

MOVE_DATA: dict[int, dict] = {
    # ── Normal ───────────────────────────────────────────────────────────
    0x01: {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"},   # POUND
    0x02: {"type": "Normal", "power": 50, "accuracy": 100, "category": "physical"},   # KARATE CHOP (Normal in Gen 1)
    0x03: {"type": "Normal", "power": 15, "accuracy": 85, "category": "physical"},    # DOUBLE SLAP
    0x04: {"type": "Normal", "power": 18, "accuracy": 85, "category": "physical"},    # COMET PUNCH
    0x05: {"type": "Normal", "power": 80, "accuracy": 85, "category": "physical"},    # MEGA PUNCH
    0x06: {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"},   # PAY DAY
    0x07: {"type": "Fire", "power": 75, "accuracy": 100, "category": "special"},      # FIRE PUNCH
    0x08: {"type": "Ice", "power": 75, "accuracy": 100, "category": "special"},       # ICE PUNCH
    0x09: {"type": "Electric", "power": 75, "accuracy": 100, "category": "special"},  # THUNDER PUNCH
    0x0A: {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"},   # SCRATCH
    0x0B: {"type": "Normal", "power": 55, "accuracy": 100, "category": "physical"},   # VICE GRIP
    0x0C: {"type": "Normal", "power": 0, "accuracy": 30, "category": "physical"},     # GUILLOTINE (OHKO)
    0x0D: {"type": "Normal", "power": 80, "accuracy": 75, "category": "special"},     # RAZOR WIND
    0x0E: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SWORDS DANCE
    0x0F: {"type": "Normal", "power": 50, "accuracy": 95, "category": "physical"},    # CUT
    0x10: {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"},   # GUST (Normal in Gen 1)
    0x11: {"type": "Flying", "power": 35, "accuracy": 100, "category": "physical"},   # WING ATTACK
    0x12: {"type": "Normal", "power": 0, "accuracy": 85, "category": "status"},       # WHIRLWIND
    0x13: {"type": "Flying", "power": 70, "accuracy": 95, "category": "physical"},    # FLY
    0x14: {"type": "Normal", "power": 15, "accuracy": 75, "category": "physical"},    # BIND
    0x15: {"type": "Normal", "power": 80, "accuracy": 75, "category": "physical"},    # SLAM
    0x16: {"type": "Grass", "power": 35, "accuracy": 100, "category": "special"},     # VINE WHIP
    0x17: {"type": "Normal", "power": 65, "accuracy": 100, "category": "physical"},   # STOMP
    0x18: {"type": "Fighting", "power": 30, "accuracy": 100, "category": "physical"}, # DOUBLE KICK
    0x19: {"type": "Normal", "power": 120, "accuracy": 75, "category": "physical"},   # MEGA KICK
    0x1A: {"type": "Fighting", "power": 70, "accuracy": 95, "category": "physical"},  # JUMP KICK
    0x1B: {"type": "Fighting", "power": 60, "accuracy": 85, "category": "physical"},  # ROLLING KICK
    0x1C: {"type": "Ground", "power": 0, "accuracy": 100, "category": "status"},      # SAND ATTACK
    0x1D: {"type": "Normal", "power": 70, "accuracy": 100, "category": "physical"},   # HEADBUTT
    0x1E: {"type": "Normal", "power": 65, "accuracy": 100, "category": "physical"},   # HORN ATTACK
    0x1F: {"type": "Normal", "power": 15, "accuracy": 85, "category": "physical"},    # FURY ATTACK
    0x20: {"type": "Normal", "power": 0, "accuracy": 30, "category": "physical"},     # HORN DRILL (OHKO)
    0x21: {"type": "Normal", "power": 35, "accuracy": 95, "category": "physical"},    # TACKLE
    0x22: {"type": "Normal", "power": 85, "accuracy": 100, "category": "physical"},   # BODY SLAM
    0x23: {"type": "Normal", "power": 15, "accuracy": 85, "category": "physical"},    # WRAP
    0x24: {"type": "Normal", "power": 90, "accuracy": 85, "category": "physical"},    # TAKE DOWN
    0x25: {"type": "Normal", "power": 90, "accuracy": 100, "category": "physical"},   # THRASH
    0x26: {"type": "Normal", "power": 100, "accuracy": 100, "category": "physical"},  # DOUBLE EDGE
    0x27: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # TAIL WHIP
    0x28: {"type": "Poison", "power": 15, "accuracy": 100, "category": "physical"},   # POISON STING
    0x29: {"type": "Bug", "power": 25, "accuracy": 100, "category": "physical"},      # TWINEEDLE
    0x2A: {"type": "Bug", "power": 14, "accuracy": 85, "category": "physical"},       # PIN MISSILE
    0x2B: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # LEER
    0x2C: {"type": "Normal", "power": 60, "accuracy": 100, "category": "physical"},   # BITE (Normal in Gen 1)
    0x2D: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # GROWL
    0x2E: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # ROAR
    0x2F: {"type": "Normal", "power": 0, "accuracy": 55, "category": "status"},       # SING
    0x30: {"type": "Normal", "power": 0, "accuracy": 55, "category": "status"},       # SUPERSONIC
    0x31: {"type": "Normal", "power": 0, "accuracy": 90, "category": "special"},      # SONIC BOOM (fixed 20 dmg)
    0x32: {"type": "Normal", "power": 0, "accuracy": 55, "category": "status"},       # DISABLE
    0x33: {"type": "Poison", "power": 40, "accuracy": 100, "category": "physical"},   # ACID
    0x34: {"type": "Fire", "power": 40, "accuracy": 100, "category": "special"},      # EMBER
    0x35: {"type": "Fire", "power": 95, "accuracy": 100, "category": "special"},      # FLAMETHROWER
    0x36: {"type": "Ice", "power": 0, "accuracy": 100, "category": "status"},         # MIST
    0x37: {"type": "Water", "power": 40, "accuracy": 100, "category": "special"},     # WATER GUN
    0x38: {"type": "Water", "power": 120, "accuracy": 80, "category": "special"},     # HYDRO PUMP
    0x39: {"type": "Water", "power": 95, "accuracy": 100, "category": "special"},     # SURF
    0x3A: {"type": "Ice", "power": 95, "accuracy": 100, "category": "special"},       # ICE BEAM
    0x3B: {"type": "Ice", "power": 120, "accuracy": 90, "category": "special"},       # BLIZZARD
    0x3C: {"type": "Psychic", "power": 65, "accuracy": 100, "category": "special"},   # PSYBEAM
    0x3D: {"type": "Water", "power": 65, "accuracy": 100, "category": "special"},     # BUBBLE BEAM
    0x3E: {"type": "Ice", "power": 65, "accuracy": 100, "category": "special"},       # AURORA BEAM
    0x3F: {"type": "Normal", "power": 150, "accuracy": 90, "category": "physical"},   # HYPER BEAM
    0x40: {"type": "Flying", "power": 35, "accuracy": 100, "category": "physical"},   # PECK
    0x41: {"type": "Flying", "power": 80, "accuracy": 100, "category": "physical"},   # DRILL PECK
    0x42: {"type": "Fighting", "power": 80, "accuracy": 80, "category": "physical"},  # SUBMISSION
    0x43: {"type": "Fighting", "power": 50, "accuracy": 90, "category": "physical"},  # LOW KICK
    0x44: {"type": "Fighting", "power": 0, "accuracy": 100, "category": "physical"},  # COUNTER (special dmg)
    0x45: {"type": "Fighting", "power": 0, "accuracy": 100, "category": "physical"},  # SEISMIC TOSS (fixed dmg)
    0x46: {"type": "Normal", "power": 80, "accuracy": 100, "category": "physical"},   # STRENGTH
    0x47: {"type": "Grass", "power": 20, "accuracy": 100, "category": "special"},     # ABSORB
    0x48: {"type": "Grass", "power": 40, "accuracy": 100, "category": "special"},     # MEGA DRAIN
    0x49: {"type": "Grass", "power": 0, "accuracy": 90, "category": "status"},        # LEECH SEED
    0x4A: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # GROWTH
    0x4B: {"type": "Grass", "power": 55, "accuracy": 95, "category": "special"},      # RAZOR LEAF
    0x4C: {"type": "Grass", "power": 120, "accuracy": 100, "category": "special"},    # SOLAR BEAM
    0x4D: {"type": "Poison", "power": 0, "accuracy": 75, "category": "status"},       # POISON POWDER
    0x4E: {"type": "Grass", "power": 0, "accuracy": 75, "category": "status"},        # STUN SPORE
    0x4F: {"type": "Grass", "power": 0, "accuracy": 75, "category": "status"},        # SLEEP POWDER
    0x50: {"type": "Grass", "power": 70, "accuracy": 100, "category": "special"},     # PETAL DANCE
    0x51: {"type": "Bug", "power": 0, "accuracy": 95, "category": "status"},          # STRING SHOT
    0x52: {"type": "Dragon", "power": 0, "accuracy": 100, "category": "special"},     # DRAGON RAGE (fixed 40)
    0x53: {"type": "Fire", "power": 15, "accuracy": 70, "category": "special"},       # FIRE SPIN
    0x54: {"type": "Electric", "power": 40, "accuracy": 100, "category": "special"},  # THUNDER SHOCK
    0x55: {"type": "Electric", "power": 95, "accuracy": 100, "category": "special"},  # THUNDERBOLT
    0x56: {"type": "Electric", "power": 0, "accuracy": 100, "category": "status"},    # THUNDER WAVE
    0x57: {"type": "Electric", "power": 120, "accuracy": 70, "category": "special"},  # THUNDER
    0x58: {"type": "Rock", "power": 50, "accuracy": 65, "category": "physical"},      # ROCK THROW
    0x59: {"type": "Ground", "power": 100, "accuracy": 100, "category": "physical"},  # EARTHQUAKE
    0x5A: {"type": "Ground", "power": 0, "accuracy": 30, "category": "physical"},     # FISSURE (OHKO)
    0x5B: {"type": "Ground", "power": 100, "accuracy": 100, "category": "physical"},  # DIG
    0x5C: {"type": "Poison", "power": 0, "accuracy": 85, "category": "status"},       # TOXIC
    0x5D: {"type": "Psychic", "power": 50, "accuracy": 100, "category": "special"},   # CONFUSION
    0x5E: {"type": "Psychic", "power": 90, "accuracy": 100, "category": "special"},   # PSYCHIC
    0x5F: {"type": "Psychic", "power": 0, "accuracy": 60, "category": "status"},      # HYPNOSIS
    0x60: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # MEDITATE
    0x61: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # AGILITY
    0x62: {"type": "Normal", "power": 40, "accuracy": 100, "category": "physical"},   # QUICK ATTACK
    0x63: {"type": "Normal", "power": 20, "accuracy": 100, "category": "physical"},   # RAGE
    0x64: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # TELEPORT
    0x65: {"type": "Ghost", "power": 0, "accuracy": 100, "category": "physical"},     # NIGHT SHADE (fixed dmg)
    0x66: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # MIMIC
    0x67: {"type": "Normal", "power": 0, "accuracy": 85, "category": "status"},       # SCREECH
    0x68: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # DOUBLE TEAM
    0x69: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # RECOVER
    0x6A: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # HARDEN
    0x6B: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # MINIMIZE
    0x6C: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SMOKESCREEN
    0x6D: {"type": "Ghost", "power": 0, "accuracy": 100, "category": "status"},       # CONFUSE RAY
    0x6E: {"type": "Water", "power": 0, "accuracy": 100, "category": "status"},       # WITHDRAW
    0x6F: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # DEFENSE CURL
    0x70: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # BARRIER
    0x71: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # LIGHT SCREEN
    0x72: {"type": "Ice", "power": 0, "accuracy": 100, "category": "status"},         # HAZE
    0x73: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # REFLECT
    0x74: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # FOCUS ENERGY
    0x75: {"type": "Normal", "power": 0, "accuracy": 100, "category": "physical"},    # BIDE (returns dmg)
    0x76: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # METRONOME
    0x77: {"type": "Flying", "power": 0, "accuracy": 100, "category": "status"},      # MIRROR MOVE
    0x78: {"type": "Normal", "power": 130, "accuracy": 100, "category": "physical"},  # SELF DESTRUCT
    0x79: {"type": "Normal", "power": 100, "accuracy": 75, "category": "physical"},   # EGG BOMB
    0x7A: {"type": "Ghost", "power": 20, "accuracy": 100, "category": "physical"},    # LICK
    0x7B: {"type": "Poison", "power": 20, "accuracy": 70, "category": "physical"},    # SMOG
    0x7C: {"type": "Poison", "power": 65, "accuracy": 100, "category": "physical"},   # SLUDGE
    0x7D: {"type": "Ground", "power": 65, "accuracy": 85, "category": "physical"},    # BONE CLUB
    0x7E: {"type": "Fire", "power": 120, "accuracy": 85, "category": "special"},      # FIRE BLAST
    0x7F: {"type": "Water", "power": 80, "accuracy": 100, "category": "special"},     # WATERFALL
    0x80: {"type": "Water", "power": 35, "accuracy": 75, "category": "special"},      # CLAMP
    0x81: {"type": "Normal", "power": 60, "accuracy": 0, "category": "physical"},     # SWIFT (never misses)
    0x82: {"type": "Normal", "power": 100, "accuracy": 100, "category": "physical"},  # SKULL BASH
    0x83: {"type": "Normal", "power": 20, "accuracy": 100, "category": "physical"},   # SPIKE CANNON
    0x84: {"type": "Normal", "power": 10, "accuracy": 100, "category": "physical"},   # CONSTRICT
    0x85: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # AMNESIA
    0x86: {"type": "Psychic", "power": 0, "accuracy": 80, "category": "status"},      # KINESIS
    0x87: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SOFT BOILED
    0x88: {"type": "Fighting", "power": 85, "accuracy": 90, "category": "physical"},  # HI JUMP KICK
    0x89: {"type": "Normal", "power": 0, "accuracy": 75, "category": "status"},       # GLARE
    0x8A: {"type": "Psychic", "power": 100, "accuracy": 100, "category": "special"},  # DREAM EATER
    0x8B: {"type": "Poison", "power": 0, "accuracy": 55, "category": "status"},       # POISON GAS
    0x8C: {"type": "Normal", "power": 15, "accuracy": 85, "category": "physical"},    # BARRAGE
    0x8D: {"type": "Bug", "power": 20, "accuracy": 100, "category": "physical"},      # LEECH LIFE
    0x8E: {"type": "Normal", "power": 0, "accuracy": 75, "category": "status"},       # LOVELY KISS
    0x8F: {"type": "Flying", "power": 140, "accuracy": 90, "category": "physical"},   # SKY ATTACK
    0x90: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # TRANSFORM
    0x91: {"type": "Water", "power": 20, "accuracy": 100, "category": "special"},     # BUBBLE
    0x92: {"type": "Normal", "power": 70, "accuracy": 100, "category": "physical"},   # DIZZY PUNCH
    0x93: {"type": "Grass", "power": 0, "accuracy": 100, "category": "status"},       # SPORE
    0x94: {"type": "Normal", "power": 0, "accuracy": 70, "category": "status"},       # FLASH
    0x95: {"type": "Psychic", "power": 0, "accuracy": 80, "category": "special"},     # PSYWAVE (variable dmg)
    0x96: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SPLASH
    0x97: {"type": "Poison", "power": 0, "accuracy": 100, "category": "status"},      # ACID ARMOR
    0x98: {"type": "Water", "power": 90, "accuracy": 85, "category": "special"},      # CRABHAMMER
    0x99: {"type": "Normal", "power": 170, "accuracy": 100, "category": "physical"},  # EXPLOSION
    0x9A: {"type": "Normal", "power": 18, "accuracy": 80, "category": "physical"},    # FURY SWIPES
    0x9B: {"type": "Ground", "power": 50, "accuracy": 90, "category": "physical"},    # BONEMERANG
    0x9C: {"type": "Psychic", "power": 0, "accuracy": 100, "category": "status"},     # REST
    0x9D: {"type": "Rock", "power": 75, "accuracy": 90, "category": "physical"},      # ROCK SLIDE
    0x9E: {"type": "Normal", "power": 80, "accuracy": 90, "category": "physical"},    # HYPER FANG
    0x9F: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SHARPEN
    0xA0: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # CONVERSION
    0xA1: {"type": "Normal", "power": 80, "accuracy": 100, "category": "physical"},   # TRI ATTACK
    0xA2: {"type": "Normal", "power": 0, "accuracy": 90, "category": "physical"},     # SUPER FANG (half HP)
    0xA3: {"type": "Normal", "power": 70, "accuracy": 100, "category": "physical"},   # SLASH
    0xA4: {"type": "Normal", "power": 0, "accuracy": 100, "category": "status"},      # SUBSTITUTE
    0xA5: {"type": "Normal", "power": 50, "accuracy": 100, "category": "physical"},   # STRUGGLE
}


def get_move_data(move_id: int) -> Optional[dict]:
    """Look up move data by Gen 1 move ID.

    Returns dict with keys: type, power, accuracy, category.
    Returns None if move_id is not in the table.
    """
    return MOVE_DATA.get(move_id)
