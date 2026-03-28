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

Map IDs (group, number) — from pret/pokecrystal:
- (3, 4): Player's House 2F — wake up here
- (3, 3): Player's House 1F — Mom is here
- (3, 1): New Bark Town — starting town
- (3, 2): Elm's Lab — get starter

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
# Source: pret/pokecrystal constants/map_constants.asm

MAP_PLAYERS_HOUSE_2F = (3, 4)   # Player starts here — bedroom
MAP_PLAYERS_HOUSE_1F = (3, 3)   # Downstairs — Mom
MAP_NEW_BARK_TOWN = (3, 1)      # Starting town
MAP_ELMS_LAB = (3, 2)           # Professor Elm's lab — get starter


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

    # Title screen detection: map 0, position (0,0)
    if pos.map_id == 0 and pos.x == 0 and pos.y == 0:
        logger.info("Phase 0: Title screen detected, mashing through...")
        # Title → language select → New Game → name entry → intro cutscene
        # Crystal has more title screens than Red
        clear_dialog_crystal(emu, presses=40, wait=20)
        emu.tick(180)  # Wait for game to load after title
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
        # Crystal Player's House 2F layout:
        # Player wakes up at approximately (4, 4). Stairs at (7, 1).
        # Path: right to x=5, up to y=1, right to stairs
        logger.info("Phase 2: Navigating to stairs in Player's House 2F...")
        state = reader.read_game_state()
        pos = state.position

        navigate_crystal(emu, reader, target_x=5, target_y=pos.y)
        navigate_crystal(emu, reader, target_x=5, target_y=1)
        navigate_crystal(emu, reader, target_x=7, target_y=1)

        # Check if transition already happened
        state = reader.read_game_state()
        if _map_matches(state.position.map_id, MAP_PLAYERS_HOUSE_1F):
            result["phases_completed"].append("stairs_to_1f")
        else:
            # Try stepping right onto stairs tile
            emu.press("right", hold_frames=10, wait_frames=120)
            emu.tick(60)
            if wait_for_map_crystal(emu, reader, MAP_PLAYERS_HOUSE_1F):
                result["phases_completed"].append("stairs_to_1f")
            else:
                logger.warning("Phase 2: Stairs transition didn't trigger")

    # ── Phase 3: Player's House 1F → exit to New Bark Town ───────────────
    state = reader.read_game_state()
    pos = state.position

    if _map_matches(pos.map_id, MAP_PLAYERS_HOUSE_1F):
        logger.info("Phase 3: In Player's House 1F, navigating to exit...")

        # Clear Mom's dialog if present
        if state.menu_state == MenuState.DIALOG:
            clear_dialog_until_overworld_crystal(emu, reader, max_presses=30)

        # Crystal House 1F: enter from stairs at top, door mat at bottom
        # Navigate down and to the door
        navigate_crystal(emu, reader, target_x=pos.x, target_y=7)
        navigate_crystal(emu, reader, target_x=3, target_y=7)

        # Step down to exit
        emu.press("down", hold_frames=10, wait_frames=120)
        emu.tick(60)

        if wait_for_map_crystal(emu, reader, MAP_NEW_BARK_TOWN):
            result["phases_completed"].append("exit_house")
        else:
            # Try adjacent door tile
            navigate_crystal(emu, reader, target_x=2, target_y=7)
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

        # In Crystal, Elm's Lab is left of Player's House.
        # Approximate coordinates: Lab door around (4, 4) in New Bark.
        # Player exits house roughly at center of town.
        navigate_crystal(emu, reader, target_x=4, target_y=6)

        # Try entering the lab door (step up into it)
        emu.press("up", hold_frames=10, wait_frames=120)
        emu.tick(120)

        state = reader.read_game_state()
        if _map_matches(state.position.map_id, MAP_ELMS_LAB):
            result["phases_completed"].append("enter_elms_lab")
        else:
            # Lab might be at slightly different coordinates
            # Try a few adjacent tiles
            for try_x in [3, 5, 4]:
                navigate_crystal(emu, reader, target_x=try_x, target_y=5)
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
