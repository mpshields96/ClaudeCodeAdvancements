# MT-53: Pokemon Crystal Bot — Status & Observations

## Current State (S221 — 2026-03-27)

### What Works
- **mGBA backend**: Fully wired, ROM boots, RAM reads verified. PyBoy is BANNED.
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
- **MAP_NAMES table fixed**: Group 24 was mapped to Kanto cities (wrong), now correct MapGroup_NewBark
- **Offline testing**: 50+ steps in 0.4s, 0 API tokens
- **Tests**: 21 boot crystal + 33 crystal data + 48 memory reader = 102 tests passing
- **Dependencies**: cffi + cached-property installed for mgba_bindings

### What's Blocking "Play for 15-20 Minutes"
1. **Mom's 1F scripted event**: Clock setting + Pokegear requires specific menu navigation, not just A-mashing. Inconsistent with brute force. **Solution**: Save a state AFTER this event manually, or teach the boot sequence to handle menu interactions.
2. **Agent loop not connected to mGBA**: main.py structure exists but needs backend wiring.
3. **Starter selection**: Requires walking to Pokeball table and interacting — LLM agent should handle this.

### Key Observation (S221 — IMPORTANT FOR FUTURE CHATS)
**The "run first, build while playing" approach (S219 Matthew directive) is correct but the boot sequence is harder than expected.** The practical path is:
- Create ONE good save state past the intro manually (or with enough brute-force retries)
- Load from that state every time
- Focus all effort on the AGENT LOOP, not boot sequence perfection
- The bot will get stuck, that's fine — fix what actually breaks during gameplay
- Matthew wants 15-20 minute play sessions, not perfection. Fun brain rot project.
- **Stop over-engineering the boot sequence.**

### Save States Available
- `states/after_crystal_boot.state` — Player's House 2F, dialog may be active
- `states/playable_start.state` — Player's House 1F at (5, 7), one step from exit
- `states/playable_newbark.state` — Elm's Lab at (4, 4), dialog cleared (mislabeled)
- `states/playable_with_starter.state` — Elm's Lab at (4, 6), no starter yet

### Next Steps (Priority Order)
1. **Get a post-intro save state**: Either manually play through intro once, or retry brute-force
2. **Wire agent loop to mGBA**: Connect main.py → emulator_control → mgba_bindings
3. **Let it play**: `python3 main.py --rom pokemon_crystal.gbc --load-state playable_newbark --steps 500`
4. **Fix what breaks**: Stuck detection, type chart, navigation — all during gameplay

### Technical Notes
- mGBA bindings are at `pokemon-agent/mgba_bindings/` (built from source, 0.10.5)
- Crystal RAM addresses: MAP_GROUP=0xDCB5, MAP_NUMBER=0xDCB6, X=0xDCB8, Y=0xDCB7
- pret/pokecrystal is the authoritative source for map data, warp coords, NPC positions
- Headless screenshots come back black after state loads (video buffer issue) — not blocking
- Mom's scripted event on 1F involves: clock setting (menu with AM/PM, hour, minute), Pokegear delivery, Elm introduction speech. Requires ~500+ A/down presses with specific menu timing.

### Matthew's Directive
This is a **fun brain rot project**. Not mission-critical. The bot should play for 15-20 minutes, address issues, restart. Learn through playing. Don't over-engineer.
