---
globs: context-monitor/**
---

# Context Monitor Rules (Frontier 3)

- Transcript path: `~/.claude/projects/<project_hash>/<session_id>.jsonl`
- Token extraction: `entry["message"]["usage"]` from assistant entries
- Zones: green (<50%) / yellow (50-70%) / red (70-85%) / critical (>=85%)
- State file: `~/.claude-context-health.json` (atomic writes only)
- Stop hook block format: `{"decision": "block", "reason": "..."}` — NOT hookSpecificOutput
- PreToolUse alert: silent for cheap tools (Read/Glob/Grep), warns on expensive tools in red/critical
- Compact anchor writes every 10 turns — may trigger system-reminder context burn (under investigation)
