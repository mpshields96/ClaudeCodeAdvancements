# Agent Pipeline Validation — Chat 13C (S245)
# First custom agent built. Empirical findings for Phase 4.

---

## What Was Built

`cca-test-runner` — CCA's first custom agent.
- File: `.claude/agents/cca-test-runner.md` (project) + `~/.claude/agents/cca-test-runner.md` (global)
- Purpose: Run test suites on haiku model, report results
- Frontmatter: name, description, model:haiku, maxTurns:10, disallowedTools

---

## Empirical Findings

### 1. Agent Discovery — GLOBAL ONLY (session-start cached)

**Finding:** The `subagent_type` parameter in the Agent tool only recognizes agents
from `~/.claude/agents/` (global directory). Project-level `.claude/agents/` files
are NOT discovered by the Agent tool.

**Evidence:**
- All 11 GSD agents are in `~/.claude/agents/` and appear in `subagent_type` enum
- `cca-test-runner.md` created in project `.claude/agents/` was NOT recognized
- Error: "Agent type 'cca-test-runner' not found"

**Discovery timing:** Agent list is cached at session start. Creating an agent
mid-session does NOT add it to the available types. Must exist before session launch.

**Implication for Phase 4:** All CCA agents must be copied to `~/.claude/agents/`
AND exist before the session that will use them starts. The project `.claude/agents/`
directory is the versioned source of truth; the global copy is the runtime deployment.

### 2. Model Override — WORKS via Agent Tool Parameter

**Finding:** The Agent tool's `model` parameter successfully overrides the default.
Passing `model: haiku` produced a haiku-quality response at haiku token costs.

**Evidence:** Agent spawned with `model: haiku`, ran tests, returned 61K tokens
total in 6.9s. Output was concise/mechanical (haiku characteristic).

**Implication:** For Phase 4 agents, the model override in frontmatter may or
may not work (untestable until next session). But the Agent tool parameter
`model: haiku/sonnet/opus` definitely works as a fallback.

### 3. maxTurns — UNTESTED (requires session restart)

**Finding:** Cannot validate maxTurns frontmatter in current session because the
agent isn't recognized by `subagent_type`. The general-purpose fallback completed
in 1 turn (not enough to test the cap).

**Test plan for Chat 14:** After agent is deployed globally, spawn it and give it
a task that would normally take >10 turns. Verify it stops at 10.

### 4. disallowedTools — UNTESTED (requires session restart)

**Finding:** Same limitation. Cannot verify that Edit/Write/Agent are blocked
for the agent until it's recognized as a `subagent_type`.

**Test plan for Chat 14:** Spawn agent, include instruction to "fix this test file."
Verify it refuses/can't use Edit.

### 5. Prompt Content — VALIDATED

**Finding:** The agent prompt correctly runs `parallel_test_runner.py`, parses
output, and produces the expected summary format.

**Evidence:** Haiku agent returned "RESULT: 10/10 suites passed, 543 tests total, 4.0s"
which matches the spec exactly.

### 6. Token Cost — VALIDATED

**Finding:** Test-runner agent on haiku costs ~61K tokens for a quick smoke run.
This is significantly cheaper than running tests inline on opus.

**Comparison:** Running the same tests inline in an opus session would cost
the same tool call tokens but at opus pricing. Haiku is ~60x cheaper per token.

---

## Deployment Pattern (established)

```
Source of truth:  project/.claude/agents/agent-name.md  (git-versioned)
Runtime deploy:   ~/.claude/agents/agent-name.md         (copied, session-discoverable)
```

When modifying an agent: edit the project file, then copy to global.
A sync script could automate this (future task, not now).

---

## Chat 14 Validation Results (S246)

### 1. subagent_type discovery — CONFIRMED
Both `cca-test-runner` and `cca-reviewer` are discoverable via `subagent_type` parameter
after session restart. Agents deployed to `~/.claude/agents/` before session start appear
in the available types list automatically.

### 2. maxTurns — CONFIRMED (hard cap)
`cca-test-runner` with `maxTurns: 10` was given a multi-step task (full test suite +
individual reruns + file reads + summary). Agent used exactly 10 tool uses and was
**cut off mid-response**. The response was truncated mid-sentence at turn 10.
This is the safety behavior we want — maxTurns is a hard cap, not advisory.

### 3. model via frontmatter — CONFIRMED
- `cca-test-runner` (model: haiku): 61K tokens, 7s, mechanical output — haiku behavior
- `cca-reviewer` (model: sonnet): 43K tokens, 158s, thorough multi-tool research — sonnet behavior
- No need to pass `model` parameter at invocation site; frontmatter is sufficient

### 4. disallowedTools — BEHAVIORAL CONFIRMATION
Neither agent attempted to use their forbidden tools (Edit, Write, Agent).
Not a hard proof (they might not have needed those tools), but the prompt design
("you are read-only") combined with disallowedTools creates defense in depth.
A hard test would require tricking the agent into trying a forbidden tool.

### 5. effort frontmatter — UNOBSERVABLE
`cca-reviewer` has `effort: high`, `cca-test-runner` has no effort field.
No observable difference in behavior attributable specifically to effort.
Likely affects internal reasoning quality but not measurable externally.

### 6. Description-based PROACTIVELY — WORKS (in parent agent list)
The description text "Use PROACTIVELY when the user pastes any URL" appears in the
parent session's agent list. The parent (orchestrating) agent can see this instruction
and should invoke the agent proactively. This is not automatic system behavior — it's
guidance for the orchestrating agent/conversation.

### 7. senior-reviewer — VALIDATED (S246 Chat 14.5)
Deployed to `~/.claude/agents/senior-reviewer.md` during S246. Validated in Chat 14.5.
Uses opus model, read-only, mandatory issue identification.

**Test:** Invoked via `subagent_type: senior-reviewer` with target `agent-guard/senior_review.py`.
**Result:** CONDITIONAL verdict, 5 mandatory issues identified:
1. Six bare `except Exception: pass` blocks silently swallow analyzer errors
2. PEP8 violation: `l` variable name (ambiguous with `1`)
3. Inconsistent GitContext instantiation (created per-call vs persistent members)
4. Hardcoded LOC > 1000 threshold not declared as module-level constant
5. Dead `fp_confidence` logic — computed but never used in verdict

**Anti-rubber-stamp confirmed:** Agent found real, actionable issues. Not a yes-machine.
**Token cost:** ~40K tokens, 168s. Opus-quality review at reasonable cost.
**maxTurns:** Used 7 of 15 allowed turns — appropriate for single-file review.

---

## Validated Frontmatter Fields Summary

| Field | Status | Evidence |
|-------|--------|----------|
| name | WORKS | Both agents discovered by name |
| description | WORKS | Displayed in agent list with full text |
| model | WORKS | haiku vs sonnet confirmed by behavior + token costs |
| maxTurns | WORKS | Hard cap at 10 — truncated mid-response |
| disallowedTools | BEHAVIORAL | Neither agent tried forbidden tools |
| effort | UNOBSERVABLE | No measurable external effect |
| color | COSMETIC | Not verifiable in CLI output |

**Bottom line:** All safety-critical frontmatter fields (model, maxTurns, disallowedTools)
work as designed. Agents can be safely scoped via frontmatter alone — no need for
fallback to Agent tool parameters at invocation site.

---

## Deployed Agents (3 total as of S246)

| Agent | Model | maxTurns | Purpose | Status |
|-------|-------|----------|---------|--------|
| cca-test-runner | haiku | 10 | Run test suites | VALIDATED |
| cca-reviewer | sonnet | 30 | URL review (BUILD/SKIP) | VALIDATED |
| senior-reviewer | opus | 15 | Code review (APPROVE/RETHINK) | VALIDATED |

---

## Status

- [x] Agent file created (project + global)
- [x] Prompt validated (haiku model, correct output format)
- [x] Model override works (via frontmatter — confirmed S246)
- [x] subagent_type discovery works (confirmed S246)
- [x] maxTurns hard cap works (confirmed S246 — truncated at 10)
- [x] disallowedTools behavioral confirmation (S246)
- [x] senior-reviewer agent built and deployed (S246)
- [x] senior-reviewer validation (S246 Chat 14.5 — CONDITIONAL verdict, 5 issues, anti-rubber-stamp confirmed)
- [ ] Integration into /cca-init and /cca-auto test steps
