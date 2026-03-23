Run /cca-init. Last session was S126 on 2026-03-23.

WHAT WAS BUILT (S126): MT-30 Phase 6 — CCA auto-loop. 3 commits, 43 new tests.
- cca_autoloop.py: Python module with AutoLoopConfig, AutoLoopState, AutoLoopRunner, read_resume_prompt(), build_claude_command(). 43 tests in tests/test_cca_autoloop.py. Handles config, state persistence (~/.cca-autoloop-state.json), audit logging (~/.cca-autoloop.log), safety guards (max iterations, crash detection, short session detection).
- start_autoloop.sh: THE ACTUAL LOOP RUNNER. Bash script that runs claude in foreground (inherits TTY — critical fix). Reads SESSION_RESUME.md, constructs prompt as "/cca-init then review prompt below then /cca-auto\n\n<resume content>", spawns `claude "$FULL_PROMPT"`. When claude exits, reads new SESSION_RESUME.md and loops. Supports --tmux (background), --status, --help. Safety: MAX_ITERATIONS=50, COOLDOWN=15s, 3 consecutive crashes or 3 consecutive short sessions (<30s) = auto-stop.
- session_daemon_cca_only.json: CCA-only daemon config (1 session max).
- VERIFIED WORKING: Launched in tmux, claude started interactive Sonnet 4.6 session, read S125 resume prompt (734 chars), ran /cca-init, began full 204-suite test run autonomously. Killed test to prevent parallel CCA conflicts.
- TTY BUG FOUND+FIXED: Python subprocess.run() doesn't give claude a real TTY when parent stdout is piped. Claude exits immediately. Fix: bash foreground exec.

WHAT MUST BE BUILT NEXT (Matthew S126 explicit directives, in order):

1. MODEL ALTERNATION: Add Sonnet 4.6 / Opus 4.6 alternation to start_autoloop.sh. The `claude` CLI accepts `--model sonnet` or `--model opus`. Options: round-robin (odd iterations=sonnet, even=opus), or smart selection checking rate limit status via statusline data. Add MODEL_STRATEGY env var (round-robin | opus-primary | sonnet-primary). Modify the `claude "$FULL_PROMPT"` line to `claude --model "$MODEL" "$FULL_PROMPT"`. Track which model was used per iteration in the audit log.

2. DESKTOP APP AUTOMATION: Matthew wants visible Terminal.app windows (not hidden tmux). He wants to WATCH the auto-loop with his eyes and INTERACT freely (type messages, give instructions to the running claude session). Build a `--desktop` mode in start_autoloop.sh that uses osascript/AppleScript to: (a) open a new Terminal.app window, (b) cd to project dir, (c) run `claude --model $MODEL "$FULL_PROMPT"`, (d) window stays visible and interactive. The bash loop itself runs in a controller terminal; each claude session opens in its own visible Terminal.app window. When claude exits, the window closes and the controller spawns the next one.

3. MT-30 PHASE 7: Supervised dry run with model alternation + desktop mode working together.

FILES TOUCHED: cca_autoloop.py (NEW, 302 LOC), tests/test_cca_autoloop.py (NEW, 43 tests), start_autoloop.sh (REWRITTEN, 209 LOC), session_daemon_cca_only.json (NEW), MASTER_TASKS.md (MT-30 Phase 6 status), PROJECT_INDEX.md (new files + test count 8083/204), SESSION_STATE.md (S126 state).

Tests: 8083 passing (204 suites). Git: 3 commits ahead of S125.
