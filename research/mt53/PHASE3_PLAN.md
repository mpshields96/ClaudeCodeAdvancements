# MT-53 Phase 3: Pokemon Crystal Agent — Build Plan
# Based on: r/ClaudePlaysPokemon ecosystem research (S201)
# Directive: "Minimal to no harness" — let Opus 4.6 reason
# Target: Pokemon Crystal via PyBoy

---

## Architecture: Minimal Harness for Opus 4.6

### Design Philosophy
From Matthew: "minimal to no harness." From the subreddit: Gemini 3.1 Pro beat the
Pokemon League with a "weak harness." Opus 4.6 is a stronger reasoner. We should need
LESS scaffolding, not more.

What we keep (ground truth):
- RAM reading for game state (location, party, battle, items, badges)
- Screenshots for visual context (upscaled 2x)
- A* pathfinding (already built, 36 tests)
- Progressive summarization (proven pattern)

What we skip (let Opus think):
- No elaborate knowledge base system (Opus can track state in context)
- No meta-critique LLM (Opus 4.6 self-corrects)
- No separate navigator LLM instance
- No checkpoint system (RAM reading IS ground truth)
- No AlphaEvolve parameter evolution
- No Twitch integration
- No dashboard (initially)

### Target: Simpler than ClaudePlaysPokemon, Stronger than "Almost Vision-Only"

```
┌─────────────────────────────────────────────┐
│              CORE LOOP (agent.py)            │
│                                             │
│  1. Read game state from RAM (ground truth) │
│  2. Capture screenshot (upscaled 2x)        │
│  3. Send state + screenshot to Opus 4.6     │
│  4. Opus responds with reasoning + tool call│
│  5. Execute tool call                       │
│  6. Check for summarization threshold       │
│  7. Save state periodically                 │
│  Repeat                                     │
└─────────────────────────────────────────────┘
```

---

## What Already Exists (S200)

| Module | LOC | Tests | Status |
|--------|-----|-------|--------|
| memory_reader.py | ~400 | 37 | Crystal RAM reader — party, location, badges, items |
| emulator_control.py | ~400 | 42 | PyBoy wrapper — buttons, screenshots, ticks |
| navigation.py | ~500 | 36 | A* pathfinding with collision detection |
| game_state.py | ~170 | 43 | State aggregation + formatting |
| **Total** | ~1470 | **158** | All passing |

---

## What Needs to Be Built (Phase 3)

### File 1: agent.py — Core Agent Loop (~300 LOC)

The heart of the system. Modeled after ClaudePlaysPokemonStarter/simple_agent.py.

```python
class CrystalAgent:
    def __init__(self, rom_path, headless=True, max_history=60):
        self.emulator = EmulatorControl(rom_path, headless)
        self.memory = CrystalMemoryReader(self.emulator.pyboy)
        self.navigator = Navigator(collision_map)
        self.client = Anthropic()
        self.message_history = []
        self.max_history = max_history

    def step(self):
        # 1. Get game state from RAM
        state = self.memory.get_full_state()

        # 2. Get screenshot
        screenshot = self.emulator.get_screenshot()
        screenshot_b64 = encode_screenshot(screenshot, upscale=2)

        # 3. Format state + screenshot for Claude
        messages = self.build_messages(state, screenshot_b64)

        # 4. Call Opus 4.6
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
        )

        # 5. Process tool calls
        for tool_call in response.tool_calls:
            self.execute_tool(tool_call)

        # 6. Check summarization
        if len(self.message_history) >= self.max_history:
            self.summarize()

    def run(self, num_steps=1000):
        for i in range(num_steps):
            self.step()
```

Key decisions:
- model="claude-opus-4-6" — use the strongest model
- max_history=60 — same as official starter
- Upscale 2x — proven to help vision
- Single model, no sub-agents (minimal harness)

### File 2: prompts.py — System Prompt + Summarization (~200 LOC)

System prompt should be MINIMAL. From the Gemini Crystal experience:
- Don't give strict orders, give advice
- Remind about vision limitations
- Include Crystal-specific tips sparingly
- No game walkthrough content

```python
SYSTEM_PROMPT = """You are playing Pokemon Crystal autonomously. You see
screenshots and receive game state from RAM.

Your goal: Complete the game — all 16 badges, defeat Red on Mt. Silver.

Key facts about your situation:
- Your vision of Game Boy screens is imperfect. Trust the RAM state data.
- The game has two regions: Johto (8 gyms) then Kanto (8 gyms).
- Day/night cycle affects encounters and NPC availability.
- You can press buttons or navigate to coordinates.

Before each action, briefly explain your reasoning.
If you're stuck in a loop, try something completely different.
"""

SUMMARY_PROMPT = """Summarize the conversation history. Include:
1. Current location and objective
2. Pokemon team (species, levels, key moves)
3. Badges earned
4. Items of importance
5. What you were trying to do and any obstacles
6. Places you've explored and dead ends found
"""
```

### File 3: tools.py — Tool Definitions (~100 LOC)

Minimal tool surface (2-3 tools):

```python
TOOLS = [
    {
        "name": "press_buttons",
        "description": "Press Game Boy buttons in sequence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "buttons": {
                    "type": "array",
                    "items": {"type": "string", "enum": [
                        "a", "b", "start", "select",
                        "up", "down", "left", "right"
                    ]}
                },
                "wait": {"type": "boolean", "description": "Wait between presses"}
            },
            "required": ["buttons"]
        }
    },
    {
        "name": "navigate_to",
        "description": "Navigate to grid coordinates using A* pathfinding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "row": {"type": "integer"},
                "col": {"type": "integer"}
            },
            "required": ["row", "col"]
        }
    }
]
```

Only 2 tools. No knowledge base tool, no menu navigator, no move selector.
Let Opus 4.6 figure out menus and battles through button presses.
If this proves insufficient, we add tools incrementally.

### File 4: config.py — Configuration (~30 LOC)

```python
MODEL_NAME = "claude-opus-4-6"
MAX_TOKENS = 4096
TEMPERATURE = 0.0  # Deterministic for reproducibility
MAX_HISTORY = 60   # Messages before summarization
USE_NAVIGATOR = True
SCREENSHOT_UPSCALE = 2
SAVE_INTERVAL = 50  # Save state every N steps
STUCK_THRESHOLD = 10  # Same location for N steps = stuck
```

### File 5: main.py — Entry Point (~50 LOC)

```python
import argparse
from agent import CrystalAgent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default="pokemon_crystal.gbc")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--load-state", type=str, default=None)
    args = parser.parse_args()

    agent = CrystalAgent(args.rom, headless=args.headless)
    if args.load_state:
        agent.emulator.load_state(args.load_state)
    agent.run(num_steps=args.steps)

if __name__ == "__main__":
    main()
```

---

## Build Order (TDD)

### Step 1: prompts.py + tools.py (no dependencies)
- Write system prompt and tool definitions
- Tests: validate prompt structure, tool schema validity

### Step 2: config.py (no dependencies)
- Configuration constants
- Tests: validate defaults

### Step 3: agent.py (depends on all existing modules)
- Core loop connecting everything
- Tests: mock emulator + mock Claude API
  - Test step() builds correct messages
  - Test summarization triggers at max_history
  - Test tool call routing
  - Test stuck detection

### Step 4: main.py (depends on agent.py)
- Entry point with arg parsing
- Tests: arg parsing, agent creation

### Step 5: Integration test (requires ROM)
- Actually run the agent for 10 steps
- Verify screenshots captured, state extracted, API called
- This is manual/optional — needs ROM file

---

## Estimated Scope
- ~680 LOC new code (agent.py 300 + prompts.py 200 + tools.py 100 + config.py 30 + main.py 50)
- ~200 LOC new tests
- Builds on 1,470 LOC existing code (158 tests)
- Total after Phase 3: ~2,350 LOC, ~360 tests
- Achievable in 1-2 sessions

---

## Key Lessons from Gemini's Crystal Failures (Built Into Design)

1. **Stuck detection** — Track location across steps. Same location for 10+ steps = stuck. Prompt model to try something different.
2. **Inventory check before quests** — System prompt reminds to check inventory first.
3. **Trust RAM over vision** — System prompt explicitly says "Trust the RAM state data."
4. **Short path planning** — Navigator handles this (A* on current visible map only).
5. **No deferred maintenance** — No knowledge base to maintain = no maintenance problem.
6. **Summarization preserves team + location** — Summary prompt is specific.
7. **Day/night awareness** — Memory reader provides time of day from RAM.

---

## Opus 4.6 Intelligence (S201 Deep Subreddit Absorption)

### Performance Data (from r/ClaudePlaysPokemon live tracking)
- Opus 4.6 is **7-10x faster** than 4.5 on Pokemon Red (same harness lineage)
- Reached Victory Road in ~30K steps (vs ~206K for 4.5)
- Exited Mt. Moon in 21 min / 3,043 steps
- Safari Zone: 13 attempts (vs 41 for 4.5)
- **Full data:** research/mt53/OPUS46_PERFORMANCE_INTEL.md

### Failure Modes Still Present in 4.6 (MUST address in Crystal bot)
1. **Sticky false assumptions** — Once committed to wrong hypothesis, retries hundreds of times
   → Stuck detection threshold (10 steps) must FORCE strategy change, not suggest
2. **DIG escape habit** — Digs out of dungeons, resetting puzzle progress
   → Anti-DIG guard: track if dungeon has active puzzle state, warn before digging
3. **Can't balance two goals** — "Train Pokemon" vs "Progress through dungeon" overloads it
   → Priority ordering in system prompt: "Progress > Training unless HP < 50% or level gap > 5"
4. **Brute-force puzzles** — Solves boulder puzzles by trying every tile, not understanding
   → For Crystal: Ice Path puzzle is the hardest challenge, may need spatial hints
5. **Forgets solutions** — After DIG/exit, doesn't remember how it solved a puzzle
   → RAM reading advantage: we read game state, not Claude's notes about it

### Harness Debate Resolution (for our design)
Community split: "scaffolding > model intelligence" vs "minimal harness proves more."
**Our position:** Minimal harness (2 tools) BUT with full RAM reading as ground truth.
This is the stream's approach + our unfair advantage. Not "cheating" — giving the model
accurate data instead of making it hallucinate from screenshots.

### What Makes 4.6 Better (behavioral, from community)
- Less likely to get stuck in hallucination loops
- Tries new things when stuck (more exploratory)
- Buys items strategically (potions, pokeballs, repels)
- Less rigid thinking overall
- These improvements VALIDATE minimal harness — stronger model needs LESS scaffolding
