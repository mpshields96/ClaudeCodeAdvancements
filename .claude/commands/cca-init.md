# /cca-init — ClaudeCodeAdvancements Session Startup

Run the full session startup ritual. No user input needed — execute every step autonomously.
After init completes, if Matthew says nothing or runs /cca-auto, proceed to autonomous work immediately.

---

## Step 1 — Orient (parallel reads)

Read these three files in parallel:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/PROJECT_INDEX.md`
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md`

Extract and note:
- Current frontier being worked on
- Last session number and date
- Next planned work item
- Total test count expected

---

## Step 2 — Run all test suites

Discover and run ALL test files:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

If any test fails: report it prominently but continue startup.

---

## Step 3 — Surface relevant findings (resurfacer)

After reading SESSION_STATE.md (Step 1), determine the current work context:
- What module/frontier is being worked on?
- What MT tasks are next?

Run the resurfacer to surface past findings relevant to the upcoming work:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
# Surface by next MT task (extract from SESSION_STATE next actions)
python3 self-learning/resurfacer.py FINDINGS_LOG.md --mt MT-<N> --limit 5 2>/dev/null
# Surface by module if working on a specific frontier
python3 self-learning/resurfacer.py FINDINGS_LOG.md --module <module-name> --limit 5 2>/dev/null
```

If findings are returned, include the top 3-5 in the briefing under a "RELEVANT FINDINGS:" section.
If no findings match or FINDINGS_LOG.md doesn't exist, skip silently.

---

## Step 4 — Check git status

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status --short && git log --oneline -5
```

Note any uncommitted changes or work-in-progress from a previous session.

---

## Step 5 — Display session briefing

Output a concise briefing in this exact format:

```
CCA SESSION [N+1] — [today's date]

Tests: [passed]/[total] [OK or FAILING]
Git: [clean / N uncommitted files]
Last session: [date] — [what was done]

NEXT UP: [specific next work item from SESSION_STATE]

RELEVANT FINDINGS: [top 3-5 resurfaced findings if any match, otherwise omit this section]

Ready to work. Run /cca-auto for autonomous mode, or describe what to build.
```

Where [N+1] is the next session number (one more than what SESSION_STATE shows).

---

## Rules

- Execute all steps autonomously — do not ask for confirmation
- If any test suite fails, report it prominently but continue startup
- Do not modify any files during init — read-only operation
- Keep the briefing under 15 lines
- If /cca-auto follows immediately, do NOT repeat the test run — init already verified tests pass
