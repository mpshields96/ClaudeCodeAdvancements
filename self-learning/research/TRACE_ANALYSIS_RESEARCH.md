# MT-7 Trace Analysis Research — Transcript JSONL Schema + Pattern Definitions
# Produced: Session 25 (2026-03-16)
# Source: Analysis of 5 real CCA transcript files (322K to 9.2MB)

---

## 1. JSONL Schema

Each `.jsonl` file = one session. Each line = one JSON entry.

### Top-Level Fields (all entries)

| Field | Type | Always? | Description |
|-------|------|---------|-------------|
| `type` | str | yes | `"user"`, `"assistant"`, `"progress"`, `"system"`, `"queue-operation"`, `"last-prompt"` |
| `sessionId` | str | yes | UUID of the session |
| `timestamp` | str | yes | ISO 8601 |
| `parentUuid` | str/null | most | UUID of parent entry (conversation tree) |
| `uuid` | str | most | This entry's UUID |
| `isSidechain` | bool | most | Side conversation flag |
| `message` | dict | user/assistant | The actual message payload |
| `toolUseResult` | dict/str | tool results only | Structured result metadata |

### Entry Type Distribution (largest session, 9.2MB)

| `type` | Count | % | Description |
|--------|-------|---|-------------|
| `progress` | 1223 | 38% | Hook/MCP/agent progress (NOISE — filter out) |
| `assistant` | 1088 | 34% | Claude responses (text + tool_use) |
| `user` | 723 | 22% | Human messages (67) + tool results (656) |
| `queue-operation` | 138 | 4% | Queue events (NOISE) |
| `system` | 47 | 1% | `stop_hook_summary` (40), `compact_boundary` (7) |

### Distinguishing Entry Types

- **Human message**: `type == "user"` AND no `toolUseResult` key AND has `permissionMode`
- **Tool result**: `type == "user"` AND `toolUseResult` exists
- **Failed tool call**: `message.content[*].is_error == true`
- **Tool call**: `type == "assistant"`, `message.content[*].type == "tool_use"`, name in `.name`, input in `.input`
- **Compaction**: `type == "system"` AND `subtype == "compact_boundary"`

### Token/Usage Data

Lives in `entry.message.usage` on **assistant entries only**:
- `input_tokens` — fresh (non-cached), usually 1-100
- `cache_read_input_tokens` — the big number, often 100K+
- `cache_creation_input_tokens` — new cache segments
- `output_tokens` — tokens generated
- `stop_reason` — `"end_turn"`, `"tool_use"`, or `null` (streaming chunk)

**Streaming**: Multiple assistant entries with `stop_reason: null` appear in sequence. Only the final chunk has the real stop_reason. Aggregate by `parentUuid`.

### Linking Tool Calls to Results

- Tool call: `message.content[*].id` (the `tool_use_id`)
- Tool result: `message.content[*].tool_use_id` matches the call's `id`
- Also: `sourceToolAssistantUUID` on result entry -> assistant entry's `uuid`

### toolUseResult Shapes by Tool

| Tool | Key Fields |
|------|-----------|
| Bash | `stdout, stderr, interrupted, isImage` |
| Read | `file, type` |
| Write | `filePath, structuredPatch, type` |
| Edit | `filePath, oldString, newString, structuredPatch` |
| Glob | `durationMs, filenames, numFiles, truncated` |
| Grep | `content, filenames, mode, numFiles, numLines` |
| Agent | `agentId, totalDurationMs, totalTokens, totalToolUseCount, usage` |
| WebFetch | `bytes, code, codeText, durationMs, url` |

---

## 2. Pattern Definitions (for trace_analyzer.py)

### Pattern A: Retry Loops

**Signal**: Same tool called 3+ times on same file within a short window.

**Real data**: SESSION_STATE.md had 5-10 consecutive Edit calls in one session. `claude plugin marketplace add` retried 8+ times. Test commands narrowed progressively (`2>&1` -> `| tail -15` -> `| tail -8`).

**Detector logic**:
1. For each file F, collect sequential tool_use entries where `input.file_path == F` or `input.command` references F
2. If 3+ consecutive assistant entries target same file with same tool, flag
3. Weight by `is_error`: if intervening tool_results have `is_error=true`, confirmed retry
4. Threshold: 3+ = minor, 5+ = major, 8+ = critical

### Pattern B: Context Waste (Read Without Use)

**Signal**: Read call whose file never appears in subsequent Edit/Write/Bash within next 20 entries.

**Real data**: 31% of Read calls had no subsequent reference (13/42 in one session).

**Detector logic**:
1. For each Read at position P, extract `file_path`
2. Scan forward 20 assistant entries for any reference to that path
3. Flag if not found
4. Severity: HIGH if file was large, LOW if small
5. Exception: session-start orientation reads (CLAUDE.md, SESSION_STATE.md, PROJECT_INDEX.md at position < 30) = tag "orientation" not "waste"

### Pattern C: Tool Call Efficiency

**Signal**: Ratio of unique files touched to total tool calls.

**Real data across 5 sessions**:
| Session Size | Tool Calls | Unique Files | Ratio | Rating |
|-------------|-----------|-------------|-------|--------|
| 9.2MB | 656 | 79 | 0.12 | Mediocre |
| 3.5MB | 260 | 33 | 0.13 | Mediocre |
| 839K | 56 | 9 | 0.16 | Mediocre |
| 390K | 21 | 4 | 0.19 | Mediocre |
| 322K | 21 | 8 | 0.38 | Good |

**Thresholds**: >0.3 = good, 0.1-0.3 = mediocre, <0.1 = poor

### Pattern D: Session Velocity

**Signal**: Deliverables (commits + file creates) per total tool calls.

**Real data**:
| Session | Tool Calls | Commits | Velocity |
|---------|-----------|---------|----------|
| 9.2MB | 656 | 9 | 1.4% |
| 3.5MB | 260 | 0 | 0% (research session) |
| 390K | 21 | 1 | 4.8% |
| 322K | 21 | 2 | 9.5% |

**Detection**: Parse Bash inputs for `git commit`. Count Write calls as file creates.

### Pattern E: Error-Prone Tools

**Real data (largest session)**:
- WebFetch: 54% error rate (21/39 calls)
- Edit: 10% error rate (8/77) — mostly "File has not been read yet"
- Bash: 6% error rate (11/179)
- 64 total `is_error=true` tool results

### Pattern F: Compaction Frequency

**Real data**: 7 `compact_boundary` entries in largest session. Each has `compactMetadata.preTokens`.

---

## 3. Architecture Recommendation for trace_analyzer.py

```
Classes:
- TranscriptEntry: parse one JSONL line, expose type/role/tool_name/file_path/is_error/usage
- TranscriptSession: load file, filter noise (progress/queue), aggregate streaming chunks
- RetryDetector: sliding window, group by file_path, flag 3+ consecutive same-tool-same-file
- WasteDetector: for each Read, forward-scan for references
- EfficiencyCalculator: unique_files / total_tool_calls
- VelocityCalculator: deliverables per hour using timestamps
- TraceAnalyzer: orchestrates all detectors, produces structured report
```

**Key implementation notes**:
- Filter out `progress` and `queue-operation` entries immediately (38%+ of all entries = noise)
- Aggregate streaming chunks by `parentUuid` before analysis
- `is_error` field on tool_result content items is the cleanest retry signal
- Link tool calls to results via `tool_use_id` matching
