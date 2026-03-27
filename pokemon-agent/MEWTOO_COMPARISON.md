# Mewtoo Architecture Comparison

Source: https://github.com/jacobyoby/mewtoo (Pokemon Red, PyBoy)

## Architecture Comparison

| Feature | CCA (Crystal Agent) | Mewtoo (Red Agent) |
|---------|--------------------|--------------------|
| **Game** | Pokemon Crystal (GBC) | Pokemon Red (GB) |
| **Emulator** | PyBoy | PyBoy |
| **LLM** | Claude API (tool use) | Claude API or Ollama (text-only) |
| **Action format** | Tool use (press_buttons, save_state) | Single action string (UP/DOWN/A/B/WAIT) |
| **RAM addresses** | Crystal wram.asm (0xDCD7 party, 0xDCB5 map) | Red wram.asm (0xD163 party, 0xD35E map) |
| **State read** | Structured dataclasses (GameState) | Dictionary (read_full_game_state) |
| **Stuck detection** | Self-anchoring counter + failed strategy log | Multi-modal (state+position+action repetition) |
| **Menu detection** | RAM-based (WINDOW_STACK_SIZE, TEXT_BOX_FLAGS) | RAM-based (CC26 menu type, D730 text box) |
| **Caching** | ActionCache LRU (S204) | ActionCache (state+screen -> action) |
| **Strategy** | LLM decides freely | 3 profiles (balanced/aggressive/conservative) |
| **OCR** | None (RAM-only) | ocr_enhancer.py (screen text extraction) |
| **Movement validation** | MovementValidator (S205) | Movement tracking per direction |
| **Screen detection** | ScreenDetector (S205) | Blank screen skip |
| **Diversity** | DiversityChecker (S205) | Action repetition flagging |
| **Tests** | 437 (21 real emulator) | 123 |

## Mewtoo Patterns — ALL ADOPTED (S204-S205)

1. **Action caching** (S204) — `action_cache.py` (32 tests). LRU state->action mapping,
   hit-based expiration, success rate tracking. Skips LLM for known states.

2. **Dialog loop prevention** (S204) — In `agent.py` (12 tests). Auto-A for dialog/healing,
   B-escape after 7+ consecutive A presses. No LLM calls for mechanical text.

3. **Movement validation** (S205) — `movement_validator.py` (29 tests). Tracks blocked
   directions after 3 failures, suggests perpendicular alternatives, clears on map change.

4. **Blank screen detection** (S205) — `screen_detector.py` (13 tests). Detects transitions
   via JOY_DISABLED RAM flag, auto-waits. START unstick after 30+ consecutive transitions.

5. **Diversity checking** (S205) — `diversity_checker.py` (13 tests). Flags when one action
   exceeds 60% of last 15 actions, warns LLM and suggests alternatives.

## Patterns We Already Handle Better

1. **Tool use vs text parsing** — Our Claude tool use approach is more reliable than parsing
   "UP" from free text. No regex/string matching needed for action extraction.

2. **Structured state** — Dataclass-based GameState with typed fields vs raw dictionaries.
   Better for prompt construction and state comparison.

3. **RAM-only state** — No OCR dependency means faster, more reliable state reads.
   Mewtoo's OCR adds latency and error surface.

4. **Test coverage** — 437 tests (21 real emulator) vs 123 tests.

5. **Self-anchoring stuck context** — Our approach gives the LLM explicit history of what
   failed and why, not just "you're stuck, try something different."

## Implementation Status — ALL COMPLETE

| Pattern | File | Tests | Session |
|---------|------|-------|---------|
| Dialog loop prevention | agent.py | 12 | S204 |
| Action caching | action_cache.py | 32 | S204 |
| Blank screen detection | screen_detector.py | 13 | S205 |
| Movement validation | movement_validator.py | 29 | S205 |
| Diversity checking | diversity_checker.py | 13 | S205 |
