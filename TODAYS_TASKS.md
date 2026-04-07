# CCA Tasks — 2026-03-30 (Updated S241, Chat 7)
# Source: S234-S241 unified plan. Phases 1-2 complete. Phase 3 planned in S241 Chat 7.
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

#### 6A. Claude-Howto Best Practices Study [DONE S241]
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

#### 6B. Task G: Paseo Evaluation [DONE S241 — DEFER verdict]
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

#### 7A. Mistake-Learning Pattern from Prism (Task D follow-up) [DONE S241]
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

#### 7B. Port Improvements to Kalshi Project [DONE S241]
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

## PHASE 3: COMPLETE THE PATTERNS + HARDEN (Chats 8-11)

Phase 1 found problems (reddit research). Phase 2 built first fixes. Phase 3 completes
the patterns and hardens the infrastructure. Each task closes a loop that Phase 1-2 opened.

**Evidence chain:**
- Correction capture (7A) built capture-only → need resurfacing to complete the pattern
- Gap analysis (6A) found 18 unused hooks, 11 unused subagent fields → pick highest ROI
- Prism research (S237) recommended Ebbinghaus decay → replace crude TTL cliffs
- Multiple sessions documented compaction state loss → PreCompact/PostCompact hooks

**Key reference documents:**
- `CLAUDE_HOWTO_GAP_ANALYSIS.md` — hook events, subagent fields, orchestration pattern
- `memory-system/research/PRISM_TURBOQUANT_RESEARCH.md` — Ebbinghaus decay, correction patterns
- `memory-system/DREAM_INTEGRATION_DESIGN.md` — how CCA memory layers on AutoDream

---

### CHAT 8: Correction Resurfacing + PostToolUseFailure (~45 min) — DONE S241

Complete the Prism mistake-learning pattern. Chat 7 built capture. Chat 8 builds resurfacing.

#### 8A. Correction Resurfacing at Session Init [DONE S241]
**Scope:** Query recent corrections from journal.jsonl and surface them as warnings.
**Delivered:** Added `get_recent_corrections()`, `format_correction_warnings()`,
`format_correction_briefing()` to `self-learning/resurfacer.py`. Groups by
(error_pattern, error_tool), sorts by frequency, shows relative time + avg fix time.
CLI: `python3 self-learning/resurfacer.py corrections [--days N] [--json]`
34 new tests in `test_correction_resurfacer.py`.

#### 8B. Wire PostToolUseFailure Hook [DONE S241]
**Scope:** Add PostToolUseFailure as a cleaner error signal for correction_detector.
**Delivered:** Confirmed PostToolUseFailure exists (25 hook events documented in
claude-howto/06-hooks). Built `self-learning/hooks/failure_capture.py` — feeds
failures to CorrectionDetector buffer (so correction_capture.py detects the fix)
and logs directly to journal as `error` events. 11 new tests in `test_failure_capture.py`.
Wired in `~/.claude/settings.local.json` as PostToolUseFailure hook (global).

#### 8C. Cross-Chat Delivery [DONE S241 — not needed]
**Scope:** PostToolUseFailure hook is global (settings.local.json), Kalshi gets it
automatically. No separate delivery required.

---

### CHAT 9: Memory Decay + Init Integration (~45 min)

Two tasks: principled memory decay function, and wiring the correction resurfacer
into /cca-init so warnings appear automatically at session start.

#### 9A. Ebbinghaus Decay for Memory Confidence [DONE S242]
**Scope:** Replace hard TTL cutoffs with continuous exponential decay.
**Context:** CCA memory uses cliff-edge TTL: HIGH=365d, MEDIUM=180d, LOW=90d.
A memory at day 89 (LOW) has full weight. At day 91 it vanishes. Prism uses
`effective = base * 0.95^days` — smooth decay where memories fade gradually.
This is more principled and avoids the cliff.
**Steps:**
1. Read memory-system/schema.md — understand current confidence/TTL model
2. Design the decay function:
   - Input: base_confidence (0-100), days_since_last_access
   - Output: effective_confidence (0-100)
   - Decay rate: configurable, default 0.95/day (Prism's value)
   - Floor: minimum effective confidence before pruning (e.g., 5)
3. Build `memory-system/decay.py`:
   - `compute_effective_confidence(base, days, decay_rate=0.95)` → float
   - `should_prune(base, days, floor=5)` → bool
   - `get_decay_rate_for_confidence(level)` → float
     (HIGH decays slower than LOW — e.g., HIGH=0.98, MEDIUM=0.96, LOW=0.93)
4. Write tests — verify decay curves, edge cases (0 days, negative days, very old)
5. Do NOT integrate into the memory system yet — this is the function only.
   Integration requires schema changes (adding `last_accessed_at` field).
**STOP CONDITION:** decay.py + tests. Integration is a future task.
**Reference:** PRISM_TURBOQUANT_RESEARCH.md Section 3B, recommendation #3
**Design note on rates:** At 0.95/day, base 100 drops to 50 in ~14 days (too
aggressive for HIGH confidence). Per-confidence rates fix this:
  - HIGH=0.98 → 50% at 34 days, effectively permanent for active memories
  - MEDIUM=0.96 → 50% at 17 days, moderate decay
  - LOW=0.93 → 50% at 10 days, fast decay for speculative memories

#### 9B. Wire Correction Resurfacer into /cca-init [DONE S242]
**Scope:** Make the capture->resurface loop fire automatically at session start.
**Context:** Chat 8 built `resurfacer.py corrections` but nothing calls it.
Without wiring into /cca-init, corrections are logged but never prevent repeat
mistakes. This is the smallest change with the highest compound value.
**Steps:**
1. Read `.claude/commands/cca-init.md` — find the session briefing output section
2. Add a step that runs `python3 self-learning/resurfacer.py corrections`
3. Display output in the session briefing (only if there are corrections to show)
4. Test: manually run the command, verify output format looks right in context
5. Also consider adding to /cca-auto and /cca-desktop if they have init sections
**Expected output in init briefing:**
```
Recent corrections (last 7 days):
  - Edit: old_string not found — (3x) — avg fix: 12s — 2h ago
  - Bash: command not found — (2x) — avg fix: 8s — 1d ago
```
**STOP CONDITION:** /cca-init displays recent corrections. Verified manually.

#### 9C. Cross-Chat Delivery [DONE S242 — skipped, CCA-internal only]
**Scope:** Write CCA_TO_POLYBOT.md if applicable (likely minimal — 9A/9B are CCA-internal).
**STOP CONDITION:** Delivery written or skipped.

---

### CHAT 10: Compaction Protection Hooks (~60 min)

**Goal:** Protect critical session state through context compaction events.
Both PreCompact and PostCompact hooks are confirmed available (claude-howto/06-hooks,
25 hook events). PreCompact receives matcher `manual/auto` (tells you why compaction
fired). Neither can block. This is a design-then-build chat.

#### 10A. Design Compaction Protection Protocol [DONE S243]
**Scope:** Define exactly what state to preserve through compaction events.
**Steps:**
1. Read `CLAUDE_HOWTO_GAP_ANALYSIS.md` Module 8 — hook event details
2. Read `references/claude-howto/06-hooks/README.md` — PreCompact/PostCompact payload
3. Determine what data the hooks receive on stdin:
   - PreCompact: likely `{"hook_event_name": "PreCompact", "matcher": "auto"}`
   - PostCompact: likely `{"hook_event_name": "PostCompact"}`
   - Key question: does PreCompact get any conversation metadata (turn count,
     token usage, recent tool calls)? Or just the trigger type?
4. Design the protocol based on what data is actually available:
   - **What to save (PreCompact):**
     a. Session progress markers from `~/.claude-context-health.json` (if exists)
     b. List of files modified this session (from git status)
     c. Current working task description (parse from recent conversation if available)
     d. Timestamp + compaction trigger type (manual vs auto)
   - **Where to save:** `~/.claude-compaction-snapshot.json` (atomic write)
   - **What to restore (PostCompact):**
     a. Write snapshot content to stdout so it appears in Claude's context
     b. This works because PostCompact hook output gets injected as context
   - **What NOT to save:** Full conversation (too large), tool outputs (stale),
     file contents (can be re-read)
5. Write design: `context-monitor/COMPACTION_PROTECTION_DESIGN.md` (~1 page)
**STOP CONDITION:** Design note written. Do NOT build until design is reviewed.
**Key risk:** If PreCompact only receives the trigger type and nothing else,
the hook can only snapshot external state (git status, health file, env vars).
It cannot snapshot conversation-internal state. This is still valuable but more
limited than ideal. The design note must address this honestly.

#### 10B. Build Compaction Protection [DONE S243]
**Scope:** Implement the protocol from 10A. Only proceed if 10A confirms hooks
provide enough data to be useful.
**Steps:**
1. Build `context-monitor/hooks/pre_compact.py`:
   - Read external state (git status, context health file, env vars)
   - Write atomic snapshot to `~/.claude-compaction-snapshot.json`
   - Keep it fast (<1s) — compaction shouldn't be delayed by the hook
2. Build `context-monitor/hooks/post_compact.py`:
   - Read snapshot file
   - Output concise summary to stdout (injected as post-compaction context)
   - Format: "Pre-compaction state: working on [task], modified [files], [N]% context used"
3. Wire both in settings.local.json
4. Write tests:
   - Snapshot write/read round-trip
   - Missing snapshot file (graceful degradation)
   - Malformed snapshot (don't crash)
   - Output format validation
5. Manual validation: trigger compaction in a test session, verify restore
**STOP CONDITION:** Hooks wired and tested, or documented as insufficient.
**Fallback:** If PreCompact data is too limited, consider a periodic snapshot
approach instead (save state every N tool calls via PostToolUse, not tied to
compaction events). Document this as an alternative in the design note.

#### 10C. Cross-Chat Delivery [DONE S243]
**Scope:** Port compaction protection to Kalshi if hooks prove useful.
Compaction protection is project-agnostic — if it works for CCA, it works
for Kalshi. Wire globally in settings.local.json (same as loop guard).
**STOP CONDITION:** Delivery written or skipped.

---

### CHAT 11: Architecture Study + Custom Agent Design + Phase 4 Planning (~60 min)

Research + evaluation session. Output is design notes and Phase 4 plan, not code.
Each exploration task is time-boxed to prevent rabbit holes.

#### 11A. Hands-On CC Feature Exploration [DONE S244] (~15 min, hard cap)
**Scope:** Try features from gap analysis we've never used. Quick pass — try each
once, note if useful, move on.
**Steps:**
1. `--bare` mode: `claude -p --bare "hello"` — measure startup time vs normal.
   Useful for CCA scripts that shell out to `claude -p` (batch operations).
   Time both: `time claude -p --bare "echo test"` vs `time claude -p "echo test"`
2. `/btw` side query — does it preserve main context? Start a session, establish
   context, then `/btw "unrelated question"`. Check if original context survives.
3. `--max-turns` flag: `claude -p --max-turns 3 "task"` — does it hard-cap?
   This would replace our reliance on maxTurns frontmatter for agent limiting.
4. Skip `/batch` and `context: fork` for now — lower priority, save for Phase 4.
**Deliverable:** 5-line findings per feature in `CC_FEATURE_NOTES.md`. No analysis
paralysis — "useful / not useful / needs more testing" is sufficient.
**STOP CONDITION:** 3 features tried, findings noted. 15 minutes max. Move on.

#### 11B. Custom Agent Design for CCA [DONE S244] (~20 min)
**Scope:** Design CCA's first custom agents as `.claude/agents/*.md` files.
This is where the deferred subagent frontmatter hardening (original 9B) lands.
**Context:** Chat 8 confirmed CCA has zero custom agents — all 32 commands are
inline slash commands. The claude-howto Module 4 subagent spec shows agents get:
`maxTurns`, `effort`, `disallowedTools`, `skills`, `model`, `permissionMode`.
**Steps:**
1. Identify which CCA workflows would benefit from being agents vs commands:
   - `/cca-review` → agent candidate (research task, could be scoped + capped)
   - `/senior-review` → agent candidate (analysis, benefits from effort:high)
   - `/cca-scout` → agent candidate (web search heavy, can be restricted)
   - `/cca-wrap` → stays as command (needs full tool access, interactive)
2. For each agent candidate, draft the frontmatter:
   ```yaml
   ---
   name: cca-reviewer
   description: Review URLs against CCA frontiers
   model: sonnet
   maxTurns: 25
   effort: high
   disallowedTools: Write(~/.claude/*), Edit(~/.claude/*)
   skills: cca-review
   ---
   ```
3. Evaluate: is splitting command -> agent actually better for each case?
   Criteria: Does it save tokens? Does it prevent runaway? Does it improve quality?
4. Write design in `CUSTOM_AGENTS_DESIGN.md` — which ones to build, which to skip
**STOP CONDITION:** Design note written. Do NOT create agents yet — that's Phase 4.
**Deferred from 9B:** This is the proper home for subagent frontmatter hardening.
The original 9B tried to add frontmatter to commands (wrong target). This task
correctly designs custom agents from scratch with proper frontmatter.

#### 11C. Native Agent Teams vs Hivemind Evaluation [DONE S244] (~15 min)
**Scope:** Compare Anthropic's native agent teams with our cca_comm.py hivemind.
**Steps:**
1. Check if native agent teams are available:
   `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude --help 2>&1 | grep -i team`
2. If available: read the docs (references/claude-howto/10-cli/ or Module 10).
   Key questions to answer:
   - How do agents share state? (shared task list vs our JSONL queue)
   - Can agents have different models? (we use Opus desktop + Sonnet worker)
   - Can they run in separate terminals? (our current pattern)
   - What coordination overhead does the native approach add?
3. If NOT available or too experimental: document this and evaluate based on docs only
4. Write verdict: ADOPT (replace hivemind) / COMPLEMENT (use alongside) / SKIP
   with specific reasoning for each criterion above
**STOP CONDITION:** Verdict written. This informs MT-21 direction.
**Time-box:** 15 minutes. If agent teams are too experimental to test, write the
verdict from docs alone and move on. Don't burn the session on setup issues.

#### 11D. Write Phase 4 Plan [DONE S244] (~10 min)
**Scope:** Based on Chats 8-11 findings, write Phase 4 task list into this file.
**Steps:**
1. Review what Chats 8-11 delivered vs deferred:
   - Chat 8: capture->resurface loop complete, PostToolUseFailure wired
   - Chat 9: decay function built, resurfacer wired into init
   - Chat 10: compaction protection (built or documented as limited)
   - Chat 11: feature notes, agent design, agent teams verdict
2. Identify Phase 4 candidates from:
   - Deferred items from Phase 3 (anything that didn't fit)
   - Custom agent creation (from 11B design)
   - Memory decay integration (from 9A — function built, schema change needed)
   - SessionStart/SessionEnd hooks (automate init/wrap)
   - Compaction protection v2 (if v1 was limited)
   - Any new gaps discovered during Chats 8-11
3. Write Phase 4 plan following same format (per-chat tasks with stop conditions)
4. Also update DEFERRED section with anything newly deferred
**STOP CONDITION:** Phase 4 plan written. This file is ready for the next cycle.

---

### CHAT 12: CC Source Study + GitHub Scan + CLAUDE.md Audit (~60 min)

**Goal:** Leverage the CC source leak for concrete improvements. Clone the actual
TypeScript source (not the Python port), study key subsystems, scan GitHub for
high-quality community analysis, and audit our CLAUDE.md token count.

**CRITICAL:** The instructkr/claude-code repo cloned in S242 is a Python REWRITE,
NOT the leaked TypeScript source. The actual source was distributed via:
- R2 zip: pub-aea8527898604c1bbb12468b1581d95e.r2.dev/src.zip (from original tweet)
- GitHub mirrors mentioned in r/ClaudeAI 2088-pt post comments
Find and clone the REAL TypeScript source. Verify by checking for .ts/.tsx files
and the compact.ts file specifically.

#### 12A. Clone Actual CC TypeScript Source [DONE S245]
**Scope:** Find and clone the real leaked source (TypeScript, ~1884 files).
**Steps:**
1. Check the GitHub links from FINDINGS_LOG entries (2026-03-31 leak posts)
2. Look for repos with actual .ts/.tsx files, not Python ports
3. Clone to references/claude-code-ts/ (separate from the Python port)
4. Verify: `find references/claude-code-ts/ -name "*.ts" | wc -l` should be ~1884
5. Verify compact.ts exists: `find references/claude-code-ts/ -name "compact.ts"`
**STOP CONDITION:** Real TypeScript source cloned and verified. If unavailable (DMCA'd),
document and proceed with the Python port's JSON snapshots instead.

#### 12B. Study Coordinator Mode + UDS Inbox [DONE S245] (~20 min)
**Scope:** Read the actual Coordinator Mode and UDS Inbox implementation.
**Steps:**
1. Read coordinator/coordinatorMode.ts — how workers spawn, communicate, report
2. Read any UDS (Unix Domain Socket) inbox implementation
3. Compare with cca_comm.py: what does native CC do that we built manually?
4. Write findings: `COORDINATOR_MODE_ANALYSIS.md` (~1 page)
5. Verdict: does this replace cca_comm.py? Partial replace? Complement?
**STOP CONDITION:** Analysis written. This directly informs MT-21 direction.

#### 12C. Study Compaction Implementation [DONE S245] (~15 min)
**Scope:** Read the actual compact.ts to understand the bug we're working around.
**Steps:**
1. Find and read services/compact/compact.ts
2. Confirm the empty-array diff bug (line ~565 per Reddit analysis)
3. Read what preCompactDiscoveredTools contains
4. Document: what can our PostCompact hook realistically restore?
**STOP CONDITION:** Compaction internals documented. Feeds Chat 10 design.

#### 12D. CLAUDE.md Token Audit [DONE S245] (~10 min)
**Scope:** Measure our CLAUDE.md against Boris Cherny's <1000 token advice.
**Steps:**
1. Count tokens in our project CLAUDE.md: `wc -w CLAUDE.md` (rough: words * 1.3)
2. Count tokens in global ~/.claude/CLAUDE.md
3. Identify what can move to subdirectory CLAUDE.md files (only loaded when relevant)
4. Write reduction plan — target <1000 tokens for root CLAUDE.md
**STOP CONDITION:** Audit complete with reduction plan. Don't implement yet.

#### 12E. GitHub Scan — Leak Derivatives [DONE S245] (~15 min, time-boxed)
**Scope:** Quick scan of GitHub trending for high-quality CC source analysis.
**Steps:**
1. Search GitHub for repos created since 2026-03-30 mentioning "claude code source"
2. Filter: >50 stars, not just forks with no changes
3. Look for: analysis tools, feature extractors, community patches, documentation
4. Apply rat poison filter: no sketchy packages, no credential harvesters
5. Log any BUILD/ADAPT findings to FINDINGS_LOG.md
**STOP CONDITION:** 15 min max. Log findings. Don't get lost in rabbit holes.

---

### CHAT 13: Compressed Research + First Agent Build (~60 min)

**Goal:** PIVOT from research to building. Last research chat in this cycle.
Compress remaining research into quick verdicts, then build the simplest custom
agent as proof-of-concept. This validates the entire agent pipeline before Chat 14
builds the harder agents.

**Strategic context (S245 analysis):**
- Chats 9-12 were 4 consecutive research-heavy sessions. Only Chat 10 produced running code.
- Research was necessary (can't build agents without studying frontmatter fields, can't design
  context monitors without understanding compaction) but 4 straight research chats is the limit.
- Chat 13 is the last with ANY pure research. After this, it's building until agents are running.
- The 4 custom agents designed in CUSTOM_AGENTS_DESIGN.md are the biggest deliverable from
  all this research. Building them proves the research was worth the investment.

#### 13A. 10 Principles Article Series [DONE S245] (~15 min)
**Scope:** Read jdforsythe.github.io/10-principles. Focus on the 4 principles most
relevant to CCA's upcoming agent builds.
**Steps:**
1. Fetch the article series
2. Focus on: PRISM identities (<50 tokens), 45% multi-agent threshold,
   rubber-stamp prevention, lost-in-middle context management
3. Write `AGENTIC_WORKFLOW_RESEARCH.md` — short (1-2 pages), actionable gaps only
**STOP CONDITION:** Research doc written. 15 min max. Move on.

#### 13B. Evaluate Forge + jig + contexto [DONE S245] (~10 min TOTAL, batched)
**Scope:** Quick BUILD/SKIP verdicts for all three tools in one pass. NOT deep dives.
**Steps:**
1. For each tool: read README, check star count, assess overlap with CCA tooling
2. Forge (agent assembly) — does it offer anything our .claude/agents/ design doesn't?
3. jig (context loading) — does it beat slim_init.py?
4. contexto (context pruning) — complementary or redundant with context-monitor?
5. Write 3-line verdict per tool in FINDINGS_LOG.md (not separate analysis docs)
**STOP CONDITION:** 3 verdicts logged. 10 min max. Don't clone any repos.

#### 13C. Build `cca-test-runner` Agent [DONE S245] (~25 min)
**Scope:** Build CCA's FIRST custom agent. The simplest one: haiku model, maxTurns 10,
runs tests and reports results. This validates the entire agent pipeline.
**Why this one first:**
- Simplest frontmatter (haiku, maxTurns:10, only needs Bash+Read)
- Immediately useful (every session runs tests — offloading saves opus tokens)
- Validates: does maxTurns work? Does model override work? Does disallowedTools work?
- If this works, Chat 14 can confidently build cca-reviewer and senior-reviewer
**Steps:**
1. Read CUSTOM_AGENTS_DESIGN.md for the cca-test-runner spec
2. Create `.claude/agents/cca-test-runner.md` with frontmatter:
   ```yaml
   ---
   name: cca-test-runner
   description: Run CCA test suite and report results
   model: haiku
   maxTurns: 10
   disallowedTools: Write, Edit, Agent
   ---
   ```
3. Write agent prompt body: run parallel_test_runner.py, parse output, report
   pass/fail with failure details. ~30 lines.
4. Test: spawn it manually with Agent tool, verify it runs tests and returns
5. Validate frontmatter: does maxTurns actually cap it? Does haiku model activate?
6. Document any frontmatter fields that don't work as expected
**STOP CONDITION:** Agent runs tests successfully. Frontmatter validated.
**Deliverable:** `.claude/agents/cca-test-runner.md` + validation notes

#### 13D. Cross-Chat Delivery [DONE S245]
**Scope:** Write CCA_TO_POLYBOT.md if research findings are Kalshi-relevant.
Also deliver the custom agent pattern — Kalshi could use a similar test-runner agent.
**STOP CONDITION:** Delivery written or skipped.

#### 13E. Process Any Reddit Posts from Matthew [DEFERRED — next session with cca-reviewer agent]
**Scope:** If Matthew feeds additional Reddit posts, review them with /cca-review.
Only do this AFTER 13A-13D are complete. Do not let new research derail the build.
**STOP CONDITION:** Posts reviewed or skipped if no time.

---

## PHASE 4: NATIVE AGENT SYSTEM + INTEGRATION (Chats 14-17)

Phase 3 researched and designed. Phase 4 builds and integrates. The key deliverables
are CCA's first custom agents (from 11B design) and integration of Phase 3 components.

**Evidence chain:**
- Chat 11B designed 4 custom agents with full frontmatter specs (CUSTOM_AGENTS_DESIGN.md)
- Chat 11C confirmed COMPLEMENT verdict: keep hivemind + add Agent Teams layer
- Chat 12B studied actual Coordinator Mode source — cca_comm.py covers ~40% of CC's functionality.
  Key gaps: typed messages, idle notifications, plan approval workflow, scratchpad.
- Chat 12C studied actual compact.ts — empty-array diff is INTENTIONAL (full re-announcement).
  preCompactDiscoveredTools preserves deferred tool schemas. Auto-compact triggers at ~98%.
- Chat 12D audited CLAUDE.md — 11.4K tokens loaded per session (11.4x Boris target).
  Reduction plan written: 58% savings achievable (Tier 1 quick wins + Tier 2 restructure).
- Chat 13C builds first agent (cca-test-runner) to validate pipeline before Phase 4.
- Chat 9A built Ebbinghaus decay function but did NOT integrate into memory system
- Chat 10 built compaction protection v1

**Key reference documents:**
- `CUSTOM_AGENTS_DESIGN.md` — 4 agents designed, frontmatter specs, migration pattern
- `AGENT_TEAMS_VS_HIVEMIND.md` — COMPLEMENT verdict, hybrid architecture
- `COORDINATOR_MODE_ANALYSIS.md` — NEW (S245): 3-layer transport, 10+ structured message types, CCA comparison
- `COMPACTION_ANALYSIS.md` — NEW (S245): full pipeline, PTL recovery, cache sharing, file restoration budgets
- `CLAUDE_MD_TOKEN_AUDIT.md` — NEW (S245): 11.4K tokens, 58% reduction plan
- `CC_SOURCE_DERIVATIVES.md` — NEW (S245): 10 repos/blogs mapped to CCA frontiers
- `CC_FEATURE_NOTES.md` — 16 frontmatter fields, --bare for tooling
- `memory-system/decay.py` — Ebbinghaus decay function (built, not integrated)
- `context-monitor/hooks/pre_compact.py` — Compaction protection v1

---

### CHAT 14: Build Custom Agents (Priority 1-2) (~60 min)

First two agents from the CUSTOM_AGENTS_DESIGN.md priority list.

#### 14A. Build `cca-reviewer` Agent [DONE S245 — pulled forward to Chat 13]
**Scope:** Convert /cca-review command into Command -> Agent pattern.
**Steps:**
1. Create `.claude/agents/cca-reviewer.md` with frontmatter from CUSTOM_AGENTS_DESIGN.md
2. Condense cca-review.md Steps 1-5 into agent prompt body (~80 lines max)
3. Convert cca-review.md into thin orchestrator that spawns the agent
4. Test: review a Reddit URL, compare output quality vs old command
5. Keep old command logic as backup comment block until proven (3+ sessions)
**STOP CONDITION:** Agent works, produces BUILD/SKIP verdicts. Old command still functional.

#### 14B. Build `senior-reviewer` Agent [DONE S246]
**Scope:** Convert /senior-review into read-only agent.
**Steps:**
1. Create `.claude/agents/senior-reviewer.md` with frontmatter from CUSTOM_AGENTS_DESIGN.md
2. Key: disallowedTools: Edit, Write, Agent — reviewer cannot modify code
3. Condense senior-review.md into agent prompt body
4. Test: review a recently modified file, verify APPROVE/CONDITIONAL/RETHINK verdict
**STOP CONDITION:** Agent works, produces structured verdicts. Cannot edit files.

#### 14C. Validate Agent Frontmatter Fields [DONE S246]
**Scope:** Verify that maxTurns, effort, disallowedTools actually work as documented.
**Steps:**
1. Test maxTurns: spawn cca-reviewer with maxTurns: 3, verify it stops
2. Test effort: compare output quality at effort:low vs effort:high
3. Test disallowedTools: verify senior-reviewer cannot Write
4. Document any fields that don't work as expected
**STOP CONDITION:** Frontmatter validation documented. Fix any broken configs.

### CHAT 14.5: Clone Repos + Validate Senior-Reviewer + Cache Audit (~20 min)

Matthew's explicit directives — urgent repo preservation + validation.

#### 14.5A. Clone claw-code Repo [DONE S246]
**Scope:** Preserve instructkr/claw-code locally before potential DMCA takedown.
Cloned to `references/claw-code/`. Not committed to CCA git (gitignored).

#### 14.5B. Clone claude-code-source-build Repo [DONE S246]
**Scope:** Preserve andrew-kramer-inno/claude-code-source-build locally.
Cloned to `references/claude-code-source-build/`. Not committed to CCA git (gitignored).

#### 14.5C. Validate senior-reviewer Agent [DONE S246]
**Result:** CONDITIONAL verdict, 5 issues found (silent exception swallowing, PEP8 `l` var,
inconsistent GitContext, hardcoded LOC threshold, dead fp_confidence). Anti-rubber-stamp confirmed.
40K tokens, 168s. Documented in AGENT_PIPELINE_VALIDATION.md.

#### 14.5D. Cache Audit Diagnostic [DONE S246]
**Result:** Cache read ratios 68-99% across recent sessions. db8 bug NOT active. No action needed.

#### 14.5E. Update TODAYS_TASKS.md [DONE S246]

#### 14.5F. Steal CLAUDE.md Rules from Reddit Review #4 [DONE S246]
Added to CLAUDE.md Architecture Principles: redundant-read guard + tool-call budget awareness (~15 call cap for simple tasks).

---

### CHAT 15: Build Custom Agents (Priority 3-4) + Memory Decay Integration (~60 min)

#### 15A. Build `cca-scout` Agent [DONE S247]
**Scope:** Convert /cca-scout into agent with sonnet model + maxTurns cap.
**Steps:**
1. Create `.claude/agents/cca-scout.md` with frontmatter from CUSTOM_AGENTS_DESIGN.md
2. Condense cca-scout.md into agent prompt body
3. Convert cca-scout.md into thin orchestrator
4. Test: run a subreddit scan, verify output quality
**STOP CONDITION:** Agent works, produces ranked post lists.

#### 15B. Harden `cca-test-runner` Agent + Build Remaining Agents [DONE S247]
**Scope:** If Chat 13C built cca-test-runner successfully, harden it based on real usage.
If 13C revealed frontmatter issues, fix them here. Then build any remaining agents
from CUSTOM_AGENTS_DESIGN.md not yet built (cca-scout if not done in 15A).
**Steps:**
1. Review 13C validation notes — any frontmatter fields that didn't work?
2. Fix any issues discovered (maxTurns not capping, model not switching, etc.)
3. If time: build additional utility agents from CUSTOM_AGENTS_DESIGN.md
**STOP CONDITION:** All 4 agents from CUSTOM_AGENTS_DESIGN.md built and tested.

#### 15C. Integrate Ebbinghaus Decay into Memory System [DONE S247]
**Scope:** Wire the decay function (9A) into actual memory queries.
**Context:** decay.py exists with compute_effective_confidence() but nothing calls it.
Integration requires adding `last_accessed_at` field to memory schema and calling
decay during memory retrieval.
**Steps:**
1. Update memory-system/schema.md — add `last_accessed_at` field
2. Update memory query path to call compute_effective_confidence()
3. Update memory access to refresh last_accessed_at timestamp
4. Tests for integration (decay during query, timestamp updates)
**STOP CONDITION:** Memory queries return decayed confidence scores.

---

### CHAT 16: /cca-nuclear Agent Teams Integration + Hook Automation (~60 min)

#### 16A. Wire Agent Teams into /cca-nuclear [DONE S249]
**Scope:** Use Agent Teams for parallel URL reviews within /cca-nuclear sessions.
**Context:** 11C COMPLEMENT verdict: Agent Teams for intra-session parallelism.
/cca-nuclear currently reviews URLs sequentially. With Agent Teams, it can spawn
multiple cca-reviewer agents in parallel.
**Steps:**
1. Add CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 to settings (if not already)
2. Modify cca-nuclear.md to spawn parallel reviewers for batches of 3-5 URLs
3. Test: run a nuclear scan, verify parallel reviews complete correctly
4. Measure: time for 10 reviews (sequential vs parallel)
**STOP CONDITION:** Nuclear scans use parallel reviews. Fallback to sequential if teams fail.
**Risk:** Agent Teams is experimental — must have graceful fallback.

#### 16B. SessionStart Hook for Auto-Init [DONE S249]
**Scope:** Move some /cca-init diagnostics into a SessionStart hook.
**Context:** Gap analysis (6A) identified SessionStart as unused. Could automate
parts of init (smoke test check, pacer reset, timer start) without the full command.
**Steps:**
1. Build `hooks/session_start.py` — lightweight session startup
2. Auto-run: smoke test cache check, pacer reset, timer start
3. Wire in settings.local.json as SessionStart hook
4. Test: start a new session, verify hook fires
**STOP CONDITION:** Hook fires reliably. Does NOT replace /cca-init — just pre-warms.

#### 16C. SubagentStart Hook for Spawn Budget [DONE S249]
**Scope:** Track and optionally limit agent spawns during peak hours.
**Context:** Peak hours (8AM-2PM ET) should minimize agent spawns (40-50% budget).
SubagentStart hook can count spawns and warn/block during peak.
**Steps:**
1. Build `hooks/subagent_budget.py` — count spawns, check time window
2. During peak: warn after 3 spawns, soft-block after 5
3. During off-peak: no limit (log only)
4. Tests
**STOP CONDITION:** Hook wired and tested. Warn-only mode initially.

---

### CHAT 17: Context Overhead Reduction (~45 min)
# REPLANNED from S249: Original Chat 17 tasks moved to Chat 18 (see below)
# Goal: Cut the ~55KB of system context loading every session by ~45%
# This directly addresses the 44%-in-3-prompts rate limit burn problem

#### 17A. MEMORY.md Prune [DONE S250 — 18391→7215 bytes (-61%)]
**Scope:** MEMORY.md is 18KB injected as system-reminder on EVERY turn (not cached).
Cutting it 50% saves ~9KB per message for the rest of every session.
**Steps:**
1. Git commit before touching anything
2. Read all 173 lines of MEMORY.md
3. Remove: expired time-sensitive entries (2x promo, CC march features),
   superseded project states (S77/S86/S94 audit notes), redundant feedback pairs,
   obvious entries already covered by CLAUDE.md
4. Target: 173 → ~80 lines
5. Verify nothing critical lost — read the pruned version before committing
**STOP CONDITION:** MEMORY.md under 90 lines. Git-committed. Reversible.

#### 17B. titanium-field-names.md Scope Fix [DONE S250 — moved to polymarket-bot/.claude/rules/]
**Scope:** Kalshi-specific field names file is in ~/.claude/rules/ (global),
loading in every CCA session. Move to polymarket-bot/.claude/rules/ instead.
**Steps:**
1. Copy to polymarket-bot/.claude/rules/titanium-field-names.md
2. Verify Kalshi session still loads it (check polymarket-bot/.claude/ exists)
3. Delete from ~/.claude/rules/
**STOP CONDITION:** File loads for Kalshi, silent for CCA. ~52 lines removed globally.

#### 17C. COMMANDS.md Split [DONE S250 — COMMANDS-CORE.md created, 6933→2690 bytes global load]
**Scope:** 6.9KB of all-project command tables loads everywhere. CCA only needs
CCA commands. Create a lean core version for the global @import.
**Steps:**
1. Create ~/.claude/COMMANDS-CORE.md — CCA section only + one-liner refs to others
2. Update ~/.claude/CLAUDE.md to @COMMANDS-CORE.md instead of @COMMANDS.md
3. Keep full COMMANDS.md intact as reference (don't delete)
**STOP CONDITION:** Global load is lean CCA-focused version. Full table still accessible.

#### 17D. mandatory-skills + gsd-framework Merge [DONE S250 — gsd-framework.md deleted, unique content merged]
**Scope:** Two overlapping files (194 lines, ~7KB) both define gsd:quick vs plan-phase.
gsd-framework.md restates ~40% of mandatory-skills-workflow.md.
**Steps:**
1. Read both side-by-side
2. Fold unique content from gsd-framework.md into mandatory-skills-workflow.md
3. Delete gsd-framework.md
4. Verify no unique directives lost
**STOP CONDITION:** Single file covers both. ~50 lines removed from global load.
**CAUTION:** Global rules — affects Kalshi chats too. Review carefully.

---

### CHAT 18: Original Chat 17 Tasks (Deferred from S249)

#### 18A. Compaction Protection v2 [DONE S250 — critical rules injection, 94 tests pass]
(was 17A) Enhance PreCompact/PostCompact. Detect context drops >30%, re-inject
critical rules. Read context-monitor/session_pacer.py first.

#### 18B. Cross-Chat Delivery — Phase 3+4 Results [DONE S250 — UPDATE 6 written to CCA_TO_POLYBOT.md]
(was 17B) Write CCA_TO_POLYBOT.md delivery: loop guard, session pacer,
custom agent pattern, Ebbinghaus decay. 4 items, mark PENDING.

#### 18C. Write Phase 5 Plan [DONE S250 — Chats 19-21 plan written: 19A cca-reviewer, 19B hook chain, 20A registry, 20B cost dashboard, 21A tool budget, 21B cca-scout]
(was 17C) Read CUSTOM_AGENTS_DESIGN.md + CLAW_CODE_ARCHITECTURE_NOTES.md,
write Phase 5 plan (production hardening + monitoring), update TODAYS_TASKS.

---

## PHASE 5: PRODUCTION HARDENING + MONITORING (Chats 19-21)
# Source: S250 Chat 17 — CUSTOM_AGENTS_DESIGN.md + CLAW_CODE_ARCHITECTURE_NOTES.md
# Goal: Harden Phases 3-4 infrastructure, build highest-priority remaining agent,
#       add monitoring for agent cost + quality, implement CLAW_CODE budget pattern.

---

### CHAT 19: cca-reviewer Agent Build (Highest ROI remaining agent)

#### 19A. Build cca-reviewer Agent [DONE S250 — agent exists, cca-review.md thin wrapper, CLAUDE.md auto-trigger updated]
**Scope:** Convert /cca-review command into isolated cca-reviewer agent. Biggest remaining
agent build from CUSTOM_AGENTS_DESIGN.md. Sonnet model, read-only, maxTurns 30.
**Context:** Phase 4 proved the agent pattern. cca-reviewer is the highest-priority
remaining candidate: self-contained research task, currently pollutes main context
with Reddit comment trees and analysis scaffolding.
**Steps:**
1. Create `~/.claude/agents/cca-reviewer.md` using the frontmatter from CUSTOM_AGENTS_DESIGN.md §1
2. Condense current `cca-review.md` into the agent prompt body (5 frontiers, verdict format, rat poison)
3. Update `/cca-nuclear` to delegate single-URL reviews to the agent instead of inline
4. Test: 3 URLs reviewed via agent — verify same verdict quality as command
5. Keep original cca-review.md as fallback until 3 session validation passes
**STOP CONDITION:** Agent produces BUILD/SKIP verdicts on 3 URLs. /cca-nuclear uses it.

#### 19B. Hook Chain Integration Test [DONE S250 — 27 tests: session_start, spawn_budget, pre/post compact chain, state isolation]
**Scope:** Validate that SessionStart → spawn budget → compaction v2 hooks work together
without conflicts. Unit tests pass but interaction hasn't been integration-tested.
**Steps:**
1. Write `tests/test_hook_chain_agents.py` — mock a session with all 3 hooks active
2. Test: spawn budget hook fires before SessionStart hook (order matters)
3. Test: compaction snapshot includes spawn budget state
4. Verify: hooks don't double-write to the same state files
**STOP CONDITION:** Integration test covers hook chain. 100% pass rate.

---

### CHAT 20: Agent Registry + Cost Monitoring

#### 20A. Agent Registry (CLAW_CODE Pattern) [DONE S250 — agent_registry.py + 33 tests pass]
**Scope:** Implement uniform agent discovery from CLAW_CODE_ARCHITECTURE_NOTES.md §3.
All CCA agents should be discoverable via a single registry, not scattered across ~/.claude/agents/.
**Steps:**
1. Create `agent-guard/agent_registry.py` — lists all CCA agents with metadata
2. Registry reads ~/.claude/agents/*.md and parses frontmatter (name, model, maxTurns)
3. CLI: `python3 agent_registry.py list` → table of agents with cost tier
4. Add registry check to /cca-init briefing (show count of active agents)
**STOP CONDITION:** Registry lists all agents, init shows count.

#### 20B. Agent Cost Dashboard [DONE S250 — agent_cost_reader.py + 41 tests pass]
**Scope:** The spawn budget hook logs agent invocations. Build a reader that shows
aggregate costs, success rates, and token usage per agent type.
**Steps:**
1. Check what spawn budget hook writes (check hooks/spawn_budget.py output format)
2. Write `agent-guard/agent_cost_reader.py` — reads the log, aggregates by agent name
3. Output: per-agent totals (invocations, tokens, estimated cost)
4. Wire to /cca-init briefing: show if any agent is unexpectedly expensive
**STOP CONDITION:** cost_reader shows per-agent breakdown. Reads real spawn data.

---

### CHAT 21: Tool-Call Budget Hook + cca-scout Agent

#### 21A. Tool-Call Budget Hook (CLAW_CODE Pattern) [DONE S250 — tool_budget.py + 38 tests, wired in settings.local.json PreToolUse]
**Scope:** Implement programmatic max_budget_tokens from CLAW_CODE_ARCHITECTURE_NOTES.md §2.
PreToolUse hook that counts cumulative tool calls this session and warns at threshold.
**Steps:**
1. Create `context-monitor/hooks/tool_budget.py` — PreToolUse hook, counts calls per session
2. State file: `~/.claude-tool-budget.json` — session_id + call_count + warnings_issued
3. Thresholds: warn at 15 calls, BLOCK at 30 (configurable via env vars)
4. Write 10 tests. Wire as PreToolUse hook.
**STOP CONDITION:** Hook warns at threshold. 10 tests pass.

#### 21B. cca-scout Agent Build [DONE S250 — cca-nuclear-daily uses scout agent, CLAUDE.md updated with cca-scout section]
**Scope:** Convert /cca-scout into isolated cca-scout agent. Third priority from
CUSTOM_AGENTS_DESIGN.md. Sonnet model, read-only, maxTurns 40.
**Context:** Scout scans 50+ Reddit posts — heavy context pollution if run inline.
Moving to agent isolates scanning context from main session.
**Steps:**
1. Create `~/.claude/agents/cca-scout.md` with frontmatter from CUSTOM_AGENTS_DESIGN.md §3
2. Condense cca-scout.md into agent prompt body (subreddit list, signal scoring, output format)
3. Verify: agent runs independently, writes findings to console (not to FINDINGS_LOG directly)
4. /cca-nuclear-daily: update to spawn scout agent instead of running inline
**STOP CONDITION:** Scout agent scans 1 subreddit via agent invocation. Results returned to caller.

---

## PHASE 6: Kalshi Bot CCA-Parity Port (Chats 22-25)
# Goal: Bring polymarket-bot up to CCA optimization level — hooks, slim init/wrap,
# session infrastructure, then get bot operational. Ordered by dependency.

### CHAT 22: Hook Chain Port

#### 22A. Wire CCA hooks into polymarket-bot settings.local.json [DONE S250 — 7 hooks wired, python3.13, all smoke-tested]
**Scope:** Zero-code configuration — point polymarket-bot at CCA's already-built hooks.
Missing: compaction protection, context meter, context alert, tool budget, memory capture.
**Steps:**
1. Add PostToolUse: meter.py, compact_anchor.py (context health + compaction anchor)
2. Add PreToolUse: alert.py, tool_budget.py (alongside existing peak_budget)
3. Add PreCompact: pre_compact.py + PostCompact: post_compact.py (critical rules injection)
4. Add Stop: auto_handoff.py (handoff at 80%+ context)
5. Smoke test: echo '{"session_id":"test","tool_name":"Write","tool_input":{}}' | python3 <hook> for each new hook
6. Commit
**STOP CONDITION:** All hooks exit 0 on dummy payload. settings.local.json committed.

#### 22B. Extract font rules + standing directives into rules files [DONE S250 — font-rules.md + standing-directives.md, stripped from 3 command files]
**Scope:** Dedup content currently hardcoded in polybot-init.md AND polybot-auto.md AND polybot-wrap.md.
Font rules and standing directives appear 3x across commands — move to .claude/rules/ where they load once.
**Steps:**
1. Create `polymarket-bot/.claude/rules/font-rules.md` — RULE 1 (no markdown tables) + RULE 2 (no dollar signs)
2. Create `polymarket-bot/.claude/rules/standing-directives.md` — bypass permissions, autonomy rules, budget, model
3. Strip font rules + standing directives sections from polybot-init.md, polybot-auto.md, polybot-wrap.md
4. Verify: rules still load via .claude/rules/ auto-include
**STOP CONDITION:** 3 command files trimmed. 2 rules files created.

---

### CHAT 23: Slim polybot-init.md

#### 23A. Extract session prompts from polybot-init.md [DONE]
**Scope:** The MAIN CHAT PROMPT and RESEARCH CHAT PROMPT blocks are the biggest waste — ~250 lines
of stale state embedded in the command file, re-parsed on every init invocation.
Extract to SESSION_RESUME.md (written by wrap, read by init at runtime).
**Steps:**
1. Create `polymarket-bot/SESSION_RESUME.md` template (written by polybot-wrap, read by polybot-init)
2. Gut polybot-init.md MAIN CHAT PROMPT section — replace with: `Read SESSION_RESUME.md`
3. Gut polybot-init.md RESEARCH CHAT PROMPT section — replace with: `Read SESSION_RESUME.md (research section)`
4. Update polybot-wrap.md Step 3C: write to SESSION_RESUME.md instead of regenerating into polybot-init.md
5. Update polybot-init.md CURRENT STATE section: `Read SESSION_HANDOFF.md` (already reads it anyway)
**TARGET:** polybot-init.md 15.4KB → ~4KB
**STOP CONDITION:** polybot-init.md under 5KB. polybot-wrap writes to SESSION_RESUME.md correctly.

#### 23B. Slim polybot-init.md structure [DONE]
**Scope:** After 23A extractions, compress remaining static content.
**Steps:**
1. Merge STEP 3 (announce state) and STEP 4 (route to work) — they're 2 lines of logic, not 2 sections
2. Collapse SELF-IMPROVEMENT CHAIN ACTIVE block — this is runtime state, belongs in SESSION_HANDOFF
3. Add CRITICAL PATH header (like CCA wrap) — Steps 1-3 mandatory, rest optional
**TARGET:** Under 4KB total
**STOP CONDITION:** polybot-init.md under 4KB. Test by starting a mock session.

---

### CHAT 24: Slim polybot-wrap.md + Session Infrastructure

#### 24A. Slim polybot-wrap.md [DONE]
**Scope:** Apply CCA wrap pattern — critical path + OPTIONAL tags.
**Steps:**
1. Add CRITICAL PATH block at top (Steps 1, 3A, 3B, 4, 5 — the money steps)
2. Tag non-critical steps OPTIONAL
3. Step 3C: now writes to SESSION_RESUME.md (from 23A) instead of polybot-init.md — verify
4. Remove embedded session prompt template from wrap — it moved to SESSION_RESUME.md
**TARGET:** polybot-wrap.md 7.3KB → ~4KB
**STOP CONDITION:** Wrap produces SESSION_RESUME.md. File under 4KB.

#### 24B. Adapt batch_wrap_learning.py for Kalshi domain [DONE]
**Scope:** CCA's batch_wrap_learning.py logs session learnings to self-learning journal.
Adapt for Kalshi trading domain: trading events instead of general dev events.
**Steps:**
1. Check if batch_wrap_learning.py works as-is in polymarket-bot context (it reads CCA paths)
2. Either: symlink CCA scripts + adapt domain flag, or create polybot_wrap_learning.py wrapper
3. Wire into polybot-wrap.md as Step 6 equivalent
**STOP CONDITION:** polybot-wrap runs batch learning without errors.

---

### CHAT 25: Get Bot Operational

#### 25A. Bot health check + API verification [DONE]
**Scope:** Bot has been stopped since ~March 18 (2+ weeks stale). Verify before restarting live.
**Steps:**
1. Check Kalshi API connectivity: `./venv/bin/python3 main.py --health`
2. Run strategy_analyzer.py --brief — see current strategy standings
3. Update SESSION_HANDOFF.md with current date/state
4. Run auto_guard_discovery.py — any new guards needed?
5. Paper mode test: restart bot in paper mode, verify bets evaluating correctly
**STOP CONDITION:** Bot runs in paper mode, --health clean, no blockers.

#### 25B. Live restart + SESSION_RESUME.md initialization [DONE]
**Scope:** Restart live trading with clean optimized infrastructure.
**Steps:**
1. Write fresh SESSION_RESUME.md with current P&L, guards, strategy standings
2. Restart bot live: `nohup ./venv/bin/python3 main.py --live ... &`
3. Verify first live bet cycle completes
4. Commit all infrastructure changes
**STOP CONDITION:** Bot running live, SESSION_RESUME.md current, all hooks active.

---

## PHASE 7: Kalshi Bot Full Optimization (Chats 26-30)

Goal: Eliminate remaining token waste, refresh stale state, harden comms loop.

### CHAT 26: POLYBOT_INIT.md Slim + SESSION_HANDOFF.md Refresh

#### 26A. Slim POLYBOT_INIT.md [DONE]
**Scope:** 105KB read every session = ~25K tokens burned at startup. Biggest remaining waste.
**Steps:**
1. Audit POLYBOT_INIT.md — identify static build docs vs live-status sections
2. Extract live-status content to SESSION_HANDOFF.md (already the canonical state file)
3. Strip or archive stale sections (old strategy docs, resolved incidents, outdated params)
4. Keep only: architecture overview, Iron Laws summary, key file map
**TARGET:** POLYBOT_INIT.md 105KB → ~15KB (static reference only)
**STOP CONDITION:** File under 20KB. No live-status content left in it.

#### 26B. Refresh SESSION_HANDOFF.md [DONE]
**Scope:** Last updated March 29. Stale PID (87224 → 12448), stale P&L, stale bot state.
**Steps:**
1. Update BOT STATE: PID 12448, log /tmp/polybot_session161.log, all-time +69.89 USD
2. Update strategy standings from --graduation-status output
3. Update PENDING TASKS to reflect Phase 6 completion
4. Trim any sections now covered by SESSION_RESUME.md
**TARGET:** SESSION_HANDOFF.md current + under 6KB
**STOP CONDITION:** Accurate state. No references to dead PIDs or March 18-29 sessions.

---

### CHAT 27: polybot-auto.md Deep Refresh

#### 27A. Remove stale strategy references [DONE]
**Scope:** polybot-auto.md monitoring loop and secondary tasks reference disabled strategies.
**Steps:**
1. Remove sol_drift_v1/xrp_drift_v1 graduation counters from monitoring loop SQL
2. Remove DIRECTION FILTERS section (btc/eth/sol/xrp_drift all disabled)
3. Update SECONDARY TASKS: reflect actual live strategies (expiry_sniper, daily_sniper, sports_game)
4. Update PRIME DIRECTIVE target: +125 USD → current gap (55.11 USD)
**STOP CONDITION:** No references to disabled strategies. SQL only queries active ones.

#### 27B. Wire every-3rd-cycle CCA check into monitoring loop [DONE]
**Scope:** CCA check currently only at startup. Needs mid-session wiring per coordination rules.
**Steps:**
1. Add cycle counter (write to /tmp/polybot_cycle_count.txt, increment each loop)
2. Every 3rd cycle: cat ~/.claude/cross-chat/CCA_TO_POLYBOT.md | tail -60
3. If new delivery found: implement + write to POLYBOT_TO_CCA.md
4. Every 3rd cycle: also write proactive request to POLYBOT_TO_CCA.md if CCA comms stale >48hr
**STOP CONDITION:** Loop checks CCA every 3rd cycle autonomously.

---

### CHAT 28: polybot-wrapresearch.md Slim + Retirement Notice

#### 28A. Slim polybot-wrapresearch.md [DONE]
**Scope:** Still 7.1KB. /kalshi-research is PERMANENTLY RETIRED — this command is rarely used.
**Steps:**
1. Add RETIRED notice at top: /kalshi-research permanently retired (S131). Use /polybot-wrap.
2. Apply critical-path treatment: compress Steps 1-6 to essential only
3. Remove embedded session prompt template (now in SESSION_RESUME.md)
**TARGET:** polybot-wrapresearch.md 7.1KB → ~2KB
**STOP CONDITION:** File under 2KB. Retirement notice prominent.

---

### CHAT 29: BOUNDS.md + Iron Laws Audit

#### 29A. Verify Iron Laws file:line references [DONE]
**Scope:** BOUNDS.md has 18 Iron Laws with file:line references — likely stale after Phase 6 refactoring.
**Steps:**
1. Read BOUNDS.md — extract all file:line references
2. Verify each reference still points to a real line in a real file
3. Update any stale references (files moved/renamed during Phase 6)
4. Flag any laws that reference removed code
**STOP CONDITION:** All 18 Iron Laws verified current. Stale refs updated or flagged.

---

### CHAT 30: Proactive POLYBOT_TO_CCA.md Request Wiring

#### 30A. Wire proactive request writing into polybot-auto [DONE]
**Scope:** POLYBOT_TO_CCA.md requests are never written autonomously — CCA only gets silence.
**Steps:**
1. Add proactive request trigger to polybot-auto.md: if guard accumulating losses (n>=5, WR<BE) → write request
2. Add CUSUM trigger: if CUSUM >= 3.0 → write request to CCA for investigation
3. Add stale comms trigger: if CCA_TO_POLYBOT.md last entry >48hr → write check-in request
4. Template the request format in polybot-auto.md
**STOP CONDITION:** polybot-auto autonomously writes POLYBOT_TO_CCA.md requests on trigger conditions.

---

### CHAT 31: Slim polybot-autoresearch.md (~30 min)

#### 31A. Slim polybot-autoresearch.md [DONE]
**Scope:** 21.7KB — largest command file. /kalshi-research permanently retired S131. Most content is dead.
**Steps:**
1. Read full file — identify permanent rules vs session-specific content
2. Remove embedded session prompt template block (now in SESSION_RESUME.md)
3. Remove stale session state blocks (task lists, analytics, restart commands)
4. Keep: research methodology, self-rating rubric, file update checklist, FONT RULES
5. Add RETIRED notice at top matching polybot-wrapresearch.md format
**TARGET:** 21.7KB → <5KB. Permanent reference only — session state in SESSION_HANDOFF.md.
**STOP CONDITION:** File under 5KB. Retirement notice at top. No embedded session prompts.

---

### CHAT 32: Iron Laws Regression Script (~30 min)

#### 32A. Build scripts/check_iron_laws.py [DONE]
**Scope:** BOUNDS.md line refs go stale on every refactor. Today fixed 10 manually — should be automated.
**Steps:**
1. Parse BOUNDS.md — extract all `file:line N` references (regex: `(src/\S+\.py|main\.py)\s+line\s+(\d+)`)
2. For each ref: `grep -n` the pattern described in the IL rule and verify it's within ±5 lines of stated line
3. Report CURRENT / STALE / MISSING for each Iron Law with file:line reference
4. Exit code 1 if any STALE or MISSING — safe to wire into pre-commit hook
**STOP CONDITION:** `python scripts/check_iron_laws.py` outputs CURRENT for all 18+ ILs. Exits 0.

---

### CHAT 33: polybot-wrap.md Audit + File Size Monitor (~30 min)

#### 33A. Audit and slim polybot-wrap.md [DONE]
**Scope:** 10.4KB — 3rd largest command file. Likely has accumulated stale session state.
**Steps:**
1. Read full file — identify stale session blocks (old restart commands, old pending tasks, session N refs)
2. Extract any session-specific state — redirect to SESSION_HANDOFF.md
3. Slim toward critical path only — keep: step structure, self-rating rubric, FONT RULES
**TARGET:** 10.4KB → <6KB.
**STOP CONDITION:** File under 6KB. No session-specific state embedded.

#### 33B. Wire command file size check into polybot-wrap.md [DONE]
**Scope:** Advancement tip from S253 — periodic wc -c audit catches file bloat before it accumulates.
**Steps:**
1. Add to polybot-wrap.md FINAL CHECKS section (or create one):
   `wc -c ~/.claude/commands/polybot-*.md` — flag any file that has grown >20% since last session
2. Add threshold annotations: polybot-auto.md warn@20KB, polybot-init.md warn@25KB, polybot-wrap.md warn@12KB, polybot-autoresearch.md warn@6KB (post-Chat-31)
**STOP CONDITION:** polybot-wrap.md outputs file sizes + threshold warnings at every wrap.

---

## PHASE 8: REDDIT BATCH BUILDS (S262+) — Chats 34-37

Source: S262 Reddit link dump (16 URLs reviewed). 2 BUILD verdicts + high-value ADAPTs.
All sessions: solo unless noted. Off-peak preferred. Use gsd:quick throughout.

### Progress Tracker

| Chat | Session | Status | Output |
|------|---------|--------|--------|
| 34: Unblock + Cache Expiry Hook | — | TODO | Green tests, cache expiry hook live, ENABLE_TOOL_SEARCH advisory |
| 35: /review Command + Context Monitor | — | TODO | /review slash command, 4 new advisory signals |
| 36: MT-53 Wire + Blast Radius | S265 | DONE S265 | collision_reader_crystal wired, blast_radius in agent-guard |
| 37: Memory Overhaul (mem0 patterns) | — | TODO | Semantic dedup, 3-tier scoping, FAISS backend |

---

### CHAT 34: Unblock Tests + Cache Expiry Hook (~75 min)

#### 34A. Python 3.9 Union Fix [DONE S263]

**Goal:** Restore full 223-suite test harness to green.
**Why now:** 81 suites blocked by `X | None` syntax (Python 3.9 incompatible). Unblocks clean baseline for all subsequent commits.

Steps:
1. `grep -rn "| None" --include="*.py"` across the project
2. Replace all `X | None` → `Optional[X]` with `from typing import Optional` at top of each file
3. Run `python3 parallel_test_runner.py --quick --workers 8` — confirm green
4. Commit: "fix: Python 3.9 union syntax — replace X|None with Optional[X]"

Stop condition: all 10 smoke suites green. Do not chase pre-existing failures unrelated to this fix.

#### 34B. Cache Expiry UserPromptSubmit Hook (BUILD #14) [DONE S263]

**Goal:** Block users before they unknowingly pay full input token cost after a cache expiry.
**Source finding:** r/ClaudeCode 1sd8t5u — 858-session audit, 54% of turns hit cache expiry, mechanism fully described.

Files to create/edit:
- `hooks/stop_hook_idle_writer.py` — append `{"idle_since": <unix_timestamp>}` to `~/.claude-context-health.json` on every Stop event
- `hooks/user_prompt_submit_cache_guard.py` — read `idle_since`, compute elapsed, block once if >5min with advisory: `"Cache likely expired (idle Xmin — Pro TTL=5min, Max TTL=1hr). Proceeding costs full input tokens. Resend to continue."`
- Wire both in `settings.local.json`: Stop hook → idle writer, UserPromptSubmit → cache guard

TTL constants: Pro = 300s, Max = 3600s. Detect plan tier from env var `CLAUDE_CODE_MAX_PLAN` if present; otherwise default to 300s (conservative).

Tests: idle_writer writes correct timestamp, cache_guard blocks at 301s, cache_guard passes at 299s, cache_guard passes on second send (block-once behavior), no-op if idle_since missing.

Commit after tests green.

#### 34C. ENABLE_TOOL_SEARCH Advisory [DONE S263]

**Goal:** Surface the single highest-leverage env var find from the batch (45k→15-20k context).
**Effort:** ~20 min add-on to context-monitor.

Steps:
1. In `context_monitor/pacer.py` session-start check: detect if `ENABLE_TOOL_SEARCH` env var is unset
2. If unset: emit one-time advisory to stderr: `"Advisory: ENABLE_TOOL_SEARCH not set. Setting it can reduce /context from ~45k to ~15-20k tokens. Add to .zshrc: export ENABLE_TOOL_SEARCH=1"`
3. Only emit once per session (gate on `~/.claude-context-health.json` `tool_search_advisory_shown` flag)

Tests: advisory fires when unset, suppressed when set, suppressed after first show.
Commit with 34B or separately.

---

### CHAT 35: /review Slash Command + Context Monitor Hardening (~75 min) [DONE S264]

#### 35A. Build /review Adversarial Code Review Command (BUILD #12) [DONE S264]

**Goal:** Ship a findings-only code review slash command that doesn't say LGTM when bugs exist.
**Source:** OpenAI Codex review prompt (open source, verified). Community SKILL.md spec already written.

Steps:
1. Fetch Codex prompt: `WebFetch https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/review_prompt.md`
2. Create `.claude/commands/review.md` (SKILL.md pattern):
   - YAML frontmatter: name, description, trigger (`/review`)
   - Instructions: findings-only output, no compliments, no invented issues
   - P0 (must fix before ship) / P1 (strong recommendation) / P2 (suggestion) / P3 (nitpick) tagging
   - Forced verdict block: `VERDICT: Ship / Ship with changes (list P0s) / Rethink (list P0s+P1s)`
3. Create `.claude/commands/references/review-output-format.md` — exact output structure
4. Create `.claude/commands/references/review-criteria.md` — what counts as P0 vs P3, "only flag what author would definitely fix" principle
5. Test: run `/review` on a recent `git diff HEAD~1` and confirm it finds something real

Commit: "feat: /review adversarial code review command (Codex prompt adapted)"

#### 35B. Context Monitor — 4 New Advisory Signals [DONE S264]

**Goal:** Context-monitor emits actionable advice before users hit the expensive scenarios.
**Sources:** Findings #1 (cache bust), #2 (--resume), #6 (CLAUDE.md size, 1M context).

All changes in `context_monitor/` module:

1. **Cache ratio signal** — in `pacer.py` or `context_health.py`: after each turn, compute `cache_read_tokens / (cache_read_tokens + cache_creation_tokens)`. If ratio < 0.5 on a non-first turn, write `cache_bust_detected: true` to health file and emit: `"Warning: cache hit ratio {ratio:.0%} — something may be busting the cache (--resume, CLAUDE.md change, MCP schema injection)."`

2. **--resume detection** — in session-start check: detect if CC was invoked with `--resume` flag (check `CLAUDE_CODE_RESUME` env var or equivalent). If set: emit `"Note: session started with --resume. Caching is disabled — every turn re-transmits full context."` before first tool call.

3. **CLAUDE.md size warning** — in session-start check: `os.path.getsize(CLAUDE_MD_PATH)`. If >3072 bytes (3KB): emit `"Advisory: CLAUDE.md is {size}KB. It re-sends on every interaction. Consider progressive disclosure (file references, not @includes)."` One-time per session.

4. **CLAUDE_CODE_DISABLE_1M_CONTEXT recommendation** — add to red/critical zone output: `"Tip: set CLAUDE_CODE_DISABLE_1M_CONTEXT=1 to force 200k context window (reduces cache expiry risk and per-token cost on uncached turns)."`

Tests: one test per signal covering fire and no-fire conditions.
Commit after all tests green.

---

### CHAT 36: MT-53 Collision Wire + Agent-Guard Blast Radius (~75 min)

#### 36A. Wire collision_reader_crystal into main.py (MT-53)

**Goal:** Crystal intro navigation uses real collision data.
**Source:** SESSION_RESUME.md — exact files named.

Steps:
1. Read `crystal_intro_navigation.py` and `main.py` current state
2. Replace `build_intro_navigator` with `build_intro_navigator_with_collision` in both files
3. Smoke test the navigation path (offline mode if possible)
4. Commit

#### 36B. Blast Radius Import Graph for Agent-Guard

**Goal:** Tag files by structural risk before multi-agent sessions touch them.
**Source:** Finding #16 (codesight concept, build Python-native).

Steps:
1. Create `agent-guard/blast_radius.py`:
   - Walk all `.py` files in project using `ast` (stdlib)
   - Parse `import` and `from X import Y` statements
   - Build forward dependency dict: `{file: [files_it_imports]}`
   - Invert to reverse dependency dict: `{file: [files_that_import_it]}`
   - `blast_radius(file)` = `len(reverse_deps[file])` (transitive optional as stretch)
2. Add `blast_radius: int` field to file ownership manifest output in `agent_guard/ownership.py`
3. Tag files with `blast_radius > 5` as `high_risk: true` in manifest
4. Emit warning in PreToolUse when a multi-agent session targets a `high_risk` file

Tests: known import graph produces correct blast_radius values, high_risk flag fires at threshold, zero-dep file = 0.
Commit.

---

### CHAT 37: Memory System — mem0 Patterns (Frontier 1 Overhaul) (~90 min) [DONE S266]

**Note:** Assess scope at session start. If changes touch >4 subsystems: run gsd:plan-phase first (20 min). Otherwise gsd:quick.

#### 37A. BMAD Party-Mode Read (research only, ~15 min)

Fetch and read: `https://raw.githubusercontent.com/bmadcode/bmad-method/main/src/core-skills/bmad-party-mode/SKILL.md`
Capture key patterns as comments in `agent-guard/hivemind_notes.md` (new file, scratch pad only).
Do NOT build anything — this is a prerequisite read before any further MT-21 hivemind work.

#### 37B. Memory System Semantic Deduplication

**Goal:** Fix append-only memory rot — memories should update/delete when stale, not pile up.
**Source:** Finding #15 (mem0 architecture). Do NOT adopt mem0 as a dependency — extract patterns only.

Steps:
1. Update `memory-system/schema.md`: add `user_id`, `agent_id`, `run_id` scoping fields to memory record schema. Get schema approved (mental review against existing records) before writing code.
2. In `memory-system/capture_hook.py` (or equivalent write path): before inserting a new memory, retrieve semantically similar existing memories (string similarity or keyword overlap — no embeddings required for v1)
3. Pass candidate memories + new memory to LLM with prompt: "Given these existing memories and this new memory, should we: (A) add new, (B) update existing [id], or (C) delete existing [id] as superseded? Reply with one word + optional id."
4. Execute the decision: ADD inserts new record, UPDATE modifies existing, DELETE removes stale
5. Three-tier scoping: all read/write operations filter by `user_id` + optional `agent_id`/`run_id`

#### 37C. FAISS Local Vector Backend (stretch — only if time permits)

- Install `faiss-cpu` (stdlib-adjacent, pure local)
- Replace keyword-overlap similarity in 37B with FAISS cosine similarity using sentence embeddings
- Fallback: if FAISS unavailable, revert to keyword overlap (graceful degradation)

Commit after 37B tests green. 37C is optional — don't delay commit for it.

---

### CHAT 38: BMAD Hivemind Patterns (MT-21) + Sports Math Port Phase 1 (~90 min)

Two tasks. Do in order 38A then 38B.

#### 38A. MT-21 Hivemind — BMAD Patterns (agent manifest + context cap + reactive pair)

**Goal:** Wire the 3 BMAD patterns from Chat 37 research into the hivemind infrastructure.
**Source:** `agent-guard/hivemind_notes.md` — all patterns are defined there.

Steps:
1. `session_orchestrator.py`: `register()` already updated with `ROLE_CAPABILITIES` manifest (S267).
   Add `manifest` CLI command: prints all roles with their capabilities and alive status.
2. `cca_comm.py` `cmd_task()`: add 400-word context cap warning. If `len(task.split()) > 400`,
   print a warning before sending: "BMAD context cap: task is N words (cap 400). Consider trimming."
   Do NOT block — warn only.
3. `cca_comm.py`: add `question` command — reactive pair pattern:
   `python3 cca_comm.py question <target> "question text"` sends a message with category="question".
   `python3 cca_comm.py inbox` already handles reading — just need a distinct send category so
   desktop knows it needs to reply in the same session, not next session.
4. Tests: manifest output format, context cap warning fires at >400 words, question category routing.
Commit.

#### 38B. Sports Math Port — Phase 1 (steal from agentic-rd-sandbox)

**Goal:** Port Sharp Score + team efficiency data into polymarket-bot as `sports_math.py`.
**Source:** Matthew directive S267. Steal from agentic-rd-sandbox, don't rewrite from scratch.
**Deliver via:** CCA_TO_POLYBOT.md (Kalshi chat implements after delivery).

Steps:
1. Read `/Users/matthewshields/Projects/agentic-rd-sandbox/core/math_engine.py`:
   Extract these functions (stdlib only, no external deps): `calculate_sharp_score()`,
   `passes_collar()`, `passes_collar_soccer()`, `implied_probability()`,
   `no_vig_probability()`, `fractional_kelly()`, `assign_grade()` + BetCandidate dataclass.
2. Read `/Users/matthewshields/Projects/agentic-rd-sandbox/core/efficiency_feed.py`:
   Extract `_TEAM_DATA` dict (NBA + NHL + MLB + soccer sections) + `get_team_efficiency()` logic.
3. Create `/Users/matthewshields/Projects/polymarket-bot/sports_math.py`:
   - All extracted math functions (adapted for Kalshi context — binary markets only, no spreads/totals)
   - `efficiency_gap_from_teams(home_team, away_team) -> float` helper using `_TEAM_DATA`
   - `sharp_score_for_bet(edge_pct, home_team, away_team) -> (float, dict)` convenience wrapper
   - No imports from polymarket-bot internals (standalone module, importable anywhere)
4. Tests: `tests/test_sports_math.py` — sharp_score formula, efficiency gap lookup, collar check,
   unknown team fallback (8.0), kelly sizing. 15+ tests.
5. Write delivery to CCA_TO_POLYBOT.md:
   - "sports_math.py delivered at [path]. Next: wire into sports_game_loop.py"
   - Include wiring instructions: 3 lines to add after edge_pct computed
6. Commit to polymarket-bot (separate commit from CCA changes).

**STOP CONDITION:** sports_math.py exists, tests pass, delivery written. Kalshi chat wires it.

---

### CHAT 38C: [TODO] Sniper Limits + 25 USD/Day Diversification Strategy (~75 min)

**Priority: HIGHEST — Matthew directive S166 + standing prime directive.**
**Goal:** (1) Set a STATISTICALLY-GROUNDED permanent sniper bet limit. (2) Design the 3-source
diversified income portfolio that reaches 25 USD/day without relying on sniper volume.
**Source data available:** REQ-080, polymarket-bot/.planning/TODAY_TASKS.md, cross-chat comms.
**Deliver via:** CCA_TO_POLYBOT.md.

Context:
- Daily sniper WR is 99%+ on BTC but a single 9-10 USD loss erases many wins
- S166 already implemented: ETH 10→2 USD cap, BTC 10→5 USD cap, max_daily_bets→20
- BUT: the S166 numbers were reactive, not statistically derived
- Need objective rules that survive scrutiny when Matthew challenges them with data

**2026-04-06 correction from post-ban audit + user feedback:**
- Sniper is the base layer, not the roadmap.
- No new sniper variants should take priority over building a second real engine.
- Sports may become `30-40%` of total bets, but only if MLB/NHL/NBA are handled as separate calibrated lanes.
- We are not ignoring other Kalshi markets; non-sports discovery remains a separate mandatory lane.
- Daily profit takes priority over betting sports games days from now. Same-day market visibility is a blocker priority.

#### Part A: Objective Sniper Limits (Kelly math)

1. Pull current stats from REQ data in POLYBOT_TO_CCA.md:
   - BTC daily_sniper: 734 bets, 95.8% WR, +41.66 net profit (pre-scale-up data)
   - ETH daily_sniper: current WR and sample size from latest comms
   - Bankroll: ~200 USD (REQ-077 confirmed)
2. Run Kelly math to derive objective bet size:
   - Fractional Kelly (0.25x) at 95.8% WR on binary bet (win=0.93 USD per dollar, lose=1.00):
     `b = 0.93, p = 0.958, q = 0.042` → `Kelly = (0.93*0.958 - 0.042) / 0.93`
   - 0.25x Kelly on 200 USD bankroll = objective BTC sniper size
   - ETH at lower WR → compute separately
3. Max bets/day limit — derive from expected daily loss risk:
   - P(at least 1 loss in N bets) = 1 - (0.958)^N
   - At N=20: P(loss) = 1-(0.958)^20 = ~57% — pick N where daily loss risk ≤ 20%
   - N where P(loss) ≤ 20% → solve: 0.8 = (0.958)^N → N = ln(0.8)/ln(0.958) ≈ 5.2 → cap = 5 BTC sniper bets/day for <20% loss-day probability
   - Document exact N for BTC and ETH separately
4. Write `SNIPER_LIMITS_RATIONALE.md` in polymarket-bot/.planning/ (1 page):
   - Kelly-derived bet sizes + max bets/day derivation with full math shown
   - Hard rules: "BTC sniper: max N bets/day at X USD each. ETH: max M bets/day at Y USD each."
   - Trigger for recalculation: after every 100 bets, recalculate from live WR

#### Part B: 3-Source Diversified Income Map

Goal: identify 3 income sources that can each contribute 5-8 USD/day independently.
Do NOT include speculative sources — must have structural edge basis.

Research each candidate and score:
1. **sports_game (MLB/NHL/NBA)** — current Phase 1 active, edge confirmed by SPRT (lambda=+6.139).
   - After Sharp Score Phase 1-2 wired: estimated +2-4 USD/day improvement
   - Realistic daily contribution: 5-8 USD/day (current ~3-5 USD, improving)
   - GAP: still needs efficiency_feed (Chat 38B) and injury data (Chat 39)

2. **economics_sniper (KXCPI/KXFED/KXUNRATE)** — paper mode, KXCPI fires April 8.
   - FLB basis: strong (academic anchoring bias in economic forecasts)
   - Monthly events only → 2-4 bets/month per market × 3 markets = ~8-12 bets/month
   - Realistic daily contribution: 0.5-1.5 USD/day averaged (low frequency, high per-bet value)
   - GAP: not a daily source — need volume from elsewhere

3. **soccer sniper (KXUCLGAME pre/in-play)** — paper mode, awaiting UCL games.
   - UCL: 8 games/month April-May, then off until September
   - EPL/Bundesliga: 10 matchdays remaining, ~30-50 games
   - FLB basis: confirmed in soccer (same structural mispricing as MLB)
   - Realistic daily contribution: 2-4 USD/day during active matchdays (not daily)
   - GAP: seasonal, not 7-day-a-week

4. **in-play sniper (90c+ trigger on sports events)** — currently paper for UCL.
   - This is the highest-ROI extension of FLB: near-expiry prices are best calibrated
   - Active daily across NBA/NHL/MLB (lots of games) once wired
   - Realistic daily contribution: 3-6 USD/day if NBA/NHL in-play wired
   - GAP: only UCL in-play wired currently; NBA/NHL games run daily and are untapped

5. Identify the COMBINATION that achieves 25 USD/day:
   - BTC sniper (capped): X USD/day
   - sports_game (post-Phase 1+2): Y USD/day
   - in-play sports sniper (new): Z USD/day
   - Sum to 25 — fill the gap analysis

#### Part C: In-Play Sports Sniper Proposal (the gap-filler)

Based on Part B analysis, in-play sports sniper is likely the missing 5-8 USD/day.
Design a concrete proposal:
1. Trigger: NBA/NHL/MLB game in last 5 minutes with Kalshi price ≥90c on one side
2. Same 90c FLB logic as UCL sniper (paper-validated S165)
3. At 20+ NBA/NHL/MLB games per day → expect 5-15 trigger events/day
4. Size: same as UCL in-play (conservative start, 2-3 USD)
5. Write 1-page design note to CCA_TO_POLYBOT.md: exact trigger logic + expected yield math

#### Delivery

Write to CCA_TO_POLYBOT.md:
- `SNIPER_LIMITS_RATIONALE.md` reference + hard rules summary (exact numbers)
- 3-source income map with realistic daily contribution per source
- In-play sports sniper proposal with wiring sketch
- Gap-to-25-USD analysis: "we need X more USD/day — in-play sniper fills it"

**STOP CONDITION:** Kelly math documented, income map complete, in-play sniper proposed,
all delivered to CCA_TO_POLYBOT.md. Do NOT implement code this session — research + design only.

---

### CHAT 39: Sports Math Port — Phase 2 (injury_data.py + SITUATIONAL component) (~60 min)

**Goal:** Port injury leverage table into polymarket-bot and wire as SITUATIONAL component in Sharp Score.
**Source:** `agentic-rd-sandbox/core/injury_data.py` (380 LOC). Matthew directive: steal ANYTHING beneficial.
**Deliver via:** CCA_TO_POLYBOT.md.

Steps:
1. Read `/Users/matthewshields/Projects/agentic-rd-sandbox/core/injury_data.py` in full:
   Extract: `POSITIONAL_LEVERAGE` dict (NBA/NFL/MLB/NHL positions → point-spread impact),
   `get_injury_leverage(sport, position, status) -> (float, bool)`, `InjuryReport` dataclass,
   `flag_injury_impact(player_name, position, sport, status) -> InjuryReport`.
2. Append to `/Users/matthewshields/Projects/polymarket-bot/sports_math.py` (created in 38B):
   - Full `POSITIONAL_LEVERAGE` static dict
   - `get_injury_leverage()` and `flag_injury_impact()` functions
   - `situational_score_from_injuries(injury_reports: list[InjuryReport]) -> float`
     Returns 0-15 pts (cap: 15) to feed SITUATIONAL component of Sharp Score
   - Update `sharp_score_for_bet()` to accept optional `injury_reports` list
3. Update `tests/test_sports_math.py`:
   - Test: leverage lookup by sport + position
   - Test: flagging fires for QB/PG/SP (star positions)
   - Test: no-flag for backup positions
   - Test: situational_score caps at 15
   - Total: 10+ new tests
4. Write delivery to CCA_TO_POLYBOT.md:
   - "injury_data ported to sports_math.py. Wire: pass injury_reports to sharp_score_for_bet()"
   - Include wiring example (2-3 lines in sports_game_loop.py)
5. Commit.

**STOP CONDITION:** injury functions in sports_math.py, tests pass, delivery written.

---

### CHAT 40: Sports Math Port — Phase 3 (nba_pdo.py + nhl_data.py) (~75 min)

**Goal:** Port NBA PDO regression signal and NHL goalie starter detection — two high-value kill switches.
**Source:** `agentic-rd-sandbox/core/nba_pdo.py` (483 LOC) + `agentic-rd-sandbox/core/nhl_data.py` (392 LOC).
**Deliver via:** CCA_TO_POLYBOT.md.

Steps:
1. Read `agentic-rd-sandbox/core/nba_pdo.py` in full:
   Extract: `_PDO_SNAPSHOT` static dict (all 30 NBA teams → pdo_score),
   `get_pdo_signal(team: str) -> str` ("regression", "recovery", "neutral"),
   `pdo_situational_pts(home_team, away_team) -> float` (0-10 pts for SITUATIONAL).
   NOTE: nba_api dependency → port static snapshot only (no live fetching). Same pattern as efficiency_feed.
2. Read `agentic-rd-sandbox/core/nhl_data.py` in full:
   Extract: `get_nhl_starters_for_game(game_id: str) -> Optional[dict]` logic and goalie cache pattern.
   Adapt: wire into Kalshi's NHL game lookup (sports_game_loop already has game_id context).
   Create `nhl_kill_switch_signal(home_goalie_starter: bool, away_goalie_starter: bool) -> dict`
   returning `{skip: bool, reason: str}` — skip bet if backup goalie detected on favored team.
3. Append both to `/Users/matthewshields/Projects/polymarket-bot/sports_math.py`:
   - `_PDO_SNAPSHOT` dict + `pdo_situational_pts()`
   - `nhl_kill_switch_signal()` 
   - Update `sharp_score_for_bet()` to accept `pdo_home_team`, `pdo_away_team` kwargs for NBA
4. Tests: pdo regression/recovery/neutral cases, neutral range (98-102), goalie kill switch fires,
   kill switch passes on both confirmed starters. 12+ new tests.
5. Write delivery:
   - "PDO + NHL goalie kill switch ported. PDO wires to NBA sharp_score. NHL kill switch replaces
     manual goalie check in sports_game_loop."
   - Include wiring sketch (4-5 lines)
6. Commit.

**STOP CONDITION:** PDO + NHL goalie in sports_math.py, tests pass, delivery written.

---

### CHAT 41: Sports Math Port — Phase 4 (analytics.py + calibration.py) (~60 min)

**Goal:** Port bet performance analytics and Sharp Score calibration pipeline — closes the self-learning loop.
**Source:** `agentic-rd-sandbox/core/analytics.py` (457 LOC) + `agentic-rd-sandbox/core/calibration.py` (401 LOC).
**Deliver via:** CCA_TO_POLYBOT.md.

Steps:
1. Read `agentic-rd-sandbox/core/analytics.py` in full:
   Extract: `compute_sharp_roi_correlation()`, `compute_equity_curve()`, `compute_rolling_metrics()`,
   `compute_book_breakdown()`, `get_bet_counts()` — all accept `list[dict]`, source-agnostic.
   These work directly on Kalshi's bet records with zero adaptation.
2. Read `agentic-rd-sandbox/core/calibration.py` in full:
   Extract: `get_calibration_report()`, `CalibrationReport` dataclass, Brier score + bin calibration logic.
   Adapt: calibration reads from polymarket-bot DB path (not sandbox DB path).
3. Create `/Users/matthewshields/Projects/polymarket-bot/sports_analytics.py`:
   - All analytics functions from analytics.py (no internal imports)
   - `CalibrationReport` dataclass + `get_calibration_report(db_path)`
   - `generate_sports_performance_report(bets: list[dict]) -> str` — text summary
     combining sharp_roi_correlation + rolling_metrics + calibration in one call
4. Tests: `tests/test_sports_analytics.py`
   - Test: equity curve monotonicity with all-win sequence
   - Test: ROI correlation returns buckets dict
   - Test: calibration returns inactive when n<10
   - Test: rolling metrics with 30-day window
   - 12+ tests
5. Write delivery to CCA_TO_POLYBOT.md:
   - "sports_analytics.py delivered. Wire generate_sports_performance_report() into /polybot-wrap
     output to get Sharp Score calibration + ROI breakdown every session."
6. Commit.

**STOP CONDITION:** sports_analytics.py exists, tests pass, delivery written.

---

### CHAT 42: Sports Math Port — Phase 5 (CLV tracking + originator_engine Monte Carlo) (~75 min)

**Goal:** Port CLV tracking and Monte Carlo simulation — gives Kalshi bot bet quality measurement + probability confidence.
**Source:** `agentic-rd-sandbox/core/clv_tracker.py` (286 LOC) + `agentic-rd-sandbox/core/originator_engine.py` (335 LOC).
**Deliver via:** CCA_TO_POLYBOT.md.

Steps:
1. Read `agentic-rd-sandbox/core/clv_tracker.py` in full:
   Extract: `log_clv_snapshot()`, `read_clv_log()`, `clv_summary()` — CSV persistence layer.
   CLV math already in math_engine.py: `calculate_clv(open_price, close_price, bet_price)` and
   `clv_grade(clv)`. Port both the math functions and the persistence layer.
2. Read `agentic-rd-sandbox/core/originator_engine.py` in full:
   Extract: `run_trinity_simulation(mean, sport, line) -> TrinityResult`, `efficiency_gap_to_margin()`.
   Trinity weighting: ceiling(20%) + floor(20%) + median(60%) → cover_probability.
   Adapt for Kalshi binary markets: use `cover_probability` as a second opinion on edge_pct.
   Add `binary_confidence_from_simulation(edge_pct, home_team, away_team, sport) -> float`
   that runs 1000 sims and returns P(our edge estimate is correct) as a confidence multiplier.
3. Create `/Users/matthewshields/Projects/polymarket-bot/sports_clv.py`:
   - CLV math functions + persistence (CSV at data/kalshi_clv_log.csv)
   - `log_clv_snapshot()` wired for Kalshi: accepts kalshi event_id, side, prices
4. Append to `sports_math.py`:
   - `binary_confidence_from_simulation()` using Trinity sim approach
   - Update `sharp_score_for_bet()` to optionally boost score when sim confidence > 0.65
5. Tests: `tests/test_sports_clv.py` — CLV log round-trip, CLV grade thresholds, summary aggregation.
   `tests/test_sports_math.py` additions: sim confidence returns float in [0,1], score boost fires. 10+ tests.
6. Write delivery:
   - "CLV tracking + Monte Carlo confidence ported. Wire sports_clv.log_clv_snapshot() after
     each bet settles. Wire binary_confidence_from_simulation() as optional sharp_score boost."
7. Commit.

**STOP CONDITION:** sports_clv.py + sim confidence in sports_math.py, tests pass, delivery written.

---

### CHAT 43: Sports Math Port — Phase 6 (tennis_data.py + full integration audit) (~60 min)

**Goal:** Port tennis surface/player data, then run a full integration audit across all Phase 1-5 ports.
**Source:** `agentic-rd-sandbox/core/tennis_data.py` (583 LOC).
**Deliver via:** CCA_TO_POLYBOT.md.

Steps:
1. Read `agentic-rd-sandbox/core/tennis_data.py` in full:
   Extract: `_SURFACE_MAP` tournament-to-surface dict, `normalize_player_name()`,
   `get_player_surface_rating(player, surface) -> float`, `tennis_surface_kill_switch(sport_key, home_player, away_player) -> dict`.
   Surface kill switch: fire if top-10 clay specialist on clay vs. hard-court specialist.
2. Append to `sports_math.py`:
   - `_TENNIS_SURFACE_MAP` dict + `get_player_surface_rating()`
   - `tennis_surface_kill_switch()` — returns `{skip: bool, reason: str, surface: str}`
   - Wire into `sharp_score_for_bet()` as a pre-filter for tennis sport_keys
3. Integration audit across ALL ported modules:
   - Verify imports: sports_math.py, sports_analytics.py, sports_clv.py are all stdlib-only
   - Run full test suite: all sports_* tests must pass
   - Check for function signature conflicts between Phase 1-5 additions
   - Verify `sharp_score_for_bet()` signature handles all new kwargs correctly
4. Write final delivery to CCA_TO_POLYBOT.md:
   - "Sports math stack COMPLETE (Phase 1-6). Summary: sports_math.py (Sharp Score + efficiency +
     injury + PDO + NHL goalie + sim confidence + tennis), sports_analytics.py (calibration + ROI),
     sports_clv.py (CLV tracking). Full wiring guide attached."
   - Include complete wiring guide: which functions to call at which point in sports_game_loop.py
5. Update TODAYS_TASKS.md: mark all CHAT 38B-43 tasks as DONE.
6. Commit.

**STOP CONDITION:** Tennis ported, integration audit passes, complete wiring guide delivered.

---

## PHASE 9: KALSHI BOT MASTER OVERHAUL (Chats 44-52)
# Matthew directive S268: "massive overhaul of the Kalshi bot and chat"
# Sports betting is ONE category among many. The full overhaul covers all 4 market categories
# plus bot infrastructure and Kalshi chat session quality.
#
# CONTEXT: Two calibration bugs were already fixed in S268 (committed to polymarket-bot):
#   - NCAAB wired into sports scanner (commit 763ba03)
#   - Daily cap raised 8→30 (commit 28a9c74)
#   - Bot needs a RESTART to pick up both changes.
#
# CODEX REVIEW REQUIRED before executing any Phase 9 chat.
# Confirm before restarting bot: is KXNCAABGAME the actual Kalshi series for NCAAB games?
# If wrong, change back to exclude basketball_ncaab until confirmed.

---

### PHASE 9 OVERVIEW — Four Layers

**Layer 1 — Bot Calibration** (Chat 44): Fix the remaining code-level bugs that cause
  the bot to behave incorrectly even when the strategy is right.

**Layer 2 — Signal Quality** (Chats 38B-43 + 45-46): Make each bet smarter.
  CCA delivers the math stack. Kalshi chat wires it.

**Layer 3 — Market Expansion** (Chats 47-49): Expand beyond the 9 current series
  into new categories with confirmed structural edge.

**Layer 4 — Session Intelligence** (Chat 50-52): Fix the Kalshi CHAT itself —
  context continuity, delivery implementation, execution quality.

Hard rules for Phase 9:
  - Sniper is the capital base, not the default answer to every profit gap.
  - Sports can reach `30-40%` of total bets once calibrated, but MLB/NHL/NBA are separate lanes.
  - Non-sports market discovery remains mandatory in parallel.
  - Market visibility is a blocker: the bot cannot execute the mission if it cannot see the board.
  - Same-day / near-term profit takes priority over betting sports games days from now.

---

### CHAT 44: [TODO] Layer 1 — Bot Calibration (Kalshi chat executes, ~45 min)

**Owner: Kalshi chat** (not CCA — these are bot wiring changes)
**Prerequisite: Codex review of NCAAB series name before restart**

#### 44A. Confirm NCAAB series name and restart bot

Before restarting: confirm `KXNCAABGAME` is the real Kalshi series prefix.
Check via: `kalshi.get_markets(series_ticker="KXNCAABGAME", status="open")` in a test script.
If empty and no error → series exists but no open markets (OK for now, off-season).
If 404/error → series name is wrong; revert the NCAAB addition until confirmed.

After confirmation: restart bot, check log for:
  `[sports_game] Scan: NBA=X NCAAB=X NHL=X MLB=X ...`

#### 44B. Game-date priority sort

File: `polymarket-bot/main.py`, function: `sports_game_loop`
Location: just before `for market in markets:` in the inner sport loop
Change: sort markets by `_parse_ticker_date(m.ticker)` ascending before iterating
Purpose: today's games are bet before April 9 games

```python
# Sort by game date ascending — today's games take priority over distant games
markets = sorted(
    markets,
    key=lambda m: _parse_ticker_date(m.ticker) or datetime.max.replace(tzinfo=timezone.utc)
)
```

Tests: add 2 unit tests to test_sports_game.py — verify sort order with mixed dates.
Risk: LOW — sort only changes order, not what gets bet.

#### 44C. 24h betting horizon

File: `polymarket-bot/main.py`, function: `sports_game_loop`
Add parameter: `max_bet_horizon_hours: int = 24`
Location: inner market loop, after `kalshi_date = _parse_ticker_date(ticker)`:

```python
if kalshi_date and (kalshi_date - _now_ts).total_seconds() > max_bet_horizon_hours * 3600:
    logger.debug("[sports_game] %s too far out (>%dh) — skip", ticker, max_bet_horizon_hours)
    continue
```

Call site: pass `max_bet_horizon_hours=24` (consider 36h if 24h feels too tight for evening games).
NOTE: This does NOT affect economics_sniper (different loop, different parameter). Economics
sniper naturally needs 48h horizon for pre-release windows — leave that loop unchanged.

Tests: add 3 unit tests — game within 24h passes, game at 25h skipped, edge case at exactly 24h.
Risk: LOW — only restricts distant bets, never blocks valid today bets.

#### 44D. Balance reconciliation script

File: `polymarket-bot/scripts/balance_check.py` (new)
Purpose: calls Kalshi `/portfolio/balance` API, compares to DB all-time P&L + initial deposit
Output: reconciliation report showing any gap between DB records and actual account balance
Context: REQ-077 requested this. DB all-time = 139.10 USD, actual balance = 223.07 USD —
  the gap is the initial deposit amount (not a bug, just untracked).

Implementation:
1. Call `GET /portfolio/balance` → get `balance` field (cash) + positions value
2. Read DB: `SELECT SUM(pnl) FROM trades WHERE resolved=1` → all-time P&L
3. Infer initial deposit: `actual_balance - db_pnl`
4. Print reconciliation table: initial_deposit | db_pnl | expected_balance | actual_balance | gap
5. Flag if gap > $5 (suggests missing trades or accounting error)

**STOP CONDITION:** Bot restarted with NCAAB confirmed, sort + horizon wired, balance_check.py working.

---

### CHAT 45: [TODO] Layer 2 — Wire Sports Math Phase 1 (Kalshi chat, ~45 min)

**Prerequisite: CCA Chat 38B must be complete (sports_math.py delivered)**
**Owner: Kalshi chat**

After CCA delivers `sports_math.py` via CCA_TO_POLYBOT.md:
1. Verify `sports_math.py` is at `polymarket-bot/sports_math.py`
2. In `sports_game_loop`, after `edge_pct` is computed for each market, add:
   ```python
   from sports_math import sharp_score_for_bet, efficiency_gap_from_teams
   sharp = sharp_score_for_bet(edge_pct=edge_pct, home_team=home_team, away_team=away_team)
   if sharp < 35:
       logger.debug("[sports_game] %s Sharp=%d below threshold (35) — skip", ticker, sharp)
       continue
   ```
3. Log Sharp Score in bet record for post-analysis
4. Paper validation: run 20 bets. Compare win rate pre/post Sharp Score filter.
5. After 20 bets: if WR unchanged or improved → raise threshold to 40, continue validation.

**STOP CONDITION:** Sharp Score filter live in paper mode, 20-bet validation running.

---

### CHAT 46: [TODO] Layer 2 — In-Play Sports Sniper (CCA designs, Kalshi wires)

**Owner: CCA designs the strategy. Kalshi chat implements.**

**This is NOT the immediate answer to every profit gap.**
Only proceed after:
1. Chat 44 bot correctness fixes land
2. same-day sports visibility is verified
3. MLB/NHL/NBA are being tracked as separate calibrated lanes

**If those conditions are met, this becomes a candidate gap-filler using the same FLB logic as UCL soccer_sniper, applied to NBA/NHL/MLB daily games.**

Why this fills the 25 USD/day gap:
- UCL soccer_sniper: 8 games/month → ~0.27 games/day → maybe 0.5-1 USD/day
- NBA/NHL/MLB daily games: 15-25 games/day → 5-15 trigger events/day at 90c+
- Each bet: 2-3 USD at 90-95c → expected value +5-15c per bet
- Expected daily contribution: 5-8 USD/day

CCA deliverable (design note in CCA_TO_POLYBOT.md):
1. Trigger logic: `yes_price >= 90` OR `no_price >= 90` AND game settle time < 3h from now
2. Eligible series: KXNBAGAME + KXNHLGAME + KXMLBGAME (NOT soccer — 90c threshold works
   differently on 3-way markets)
3. Size: start at 2 USD (same as UCL soccer_sniper), ramp after 20-bet validation
4. Dedup: one bet per game (same game_key dedup as sports_game_loop)
5. NOT eligible if we already have an open sports_game bet on the same game
6. Loop: separate `sports_inplay_sniper_loop` — same architecture as soccer_sniper_loop
7. Wiring: add to main.py alongside existing soccer_sniper_loop

Kalshi deliverable: implement after CCA design note arrives.

**STOP CONDITION:** sports_inplay_sniper_loop live in paper mode, firing on NBA/NHL/MLB.

---

### CHAT 47: [TODO] Layer 3 — UFC Market Strategy (research + design only)

**Owner: CCA research, Kalshi chat implements after validation**

UFC has documented oddsmaker conservatism bias (FLB-like structure) in academic literature.
Kalshi series: KXUFCFIGHT. Next event: UFC 316 (May 3, 2026 — Oliveira vs Makhachev 2).

CCA deliverable (research note + design sketch):
1. Verify: does Kalshi KXUFCFIGHT open 14 days before the event or closer?
   If <7 days: limited time to scan + bet at good prices.
2. Signal: compare Kalshi implied probability vs BestFightOdds / DraftKings consensus
   Same edge% + collar logic as sports_game_v1 — almost identical implementation.
3. Edge floor: 8% minimum (UFC markets are less liquid than MLB/NBA)
4. Kill switch: title fights vs prelims (different price behavior)
5. Volume check: is KXUFCFIGHT volume comparable to KXMLBGAME? If <50K, skip for now.

**NOT a new strategy file** — if volume and edge basis confirmed, extend `sports_game_v1`
to include `"mma_mixed_martial_arts": "KXUFCFIGHT"` in the sport map.

Paper validation: 5 UFC events before going live (low event frequency = long validation window).

**STOP CONDITION:** Research note written. Decision: BUILD or DEFER (volume-gated).

---

### CHAT 48: [TODO] Layer 3 — Dynamic Market Discovery (lightweight scanner)

**Context:** Kalshi has 9,490 total series. Most are irrelevant (copy trading, micro-cap,
vanity markets). A few will have FLB-exploitable structure we haven't found yet.

**NOT a real-time 9,490-series scanner** — that's expensive and unnecessary.

CCA deliverable: `scripts/kalshi_series_scout.py` — runs weekly, finds high-volume series
outside current coverage, and makes full-market visibility a first-class capability rather than an afterthought.

Design:
1. `GET /markets/series` paginated — fetch ALL series (one-time weekly scan, not per-loop)
2. Filter: `volume > 50000` AND `close_time > 7 days from now` AND NOT in known series set
3. Group by category prefix: KXBTC*/KXETH* (crypto), KXNBA*/KXNHL* etc. (sports),
   KXCPI/KXFED/KXGDP (economics), KX* unknown (candidates)
4. Output: ranked list of candidates by volume, with category label
5. Human review: Matthew reviews weekly output and decides which to add to strategy map

Correction:
- This is not just "nice to have." Market visibility is a blocker priority because the current bot
  cannot even see enough of Kalshi correctly to satisfy the daily-profit mandate.

Weekly cron: run every Monday 06:00 ET, output to `.planning/SERIES_SCOUT_YYYY-MM-DD.md`

This is NOT automation of new markets — it's INTELLIGENCE about what exists.
Matthew makes the decision to expand, not the bot.

**STOP CONDITION:** scout script runs and produces weekly report.

---

### CHAT 49: [TODO] Layer 3 — Economics Sniper Live Promotion

**Prerequisite: KXCPI April 8 paper bet settles correctly**
**Owner: Kalshi chat**

After KXCPI April 8 paper bet:
1. Verify paper bet settled correctly (correct direction, correct price)
2. Check: was the signal correct? Did the CPI print match the over/under threshold?
3. If YES: promote economics_sniper to live for KXCPI only. Keep KXFED/KXUNRATE paper.
4. After 3 live CPI bets with wins: promote KXFED and KXUNRATE to live.
5. After all 3 live with 10+ bets total: raise economics bet size from default to 5 USD.

Expected contribution: 2-3 USD per event × ~4 events/month = ~8-12 USD/month ≈ 0.3-0.4 USD/day
Low daily frequency but high per-event value (consistent with "diversified income" goal).

**STOP CONDITION:** KXCPI live, KXFED/KXUNRATE paper, size ramp scheduled.

---

### CHAT 50: [TODO] Layer 4 — Kalshi Chat Session Quality Overhaul

**This is the highest-leverage improvement. Bad session quality erases good bot code.**

Root causes identified S268:
1. Kalshi chat not reading CCA_TO_POLYBOT.md at session start — misses deliveries
2. SESSION_HANDOFF.md goes stale — chat works from outdated state
3. No mandatory checklist — chat starts coding before reading context
4. Context limit causes mid-session degradation — chat forgets earlier decisions

CCA deliverable: new `polymarket-bot/.planning/KALSHI_INIT_CHECKLIST.md`

Mandatory Kalshi session init (5 steps, all required before any code):
```
Step 1: cat ~/.claude/cross-chat/CCA_TO_POLYBOT.md | tail -200
        → Any URGENT items? Implement them NOW before anything else.
Step 2: cat .planning/SESSION_HANDOFF.md | head -100
        → What was the last session's state? What was left unfinished?
Step 3: python3 main.py --health (or equivalent) + verify bot is running
        → PID alive? Log shows errors? Recent bets settling correctly?
Step 4: python3 scripts/balance_check.py
        → P&L today (CST). Are we on track for 25 USD? Any strategy bleeding?
Step 5: Check open positions + daily bet count per strategy
        → Any strategy at cap? Any bets stuck open >48h?
```

Then and ONLY then: decide what to work on this session.

Also: update `/polybot-auto` loop rule — every 3rd cycle must re-read CCA_TO_POLYBOT.md tail.
If last CCA delivery >48h ago, write POLYBOT_TO_CCA.md requesting update.

**STOP CONDITION:** KALSHI_INIT_CHECKLIST.md written. /polybot-init updated to run it at start.
polybot-auto updated to check CCA comms every 3rd cycle.

---

### CHAT 51: [TODO] Layer 4 — Kalshi Chat Context Management

**Problem:** Kalshi sessions degrade as context fills. Chat forgets directives from session start.

CCA deliverable: context anchor strategy for Kalshi sessions.

1. Expand PreCompact hook (already in CCA) → port to Kalshi project.
   Snapshot current bot state (strategy statuses, open bets, P&L today) before compaction.
2. PostCompact hook: restore key state from snapshot + print reminder of current directives.
3. SESSION_HANDOFF.md: redesign format to be compaction-resilient.
   Use numbered sections (survive compression). Max 500 words (BMAD context cap analogue).
4. Critical directive anchoring: at session start, write key directives to a file the chat
   can re-read mid-session: `.planning/ACTIVE_DIRECTIVES.md` (5 bullet points max).

**STOP CONDITION:** PreCompact/PostCompact ports to Kalshi project. SESSION_HANDOFF.md redesigned.
ACTIVE_DIRECTIVES.md format defined.

---

### CHAT 52: [TODO] Phase 9 Wrap + Phase 10 Planning

After Chats 44-51 complete:
1. Audit actual vs expected P&L improvement:
   - Before overhaul: X USD/day (last 7 days average before S268)
   - After overhaul: Y USD/day (7 days after full deployment)
   - Gap analysis: what still needs to close to hit 25 USD/day?
2. Evaluate sports_math Phase 1-2 impact: did Sharp Score filter improve WR?
3. Evaluate in-play sniper: is it firing? What's the per-bet expected value?
4. Write Phase 10 plan (if needed) based on measured gaps.

**STOP CONDITION:** Audit complete, P&L delta measured, Phase 10 plan written if gap remains.

---

## DEFERRED FROM PHASE 8 (scheduled when phase 8 complete)

- **SKILL.md wrapping of CCA modules** — Wrap CCA frontier modules as publishable Agent Skills (NEW F6 candidate). Strategic decision needed first: do we want to publish externally?
- **ai-blind-spots taxonomy** → port into `/senior-review` + `/spec:design-review` (small, any session gap)
- **MT-21 hivemind with BMAD patterns** — after Chat 37 BMAD read
- **Loop detector PostToolUse enhancement** — count same-file read+edit, warn if >N without test pass (extends S238 loop_guard.py)
- **Auto-generate PROJECT_INDEX.md** from AST (codesight pattern) — after blast_radius is working

---

## DEFERRED (not scheduled, revisit when relevant)

- **TurboQuant vector compression** — only when Frontier 1 hits storage scale problems
- **Computer use monitoring** — token costs catastrophic, revisit when Anthropic stabilizes pricing
- **cc2codex** — LLM diversification tool, revisit if needed
- **Octopoda shared knowledge spaces** — MT-21 hivemind enhancement, after basic hivemind is proven
- **Loop guard v2 (embeddings)** — only if v1 string similarity proves insufficient
- **Subagent frontmatter hardening** — COMPLETED via 11B. Custom agent designs now in CUSTOM_AGENTS_DESIGN.md with full frontmatter specs. Phase 4 Chats 14-15 will build them.

---

## PHASE 2: COMPLETED (S239-S241)

Chats 4-7 from Phase 2 plan. All build/evaluation/port work done.

| Chat | Session | Status | Output |
|------|---------|--------|--------|
| 4: Cleanup + Dream Design | S239 | DONE | Phase 1 committed, env vars verified, loop guard smoke tested, DREAM_INTEGRATION_DESIGN.md |
| 5: Wrap Optimization | S240 | DONE | batch_wrap_analysis.py, slim cca-wrap.md, conditional cross-chat (~40% wrap token reduction) |
| 6: Learning + Evaluation | S241 | DONE | CLAUDE_HOWTO_GAP_ANALYSIS.md (13 modules, top gaps: subagents, hooks, orchestration), Paseo DEFER |
| 7: Mistake-Learning + Port | S241 | DONE | correction_detector.py + correction_capture.py hook (68 tests), Kalshi port (hooks + env vars) |

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
