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
| **Caching** | None yet | ActionCache (state+screen -> action) |
| **Strategy** | LLM decides freely | 3 profiles (balanced/aggressive/conservative) |
| **OCR** | None (RAM-only) | ocr_enhancer.py (screen text extraction) |
| **Tests** | 339 (21 real emulator) | 123 |

## Key Mewtoo Patterns to Adopt

1. **Action caching** — Cache state->action mappings to skip LLM calls for known situations.
   CCA doesn't have this yet. Could reduce token burn significantly for repetitive game states
   (grinding, walking, text dialogs).

2. **Dialog loop prevention** — After 7+ consecutive A presses, try B. After 10+ identical
   state steps, aggressive B-pressing. Simple heuristic that prevents common soft-locks.

3. **Movement validation** — Track failed movement per direction, mark blocked after 3 failures,
   suggest perpendicular alternatives. Good for maze/obstacle navigation.

4. **Blank screen detection** — Skip LLM entirely on blank/transition screens, send A/START.
   Saves tokens on transitions that don't need intelligence.

5. **Diversity checking** — If one action exceeds 60% of last 15 actions, suggest alternatives.
   Complements our stuck detection with a different signal.

## Patterns We Already Handle Better

1. **Tool use vs text parsing** — Our Claude tool use approach is more reliable than parsing
   "UP" from free text. No regex/string matching needed for action extraction.

2. **Structured state** — Dataclass-based GameState with typed fields vs raw dictionaries.
   Better for prompt construction and state comparison.

3. **RAM-only state** — No OCR dependency means faster, more reliable state reads.
   Mewtoo's OCR adds latency and error surface.

4. **Test coverage** — 339 tests (21 real emulator) vs 123 tests.

5. **Self-anchoring stuck context** — Our approach gives the LLM explicit history of what
   failed and why, not just "you're stuck, try something different."

## Implementation Priority

| Pattern | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Blank screen skip | Low (10 LOC) | Medium | P0 |
| Dialog loop prevention | Low (20 LOC) | High | P0 |
| Action caching | Medium (100 LOC) | High | P1 |
| Movement validation | Medium (80 LOC) | Medium | P1 |
| Diversity checking | Low (30 LOC) | Low | P2 |
