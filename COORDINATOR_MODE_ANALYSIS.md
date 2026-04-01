# Coordinator Mode + UDS Inbox Analysis

**Source:** `references/claude-code-ts/src/coordinator/coordinatorMode.ts` (369 lines)
**Related:** `src/tools/SendMessageTool/SendMessageTool.ts` (918 lines), `src/utils/teammateMailbox.ts` (1184 lines)
**Date:** 2026-03-31 (Chat 12B, S245)

---

## 1. What Coordinator Mode Actually Is

Coordinator Mode is a **separate system prompt personality** activated by the env var `CLAUDE_CODE_COORDINATOR_MODE=1`. When active, Claude becomes an orchestrator that:

- Does NOT use standard tools (Bash, Read, Edit, etc.) directly
- Instead spawns **workers** via the `Agent` tool
- Communicates with running workers via `SendMessage`
- Can stop workers with `TaskStop`
- Synthesizes worker results for the user

### Activation
```typescript
export function isCoordinatorMode(): boolean {
  if (feature('COORDINATOR_MODE')) {  // feature flag gate
    return isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE)
  }
  return false
}
```

Feature-flagged behind `COORDINATOR_MODE` gate. Not yet GA — internal/experimental.

### Session Persistence
Mode is stored in session metadata. On resume, `matchSessionMode()` flips the env var to match, ensuring coordinator sessions resume as coordinator and vice versa.

---

## 2. Coordinator System Prompt (Key Design Decisions)

The full system prompt is in `getCoordinatorSystemPrompt()` (lines 111-368). Key architectural decisions:

### Role Model: Research → Synthesis → Implementation → Verification
```
| Phase          | Who            | Purpose                                    |
|Research        | Workers        | Investigate codebase, find files            |
|Synthesis       | Coordinator    | Read findings, craft implementation specs   |
|Implementation  | Workers        | Make targeted changes per spec, commit      |
|Verification    | Workers        | Test changes work                           |
```

### Critical: Coordinator MUST Synthesize
The prompt explicitly bans lazy delegation:
> "Never write 'based on your findings' or 'based on the research.' These phrases delegate understanding to the worker instead of doing it yourself."

Anti-patterns called out:
- `"Based on your findings, fix the auth bug"` (bad)
- `"Fix the null pointer in src/auth/validate.ts:42..."` (good — synthesized)

### Worker Capabilities
Workers get either:
- **Simple mode** (`CLAUDE_CODE_SIMPLE`): Bash, Read, Edit only
- **Full mode**: All `ASYNC_AGENT_ALLOWED_TOOLS` minus internal tools (TeamCreate, TeamDelete, SendMessage, SyntheticOutput)

Workers also get MCP tools and scratchpad access (feature-gated behind `tengu_scratch`).

### Scratchpad
```typescript
if (scratchpadDir && isScratchpadGateEnabled()) {
  content += `\n\nScratchpad directory: ${scratchpadDir}\nWorkers can read and write here without permission prompts.`
}
```
Shared directory for cross-worker knowledge. No permission prompts needed.

---

## 3. SendMessage Tool — Three Transport Layers

SendMessage routes messages through THREE different backends:

### 3a. Teammate Mailbox (File-Based)
- Path: `~/.claude/teams/{team_name}/inboxes/{agent_name}.json`
- File locking with retries (10 retries, 5-100ms backoff)
- Messages have `read` boolean — inbox polling marks as read
- JSON format: `{from, text, timestamp, read, color?, summary?}`

### 3b. UDS (Unix Domain Socket)
- Prefix: `uds:<socket-path>` or bare `/path` (legacy)
- Cross-session messaging (different Claude Code processes)
- String messages only — structured messages blocked
- Dynamic import: `require('../../utils/udsClient.js')`

### 3c. Bridge (Remote Control)
- Prefix: `bridge:<session-id>`
- Cross-MACHINE messaging via Anthropic's servers
- Requires explicit user consent (safety check, not bypassable)
- Active connection validation before and after permission prompt

### Routing Logic (simplified)
```
if to starts with "bridge:" → handleBridge (cross-machine)
if to starts with "uds:" or "/" → handleUDS (cross-session)
if to matches agentId → route to in-process subagent
if to is "*" → broadcast to all team members
else → teammate mailbox (file-based)
```

---

## 4. Structured Protocol Messages

The mailbox carries 10 structured message types beyond plain text:

| Type | Purpose |
|------|---------|
| `idle_notification` | Worker went idle (available/interrupted/failed) |
| `permission_request` | Worker needs permission from leader |
| `permission_response` | Leader grants/denies permission |
| `sandbox_permission_request` | Worker needs network access |
| `sandbox_permission_response` | Leader grants/denies network |
| `shutdown_request` | Leader asks worker to stop |
| `shutdown_approved` | Worker agrees to stop |
| `shutdown_rejected` | Worker refuses (with reason) |
| `plan_approval_request` | Worker submits plan for review |
| `plan_approval_response` | Leader approves/rejects plan |
| `mode_set_request` | Leader changes worker's permission mode |
| `team_permission_update` | Leader broadcasts permission rule |
| `task_assignment` | Task assigned to teammate |

`isStructuredProtocolMessage()` checks the `type` field to route these to proper handlers (not consumed as raw text).

---

## 5. Comparison: CC Coordinator vs CCA cca_comm.py

| Feature | CC Coordinator Mode | CCA cca_comm.py |
|---------|-------------------|-----------------|
| **Transport** | File-based mailbox + UDS + Bridge | File-based JSONL queue |
| **Locking** | proper-lockfile with retries | fcntl.flock |
| **Message Types** | 10+ structured types | say, task, done, ack |
| **Workers** | In-process subagents + tmux + UDS | Separate Claude Code processes |
| **Coordination** | Real-time (inbox polling) | Poll-based (manual inbox check) |
| **Scope Claims** | Permission-based (leader grants) | Manual claim/release |
| **Permissions** | Leader can set mode, broadcast rules | N/A |
| **Cross-Machine** | Yes (bridge protocol) | No |
| **Plan Approval** | Worker submits → leader approves/rejects | N/A |
| **Scratchpad** | Shared directory, no permission prompts | N/A |
| **Shutdown** | Graceful request → approve/reject | N/A |

### What CC Has That CCA Should Steal

1. **Structured message types** — CCA uses free-text; CC uses typed JSON with schema validation (zod). Adopt this for reliability.

2. **Plan approval workflow** — Workers submit plans, leader approves before implementation begins. Prevents wasted work.

3. **Idle notifications** — Workers signal "I'm done" automatically (via Stop hook). CCA relies on manual `done` command.

4. **Permission delegation** — Leader can grant/revoke worker permissions mid-session. CCA has no runtime permission model.

5. **Scratchpad directory** — Shared workspace without permission prompts. CCA uses session state files but no formal shared workspace.

6. **Broadcast with `*`** — Send to all teammates at once. CCA has `broadcast` but CC's is more elegant (just `to: "*"`).

### What CCA Has That CC Doesn't

1. **Cross-project comms** — CCA routes between CCA and Kalshi via `cross_chat_queue.py`. CC coordinator is single-project.

2. **Explicit scope claiming** — CCA `claim/release` prevents file conflicts. CC relies on coordinator to not assign overlapping work (prompt-level, not enforced).

3. **Session persistence** — CCA queue survives across sessions (JSONL on disk). CC mailbox is session-scoped.

---

## 6. Implications for CCA Hivemind (MT-21)

### Short-term (adopt now)
- Add typed message schemas to `cca_internal_queue.py` (use dataclasses or TypedDict, not zod)
- Add idle notifications (auto-send `done` on session Stop hook)
- Add scratchpad concept: `~/.claude/cca-scratch/` for cross-worker temporary data

### Medium-term (Phase 3-4)
- Implement plan approval: worker proposes plan → desktop approves before coding
- Add runtime permission control: desktop can change worker access mid-session

### Long-term (when available)
- When Coordinator Mode goes GA, evaluate replacing cca_comm.py with native coordinator
- CCA's cross-project routing would remain a layer on top

---

## 7. Key Source Files for Further Study

| File | Lines | Purpose |
|------|-------|---------|
| `src/coordinator/coordinatorMode.ts` | 369 | Mode detection, system prompt, worker tool listing |
| `src/tools/SendMessageTool/SendMessageTool.ts` | 918 | Message routing (mailbox/UDS/bridge), structured types |
| `src/utils/teammateMailbox.ts` | 1184 | File-based inbox: read/write/lock, 10+ message type schemas |
| `src/utils/peerAddress.ts` | 22 | URI parsing: `uds:`, `bridge:`, bare paths |
| `src/constants/tools.ts` | — | ASYNC_AGENT_ALLOWED_TOOLS list |
| `src/utils/swarm/` | — | Team management, tmux backend, in-process runner |
