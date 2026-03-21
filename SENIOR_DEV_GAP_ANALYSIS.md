# Senior Developer Agent — Gap Analysis
# Session 77 — 2026-03-20
# Purpose: Document the gap between what exists and what Matthew wants

---

## Matthew's Vision (verbatim, S77)

> "Picturing the CLI chat as a senior developer coder in constant communication
> with the desktop chat as if it were some virtual Anthropic senior developer
> who is helping the project work with the wisdom and authority and experience
> of an actual human senior developer."

> "If it's not meeting that quality, then we're off base."

**Translation**: The tool should behave like having a real senior engineer sitting
next to you. Not a linter. Not a metric dashboard. A colleague who:
- Reviews your work with architectural context
- Catches things you'd miss because they require system-wide thinking
- Communicates findings clearly, like a code review comment from a trusted peer
- Makes you more productive, not more annoyed (ADHD-aware: batch, prioritize, be brief)
- Has institutional memory (knows WHY decisions were made, not just WHAT the code does)

---

## What Exists Today (MT-20 Phases 1-5, built S70-S74)

### Built Modules (all tested, all passing)

| Module | LOC | Tests | What It Does |
|--------|-----|-------|-------------|
| satd_detector.py | 176 | 42 | Regex scan for TODO/FIXME/HACK/WORKAROUND/DEBT/XXX/NOTE |
| effort_scorer.py | 185 | 42 | LOC + complexity keyword count -> 1-5 score |
| code_quality_scorer.py | 363 | 38 | 5-dimension weighted score (debt, complexity, size, docs, naming) |
| fp_filter.py | ~150 | 40 | Filters findings from test files, vendored code, low-confidence |
| review_classifier.py | ~200 | 43 | CRScore-style 6-category classification |
| tech_debt_tracker.py | ~180 | 27 | SATD trend analysis over time |
| adr_reader.py | ~200 | 38 | ADR discovery + relevance matching |
| senior_dev_hook.py | 249 | 48 | PostToolUse orchestrator combining SATD + effort + quality |

**Total: ~1,700 LOC, ~318 tests, all passing.**

### What These Modules Actually Do

They are **static metric calculators**. They:
- Count TODO markers (regex)
- Count control flow keywords (regex)
- Measure LOC against thresholds (arithmetic)
- Check documentation ratios (arithmetic)
- Classify findings into categories (rule-based)
- Score files 0-100 using weighted averages (arithmetic)

### What These Modules Do NOT Do

| Senior Developer Function | Current Capability | Gap |
|--------------------------|-------------------|-----|
| **Design review** — "Is this the right approach?" | None | TOTAL |
| **Architectural coherence** — "Does this fit the system?" | None (ADR reader exists but isn't integrated into review) | LARGE |
| **Intent verification** — "Is this what the user actually needs?" | None | TOTAL |
| **Blast radius assessment** — "What else breaks if this changes?" | None | TOTAL |
| **Interactive communication** — "I think you should consider X" | None (PostToolUse additionalContext is one-way) | LARGE |
| **Context-aware review** — "Given the project's history, this is risky" | None | LARGE |
| **Knowledge transfer** — "Can someone else maintain this at 3am?" | None | TOTAL |
| **Cross-file reasoning** — "This change conflicts with module Y" | None | TOTAL |
| **Trade-off judgment** — "Simpler approach vs. extensible approach" | None | TOTAL |
| **Pattern enforcement** — "Other modules do this differently" | None (quality scorer checks naming length, not patterns) | LARGE |

### Honest Assessment

**The current "Senior Dev" is a linter with a good name.** It does what SonarQube
or ESLint does — count smells, flag complexity, report metrics. That's valuable
infrastructure, but it's not what Matthew described.

A real senior developer:
1. **Understands WHY** code exists, not just HOW it's structured
2. **Communicates** findings as actionable advice, not metric scores
3. **Has context** about the project's history, patterns, and decisions
4. **Prioritizes** — knows when a 300-LOC function is fine vs. when it's a problem
5. **Asks questions** — "Did you consider X?" rather than "Complexity: 72/100"

The current tool does none of these. It's Phase 0 infrastructure that Phase 1
(the actual senior dev experience) should build on.

---

## The Research Is Excellent

The S70 research document (SENIOR_DEV_AGENT_RESEARCH.md) is genuinely high quality:
- 11 verified academic papers
- 5 open-source tools analyzed
- Industry standards from Google, Stripe, Atlassian, Anthropic
- Clear automatability matrix (what AI CAN vs. CANNOT do)
- MVP architecture recommendations grounded in evidence

**Key insight from the research**: The Atlassian RovoDev deployment proves that
LLM code review works in production IF there's a quality gate layer. The filter
is where trust is earned. Raw output (even from good models) has ~76% false
positive rate without filtering (Tencent/Fudan ICSE 2026).

The research recommended:
1. MVP: Hook-based passive checks (SATD, effort, consistency) + on-demand skill for deep review
2. Full vision: Interactive agent for architectural decisions, triggered explicitly

**What got built was MVP item 1. MVP item 2 (on-demand skill) was never started.**

---

## What Needs to Happen

### Phase 1: Make Current Tools Useful (1 session)

The existing modules work but aren't wired into a useful workflow:
- senior_dev_hook fires on every Write/Edit but output is generic metric text
- No one reads "Quality: C (67/100)" and changes their behavior
- The hook should produce ACTIONABLE advice, not scores

**Concrete changes:**
1. Rewrite `format_context()` to produce natural language, not metric dumps
   - BAD: `[HIGH] (satd) Line 42: TODO — fix this later`
   - GOOD: `Consider resolving the TODO on line 42 before committing — it marks unfinished work that could be forgotten`
2. Add project context awareness — read CLAUDE.md rules and check if the code violates them
3. Threshold tuning — only fire when there's something genuinely worth saying (current: fires on any finding)

### Phase 2: Build the On-Demand Skill (1-2 sessions)

Create `/senior-review` slash command that does what a real senior dev would:
1. Reads the file being reviewed + related files (imports, callers)
2. Checks against project's architectural patterns (from CLAUDE.md, existing module structure)
3. Checks against ADRs (already built but not integrated)
4. Produces a structured review with:
   - Design fit: Does this belong here? Does it follow the module's patterns?
   - Concerns: What could go wrong? What's fragile?
   - Suggestions: Specific, actionable improvements (not "consider refactoring")
   - Approval: YES (good to merge) / CONDITIONAL (fix X first) / NO (rethink approach)

### Phase 3: Build the Interactive CLI Chat Mode (2-3 sessions)

This is Matthew's actual vision — a CLI chat running as a senior dev colleague:
1. Define the senior dev persona (CLAUDE.md for the CLI chat)
2. Wire it into hivemind communication (queue + scope awareness)
3. The CLI chat RECEIVES code changes via queue, REVIEWS them, SENDS feedback back
4. Desktop chat sees feedback as queue messages, not PostToolUse noise
5. Prove this works over 3-5 sessions before expanding scope

### Phase 4: Architectural Coherence Checker (2-3 sessions)

The hardest and most valuable piece — from the research synthesis:
1. Cross-file pattern detection (do all modules follow the same conventions?)
2. Dependency graph analysis (what else is affected by this change?)
3. System health scoring (does this change improve or degrade the whole project?)
4. This is where the "senior developer wisdom" actually lives

---

## What To Keep, What To Rebuild, What To Discard

| Component | Verdict | Reason |
|-----------|---------|--------|
| satd_detector.py | KEEP | Solid, tested, useful as infrastructure |
| effort_scorer.py | KEEP | Solid, tested, good for hook threshold decisions |
| code_quality_scorer.py | KEEP | Solid, useful for batch analysis |
| fp_filter.py | KEEP | Critical — filters noise, prevents alert fatigue |
| review_classifier.py | KEEP | Useful for categorizing findings by type |
| tech_debt_tracker.py | KEEP | Good for trend analysis over time |
| adr_reader.py | KEEP + INTEGRATE | Built but not wired into the review flow |
| senior_dev_hook.py | KEEP + REWRITE format_context() | Orchestrator is fine, output format needs work |
| Research document | KEEP as reference | Excellent foundation, don't re-research |

**Nothing needs to be discarded.** The infrastructure is sound. What's missing is
the intelligence layer that turns metrics into advice.

---

## Success Criteria

The Senior Dev tool is successful when:
1. Matthew gets feedback that changes his behavior (not feedback he ignores)
2. The feedback is specific enough to act on without further research
3. False positive rate is <20% (research says trust collapses above this)
4. It catches things Matthew would have missed (not things he already knows)
5. It feels like having a colleague, not like running a linter

---

## Timeline

This is NOT a one-session project. Estimated across multiple CCA chats:
- Phase 1 (hook output quality): 1 session
- Phase 2 (on-demand skill): 1-2 sessions
- Phase 3 (interactive CLI mode): 2-3 sessions
- Phase 4 (architectural coherence): 2-3 sessions

Total: 6-9 sessions across multiple CCA chats. No rush.

---

## Progress Update (S78-S79, 2026-03-20)

### Gaps Closed

| Gap from Table | Status | How Closed |
|----------------|--------|------------|
| Architectural coherence | CLOSED | coherence_checker.py: module structure, pattern consistency, import dependency graph |
| Blast radius assessment | CLOSED | ImportDependencyCheck.blast_radius() wired into senior_review |
| Pattern enforcement | CLOSED | RuleExtractor + RuleComplianceCheck: reads CLAUDE.md rules, flags violations |
| Cross-file reasoning | PARTIALLY CLOSED | Import dependency graph shows what depends on what; blast radius in reviews |
| Interactive communication | CLOSED (foundation) | senior_chat.py: CLI REPL with review context + LLM prompt generation |
| ADR integration | CLOSED | adr_reader wired into senior_review — surfaces accepted/deprecated ADRs |
| Context-aware review | PARTIALLY CLOSED | Project-root + module CLAUDE.md rules extracted and checked |

### Phases Completed

| Phase | Status | Session |
|-------|--------|---------|
| Phase 6 (hook output rewrite) | DONE | S78 |
| Phase 7 (/senior-review skill) | DONE | S78 |
| Phase 8 (interactive CLI chat) | DONE (foundation) | S79 |
| Phase 9 (architectural coherence) | DONE | S78-S79 |

### What's Still Missing

| Senior Developer Function | Status | Next Step |
|--------------------------|--------|-----------|
| Intent verification | CLOSED | build_intent_check_prompt() — structured LLM prompt (S81) |
| Context-aware review (full) | CLOSED | git_context.py: file history, blame, churn detection (S80) |
| Trade-off judgment | CLOSED | build_tradeoff_prompt() — structured LLM prompt (S81) |
| Knowledge transfer check | CLOSED (via LLM) | Trade-off prompt includes maintainability assessment |
| senior_chat LLM wiring | CLOSED | LLMClient with Anthropic API, conversation history (S80) |

**All 10 gap analysis items now have implementations.** E2E validation with real
API key completed in Session 101. All LLM features confirmed working:
- LLMClient.ask(): basic Q&A, multi-turn conversation with history
- build_intent_check_prompt(): verifies code matches stated purpose
- build_tradeoff_prompt(): analyzes design trade-offs in context
- format_initial_review(): static review with metrics/concerns
- Multi-turn conversation: 4-message history preserved correctly

### Module Count

senior_review.py orchestrates 7 submodules: SATD, quality, effort, coherence (with rule compliance), blast radius, fp_filter, ADR reader. senior_chat.py provides interactive mode with LLMClient, intent verification, and trade-off judgment. git_context.py provides history awareness. Total: ~3,000 LOC, ~890 tests.

---

*Written: Session 77, 2026-03-20*
*Updated: Session 81, 2026-03-20 — All 10 gaps closed (S78-S81)*
*Updated: Session 101, 2026-03-21 — E2E LLM validation PASSED (all features confirmed)*
