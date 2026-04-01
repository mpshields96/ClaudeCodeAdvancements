# Custom Agent Design for CCA — Chat 11B (S244)
# Design doc for CCA's first custom agents using CC's native agent system.
# Stop condition: Design written. Do NOT create agents yet — that's Phase 4.

---

## Current State

CCA has 33 slash commands and 0 custom agents. All work runs inline in the main
context window. GSD has 11 agents but uses only 4 of 16 available frontmatter fields
(name, description, tools, color). CCA can do better by using the full frontmatter spec.

---

## Agent vs Command Decision Matrix

**Use an agent when:**
- Task is self-contained (clear input, clear output)
- Task benefits from its own context window (prevents main context pollution)
- Task can be scoped down (restricted tools, capped turns)
- Task runs autonomously without needing main conversation state

**Keep as a command when:**
- Task needs interactive dialogue with the user
- Task must read/write shared state files (SESSION_STATE, PROJECT_INDEX)
- Task modifies the session environment (hooks, settings)
- Task coordinates other tasks (orchestrator role)

---

## Candidate Evaluation

### 1. `/cca-review` -> `cca-reviewer` agent: BUILD

**Why agent:** Self-contained research task. Takes a URL, returns a verdict.
Does not need main context. Currently 132 lines that run in-context, polluting
the main window with Reddit comment trees and analysis scaffolding.

**Frontmatter:**
```yaml
---
name: cca-reviewer
description: Review URLs against CCA's five frontiers. Use PROACTIVELY when the user pastes any URL.
tools: Read, Bash, Grep, Glob, WebFetch, WebSearch
disallowedTools: Edit, Write
model: sonnet
maxTurns: 30
effort: high
color: cyan
---
```

**Prompt body:** Condensed version of current cca-review.md Steps 1-5.
Include the 5 frontiers, rat poison checklist, and verdict format (BUILD/ADAPT/REFERENCE/SKIP).
Reference `reddit_reader.py` path for Reddit URLs.

**Benefits:**
- Separate context window: Reddit comment trees don't pollute main session
- Sonnet model: cheaper than Opus for research tasks (no code generation needed)
- maxTurns 30: prevents runaway on massive Reddit threads
- disallowedTools: can't accidentally edit CCA files during review
- PROACTIVELY in description: auto-invokes when user pastes a URL

**Estimated savings:** ~3-5K tokens per review (context isolation)

---

### 2. `/senior-review` -> `senior-reviewer` agent: BUILD

**Why agent:** Analysis task with clear input (file path) and output (verdict).
Benefits from effort:high for deeper reasoning. Should NOT be able to modify
the file it's reviewing (adversarial reviewer pattern).

**Frontmatter:**
```yaml
---
name: senior-reviewer
description: Senior developer code review. Use PROACTIVELY after significant code changes.
tools: Read, Grep, Glob, Bash
disallowedTools: Edit, Write, Agent
model: opus
maxTurns: 15
effort: high
color: magenta
---
```

**Prompt body:** Condensed senior-review.md. Structured verdict format
(APPROVE / CONDITIONAL / RETHINK). Focus areas: correctness, edge cases,
security, maintainability, test coverage.

**Benefits:**
- Read-only: can't modify the code it reviews (rubber-stamp prevention)
- Opus model: quality matters for review (catches subtle bugs)
- maxTurns 15: reviews should not be open-ended
- No Agent tool: reviewer can't spawn sub-agents (cost control)

**Key insight from 10 Principles research:** Making the reviewer unable to
fix issues forces it to clearly articulate what's wrong — better feedback.

---

### 3. `/cca-scout` -> `cca-scout` agent: BUILD

**Why agent:** Heavy web scraping task. Pulls 50+ Reddit posts, filters,
analyzes. Massive context window pollution if run inline.

**Frontmatter:**
```yaml
---
name: cca-scout
description: Scan subreddits for high-signal posts relevant to CCA frontiers.
tools: Read, Bash, Grep, Glob, WebFetch
disallowedTools: Edit, Write, Agent
model: sonnet
maxTurns: 40
effort: medium
color: green
---
```

**Prompt body:** Steps 1-4 from current cca-scout.md. Subreddit list,
filtering criteria, signal scoring. Output: ranked list of posts with
one-line verdicts.

**Benefits:**
- Sonnet: cheap for bulk scanning
- maxTurns 40: needs room for 3 subreddits x 50 posts
- Read-only: scout reports findings, doesn't modify CCA files
- Main context stays clean for the session's real work

---

### 4. `/cca-nuclear` -> KEEP AS COMMAND

**Why command:** 334-line orchestrator that coordinates multiple URL reviews,
writes to FINDINGS_LOG.md, manages session state. It spawns work, it doesn't
do the work itself. With cca-reviewer as an agent, /cca-nuclear becomes a
thin command that dispatches reviews to the agent and collects results.

**Pattern:** Command -> Agent orchestration.
`/cca-nuclear` (command, coordinates) -> `cca-reviewer` (agent, per-URL review)

---

### 5. `/cca-wrap` -> KEEP AS COMMAND

**Why command:** Interactive, state-modifying, session-scoped. Needs to update
SESSION_STATE.md, PROJECT_INDEX.md, commit code, write resume prompts. Cannot
be isolated in a separate context.

---

### 6. `/cca-init` -> KEEP AS COMMAND

**Why command:** Same as wrap — modifies session state, runs diagnostics,
produces briefing that the main context needs to see.

---

### 7. `/cca-report` -> `cca-reporter` agent: MAYBE (Phase 5+)

**Why maybe:** Report generation is self-contained but needs Write access
to create the output file. Could work with isolation:worktree. Lower priority
than the three BUILD candidates above.

---

## New Agent Candidates (not from existing commands)

### 8. `cca-test-runner` agent: BUILD

**Why new agent:** Dedicated test execution agent. Runs tests in separate
context, reports results. Useful for /cca-auto test cycles.

**Frontmatter:**
```yaml
---
name: cca-test-runner
description: Run CCA test suites and report results. Use when tests need to be run.
tools: Read, Bash, Grep, Glob
disallowedTools: Edit, Write, Agent, WebFetch, WebSearch
model: haiku
maxTurns: 10
effort: low
color: yellow
---
```

**Benefits:**
- Haiku model: tests don't need intelligence, just execution
- maxTurns 10: run tests, report, done
- Cheapest possible agent for a routine task

---

### 9. `cca-findings-writer` agent: DEFER

Not worth the overhead. Writing to FINDINGS_LOG.md is a quick append that
should stay in the main context.

---

## Implementation Priority

| Priority | Agent | Model | Estimated Build Time |
|----------|-------|-------|---------------------|
| 1 | cca-reviewer | sonnet | ~30 min (condense cca-review.md) |
| 2 | senior-reviewer | opus | ~20 min (condense senior-review.md) |
| 3 | cca-scout | sonnet | ~25 min (condense cca-scout.md) |
| 4 | cca-test-runner | haiku | ~15 min (new, simple) |

**Total: ~90 min across 1-2 Phase 4 chats.**

---

## Frontmatter Best Practices (from 11A findings)

1. **Always set maxTurns.** No agent should run unbounded. Default caps:
   - Research/review: 15-30 turns
   - Scanning/scraping: 30-40 turns
   - Testing: 5-10 turns

2. **Always set model explicitly.** Don't inherit — be intentional about cost:
   - Opus: quality-critical (senior review, architecture analysis)
   - Sonnet: research/scanning (good enough, 5x cheaper)
   - Haiku: mechanical tasks (test running, formatting, grep)

3. **Use disallowedTools for safety scoping.** Read-only agents should not have
   Edit/Write. Research agents should not have Agent (prevents recursive spawning).

4. **Use PROACTIVELY in description** for agents that should auto-invoke
   (reviewer when URL pasted, test-runner after code changes).

5. **Set effort per task type:**
   - high/max: reviews, analysis, architecture
   - medium: research, scanning
   - low: test execution, formatting

6. **Consider skills: field** for domain knowledge preloading. E.g., the
   senior-reviewer agent could have `skills: senior-review` to preload
   review criteria without stuffing the prompt.

---

## Command -> Agent Migration Pattern

For each BUILD candidate:
1. Create `.claude/agents/agent-name.md` with full frontmatter
2. Condense the existing command's logic into the agent prompt body
3. Convert the existing command into a thin orchestrator:
   - Parse user input
   - Spawn the agent with `Agent` tool
   - Format and display results
4. Test: verify agent produces same quality output as old command
5. Keep old command as backup until agent is proven over 3+ sessions

This is the Module 9 pattern: Command (lightweight, user-facing) -> Agent (isolated, specialized).
