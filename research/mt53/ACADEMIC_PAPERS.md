# MT-53 Academic Paper Reference
# Session: S203, 2026-03-26
# Purpose: Research foundation for Pokemon Crystal agent

---

## Tier 1 — Directly Relevant (Pokemon + LLM agents)

### The PokeAgent Challenge (NeurIPS 2025)
- **arxiv:** 2603.15563
- **URL:** https://arxiv.org/html/2603.15563v2
- **Competition site:** https://pokeagent.github.io/
- **What:** Two-track competition — battling (strategic reasoning, partial observability) + speedrunning (long-horizon planning, sequential decision-making)
- **Scale:** 100+ teams, 650+ community members, 150+ submissions
- **Key finding:** "Considerable gaps between generalist (LLM), specialist (RL), and elite human performance." Pokemon battling is "nearly orthogonal to standard LLM benchmarks."
- **Why it matters for us:** First standardized evaluation framework for RPG speedrunning. Open-source multi-agent orchestration system. Proves hybrid LLM+RL is the winning architecture.
- **Our position:** We're building the speedrunning track approach (LLM planning + tool use). If battles become the bottleneck, their RL specialist data is the path forward.

### PokeChamp (ICML 2025 Spotlight)
- **arxiv:** 2503.04094
- **URL:** https://arxiv.org/abs/2503.04094
- **Repo:** https://github.com/sethkarten/pokechamp
- **What:** Minimax + LLM hybrid for competitive Pokemon battles. No additional LLM training.
- **Architecture:** LLM replaces 3 minimax modules: (1) player action sampling, (2) opponent modeling, (3) value function estimation
- **Results:** GPT-4o achieves 76% WR vs best LLM bot, 84% vs strongest rule-based bot. Elo 1300-1500 (top 10-30% humans).
- **Dataset:** 3M+ real player battles, 500k+ high-Elo matches
- **Why it matters for us:** If we add competitive battle support later, this is the architecture. Minimax tree search + LLM evaluation is the proven approach.
- **Key insight:** No training needed — just prompt engineering + search structure.

---

## Tier 2 — Conceptual Foundations

### Toolformer (Meta AI, 2023)
- LLMs learning to use tools autonomously
- Directly parallels our press_buttons/navigate_to tool interface
- Our agent is essentially Toolformer applied to game emulation

### Monte Carlo Tree Search (AlphaGo lineage)
- Game tree search for decision-making under uncertainty
- Relevant if we add RL battle specialist (Phase 5+)
- PokeChamp uses minimax variant, not MCTS — but same family

### Curriculum Learning
- Our milestone progression (room -> city -> gym -> league) is textbook curriculum scaffolding
- Start with easy sub-goals, build up to full game completion
- PokeAgent Challenge speedrunning track uses similar milestone-based evaluation

### Self-Play / Self-Improvement
- Our self-anchoring counter (failed strategy anonymization) is a form of adversarial self-reflection
- CCA's self-learning journal is a meta-level version of the same idea
- Three nested evolution loops: Pokemon in-game, bot strategies, CCA system

---

## Architecture Comparison: Us vs Community

| Feature | Our Agent | ClaudePlaysPokemon | PokeChamp | PokeAgent |
|---------|-----------|-------------------|-----------|-----------|
| Game | Crystal (Gen II) | Red (Gen I) | Showdown | Emerald |
| Emulator | PyBoy | PyBoy | N/A (sim) | PyGBA |
| LLM | Opus 4.6 | Claude 3.7+ | GPT-4o | Various |
| RAM reading | Yes | Yes | N/A | Yes |
| A* pathfinding | Yes | Some forks | N/A | Yes |
| Stuck detection | Enhanced (self-anchoring) | Basic | N/A | Basic |
| Battle strategy | LLM only | LLM only | Minimax+LLM | RL+LLM |
| Offline capable | Yes (except LLM) | No | No | No |
| Self-learning | CCA pipeline | None | None | None |

Our unique advantages: Crystal (Gen II, more complex), offline-capable, self-anchoring counter, CCA self-learning pipeline, menu state detection from RAM.
