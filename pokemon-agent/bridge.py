"""Claude Code bridge — runs the emulator and communicates via files.

This script runs PyBoy headlessly and exposes game state via files that
Claude Code can read. Claude Code acts as the brain (via slash command),
reads the state, and writes actions. This script picks up those actions
and executes them. Zero API cost — uses your Max subscription.

Supports: Pokemon Red (.gb), Pokemon Crystal (.gbc)

Architecture:
    bridge.py (this)          <-->  Claude Code session
    - Runs PyBoy emulator            - Reads state.json
    - Writes state.json               - Reads screenshot.png
    - Writes screenshot.png            - Writes action.json
    - Reads action.json                - Reasons about game
    - Executes the action              - Decides next move
    - Loop                             - Loop

Usage:
    # Terminal 1: Start the emulator bridge
    cd pokemon-agent
    python3 bridge.py --rom pokemon_red.gb

    # Terminal 2 (Claude Code): Run the brain
    /pokemon-play

Files (in pokemon-agent/bridge_io/):
    state.json      - Current game state (RAM data)
    screenshot.png  - Current screen capture
    action.json     - Next action from Claude Code
    log.jsonl       - Step-by-step history

Stdlib + pyboy only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add pokemon-agent to path
sys.path.insert(0, os.path.dirname(__file__))

from config import DEFAULT_ROM, STATE_DIR

BRIDGE_DIR = os.path.join(os.path.dirname(__file__), "bridge_io")
STATE_FILE = os.path.join(BRIDGE_DIR, "state.json")
SCREENSHOT_FILE = os.path.join(BRIDGE_DIR, "screenshot.png")
ACTION_FILE = os.path.join(BRIDGE_DIR, "action.json")
LOG_FILE = os.path.join(BRIDGE_DIR, "log.jsonl")
READY_FILE = os.path.join(BRIDGE_DIR, ".ready")
STOP_FILE = os.path.join(BRIDGE_DIR, ".stop")


def write_state(reader, emu, step: int, text_reader=None) -> dict:
    """Read game state from RAM and write to state.json + screenshot."""
    from game_state import MenuState

    state = reader.read_game_state()

    # Build state dict
    party_data = []
    for mon in state.party.pokemon:
        moves = [{"name": m.name, "pp": m.pp} for m in mon.moves]
        party_data.append({
            "species": mon.species,
            "nickname": mon.nickname,
            "level": mon.level,
            "hp": mon.hp,
            "hp_max": mon.hp_max,
            "status": mon.status,
            "moves": moves,
        })

    battle_data = None
    if state.battle.in_battle:
        enemy = state.battle.enemy
        battle_data = {
            "type": state.battle.battle_type(),
            "enemy_species": enemy.species if enemy else "unknown",
            "enemy_level": enemy.level if enemy else 0,
            "enemy_hp": enemy.hp if enemy else 0,
            "enemy_hp_max": enemy.hp_max if enemy else 0,
        }

    # Read text from RAM
    text_context = ""
    if text_reader:
        text_context = text_reader.format_for_prompt()

    state_dict = {
        "step": step,
        "position": {
            "map_id": state.position.map_id,
            "map_group": state.position.map_group,
            "map_number": state.position.map_number,
            "map_name": state.position.map_name or f"Map {state.position.map_group}:{state.position.map_number}",
            "x": state.position.x,
            "y": state.position.y,
        },
        "menu_state": state.menu_state.value,
        "badges": state.badges.count(),
        "money": state.money,
        "party": party_data,
        "battle": battle_data,
        "text_on_screen": text_context,
        "play_time_minutes": state.play_time_minutes,
    }

    # Write state
    with open(STATE_FILE, "w") as f:
        json.dump(state_dict, f, indent=2)

    # Take screenshot
    try:
        emu.screenshot("bridge_screenshot")
        src = emu._state_path("bridge_screenshot", ext=".png")
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, SCREENSHOT_FILE)
    except Exception:
        pass  # Screenshot optional

    # Signal ready
    Path(READY_FILE).touch()

    return state_dict


def read_action() -> dict | None:
    """Read and consume action.json written by Claude Code."""
    if not os.path.exists(ACTION_FILE):
        return None

    try:
        with open(ACTION_FILE) as f:
            action = json.load(f)
        os.remove(ACTION_FILE)  # Consume it
        return action
    except (json.JSONDecodeError, OSError):
        return None


def execute_action(emu, action: dict, nav=None, collision_reader=None) -> dict:
    """Execute an action from Claude Code on the emulator.

    Args:
        emu: EmulatorControl instance.
        action: Action dict from Claude Code.
        nav: Optional Navigator for A* pathfinding (Red games).
        collision_reader: Optional CollisionReaderRed for building maps.
    """
    action_type = action.get("type", "press_buttons")
    result = {}

    if action_type == "press_buttons":
        buttons = action.get("buttons", ["a"])
        for button in buttons:
            if button in ("a", "b", "start", "select", "up", "down", "left", "right"):
                # Directional buttons need longer hold for Crystal to register movement
                if button in ("up", "down", "left", "right"):
                    emu.press(button, hold_frames=8, wait_frames=12)
                else:
                    emu.press(button, hold_frames=4, wait_frames=12)
        result = {"executed": "press_buttons", "buttons": buttons}

    elif action_type == "wait":
        frames = action.get("frames", 60)
        emu.tick(frames)
        result = {"executed": "wait", "frames": frames}

    elif action_type == "save":
        name = action.get("name", f"bridge_save")
        path = emu.save_state(name)
        result = {"executed": "save", "path": path}

    elif action_type == "load":
        name = action.get("name", "bridge_save")
        try:
            emu.load_state(name)
            result = {"executed": "load", "name": name}
        except Exception as e:
            result = {"executed": "load", "error": str(e)}

    elif action_type == "navigate":
        # A* pathfinding: move to a target tile, optionally cross-map
        target_x = action.get("x")
        target_y = action.get("y")
        target_map = action.get("map_id")  # Optional: for cross-map navigation
        if nav is None or collision_reader is None:
            result = {"error": "navigate requires collision_reader (Red games only)"}
        elif target_x is None or target_y is None:
            result = {"error": "navigate requires x and y"}
        else:
            result = _execute_navigate(emu, nav, collision_reader, target_x, target_y, target_map)

    else:
        result = {"error": f"Unknown action type: {action_type}"}

    return result


def _execute_navigate(emu, nav, collision_reader, target_x: int, target_y: int,
                      target_map: int = None) -> dict:
    """Execute A* navigation to a target tile, optionally on a different map.

    Builds the collision map from current RAM state, runs A*, and
    executes the resulting path as directional button presses.
    For cross-map navigation, uses warps and connections loaded at startup.
    """
    from navigation import Navigator
    from game_state import MapPosition
    import memory_reader_red as mrr

    # Read current position
    map_id = emu.read_byte(mrr.MAP_ID)
    cur_x = emu.read_byte(mrr.PLAYER_X)
    cur_y = emu.read_byte(mrr.PLAYER_Y)

    # Default target_map to current map (same-map navigation)
    if target_map is None:
        target_map = map_id

    # Build fresh collision map
    map_data = collision_reader.build_current_map()
    if not nav.has_map(map_id):
        nav.add_map(map_data)
    else:
        # Replace with fresh data (NPCs may have moved)
        nav._maps[map_id] = map_data

    start = MapPosition(map_id=map_id, x=cur_x, y=cur_y)
    goal = MapPosition(map_id=target_map, x=target_x, y=target_y)

    path = nav.find_path(start, goal)
    if path is None:
        return {"executed": "navigate", "error": "no path found",
                "from": (cur_x, cur_y), "to": (target_x, target_y)}

    if len(path) == 0:
        return {"executed": "navigate", "steps": 0, "already_there": True}

    # Execute each step (skip warp markers — warps trigger automatically)
    directions = Navigator.path_to_directions(path)
    for direction in directions:
        if direction == "warp":
            continue  # Warp happens when player steps on the tile
        emu.press(direction, hold_frames=8, wait_frames=12)

    return {
        "executed": "navigate",
        "steps": len(directions),
        "path": directions,
        "from": (cur_x, cur_y),
        "to": (target_x, target_y),
    }


def log_step(step: int, state: dict, action: dict, result: dict):
    """Append step to the log file."""
    entry = {
        "step": step,
        "position": state.get("position"),
        "action": action,
        "result": result,
        "timestamp": time.time(),
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def maybe_checkpoint(prev_state, curr_state, checkpoint_mgr, step: int) -> list[str]:
    """Check for checkpoint-worthy transitions and save if needed.

    Returns the string values of any triggered checkpoint reasons.
    """
    if prev_state is None:
        return []

    reasons = checkpoint_mgr.should_checkpoint(
        prev_state,
        curr_state,
        current_step=step,
    )
    if reasons:
        checkpoint_mgr.save_checkpoint(step=step, reasons=reasons)
    return [r.value for r in reasons]


def main():
    parser = argparse.ArgumentParser(description="Pokemon Crystal emulator bridge for Claude Code")
    parser.add_argument("--rom", default=DEFAULT_ROM, help="ROM path")
    parser.add_argument("--headless", action="store_true", help="No display window")
    parser.add_argument("--speed", type=int, default=1, help="Emulator speed (1=normal, 0=uncapped)")
    parser.add_argument("--load-state", type=str, default=None, help="Load a saved state on boot")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for Claude Code action")
    args = parser.parse_args()

    # Create bridge directory
    os.makedirs(BRIDGE_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)

    # Clean up any stale files
    for f in (ACTION_FILE, READY_FILE, STOP_FILE):
        if os.path.exists(f):
            os.remove(f)

    # Boot emulator
    from emulator_control import EmulatorControl
    from checkpoint import CheckpointManager

    # Detect ROM type from file extension
    rom_lower = args.rom.lower()
    if rom_lower.endswith(".gb"):
        game_type = "red"
    elif rom_lower.endswith(".gbc"):
        game_type = "crystal"
    else:
        game_type = "red"  # Default

    print(f"Loading ROM: {args.rom} (detected: {game_type})")
    emu = EmulatorControl.from_rom(args.rom, headless=args.headless, speed=args.speed)
    emu.set_state_dir(STATE_DIR)

    # Use the right memory reader for the game
    collision_reader = None
    nav = None
    if game_type == "red":
        from memory_reader_red import MemoryReaderRed
        from text_reader_red import TextReaderRed
        from collision_reader_red import CollisionReaderRed
        from navigation import Navigator
        reader = MemoryReaderRed(emu)
        text_reader = TextReaderRed(emu)
        collision_reader = CollisionReaderRed(emu)
        nav = Navigator()
        # Load static warps and connections for cross-map A*
        from warp_data_red import WARP_TABLE, CONNECTION_TABLE
        for warp in WARP_TABLE:
            nav.add_warp(warp)
        for conn in CONNECTION_TABLE:
            nav.add_connection(conn)
    else:
        from memory_reader import MemoryReader
        from text_reader import TextReader
        reader = MemoryReader(emu)
        text_reader = TextReader(emu)

    checkpoint_mgr = CheckpointManager(emu, state_dir=STATE_DIR)
    if game_type == "crystal":
        checkpoint_mgr.register_crystal_gyms()

    if args.load_state:
        print(f"Loading state: {args.load_state}")
        emu.load_state(args.load_state)
        # Stabilize after load — tick to let game settle, then clear any dialog
        emu.tick(30)
        # Mash B+A to clear any stuck dialog/text boxes from save state
        for _ in range(5):
            emu.press("b", hold_frames=4, wait_frames=8)
        for _ in range(3):
            emu.press("a", hold_frames=4, wait_frames=8)
        emu.tick(30)
        print("  State loaded, dialog cleared.")
    else:
        # Let the game boot (title screen)
        print("Booting game (advancing 300 frames)...")
        emu.tick(300)

    print(f"\nBridge running. Waiting for Claude Code actions in: {BRIDGE_DIR}/")
    print(f"Timeout: {args.timeout}s per step")
    print("To stop: create a .stop file or Ctrl+C\n")

    step = 0
    prev_gs = None

    try:
        while True:
            # Check for stop signal
            if os.path.exists(STOP_FILE):
                print("Stop signal received.")
                break

            step += 1

            # Write current state
            state_dict = write_state(reader, emu, step, text_reader)

            # Checkpoint check
            curr_gs = reader.read_game_state()
            reason_names = maybe_checkpoint(prev_gs, curr_gs, checkpoint_mgr, step)
            if reason_names:
                print(f"  [Checkpoint: {reason_names}]")
            prev_gs = curr_gs

            # Print status
            pos = state_dict["position"]
            party_lead = state_dict["party"][0] if state_dict["party"] else None
            lead_str = f"{party_lead['species']} Lv{party_lead['level']} HP:{party_lead['hp']}/{party_lead['hp_max']}" if party_lead else "no party"
            print(f"Step {step}: Map {pos['map_id']} ({pos['x']},{pos['y']}) | {lead_str} | Waiting for action...")

            # Wait for Claude Code to write an action
            waited = 0.0
            poll_interval = 0.5
            while waited < args.timeout:
                action = read_action()
                if action is not None:
                    break
                time.sleep(poll_interval)
                waited += poll_interval
            else:
                print(f"  Timeout ({args.timeout}s) — pressing A as default")
                action = {"type": "press_buttons", "buttons": ["a"]}

            # Execute
            result = execute_action(emu, action, nav=nav, collision_reader=collision_reader)
            buttons = action.get("buttons", [])
            print(f"  -> {action.get('type', '?')}: {buttons if buttons else action} | {result}")

            # Log
            log_step(step, state_dict, action, result)

            # Let game process movement animation (16 frames for a step)
            emu.tick(20)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        # Save final state
        emu.save_state("bridge_final")
        emu.close()
        # Clean up ready signal
        if os.path.exists(READY_FILE):
            os.remove(READY_FILE)
        print(f"Bridge stopped after {step} steps. Final state saved.")


if __name__ == "__main__":
    main()
