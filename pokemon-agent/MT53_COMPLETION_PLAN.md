# MT-53 Completion Plan

## Why This Doc Exists

MT-53 has research, milestone logs, and a high-level 9-phase roadmap in `MASTER_TASKS.md`,
but it does not have one current execution plan that answers:

- What does "100% complete" actually mean?
- What is already built vs merely researched?
- What must be planned, designed, built, tested, and executed next?
- What is the correct order of operations for `pokemon-agent/` on macOS with mGBA?

This document is the missing source of truth.

## Hard Constraints

- **mGBA only.** PyBoy is banned for MT-53 on this machine.
- **Crystal first.** Do not dilute the plan by mixing Crystal, Emerald, and ROM hacks in one build phase.
- **Zero ongoing token burn is the final target.** LLM-assisted play is allowed for research and prototyping, but not as the final runtime architecture.
- **One file = one job.** Follow existing CCA architecture discipline.
- **Steal code where useful.** Port/adapt from reference repos instead of rewriting solved pieces.

## What "100%" Means

There are two finish lines. They should not be conflated.

### Finish Line A: Crystal MVP

The bot can complete Pokemon Crystal start-to-finish on mGBA with no human input, using a
repeatable standalone runtime on macOS.

Minimum bar:

- boots and recovers from save state reliably
- navigates towns, routes, caves, and story buildings
- handles menus, healing, shops, PCs, and HM use
- catches and maintains a viable team automatically
- defeats gyms, Elite Four, and champion
- survives crashes, wipes, and stuck states with checkpoint recovery
- produces logs and milestone artifacts so failures are debuggable
- can run without Claude or Gemini making decisions at runtime

### Finish Line B: Full MT-53

Everything in Crystal MVP, plus the larger Matthew directive from `MASTER_TASKS.md`:

- post-game legendaries and practical Pokedex completion in Crystal
- Emerald support on the same mGBA-first architecture
- ROM hack support after base games are stable
- dark/toilet-humor naming and commentary
- x1.5/x2 watchable runtime
- cross-run data logging and self-improvement

## Current Reality Check

Estimated status as of 2026-04-02:

- **Crystal MVP:** about `40-45%`
- **Full MT-53:** about `20-25%`

Reason:

- the emulator and state-reading foundation are real
- some battle logic and boot automation exist
- live mGBA + Gemini runs now work
- but the project still lacks the actual zero-token autonomous brain, Crystal pathfinding,
  story progression engine, robust party/team management, and full-route reliability

## Capability Matrix

| Area | Status | Notes |
| --- | --- | --- |
| mGBA emulator control | Done | Real ROM boots, save states load, button/frame control works |
| Crystal RAM reader | Done | Position, battle, party, badges, text hooks exist |
| Crystal boot/setup state | Done | `setup_crystal_state.py`, `crystal_playable` base state |
| Live Gemini path | Partial | Useful for prototyping, but not final architecture |
| Tool schema/message bridge | Done | Gemini path now executes tools without schema mismatch |
| Action verification/checkpoints | Partial | Core path exists; longer recovery loops still need proving |
| Crystal navigation/pathfinding | Missing | No live Crystal navigator wired from `main.py` |
| Menu automation | Partial | Basic button tools exist; full deterministic menu workflows do not |
| Battle AI | Partial | Useful foundation, not full Gen 2 story-grade autonomy |
| Catch/team management | Partial | Pieces exist; no full team-building policy loop |
| Story progression engine | Missing | No badge/story/HM/state-machine planner yet |
| Item economy/shop logic | Partial | Data and tools exist; policy layer is missing |
| PC/box management | Missing | Needed for practical dex/team rotation |
| HM usage / world traversal gating | Missing | Required for full game completion |
| Robust recovery from wipes/stuck states | Partial | Checkpoints exist; retry/recovery policy incomplete |
| Zero-token offline brain | Missing | Final target not implemented |
| Naming/personality layer | Partial | Prompt personality exists; standalone naming system does not |
| Telemetry and run evaluation | Partial | Logs exist; milestone/failure dashboards are missing |
| Emerald support | Missing | Explicitly out of scope until Crystal MVP passes |

## Plan of Record

### Phase 0: Freeze The Target

Goal: stop scope drift.

Deliverables:

- Crystal MVP definition of done
- capability matrix kept current
- milestone list with acceptance tests

Acceptance:

- this document exists and is the file future MT-53 work references first

### Phase 1: Runtime Hardening

Goal: make the current mGBA harness reliable enough to build on.

Build:

- remove or hide any tool not executable in the current runtime
- migrate remaining backend-specific edge cases into clean adapter boundaries
- add request pacing/backoff for Gemini prototype runs
- document supported run modes: offline, Gemini prototype, final offline brain

Test:

- repeated 25-step smoke runs from `crystal_playable`
- restart-from-state reliability tests
- explicit tool-contract tests for every exposed tool

Acceptance:

- 10 consecutive smoke runs complete without backend/schema/type failures

### Phase 2: Crystal Navigation Engine

Goal: make overworld traversal deterministic.

Build:

- Crystal map registry for current reachable maps
- collision/walkability reader for Crystal
- warp/door/stairs metadata for Crystal
- navigator wiring into `main.py` / `CrystalAgent`
- deterministic door, stairs, and route transitions

Test:

- unit tests for map data, walkability, and warp links
- milestone tests:
  - leave player's house
  - enter Elm's lab
  - leave New Bark Town
  - reach Route 29 grass

Acceptance:

- `navigate_to` works on real Crystal intro maps and reaches target transitions reliably

### Phase 3: Deterministic Menu And Utility Engine

Goal: stop depending on free-form model reasoning for mechanical chores.

Build:

- reusable menu scripts for:
  - party screen
  - move selection
  - Pokemon Center healing
  - marts and buying
  - item use
  - save/load/retry flows
- deterministic interaction helpers for signs, NPCs, yes/no prompts, move learning

Test:

- scripted state-based tests for each menu flow
- real emulator milestones:
  - heal at Pokemon Center
  - buy Pokeballs
  - use item from bag

Acceptance:

- routine non-strategic interactions no longer require an LLM

### Phase 4: Gen 2 Battle And Catch Policy

Goal: make combat and capture reliable enough for story progression.

Build:

- finish Gen 2 battle heuristics
- trainer vs wild battle distinction throughout
- catch policy: when to catch, weaken, status, skip
- healing/switching/item thresholds
- whiteout recovery policy

Test:

- deterministic battle scenarios
- first wild encounter test
- trainer battle survival tests
- gym leader rehearsal fixtures where feasible

Acceptance:

- bot can survive early-game battles and maintain a functional team without human help

### Phase 5: Team Builder And Resource Policy

Goal: stop improvising party composition.

Build:

- target team planner for Crystal
- encounter/catch shortlist by route
- move progression and evolution plan
- item economy policy: what to buy, save, carry
- PC/box management for overflow

Test:

- planner tests for target composition and replacement rules
- route-capture tests for early team formation

Acceptance:

- bot can explain and execute a stable team plan from starter through champion

### Phase 6: Story Progression Engine

Goal: convert scattered mechanics into an actual game-completion policy.

Build:

- objective/state machine for badges, story events, HMs, key items, blockers
- route plans by segment:
  - intro -> first badge
  - early game
  - mid game
  - late game
  - Elite Four
- retry logic for failed fights or dead-end states

Test:

- milestone harnesses for major story checkpoints
- recovery tests after wipe/reload

Acceptance:

- bot can progress from one major story checkpoint to the next without manual intervention

### Phase 7: Offline Brain

Goal: hit Matthew's real requirement: no ongoing token burn.

Build:

- replace LLM-driven decision loop with an internal planner/policy engine
- keep Gemini/LLM only as optional dev instrumentation, not runtime dependency
- choose architecture explicitly:
  - finite-state progression engine
  - deterministic planners for known routes/menus
  - heuristic policy for exploration and battles

Test:

- offline step-loop tests
- long-run soak from `crystal_playable`
- no-network execution validation

Acceptance:

- Crystal can progress meaningfully with network disabled

### Phase 8: Long-Run Reliability

Goal: prove the bot can finish, not just demo.

Build:

- milestone save-state suite
- failure taxonomy and logging
- watchdog/restart policy
- speed tuning for watchable x1.5/x2 playback

Test:

- 15-20 minute autonomous sessions
- overnight or extended soak runs
- repeated checkpoint resume tests

Acceptance:

- bot clears multiple major game segments across repeated runs without supervision

### Phase 9: Full MT-53 Expansion

Goal: only after Crystal MVP is real.

Build:

- post-game Crystal objectives
- practical dex completion rules
- personality/naming polish
- Emerald support
- ROM hack support
- cross-run self-learning and optimization

Acceptance:

- Crystal MVP already proven
- Emerald added without regressing Crystal

## Immediate Next Build Queue

This is the correct order for the next MT-53 sessions:

1. Crystal navigator and warp data
2. deterministic menu utility engine
3. early-game milestone harnesses
4. Gen 2 battle/catch hardening
5. story progression state machine
6. offline brain replacement

## What CCA Already Planned Well

- the ambition and final target in `MASTER_TASKS.md`
- the research basis in `RESEARCH.md`
- the emulator pivot to mGBA
- the "steal code" directive
- the general module decomposition

## What Was Missing Until Now

- a current definition of done
- a separation between Crystal MVP and Full MT-53
- a capability matrix
- dependency-ordered milestones
- milestone acceptance tests
- an explicit path from "Gemini prototype works" to "zero-token standalone bot"

## Rule For Future MT-53 Work

Every future MT-53 session should answer these four questions before coding:

1. Which phase in this document is being worked?
2. What acceptance test will prove the phase advanced?
3. Is this for Crystal MVP or only for Full MT-53 later?
4. Does this reduce dependence on runtime LLM calls, or only improve the prototype?
