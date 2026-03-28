"""Boot sequence — automate Pokemon Crystal intro through to Elm's Lab.

Handles the deterministic Crystal intro without LLM calls:
1. Clear title screen / new game selection
2. Clear opening dialog (Mom wakes you up in Player's House 2F)
3. Navigate downstairs from Player's House 2F to 1F
4. Exit Player's House to New Bark Town
5. Walk to Elm's Lab
6. Clear Elm's dialog + get starter Pokemon

Adapted from boot_sequence.py (Red) using the STEAL CODE pattern (S218).
Crystal uses map group:number addressing instead of single map IDs.

Map IDs (group, number) — from pret/pokecrystal maps.asm (MapGroup_NewBark = 24):
- (24, 7): Player's House 2F — wake up here (verified S220 RAM + S221 source)
- (24, 6): Player's House 1F — Mom is here (verified S221 RAM via stair warp)
- (24, 4): New Bark Town — starting town (verified S221 pret/pokecrystal source)
- (24, 5): Elm's Lab — get starter (verified S221 pret/pokecrystal source)

Warp tiles (from pret/pokecrystal map .asm files):
- 2F stairs: (7, 0) → 1F at (9, 0)
- 1F door: (6, 7) and (7, 7) → New Bark Town

Usage:
    from boot_sequence_crystal import run_crystal_boot_sequence
    result = run_crystal_boot_sequence(emu, reader)

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logger = logging.getLogger("boot_crystal")


# ── Crystal intro map IDs (group, number) ────────────────────────────────────
# Source: pret/pokecrystal maps.asm (MapGroup_NewBark = group 24)
# Verified empirically: 2F and 1F confirmed via mGBA RAM reads (S220-S221).
# 4 (NewBarkTown) and 5 (ElmsLab) confirmed from pret/pokecrystal source.

MAP_PLAYERS_HOUSE_2F = (24, 7)  # Player starts here — bedroom (RAM verified S220+S221)
MAP_PLAYERS_HOUSE_1F = (24, 6)  # Downstairs — Mom (RAM verified S221 via stair warp)
MAP_NEW_BARK_TOWN = (24, 4)     # Starting town (pret/pokecrystal source verified S221)
MAP_ELMS_LAB = (24, 5)          # Professor Elm's lab (pret/pokecrystal source verified S221)

# Warp tile coordinates (from pret/pokecrystal map .asm files, verified S221)
STAIRS_2F_TILE = (7, 0)         # Step onto this tile in 2F to warp to 1F
STAIRS_1F_ARRIVE = (9, 0)       # Arrival position in 1F from stairs
DOOR_1F_TILES = [(6, 7), (7, 7)]  # Step onto either to exit to New Bark Town


def _encode_map(group: int, number: int) -> int:
    """Encode Crystal map group:number as single int for comparison.

    Crystal's RAM stores map_group and map_number separately. Our
    MemoryReader combines them as group * 256 + number for a single
    comparable map_id. This matches memory_reader.py's encoding.
    """
    return group * 256 + number


def _map_matches(current_map_id: int, target: tuple) -> bool:
    """Check if current_map_id matches a (group, number) target."""
    return current_map_id == _encode_map(target[0], target[1])


def clear_dialog_crystal(emu, presses: int = 20, hold: int = 4,
                         wait: int = 16) -> None:
    """Mash A to clear dialog boxes.

    Crystal dialog tends to be longer than Red's. Default 20 presses
    covers most multi-page conversations (Elm's intro, Mom, etc.).
    """
    logger.info("Clearing dialog (%d A presses)", presses)
    for _ in range(presses):
        emu.press("a", hold_frames=hold, wait_frames=wait)
    emu.tick(60)


def clear_dialog_until_overworld_crystal(emu, reader,
                                         max_presses: int = 50) -> bool:
    """Mash A until overworld state is reached.

    Returns True if overworld reached, False if max_presses exhausted.
    """
    from game_state import MenuState

    logger.info("Clearing dialog until overworld (max %d presses)", max_presses)
    for i in range(max_presses):
        state = reader.read_game_state()
        if state.menu_state == MenuState.OVERWORLD:
            logger.info("Overworld reached after %d presses", i)
            return True
        emu.press("a", hold_frames=4, wait_frames=20)

    state = reader.read_game_state()
    if state.menu_state == MenuState.OVERWORLD:
        logger.info("Overworld reached after %d presses", max_presses)
        return True

    logger.warning("Failed to reach overworld after %d presses", max_presses)
    return False


def navigate_crystal(emu, reader, target_x: int, target_y: int,
                     max_steps: int = 30) -> bool:
    """Simple grid navigation — move toward target coordinates.

    No A* pathfinding — just move in the right direction. Works for
    simple indoor rooms without obstacles in the direct path.

    Returns True if target reached.
    """
    for step in range(max_steps):
        state = reader.read_game_state()
        pos = state.position
        cx, cy = pos.x, pos.y

        if cx == target_x and cy == target_y:
            logger.info("Reached (%d, %d) in %d steps", target_x, target_y, step)
            return True

        dx = target_x - cx
        dy = target_y - cy

        if dx > 0:
            direction = "right"
        elif dx < 0:
            direction = "left"
        elif dy < 0:
            direction = "up"
        elif dy > 0:
            direction = "down"
        else:
            return True

        logger.debug("Step %d: (%d,%d) -> %s toward (%d,%d)",
                     step, cx, cy, direction, target_x, target_y)
        emu.press(direction, hold_frames=10, wait_frames=120)

    state = reader.read_game_state()
    pos = state.position
    reached = (pos.x == target_x and pos.y == target_y)
    if not reached:
        logger.warning("Did not reach (%d, %d) — at (%d, %d) after %d steps",
                       target_x, target_y, pos.x, pos.y, max_steps)
    return reached


def wait_for_map_crystal(emu, reader, target: tuple,
                         max_ticks: int = 300) -> bool:
    """Wait for a map transition to complete.

    Crystal map transitions can take several frames. Polls until the
    map group:number matches the target.

    Args:
        target: (group, number) tuple
        max_ticks: maximum frame ticks to wait
    """
    target_id = _encode_map(target[0], target[1])

    for _ in range(max_ticks // 10):
        emu.tick(10)
        state = reader.read_game_state()
        if state.position.map_id == target_id:
            logger.info("Map transition complete: (%d, %d)", target[0], target[1])
            return True

    state = reader.read_game_state()
    current = state.position.map_id
    logger.warning("Map transition timeout: expected (%d,%d)=%d, got %d",
                   target[0], target[1], target_id, current)
    return (current == target_id)


def run_crystal_boot_sequence(emu, reader) -> dict:
    """Run the full Crystal boot sequence from game start to Elm's Lab.

    Handles the deterministic intro:
    1. Title screen → mash through
    2. Player's House 2F → clear dialog, navigate to stairs
    3. Player's House 1F → clear Mom dialog, exit house
    4. New Bark Town → walk to Elm's Lab
    5. Elm's Lab → clear Elm dialog (starter selection is LLM's job)

    Returns:
        dict with: success, final_map, final_position, phases_completed
    """
    from game_state import MenuState

    result = {
        "success": False,
        "final_map": -1,
        "final_position": (0, 0),
        "phases_completed": [],
    }

    # ── Phase 0: Check initial state ─────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position
    logger.info("Boot start: map_id=%d, pos=(%d,%d), menu=%s",
                pos.map_id, pos.x, pos.y, state.menu_state.value)

    # Title screen detection: map_id 0 = not in any game map yet.
    # mGBA may initialize position RAM to (255, 0) or (0, 0) — either way,
    # map_id 0 means we're at the title/intro screen.
    if pos.map_id == 0:
        logger.info("Phase 0: Title screen detected (map=0), booting through intro...")
        # Crystal intro is VERY long (~9000 frames empirically verified S220):
        # 1. Game Boy boot logo (~150 frames)
        # 2. Game Freak logo (~400 frames)
        # 3. Crystal Suicune animation (~2000 frames)
        # 4. Title screen (waits for A press)
        # 5. New Game / Continue menu
        # 6. Time/day setting
        # 7. Player name selection (default CHRIS)
        # 8. Opening cutscene + Mom dialog
        # 9. Wake up in Player's House 2F
        # Strategy: alternate between frame advances and A mashing in chunks
        for cycle in range(6):
            emu.tick(600)
            for _ in range(30):
                emu.press("a", hold_frames=4, wait_frames=30)
            # Check if we've entered the game
            state = reader.read_game_state()
            if state.position.map_id != 0:
                logger.info("Phase 0: Entered game at cycle %d, map=%d",
                            cycle, state.position.map_id)
                break
        result["phases_completed"].append("title_screen")

    # ── Phase 1: Clear opening dialog (Player's House 2F) ────────────────
    state = reader.read_game_state()
    pos = state.position

    if _map_matches(pos.map_id, MAP_PLAYERS_HOUSE_2F):
        logger.info("Phase 1: In Player's House 2F, clearing opening dialog...")

        if state.menu_state in (MenuState.DIALOG, MenuState.POKEMON_CENTER):
            success = clear_dialog_until_overworld_crystal(emu, reader, max_presses=50)
            if success:
                result["phases_completed"].append("opening_dialog")
            else:
                # Try B presses to dismiss stubborn dialog
                for _ in range(10):
                    emu.press("b", hold_frames=4, wait_frames=16)
                clear_dialog_until_overworld_crystal(emu, reader, max_presses=20)
                result["phases_completed"].append("opening_dialog_forced")
        else:
            result["phases_completed"].append("opening_dialog_skipped")

        # ── Phase 2: Navigate to stairs ──────────────────────────────────
        # Crystal Player's House 2F layout (from pret/pokecrystal):
        # Player wakes up at approximately (3, 3). Stairs warp at (7, 0).
        # Path: navigate to (7, 1) then press UP to step onto stair warp.
        logger.info("Phase 2: Navigating to stairs in Player's House 2F...")
        state = reader.read_game_state()
        pos = state.position

        # Navigate to one tile below the stairs warp
        stair_x, stair_y = STAIRS_2F_TILE
        navigate_crystal(emu, reader, target_x=stair_x, target_y=stair_y + 1)

        # Step UP onto the stair warp tile
        emu.press("up", hold_frames=10, wait_frames=120)
        emu.tick(120)

        # Check if transition happened
        state = reader.read_game_state()
        if _map_matches(state.position.map_id, MAP_PLAYERS_HOUSE_1F):
            result["phases_completed"].append("stairs_to_1f")
        else:
            # Retry with longer wait
            emu.press("up", hold_frames=10, wait_frames=180)
            emu.tick(180)
            if wait_for_map_crystal(emu, reader, MAP_PLAYERS_HOUSE_1F):
                result["phases_completed"].append("stairs_to_1f")
            else:
                logger.warning("Phase 2: Stairs transition didn't trigger")

    # ── Phase 3: Player's House 1F → exit to New Bark Town ───────────────
    state = reader.read_game_state()
    pos = state.position

    if _map_matches(pos.map_id, MAP_PLAYERS_HOUSE_1F):
        logger.info("Phase 3: In Player's House 1F, navigating to exit...")

        # Clear Mom's dialog — Crystal 1F has extensive scripted events:
        # clock setting, Pokegear, Elm introduction. Need many presses.
        # Mix A presses with down+A to navigate clock/time menus.
        for _round in range(8):
            for _ in range(40):
                emu.press("a", hold_frames=4, wait_frames=12)
            for _ in range(3):
                emu.press("down", hold_frames=4, wait_frames=8)
                emu.press("a", hold_frames=4, wait_frames=12)
        emu.tick(120)

        # Navigate to door — door warp tiles at (6,7) and (7,7)
        # Arrive from stairs at (9, 0), need to reach door area
        door_x, door_y = DOOR_1F_TILES[0]  # (6, 7)
        navigate_crystal(emu, reader, target_x=door_x, target_y=door_y - 1)

        # Step DOWN onto the door warp tile
        emu.press("down", hold_frames=10, wait_frames=120)
        emu.tick(120)

        if wait_for_map_crystal(emu, reader, MAP_NEW_BARK_TOWN):
            result["phases_completed"].append("exit_house")
        else:
            # Try second door tile (7, 7)
            door_x2, door_y2 = DOOR_1F_TILES[1]
            navigate_crystal(emu, reader, target_x=door_x2, target_y=door_y2 - 1)
            emu.press("down", hold_frames=10, wait_frames=120)
            emu.tick(120)
            state = reader.read_game_state()
            if _map_matches(state.position.map_id, MAP_NEW_BARK_TOWN):
                result["phases_completed"].append("exit_house")
    elif _map_matches(pos.map_id, MAP_NEW_BARK_TOWN):
        logger.info("Phase 3: Already in New Bark Town, skipping house exit")
        result["phases_completed"].append("exit_house_skipped")
    elif _map_matches(pos.map_id, MAP_ELMS_LAB):
        logger.info("Phase 3: Already in Elm's Lab, skipping all navigation")
        result["phases_completed"].append("already_in_lab")

    # ── Phase 4: Walk to Elm's Lab ───────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position

    if _map_matches(pos.map_id, MAP_NEW_BARK_TOWN):
        logger.info("Phase 4: In New Bark Town, heading to Elm's Lab...")

        # Clear any outdoor dialog/cutscenes
        if state.menu_state == MenuState.DIALOG:
            clear_dialog_until_overworld_crystal(emu, reader, max_presses=30)

        # Elm's Lab door is at (6, 3) in New Bark Town (pret/pokecrystal).
        # Player exits house at roughly (13, 5). Navigate left to lab.
        # Navigate to one tile below the lab door, then step up.
        navigate_crystal(emu, reader, target_x=6, target_y=4)

        # Step UP onto the lab door warp tile at (6, 3)
        emu.press("up", hold_frames=10, wait_frames=120)
        emu.tick(120)

        state = reader.read_game_state()
        if _map_matches(state.position.map_id, MAP_ELMS_LAB):
            result["phases_completed"].append("enter_elms_lab")
        else:
            # Retry from slightly different positions
            for try_x in [5, 7, 6]:
                navigate_crystal(emu, reader, target_x=try_x, target_y=4)
                emu.press("up", hold_frames=10, wait_frames=120)
                emu.tick(120)
                state = reader.read_game_state()
                if _map_matches(state.position.map_id, MAP_ELMS_LAB):
                    result["phases_completed"].append("enter_elms_lab")
                    break

    # ── Phase 5: Elm's Lab dialog ────────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position

    if _map_matches(pos.map_id, MAP_ELMS_LAB):
        logger.info("Phase 5: In Elm's Lab, clearing dialog...")

        # Elm has a long intro speech. Clear it.
        if state.menu_state == MenuState.DIALOG:
            clear_dialog_until_overworld_crystal(emu, reader, max_presses=60)
            result["phases_completed"].append("elm_dialog")
        else:
            result["phases_completed"].append("elm_dialog_skipped")

        # Note: Starter selection is handled by the LLM agent, not boot sequence.
        # The boot sequence just gets us to Elm's Lab with dialog cleared.
        logger.info("Phase 5 complete: ready for starter selection (LLM)")

    # ── Final state ──────────────────────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position
    result["final_map"] = pos.map_id
    result["final_position"] = (pos.x, pos.y)
    result["success"] = len(result["phases_completed"]) >= 2

    logger.info("Crystal boot complete: %s", result)
    return result


def main():
    """Standalone Crystal boot sequence runner."""
    parser = argparse.ArgumentParser(
        description="Pokemon Crystal boot sequence automation",
    )
    parser.add_argument("--rom", default="pokemon_crystal.gbc", help="ROM path")
    parser.add_argument("--headless", action="store_true", help="No display")
    parser.add_argument("--speed", type=int, default=0, help="Emulator speed")
    parser.add_argument("--load-state", type=str, default=None, help="Load state")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )

    if not os.path.exists(args.rom):
        print(f"Error: ROM not found: {args.rom}")
        return 1

    from emulator_control import EmulatorControl
    from memory_reader import MemoryReader

    logger.info("Loading ROM: %s", args.rom)
    emu = EmulatorControl.from_rom(args.rom, headless=args.headless, speed=args.speed)
    emu.set_state_dir("states")

    if args.load_state:
        logger.info("Loading state: %s", args.load_state)
        emu.load_state(args.load_state)
    else:
        logger.info("Booting game (advancing 600 frames for logo/title)...")
        emu.tick(600)

    reader = MemoryReader(emu)

    try:
        result = run_crystal_boot_sequence(emu, reader)
        print(f"\nBoot result: {'SUCCESS' if result['success'] else 'PARTIAL'}")
        print(f"Phases completed: {result['phases_completed']}")
        print(f"Final map: {result['final_map']}, position: {result['final_position']}")

        state_path = emu.save_state("after_crystal_boot")
        print(f"State saved: {state_path}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        logger.exception("Boot error: %s", e)
        print(f"Error: {e}")
    finally:
        emu.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
