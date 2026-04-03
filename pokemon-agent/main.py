"""Pokemon Crystal autonomous agent — entry point.

Usage:
    python3 main.py --rom pokemon_crystal.gbc --steps 1000
    python3 main.py --rom pokemon_crystal.gbc --headless --steps 500
    python3 main.py --rom pokemon_crystal.gbc --load-state states/before_gym.state

Runs entirely offline except for LLM API calls (Anthropic).
The emulator, RAM reading, pathfinding, and state management are local.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from config import DEFAULT_ROM, LOG_DIR, STATE_DIR, SCREENSHOT_DIR

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def setup_logging(log_dir: str, verbose: bool = False) -> None:
    """Configure logging to file and console."""
    os.makedirs(log_dir, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "crystal_agent.log")),
            logging.StreamHandler(),
        ],
    )


def parse_args(argv=None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pokemon Crystal autonomous agent powered by Opus 4.6",
    )
    parser.add_argument(
        "--rom", default=DEFAULT_ROM,
        help=f"Path to Pokemon Crystal ROM (.gbc). Default: {DEFAULT_ROM}",
    )
    parser.add_argument(
        "--steps", type=int, default=1000,
        help="Number of agent steps to run. Default: 1000",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run without display window (for CI/servers).",
    )
    parser.add_argument(
        "--speed", type=int, default=0,
        help="Emulator speed: 0=uncapped, 1=normal, N=Nx. Default: 0 (fastest).",
    )
    parser.add_argument(
        "--load-state", type=str, default=None,
        help="Load a saved emulator state before starting.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug-level logging.",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Offline mode: run emulator without LLM calls (for testing).",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override LLM model name (e.g. claude-haiku-4-5-20251001). Default: config.py MODEL_NAME.",
    )
    parser.add_argument(
        "--backend", type=str, default="anthropic",
        choices=["anthropic", "gemini", "auto"],
        help="LLM backend: anthropic (default), gemini (free tier), auto (try gemini then anthropic).",
    )
    return parser.parse_args(argv)


def _init_llm(backend: str, logger):
    """Initialize LLM client based on backend choice.

    Args:
        backend: 'anthropic', 'gemini', or 'auto'
        logger: Logger instance

    Returns:
        LLM client or None on failure.
    """
    backends_to_try = []
    if backend == "auto":
        backends_to_try = ["gemini", "anthropic"]
    else:
        backends_to_try = [backend]

    for name in backends_to_try:
        try:
            if name == "gemini":
                from gemini_client import GeminiClient
                client = GeminiClient()
                logger.info("Gemini client initialized (free tier)")
                return client
            else:
                from agent import AnthropicClient
                client = AnthropicClient()
                logger.info("Anthropic client initialized")
                return client
        except ImportError as e:
            logger.warning("Backend %s unavailable: %s", name, e)
            if backend != "auto":
                print(f"Error: {e}")
                return None
        except (ValueError, Exception) as e:
            logger.warning("Backend %s failed: %s", name, e)
            if backend != "auto":
                print(f"Error: {e}")
                return None

    logger.error("No LLM backend available. Install google-generativeai or anthropic.")
    print("Error: No LLM backend available. Set GEMINI_API_KEY or ANTHROPIC_API_KEY.")
    return None


def resolve_model_name(backend: str, cli_model: str | None) -> str | None:
    """Resolve the model override to pass into CrystalAgent.

    Anthropic can keep using config.MODEL_NAME by omitting an override.
    Gemini needs an explicit Gemini model unless the user provided one.
    """
    if cli_model:
        return cli_model
    if backend in {"gemini", "auto"}:
        return DEFAULT_GEMINI_MODEL
    return None


def detect_game_type(rom_path: str) -> str:
    """Detect game type from ROM file extension.

    Returns 'red' for .gb, 'crystal' for .gbc, 'firered' for .gba.
    Defaults to 'red' for unknown extensions.
    """
    rom_lower = rom_path.lower()
    if rom_lower.endswith(".gbc"):
        return "crystal"
    elif rom_lower.endswith(".gba"):
        return "firered"
    else:
        return "red"


def main(argv=None) -> int:
    """Run the Pokemon agent."""
    args = parse_args(argv)
    setup_logging(LOG_DIR, verbose=args.verbose)
    logger = logging.getLogger("pokemon")

    # Check ROM exists
    if not os.path.exists(args.rom):
        logger.error("ROM not found: %s", args.rom)
        print(f"Error: ROM file not found: {args.rom}")
        print(f"Place your Pokemon ROM at: {os.path.abspath(args.rom)}")
        return 1

    # Create directories
    for d in (STATE_DIR, SCREENSHOT_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)

    game_type = detect_game_type(args.rom)
    logger.info("Detected game type: %s", game_type)

    # Initialize emulator
    from emulator_control import EmulatorControl

    logger.info("Loading ROM: %s", args.rom)
    emu = EmulatorControl.from_rom(
        args.rom, headless=args.headless, speed=args.speed,
    )
    emu.set_state_dir(STATE_DIR)

    # Load saved state if requested
    if args.load_state:
        logger.info("Loading state: %s", args.load_state)
        emu.load_state(args.load_state)

    # Initialize LLM
    llm = None
    if not args.offline:
        llm = _init_llm(args.backend, logger)
        if llm is None:
            emu.close()
            return 1
    else:
        logger.info("Offline mode — no LLM calls")

    # Create game-specific agent
    if game_type == "red":
        from red_agent import RedAgent
        auto_boot = not args.load_state  # Boot only if no saved state
        agent = RedAgent(emulator=emu, llm=llm, auto_boot=auto_boot)
        logger.info("RedAgent created (auto_boot=%s)", auto_boot)
    else:
        from memory_reader import MemoryReader
        from agent import CrystalAgent
        from crystal_intro_navigation import build_crystal_intro_navigator
        reader = MemoryReader(emu)
        agent_kwargs = dict(
            emulator=emu,
            reader=reader,
            llm=llm,
            navigator=build_crystal_intro_navigator(),
        )
        model_name = resolve_model_name(args.backend, args.model)
        if model_name:
            agent_kwargs["model_name"] = model_name
        agent = CrystalAgent(**agent_kwargs)

        # Run Crystal boot sequence if starting from fresh ROM
        if not args.load_state:
            from boot_sequence_crystal import run_crystal_boot_sequence
            logger.info("Running Crystal boot sequence...")
            boot_result = run_crystal_boot_sequence(emu, reader)
            if boot_result["success"]:
                logger.info("Crystal boot complete: %s", boot_result["phases_completed"])
            else:
                logger.warning("Crystal boot partial: %s", boot_result["phases_completed"])

    # Step callback for live progress
    def on_step(result):
        pos = result.state.position
        badges = result.state.badges.count()
        party_size = result.state.party.size()
        markers = []
        if result.was_stuck:
            markers.append("STUCK")
        if result.was_summarized:
            markers.append("SUMMARIZED")
        # Detect auto-advance and cache hits from tool results
        for tr in result.tool_results:
            if isinstance(tr, dict):
                if tr.get("auto"):
                    markers.append("AUTO")
                if tr.get("cached"):
                    markers.append(f"CACHED({agent.action_cache.hit_rate()*100:.0f}%)")
        marker_str = " [" + ", ".join(markers) + "]" if markers else ""
        print(
            f"Step {result.step_number}: "
            f"Map {pos.map_id} ({pos.x},{pos.y}) | "
            f"Badges: {badges}/8 | "
            f"Party: {party_size} | "
            f"Tokens: {result.input_tokens}+{result.output_tokens}"
            f"{marker_str}"
        )

    agent.on_step(on_step)

    # Run
    logger.info("Starting agent for %d steps", args.steps)
    start_time = time.time()

    try:
        results = agent.run(num_steps=args.steps)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted. Saving state...")
        agent._save_state()
    except Exception as e:
        logger.exception("Agent error: %s", e)
        print(f"\nError: {e}")
        agent._save_state()
    finally:
        elapsed = time.time() - start_time
        usage = agent.token_usage
        mv_stats = agent.movement_validator.stats()
        cache_stats = agent.action_cache.stats()
        logger.info(
            "Done. Steps: %d, Time: %.1fs, Tokens: %d in + %d out = %d total",
            usage["steps"], elapsed,
            usage["input_tokens"], usage["output_tokens"],
            usage["total_tokens"],
        )
        print(f"\nSession complete: {usage['steps']} steps in {elapsed:.1f}s")
        print(f"Tokens: {usage['total_tokens']:,} total "
              f"({usage['input_tokens']:,} in + {usage['output_tokens']:,} out)")
        print(f"Auto-advances: {agent.auto_advance_count} | "
              f"Cache: {cache_stats.get('hits', 0)} hits, "
              f"{cache_stats.get('size', 0)} entries | "
              f"Blocked dirs: {mv_stats['blocked_directions']}")
        emu.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
