# CCA Learnings — Severity-Tracked Patterns
# Severity: 1 = noted, 2 = hard rule, 3 = global (promoted to ~/.claude/rules/)
# Append-only. Never truncate.

---

### Anthropic key regex must include hyphens — Severity: 3 — Count: 3
- **Anti-pattern:** `sk-[A-Za-z0-9]{20,}` (misses keys with hyphens)
- **Fix:** `sk-[A-Za-z0-9\-]{20,}` (keys contain `sk-ant-api03-...`)
- **First seen:** 2026-02-19
- **Last seen:** 2026-03-15
- **Files:** any credential scanning or validation

---

### PreToolUse deny format vs Stop hook block format differ — Severity: 2 — Count: 2
- **Anti-pattern:** Using same format for both hook types. Top-level `{"decision": "block"}` on PreToolUse silently fails.
- **Fix:**
  - PreToolUse deny: `{"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "..."}}`
  - Stop hook block: `{"decision": "block", "reason": "..."}`
- **First seen:** 2026-02-20 (Session 2)
- **Last seen:** 2026-03-08 (Session 8)
- **Files:** any hook that needs to block or deny

---

### Claude Code transcript usage field location — Severity: 2 — Count: 1
- **Anti-pattern:** Reading `entry.get("usage", {})` on all entries — returns 0 for real transcripts
- **Fix:** For `type == "assistant"` entries, usage is at `entry["message"]["usage"]`. Sum: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
- **First seen:** 2026-03-08 (Session 8 CTX-1 bug fix)
- **Last seen:** 2026-03-08
- **Files:** `context-monitor/hooks/meter.py`, any transcript parser

---

### argparse subparsers don't inherit parent options — Severity: 1 — Count: 1
- **Anti-pattern:** Adding `--project` to the parent parser expecting subcommands to inherit it
- **Fix:** Add `--project` explicitly to each subparser that needs it
- **First seen:** 2026-03-08 (Session 8, memory-system/cli.py)
- **Last seen:** 2026-03-08
- **Files:** any CLI using argparse subparsers

---

### Commit discipline — work must be committed before session close — Severity: 2 — Count: 1
- **Anti-pattern:** Completing and testing multiple features across sessions without committing — leaves 80+ untracked files as recovery liability
- **Fix:** Commit each task when tests pass. Never close a session with untracked deliverables.
- **First seen:** 2026-03-15 (Session 9 — sessions 7+8 work never committed)
- **Last seen:** 2026-03-15
- **Files:** session workflow (applies to all sessions)

---
