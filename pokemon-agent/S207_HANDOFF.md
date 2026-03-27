# S207 Handoff — MT-53 Pokemon Crystal Bot

## CRITICAL: READ THIS ENTIRE FILE BEFORE TOUCHING ANY CODE

Session 207 was a mess. The previous chat (you) rushed headfirst into trying to get
the emulator running without doing proper research, misdiagnosed problems, created
duplicate processes, wasted Matthew's time, and glossed over bugs instead of fixing
them. Do NOT repeat this. Research first, verify assumptions, then build.

Matthew's exact words: "do more research into all of this and not be such a dumb
bitch about it." Take that to heart.

---

## What S207 Actually Accomplished

1. Installed Pillow into pokemon-agent/venv (was missing, needed for screenshots)
2. Confirmed PyBoy boots and runs headless on macOS — no freeze, no issues
3. Confirmed SDL2 windowed mode DOES work from a foreground process (not background)
4. Confirmed SDL2 windowed mode FREEZES when launched as background process from CC
5. Automated through the Crystal intro — got to player's bedroom in New Bark Town
6. Saved a working state file: `states/new_game.state` (Map 24, pos 3,5, 0 badges, 0 party)
7. Created `viewer.html` — browser-based game viewer (NOT fully tested/working yet)
8. Created `.claude/launch.json` for preview panel HTTP server (started but NOT verified)
9. Updated `prompts.py` SYSTEM_PROMPT with dark comedy personality (Jeselnik/Burnham/Mulaney style)
10. Fixed bridge.py to skip 300-frame boot tick when loading a saved state

## What S207 Left Broken / Unverified

### BUG 1: Memory Reader RAM Addresses Are Wrong
- Map ID reads as 6151 instead of 24 (should be player's bedroom in New Bark Town)
- When tested directly with raw PyBoy: `pb.memory[0xDCB5]` returns 24 (correct)
- When read through MemoryReader via bridge: returns 6151 (wrong)
- This means MemoryReader.read_game_state() is reading wrong addresses or interpreting them wrong
- **Impact: ALL game state data sent to the AI brain may be garbage**
- Files to investigate: `memory_reader.py`, `game_state.py`

### BUG 2: Button Presses Don't Move the Character
- Sent multiple "down" actions via bridge_io/action.json
- Position stayed at (3,5) after every press
- Possible causes:
  - bridge.py action consumption timing is off
  - The `emu.press()` hold/wait frames are too short
  - The character is stuck on something (dialog, menu)
  - The RAM position read is wrong (maybe position DID change but we read stale data)
- **Impact: The bot literally cannot play the game if movement doesn't work**

### BUG 3: Web Viewer Never Verified Working
- Created viewer.html with auto-refresh polling
- Set up launch.json with python3 HTTP server on port 8765
- Started the server via preview_start
- NEVER actually confirmed the viewer shows the game screen updating
- The preview panel was showing "Waiting for bridge..." and "Connecting..."
- Possible issues: file paths, caching, preview panel behavior, CORS

### BUG 4: End-to-End Flow Never Tested
- Never ran /pokemon-play to see Claude actually play
- Never tested: bridge writes state -> Claude reads state -> Claude reasons -> Claude writes action -> bridge executes action -> character moves -> repeat
- The full loop is completely unproven

---

## Confidence Assessment (Verbatim from S207)

**High confidence (verified):**
- PyBoy boots, ticks, saves screenshots headless — tested, proven
- The file-based bridge architecture is sound in concept
- Other CC sessions won't be blocked by the bridge running

**Medium confidence (should work but not fully verified):**
- The preview panel web viewer — launch.json set up but never confirmed the viewer
  loads and updates live. Could have caching issues, CORS issues, or the preview
  panel might not behave like a regular browser.

**Low confidence / known undiagnosed bugs glossed over:**
- Map ID was wrong — showed 6151 instead of 24. RAM addresses in memory_reader.py
  may be incorrect for Crystal. If state data is garbage, AI makes garbage decisions.
- Movement didn't register — sent multiple down presses, position stayed at (3,5).
  Either actions aren't consumed properly, RAM read is wrong, or frame timing is off.
- Never tested the full loop — never seen Claude read state, reason, write action
  that moves the character. End-to-end flow is unproven.
- Never researched what r/ClaudePlaysPokemon actually did — S206 resume said "steal
  everything" from that project. S207 never looked at their approach. They likely
  solved problems we're about to hit.

---

## What the Next Session MUST Do (In Order)

### Step 1: RESEARCH (before touching any code)
- Read reference_claude_plays_pokemon.md in CCA memory
- Look at the r/ClaudePlaysPokemon subreddit and GitHub repos
- Understand what emulator they use, how they display the game, what RAM addresses
  they use for Crystal, how they handle the action loop
- Check if there's a better-maintained Pokemon Crystal RAM map than what we have
- Research: is PyBoy the right choice? What do other Pokemon AI bots use?

### Step 2: DIAGNOSE the bugs
- Fix memory_reader.py RAM addresses — verify against a known Crystal RAM map
- Fix the movement/action bug — is it timing, consumption, or reading?
- Test each fix in isolation before integrating

### Step 3: VERIFY the viewer
- Confirm the HTTP server serves files correctly
- Confirm the viewer.html auto-refreshes and shows the game
- If the preview panel doesn't work, use the browser directly at localhost:8765

### Step 4: TEST end-to-end
- Run bridge headless
- Open viewer in browser
- Send manual actions via action.json
- Confirm: state updates, screenshot updates, position changes, viewer shows it

### Step 5: THEN and only then — try /pokemon-play

---

## Architecture Decisions Made

- **Headless PyBoy + web viewer** (not SDL2 window) — because SDL2 freezes when
  launched from CC background processes on macOS
- **File-based IPC** (bridge_io/state.json, action.json, screenshot.png) — simple,
  allows any process to be the "brain"
- **Dark comedy personality** — Anthony Jeselnik / Bo Burnham / John Mulaney style,
  added to SYSTEM_PROMPT in prompts.py
- **launch.json** — python3 HTTP server on port 8765 serving pokemon-agent/

## Files Modified in S207
- `pokemon-agent/bridge.py` — fixed state loading (skip 300-frame boot when loading state)
- `pokemon-agent/prompts.py` — added dark comedy personality to SYSTEM_PROMPT
- `pokemon-agent/viewer.html` — NEW: browser-based live game viewer
- `.claude/launch.json` — NEW: preview panel server config
- `pokemon-agent/venv/` — installed Pillow

## Files NOT Modified But Need Investigation
- `pokemon-agent/memory_reader.py` — RAM addresses likely wrong
- `pokemon-agent/game_state.py` — data structures may not match actual RAM layout
- `pokemon-agent/config.py` — RAM address constants may be wrong

## Running Processes
- ALL killed before wrap. No bridge, no HTTP server running.

## The Save State
- `pokemon-agent/states/new_game.state` — Player's bedroom, New Bark Town
- Verified working: loads correctly, shows bedroom screenshot
- No Pokemon yet, 0 badges, need to go to Prof Elm's lab for starter
