# MT-53: Opus 4.6 Pokemon Performance — Deep Intelligence
# Source: r/ClaudePlaysPokemon full subreddit absorption (397 posts, S201)
# Date: 2026-03-26
# Purpose: Every actionable finding for building our Crystal bot

---

## 1. OPUS 4.6 vs ALL PREVIOUS MODELS — Hard Numbers

### Speed Comparison (Pokemon Red, same harness lineage)
| Model | Steps to Victory Road | Time to Exit Mt. Moon | Safari Zone Attempts for HM03 |
|-------|----------------------|----------------------|-------------------------------|
| Claude 3.7 Sonnet | Never reached | ~78 hours | N/A |
| Claude Opus 4.0 | ~1000 hours (halfway) | Long | N/A |
| Claude Opus 4.5 | ~206,000 steps | ~8 hours | 41 attempts |
| **Claude Opus 4.6** | **~30,000 steps** | **21 min (3,043 steps)** | **13 attempts** |

**Opus 4.6 is ~7x faster than 4.5 measured by steps, ~10x faster by time.**

### Key Milestones (Opus 4.6 only — from community tracking)
- Step 157: First rival battle won
- Step 658: Exited Viridian Forest (new PB)
- Step 798: Beat Brock
- Step 4,307: Exited Mt. Moon (21 min 43 sec)
- Step 13,224: Beat Giovanni (Hideout) + Silph Scope
- Step 15,855: Beat Giovanni (Silph Co)
- Step 16,804: Beat Sabrina
- Step 19,086: Beat Koga (5/8 badges)
- Step 21,574: Gold Teeth obtained
- Step 21,612: HM03 Surf obtained (13 Safari attempts vs 41 for 4.5)
- Step 23,533: Beat Erica (backtracked for Rainbow Badge — needed for Strength)
- Step 29,925: Beat Blaine
- Step 30,275: Beat Giovanni (Gym Leader, 8/8 badges)
- Step 30,625: Entered Victory Road (15% of steps 4.5 needed)
- Step 35,911: First boulder puzzle solved
- Step 45,048: Second boulder puzzle solved (F1 done for 2nd time)
- Step 45,200: Second boulder puzzle (F2) solved

### Comparison: Benjamin Todd Analysis (X/Twitter)
"Opus 4 needed about 1,000 hours to get roughly halfway through the game,
Opus 4.5 could almost finish in about 1,000 hours, and Opus 4.6 was another 10x faster."

---

## 2. WHY OPUS 4.6 IS BETTER — Community Analysis

### u/ApexHawke (highly upvoted, 7pts):
> "4.6 is much less likely to get stuck on a bad hallucination or an infinite loop of actions.
> It has more of a tendency to try new things when it gets stuck. Sometimes it wanders away
> from the correct solution, but most of the time Claude is much more quick to zero in on
> a correct solution via its semi-random adjustments."

> "There's also some smaller things this claude does that the previous ones didn't like
> buying more items (potions, pokeballs and Repels), and it can think just a smidge less
> rigidly than previous Claudes."

### u/ChezMere (key insight — applies to 4.5 AND 4.6):
> "The key takeaway about Opus 4.5 and Gemini 3 is that they're quite smart whenever
> they DON'T make any false assumptions, but once they do, they take an absurdly long time
> to notice their error, and end up paralyzed for ages. A big part of this being because
> they never notice when they're in a long loop of retrying the same wrong idea hundreds
> of times."

### u/reasonosaur (stream maintainer):
> "Claude has inhuman patience. But it's inhuman patience combined with the inability to
> actually commit to the systematic completion of a plan."

### u/doubleunplussed (on single-goal focus):
> "He's very focused on the task at hand, it's hard for him to balance 'train pokemon' and
> 'progress in dungeon' given the two are a trade-off. Or even just given that's two goals —
> two is too much for him."

> "He also has some ideas about needing to be 'fast'. This makes him run from wild pokemon
> in the name of saving 'time'. But it makes sense that it reduces clutter in his context."

---

## 3. FAILURE MODES STILL PRESENT IN 4.6

### 3A. Boulder Puzzle — Brute Force, Not Understanding
u/doubleunplussed: "The solution was entirely brute-force. Claude never really made the
connection between the maybe-switch that he could see and the idea of pushing the boulder
there. Instead, he systematically placed the boulder on every accessible tile, each time
walking over to the barrier to check if it had opened."

After solving, Claude exited and lost the state (it resets on floor change).
**Implication for Crystal:** Need explicit spatial puzzle support or at minimum a persistent
notepad that tracks puzzle solutions.

### 3B. DIG Escape Habit — Resets Dungeon Progress
u/ApexHawke: "In general terms, when you give the model a button, they will eventually push it."
Claude repeatedly digs out of dungeons, resetting puzzle state and wasting progress.
**Implication for Crystal:** Consider making DIG unavailable in dungeons with puzzle state,
or adding explicit "don't dig unless X" to the system prompt.

### 3C. False Assumptions Are Sticky
Claude takes "an absurdly long time" to notice errors. Once committed to a wrong hypothesis,
it retries hundreds of times. The "inhuman patience" becomes a liability.
**Implication for Crystal:** Stuck detection (same location for N steps) MUST trigger
a forced strategy change, not just a gentle suggestion.

### 3D. Can't Balance Two Goals
When told to both progress through a dungeon AND train Pokemon, Claude can only focus on one.
It runs from wild encounters because fighting risks blackout AND clutters context.
**Implication for Crystal:** Give clear priority ordering in system prompt. "Progress > Training
unless team HP < 50% or level disadvantage > 5."

### 3E. Knowledge Base Corruption After Summarization
From Opus 4.5 era: Claude's notes on the Mansion puzzles became contradictory after DIG resets.
The knowledge base contained two conflicting entries about the same barrier.
**Implication for Crystal:** RAM reading eliminates this — we read game state directly,
not relying on Claude's notes about it.

---

## 4. HARNESS DETAILS — What the Claude Stream Actually Uses

### Current Harness (Opus 4.6):
1. **Color hack ROM** — Gen 2 coloring for better vision
2. **Red squares** on unreachable terrain (walls)
3. **Cyan squares** on unreachable floor tiles (can't path there from current position)
4. **Navigation tool** — auto-walk to screen coordinates
5. **One-page notepad** — persistent notes loaded into context
6. **Spin tile fix** — Navigator treats spin tiles as obstructions, model must step manually
7. **Screenshot pause** — No screenshots captured while model is mid-spin
8. **Multi-file memory system** — restored for 4.5+ (was removed, then brought back)
9. **Surf support** — necessary for late game

### What Was Removed Over Time:
- Location hints from the streamer (mostly removed for 4.5)
- Internal file system (models couldn't manage it well, replaced with single notepad)
- Some game mechanic tips in the prompt

### Harness Changes for 4.5 (that helped significantly):
From u/NotUnusualYet's cut content:
> "The importance of points 2 and 3 (spin tile fixes) must be explained... in the Team Rocket
> Hideout spin maze, the model was constantly walking onto spinner tiles while trying to path
> somewhere else, and also being provided screenshots of the player character mid-spin."

---

## 5. HARNESS DEBATE — Key Perspectives

### "Scaffolding > Model Intelligence" Camp
u/ATimeOfMagic: "Testing and iterating on a solid scaffold seems to be substantially
more valuable than upgrading raw intelligence."

u/Badfan92: "The cases where LLMs really are better than any other traditional system
are also exactly those cases where you can't really help from the harness. Solving all
long horizon aspects in the harness doesn't show that LLM systems can now solve long
horizon tasks — it shows that YOU can solve long horizon tasks."

### "Minimal Harness Is More Impressive" Camp
u/ChezMere: "This progress is far more impressive than what Gemini and GPT have done
with their strong harnesses."

u/NotUnusualYet: "Ultimately the LLM is doing all the reasoning... What I would consider
an 'advanced' harness would be something much more tool heavy."

### OUR POSITION (Matthew's directive):
**Minimal harness, let Opus 4.6 reason.** But we have ONE unfair advantage the stream
doesn't: full RAM reading. The stream uses "almost vision-only" with minimal RAM.
We use complete RAM state. This is not "cheating" — it's giving the model ground truth
instead of making it hallucinate from screenshots.

---

## 6. GPT AND GEMINI COMPARISON INTELLIGENCE

### GPT-5.1 (Beat Pokemon Red Fastest — ~138 hours):
- Harness: 7000+ word prompt, forced exploration directive, fully automatic map data,
  long-range pathfinder, LLM-reasoning-powered navigator
- ROM optimized for faster movement
- Prompted to use game knowledge and complete as fast as possible
- u/Own-Cartoonist4263: "fundamentally different goals" — optimized for speed, not testing

### Gemini 2.5 Pro (Beat Pokemon Blue):
- First run: harness advantages weren't present for most of the run (bugs)
- Second run: half the time, harness working properly
- Prompted to NOT use game knowledge, act like first-time player
- No ability to write code or take notes in some runs
- "Almost vision-only" approach for Crystal (anonymized IDs, minimal RAM)

### Key Insight: The Comparison Is Invalid
u/Own-Cartoonist4263 (likely a developer): "The harnesses/projects have different goals
entirely. If you optimize for different goals, you will naturally be unable to compare."

For MT-53: We don't care about comparisons. We care about beating Crystal.

---

## 7. CRYSTAL-SPECIFIC INTELLIGENCE (From All Sources)

### Why Crystal Is Harder Than Red:
1. **Two regions** (Johto + Kanto) = 2x the content
2. **Day/night cycle** — certain events only happen at certain times
3. **More complex HM chains** — Surf, Waterfall, Whirlpool, Strength, Cut, Flash, Fly
4. **Non-linear gym order** (partially) — can do some gyms out of order
5. **Phone system** — NPCs call you, can trigger events
6. **Ice Path puzzle** — harder than any Red puzzle
7. **Radio Tower** — multi-floor dungeon with Team Rocket
8. **16 badges total** (8 Johto + 8 Kanto)

### Crystal Attempts to Date:
- **Gemini 3.1 Pro** — "Almost vision-only" harness. Never got 8th badge.
  Accidentally KO'd Suicune. 4 sub-agents, 6 tools, extensive knowledge base.
- **No Claude Crystal attempt exists.** This is our opening.

### Our Crystal Advantages:
1. Full RAM reading (37 tests) — party, location, badges, items, time of day
2. A* pathfinding (36 tests) — collision-aware navigation
3. Emulator control (42 tests) — button presses, screenshots, state management
4. Game state aggregation (43 tests) — formatted state for Claude
5. Opus 4.6 — strongest model, proven 7-10x improvement over 4.5

---

## 8. ACTIONABLE DESIGN DECISIONS FOR MT-53

Based on all subreddit intelligence:

1. **Keep minimal harness** — 2 tools (press_buttons, navigate_to) is right
2. **Add stuck detection** — Same location for 10+ steps → force new behavior
3. **Add anti-dig guard** — Prevent digging out of puzzles that have state
4. **RAM state > Notes** — Don't rely on Claude's notepad for game state
5. **Priority ordering in prompt** — "Progress > Training unless [conditions]"
6. **Spin/slide tile handling** — Treat special tiles as manual-only (like stream)
7. **Screenshot upscaling** — 2x proven to help vision (from stream)
8. **Summarization with team/location** — Proven critical for long runs
9. **No game walkthrough in prompt** — Advice, not orders (from stream experience)
10. **DIG respawn management** — Teach Claude to visit Pokemon Centers before dungeons

---

## 9. SOURCES

- r/ClaudePlaysPokemon — 397 posts scanned, ~30 read in detail with all comments
- LessWrong: "Insights into Claude Opus 4.5 from Pokemon" (NotUnusualYet)
- LessWrong: "Research Notes: Running Claude 3.7, Gemini 2.5 Pro, and o3" (NotUnusualYet)
- LessWrong: "Is Gemini now better than Claude at Pokemon?" (NotUnusualYet)
- GitHub: ClaudePlaysPokemonStarter, NousResearch/pokemon-agent, gpt-plays-pokemon
- Gemini Crystal harness: waylaidwanderer/gemini-plays-pokemon-public
- Google Docs: Harness changes document (linked from subreddit)
- Google Sheets: All LLM Pokemon runs raw data (SyAl04)
