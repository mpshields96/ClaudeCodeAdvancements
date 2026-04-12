# NEXT CHAT HANDOFF — S302

## Start Here
Run /cca-init. Then read this file — it contains the specific task for S302.
DO NOT run /cca-auto. This session has a specific gated task (upload + smoke test).

## Repo State
- Repo: /Users/matthewshields/Projects/ClaudeCodeAdvancements
- Last wrapped session: S301 (2026-04-12)
- Phase: Claude Project upload gate. Docs patched and validated. Awaiting upload + live smoke test.

## S302 SPECIFIC TASK — Upload + Smoke Test Gate

**This is Chat 1 of the Codex multi-chat sequence (CODEX_TO_CLAUDE.md:247).**

### Step 1 — Give Matthew the upload click path

Tell Matthew to do exactly this in claude.ai (web or iPhone):
1. Go to claude.ai → Projects → Create new project: name it `Leagues 6 Planner`
2. Upload these 7 files from `leagues6-companion/claude-project/` (drag all at once or one by one):
   - `00_README.md`
   - `01_OVERVIEW.md`
   - `02_FACTS_REFERENCE.md`
   - `03_BUILD_ADVISOR.md`
   - `04_MATTHEW_BUILD.md`
   - `05_COMMUNITY_META.md`
   - `06_QUERY_EXAMPLES.md`
3. Do NOT upload `manifest.json`
4. Wait for upload to complete (no confirmation needed — just proceed)

### Step 2 — Give Matthew the 5 smoke prompts (copy-paste ready)

Tell Matthew to run these 5 prompts in the Project, one at a time, and paste the answers back:

**Prompt 1 (melee identity check):**
```
Give me a melee-first Leagues 6 build using the uploaded docs only. Keep it truly melee-focused, not a magic build in disguise. Explain regions, relic direction, and why this works.
```

**Prompt 2 (ranged identity check):**
```
Give me a ranged build and clearly explain crossbow versus thrown/atlatl style tradeoffs from the uploaded docs only.
```

**Prompt 3 (multi-build comparison check):**
```
Compare magic vs melee vs ranged for a casual/AFK-leaning player. Tell me where the uploaded docs show strong consensus, where they show splits, and what tradeoffs change by style.
```

**Prompt 4 (T6 freshness check):**
```
What should I know about Tier 6 right now, especially Eternal Sustenance? Separate hard facts from current uncertainty and do not overstate confidence.
```

**Prompt 5 (source-discipline check):**
```
Answer using only the uploaded docs and tell me which doc each major claim came from. If a claim is not well supported, say so clearly.
```

### Step 3 — After Matthew pastes answers

For each prompt, evaluate against Codex's pass criteria (CODEX_TO_CLAUDE.md:351-408):
- Prompt 1 PASS: melee stays melee, names melee-specific archetype logic, does NOT pivot back to magic
- Prompt 2 PASS: ranged stays ranged, crossbow and thrown paths remain distinct
- Prompt 3 PASS: all three styles get real treatment, no magic-only behavior
- Prompt 4 PASS: Eternal Sustenance treated as live/freshness-sensitive, avoids false certainty
- Prompt 5 PASS: Claude cites correct file roles, unsupported claims softened

**If all 5 pass:** Proceed to Step 4 (productionize state). Do NOT open more doc work.

**If any fail:** Patch ONLY the specific source doc per the failure-to-doc routing table (CODEX_TO_CLAUDE.md:386-414). Re-run only the failed prompt + one regression check. Do NOT rewrite the whole pack.

### Step 4 — Write Codex verification report to CLAUDE_TO_CODEX.md

Required per CODEX_TO_CLAUDE.md:318 (no self-cert rule). Must include:
- exact 7 files uploaded
- manifest.json skipped confirmation
- prompt list used
- 1-2 sentence summary of each answer
- any combat-style collapse or T6 false certainty found
- whether a correction/re-upload was needed

### Step 5 — Update SESSION_STATE.md

If pack passes smoke test: mark Claude Project as `pushed_to_github` / live for user testing.
Write SESSION_RESUME.md for S303 (productionize wrap or correction loop).

## Coordination
- CCA->Codex: S301 POST-FLIGHT written (CLAUDE_TO_CODEX.md, 2026-04-12 UTC)
- Codex has 4 ACTION NEEDED entries — all acked in S301 PRE-FLIGHT
- Codex->CCA: [2026-04-12 18:05 UTC] LEAGUES6 FINISH PLAN (CODEX_TO_CLAUDE.md:222) — primary guide
- Codex->CCA: [2026-04-12 13:13 UTC] LEAGUES6 EXECUTION PLAN (CODEX_TO_CLAUDE.md:247) — multi-chat sequence
- Codex->CCA: [2026-04-12 13:16 UTC] NO SELF-CERT rule (CODEX_TO_CLAUDE.md:318)
- Codex->CCA: [2026-04-12 13:22 UTC] SMOKE MATRIX (CODEX_TO_CLAUDE.md:344)
- CCA->Kalshi: stale 4d — cross-chat board shows URGENT items; address in a Kalshi session not this one

## Leagues6 State (entering S302)
- 7 docs, 67.5KB total, validator GATE PASSED (leagues6 venv)
- Last commit: f7cab9e (S301 pre-upload patches)
- leagues6 repo: ahead of origin by 6 commits — push before upload if desired
- April 15 launch in 3 days

## Fresh-Chat Rule
/cca-init → read this file → do NOT /cca-auto → execute steps above.

