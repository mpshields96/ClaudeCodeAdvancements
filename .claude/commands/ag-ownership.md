# /ag-ownership — File Ownership Manifest (AG-2)

Generate a file ownership map from git history to identify conflict risks before
running parallel agents. Shows which sessions recently modified each file and flags
files touched by multiple sessions.

---

## What to do when this command is invoked

1. **Run the ownership script:**
   ```bash
   python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/agent-guard/ownership.py
   ```

2. **Present the output** — show the Markdown report directly.

3. **Highlight any conflict risks:**
   - If the "Conflict Risk Files" section is non-empty, call out those files specifically.
   - If "Uncommitted Changes" is non-empty, note that those files are currently in-flight.

4. **Recommend a course of action** based on findings:
   - No conflicts + no uncommitted changes → "Safe to start parallel agents"
   - Conflict risks present → "Coordinate before running agents that might touch: [files]"
   - Uncommitted changes → "Commit or stash current changes before starting parallel run"

---

## Options

Pass these after the command to customize behavior:

| Option | Effect |
|--------|--------|
| `--commits N` | Analyze last N commits (default: 20) |
| `--hours N` | Only show files changed in last N hours |
| `--conflicts-only` | Only show conflict risk files |
| `--output OWNERSHIP.md` | Write report to a file instead of stdout |

Examples:
```
/ag-ownership --commits 5          → Last 5 commits only
/ag-ownership --hours 4            → Files changed in last 4 hours
/ag-ownership --conflicts-only     → Just the conflict risks
```

---

## When to use this

Run `/ag-ownership` before:
- Starting any parallel agent session (`/gsd:execute-phase` with parallel agents)
- Handing off work to another Claude Code session
- Unsure which files another process has recently modified
