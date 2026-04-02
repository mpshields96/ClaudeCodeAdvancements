# NEXT CHAT HANDOFF — Chat 17

## Start Here
Run /cca-init. Last session was S249 Chat 16 on 2026-04-01.

---

## Context: What was done (Chat 16)

All 3 Chat 16 tasks complete:
- **16A**: `reddit-intelligence/verdict_parser.py` + `/cca-nuclear` Phase 3 rewritten for parallel cca-reviewer agent delegation (22 tests)
- **16B**: `hooks/session_start_hook.py` — SessionStart hook, runs smoke+budget+top-task on session open (8 tests, wired in settings.local.json)
- **16C**: `hooks/spawn_budget_hook.py` — PreToolUse[Agent] hook, tracks spawn cost by model, warns at 200K threshold (11 tests, wired in settings.local.json)

3 commits: c104c87 / 8526d41 / 333ad5d

---

## Chat 17 — Context Overhead Reduction (~45 min)

**WHY THIS IS NOW CHAT 17:**
After Chat 16, session hit 44% of 5-hour limit in 3 prompts. Root cause: ~55KB of
context loads every session. MEMORY.md (18KB) is injected as system-reminder on
EVERY turn — not cached. Fixing this directly reduces burn rate for all future sessions.

**Before touching anything: `git commit` current state as safety checkpoint.**

### 17A. MEMORY.md Prune — Do This First (~20 min)
File: `/Users/matthewshields/.claude/projects/-Users-matthewshields-Projects-ClaudeCodeAdvancements/memory/MEMORY.md`
Current: 173 lines, 18KB — injected every turn as system-reminder.
Target: ~80 lines (50%+ cut).

**What to remove:**
- Expired time-sensitive entries: `project_2x_token_promotion`, `project_cc_march_features`, `project_cli_migration_s226` (done), `project_post_promo_rate_reality`
- Superseded project states: `project_s94_loop_seniordev_audit`, `project_hivemind_rollout`, `project_hivemind_vision` (if superseded by later work)
- Redundant feedback pairs: `feedback_slow_build_mt20_mt21` + `feedback_no_rush_hivemind` (same message), `feedback_3chat_correctness_first` + `feedback_stick_with_2chat` (overlapping)
- Entries whose content is already enforced by CLAUDE.md rules (e.g., cardinal safety pointers)

**What to keep:**
- All active feedback entries covering Matthew's preferences
- Active project states (current MT priorities, financial sustainability goal)
- All reference entries (they're short)
- Model configuration entries (opus/sonnet assignments)

**Safety:** git commit first. MEMORY.md is an index — the actual memory files aren't deleted.

### 17B. titanium-field-names.md Scope Fix (~5 min)
Global file loading in every CCA session — Kalshi-only content.
- Copy: `~/.claude/rules/titanium-field-names.md` → `polymarket-bot/.claude/rules/`
- Verify polymarket-bot/.claude/rules/ directory exists (create if not)
- Delete from `~/.claude/rules/`
- ~52 lines removed from global load permanently

### 17C. COMMANDS.md Split (~15 min)
6.9KB of all-project tables loads everywhere. CCA sessions don't need Kalshi/GSD tables.
- Create `~/.claude/COMMANDS-CORE.md` with just CCA section + one-liner refs to Kalshi/GSD
- Update `~/.claude/CLAUDE.md`: change `@COMMANDS.md` → `@COMMANDS-CORE.md`
- Keep full `~/.claude/COMMANDS.md` intact (don't delete — still the reference)
- ~120 lines removed from global per-session load

### 17D. mandatory-skills + gsd-framework Merge (~15 min)
130 + 64 = 194 lines, ~7KB — ~40% overlap between the two files.
- Read both files
- Fold unique content from `gsd-framework.md` into `mandatory-skills-workflow.md`
- Delete `gsd-framework.md`
- **CAUTION: global rules — affects Kalshi chats. Read carefully before deleting.**
- ~50 lines removed

### Expected outcome
| Source | Before | After |
|--------|--------|-------|
| MEMORY.md (per turn) | 18KB | ~9KB |
| COMMANDS.md (system prompt) | 6.9KB | ~2KB |
| titanium-field-names (global) | ~1.9KB | 0 in CCA |
| gsd-framework (global) | ~2.3KB | 0 (merged) |
| **Total** | **~55KB** | **~30KB** |

---

## Chat 18 — Original Chat 17 Tasks (Deferred)

- **18A**: Compaction Protection v2 (session_pacer.py compaction detection)
- **18B**: Cross-Chat Delivery — Phase 3+4 results to CCA_TO_POLYBOT.md
- **18C**: Write Phase 5 Plan (CUSTOM_AGENTS_DESIGN.md Phase 5 section)

---

## Warnings for Chat 17
- **DO NOT run `resume_generator.py --force`** — overwrites this file (3rd instance)
- **Token budget**: Sonnet model. No agent spawns. This is pure file editing.
- **git commit before each change** — all edits to global rules are risky
- Tests: 269/353 passing (pre-existing failures, not from Chat 16 work)
