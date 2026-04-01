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

## What Chat 14 Must Validate

1. [ ] `subagent_type: cca-test-runner` works after session restart
2. [ ] maxTurns:10 actually caps execution
3. [ ] disallowedTools prevents Write/Edit/Agent access
4. [ ] model:haiku in frontmatter works (vs only Agent tool parameter)
5. [ ] effort:low in frontmatter has observable effect
6. [ ] Description-based auto-invocation (PROACTIVELY trigger) works

If frontmatter fields 2-5 don't work, fallback is Agent tool parameters only.
This changes the cca-reviewer and senior-reviewer designs (can't rely on
frontmatter for safety scoping — must use tool parameters at invocation site).

---

## Status

- [x] Agent file created (project + global)
- [x] Prompt validated (haiku model, correct output format)
- [x] Model override works (via Agent tool parameter)
- [ ] Full frontmatter validation (needs session restart)
- [ ] Integration into /cca-init and /cca-auto test steps
