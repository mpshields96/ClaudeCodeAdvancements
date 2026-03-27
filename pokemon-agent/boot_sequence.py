"""Boot sequence — automate Pokemon Red intro through to overworld.

Handles the deterministic intro sequence without LLM calls:
1. Clear opening dialog (Mom wakes you up)
2. Navigate downstairs from Red's House 2F to 1F
3. Exit Red's House to Pallet Town
4. Walk to Oak's Lab (where the real game begins)

This is step-by-step button automation. No randomness, no AI needed.
The game intro is the same every time — just mash through dialogs and walk.

Usage:
    # Run standalone (boots game and automates intro)
    python3 boot_sequence.py --rom pokemon_red.gb

    # Or use from bridge.py / main.py
    from boot_sequence import run_boot_sequence
    run_boot_sequence(emu, reader)

Stdlib + pyboy only.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

logger = logging.getLogger("boot")


# ── Pokemon Red intro map IDs ─────────────────────────────────────────────

MAP_REDS_HOUSE_2F = 38
MAP_REDS_HOUSE_1F = 37
MAP_PALLET_TOWN = 0
MAP_OAKS_LAB = 40

# ── Red House 2F layout (verified S211) ──────────────────────────────────
# Player starts at (3, 6). Stairs trigger at (7, 1) when stepping right.
# Walkable area verified by exhaustive movement scan:
#   - x=3..5 walkable at row 6 (blocked at x=6)
#   - x=5 walkable rows 1..6 (blocked at row 0)
#   - x=6..7 walkable at rows 1+
#   - Stepping right from (6,1) to (7,1) triggers map transition to 1F
# Path: right 2 to (5,6), up 5 to (5,1), right 2 → stairs at (7,1)
#
# ── Red House 1F layout (verified S211) ──────────────────────────────────
# Enter from stairs at (7, 1). Door mat at x=2 or x=3, y=7.
# Stepping down from (2,7) or (3,7) exits to Pallet Town (map 0).
# Path: down 6 to (7,7), left 5 to (2,7), down → exit


def clear_dialog(emu, presses: int = 20, hold: int = 4, wait: int = 16) -> None:
    """Mash A to clear all dialog/text boxes.

    Pokemon Red dialog requires repeated A presses. Each press advances
    one text box. 20 presses clears most multi-page dialogs.
    """
    logger.info("Clearing dialog (%d A presses)", presses)
    for i in range(presses):
        emu.press("a", hold_frames=hold, wait_frames=wait)
    # Extra ticks to let the game settle after dialog
    emu.tick(60)


def clear_dialog_until_overworld(emu, reader, max_presses: int = 50) -> bool:
    """Mash A until we're back in overworld state.

    Returns True if overworld was reached, False if max_presses exhausted.
    """
    from game_state import MenuState

    logger.info("Clearing dialog until overworld (max %d presses)", max_presses)
    for i in range(max_presses):
        state = reader.read_game_state()
        if state.menu_state == MenuState.OVERWORLD:
            logger.info("Overworld reached after %d presses", i)
            return True
        emu.press("a", hold_frames=4, wait_frames=20)

    # Check one final time
    state = reader.read_game_state()
    if state.menu_state == MenuState.OVERWORLD:
        logger.info("Overworld reached after %d presses", max_presses)
        return True

    logger.warning("Failed to reach overworld after %d presses", max_presses)
    return False


def navigate_to(emu, reader, target_x: int, target_y: int,
                max_steps: int = 30) -> bool:
    """Simple grid navigation — move toward target coordinates.

    No A* yet — just move in the right direction. Works for simple
    indoor rooms without obstacles in the path.

    Returns True if target reached.
    """
    for step in range(max_steps):
        state = reader.read_game_state()
        pos = state.position
        cx, cy = pos.x, pos.y

        if cx == target_x and cy == target_y:
            logger.info("Reached target (%d, %d) in %d steps", target_x, target_y, step)
            return True

        # Determine direction
        dx = target_x - cx
        dy = target_y - cy

        # Prefer horizontal movement first, then vertical
        if dx > 0:
            direction = "right"
        elif dx < 0:
            direction = "left"
        elif dy < 0:
            direction = "up"
        elif dy > 0:
            direction = "down"
        else:
            return True  # Already there

        logger.debug("Step %d: (%d,%d) -> %s toward (%d,%d)",
                     step, cx, cy, direction, target_x, target_y)

        # Use the proven timing from S209: hold=10, wait=120
        emu.press(direction, hold_frames=10, wait_frames=120)

    # Final check
    state = reader.read_game_state()
    pos = state.position
    reached = (pos.x == target_x and pos.y == target_y)
    if not reached:
        logger.warning("Did not reach (%d, %d) — at (%d, %d) after %d steps",
                       target_x, target_y, pos.x, pos.y, max_steps)
    return reached


def wait_for_map(emu, reader, target_map_id: int,
                 max_ticks: int = 300) -> bool:
    """Wait for a map transition to complete.

    After stepping on stairs/doors, the game takes several frames to
    load the new map. Poll until the map ID changes.
    """
    for _ in range(max_ticks // 10):
        emu.tick(10)
        state = reader.read_game_state()
        if state.position.map_id == target_map_id:
            logger.info("Map transition complete: map %d", target_map_id)
            return True

    state = reader.read_game_state()
    logger.warning("Map transition timeout: expected %d, got %d",
                   target_map_id, state.position.map_id)
    return (state.position.map_id == target_map_id)


def run_boot_sequence(emu, reader) -> dict:
    """Run the full boot sequence from game start to Pallet Town.

    Assumes the game has just been loaded (title screen or in-game start).

    Returns a dict with:
        success: bool
        final_map: int
        final_position: (x, y)
        steps_taken: int
    """
    result = {
        "success": False,
        "final_map": -1,
        "final_position": (0, 0),
        "phases_completed": [],
    }

    # ── Phase 0: Initial state check ──────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position
    logger.info("Boot start: map=%d (%s), pos=(%d,%d), menu=%s",
                pos.map_id, pos.map_name, pos.x, pos.y,
                state.menu_state.value)

    # If we're still at title screen, mash through it
    if pos.map_id == 0 and pos.x == 0 and pos.y == 0:
        logger.info("Phase 0: At title screen, mashing through...")
        # Title screen -> New Game -> intro
        clear_dialog(emu, presses=30, wait=20)
        emu.tick(120)
        result["phases_completed"].append("title_screen")

    # ── Phase 1: Clear opening dialog ─────────────────────────────────────
    logger.info("Phase 1: Clearing opening dialog...")
    state = reader.read_game_state()

    if state.menu_state.value == "dialog":
        success = clear_dialog_until_overworld(emu, reader, max_presses=50)
        if success:
            result["phases_completed"].append("opening_dialog")
            logger.info("Phase 1 complete: dialog cleared")
        else:
            # Try harder — some dialogs need B presses to dismiss
            logger.info("Phase 1: Trying B presses to clear remaining dialog...")
            for _ in range(10):
                emu.press("b", hold_frames=4, wait_frames=16)
            clear_dialog_until_overworld(emu, reader, max_presses=20)
            result["phases_completed"].append("opening_dialog_forced")
    else:
        logger.info("Phase 1: Already in overworld, skipping dialog clear")
        result["phases_completed"].append("opening_dialog_skipped")

    # ── Phase 2: Navigate to stairs in Red's House 2F ─────────────────────
    state = reader.read_game_state()
    pos = state.position

    if pos.map_id == MAP_REDS_HOUSE_2F:
        logger.info("Phase 2: Navigating to stairs in Red's House 2F...")
        logger.info("  Current position: (%d, %d)", pos.x, pos.y)

        # Verified path (S211): right 2 to (5,6), up 5 to (5,1), right 2
        # Column 6+ is blocked at row 6, so go up first then across.
        navigate_to(emu, reader, target_x=5, target_y=pos.y)  # right to x=5
        navigate_to(emu, reader, target_x=5, target_y=1)      # up to row 1
        navigate_to(emu, reader, target_x=7, target_y=1)      # right to stairs

        # Check if stepping to (7,1) already triggered transition
        state = reader.read_game_state()
        if state.position.map_id == MAP_REDS_HOUSE_1F:
            result["phases_completed"].append("stairs_to_1f")
            logger.info("Phase 2 complete: arrived at Red's House 1F")
        else:
            # Try stepping up onto stair tile
            emu.press("up", hold_frames=10, wait_frames=120)
            emu.tick(60)
            if wait_for_map(emu, reader, MAP_REDS_HOUSE_1F, max_ticks=300):
                result["phases_completed"].append("stairs_to_1f")
                logger.info("Phase 2 complete: arrived at Red's House 1F")
            else:
                logger.warning("Phase 2: Stairs didn't trigger")
    elif pos.map_id == MAP_REDS_HOUSE_1F:
        logger.info("Phase 2: Already on 1F, skipping stairs navigation")
        result["phases_completed"].append("stairs_skipped")

    # ── Phase 3: Navigate through Red's House 1F and exit ─────────────────
    state = reader.read_game_state()
    pos = state.position

    if pos.map_id == MAP_REDS_HOUSE_1F:
        logger.info("Phase 3: In Red's House 1F, navigating to exit...")
        logger.info("  Current position: (%d, %d)", pos.x, pos.y)

        # Clear any dialog from Mom on 1F
        if state.menu_state.value == "dialog":
            clear_dialog_until_overworld(emu, reader, max_presses=30)

        # Verified path (S211): door mat at x=2-3, y=7. Step down to exit.
        # Enter from stairs at (7,1). Go down to row 7, left to x=3, down.
        navigate_to(emu, reader, target_x=pos.x, target_y=7)  # down first
        navigate_to(emu, reader, target_x=3, target_y=7)       # left to door

        # Step down to exit
        emu.press("down", hold_frames=10, wait_frames=120)
        emu.tick(60)

        if wait_for_map(emu, reader, MAP_PALLET_TOWN, max_ticks=300):
            result["phases_completed"].append("exit_house")
            logger.info("Phase 3 complete: arrived at Pallet Town")
        else:
            # Try the other door tile
            navigate_to(emu, reader, target_x=2, target_y=7)
            emu.press("down", hold_frames=10, wait_frames=120)
            emu.tick(120)
            state = reader.read_game_state()
            if state.position.map_id == MAP_PALLET_TOWN:
                result["phases_completed"].append("exit_house")

    # ── Phase 4: Walk to Oak's Lab ────────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position

    if pos.map_id == MAP_PALLET_TOWN:
        logger.info("Phase 4: In Pallet Town, heading to Oak's Lab...")
        logger.info("  Current position: (%d, %d)", pos.x, pos.y)

        # In Pokemon Red, Red's house exit puts you near (3, 3-4) area.
        # Oak's Lab is south of the town. Door at approximately (4, 11).
        # But the game might trigger Prof Oak cutscene when you try to leave.

        # For now, just clear any cutscene dialogs and navigate south
        if state.menu_state.value == "dialog":
            clear_dialog_until_overworld(emu, reader, max_presses=30)

        # Oak's Lab door — walk south and slightly right
        navigate_to(emu, reader, target_x=4, target_y=9)
        emu.press("down", hold_frames=10, wait_frames=120)
        emu.tick(120)

        state = reader.read_game_state()
        if state.position.map_id == MAP_OAKS_LAB:
            result["phases_completed"].append("enter_oaks_lab")
            logger.info("Phase 4 complete: arrived at Oak's Lab!")

    # ── Final state ───────────────────────────────────────────────────────
    state = reader.read_game_state()
    pos = state.position
    result["final_map"] = pos.map_id
    result["final_position"] = (pos.x, pos.y)
    result["success"] = len(result["phases_completed"]) >= 2  # At least dialog + navigation

    logger.info("Boot sequence complete: %s", result)
    return result


def main():
    """Standalone boot sequence runner."""
    parser = argparse.ArgumentParser(description="Pokemon Red boot sequence automation")
    parser.add_argument("--rom", default="pokemon_red.gb", help="ROM path")
    parser.add_argument("--headless", action="store_true", help="No display")
    parser.add_argument("--speed", type=int, default=0, help="Emulator speed (0=uncapped)")
    parser.add_argument("--load-state", type=str, default=None, help="Load saved state")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Setup logging
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
    from memory_reader_red import MemoryReaderRed

    logger.info("Loading ROM: %s", args.rom)
    emu = EmulatorControl.from_rom(args.rom, headless=args.headless, speed=args.speed)
    emu.set_state_dir("states")

    if args.load_state:
        logger.info("Loading state: %s", args.load_state)
        emu.load_state(args.load_state)
    else:
        # Boot the game — advance past logo
        logger.info("Booting game (advancing 600 frames for logo/title)...")
        emu.tick(600)

    reader = MemoryReaderRed(emu)

    try:
        result = run_boot_sequence(emu, reader)
        print(f"\nBoot result: {'SUCCESS' if result['success'] else 'PARTIAL'}")
        print(f"Phases completed: {result['phases_completed']}")
        print(f"Final map: {result['final_map']}, position: {result['final_position']}")

        # Save state after boot
        state_path = emu.save_state("after_boot")
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
