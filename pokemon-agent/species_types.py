"""Gen 1 species-to-type lookup table.

Maps each Pokemon Red internal species ID to its type(s).
Provides type information without reading RAM — useful for
reasoning about encounters, team composition, and type matchups
outside of battle (where RAM-based type reading isn't available).

All 151 Gen 1 Pokemon covered. Types use the same string format
as TYPE_NAMES in memory_reader_red.py.

Source: https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_by_index_number_(Generation_I)

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from typing import Dict, List


# Species ID (hex) -> [type1, type2] or [type1] for single-type
# Internal IDs match SPECIES_NAMES in memory_reader_red.py
SPECIES_TYPES: Dict[int, List[str]] = {
    # ── Original 151 Gen 1 Pokemon ──────────────────────────────────────
    0x01: ["Ground", "Rock"],       # RHYDON
    0x02: ["Normal"],               # KANGASKHAN
    0x03: ["Poison"],               # NIDORAN_M
    0x04: ["Normal"],               # CLEFAIRY
    0x05: ["Normal", "Flying"],     # SPEAROW
    0x06: ["Electric"],             # VOLTORB
    0x07: ["Poison", "Ground"],     # NIDOKING
    0x08: ["Water", "Psychic"],     # SLOWBRO
    0x09: ["Grass", "Poison"],      # IVYSAUR
    0x0A: ["Grass", "Psychic"],     # EXEGGUTOR
    0x0B: ["Normal"],               # LICKITUNG
    0x0C: ["Grass", "Psychic"],     # EXEGGCUTE
    0x0D: ["Poison"],               # GRIMER
    0x0E: ["Ghost", "Poison"],      # GENGAR
    0x0F: ["Poison"],               # NIDORAN_F
    0x10: ["Poison", "Ground"],     # NIDOQUEEN
    0x11: ["Ground"],               # CUBONE
    0x12: ["Ground", "Rock"],       # RHYHORN
    0x13: ["Water", "Ice"],         # LAPRAS
    0x14: ["Fire"],                 # ARCANINE
    0x15: ["Psychic"],              # MEW
    0x16: ["Water", "Flying"],      # GYARADOS
    0x17: ["Water"],                # SHELLDER
    0x18: ["Water", "Poison"],      # TENTACOOL
    0x19: ["Ghost", "Poison"],      # GASTLY
    0x1A: ["Bug", "Flying"],        # SCYTHER
    0x1B: ["Water"],                # STARYU
    0x1C: ["Water"],                # BLASTOISE
    0x1D: ["Bug"],                  # PINSIR
    0x1E: ["Grass"],                # TANGELA
    # 0x1F-0x20: MissingNo (not real Pokemon)
    0x21: ["Fire"],                 # GROWLITHE
    0x22: ["Rock", "Ground"],       # ONIX
    0x23: ["Normal", "Flying"],     # FEAROW
    0x24: ["Normal", "Flying"],     # PIDGEY
    0x25: ["Water", "Psychic"],     # SLOWPOKE
    0x26: ["Psychic"],              # KADABRA
    0x27: ["Rock", "Ground"],       # GRAVELER
    0x28: ["Normal"],               # CHANSEY
    0x29: ["Fighting"],             # MACHOKE
    0x2A: ["Psychic"],              # MR_MIME
    0x2B: ["Fighting"],             # HITMONLEE
    0x2C: ["Fighting"],             # HITMONCHAN
    0x2D: ["Poison"],               # ARBOK
    0x2E: ["Bug", "Grass"],         # PARASECT
    0x2F: ["Water"],                # PSYDUCK
    0x30: ["Psychic"],              # DROWZEE
    0x31: ["Rock", "Ground"],       # GOLEM
    # 0x32: MissingNo
    0x33: ["Fire"],                 # MAGMAR
    # 0x34: MissingNo
    0x35: ["Electric"],             # ELECTABUZZ
    0x36: ["Electric"],             # MAGNETON
    0x37: ["Poison"],               # KOFFING
    # 0x38: MissingNo
    0x39: ["Fighting"],             # MANKEY
    0x3A: ["Water"],                # SEEL
    0x3B: ["Ground"],               # DIGLETT
    0x3C: ["Normal"],               # TAUROS
    # 0x3D-0x3F: MissingNo
    0x40: ["Normal", "Flying"],     # FARFETCHD
    0x41: ["Bug", "Poison"],        # VENONAT
    0x42: ["Dragon", "Flying"],     # DRAGONITE
    # 0x43-0x45: MissingNo
    0x46: ["Normal", "Flying"],     # DODUO
    0x47: ["Water"],                # POLIWAG
    0x48: ["Ice", "Psychic"],       # JYNX
    0x49: ["Fire", "Flying"],       # MOLTRES
    0x4A: ["Ice", "Flying"],        # ARTICUNO
    0x4B: ["Electric", "Flying"],   # ZAPDOS
    0x4C: ["Normal"],               # DITTO
    0x4D: ["Normal"],               # MEOWTH
    0x4E: ["Water"],                # KRABBY
    # 0x4F-0x51: MissingNo
    0x52: ["Fire"],                 # VULPIX
    0x53: ["Fire"],                 # NINETALES
    0x54: ["Electric"],             # PIKACHU
    0x55: ["Electric"],             # RAICHU
    # 0x56-0x57: MissingNo
    0x58: ["Dragon"],               # DRATINI
    0x59: ["Dragon"],               # DRAGONAIR
    0x5A: ["Rock", "Water"],        # KABUTO
    0x5B: ["Rock", "Water"],        # KABUTOPS
    0x5C: ["Water"],                # HORSEA
    0x5D: ["Water"],                # SEADRA
    # 0x5E-0x5F: MissingNo
    0x60: ["Ground"],               # SANDSHREW
    0x61: ["Ground"],               # SANDSLASH
    0x62: ["Rock", "Water"],        # OMANYTE
    0x63: ["Rock", "Water"],        # OMASTAR
    # 0x64: MissingNo
    0x65: ["Normal"],               # JIGGLYPUFF
    0x66: ["Normal"],               # WIGGLYTUFF
    0x67: ["Normal"],               # EEVEE
    0x68: ["Fire"],                 # FLAREON
    0x69: ["Electric"],             # JOLTEON
    0x6A: ["Water"],                # VAPOREON
    0x6B: ["Fighting"],             # MACHOP
    0x6C: ["Poison", "Flying"],     # ZUBAT
    0x6D: ["Poison"],               # EKANS
    0x6E: ["Bug", "Grass"],         # PARAS
    0x6F: ["Water"],                # POLIWHIRL
    0x70: ["Water", "Fighting"],    # POLIWRATH
    0x71: ["Bug", "Poison"],        # WEEDLE
    0x72: ["Bug", "Poison"],        # KAKUNA
    0x73: ["Bug", "Poison"],        # BEEDRILL
    # 0x74-0x75: MissingNo
    0x76: ["Normal", "Flying"],     # DODRIO
    0x77: ["Fighting"],             # PRIMEAPE
    0x78: ["Ground"],               # DUGTRIO
    0x79: ["Bug", "Poison"],        # VENOMOTH
    0x7A: ["Water", "Ice"],         # DEWGONG
    0x7B: ["Bug"],                  # CATERPIE
    0x7C: ["Bug"],                  # METAPOD
    0x7D: ["Bug", "Flying"],        # BUTTERFREE
    0x7E: ["Fighting"],             # MACHAMP
    # 0x7F: MissingNo
    0x80: ["Water"],                # GOLDUCK
    0x81: ["Psychic"],              # HYPNO
    0x82: ["Poison", "Flying"],     # GOLBAT
    0x83: ["Psychic"],              # MEWTWO
    0x84: ["Normal"],               # SNORLAX
    0x85: ["Water"],                # MAGIKARP
    # 0x86-0x87: MissingNo
    0x88: ["Poison"],               # MUK
    # 0x89: MissingNo
    0x8A: ["Water"],                # KINGLER
    0x8B: ["Water", "Ice"],         # CLOYSTER
    # 0x8C: MissingNo
    0x8D: ["Electric"],             # ELECTRODE
    0x8E: ["Normal"],               # CLEFABLE
    0x8F: ["Poison"],               # WEEZING
    0x90: ["Normal"],               # PERSIAN
    0x91: ["Ground"],               # MAROWAK
    # 0x92: MissingNo
    0x93: ["Ghost", "Poison"],      # HAUNTER
    0x94: ["Psychic"],              # ABRA
    0x95: ["Psychic"],              # ALAKAZAM
    0x96: ["Normal", "Flying"],     # PIDGEOTTO
    0x97: ["Normal", "Flying"],     # PIDGEOT
    0x98: ["Water", "Psychic"],     # STARMIE
    0x99: ["Grass", "Poison"],      # BULBASAUR
    0x9A: ["Grass", "Poison"],      # VENUSAUR
    0x9B: ["Water", "Poison"],      # TENTACRUEL
    # 0x9C: MissingNo
    0x9D: ["Water"],                # GOLDEEN
    0x9E: ["Water"],                # SEAKING
    # 0x9F-0xA2: MissingNo
    0xA3: ["Fire"],                 # PONYTA
    0xA4: ["Fire"],                 # RAPIDASH
    0xA5: ["Normal"],               # RATTATA
    0xA6: ["Normal"],               # RATICATE
    0xA7: ["Poison"],               # NIDORINO
    0xA8: ["Poison"],               # NIDORINA
    0xA9: ["Rock", "Ground"],       # GEODUDE
    0xAA: ["Normal"],               # PORYGON
    0xAB: ["Rock", "Flying"],       # AERODACTYL
    # 0xAC: MissingNo
    0xAD: ["Electric"],             # MAGNEMITE
    # 0xAE-0xAF: MissingNo
    0xB0: ["Fire"],                 # CHARMANDER
    0xB1: ["Water"],                # SQUIRTLE
    0xB2: ["Fire"],                 # CHARMELEON
    0xB3: ["Water"],                # WARTORTLE
    0xB4: ["Fire", "Flying"],       # CHARIZARD
    # 0xB5-0xB8: MissingNo
    0xB9: ["Grass", "Poison"],      # ODDISH
    0xBA: ["Grass", "Poison"],      # GLOOM
    0xBB: ["Grass", "Poison"],      # VILEPLUME
    0xBC: ["Grass", "Poison"],      # BELLSPROUT
    0xBD: ["Grass", "Poison"],      # WEEPINBELL
    0xBE: ["Grass", "Poison"],      # VICTREEBEL
}


def get_species_types(species_id: int) -> List[str]:
    """Look up a Pokemon's types by its internal species ID.

    Returns a list of type strings (1 or 2 elements).
    Returns empty list for unknown species IDs.
    """
    return SPECIES_TYPES.get(species_id, [])
