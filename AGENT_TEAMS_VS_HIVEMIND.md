# Native Agent Teams vs CCA Hivemind — Chat 11C Evaluation (S244)
# 15-min time-boxed comparison. Verdict informs MT-21 direction.

---

## Systems Compared

### 1. CC Native Agent Teams (Experimental)
- Source: claude-howto/04-subagents Module 15
- Status: Experimental, requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Architecture: Team lead + teammates with shared task list + mailbox
- Display: in-process (inline) or tmux split-panes

### 2. CCA Hivemind (Custom, MT-21)
- Source: cca_comm.py (480 LOC) + cca_internal_queue.py + cross_chat_queue.py
- Status: Production, used daily in dual-chat mode
- Architecture: Desktop coordinator + CLI workers with JSONL queue + scope claiming
- Display: Separate terminal windows

### 3. Coordinator Mode (From CC Source Leak)
- Source: FINDINGS_LOG entry #1 (2026-03-31, CC source leak)
- Status: Unreleased/internal (CLAUDE_CODE_COORDINATOR_MODE=1 env var)
- Architecture: Parallel workers spawned by coordinator
- Note: Cannot be tested — no actual TS source cloned yet. Evaluate from docs only.

### 4. UDS Inbox (From CC Source Leak)
- Source: FINDINGS_LOG entry #1 (CC source leak)
- Status: Unreleased/internal
- Architecture: Unix Domain Socket for multi-session communication
- Note: Cannot be tested — evaluate from docs only.

---

## Feature Comparison

| Feature | CC Agent Teams | CCA Hivemind | Coordinator Mode | UDS Inbox |
|---------|---------------|--------------|-----------------|-----------|
| **State sharing** | Shared task list (native) | JSONL queue (file-based) | Unknown (parallel workers) | Socket-based messages |
| **Communication** | Mailbox (inter-agent) | cca_comm.py say/task/ack | Unknown | Unix socket |
| **Scope protection** | Not mentioned | claim/release (file-level) | Unknown | N/A |
| **Different models** | Not mentioned | Yes (Opus desktop + Sonnet worker) | Unknown | N/A |
| **Separate terminals** | Yes (tmux mode) | Yes (separate windows) | Unknown | Unknown |
| **Session resumption** | NO (explicitly unsupported) | Yes (file-based = persistent) | Unknown | Unknown |
| **Dependency tracking** | Automatic | Manual (task ordering) | Unknown | N/A |
| **Max team size** | 3-5 recommended | 2-3 tested | Unknown | N/A |
| **Hook integration** | TeammateIdle, TaskCompleted | PostToolUse (loop guard) | Unknown | Unknown |
| **Setup cost** | Zero (built-in) | ~480 LOC custom code | Unknown | Unknown |
| **Cross-project** | Same session only | Cross-chat queue to Kalshi | Unknown | Multi-session |
| **Stability** | Experimental | Production-tested | Unreleased | Unreleased |

---

## Strengths of CC Agent Teams

1. **Zero setup cost.** No custom code needed — just enable the env var and ask Claude
   to spawn teammates. Our hivemind required ~1000 LOC of custom infrastructure.

2. **Automatic dependency management.** Shared task list tracks dependencies natively.
   Our hivemind relies on manual task ordering and scope claims.

3. **Native hooks.** TeammateIdle and TaskCompleted hooks enable reactive automation
   (e.g., assign follow-up work when a teammate finishes). Our hivemind has no
   equivalent — we poll the inbox.

4. **Integrated display.** tmux split-pane mode gives visual coordination. Our approach
   requires manually arranging terminal windows.

5. **Mailbox system.** Purpose-built inter-agent messaging. Our JSONL queue works but
   is a filesystem hack compared to a native communication channel.

---

## Strengths of CCA Hivemind

1. **Session persistence.** File-based queues survive session restarts, crashes, and
   even macOS reboots. Agent Teams explicitly do NOT support session resumption for
   in-process teammates. This is a dealbreaker for our overnight sessions.

2. **Cross-project communication.** cca_comm.py + cross_chat_queue.py bridges CCA
   and Kalshi sessions. Agent Teams only work within a single session — they cannot
   coordinate across separate projects.

3. **Different models per chat.** We run Opus on desktop + Sonnet on workers.
   Agent Teams docs don't mention per-teammate model control (though this may be
   possible via agent frontmatter — untested).

4. **Scope claiming.** Explicit file-level scope claims prevent workers from colliding.
   Agent Teams recommend "assign different files to different teammates" but have no
   enforcement mechanism.

5. **Production stability.** Our hivemind is tested and proven over 100+ sessions.
   Agent Teams is experimental with explicit warnings about behavior changes.

6. **Non-blocking independence.** Each CCA chat is a fully independent Claude session
   with its own context, hooks, CLAUDE.md. Agent Teams teammates share a session.

---

## Coordinator Mode + UDS Inbox Assessment

Cannot evaluate hands-on — these are unreleased internal features found in the leaked
source code. Based on the FINDINGS_LOG entry:

- **Coordinator Mode** appears to be the production version of what Agent Teams is the
  experimental preview of. If Anthropic ships this publicly, it could supersede both
  Agent Teams and our hivemind.

- **UDS Inbox** solves the cross-session communication problem that Agent Teams lacks.
  This is architecturally similar to what cca_comm.py does via files, but using sockets
  for lower latency.

**Action for Chat 12:** When the real TS source is cloned (12A), study Coordinator Mode
and UDS Inbox implementations. This is the most important study item for MT-21 direction.

---

## Verdict: COMPLEMENT (use alongside, don't replace)

**Do NOT replace the hivemind with Agent Teams.** Three blocking issues:

1. **No session resumption** — kills overnight/multi-session workflows
2. **No cross-project communication** — kills CCA <-> Kalshi bridge
3. **Experimental status** — API may change, breaking our production flow

**DO adopt Agent Teams for specific use cases where it excels:**

1. **Intra-session parallelism** — when a single CCA session needs 2-3 parallel tasks
   done on the same codebase (e.g., "run tests while I review this file"). Agent Teams
   is perfect for this because it's zero-setup and auto-coordinates.

2. **Phase 4 agent builds** — the cca-reviewer, senior-reviewer, and cca-scout agents
   designed in 11B can work as teammates within a /cca-nuclear session, each reviewing
   different URLs in parallel.

**The hybrid architecture:**

```
CCA Ecosystem (cross-session, cross-project):
  CCA Desktop  <--cca_comm.py/cross_chat_queue--> Kalshi Main
       |
       |--> CCA CLI Worker (via hivemind queue)

Within a single CCA session (intra-session parallelism):
  Main agent
       |--> Agent Team: reviewer-1 (URL review)
       |--> Agent Team: reviewer-2 (URL review)
       |--> Agent Team: test-runner (parallel tests)
```

The hivemind handles cross-session coordination (overnight, multi-project).
Agent Teams handles intra-session parallelism (within a single chat).
They operate at different levels and complement rather than compete.

---

## Impact on MT-21

MT-21 (Hivemind) should:
1. **Keep** cca_comm.py as the cross-session/cross-project backbone
2. **Add** Agent Teams as an optional intra-session parallelism layer
3. **Watch** Coordinator Mode + UDS Inbox — if these ship publicly, they may
   provide a native replacement for cca_comm.py's cross-session capabilities
4. **Evaluate** in Chat 12B when actual TS source is studied

**No code changes needed now.** This is a strategic direction document.
