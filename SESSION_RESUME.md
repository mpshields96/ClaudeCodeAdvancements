Run /cca-init. Last session was 207 on 2026-03-27.

WHAT WAS DONE: S207 was a C-grade session. Confirmed PyBoy headless works on macOS, automated through Crystal intro, saved state at New Bark Town bedroom, added dark comedy personality, created browser viewer and launch.json. BUT — left multiple bugs undiagnosed (wrong map IDs from memory reader, button presses not moving character, viewer never verified). Did NOT research r/ClaudePlaysPokemon or existing Pokemon AI bots.

CRITICAL — READ pokemon-agent/S207_HANDOFF.md FIRST. It has the full bug inventory, confidence assessment, and step-by-step instructions for what to do. The previous session (S207) rushed without research and wasted time. DO NOT REPEAT THIS.

NEXT (in this exact order):
1. READ S207_HANDOFF.md completely before touching any code
2. RESEARCH r/ClaudePlaysPokemon subreddit and GitHub repos — what emulator, what RAM addresses, how they display, what worked
3. Check CCA memory: reference_claude_plays_pokemon.md
4. FIX memory_reader.py — map ID reads 6151 instead of 24. Raw PyBoy pb.memory[0xDCB5] returns 24 (correct), but MemoryReader returns wrong value
5. FIX button press movement — sent down presses, position stayed at (3,5). Diagnose: timing? action consumption? RAM read?
6. VERIFY viewer.html works end-to-end via localhost:8765 (launch.json already set up)
7. TEST full loop: bridge writes state -> read state -> write action -> character moves
8. THEN try /pokemon-play

Matthew's directive: "do more research and not be such a dumb bitch about it." Take your time. Research first. Diagnose bugs systematically. Don't rush.

Tests: 315/315 suites, 11514 tests passing. Git: clean (committed 3d5edb2).
Save state: pokemon-agent/states/new_game.state (New Bark Town bedroom, 0 badges, 0 party).
FOCUS ON TODAYS_TASKS.md — read it first for today's priorities.
