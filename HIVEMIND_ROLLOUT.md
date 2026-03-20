# Hivemind — Phased Rollout Plan
# Session 77 — 2026-03-20
# Purpose: Prove 2-chat before 3-chat, with validation gates at each phase

---

## Matthew's Directive (S77, verbatim)

> "If we do it slower and properly, I'd like to eventually test and prove with
> a few sessions of work that CCA chat on desktop app with only ONE ClaudeCode
> terminal CLI chat acting as a hivemind helper or as the senior developer coder
> chat helper would make me more secure."

> "Seeing the success and proper execution of that two chat setup over several
> sessions before then safely escalating to the three chat setup."

**Translation**: Incremental validation. 2-chat must be proven before 3-chat.
Proven = multiple sessions of successful, non-buggy coordinated output.

---

## What Exists Today

### Infrastructure (built S72-S90, tested, passing)

| Component | LOC | Tests | Status |
|-----------|-----|-------|--------|
| cca_hivemind.py | 625 | 22 | Process detection, AppleScript injection, safety validation |
| cca_internal_queue.py | 584 | 69 | JSONL queue, scope tracking, conflict detection, preflight |
| cca_comm.py | 249 | 18 | CLI wrappers (inbox, say, task, claim, release, done, shutdown) |
| loop_health.py | 251 | 54 | Session health grading, regression detection |
| queue_injector.py | ~150 | 19 | UserPromptSubmit hook for queue context injection |
| launch_worker.sh | 56 | -- | One-command worker launcher (Terminal tab + AppleScript) |
| hivemind_session_validator.py | 170 | 17 | Desktop-side cycle validation + Phase 1 gate tracking |
| hivemind_metrics.py | 149 | 20 | Phase 1 validation metrics persistence (built by cli1 worker) |
| test_hivemind_deep.py | ~600 | 117 | Deep coverage: shutdown, collisions, stress, edge cases |

**Total: ~2,834 LOC, 336 tests, all passing.**

### What's Been Proven

- **S72**: First 3-chat hivemind sprint. Desktop coordinated 2 CLI chats to build
  6 MT-20 modules. Resulted in 198 new tests, all passing. File ownership via queue
  scope claims worked — no merge conflicts.
- **S74**: Skills made hivemind-aware (/cca-init, /cca-auto, /cca-wrap skip shared
  doc updates when running as worker). loop_health wired to record sessions.

### What Has NOT Been Proven

1. ~~**Sustained 2-chat operation** — S72 was a single sprint.~~ **S90: First validated live test PASS. Queue-based task cycle proven.**
2. **Error recovery** — What happens when a CLI chat crashes mid-scope-claim?
3. ~~**Queue reliability under real load** — Only ~20 messages have ever gone through.~~ **S89-90: 117 deep tests + live queue cycle proven.**
4. ~~**AppleScript injection reliability**~~ **S90: launch_worker.sh opens Terminal tab, worker starts autonomously.**
5. **Worker productivity** — Overhead ratio not yet measured across multiple sessions.

---

## Phase 1: Validated 2-Chat Operation (Desktop + 1 CLI)

### Goal
Prove that Desktop CCA + 1 CLI chat produces higher quality work than Desktop alone,
over 3-5 sessions, without coordination failures.

### Setup
- Desktop: CCA coordinator (runs /cca-init, /cca-auto, /cca-wrap, owns all shared docs)
- CLI 1: Worker (receives tasks via queue, commits code, sends done summaries)

### What the CLI Worker Does
The CLI worker should handle one of these roles per session:
- **Builder**: Receives a specific task (e.g., "build test_foo.py"), executes, commits, reports back
- **Reviewer**: Reviews Desktop's recent commits, provides feedback via queue
- **Researcher**: Deep-dives a topic (reads files, analyzes patterns, reports findings via queue)

### Validation Metrics (measured per session)

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Coordination failures | 0 | Queue errors, scope conflicts, merge conflicts |
| Worker task completion | 100% | Tasks assigned vs. tasks completed |
| Regression rate | 0% | Tests passing before and after worker commits |
| Overhead ratio | <15% | Time spent on coordination vs. time spent on actual work |
| Quality parity | >= Desktop-only | loop_health grades for coordinated vs. solo sessions |

### Phase 1 Validation Log

| Session | Date | Worker | Task | Verdict | Conflicts | Notes |
|---------|------|--------|------|---------|-----------|-------|
| S90 #1 | 2026-03-20 | cli1 | hivemind_metrics.py (149 LOC, 20 tests) | PASS | 0 | First live test. Full cycle: assign->pickup->build->commit->report->release. |
| S90 #2 | 2026-03-20 | cli1 | hivemind_dashboard.py (4.3K, 16 tests) | PASS | 0 | Integration task: imported 2 existing modules, fixed import path issue. |
| S90 #3 | 2026-03-20 | cli1 | Integrate overhead_timer into dashboard | IN PROGRESS | - | Modify existing code task. |

**Automated tracking**: `hivemind_sessions.jsonl` + `hivemind_session_validator.py`
**Gate status**: `python3 -c "import hivemind_session_validator as hsv; print(hsv.format_for_init())"`

### Gate to Phase 2
ALL of the following must be true across 3+ sessions:
- [x] Zero coordination failures (no scope conflicts, no queue corruption) — S90 #1 PASS
- [x] Worker completed all assigned tasks in every session — S90 #1 completed
- [x] No test regressions introduced by worker commits — 3518 total after worker commit
- [ ] Matthew subjectively confirms: "this is better than solo"
- [ ] Overhead ratio measured and documented

### Known Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| AppleScript injection fails | Use queue-only communication (no injection needed for Phase 1) |
| CLI chat crashes mid-scope | Add scope timeout — auto-release after 30 min inactivity |
| Queue gets corrupted | Add queue health check to /cca-init |
| Worker produces low-quality code | Desktop reviews worker commits before doc updates |

---

## Phase 2: Hardened 2-Chat Operation (3-5 more sessions)

### Goal
Stress-test the 2-chat model with harder tasks and edge cases.

### What Changes From Phase 1
- Worker handles multi-file tasks (not just single-file assignments)
- Worker handles tasks that require reading Desktop's recent work first
- Worker operates more autonomously (less hand-holding from Desktop)
- Queue handles higher message volume (50+ messages per session)
- Error recovery tested: deliberately kill CLI chat mid-task, verify clean recovery

### Validation Metrics

Same as Phase 1, plus:
| Metric | Target | How to Measure |
|--------|--------|---------------|
| Multi-file task success | 100% | Complex tasks completed without conflicts |
| Recovery success | 100% | Clean state after deliberate crash |
| Queue throughput | 50+ msgs/session | Message count in queue file |

### Gate to Phase 3
ALL of the following must be true:
- [ ] Phase 1 gate fully passed
- [ ] 3+ sessions of hardened 2-chat operation without failures
- [ ] At least 1 successful crash recovery test
- [ ] Worker handles multi-file tasks without conflicts
- [ ] Matthew confirms: "ready for a second worker"

---

## Phase 3: 3-Chat Operation (Desktop + 2 CLI)

### Goal
Prove that adding a second CLI worker provides additional value without
introducing coordination complexity that cancels the benefit.

### Setup
- Desktop: CCA coordinator (same as Phase 1-2)
- CLI 1: Primary worker (builder/implementer)
- CLI 2: Secondary worker (reviewer/researcher OR second builder on independent tasks)

### Critical Difference From S72
S72 ran a 3-chat sprint but:
- All tasks were pre-assigned (no dynamic coordination needed)
- No inter-worker communication (workers didn't need to read each other's output)
- Single session (no proof of sustained operation)

Phase 3 must prove:
- Dynamic task assignment (Desktop decides who gets what based on progress)
- Inter-worker awareness (CLI 2 knows what CLI 1 is working on via scope claims)
- Sustained operation across 3+ sessions
- Net productivity gain over 2-chat (measured, not assumed)

### Validation Metrics

Same as Phase 2, plus:
| Metric | Target | How to Measure |
|--------|--------|---------------|
| Inter-worker conflicts | 0 | Scope claim collisions between CLI 1 and CLI 2 |
| Net productivity vs 2-chat | >20% improvement | Tasks completed per session |
| Coordination overhead | <20% combined | Time on coordination vs. work |

### Gate to Production
- [ ] Phase 2 gate fully passed
- [ ] 3+ sessions of 3-chat operation without failures
- [ ] Measured productivity improvement over 2-chat
- [ ] Matthew confirms: "this is how I want to work"

---

## What NOT To Build Yet

The following are Phase 4+ ideas. Do NOT start them until Phase 3 is proven:
- Automatic task decomposition (Desktop auto-splits work for workers)
- Worker-to-worker direct communication (bypassing Desktop coordinator)
- More than 3 chats
- Overnight hivemind operation (daytime supervised only until Phase 3 passes)
- Cross-project hivemind (CCA + Kalshi workers in same hivemind)

---

## Relationship to Senior Dev Agent

The Senior Dev vision (SENIOR_DEV_GAP_ANALYSIS.md Phase 3) describes the CLI chat
running as a senior dev colleague. This is a SPECIFIC ROLE within the hivemind:

- Hivemind Phase 1-2: CLI worker does general tasks (build, test, research)
- Senior Dev Phase 3: CLI worker runs with a senior-dev persona (reviews, advises)
- These converge: a proven 2-chat hivemind + a proven senior dev skill = a CLI chat
  that acts as your senior developer colleague

The hivemind infrastructure enables the senior dev experience. They're not competing
projects — they're the same project at different layers:
- Hivemind = transport + coordination (queue, scope, injection)
- Senior Dev = intelligence + review quality (analysis, advice, context)

---

## Current Recommended Next Steps

1. **This session (S77)**: Document everything (this file + gap analysis). No code.
2. **Next session**: Phase 1 prep — add queue health check to /cca-init, add scope
   timeout, write the worker role CLAUDE.md (persona instructions for CLI worker).
3. **Session after**: First real Phase 1 test — Desktop + 1 CLI on a real task.
4. **Continue**: Iterate Phase 1 for 3-5 sessions, measuring metrics.

---

*Written: Session 77, 2026-03-20*
*Principle: Measure twice, cut once. Prove small before scaling up.*
