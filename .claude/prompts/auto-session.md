# Autonomous Session Prompt
# Usage: claude -p "$(cat .claude/prompts/auto-session.md)" --dangerously-skip-permissions

Read the following files in order before doing anything else:
1. /Users/matthewshields/Projects/ClaudeCodeAdvancements/PROJECT_INDEX.md
2. /Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md
3. /Users/matthewshields/Projects/ClaudeCodeAdvancements/MASTER_ROADMAP.md

Then run all three test suites and confirm they pass:
- python3 memory-system/tests/test_memory.py
- python3 memory-system/tests/test_mcp_server.py
- python3 spec-system/tests/test_spec.py

If any tests fail, fix them before proceeding. Do not start new work with failing tests.

Find the first incomplete item ([ ]) in the MASTER_ROADMAP.md "Current Completion Summary" table.
Read the full session entry for that item in MASTER_ROADMAP.md.
Follow the Start Prompt for that session exactly.
Build the complete deliverable described — all files, all tests.

When the session task is fully complete:
1. Run all test suites again and confirm passing
2. Update SESSION_STATE.md — mark the completed item, set next session target
3. Update MASTER_ROADMAP.md — mark the completed session as ✅
4. git add the specific files changed
5. git commit with a clear message describing what was built and test counts
6. git push

Constraints:
- Only read/write files inside /Users/matthewshields/Projects/ClaudeCodeAdvancements/
- Python stdlib only unless MASTER_ROADMAP.md explicitly permits an external package
- Never store credentials or tokens in any file
- One session task per run — do not chain into the next task
