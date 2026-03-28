# MT-53 Pokemon Crystal Bot — Research Log

## S208 Research (2026-03-27)

### Emulator Choice: mGBA (S219 — PyBoy BANNED)
Most LLM Pokemon bots use PyBoy, but it freezes on macOS Apple Silicon:
- ClaudePlaysPokemon (official Anthropic stream) — PyBoy, Pokemon Red
- NousResearch/pokemon-agent — PyBoy + PyGBA, Red/Blue/Yellow (Crystal planned)
- cicero225/llm_pokemon_scaffold — PyBoy, Red

**PyBoy BANNED (S219 Matthew directive).** Freezes on macOS ARM64 during headless operation.
**We use mGBA** (mgba-py bindings). Supports GB/GBC/GBA — one backend for all ROMs.
Built from source (mgba 0.10.5), confirmed working headless on macOS ARM64.
Dependencies: cffi, cached_property (installed in venv).

### RAM Addresses: Verified Correct
Our `memory_reader.py` addresses match pret/pokecrystal (authoritative disassembly). Key addresses:
- Party: 0xDCD7 (count), 0xDCDF (data, 48 bytes/mon)
- Map: 0xDCB5 (group), 0xDCB6 (number), 0xDCB7 (Y), 0xDCB8 (X)
- Battle: 0xD22D (mode), 0xD206 (enemy species)
- Badges: 0xD57C (bit flags)
- Dialog text: 0xC4E1 (line 1 tilemap), 0xC505 (line 2 tilemap)
- Text buffer: 0xD073 (wStringBuffer1)

### S207 "Bug 1" Was Not A Bug
Map ID 6151 = (group=24 << 8) | number=7 = 0x1807. This is the correct composite ID.
S207 compared against raw group byte (24) and thought it was wrong.
**Fix:** Store group and number separately on MapPosition for readability. Done in S208.

### Display Approaches (What Others Do)
| Project | Method | Notes |
|---------|--------|-------|
| Official stream | Screenshot 2x + RAM + walkability overlay | Red/cyan overlay for walkable tiles |
| cicero225 | Screenshot + ASCII collision map + distances | Most elaborate augmentation |
| Gemini Crystal | Screenshot + text logs + NPC reports | "Almost vision-only" |
| papercomputeco | Headless, no display | Heuristic-only, no LLM vision |

**Best practices:**
- Upscale screenshots 2x before sending to LLM
- Color patch ROM (Danny-E 33 + FroggestSpirit) improves contrast
- Read dialog text from RAM tilemap — more reliable than OCR on pixel fonts
- RAM state is ground truth; screenshots are supplementary

### Action Loop Timing
- Game Boy: ~60 fps
- Button press: hold 4 frames (~67ms), wait 8 frames after release
- Movement step: hold 8 frames, wait 8 frames (directional)
- Text advance: press A, wait 20 frames between presses
- Menu nav: 4 frame hold, 16 frame wait

### Architecture: Two Valid Patterns

**Pattern 1 — API-based (what others use):**
In-process Python loop calling Anthropic API directly. Claude reasons and returns tool calls.
Used by: official stream, cicero225, NousResearch.

**Pattern 2 — File-based IPC (what we use):**
bridge.py runs emulator, writes state.json + screenshot.png. Claude Code reads them via
/pokemon-play slash command. Zero API cost — uses Max subscription.
**This is our approach. No API.**

### Key Repos
- `davidhershey/ClaudePlaysPokemonStarter` — Official Anthropic starter (190 stars, 3 files)
- `NousResearch/pokemon-agent` — FastAPI, A* pathfinding, multi-game (MIT)
- `cicero225/llm_pokemon_scaffold` — Most elaborate harness, meta-critique (GPL-3.0)
- `waylaidwanderer/gemini-plays-pokemon-public` — Gemini Crystal harness
- `pret/pokecrystal` — Authoritative Crystal disassembly (RAM map source)

### NousResearch Gap We Fill
NousResearch/pokemon-agent has Crystal "planned" but their Crystal memory reader is missing.
Our `memory_reader.py` (with 37 tests) fills this exact gap.

### Progressive Summarization (for long play sessions)
Official starter uses this: when conversation exceeds max_turns (~60 messages), Claude
self-summarizes recent progress. History cleared, summary becomes first message. Knowledge
base persists across summaries. A second LLM call audits quality.
**We'll need this for /pokemon-play sessions that go long.**

### S207 "Bug 2" Diagnosis: Movement
Most likely cause: character stuck in dialog/text after state load. The save state captures
a moment in time — if a text box was partially active, the game ignores directional input
until the text is dismissed. Fix: mash B+A after loading state to clear any stuck UI.
Also increased post-action tick from 12 to 20 frames to ensure movement animation completes.
