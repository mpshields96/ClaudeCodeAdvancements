# NEXT CHAT HANDOFF

## Start Here
Run /cca-init. Last session S264 on 2026-04-05.

COMPLETED (Chat 35 — S264):
  35A. /review adversarial code review slash command (BUILD #12)
       - ~/.claude/commands/review.md — main command (routes by arg: staged diff, HEAD, file, PR)
       - ~/.claude/commands/references/review-criteria.md — P0-P3 defs, author-aligned filter
       - ~/.claude/commands/references/review-output-format.md — VERDICT block format
       - Adapted from OpenAI Codex prompt (open source). Commit 6d2aa4b.
  35B. context-monitor 4 advisory signals — commit 9a24138
       - Signal 1 (meter.py): cache bust detection — ratio<0.5 on non-first turn → one-shot warning
       - Signal 2 (session_start.py): CLAUDE_CODE_RESUME env var → warns caching disabled
       - Signal 3 (session_start.py): CLAUDE.md >3KB → warns re-sent every turn
       - Signal 4 (alert.py): CLAUDE_CODE_DISABLE_1M_CONTEXT tip in red/critical alerts
       - 21 new tests passing. Test gotcha: Path.home() mock needs two-temp-dir pattern.

NEXT (Chat 36 — TODAYS_TASKS.md §CHAT 36):
  36A. Wire collision_reader_crystal into main.py (MT-53)
       - Replace build_intro_navigator with build_intro_navigator_with_collision in
         crystal_intro_navigation.py and main.py. Smoke test offline mode. Commit.
  36B. Blast radius import graph for agent-guard
       - Create agent-guard/blast_radius.py (ast stdlib): forward/reverse dep dict,
         blast_radius(file) = len(reverse_deps[file]), high_risk flag for >5
       - Add blast_radius field to agent_guard/ownership.py manifest output
       - Tests: known import graph → correct values, high_risk fires at threshold, zero-dep=0

Tests: 362/373 passing (11 pre-existing failures unrelated to our work).
Git: clean after S264 wrap commit.
