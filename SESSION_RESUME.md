---
**RESUME PROMPT (copy-paste into next CCA session):**

Run /cca-init. Last session was S244 Chat 11 on 2026-03-31.
Of note, YOU are chat 12, only do assigned tasks for chat 12.

**What was done (Chat 11):** Pure research + design session. (1) 11A: CC Feature Exploration — tested `--bare`, `/btw`, `--max-turns` (doesn't exist as CLI flag, frontmatter only), mapped all 16 agent frontmatter fields (GSD uses only 4 of 16). Written to `CC_FEATURE_NOTES.md`. (2) 11B: Custom Agent Design — designed 4 CCA-specific agents: `cca-reviewer` (sonnet, maxTurns 30, read-only), `senior-reviewer` (opus, maxTurns 15, can't edit code), `cca-scout` (sonnet, maxTurns 40), `cca-test-runner` (haiku, maxTurns 10). Full frontmatter specs + Command->Agent migration pattern. Written to `CUSTOM_AGENTS_DESIGN.md`. (3) 11C: Agent Teams vs Hivemind — COMPLEMENT verdict. Agent Teams lacks session resumption and cross-project comms (dealbreakers). Keep hivemind for cross-session/cross-project, add Agent Teams for intra-session parallelism. Written to `AGENT_TEAMS_VS_HIVEMIND.md`. (4) 11D: Phase 4 plan (Chats 14-17) written into `TODAYS_TASKS.md`.

**CRITICAL for next chat:** The `references/claude-code-source/` clone is a Python PORT (instructkr/claude-code), NOT the actual TypeScript source. Chat 12A must find and clone the real TypeScript source. Check the R2 zip URL or GitHub mirrors from the 2088-pt Reddit post comments. Verify by finding actual .ts/.tsx files and `compact.ts`.

**What's next (Chat 12 tasks from TODAYS_TASKS.md):**
- **12A.** Clone Actual CC TypeScript Source [TODO] — find real leaked TS source (~1884 files), clone to `references/claude-code-ts/`, verify .ts/.tsx files + compact.ts
- **12B.** Study Coordinator Mode + UDS Inbox [TODO] (~20 min) — read coordinatorMode.ts, compare with cca_comm.py, write `COORDINATOR_MODE_ANALYSIS.md`
- **12C.** Study Compaction Implementation [TODO] (~15 min) — read compact.ts, confirm empty-array diff bug (line ~565), document preCompactDiscoveredTools
- **12D.** CLAUDE.md Token Audit [TODO] (~10 min) — measure token count vs Boris's <1000 advice, write reduction plan
- **12E.** GitHub Scan — Leak Derivatives [TODO] (~15 min, time-boxed) — scan trending repos for CC source analysis tools

**Key files:**
- `TODAYS_TASKS.md` — Chats 10-13 + Phase 4 (Chats 14-17) fully planned
- `CC_FEATURE_NOTES.md` — NEW (Chat 11A feature exploration findings)
- `CUSTOM_AGENTS_DESIGN.md` — NEW (Chat 11B agent design specs — 4 agents with full frontmatter)
- `AGENT_TEAMS_VS_HIVEMIND.md` — NEW (Chat 11C COMPLEMENT verdict)
- `FINDINGS_LOG.md` — 8 entries from Chat 9 (CC source leak, Coordinator Mode, UDS Inbox, Boris tips)
- `references/claude-howto/04-subagents/README.md` — Full agent spec (16 frontmatter fields, Agent Teams docs)
- `references/claude-code-source/` — Python port only, NOT real TS source (12A must fix this)

Tests: 343/349 suites, 12199 total (6 pre-existing failures: pytest module, autoloop drift). Git: main, clean after commit 173a977.

Advancement tip: For 12A, if the R2 zip URL is DMCA'd, check GitHub mirrors created in the 24hrs after the leak (2026-03-30). The 2088-pt r/ClaudeAI post comments had several mirror links. If no mirror survives, the Python port's JSON snapshots still contain the TypeScript type signatures which are useful for 12B/12C study.
