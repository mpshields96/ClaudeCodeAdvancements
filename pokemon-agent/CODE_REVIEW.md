# Codex Review: pokemon-agent

## Scope

Read-only review of all `.py` files under `pokemon-agent/`, plus:
- `pokemon-agent/bridge_io/state.json`
- `research/MT53_POKEMON_RESEARCH.md`

No existing Python files were modified.

## Current Runtime Context

Current bridge state shows the game at:
- `map_id=38`
- `map_name="REDS HOUSE 2F"`
- `position=(3,6)`
- `menu_state="dialog"`

That matches the next-phase target from `SESSION_STATE.md`: deterministic boot automation to clear dialog, get downstairs, and leave the house.

## Architecture Assessment

Overall architecture is good and mostly follows CCA's "one file = one job" rule:
- `emulator_control.py` cleanly isolates emulator I/O
- `memory_reader.py` / `memory_reader_red.py` separate RAM decoding from agent logic
- `agent.py` owns the loop and verification logic
- `navigation.py` is a self-contained pathfinding module
- `checkpoint.py`, `screen_detector.py`, `movement_validator.py`, `action_cache.py`, and `diversity_checker.py` are all nicely scoped support modules
- `bridge.py` provides a clean file-based Claude Code integration path

The strongest part of the design is that the harness is already thinking in the right abstractions: RAM ground truth, tool use, post-action verification, checkpointing, and deterministic automation for mechanical sequences.

The main architectural weakness is not file structure, but **wiring completeness**:
- several good subsystems exist but are not connected to the live path yet
- Red-specific and Crystal-specific runtime paths are mixed in one directory without a stronger top-level game boundary
- the exposed tool surface is ahead of the actually implemented execution surface

## Findings

### 1. Exposed tool surface does not match executable tool support

This is the biggest issue in the directory today.

- `pokemon-agent/tools.py:308-318` exposes 10 tools to the model, including `write_memory`, `delete_memory`, `add_marker`, `delete_marker`, and `update_objectives`
- `pokemon-agent/agent.py:649-672` only executes 4 tool names: `press_buttons`, `navigate_to`, `wait`, and `reload_checkpoint`
- every other advertised tool returns `{"error": "Unknown tool: ..."}` at runtime
- `pokemon-agent/agent_memory.py` exists and is reasonably well-structured, but it is currently orphaned from the live agent path

Why this matters:
- the model is being told capabilities exist that do not actually exist
- that increases prompt/tool mismatch risk exactly when the agent starts needing persistent planning and map memory
- it also means the promising `agent_memory.py` subsystem is currently dead weight

Recommendation:
- either wire the memory/marker/objective tools into `CrystalAgent._execute_tool()` immediately
- or remove them from `TOOLS` until the implementation path is real

### 2. `navigate_to` is effectively unavailable in the real entrypoint

The codebase has a good `Navigator`, but the runtime path does not actually supply one.

- `pokemon-agent/agent.py:214-222` accepts `navigator=None`
- `pokemon-agent/agent.py:695-723` implements `navigate_to`, but hard-fails with `{"error": "Navigator not available"}` when `self.navigator is None`
- `pokemon-agent/main.py:126-131` constructs `CrystalAgent(...)` without passing any navigator

Why this matters:
- the prompt and tool surface imply pathfinding is available
- the research doc explicitly calls out pathfinding as a critical borrowed architecture
- in real runtime, the tool is present but nonfunctional unless another caller wires it manually

Recommendation:
- treat this as a wiring bug, not a future enhancement
- build a minimal navigator bootstrap for the current map set, then pass it from `main.py`
- for the immediate Red intro phase, even a tiny map registry for `REDS HOUSE 2F`, `REDS HOUSE 1F`, `PALLET TOWN`, and `OAKS LAB` would unlock much more reliable automation than the current hardcoded directional walking

### 3. Bridge checkpointing appears broken

The bridge loop has checkpoint logic, but it is not comparing a real previous state to the current state.

- `pokemon-agent/bridge.py:271-296` tracks `prev_state`
- `pokemon-agent/bridge.py:287-291` reads `curr_gs = reader.read_game_state()` and then immediately sets `prev_gs = reader.read_game_state()  # Approximate`
- `prev_state` is assigned from `state_dict`, but never converted back into a previous `GameState` for checkpoint comparison

Why this matters:
- `CheckpointManager.should_checkpoint()` is designed around state transitions
- the bridge currently compares "current-ish" to "current-ish", so trainer battle / low HP / map transition checkpoints can be missed or behave inconsistently
- that undercuts one of the nicest safety features in the directory

Recommendation:
- keep the previous `GameState` object directly in the bridge loop
- compare `prev_gs` to `curr_gs` properly, mirroring how `CrystalAgent.step()` already does it

## Dead Code / Unwired Code

These are not all "bad", but they are worth naming clearly:

- `agent_memory.py` is currently an unwired subsystem rather than an active runtime dependency
- `_capture_screenshot()` in `agent.py` declares `tmp_path` at `pokemon-agent/agent.py:623` but never uses it
- the repo currently contains both Crystal-focused runtime files and Red-focused runtime files in one flat directory; that is workable for now, but it increases the chance of accidental cross-game assumptions

## Next-Phase Suggestions

For the immediate boot-automation target, I would do this next:

1. Make boot automation explicitly phase-based.
   - Treat intro progression as a deterministic state machine:
     - clear opening dialog
     - move to stairs
     - transition to 1F
     - clear Mom dialog if present
     - exit house
     - navigate toward Oak's Lab / cutscene trigger
   - `boot_sequence.py` is already close to this; formalizing phases and expected map/menu states would make it much easier to debug.

2. Add Red-specific text/name-screen helpers before expanding the LLM loop.
   - `state.json` currently shows `menu_state="dialog"` with empty `text_on_screen`
   - if the next step is naming the character and clearing early dialog reliably, Red needs some equivalent of Crystal's `TextReader`
   - even partial support for visible dialog lines / naming screen state would reduce blind button mashing

3. Wire a minimal navigator for the intro maps.
   - The current `navigate_to()` in `boot_sequence.py` is intentionally simple, but the project already has a much better abstraction in `navigation.py`
   - for the intro, a tiny hand-authored map registry is enough
   - that is probably the cleanest path toward "leave Red House 2F reliably" without overengineering

4. Add "facing direction" to structured state.
   - This came up in the broader MT-53 research and would help both deterministic automation and LLM reasoning
   - for indoor movement and stairs/door alignment, facing matters a lot

5. Decide whether the near-term runtime is Red-first or Crystal-first.
   - The directory name and many modules say "Crystal"
   - the live bridge state and boot automation work are clearly Red-oriented right now
   - that is okay, but the boundary should be made explicit so later features don't silently assume the wrong RAM map or prompt model

## Reference-Repo Patterns Worth Adopting

From `research/MT53_POKEMON_RESEARCH.md`, the most valuable patterns to adopt next are:

### 1. Fully wire the notepad/objectives/markers pattern

The GPT FireRed architecture uses persistent memory because long-horizon Pokemon play collapses without it. This repo already has the beginnings of that in `agent_memory.py`; the missing step is runtime integration.

### 2. Use deterministic automation for mechanical sequences

The research strongly supports using tools or scripts for things that do not need reasoning:
- clearing dialog
- naming screens
- known intro routes
- routine traversal

`boot_sequence.py` is the right move. I would lean further into that rather than asking the LLM to do intro boilerplate.

### 3. Promote navigator data, not just navigator code

The repo has pathfinding logic, but pathfinding only becomes valuable once the map data exists and is live in runtime. The next milestone should probably be:
- minimal map data for current Red intro maps
- then fog-of-war / markers later

### 4. Keep the post-action verification pattern

This is already one of the best parts of the harness. The Gemini-style "hallucination check" idea is correctly reflected in `agent.py`, and it is worth extending rather than replacing.

## Bottom Line

This is a strong directory with good decomposition and several genuinely smart design choices already in place. The biggest problem is not bad architecture; it is **unfinished wiring between good modules**.

If I were prioritizing work for the next MT-53 phase, I would do it in this order:

1. Fix tool-surface/runtime mismatch
2. Wire navigator into real runtime for the intro maps
3. Fix bridge checkpoint comparisons
4. Add Red text/name-screen support
5. Keep boot automation deterministic until the run reaches a point where open-ended reasoning is actually valuable

