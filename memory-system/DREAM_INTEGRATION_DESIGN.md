# Dream Integration Design — CCA Memory System x Anthropic AutoDream

**Author:** CCA S239 | **Status:** Design Note (no code) | **Date:** 2026-03-30

---

## What AutoDream Does

Anthropic's `/dream` (AutoDream) is memory consolidation that runs between sessions:

1. Scans the `MEMORY.md` index + memory files in `.claude/projects/*/memory/`
2. Merges duplicate or overlapping entries
3. Prunes outdated/contradicted information
4. Converts relative timestamps to absolute dates
5. Re-indexes MEMORY.md to stay under the 200-line load threshold

**Triggering:** Manual (`/dream` command) or automatic (24h elapsed AND 5+ sessions since last dream). Currently in staged rollout (feature-flag gated, March 2026).

**Scope:** Works exclusively on what AutoMemory already saved. Does not capture new information — it consolidates existing memory files.

---

## What CCA Frontier 1 Does That Dream Doesn't

| Capability | AutoDream | CCA Memory |
|-----------|-----------|------------|
| Structured types (user, feedback, project, reference) | No — free-form markdown | Yes — typed with validation |
| Confidence scoring + TTL-based decay | No | Yes — HIGH=365d, MEDIUM=180d, LOW=90d |
| FTS5 search across all memories | No — relies on MEMORY.md scan | Yes — SQLite full-text search |
| Auto-capture from hooks (not just session-end) | No — captures during session via AutoMemory | Yes — PreToolUse/PostToolUse/Stop hooks |
| Credential filtering before storage | No explicit guarantee | Yes — regex filtering on capture |
| Cross-chat coordination (CCA/Kalshi) | No — single-project scope | Yes — designed for multi-chat |
| Severity tracking + promotion | No | Yes — learnings.md pattern |

## What AutoDream Does That CCA Memory Doesn't

| Capability | AutoDream | CCA Memory |
|-----------|-----------|------------|
| Native integration (survives compaction, auto-loaded) | Yes | No — requires hook wiring |
| Zero configuration | Yes — works out of the box | No — needs schema + hooks |
| Dedup/merge intelligence | Yes — automatic consolidation | No — manual dedup |
| Anthropic-maintained, evolving | Yes | No — CCA maintains |
| Contradiction resolution | Yes — removes outdated facts | Not yet |

---

## Integration Strategy: Complement, Don't Compete

CCA memory should **layer on top** of AutoDream, not replace it.

```
Layer 4: CCA specialized memory (typed, scored, cross-chat, TTL)
Layer 3: /dream consolidation (dedup, prune, re-index)
Layer 2: AutoMemory (Claude's session notes, free-form)
Layer 1: CLAUDE.md (manual rules, always loaded)
```

### What CCA Memory Owns

- **Typed capture:** Enforcing schema (user/feedback/project/reference) with confidence scoring
- **Cross-chat coordination:** Memory that bridges CCA and Kalshi sessions
- **Credential filtering:** Hard security boundary — no keys/balances ever persisted
- **TTL decay:** Automatic expiration based on confidence level
- **Queryable search:** FTS5 for "what did we decide about X?" across all memory
- **Severity-tracked learnings:** Patterns that promote from project to global scope

### What CCA Memory Defers to Dream

- **Deduplication:** Let dream merge overlapping entries in MEMORY.md
- **Timestamp normalization:** Let dream convert relative dates
- **Stale pruning:** Let dream remove notes about deleted files/config
- **MEMORY.md re-indexing:** Let dream keep the index under 200 lines

### Integration Points

1. **CCA writes structured memory files** to `.claude/projects/*/memory/` with proper frontmatter
2. **Dream consolidates** those files alongside AutoMemory entries
3. **CCA reads consolidated results** at session init — benefits from dream's cleanup
4. **CCA never overwrites dream's work** — additive only, let dream handle cleanup

### Risk: Dream Corrupting CCA Structure

If dream merges or rewrites CCA's typed memory files, it could strip frontmatter or break schema.

**Mitigation:** CCA memory files use YAML frontmatter that dream preserves (dream respects markdown structure). If dream ever strips frontmatter, CCA's init can detect and restore from the SQLite backing store.

---

## Decision: When to Build What

| Phase | Action | Depends On |
|-------|--------|-----------|
| Now | Continue using AutoMemory + MEMORY.md (current state) | Nothing |
| When dream reaches GA | Validate dream doesn't break CCA frontmatter | Dream GA |
| When memory count > 50 | Build FTS5 search layer | Scale need |
| When cross-chat memory needed | Build coordination layer | Hivemind maturity |

**Bottom line:** AutoDream solves the consolidation problem we'd otherwise need to build. CCA's value-add is typed structure, security filtering, cross-chat coordination, and queryable search — none of which dream provides.
