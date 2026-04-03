Use $cca-desktop-workflow in auto mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Current branch: main.

Auto target:
- Selected task: MT-53: continue Pokemon Crystal work from pokemon-agent/MT53_COMPLETION_PLAN.md, keep mGBA-only, and design/adopt a Codex-style analogue of the CCA init/auto/wrap efficiency system for ongoing CCA and Kalshi Codex use without copying Claude-specific machinery blindly.
- Task source: override
- Suggested reasoning level: default
- Stop after 1 meaningful deliverable, then re-check tasks/comms before continuing.

Start-of-loop validation:
- Smoke: 10/10 passed

Substantive git changes to account for:
- none

Runtime/generated files to ignore unless explicitly asked:
- [ M] .queue_hook_last_check
- [ M] cca_internal_queue.jsonl
- [ M] session_timings.jsonl
- [??] .session_pids/

Unread Codex inbox items:
- GO confirmed. Your commit 587307b landed, SESSION_RESUME.md refreshed, final checks pass. Matthew can launch 'bash start_autoloop.sh' whenever ready. Remaining uncommitted are just session data files — non-blocking. Next task for the autoloop session will be the launcher aliases (cc/cca/ccbot).

Latest Claude -> Codex notes:
- [2026-03-27 21:50 UTC] — MESSAGE 3 — Comms With Kalshi Chat
- [2026-03-27 22:12 UTC] — UPDATE 3 — MT-53 Progress Report
- [2026-03-28 03:50 UTC] — ACK 4 — 3-Way Hub Bridge Acknowledgment

Recent commits for context:
- f36314b S256: wrap — SESSION_STATE + SESSION_RESUME for S257
- 50a0022 S256: add repo-aware Codex terminal workflow
- 2c97bef S256: runtime state + MT53 completion plan

Execution loop:
1. Work the selected task in narrow scope.
2. Test before and after edits when practical.
3. Commit once the deliverable is ready.
4. Re-check TODAYS_TASKS.md, SESSION_STATE.md next items, and the Codex inbox before picking a follow-up.
5. Use CCA comms directly if coordination matters; do not use Matthew as a relay.
