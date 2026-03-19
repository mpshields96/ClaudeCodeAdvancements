# Frontier 1 Memory — External Architecture Comparison
# Date: 2026-03-19 (Session 60)
# Sources: engram, ClawMem, claude-mem (MT-11 GitHub scan findings)

---

## CCA Memory System vs. External Tools

| Feature | CCA (current) | engram | ClawMem | claude-mem |
|---------|---------------|--------|---------|------------|
| Storage | JSON files | SQLite + FTS5 | SQLite + vector store | Agent SDK compressed |
| Search | Substring match | Full-text search (FTS5) | BM25 + vector + RRF + cross-encoder | Context injection |
| Capture | Hook-based (selective) | Manual (mem_save) | 7 hooks (auto) | Auto (everything) |
| Retrieval | MCP server | MCP + HTTP + CLI + TUI | Hook-injected | Auto-injected |
| Scoring | Confidence levels + TTL | None visible | SAME composite (recency, confidence, type half-lives) | Compression-based |
| Language | Python (stdlib) | Go (zero deps) | Python (heavy deps) | Python (Anthropic SDK) |
| Stars | N/A (internal) | 1.5K | Low | Low |

---

## Key Architectural Insights

### 1. FTS5 Search (from engram) — HIGHEST IMPACT, LOWEST EFFORT
engram's SQLite FTS5 is the single most impactful pattern CCA should adopt.
- Python 3.10+ sqlite3 module includes FTS5 support (no external deps)
- Replaces CCA's O(n) substring scan with O(log n) full-text search
- Supports boolean queries: `"sqlite AND NOT postgres"`
- Supports ranking by relevance (BM25 built into FTS5)
- Migration path: JSON -> SQLite with FTS5 virtual table

### 2. Recency Decay Scoring (from ClawMem) — MEDIUM IMPACT
ClawMem's SAME-inspired scoring is more principled than CCA's simple TTL:
- Score = f(relevance, recency, confidence, content-type)
- Content-type half-lives: decisions decay slow, errors decay fast
- CCA already has differential TTL (HIGH=365d, MEDIUM=180d, LOW=90d)
- Improvement: add continuous decay function instead of hard TTL cutoff
- Formula: `score = relevance * recency_weight * confidence_weight`
  where `recency_weight = exp(-lambda * days_since_used)`

### 3. Structured Memory Fields (from engram)
engram's mem_save format: title/type/What/Why/Where/Learned
- More structured than CCA's flat `content` string
- The "Why" and "Learned" fields force higher-quality captures
- CCA's 500-char limit already prevents rambling; structure would add retrieval precision

### 4. Auto-Capture vs. Selective (from claude-mem)
claude-mem captures everything, then compresses later.
- Opposite of CCA's approach (selective capture via hooks)
- Risk: noise. If you capture everything, retrieval quality depends entirely on search
- CCA's hook-based selective approach is better IF capture triggers are well-tuned
- Hybrid: keep selective capture, add transcript-scan for "remember/always/never" keywords

---

## Recommended CCA Improvements (Priority Order)

### P0: Migrate JSON to SQLite + FTS5
- One-time migration: read JSON, write to SQLite with FTS5 virtual table
- Enables relevance-ranked search instead of substring matching
- No external dependencies (sqlite3 is stdlib)
- Estimated: ~200 LOC change to schema + mcp_server + cli

### P1: Add Recency Decay to Retrieval Scoring
- Replace hard TTL with exponential decay in retrieval ranking
- Score = BM25_relevance * exp(-0.003 * days_unused) * confidence_multiplier
- Decisions: lambda=0.001 (slow decay), errors: lambda=0.01 (fast decay)
- Keeps TTL as hard cutoff but adds continuous ranking within TTL window

### P2: Structured Memory Fields
- Add optional `what`, `why`, `where`, `learned` fields alongside content
- Backward-compatible: existing memories still work with just `content`
- FTS5 indexes all fields, so structured data improves search precision

### P3: Hybrid RAG (Future — requires dependencies)
- BM25 (FTS5) is 80% of the value with 0% dependency cost
- Vector search + RRF adds the remaining 20% but requires sentence-transformers or similar
- Only pursue if FTS5 proves insufficient for CCA's memory volume (~100-1000 entries)

---

## What NOT to Copy

- ClawMem's heavy dependency chain (vector stores, cross-encoders) — violates stdlib-first
- claude-mem's "capture everything" approach — noise risk too high for CCA's use case
- engram's Go rewrite — CCA is Python-native, rewriting in Go adds no value
- Any external API calls for memory operations — local-first is non-negotiable
