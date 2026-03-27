# MT-53 Phase 1 Research: Pokemon Autonomous Bot

**Date:** 2026-03-26 (S199)
**Directive:** Matthew S188/S189 — autonomous Pokemon bot on macOS emulator

---

## 1. Emulator Comparison

### PyBoy (RECOMMENDED for GBC — Pokemon Crystal)

| Attribute | Details |
|-----------|---------|
| **Platform** | macOS, Linux, Windows, Raspberry Pi |
| **Games** | Game Boy / Game Boy Color (Pokemon Crystal, Red, Blue, Yellow, Gold, Silver) |
| **Language** | Python-native (`pip install pyboy`) |
| **Version** | 2.7.0 (Jan 2026) — actively maintained |
| **Scripting** | Full Python API — button input, frame advance, memory read/write, save states, screenshots |
| **Speed control** | `pyboy.set_emulation_speed(0)` = uncapped, any integer multiplier |
| **Stars** | ~5K+ |
| **Key advantage** | Python-native = zero FFI overhead, direct integration with Claude/LLM tooling |
| **Key limitation** | GBC only — no GBA (no Emerald) |

**API highlights:**
```python
from pyboy import PyBoy
pyboy = PyBoy("pokemon_crystal.gbc")
pyboy.set_emulation_speed(2)  # 2x speed
pyboy.button_press("a")
pyboy.tick()  # Advance one frame
screen = pyboy.screen.ndarray  # Screenshot as numpy array
memory = pyboy.memory[0xD162]  # Direct memory read
```

### mGBA (RECOMMENDED for GBA — Pokemon Emerald)

| Attribute | Details |
|-----------|---------|
| **Platform** | macOS, Linux, Windows + 6 more |
| **Games** | Game Boy Advance (Pokemon Emerald, Ruby, Sapphire, FireRed, LeafGreen) |
| **Language** | Lua scripting (built-in), Python via mGBA-http bridge |
| **Scripting** | Full Lua 5.4 — memory read/write, input, callbacks, frame advance |
| **Speed control** | Built-in fast-forward (configurable multiplier) |
| **HTTP bridge** | [mGBA-http](https://github.com/nikouu/mGBA-http) — REST API wrapper for any language |
| **Key advantage** | Best GBA emulator, accurate, mature Lua API |
| **Key limitation** | Lua scripting (not Python-native), needs bridge for Python |

### BizHawk (ALTERNATIVE)

| Attribute | Details |
|-----------|---------|
| **Platform** | Windows primary, Linux experimental, macOS NOT supported |
| **Games** | Multi-system (GB, GBC, GBA, NES, SNES, etc.) |
| **Scripting** | Lua |
| **Verdict** | SKIP — no macOS support |

### OpenEmu (macOS native)

| Attribute | Details |
|-----------|---------|
| **Platform** | macOS only |
| **Scripting** | NONE — consumer-focused, no API |
| **Verdict** | SKIP — no scripting API. Good for playing, not for bots. |

### Verdict

| Game | Emulator | Why |
|------|----------|-----|
| **Pokemon Crystal (GBC)** | **PyBoy** | Python-native, direct API, proven in Pokemon RL projects |
| **Pokemon Emerald (GBA)** | **mGBA + mGBA-http** | Best GBA emulator, HTTP bridge enables Python control |
| **ROM hacks (GBC)** | **PyBoy** | Same engine, ROM hacks are just modified GBC ROMs |
| **ROM hacks (GBA)** | **mGBA** | Same engine |

**START WITH PyBoy + Pokemon Crystal.** Python-native = fastest path to working bot. Add mGBA for Emerald later.

---

## 2. Existing AI Pokemon Bot Projects

### 2a. Anthropic's Claude Plays Pokemon (David Hershey)

**Source:** [ZenML writeup](https://www.zenml.io/llmops-database/building-and-deploying-a-pokemon-playing-llm-agent-at-anthropic)

**Architecture (minimal, intentionally stripped down):**
- 3 tools: button press, persistent knowledge base (editable by model), navigation helper
- Dual input per action: screenshot + structured game data from emulator
- Accordion-style summarization for long-horizon context (16K+ actions in 3 days)
- Knowledge base persists across summarization boundaries

**Key insights:**
- Spatial reasoning is LLMs' weakest point — navigator tool compensates
- Simpler is better — Hershey stripped complexity over time, not added it
- Standard benchmarks miss real-world agent capabilities

**CCA relevance:** VERY HIGH. This is literally what Matthew wants. Architecture is public, can be adapted.

### 2b. llm_pokemon_scaffold (cicero225)

**Source:** [GitHub](https://github.com/cicero225/llm_pokemon_scaffold) — 33 stars, 64 commits

**Architecture:**
- PyBoy emulator, supports Claude 3.7, Gemini 2.5, o3/o4-mini
- Memory reader extracts game state directly from emulator RAM
- LLM function calling executes emulator commands
- Meta-Critique LLM for fact verification and game state tracking
- ASCII collision map generation for exploration
- Checkpoint logging prevents hallucinations
- Auto-pathing to known coordinates

**Key features:**
- Separate emulator threading (runs while agent thinks)
- Location-first-visit logging for progress tracking
- Detailed navigator tool for maze solving

**CCA relevance:** HIGH. Open source, uses PyBoy, supports Claude. Could be the base framework.

### 2c. PokemonRedExperiments (Peter Whidden)

**Source:** [GitHub](https://github.com/PWhiddy/PokemonRedExperiments) — likely 10K+ stars, arXiv paper (2502.19920)

**Architecture:**
- Pure Reinforcement Learning (NOT LLM-based)
- PyBoy for emulation
- Stable Baselines3 for RL algorithms
- Custom gym environments (red_gym_env.py)
- <10M parameter policy beats Pokemon Red (as of Feb 2025)

**CCA relevance:** MEDIUM. Different approach (RL vs LLM), but validates PyBoy as the emulator choice and provides reward shaping ideas.

### 2d. PokeAgent Challenge (NeurIPS 2025)

**Source:** [arXiv:2603.15563](https://arxiv.org/abs/2603.15563)

**Architecture:**
- Large-scale benchmark: battling + speedrunning tracks
- 20M+ battle trajectories dataset
- Multi-agent orchestration system for speedrunning
- First standardized RPG speedrunning evaluation

**Key finding:** "Pokemon battling is nearly orthogonal to standard LLM benchmarks" — measures capabilities not captured by MMLU etc. Considerable gap between LLM, RL, and human performance.

**CCA relevance:** MEDIUM. Benchmark framework, not a bot to reuse. But confirms this is a legitimate AI research area.

### 2e. Other Notable Results (2025-2026)

| Model | Achievement |
|-------|-------------|
| Claude (Hershey) | 16K+ actions in 3 days, extended thinking over 35K actions |
| Gemini 2.5 Pro | Completed Pokemon Blue in 406 hours |
| GPT-5 | Finished Pokemon Red in 6,470 steps |
| Gemini 3 Pro | Completed Pokemon Crystal WITHOUT losing a single battle |

---

## 3. RAM Maps (Critical for Game State Reading)

Pokemon games store all state in known RAM addresses. Community-maintained RAM maps exist for every game:

| Game | RAM Map Source |
|------|---------------|
| Pokemon Crystal | [pret/pokecrystal](https://github.com/pret/pokecrystal) — full disassembly |
| Pokemon Emerald | [pret/pokeemerald](https://github.com/pret/pokeemerald) — full disassembly |
| Pokemon Red | [pret/pokered](https://github.com/pret/pokered) — full disassembly |

These disassemblies provide exact memory addresses for:
- Party Pokemon (species, level, HP, moves, EVs/DVs)
- Current map/position
- Badges obtained
- Items in bag
- Battle state (enemy Pokemon, HP, status)
- Story progress flags

---

## 4. Recommended Architecture for MT-53

```
┌─────────────────────────────────────────────┐
│  CCA MT-53 Pokemon Bot                      │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Emulator │  │ State    │  │ Decision  │ │
│  │ Control  │──│ Reader   │──│ Engine    │ │
│  │ (PyBoy)  │  │ (RAM Map)│  │ (Rules +  │ │
│  └──────────┘  └──────────┘  │  Heuristic)│ │
│       │                      └───────────┘ │
│       │         ┌───────────┐              │
│       └─────────│ Event Log │              │
│                 │ (JSONL)   │              │
│                 └───────────┘              │
└─────────────────────────────────────────────┘
```

**Phase 1 decision: LLM vs Rules-Based**

Matthew said: "Once built, it doesn't burn tokens." This means the decision engine should be RULES-BASED, not LLM-powered. Use LLM only during development for debugging/testing. The shipping bot should be standalone Python.

**Recommended stack:**
1. **Emulator:** PyBoy (Crystal first, mGBA for Emerald later)
2. **State reader:** Direct RAM access via PyBoy API + pret disassembly addresses
3. **Decision engine:** Rule-based + heuristic (type chart, damage calc, team optimization)
4. **Navigation:** A* pathfinding on tile maps extracted from ROM
5. **Battle AI:** Minimax or expectimax with type effectiveness + STAB + stat modifiers
6. **Event log:** JSONL for every battle outcome, route timing, team evolution (Phase 9 self-learning)
7. **Name generator:** Standalone module with dark humor word lists

**NOT recommended:**
- LLM-in-the-loop for real-time decisions (burns tokens, Matthew explicitly said no)
- Reinforcement learning (requires GPU training, months of compute)
- Full game disassembly (overkill — RAM maps sufficient)

---

## 5. Phase 2 Plan Preview

Phase 2 (Core Engine) should build:
1. `emulator_control.py` — PyBoy wrapper (init, button press, frame advance, save/load state, screenshot)
2. `state_reader.py` — RAM map reader (party, map, badges, items, battle state)
3. `game_state.py` — Dataclasses for structured game state
4. Tests for all three modules

Estimated: ~400 LOC + ~150 LOC tests. One session.

---

## Sources

- [PyBoy GitHub](https://github.com/Baekalfen/PyBoy) / [Docs](https://docs.pyboy.dk/)
- [mGBA](https://mgba.io/) / [Scripting API](https://mgba.io/docs/scripting.html)
- [mGBA-http bridge](https://github.com/nikouu/mGBA-http)
- [llm_pokemon_scaffold](https://github.com/cicero225/llm_pokemon_scaffold)
- [PokemonRedExperiments](https://github.com/PWhiddy/PokemonRedExperiments) / [Paper](https://arxiv.org/abs/2502.19920)
- [PokeAgent Challenge](https://arxiv.org/abs/2603.15563)
- [Claude Plays Pokemon (Hershey/Anthropic)](https://www.zenml.io/llmops-database/building-and-deploying-a-pokemon-playing-llm-agent-at-anthropic)
- [TIME: AI Systems Playing Pokemon](https://time.com/7345903/ai-chatgpt-claude-gemini-pokemon/)
- [pret disassemblies](https://github.com/pret/) (pokered, pokecrystal, pokeemerald)
