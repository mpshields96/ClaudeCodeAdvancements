# CLAUDE.md Token Audit

**Date:** 2026-03-31 (Chat 12D, S245)
**Reference:** Boris's advice — CLAUDE.md should be <1000 tokens for optimal prompt cache efficiency

---

## Current Token Counts (4 chars/token estimate)

### Project-Level (loaded for CCA sessions)
| File | Chars | ~Tokens | Notes |
|------|-------|---------|-------|
| `CLAUDE.md` | 10,804 | 2,701 | **2.7x over Boris target** |
| `.claude/rules/agent-guard.md` | 549 | 137 | |
| `.claude/rules/reddit-intelligence.md` | 520 | 130 | |
| `.claude/rules/context-monitor.md` | 657 | 164 | |
| `.claude/rules/memory-system.md` | 552 | 138 | |
| `.claude/rules/hivemind-worker.md` | 2,024 | 506 | Only loads for workers |
| `.claude/rules/spec-system.md` | 867 | 216 | |
| **Project subtotal** | **15,973** | **~3,992** | |

### Global (loaded for ALL sessions on this machine)
| File | Chars | ~Tokens | Notes |
|------|-------|---------|-------|
| `~/.claude/RTK.md` | 958 | 239 | |
| `~/.claude/COMMANDS.md` | 6,921 | 1,730 | **Huge — reference table** |
| `~/.claude/rules/mandatory-skills-workflow.md` | 4,614 | 1,153 | |
| `~/.claude/rules/feature-estimation.md` | 968 | 242 | |
| `~/.claude/rules/gsd-framework.md` | 2,361 | 590 | |
| `~/.claude/rules/peak-offpeak-budgeting.md` | 1,953 | 488 | |
| `~/.claude/rules/cca-polybot-coordination.md` | 4,002 | 1,000 | |
| `~/.claude/rules/learnings.md` | 5,864 | 1,466 | |
| `~/.claude/rules/titanium-field-names.md` | 2,148 | 537 | |
| **Global subtotal** | **29,789** | **~7,445** | |

### Grand Total: ~11,437 tokens loaded every CCA session

Boris target: <1,000 tokens for CLAUDE.md. We're at **11.4x** the recommended budget when counting all loaded instructions.

---

## Reduction Plan

### Tier 1: Quick Wins (save ~3,500 tokens)

**1. COMMANDS.md → Remove from @include (~1,730 tokens saved)**
- This is a reference table, not behavioral instructions
- Claude doesn't need the full command table in context — it already has skill definitions
- Move to a file that's read on-demand, not auto-loaded

**2. learnings.md → Prune expired entries (~800 tokens saved)**
- "Anthropic 2x Usage Limits Promotion" — EXPIRED March 28. Delete entirely.
- "Peak/Off-Peak Token Budgeting" — duplicated in its own rules file. Keep one.
- Net: ~5,864 → ~3,500 chars

**3. MT-53 Pokemon sections → Move to project-level rules file (~400 tokens saved)**
- STEAL CODE directive (lines 39-44) — only relevant when working on pokemon-agent
- EMULATOR RULES (lines 46-59) — only relevant when working on pokemon-agent
- Move both to `.claude/rules/pokemon-bot.md` or `pokemon-agent/.claude/rules/`

**4. titanium-field-names.md → Evaluate necessity (~537 tokens saved)**
- Is this still being used? If it's for the old Kalshi bot field names, check if current codebase references it.

### Tier 2: Structural Refactoring (save ~2,500 tokens)

**5. CLAUDE.md → Compress to essentials**
Current structure has redundancy:
- "Cardinal Safety Rules" — 7 rules at ~700 tokens. Compress to 3-line summary: "Don't break anything, don't expose credentials, fail safe. Full rules in .claude/rules/safety.md"
- "Session Workflow" — Already handled by slim_init.py. Remove from CLAUDE.md.
- "Test Commands" — Already in slim_init.py. Remove.
- "Desktop Autoloop" — One sentence reference, not full description.
- "Known Gotchas" — Move to `.claude/rules/gotchas.md`.

Target CLAUDE.md: 150 lines → ~60 lines (~600-800 tokens)

**6. mandatory-skills-workflow.md → Compress decision tree (~500 tokens saved)**
The full tier table + decision tree is ~1,153 tokens. Compress to:
```
Default: gsd:quick + TDD. Escalate to plan-phase ONLY when 5+ tasks + 4+ subsystems + multi-session.
Free tiers: TDD, verification, systematic-debugging, add-todo. Use always.
```
~200 tokens instead of 1,153.

**7. cca-polybot-coordination.md → Extract static parts (~400 tokens saved)**
The monitoring cadence section and self-learning mechanisms list are reference material, not behavioral instructions. Move to a reference doc.

### Tier 3: Architectural Change (save ~2,000+ tokens)

**8. Move from @include to on-demand loading**
Instead of loading COMMANDS.md and learnings.md into every session context:
- Create a `/cca-lookup` command that reads reference files when needed
- Only include behavioral rules (< 2,000 tokens) in auto-loaded context
- Reference material loaded on tool call, not on init

---

## Proposed Token Budget

| Category | Current | Target | Savings |
|----------|---------|--------|---------|
| CLAUDE.md | 2,701 | 800 | 1,901 |
| Project rules | 1,291 | 1,000 | 291 |
| Global rules | 7,445 | 3,000 | 4,445 |
| **Total** | **11,437** | **4,800** | **6,637 (58% reduction)** |

Boris target of <1,000 for CLAUDE.md alone is achievable. Getting ALL auto-loaded context under 5,000 tokens requires the structural refactoring (Tier 2+3).

---

## Priority

This is a medium-priority optimization. The cost is real (~11K tokens per session, ~$0.03-0.05/session at current rates, multiplied across hundreds of sessions). More importantly, it affects prompt cache efficiency — shorter CLAUDE.md = more of the system prompt stays cached across turns.

Implementation should be multi-session: Tier 1 in one session, Tier 2 in another, with testing between.
