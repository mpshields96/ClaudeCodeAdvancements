Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Current branch: codex/codex-desktop-autoloop.

Substantive git changes to account for:
- [ M] CODEX_DESKTOP_WORKFLOW.md
- [ M] CODEX_QUICKSTART.md
- [ M] codex-skills/cca-desktop-workflow/SKILL.md
- [??] CODEX_WRAP_PROMPT.md
- [??] codex_wrap.py
- [??] tests/test_codex_wrap.py

Runtime/session artifacts to ignore unless explicitly asked:
- [ M] .queue_hook_last_check
- [ M] .session_pids/desktop.pid
- [ M] cca_internal_queue.jsonl
- [ M] self-learning/journal.jsonl

Recent commits for context:
- aad0aff S214: Add warp data + cross-map A* navigation for Pokemon Red (MT-53)
- 7bf4ccf S213: Update session state and project index
- b2b9aed S213: Wire collision maps for A* pathfinding in live play (MT-53)

Wrap checklist:
1. Run the most relevant validation for the substantive changes.
2. Summarize what changed, what passed, and any remaining risks.
3. Commit if there are substantive changes ready to land.
4. Leave runtime/session files alone unless the task explicitly includes them.
5. If the result matters inside CCA, send a direct queue note from codex to desktop.
