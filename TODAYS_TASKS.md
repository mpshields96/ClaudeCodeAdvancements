# CCA Tasks — 2026-03-30 (Updated S238)
# Source: S234-S238 unified plan. Matthew approved in S235, refined in S238.
# Read by ALL subsequent CCA chats. This is the ONLY task authority.

---

## PHASE 1: COMPLETED (S236-S238)

Tasks A-E from the original S235 plan. All investigation/research/build work done.
Chats 1-3 executed as planned. See "Completion Archive" at bottom for details.

| Task | Session | Status | Output |
|------|---------|--------|--------|
| A. Cache Bug Mitigations | S236 | DONE | .zshrc env vars set, findings documented |
| B. /cca-wrap Token Audit | S236 | DONE | Step 6g removed (~3K saved), 4 proposals documented |
| C. Rate Limits Statusline | S236 | DONE | Already configured via cship — no changes needed |
| D. Prism/TurboQuant Research | S237 | DONE | Research doc: memory-system/research/PRISM_TURBOQUANT_RESEARCH.md |
| E. Loop Detection Guard | S238 | DONE | agent-guard/loop_detector.py + hooks/loop_guard.py, 40 tests, hook wired |

### Uncommitted work from Phase 1 (must be committed in Chat 4):
- S236: .claude/commands/cca-wrap.md (Step 6g removal) — modified but never committed
- S237: memory-system/research/PRISM_TURBOQUANT_RESEARCH.md — untracked, never committed
- S236 findings in this file — never committed as standalone commit

---

## PHASE 2: BUILD + HARDEN (Chats 4-7)

Everything below builds on Phase 1 research. Ordered by ROI: token savings first,
then workflow improvements, then learning/evaluation.

---

### CHAT 4: Cleanup + Env Verification + Dream Design (~45 min)

Four tasks. Do them in order 4A-4D.

#### 4A. Commit Phase 1 Uncommitted Work [DONE S239]
**Scope:** Git hygiene — commit everything Phase 1 left behind.
**Steps:**
1. `git add .claude/commands/cca-wrap.md` — S236 wrap quick win
2. `git add memory-system/research/PRISM_TURBOQUANT_RESEARCH.md` — S237 research
3. Commit with message referencing S236+S237 work
**STOP CONDITION:** One clean commit. Move to 4B.

#### 4B. Verify Environment Variables Are Active [DONE S239 — set in .zshrc, takes effect next launch]
**Scope:** Confirm S236 cache mitigations are live in this session.
**Steps:**
1. Run `echo $ENABLE_TOOL_SEARCH` — should be `false` (not `auto`)
2. Run `echo $CLAUDE_CODE_DISABLE_1M_CONTEXT` — should be `1`
3. If either is wrong: `source ~/.zshrc` or note that it takes effect on next launch
4. Confirm loop guard state file exists: `ls ~/.claude-loop-detector.json`
**STOP CONDITION:** Both vars confirmed or documented as "next launch." Move to 4C.

#### 4C. Smoke Test Loop Guard in Real Usage [DONE S239 — fires correctly on 3+ similar outputs, no false positives]
**Scope:** Validate the loop guard actually fires when it should.
**Steps:**
1. Run 4 identical bash commands (e.g., `echo "test loop"` four times)
2. Check if the hook outputs a LOOP DETECTED warning after the 4th
3. If no warning: check `~/.claude-loop-detector.json` to see if state is accumulating
4. If hook isn't firing: verify settings.local.json has the PostToolUse entry
**STOP CONDITION:** Guard fires correctly OR issue identified and logged. Move to 4D.

#### 4D. Task F: Auto Dream Integration Design [DONE S239 — memory-system/DREAM_INTEGRATION_DESIGN.md]
**Scope:** SHORT design note — 1 page max. No code.
**Context:** `/dream` is Anthropic's native memory consolidation (runs at session end,
writes learnings to CLAUDE.md). CCA's Frontier 1 memory system must complement, not compete.
**Steps:**
1. Read `/dream` docs (official CC docs or test it once to see what it produces)
2. Answer: What does CCA memory do that /dream doesn't?
   - Structured types with TTL/confidence scoring
   - Cross-session FTS5 search
   - Auto-capture from hooks (not just session-end)
   - Typed categories (user, feedback, project, reference)
3. Answer: What does /dream do that CCA memory doesn't?
   - Native integration (survives compaction, auto-loaded)
   - Zero configuration
   - Anthropic maintains it
4. Write `DREAM_INTEGRATION_DESIGN.md` in memory-system/ — 1 page, clear separation
**STOP CONDITION:** Design note written and committed. Do NOT build anything.
**Reference:** FINDINGS_LOG entry #11 (Auto Dream pivot), D research doc

---

### CHAT 5: Wrap/Init Token Optimization Build (~60 min)

The highest-ROI build remaining. Every token saved here compounds across every future session.

#### 5A. Build batch_wrap_analysis.py [DONE S240]
**Scope:** Consolidate wrap Steps 6b-6h into a single Python script.
**Context:** Currently 7 separate optional steps, each with its own bash call and
context overhead in the wrap command. A single script runs reflect, escalate, validate,
and evolve in one subprocess call.
**Steps:**
1. Read current Steps 6b-6h in .claude/commands/cca-wrap.md
2. Build `batch_wrap_analysis.py` that runs all 7 analyses and outputs combined results
3. Write tests
4. Replace Steps 6b-6h in cca-wrap.md with single `python3 batch_wrap_analysis.py` call
**Expected savings:** ~5,000 tokens per wrap (7 bash blocks → 1)
**STOP CONDITION:** Script works, tests pass, wrap command updated. Move to 5B.

#### 5B. Trim Wrap Command to Slim-Only [DONE S240]
**Scope:** Move verbose documentation out of the command file into a reference doc.
**Steps:**
1. Create `WRAP_REFERENCE.md` with full step explanations (the "why" behind each step)
2. Reduce cca-wrap.md to code blocks + one-line descriptions only
3. Remove full-mode instructions (SLIM covers 90% of wraps; full mode in reference only)
4. Target: 600 lines → ~250 lines (~1,650 tokens saved on every wrap load)
**STOP CONDITION:** Wrap command is leaner, reference doc has the details, wrap still works.

#### 5C. Conditional Cross-Chat Step [DONE S240]
**Scope:** Make Step 7.5 (cross-chat coordination) skip if no Kalshi-relevant work.
**Steps:**
1. Add check: if session touched no Kalshi-related files/topics, skip the cross-chat write
2. ~5 LOC conditional
**STOP CONDITION:** Implemented and tested.

**Chat 5 target:** Wrap cost drops from ~20K to ~12K tokens (40% reduction).

---

### CHAT 6: Claude Code Guide Study + Paseo Evaluation (~45 min)

Two evaluation/learning tasks that pair well — neither produces CCA code.

#### 6A. Claude-Howto Best Practices Study [TODO]
**Scope:** Read shanraisshan/claude-code-best-practice repo (25K+ stars, 10 modules).
This is Matthew's personal learning resource — CCA reads it and produces a gap analysis.
**Steps:**
1. Read the repo's module index / table of contents
2. For each module: summarize what it teaches vs what CCA already does
3. Flag any gaps — things the guide covers that we DON'T do yet
4. Prioritize the CLAUDE.md layering section, hooks deep-dive, and MCP server setup
5. Write a short `CLAUDE_HOWTO_GAP_ANALYSIS.md` — what to focus on, what to skip
**STOP CONDITION:** Gap analysis written. Do NOT implement anything from it in this chat.
**Reference:** FINDINGS_LOG entry #5, entry #72. github.com/shanraisshan/claude-code-best-practice

#### 6B. Task G: Paseo Evaluation [TODO]
**Scope:** Install, test, and evaluate Paseo for mobile Claude Code access.
**Steps:**
1. Clone getpaseo/paseo repo
2. Read architecture docs — understand daemon + WebSocket model
3. Install and run locally
4. Test: can you connect to a running CC session from a second device?
5. Evaluate: latency, reliability, security (E2EE?), mobile UX
6. Write verdict: ADOPT / DEFER / SKIP with reasoning
**STOP CONDITION:** Verdict written. Adopt only if it works reliably.
**Reference:** FINDINGS_LOG entry #67 (Paseo review)

---

### CHAT 7: Mistake-Learning Build + Kalshi Port (~60 min)

#### 7A. Mistake-Learning Pattern from Prism (Task D follow-up) [TODO]
**Scope:** Build auto-capture of error corrections into self-learning journal.
**Context:** Prism MCP's mistake-learning pattern: when an agent makes an error and
then corrects it, the correction is auto-captured and resurfaced as a warning in future
sessions. This turns reactive debugging into proactive prevention.
**Steps:**
1. Design: detect error→correction sequences in tool output
2. Build: capture module that writes corrections to self-learning/journal.jsonl
3. Integration: PostToolUse or Stop hook that identifies the pattern
4. Tests
**STOP CONDITION:** Working capture + tests. Resurfacing is a separate enhancement.
**Reference:** S237 research doc (PRISM_TURBOQUANT_RESEARCH.md), FINDINGS_LOG entry #39

#### 7B. Port Improvements to Kalshi Project [TODO]
**Scope:** Apply CCA workflow improvements to polymarket-bot project.
**Steps:**
1. Add loop guard hook to Kalshi project's settings (settings.local.json or project settings)
2. Verify env vars (ENABLE_TOOL_SEARCH, DISABLE_1M_CONTEXT) apply to Kalshi sessions
3. Apply any wrap optimizations built in Chat 5 that are project-agnostic
4. Write CCA_TO_POLYBOT.md delivery noting all changes
**STOP CONDITION:** Kalshi project has parity with CCA's workflow improvements.

---

## STANDING TASKS (all chats)

### Cross-Chat Coordination
- Check POLYBOT_TO_CCA.md at start of every chat
- Write CCA_TO_POLYBOT.md deliveries as findings warrant
- Lopez de Prado AFML delivery already written (S234)

### CLI Migration Status
- Phase 1 (CCA): DONE S227
- Phase 2 (Codex): PENDING — not today's priority
- Phase 3 (Kalshi): PENDING — not today's priority

### Loop Guard Validation (passive — all autonomous sessions)
- Loop guard is wired as PostToolUse hook in ~/.claude/settings.local.json
- Monitor for false positives or missed loops across Chats 4-7
- If threshold needs tuning, adjust CLAUDE_LOOP_THRESHOLD env var (default: 0.80)

---

## DEFERRED (not scheduled, revisit when relevant)

- **TurboQuant vector compression** — only when Frontier 1 hits storage scale problems
- **Computer use monitoring** — token costs catastrophic, revisit when Anthropic stabilizes pricing
- **cc2codex** — LLM diversification tool, revisit if needed
- **Octopoda shared knowledge spaces** — MT-21 hivemind enhancement, after basic hivemind is proven
- **Loop guard v2 (embeddings)** — only if v1 string similarity proves insufficient

---

## COMPLETION ARCHIVE (Phase 1, S236-S238)

S234: 10 Reddit posts reviewed, cache bugs PSA found, 2 memories created, Kalshi AFML delivery
S235: 11 Reddit posts reviewed (21 total), unified plan created, this file updated
S236: Cache bug investigation + wrap audit + statusline check. Findings documented. Quick win (Step 6g removal) implemented.
S237: TurboQuant + Prism MCP research complete. Written to memory-system/research/PRISM_TURBOQUANT_RESEARCH.md
S238: Loop Detection Guard v1 built. agent-guard/loop_detector.py + hooks/loop_guard.py. 40 tests. Hook wired globally.

---

## SESSION RULES (Matthew directive, S178 — still active)
- **THIS FILE IS AUTHORITATIVE.** All CCA sessions work on TODO items here until complete.
- Do NOT use priority_picker or MASTER_TASKS until ALL TODOs here are done.
- Kalshi bot tasks: deliver via CCA_TO_POLYBOT.md, don't implement in polybot directly.
- Mark items [DONE SN] as they complete, but NEVER remove them.
- Each subsequent CCA chat reads THIS FILE FIRST to know what to work on.
- Matthew updates this file daily — follow it, don't second-guess it.
- **STOP CONDITIONS are boundaries, not suggestions.** When a stop condition is hit, MOVE ON.
- **Do NOT engage in autoloop or autowork unless Matthew explicitly requests it.**
