# MT-53 Phase 4: Integration + Hardening
# Based on: S201 agent intelligence (8 agents, 78KB), Phase 3 code review
# Prerequisite: ROM file (pokemon_crystal.gbc) installed

---

## What Phase 3 Built

| File | LOC | Tests | Purpose |
|------|-----|-------|---------|
| config.py | 30 | 10 | Configuration constants |
| tools.py | 100 | 24 | 3 tools + validation |
| prompts.py | 200 | 40 | System prompt, state formatting, stuck detection |
| agent.py | 350 | 31 | Core loop, MockLLM, summarization |
| main.py | 100 | 9 | CLI entry point |
| **Total Phase 3** | **780** | **114** | |
| **Total pokemon-agent** | **~2,250** | **272** | Including Phase 2 modules |

---

## Design Decisions from S201 Agent Intelligence

### 1. Anti-Blackpilling (Agent 3)
**Finding:** Without encouragement, Claude "starts blackpilling and refusing to play saying the game is broken."
**Decision:** System prompt includes encouragement ("You're doing great") — ALREADY IN prompts.py.
**Phase 4:** Add dynamic encouragement when consecutive failures exceed 5. Escalate from "try a different approach" to "this is a hard part of the game, persistence pays off."

### 2. Self-Anchoring Counter (Agent 8)
**Finding:** Models are far less likely to change their mind when shown their own previous answer. Anonymization trick works — present the model's own wrong answer as "another AI's" suggestion.
**Decision:** When stuck detection fires AND the model repeats a strategy:
- Include in stuck prompt: "A previous AI tried [X] and it didn't work. What would YOU try instead?"
- This leverages the documented self-anchoring bias to force new approaches.
**Phase 4 task:** Implement `_format_stuck_context()` that anonymizes the model's failed approach.

### 3. Sandboxing (Agent 3)
**Finding:** Gemini hallucinated it should have map data, searched the filesystem, and exploited internal harness files.
**Decision:** Our agent can't access the filesystem beyond save states. Tool surface is 3 tools only. No file access tools. No knowledge base tool. This is already correct by design.
**Phase 4:** Verify tool validation rejects any unexpected tool names.

### 4. Hybrid LLM+RL Insight (Agent 4)
**Finding:** NeurIPS 2025 showed hybrid LLM planning + RL execution wins speedrunning. Small RL specialists beat LLM generalists at battling.
**Decision:** Phase 4 is pure LLM. Phase 5+ could add RL-trained battle specialist. Park this.
**Future:** If battles prove to be the bottleneck, add a lightweight RL policy for battle decisions.

### 5. Vision vs RAM (Agent 5)
**Finding:** "They're all mostly good enough reasoners once they have access to the relevant facts."
**Decision:** RAM reading is our unfair advantage. Vision is supplementary, not primary.
**Phase 4:** Ensure format_game_state provides ALL relevant facts. Add:
- Current menu state (in menu vs overworld vs battle)
- Available items with quantities
- Known NPC locations if available from RAM

### 6. Completion Benchmarks (Agent 6)
**Finding:** GPT-5 CT beat Crystal Champion in 91h / 5,743 steps with optimized prompt.
**Decision:** Our first target is Falkner (Gym 1), not full completion. Incremental goals:
1. Navigate from New Bark Town to Cherrygrove City
2. Reach Violet City
3. Beat Falkner
4. Each milestone validates the harness works
**Phase 4 integration test:** Run 50 steps and verify the agent can navigate out of a room.

### 7. Reference Repos (Agents 5, 6, 7)
**Priority repos to study (in order of relevance to our stack):**
1. `jacobyoby/mewtoo` — PyBoy + memory reads + Claude/Ollama (MOST similar to us)
2. `clambro/ai-plays-pokemon` — workflow-based, cheaper models
3. `Clad3815/gpt-play-pokemon-firered` — GPT reference impl
4. `sethkarten/pokeagent-speedrun` — NeurIPS competition, Emerald adapter
**Phase 4:** Read mewtoo's screen state detection and compare with our emulator_control.py.

### 8. Gemini's 14 Self-Discovered Rules (Agent 8)
**Key rules to incorporate:**
- "NEVER use dead reckoning" — always use RAM coordinates (already our design)
- "EXHAUSTIVE EXPLORATION before declaring dead end" — add to system prompt
- "HALLUCINATION CHECK system" — verify RAM state matches expected outcome after actions
- "Custom tools CANNOT read screen mid-execution" — our tools don't try to (correct by design)
**Phase 4:** Add post-action verification: after navigate_to, verify RAM position matches target.

---

## Phase 4 Build Order

### Step 1: Post-Action Verification (~50 LOC, ~15 tests)
Add to agent.py: after executing a tool call, read RAM to verify the action took effect.
- After press_buttons: verify game state changed (not frozen)
- After navigate_to: verify position matches target ± 1 tile
- After wait: no verification needed

### Step 2: Enhanced Stuck Detection (~80 LOC, ~20 tests)
Upgrade stuck detection with self-anchoring counter:
- Track last N failed strategies (button sequences)
- When stuck, include anonymized "another AI tried X" context
- Add dynamic encouragement escalation (3 levels)

### Step 3: Menu State Detection (~60 LOC, ~15 tests)
Read RAM to detect current menu/mode state:
- Overworld, battle, menu, dialog, shop, Pokemon Center
- Add to format_game_state output so the model knows what screen it's on

### Step 4: Integration Test Framework (~100 LOC, ~10 tests)
- Test harness that runs N agent steps with MockLLM
- Verify state changes propagate correctly through the full loop
- Verify summarization + stuck detection + tool execution work end-to-end

### Step 5: Real Emulator Test (requires ROM)
- Run agent for 50 steps against real PyBoy
- Verify screenshots are captured
- Verify RAM reads return valid data
- Manual verification only (not automated — needs ROM)

---

## Estimated Scope
- ~290 LOC new code
- ~60 new tests
- Total after Phase 4: ~2,540 LOC, ~330 tests
- Achievable in 1 session
