Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Current branch: main.

Substantive git changes to account for:
- [ M] SESSION_RESUME.md

Runtime/generated session artifacts to ignore unless explicitly asked:
- [ M] .queue_hook_last_check
- [ D] .session_pids/desktop.pid
- [ M] session_timings.jsonl

Recent commits for context:
- 1a52288 S214: Wrap — docs, self-learning, project index
- 5ee284a S214: Update session state and project index
- 8387d70 S214: Add RedAgent subclass for Pokemon Red agent loop (MT-53)

Wrap checklist:
1. Run the most relevant validation for the substantive changes.
2. Summarize what changed, what passed, and any remaining risks.
3. Commit if there are substantive changes ready to land.
4. Leave runtime/session files alone unless the task explicitly includes them.
5. If the result matters inside CCA, send a direct queue note from codex to desktop.
