# CCA Operational Hardening Plan — 2026-04-11

Purpose: keep CCA performing at a high level despite current Claude Code quality
regression, caching instability, and long-session drift.

This is not a generic best-practices doc.
It is a temporary operating mode for a degraded upstream environment.

---

## Executive Summary

CCA should assume the upstream agent is now:
- more volatile
- less trustworthy on first pass
- more likely to shortcut or self-certify
- more likely to waste budget during long or contaminated sessions

Therefore CCA must shift from "smart autonomous builder" to:
- narrower-task executor
- stricter verifier
- earlier wrapper
- explicit model/router operator
- mandatory second-opinion consumer on meaningful work

The goal is not to make Claude "good again."
The goal is to make the harness strong enough that CCA remains useful even when
Claude is weaker.

---

## Phase 1 — Launch Settings

These are the highest-leverage settings changes because they affect every session.

### 1. Shell-level env vars, not `settings.json.env`

Per S294 community review, anything meant to affect the main Claude process should
be treated as a shell-launch concern until directly disproven.

CCA should:
- stop recommending `settings.json.env` for main-process quality controls
- verify shell env at session start for any performance/quality flags that matter
- explicitly log whether those flags are active in pre-flight notes

If Matthew keeps using Anthropic during this degraded period, CCA should verify at init:
- `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`
- `CLAUDE_CODE_EFFORT_LEVEL`
- `MAX_THINKING_TOKENS`
- `CLAUDE_CODE_DISABLE_1M_CONTEXT`

Important:
- CCA should report whether these are set
- CCA should NOT claim they are effective unless the behavior was locally observed

### 2. Default model posture

Until upstream quality is proven restored:
- default routine work to **Sonnet 4.6**
- use explicit **`claude-opus-4-5`** only for hard reasoning / architecture / research
- do NOT assume Opus 4.6 is the premium default

Operational rule:
- if a task is broad, ambiguous, or high-stakes, CCA must state the model assumption
- if no model pin is available, CCA should behave as if reasoning depth is unreliable

### 3. Budget-aware launch discipline

CCA already has the tooling:
- `token_budget.py`
- `overhead_tracker.py`

CCA should use them as real controls, not decorative status lines.

Rules:
- Peak hours: only narrow work, no discretionary exploration
- Shoulder hours: one meaningful task only
- Off-peak: research, review, deeper scans, heavier verification

---

## Phase 2 — In-Session Operating Rules

### 4. Narrow task grain by default

New default unit of work:
- one file
- one function
- one narrow behavior change
- one verified conclusion

Avoid in one session:
- mixed build + redesign + research + docs + deployment
- broad "fix everything" asks
- multiple speculative changes before first verification

Practical cap:
- no more than **2 meaningful deliverables** per session unless each is tiny and verified

### 5. Read-before-write on critical paths

CCA should treat critical files as read-verify-write zones:
- `SESSION_STATE.md`
- `SESSION_RESUME.md`
- `PROJECT_INDEX.md`
- command docs
- hook/config files
- any file with structured tables or state continuity

Operational rule:
- no edit of these files without first reading the exact current text in-session
- no trust in stale memory of those files

### 6. Explicit acceptance criteria before edits

Before meaningful work, CCA should state:
1. exact file scope
2. acceptance criteria
3. verification method
4. what it will NOT touch

This is especially important now because degraded agents tend to drift or overreach.

### 7. Ban self-certification on important work

CCA should no longer mark meaningful work "done" based on narrative confidence.

"Meaningful work" includes:
- architecture changes
- multi-file changes
- any deployment-adjacent change
- state/handoff file changes
- cross-chat protocol changes
- external repo delegation
- research conclusions affecting subscription/tool choices

For these, CCA must have one of:
- direct test/verification evidence
- Codex review
- both

### 8. Earlier session wrapping

CCA should stop riding sessions deep into contamination.

New pacing target:
- prefer **60-90 minute** effective sessions over long, sprawling ones
- wrap sooner if:
  - 2 meaningful tasks are complete
  - context turns yellow late in session
  - the chat starts repeating itself
  - quality feels "off" even before formal failure

Use existing tool:
- `context-monitor/session_pacer.py`

Operational posture:
- "fresh session" is now a quality tool, not a last resort

---

## Phase 3 — Verification Layer

### 9. Make verification mandatory, not optional

CCA already has the right primitives:
- quick smoke suite
- full test runner
- `worker_verifier.py`
- `agent-guard/senior_review.py`

New rule set:

For any code change:
- run at least targeted verification

For any nontrivial Python change:
- run `senior_review.py` on changed files before wrap when feasible

For any meaningful worker-like output, including CCA's own:
- use `worker_verifier.py` logic conceptually:
  - tests pass
  - no regression in test count where relevant
  - working tree/commit state is explicit

### 10. Label every test count by domain

CCA must stop writing naked test numbers.

Allowed:
- `[CCA-root] 10/10 smoke suites, 543 tests`
- `[leagues6] pytest -q → 270 passed`

Forbidden:
- `270 tests passing`
- `1 suites`
- `355/374 suites` without domain and timestamp

### 11. Split facts from inferences in research

For degraded-agent periods, CCA research outputs should explicitly separate:
- what a source claimed
- what CCA verified
- what CCA infers
- what remains uncertain

This matters for:
- subscription decisions
- model-regression claims
- vendor trust conclusions

---

## Phase 4 — Codex Review Protocol

### 12. Codex as mandatory reviewer for defined classes of work

CCA should route these to Codex review by default:
- architecture decisions
- state hygiene / bridge / handoff changes
- multi-file refactors
- external repo delegation plans
- research that changes Matthew's spending/tool decision
- any session where CCA itself was called out for quality drift

### 13. Review handoff contract

When CCA asks Codex to review or own work, it must include:
- exact repo path
- pinned commit baseline
- owned files
- frozen files
- test command
- gate command
- exact question for Codex

This prevents parallel-agent ambiguity and stale-context collisions.

### 14. CCA should consume Codex review as a gate, not decoration

If Codex flags:
- conflicting state
- weak verification
- under-specified delegation
- sloppy test reporting

CCA should fix that before more feature work.

---

## Phase 5 — Wrap / Handoff Hygiene

### 15. Every wrap must include these fields

Required:
- what changed
- what was verified
- what remains unverified
- exact next step
- labeled test domains
- deployment status language from controlled vocabulary

### 16. Controlled vocabulary for deployment state

CCA should use only these states:
- `in_development`
- `deploy_prep_complete`
- `pushed_to_github`
- `deployed_to_streamlit_cloud`
- `post_deploy_verified`

Do not use vague labels like:
- `deployed`
- `live` alone
- `ready` without context

### 17. Canonical bridge lane

CCA must treat these as canonical unless Matthew explicitly changes protocol:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md`

No silent switching to another repo-local bridge lane.

---

## Phase 6 — What CCA Should Actually Do Next

1. Canonicalize shell-env verification in `/cca-init`
2. Add explicit model/status line to init briefing:
   - model in use
   - quality-control env flags observed
3. Lower practical session trust horizon:
   - 60-90 min target
   - max 2 meaningful deliverables
4. Make labeled test domains mandatory in state/resume/wrap outputs
5. Treat Codex review as required for meaningful work until Matthew says otherwise
6. Keep a small "degraded upstream mode" checklist visible in init/wrap flow

---

## Suggested Temporary Rule Block For CCA

If CCA wants a concise operating block, use this:

1. Assume first-pass quality is unreliable.
2. Scope narrowly.
3. Read before editing critical files.
4. Verify every meaningful change.
5. Wrap earlier than usual.
6. Label every test count by domain.
7. Use canonical CCA-root Codex bridge files only.
8. Do not self-certify architecture or state changes.
9. Escalate meaningful work to Codex review.
10. Prefer portable workflow over vendor trust.

---

## Final Principle

The right response to current Claude degradation is not more pleading.
It is stronger process.

CCA remains useful if the harness becomes stricter than the model is reliable.
