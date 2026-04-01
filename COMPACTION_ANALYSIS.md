# Compaction Implementation Analysis

**Source:** `references/claude-code-ts/src/services/compact/compact.ts` (1705 lines)
**Prompt:** `references/claude-code-ts/src/services/compact/prompt.ts` (375 lines)
**Date:** 2026-03-31 (Chat 12C, S245)

---

## 1. How Compaction Actually Works

Compaction is Claude Code's context management strategy. When the conversation exceeds a token threshold, it summarizes older messages and replaces them with the summary + post-compact attachments.

### Three Compaction Modes

| Mode | Trigger | What Gets Summarized |
|------|---------|---------------------|
| **Full (auto)** | Token count exceeds threshold | ALL messages before boundary |
| **Full (manual)** | User runs `/compact` | ALL messages before boundary |
| **Partial** | User selects a message pivot | Either before or after pivot |

Partial compact has two directions:
- `from` (prefix-preserving): keeps early messages, summarizes tail → preserves prompt cache
- `up_to` (suffix-preserving): summarizes early messages, keeps recent → loses prompt cache

### The Summarization Pipeline

```
1. Execute PreCompact hooks (custom instructions injection)
2. Strip images → replace with [image] markers
3. Strip re-injectable attachments (skill_discovery, skill_listing)
4. Group messages by API round
5. Send to model with compact prompt (NO tools allowed)
6. Model returns <analysis> + <summary> blocks
7. Strip <analysis> (drafting scratchpad only)
8. Build post-compact context:
   - Compact boundary marker
   - Formatted summary as UserMessage
   - Post-compact file attachments (top 5 recent files, 50K tok budget)
   - Plan file attachment (if active)
   - Plan mode attachment (if in plan mode)
   - Invoked skills attachment (5K tok/skill, 25K total budget)
   - Deferred tools delta attachment
   - Agent listing delta attachment
   - MCP instructions delta attachment
   - Async agent status attachments
   - SessionStart hook results
9. Execute PostCompact hooks
10. Log telemetry (tengu_compact event)
```

---

## 2. The Compact Prompt (What Survives Compaction)

The summarizer is instructed to produce a 9-section summary:

1. **Primary Request and Intent** — user's goals
2. **Key Technical Concepts** — frameworks, patterns
3. **Files and Code Sections** — with full code snippets
4. **Errors and Fixes** — including user feedback
5. **Problem Solving** — resolved and ongoing
6. **All User Messages** — every non-tool-result user message (critical)
7. **Pending Tasks** — explicitly requested work
8. **Current Work** — precise description of in-progress work
9. **Optional Next Step** — with direct quotes from conversation

### Key Design Decisions

**Analysis scratchpad:** The model writes `<analysis>` first (chain-of-thought for quality), then `<summary>`. Analysis is STRIPPED before the summary enters context — it's a free quality boost.

**No-tools enforcement:** Double-enforced with preamble AND trailer:
```
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
Tool calls will be REJECTED and will waste your only turn.
```
This exists because Sonnet 4.6+ sometimes attempts tool calls despite instructions. The `maxTurns: 1` means a tool call = wasted turn = empty summary = fallback.

**Autonomous mode awareness:**
```
You are running in autonomous/proactive mode. This is NOT a first wake-up.
Continue your work loop: pick up where you left off.
```

---

## 3. preCompactDiscoveredTools — The Deferred Tools Fix

This is the mechanism that prevents tools from disappearing after compaction.

### The Problem
Deferred tools (loaded via ToolSearch) only appear in tool_use blocks within the conversation. After compaction, those blocks are gone → the model loses access to tools it previously loaded.

### The Fix (lines 606-611)
```typescript
const preCompactDiscovered = extractDiscoveredToolNames(messages)
if (preCompactDiscovered.size > 0) {
  boundaryMarker.compactMetadata.preCompactDiscoveredTools = [
    ...preCompactDiscovered,
  ].sort()
}
```

`extractDiscoveredToolNames()` scans all messages for tool_use blocks referencing deferred tools. Their names are stored in the boundary marker's metadata. Post-compaction, the tool schema filter uses this list to keep sending those tool schemas to the API.

### CCA Relevance
This is exactly the pattern our context monitor should watch for. If we detect tool schemas being lost post-compaction, we can re-inject them. The `getDeferredToolsDeltaAttachment` function (called post-compact with empty message array → announces full set) is the re-announcement mechanism.

---

## 4. Post-Compact File Restoration

### Budget Constants
```typescript
POST_COMPACT_MAX_FILES_TO_RESTORE = 5      // max recent files
POST_COMPACT_TOKEN_BUDGET = 50_000          // total budget for files
POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000    // per-file cap
POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000   // per-skill cap
POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000   // total skill budget
```

### File Selection Logic
1. Get all files from `readFileState` cache (maps filename → {content, timestamp})
2. Filter out plan files and CLAUDE.md files (re-injected separately)
3. Filter out files already in preserved messages (dedup)
4. Sort by timestamp (most recent first)
5. Take top 5
6. Re-read each via FileReadTool (fresh content, proper validation)
7. Filter by cumulative token budget (50K)

### What Gets Excluded
- Plan files → separate `createPlanAttachmentIfNeeded()`
- Memory files (all CLAUDE.md types) → re-injected by SessionStart hooks
- Files already in preserved tail (partial compact) → dedup via `collectReadToolFilePaths()`

---

## 5. Prompt-Too-Long Recovery (CC-1180)

When the compact request ITSELF hits the prompt-too-long limit:

```typescript
const MAX_PTL_RETRIES = 3

function truncateHeadForPTLRetry(messages, ptlResponse) {
  // Group messages by API round
  // Parse token gap from error response
  // Drop oldest groups until gap is covered
  // Fallback: drop 20% if gap unparseable
  // Keep at least 1 group
  // Prepend synthetic user message if first remaining is assistant
}
```

Three retries. Each drops the oldest message groups until the token gap is covered. If unparseable (Vertex/Bedrock error formats), drops 20%.

This is the "last resort" for users who are stuck with conversations too long to even compact.

---

## 6. Cache Sharing (Forked Agent Path)

Compaction uses a clever optimization: run as a "forked agent" that shares the main conversation's prompt cache.

```typescript
const result = await runForkedAgent({
  promptMessages: [summaryRequest],
  cacheSafeParams,            // main thread's cache key
  canUseTool: createCompactCanUseTool(),  // deny all tools
  querySource: 'compact',
  forkLabel: 'compact',
  maxTurns: 1,
  skipCacheWrite: true,
})
```

The fork inherits the main thread's system prompt + tools + messages (cache-key params). This means the compact call gets a cache HIT on most of the input, saving significant cost.

**Critical constraint:** Cannot set `maxOutputTokens` on fork path — it would change the thinking config hash, invalidating the cache.

Falls back to regular streaming if the fork fails.

---

## 7. The "Empty Array Diff" Pattern

**Previously hypothesized as a bug — actually a deliberate design choice.**

After compaction, delta attachments are generated by diffing against an empty array:
```typescript
for (const att of getDeferredToolsDeltaAttachment(
  context.options.tools,
  context.options.mainLoopModel,
  [],                           // ← empty array = diff against nothing
  { callSite: 'compact_full' },
)) {
```

This is NOT a bug. Comment on line 566-567 explains:
> "Compaction ate prior delta attachments. Re-announce from the current state so the model has tool/instruction context on the first post-compact turn. Empty message history → diff against nothing → announces the full set."

For **partial** compaction, it diffs against `messagesToKeep` instead:
```typescript
getDeferredToolsDeltaAttachment(
  context.options.tools,
  context.options.mainLoopModel,
  messagesToKeep,               // ← only announce what's not in kept messages
  { callSite: 'compact_partial' },
)
```

This means full compact always re-announces everything. Partial compact only re-announces what was lost in the summarized portion.

---

## 8. Implications for CCA Context Monitor (Frontier 3)

### What Our Monitor Should Track

1. **Pre/post compact token counts** — the `tengu_compact` event logs both. Our monitor should detect the same threshold approaching and warn.

2. **Recompaction loops** — `RecompactionInfo` tracks `isRecompactionInChain` and `turnsSincePreviousCompact`. If the post-compact context is STILL above threshold, it'll retrigger next turn. Our monitor should detect this spiral.

3. **File restoration budget** — 5 files, 50K tokens. If we've been reading 20+ files, 15 are lost on compaction. Consider pre-emptive file state snapshots.

4. **Skill truncation** — Skills over 5K tokens are head-truncated. Our custom agent definitions and skills should keep critical instructions at the TOP of files.

5. **Plan mode preservation** — Plans survive compaction via attachment. Our equivalent (session state files) should be designed to survive similarly.

### Compaction-Resilient Patterns

| Pattern | Why It Survives |
|---------|----------------|
| Numbered todo lists | Preserved in summary section 7 |
| File paths + line numbers | Preserved in summary section 3 |
| Error descriptions | Preserved in summary section 4 |
| User feedback quotes | Preserved in summary section 6 |
| Current work description | Preserved in summary section 8 |
| Tool schemas | `preCompactDiscoveredTools` metadata |

| Pattern | Why It's LOST |
|---------|---------------|
| Full file contents (beyond top 5) | Only 5 restored, 50K budget |
| Old conversation tone/style | Not captured in summary |
| Intermediate debugging steps | Summarized away |
| Read-only file state (except top 5) | Cache cleared |
| Loaded nested memory paths | Cache cleared |

---

## 9. Key Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/services/compact/compact.ts` | 1705 | Main compaction logic, file restoration, PTL recovery |
| `src/services/compact/prompt.ts` | 375 | Summarizer prompts (full/partial/up_to), analysis stripping |
| `src/services/compact/grouping.ts` | — | Group messages by API round for PTL truncation |
| `src/utils/toolSearch.ts` | — | `extractDiscoveredToolNames()` for tool preservation |
| `src/utils/messages.ts` | — | Boundary markers, summary message creation |
| `src/utils/attachments.ts` | — | Delta attachment generation (tools, agents, MCP) |
