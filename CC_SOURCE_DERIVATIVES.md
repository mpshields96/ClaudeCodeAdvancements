# Claude Code Source Leak — Derivative Tools & Analyses

**Date:** 2026-03-31 (Chat 12E, S245)
**Context:** CC v2.1.88 TypeScript source leaked via npm sourcemaps on 2026-03-31

---

## Top Derivative Repos (ranked by CCA relevance)

### 1. ComeOnOliver/claude-code-analysis (34 stars)
Comprehensive architecture documentation: 41 tools, 101 slash commands, 130+ React/Ink components, 300+ utility modules, all special modes (Bridge, Kairos, Coordinator, Voice, Plan, Vim). Full DOCUMENTATION.md with 17 sections.
**Use:** Reference map of every CC subsystem. Most useful single repo for CCA.

### 2. Yuyz0112/claude-code-reverse (2.3k stars)
Monkey-patches CC to intercept all LLM API requests/responses + interactive visualization. Parser + HTML visualizer included.
**Use:** Run it to capture live compaction behavior and token flow for Frontier 3 context monitoring.

### 3. instructkr/claw-code (68k stars)
Clean-room Python reimplementation of CC's agent harness. Rust port in progress. Captures architectural patterns without copying source.
**Use:** Reference architecture for CCA's agent/tool wiring patterns.

### 4. Kuberwastaken/claude-code (3.7k stars)
Source mirror + detailed breakdown + Rust rewrite. Documents autoDream, KAIROS, ULTRAPLAN, Undercover Mode, ML-powered permission auto-approval.
**Use:** autoDream (four-phase background memory consolidation) is exactly what Frontier 1 aims to build.

---

## Top Blog Analyses

### Alex Kim — "The Claude Code Source Leak"
Anti-distillation mechanisms (fake tool injection, crypto signatures), client attestation/DRM, frustration detection regex, KAIROS details. 1,279 sessions with 50+ failures = ~250K wasted API calls/day.
**Use:** Security and anti-abuse patterns for Agent Guard (Frontier 4).

### Sathwick — "Reverse-Engineering Claude Code"
26-subsystem deep dive. Multi-strategy compaction (image stripping, microcompaction, model summaries), tiered permissions, file-based IPC with mtime conflict detection, 18 deferred tools, three interning pools.
**Use:** Most technically dense analysis. Directly actionable for Frontiers 3, 4, 5.

### DEV Community — "12 Versions Reverse Engineered"
Analyzed v2.1.74-2.1.88. 16.3% API failure rate, silent model downgrade (Opus→Sonnet), streaming watchdog disabled by default, 3,167-line function with 486 branches.
**Use:** Failure rate data and degradation patterns for Frontier 5 usage dashboard.

### dreadheadio — Claude Code Roadmap Blog
Extracted roadmap + built 3 working implementations: cron scheduler, multi-agent coordinator (async Python), GitHub webhook PR reviewer.
**Use:** Working implementations we could port for CCA.

---

## Key Intelligence for CCA Frontiers

| Frontier | Key Finding | Source |
|----------|-------------|--------|
| Memory (F1) | autoDream = 4-phase background consolidation. MEMORY.md uses ~150-char pointer lines perpetually loaded. | Kuberwastaken, ComeOnOliver |
| Spec (F2) | Plan approval workflow: worker submits → leader approves. Plan mode persists across compaction. | coordinatorMode.ts source |
| Context (F3) | Auto-compact at ~98% capacity. Multi-strategy: image strip, microcompaction, model summaries. PTL recovery with 3 retries. | Sathwick, compact.ts source |
| Agent Guard (F4) | File-based IPC + mtime conflict. ML permission auto-approval. 5 nested AbortControllers. Anti-distillation. | Alex Kim, Sathwick |
| Usage (F5) | 16.3% API failure rate. 250K wasted calls/day from retry storms. 3 interning pools. 18 deferred tools. | DEV Community, Sathwick |

---

## Action Items

1. **Clone claude-code-analysis for structured reference** — better than reading raw source for overview
2. **Try claude-code-reverse** — live interaction traces would validate our context monitor design
3. **Study autoDream pattern** — exactly what Frontier 1 memory needs (background consolidation)
4. **Read Sathwick's microcompaction section** — CCA could implement similar for context monitor
