# MT-53 Phase 1: Reddit/GitHub Intelligence Scan

**Date:** 2026-03-26 (S191)
**Scope:** Pokemon AI bot projects, emulator scripting frameworks, automated gameplay tools
**Method:** Parallel Reddit + GitHub search agents across r/pokemon, r/PokemonROMhacks, r/emulation, r/MachineLearning, and GitHub trending repos

---

## BUILD — Foundation Projects (Use These)

### 1. NousResearch/pokemon-agent
- **GitHub:** https://github.com/NousResearch/pokemon-agent
- **What:** AI-powered Pokemon gameplay agent with headless emulation, REST API, and live dashboard. Works with ANY LLM.
- **Language:** Python | **Framework:** PyBoy (GB) + PyGBA (GBA)
- **macOS:** Yes — pip installable, headless
- **Key strength:** Clean HTTP API (GET /state, POST /action, GET /screenshot). Game state parsed into structured JSON (party, bag, badges, map, battle, dialog). Multi-game support (Red/Blue via PyBoy, FireRed via PyGBA).
- **Install:** `pip install pokemon-agent pyboy`
- **Verdict:** **BUILD** — Best starting point. Production-grade architecture, LLM-agnostic. Wire Claude as the decision brain via REST API.

### 2. PWhiddy/PokemonRedExperiments
- **GitHub:** https://github.com/PWhiddy/PokemonRedExperiments
- **Stars:** ~9K+ (viral, TechCrunch coverage)
- **What:** Playing Pokemon Red with Reinforcement Learning. First to beat Pokemon Red with RL (Feb 2025 paper: arXiv:2502.19920).
- **Language:** Python | **Framework:** PyBoy + Stable Baselines3 + Gymnasium
- **macOS:** Yes
- **Key strength:** Custom gym environment, reward shaping for exploration/battles/badges, StreamWrapper for collaborative training visualization, <10M parameter policy.
- **Verdict:** **BUILD** — Gold standard for RL approach. Proven to beat the game. Gymnasium wrapper reusable.

### 3. PyBoy (Baekalfen/PyBoy)
- **GitHub:** https://github.com/Baekalfen/PyBoy
- **Stars:** ~5.1K
- **What:** Game Boy emulator written in Python with scripting API, game wrappers, AI/bot support
- **Language:** Python (Cython-accelerated)
- **macOS:** Yes — `pip install pyboy`, Apple Silicon native (ARM64 wheel)
- **Key strength:** Pokemon-specific game wrapper with `.game_area_collision()`. 395x speed headless. Multiple instances supported. v2.7.0 (Jan 2026).
- **Verdict:** **BUILD** — Foundational emulator layer. Nearly every GB Pokemon AI project uses this.

### 4. PyGBA (dvruette/pygba)
- **GitHub:** https://github.com/dvruette/pygba
- **What:** Python wrapper around mGBA with built-in Gymnasium environment support for GBA games
- **Language:** Python | **Framework:** mGBA + Gymnasium
- **macOS:** Yes — pre-built wheels for Python >= 3.10
- **Key strength:** Pokemon Emerald wrapper included with reward function. `pip install pygba`.
- **Verdict:** **BUILD** — GBA equivalent of PyBoy. Target this for Emerald/FireRed.

---

## ADAPT — Strong Projects, Need Modification

### 5. PokeLLMon (git-disl/PokeLLMon)
- **GitHub:** https://github.com/git-disl/PokeLLMon
- **Paper:** arXiv:2402.01118
- **What:** First LLM agent achieving human-parity in Pokemon Showdown battles (49% ladder WR, 56% invited)
- **Key strength:** Three novel techniques: in-context RL, knowledge-augmented generation, consistent action generation. Georgia Tech research.
- **Verdict:** **ADAPT** — Battle-only (Showdown), but techniques transferable to ROM agent.

### 6. poke-env (hsahovic/poke-env)
- **GitHub:** https://github.com/hsahovic/poke-env
- **Stars:** ~300+
- **What:** Python interface for training RL bots on Pokemon Showdown
- **Verdict:** **ADAPT** — Battle-focused only. Excellent for competitive battle AI.

### 7. Clad3815/gpt-play-pokemon-firered
- **GitHub:** https://github.com/Clad3815/gpt-play-pokemon-firered
- **What:** Autonomous AI agent playing Pokemon FireRed with live web dashboard
- **License:** CC BY-NC 4.0 (non-commercial)
- **Verdict:** **ADAPT** — Good dashboard/monitoring architecture. NC license limits reuse.

### 8. 40Cakes/pokebot-gen3
- **GitHub:** https://github.com/40Cakes/pokebot-gen3
- **What:** Shiny hunting bot for Gen 3 using libmgba + Python
- **Verdict:** **ADAPT** — Scripted loops (not AI), but excellent reference for mGBA Python bindings and game state reading.

---

## REFERENCE — Design Patterns & Techniques

### 9. Ayaan-P/agentic-emerald
- **GitHub:** https://github.com/Ayaan-P/agentic-emerald
- **What:** AI Game Master — watches gameplay via mGBA, rewards story moments with invisible interventions
- **Architecture:** mGBA Lua -> Python daemon -> Claude API
- **Verdict:** **REFERENCE** — Not an autonomous player, but the mGBA Lua -> Python -> LLM pipeline is a reusable pattern.

### 10. CalebDeLeeuwMisfits/PokemonLLMAgentBenchmark
- **GitHub:** https://github.com/CalebDeLeeuwMisfits/PokemonLLMAgentBenchmark
- **What:** Autonomous agent using HuggingFace smolagents to play Pokemon Red via PyBoy + Claude/Ollama
- **Verdict:** **REFERENCE** — smolagents integration pattern + OCR-based state extraction.

### 11. jmurth1234/ClaudePlayer
- **GitHub:** https://github.com/jmurth1234/ClaudePlayer
- **What:** AI agent letting Claude play Game Boy games through PyBoy
- **Verdict:** **REFERENCE** — Simple, clean Claude + PyBoy integration reference.

### 12. PokéChamp (arXiv:2503.04094)
- **What:** Expert-level minimax language agent for Pokemon battles
- **Verdict:** **REFERENCE** — Hybrid classical search + LLM approach for battles.

---

## Recommended Stack

### Fastest Path (GB games — Crystal):
1. `pip install pokemon-agent pyboy` (NousResearch — REST API + headless)
2. Wire Claude as decision brain via HTTP API
3. Reference PokemonRedExperiments for reward shaping + Gymnasium wrapper

### GBA Games (Emerald):
1. `pip install pygba` (mGBA wrapper with Gymnasium)
2. Reference pokebot-gen3 for game state reading patterns
3. Reference agentic-emerald for mGBA Lua -> Python -> LLM pipeline

### Battle AI:
1. poke-env for Pokemon Showdown integration
2. PokeLLMon's three techniques as AI architecture

---

## Key Insight

**NousResearch's `pokemon-agent` is the game-changer.** It decouples the emulator from the AI brain via REST API. This means:
- Swap LLMs without touching game control
- Add multi-agent architectures (scout agent + battle agent + inventory agent)
- Layer RL training on top of LLM decisions
- Run headless at max speed for training, with GUI for demos

**PyGBA eliminates the mGBA Lua scripting concern.** We originally planned a Python-Lua bridge for Emerald. PyGBA wraps mGBA directly in Python with Gymnasium support, making the architecture uniform: PyBoy for GB, PyGBA for GBA, same Python API patterns.

---

## Next Steps (Phase 2)
- [ ] Install and test pokemon-agent with Crystal ROM
- [ ] Install and test pygba with Emerald ROM
- [ ] Design the Claude decision-making architecture (structured prompts, game state -> action)
- [ ] Map RAM addresses for Crystal and Emerald (party, HP, location, badges)
- [ ] Prototype: Claude plays first 30 minutes of Crystal via pokemon-agent REST API
