# TurboQuant + Prism MCP — Frontier 1 Research
# Date: 2026-03-30 (S237, Chat 2 of 3)
# Sources: arxiv 2504.19874, github.com/dcostenco/prism-mcp v6.1.9
# Scope: Pure research — no implementation. Evaluates applicability to CCA.

---

## 1. TurboQuant Paper Summary

**Title:** TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate
**Authors:** Amir Zandieh (Google Research), Majid Daliri (NYU), Majid Hadian (Google DeepMind), Vahab Mirrokni (Google Research)
**Venue:** ICLR 2026 (arxiv 2504.19874, April 2025)
**Verified:** Paper read from arxiv PDF, 20 pages, all algorithms and experiments reviewed.

### Core Algorithm (Two-Stage)

**Stage 1 — MSE-Optimal Quantization:**
1. Generate random rotation matrix Pi via QR decomposition of a d x d Gaussian matrix
2. Rotate input vector: y = Pi * x
3. After rotation, each coordinate follows a Beta distribution (converges to N(0,1/d) in high dims)
4. Coordinates become near-independent — this is the key insight
5. Apply Lloyd-Max optimal scalar quantizer independently to each coordinate
6. Store indices (b-bit integers per dimension)

**Stage 2 — 1-bit QJL Residual Correction (for inner product):**
1. Use (b-1)-bit MSE quantizer from Stage 1
2. Compute residual: r = x - DeQuant_mse(Quant_mse(x))
3. Apply QJL: qjl = sign(S * r) where S is random Gaussian matrix
4. Store sign bits (1 bit per dimension) + residual norm scalar
5. Result: unbiased inner product estimator at total b bits per coordinate

### Why It Works

Random rotation transforms ANY input distribution into a known distribution (Beta/Normal).
This eliminates the need for data-dependent training (unlike Product Quantization).
Lloyd-Max codebooks are precomputed once for the Beta distribution and reused forever.
The QJL residual correction removes the systematic bias that MSE quantizers introduce
in inner product estimation.

### Compression Ratios

For 768-dimensional vectors (Gemini embedding size, also common for text-embedding-3):

| Bit Width | Bytes/Vector | Compression | MSE Distortion | IP Distortion (per dim) |
|-----------|-------------|-------------|----------------|------------------------|
| Uncompressed (float32) | 3,072 | 1x | 0 | 0 |
| 4-bit | 384 + 96 (QJL) = 480 | 6.4x | 0.009 | 0.047/d |
| 3-bit | 288 + 96 (QJL) = 384 | 8.0x | 0.03 | 0.18/d |
| 2-bit | 192 + 96 (QJL) = 288 | 10.7x | 0.117 | 0.56/d |
| 1-bit | 96 + 96 (QJL) = 192 | 16x | 0.36 | 1.57/d |

Note: QJL residual adds 96 bytes (768 bits) regardless of MSE bit width.
Prism claims ~400 bytes at 4-bit (matches: 288 MSE + 96 QJL + 16 header = 400).

### Near-Optimality

TurboQuant MSE distortion is within 2.7x of the Shannon lower bound.
At b=1, it's within 1.45x of optimal — confirmed experimentally.
This means no algorithm can do fundamentally better.

### Experimental Results (Key Numbers)

**Needle-in-a-Haystack (KV cache):**
- Full precision: 0.997 score
- TurboQuant (4x compressed): 0.997 score — IDENTICAL
- SnapKV: 0.858, PyramidKV: 0.895, KIVI: 0.981

**LongBench-V1 (Llama-3.1-8B):**
- Full cache (16 KV): avg 50.06
- TurboQuant (3.5 KV): avg 50.06 — matches full precision at 4.5x compression
- TurboQuant (2.5 KV): avg 49.44 — marginal degradation at 6.4x compression
- Outperforms KIVI and PolarQuant at comparable compression

**Quantization Speed (the killer feature for us):**
- d=768: ~0.001 seconds — essentially instant
- d=1536: 0.0013 seconds
- d=3072: 0.0021 seconds
- Product Quantization d=1536: 239.75 seconds (184,000x slower)
- RabitQ d=1536: 2267.59 seconds (1,744,000x slower)

TurboQuant is "online" — no training phase, no codebook construction from data.
You can quantize vectors one at a time as they arrive.

---

## 2. Prism MCP Architecture Analysis

**Repo:** dcostenco/prism-mcp (v6.1.9, MIT license)
**Language:** TypeScript, runs as MCP server via npx
**Tests:** 303 tests
**Storage:** Local SQLite (default) or Supabase (optional sync)

### TurboQuant Implementation (src/utils/turboquant.ts)

Pure TypeScript port. Key implementation details:

- **Householder QR** for rotation matrix (not Gram-Schmidt — more numerically stable)
- **Mulberry32 PRNG** for deterministic random matrices (seed=42, cross-platform consistent)
- **Precomputed Lloyd-Max codebooks** for bit widths 1-8
- **Asymmetric scoring:** queries stay float32, only stored vectors quantized
- **Wire format:** little-endian binary (uint16 dim + uint8 bits + float32 radius + float32 residualNorm + packed MSE indices + packed QJL signs)
- **Default:** d=768, bits=4 (Gemini embedding dimension)
- **Config is immutable per database** — changing bits would invalidate all existing embeddings

### Three-Tier Search Fallback

1. **sqlite-vec** (native SQLite vector extension) — if installed
2. **JS-side TurboQuant scoring** — asymmetric inner product in TypeScript
3. **FTS5 keyword search** — always available, zero-config

This is smart. FTS5 works offline with zero API keys. Vector search requires
GOOGLE_API_KEY for Gemini embeddings. The fallback ensures the system always works.

### Mistake-Learning System (src/utils/cognitiveMemory.ts)

Much simpler than expected. Two functions:

1. **computeEffectiveImportance(baseScore, timestamp):**
   - Ebbinghaus forgetting curve: `effective = base * 0.95^daysSinceAccess`
   - 5% daily decay
   - Clock-skew protection: Math.max(0, delta)
   - Falls back from lastAccessed to createdAt if never retrieved

2. **updateLastAccessed(memoryIds):**
   - Fire-and-forget async timestamp update
   - Processes IDs in parallel
   - Swallows errors (non-blocking)

The "corrections" table in the schema stores mistakes with importance weights.
High-importance corrections auto-surface as warnings in future sessions.
Can sync to .cursorrules/.clauderules for permanent rule enforcement.

### Other Notable Features

- **Morning Briefings:** Auto-synthesized 3-bullet action plan after 4+ hours away
- **Time Travel:** Version checkout of memory to any historical snapshot
- **Hivemind Radar:** Active agent roster with heartbeats (multi-agent)
- **Web Scholar:** Background research pipeline (Brave Search + Firecrawl + LLM synthesis)
- **Mind Palace Dashboard:** Interactive force-directed knowledge graph (localhost:3000)
- **GDPR compliance:** Soft/hard delete, full export, API key redaction

---

## 3. Applicability to CCA Frontier 1 Memory System

### 3A. TurboQuant for Memory Schema — VERDICT: NOT YET APPLICABLE

**Current state:** CCA's memory system uses JSON/SQLite + FTS5. No embeddings. No vectors.
Memory retrieval is tag-based + FTS5 keyword search. The schema stores 500-char text strings.

**TurboQuant would apply IF:**
- We added semantic (vector) search to the memory system
- We needed to store thousands of embedding vectors compactly
- We needed similarity search across memories

**Why it doesn't apply now:**
1. CCA has no embedding pipeline. We'd need an API key for Gemini/OpenAI embeddings.
   Matthew has explicitly stated: NO Anthropic API key available. Gemini key exists
   (GEMINI_API_KEY env var) but using it adds external dependency and cost.
2. FTS5 search is sub-100ms and covers CCA's current retrieval needs.
3. CCA's memory store has ~100 memories total. At 100 memories x 3KB each = 300KB.
   Compression from 300KB to 40KB is meaningless at this scale.
4. The stdlib-first principle conflicts with adding an embedding dependency.

**When it WOULD become valuable:**
- If memory count exceeds ~1000 entries and FTS5 recall degrades
- If we add cross-project semantic search ("find similar decisions across projects")
- If Anthropic ships native embeddings in Claude Code (no API key needed)
- If we build a shared memory layer for MT-21 hivemind agents

**Bottom line:** TurboQuant is an excellent compression algorithm that solves a problem
CCA doesn't have yet. File this as a known technique for when/if we add vector search.
The paper is verified, the math is sound, Prism's implementation is proven.

### 3B. Prism Mistake-Learning for Self-Learning Journal — VERDICT: ADAPT (PARTIAL)

**What Prism does:** Ebbinghaus decay on correction importance. Simple but principled.

**What CCA already has:** self-learning/journal.jsonl with structured events, learnings
captured per session, SKILLBOOK.md for distilled strategies, APF metric for quality.

**What's worth stealing:**

1. **Ebbinghaus decay function** — CCA's memory system uses hard TTL cutoffs
   (HIGH=365d, MEDIUM=180d, LOW=90d). Prism's continuous decay is more principled:
   `effective = base * 0.95^days`. This could replace the cliff-edge TTL.
   Already noted in EXTERNAL_COMPARISON.md as "recency decay scoring" from ClawMem.

2. **Corrections-as-first-class-entities** — CCA's self-learning logs learnings as
   strings in JSONL events. Prism promotes corrections to their own table with
   importance weights that compound over time. CCA should consider making the
   `error` memory type more structured: add `importance` field, `times_triggered`,
   `last_triggered_at`.

3. **Auto-surfacing high-importance corrections** — Prism automatically shows
   high-importance corrections as warnings in future sessions. CCA's capture_hook
   already filters by confidence level, but doesn't specifically prioritize recent
   corrections. Adding a "corrections in the last 7 days" bucket to session-start
   retrieval would catch fresh lessons before they decay.

**What's NOT worth stealing:**
- The fire-and-forget async pattern (CCA is Python, not async TypeScript)
- The Ebbinghaus constant (0.95/day is tuned for their use case, not ours)
- Syncing to .cursorrules — CCA already has CLAUDE.md layering

### 3C. Auto Dream Integration — VERDICT: COMPLEMENT, DON'T COMPETE

**Context:** Anthropic shipped /dream in March 2026 (FINDINGS_LOG entry #11, 1657pts).
Auto Dream is a background sub-agent that consolidates Auto Memory notes after 24h + 5 sessions.

**What /dream does:**
1. Orient — scan memory dir
2. Gather Signal — check daily logs, transcript JSONL
3. Consolidate — merge topics, absolute dates, delete contradictions
4. Prune & Index — clean index, resolve conflicts
Read-only on project code, write-only on memory files.

**CCA's Frontier 1 advantages over native Auto Memory + Auto Dream:**
- Structured schema (5 types, confidence levels, TTL)
- Explicit extraction ("remember/always/never" triggers = HIGH confidence)
- FTS5 search (native memory is substring-match on MEMORY.md)
- Credential filtering (regex-based, absolute security boundary)
- Hook-based selective capture (vs Auto Memory's auto-capture-everything)
- Retention policy with differential TTL by confidence

**How to complement /dream:**
1. CCA's capture_hook extracts explicit memories via transcript keywords
2. /dream consolidates the broader auto-captured notes
3. CCA's FTS5 store provides structured search; /dream provides organic synthesis
4. CCA handles what /dream doesn't: error resolutions, architectural decisions,
   cross-project patterns, credential-filtered capture

**Integration path:**
- CCA memory store writes to `~/.claude/projects/<hash>/memory/` (native path)
- CCA's structured memories coexist with Auto Memory notes
- /dream sees CCA's memories during consolidation and may merge/reference them
- CCA never deletes native memory files; it only adds its own structured ones
- The two systems are additive, not competitive

**Risk:** /dream might "consolidate" CCA's carefully structured memories into
unstructured prose. Mitigation: CCA files use clear frontmatter that /dream should
recognize as intentional structure. Monitor for this in practice.

### 3D. Prism's Full Architecture — VERDICT: REFERENCE, SPECIFIC PATTERNS WORTH STEALING

**Prism is a more mature, feature-rich system than CCA's Frontier 1.**
But it has different design constraints:
- TypeScript (MCP server) vs Python (hooks + CLI)
- Requires API keys for most advanced features vs CCA's zero-config
- 6000+ lines across dozens of files vs CCA's focused ~800 lines
- External dependencies (Brave, Firecrawl, Gemini, etc.) vs stdlib-first

**Patterns worth stealing (in priority order):**

1. **Three-tier search fallback** — Always have a zero-config path.
   CCA already has this (FTS5 is zero-config). Good validation.

2. **Session ledger format** — Prism captures decisions, TODOs, files changed,
   corrections, and rationale in a structured ledger per session. CCA's
   session_outcomes.jsonl is simpler. The ledger pattern is worth considering
   if we want richer session history.

3. **Mind Palace visualization** — Interactive knowledge graph. Not applicable
   now but validates the concept for a future Frontier 5 dashboard feature.

4. **Morning briefings** — Auto-synthesized action plan after 4+ hours away.
   CCA's /cca-init serves this purpose already, but a time-aware "you've been
   away for X hours, here's what changed" would be a nice enhancement.

5. **Content-hash deduplication** — Prevents duplicate imports on re-run.
   CCA's 8-char hex ID suffix already prevents collision, but content-hash
   dedup would catch semantically identical memories with different IDs.

---

## 4. Recommendations for CCA

### Do Now (next session that touches Frontier 1)
- [ ] Add `importance` field to `error` memory type (integer 1-10)
- [ ] Add `times_triggered` counter to error memories
- [ ] Replace hard TTL cutoffs with continuous decay: `effective = base * decay^days`
- [ ] Add "recent corrections" bucket to session-start retrieval (last 7 days)

### Do Later (when scaling demands it)
- [ ] Add content-hash deduplication to prevent semantic duplicates
- [ ] Evaluate Gemini embeddings + TurboQuant compression when memory count > 500
- [ ] Consider session ledger format for richer session-end capture
- [ ] Design /dream compatibility — CCA memories in native Auto Memory path

### Do Not Do
- [ ] Do not add vector search until FTS5 is proven insufficient
- [ ] Do not add external API dependencies for core memory operations
- [ ] Do not port TurboQuant to Python — no use case at current scale
- [ ] Do not replicate Prism's full architecture — different design constraints

---

## 5. Key Takeaways

1. **TurboQuant is real and impressive.** Google Research paper, near-Shannon-optimal,
   184,000x faster than Product Quantization, proven in production via Prism MCP.
   But CCA doesn't need vector compression yet — our memory store is tiny.

2. **Prism validates CCA's architectural direction.** Local-first SQLite, FTS5 search,
   hook-based capture, structured memory types — Prism does all of these too, just
   in TypeScript with more features. CCA is on the right track.

3. **The mistake-learning pattern is the highest-value steal.** Ebbinghaus decay +
   importance scoring + auto-surfacing corrections is cheap to implement and
   directly improves session quality. This should be the next Frontier 1 work.

4. **Auto Dream is complementary, not competitive.** CCA captures what /dream doesn't
   (explicit extraction, credential filtering, structured types). The two systems
   should coexist in the native memory directory.

5. **Scale triggers matter.** TurboQuant, vector search, and content-hash dedup
   become valuable at ~500-1000 memories. CCA is at ~100. Track this threshold.
