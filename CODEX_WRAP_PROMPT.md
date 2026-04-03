Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Current branch: main.

Substantive git changes to account for:
- none

Runtime/generated session artifacts to ignore unless explicitly asked:
- [ M] .queue_hook_last_check
- [ M] cca_internal_queue.jsonl
- [ M] session_timings.jsonl
- [??] .session_pids/

Recent commits for context:
- f36314b S256: wrap — SESSION_STATE + SESSION_RESUME for S257
- 50a0022 S256: add repo-aware Codex terminal workflow
- 2c97bef S256: runtime state + MT53 completion plan

Wrap checklist:
1. Run the most relevant validation for the substantive changes.
2. Summarize what changed, what passed, and any remaining risks.
3. Commit if there are substantive changes ready to land.
4. Leave runtime/session files alone unless the task explicitly includes them.
5. If the result matters inside CCA, send a direct queue note from codex to desktop and leave a durable note in CODEX_TO_CLAUDE.md when useful.
