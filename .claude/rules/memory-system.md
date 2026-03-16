---
globs: memory-system/**
---

# Memory System Rules (Frontier 1)

- Memory IDs use 8-char hex suffix minimum (3-char caused collisions at 100 rapid-fire creates)
- Local-first storage at `~/.claude-memory/` — user owns all data, no cloud
- Schema before code — schema.md must be approved before writing capture_hook.py
- Stop hook delivery — Stop has `last_assistant_message` for better context extraction
- Transcript JSONL for explicit memory — "remember/always/never" triggers HIGH confidence
- TTL by confidence: HIGH=365d, MEDIUM=180d, LOW=90d
