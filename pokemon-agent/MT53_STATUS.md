# MT-53: Pokemon Crystal Bot — Status & Observations

## Current State (Codex takeover — 2026-04-02)

### 2026-04-02 Updates
- **Gemini backend is now live on mGBA**: Real `main.py` session verified with `--backend gemini --load-state crystal_playable --headless`.
- **Schema bridge fixed**: Anthropic JSON Schema tool definitions now convert recursively into Gemini's function declaration schema (`type_`, nested `items` / `properties`, unsupported keys dropped).
- **Message bridge fixed**: Anthropic message history now converts into Gemini text/image/function-call/function-response parts instead of flattening tool blocks into strings.
- **Backend/model mismatch fixed**: Crystal runs now default to `gemini-2.5-flash` when backend is `gemini` or `auto`, instead of accidentally passing `claude-opus-4-6` to Gemini.
- **Gemini arg normalization fixed**: Integer-like numeric args are coerced back to ints, and sequence-like arg containers are normalized to plain Python lists. This fixed real tool-validation failures like `buttons must be a list`.
- **Dead tool removed from prompt surface**: `navigate_to` is no longer offered when `CrystalAgent` has no navigator wired, so Gemini can't waste turns on impossible pathfinding actions.
- **Real tool execution verified**: Live 2-step Crystal harness produced a successful Gemini `press_buttons` call (`left`) with no validation error.
- **Tests**: 211 targeted `pokemon-agent` tests passing (`tests.test_gemini_client`, `test_main`, `test_agent`, `test_emulator_control`, `test_boot_sequence_crystal`, `test_memory_reader`, `test_setup_crystal_state`).

### What Still Blocks Longer Play
- **Gemini free-tier quota is tight**: The current backend hits `gemini-2.5-flash` free-tier request limits fast (observed 5 RPM). Long autonomous runs need pacing, more offline shortcuts, or a different provider path.
- **Crystal navigation is still manual**: mGBA movement works, but there is no Crystal navigator wired yet, so the model must walk with button presses instead of map-aware routing.
- **Deprecated SDK warning**: `google.generativeai` works in the current venv, but it prints a deprecation warning. A later MT-53 cut should migrate to `google.genai`.

### Next Step
1. Run a paced 10-20 minute Gemini+mGBA session with request throttling or more auto-advance shortcuts.
2. Build Crystal-specific navigation/pathfinding before re-enabling `navigate_to`.
3. Consider migrating `gemini_client.py` from `google.generativeai` to `google.genai` once the current live loop is stable.

## Previous State (S224 — 2026-03-27)

### S224 Updates
- **--model CLI flag added**: `--model claude-haiku-4-5-20251001` overrides config.py MODEL_NAME
- **anthropic SDK installed** in pokemon-agent/venv (v0.86.0)
- **Offline mode verified**: 10 steps in 0.2s, emulator + state load working
- **LLM session BLOCKED**: No Anthropic API key available (Matthew confirmed — never assume one exists). Agent loop needs redesign to use an alternative LLM backend (e.g., Gemini via MCP, local model, or Claude Code integration).
- **Next step**: Either (a) add Gemini/alternative LLM backend, or (b) build a smarter offline heuristic agent that doesn't need an LLM

## Previous State (S222 — 2026-03-27)

### What Works
- **mGBA backend**: Fully wired, ROM boots, RAM reads verified. PyBoy is BANNED.
- **Agent loop wired to mGBA**: main.py creates CrystalAgent, connects to emulator + LLM. Offline mode verified (30 steps in 0.6s).
- **Playable save state**: `crystal_playable` — New Bark Town with Cyndaquil Lv5. Created by `setup_crystal_state.py`.
- **Starter injection**: RAM-write approach bypasses menu navigation entirely. All 3 starters supported (Cyndaquil, Totodile, Chikorita).
- **Map IDs verified**: All 4 intro maps confirmed via RAM + pret/pokecrystal source:
  - Player's House 2F: (24, 7)
  - Player's House 1F: (24, 6)
  - New Bark Town: (24, 4)
  - Elm's Lab: (24, 5)
- **Warp coordinates verified**:
  - 2F stairs: tile (7, 0) — navigate to (7, 1), press UP
  - 1F door: tiles (6, 7) and (7, 7) — navigate there, press DOWN
  - Elm's Lab door in New Bark: (6, 3) — navigate to (6, 4), press UP
  - Player's House door in New Bark: (13, 5)
- **load_state path handling**: Accepts both bare names ("crystal_playable") and full paths ("states/crystal_playable.state")
- **Tests**: 10 setup + 45 emulator_control + 21 boot + 33 crystal data + 48 memory reader = 157 tests

### How to Play (S222 — copy-paste ready)
```bash
cd pokemon-agent

# Create save state (only needed once, or after ROM changes)
python3 setup_crystal_state.py

# Play offline (no API cost, presses A every step)
python3 main.py --rom pokemon_crystal.gbc --load-state crystal_playable --steps 100 --offline

# Play with LLM (requires ANTHROPIC_API_KEY)
python3 main.py --rom pokemon_crystal.gbc --load-state crystal_playable --steps 50

# Choose a different starter
python3 setup_crystal_state.py --starter totodile
```

### Save States Available
- `states/crystal_playable.state` — **PRIMARY** — New Bark Town, Cyndaquil Lv5, movement verified
- `states/playable_start.state` — Player's House 1F at (5, 7), movement works, no party
- `states/playable_newbark.state` — Elm's Lab at (4, 4), movement BLOCKED (script state)
- `states/after_crystal_boot.state` — Player's House 2F, movement works, no party

### Known Issues
- **Headless screenshots**: Come back black after state loads (video buffer issue). Not blocking — agent works from RAM state, not screenshots.
- **Some save states have stuck movement**: Elm's Lab states (playable_newbark, playable_with_starter) have scripted events that block joypad. Use `playable_start` or `crystal_playable` as base.
- **No wild encounters yet**: Need to walk into grass routes (Route 29 east of New Bark) to trigger battles.

### Next Steps (Priority Order)
1. **Run with LLM**: `python3 main.py --rom pokemon_crystal.gbc --load-state crystal_playable --steps 50` — first real play session
2. **Fix what breaks**: Stuck detection, battle handling, navigation — all during gameplay
3. **Route 29 exploration**: Walk east to encounter wild Pokemon, test battle AI
4. **Screenshot fix**: Investigate video buffer refresh after state load

### Technical Notes
- mGBA bindings at `pokemon-agent/mgba_bindings/` (built from source, 0.10.5)
- Crystal RAM: MAP_GROUP=0xDCB5, MAP_NUMBER=0xDCB6, X=0xDCB8, Y=0xDCB7
- Party RAM: PARTY_COUNT=0xDCD7, PARTY_DATA=0xDCDF (48 bytes/mon)
- `setup_crystal_state.py` handles state creation reproducibly
- pret/pokecrystal is authoritative for map data, warp coords, NPC positions

### Matthew's Directive
This is a **fun brain rot project**. Not mission-critical. The bot should play for 15-20 minutes, address issues, restart. Learn through playing. Don't over-engineer.
