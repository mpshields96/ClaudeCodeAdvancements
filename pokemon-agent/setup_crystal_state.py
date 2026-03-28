"""Create a playable Crystal state with a starter Pokemon.

This script bootstraps a save state suitable for the agent loop:
1. Loads the 'playable_start' base state (Player's House 1F, movement works)
2. Injects a Cyndaquil Lv5 into the party via RAM writes
3. Walks out the front door to New Bark Town
4. Saves as 'crystal_playable.state'

Usage:
    python3 setup_crystal_state.py
    python3 setup_crystal_state.py --starter totodile
    python3 setup_crystal_state.py --verify-only

The resulting state can be used with:
    python3 main.py --rom pokemon_crystal.gbc --load-state crystal_playable --steps 500
"""
from __future__ import annotations

import argparse
import os
import sys

# Crystal RAM addresses (from memory_reader.py / pret/pokecrystal wram.asm)
PARTY_COUNT = 0xDCD7
PARTY_SPECIES_START = 0xDCD8
PARTY_DATA_START = 0xDCDF
PARTY_PP_START = 0xDD17

# Starter definitions: species_id, moves [(id, pp)], base stats at Lv5
STARTERS = {
    "cyndaquil": {
        "species": 155,
        "moves": [(33, 35), (43, 30)],  # Tackle, Leer
        "stats": {"hp": 20, "atk": 12, "def": 10, "spd": 14, "spatk": 13, "spdef": 12},
    },
    "totodile": {
        "species": 158,
        "moves": [(10, 35), (43, 30)],  # Scratch, Leer
        "stats": {"hp": 21, "atk": 14, "def": 13, "spd": 11, "spatk": 11, "spdef": 12},
    },
    "chikorita": {
        "species": 152,
        "moves": [(33, 35), (45, 40)],  # Tackle, Growl
        "stats": {"hp": 21, "atk": 11, "def": 14, "spd": 11, "spatk": 11, "spdef": 14},
    },
}


def inject_starter(emu, starter_name: str = "cyndaquil") -> dict:
    """Write starter Pokemon data directly to party RAM.

    Returns dict with species info for verification.
    """
    starter = STARTERS[starter_name]
    sid = starter["species"]
    stats = starter["stats"]
    moves = starter["moves"]

    # Party count = 1, species list terminated with 0xFF
    emu.write_byte(PARTY_COUNT, 1)
    emu.write_byte(PARTY_SPECIES_START, sid)
    emu.write_byte(PARTY_SPECIES_START + 1, 0xFF)

    # 48-byte party data block for slot 0
    base = PARTY_DATA_START
    emu.write_byte(base + 0, sid)       # species
    emu.write_byte(base + 1, 0)         # held item (none)
    for i, (move_id, _pp) in enumerate(moves):
        emu.write_byte(base + 2 + i, move_id)
    for i in range(len(moves), 4):
        emu.write_byte(base + 2 + i, 0)  # empty move slots
    emu.write_byte(base + 31, 5)        # level
    emu.write_byte(base + 32, 0)        # status = OK
    emu.write_byte(base + 34, 0)        # HP hi
    emu.write_byte(base + 35, stats["hp"])  # HP lo
    emu.write_byte(base + 36, 0)        # Max HP hi
    emu.write_byte(base + 37, stats["hp"])  # Max HP lo
    emu.write_byte(base + 38, 0)
    emu.write_byte(base + 39, stats["atk"])
    emu.write_byte(base + 40, 0)
    emu.write_byte(base + 41, stats["def"])
    emu.write_byte(base + 42, 0)
    emu.write_byte(base + 43, stats["spd"])
    emu.write_byte(base + 44, 0)
    emu.write_byte(base + 45, stats["spatk"])
    emu.write_byte(base + 46, 0)
    emu.write_byte(base + 47, stats["spdef"])

    # PP block
    for i, (_move_id, pp) in enumerate(moves):
        emu.write_byte(PARTY_PP_START + i, pp)
    for i in range(len(moves), 4):
        emu.write_byte(PARTY_PP_START + i, 0)

    return {"name": starter_name, "species_id": sid, "level": 5}


def walk_to_new_bark(emu, reader) -> bool:
    """Walk from Player's House 1F to New Bark Town.

    Returns True if successfully exited the house.
    """
    gs = reader.read_game_state()

    # Navigate to door at (7, 7) from current position
    # Door tiles: (6,7) and (7,7), exit by pressing DOWN
    target_x = 7
    dx = target_x - gs.position.x
    direction = "right" if dx > 0 else "left"
    for _ in range(abs(dx)):
        emu.press(direction, hold_frames=10, wait_frames=120)

    # Walk to y=7 if not already there
    gs = reader.read_game_state()
    dy = 7 - gs.position.y
    if dy > 0:
        for _ in range(dy):
            emu.press("down", hold_frames=10, wait_frames=120)

    # Step onto the door (press DOWN from y=7)
    emu.press("down", hold_frames=10, wait_frames=120)
    emu.tick(120)  # Wait for map transition

    gs = reader.read_game_state()
    return gs.position.map_number == 4  # New Bark Town


def main():
    parser = argparse.ArgumentParser(description="Create playable Crystal save state")
    parser.add_argument("--starter", choices=list(STARTERS.keys()), default="cyndaquil")
    parser.add_argument("--verify-only", action="store_true",
                        help="Just verify existing crystal_playable state")
    parser.add_argument("--rom", default="pokemon_crystal.gbc")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from emulator_control import EmulatorControl
    from memory_reader import MemoryReader

    emu = EmulatorControl.from_rom(args.rom, headless=True)
    emu.set_state_dir("states")
    reader = MemoryReader(emu)

    if args.verify_only:
        try:
            emu.load_state("crystal_playable")
            gs = reader.read_game_state()
            lead = gs.party.lead() if gs.party.size() > 0 else None
            print(f"Map: ({gs.position.map_group},{gs.position.map_number})")
            print(f"Position: ({gs.position.x},{gs.position.y})")
            print(f"Party: {gs.party.size()}")
            if lead:
                print(f"Lead: {lead.species} Lv{lead.level} HP={lead.hp}/{lead.hp_max}")
            ok = gs.position.map_number == 4 and gs.party.size() > 0
            print(f"Status: {'OK' if ok else 'NEEDS REBUILD'}")
            emu.close()
            return 0 if ok else 1
        except Exception as e:
            print(f"Error: {e}")
            emu.close()
            return 1

    # Load base state
    print("Loading base state (playable_start)...")
    emu.load_state("playable_start")
    gs = reader.read_game_state()
    print(f"  Position: ({gs.position.x},{gs.position.y}) Map({gs.position.map_group},{gs.position.map_number})")

    # Inject starter
    print(f"Injecting {args.starter}...")
    info = inject_starter(emu, args.starter)
    gs = reader.read_game_state()
    lead = gs.party.lead()
    print(f"  Party: {gs.party.size()} | {lead.species} Lv{lead.level} HP={lead.hp}/{lead.hp_max}")

    # Walk outside
    print("Walking to New Bark Town...")
    success = walk_to_new_bark(emu, reader)
    gs = reader.read_game_state()

    if success:
        print(f"  In New Bark Town at ({gs.position.x},{gs.position.y})")
        path = emu.save_state("crystal_playable")
        print(f"Saved: {path}")
        print(f"\nReady to play:")
        print(f"  python3 main.py --rom {args.rom} --load-state crystal_playable --steps 500 --offline")
    else:
        print(f"  Failed to exit house. Map: ({gs.position.map_group},{gs.position.map_number})")
        emu.close()
        return 1

    emu.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
