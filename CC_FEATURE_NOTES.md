# CC Feature Notes — Chat 11A Exploration (S244)
# 15-min hard cap feature exploration. Try each once, note verdict.

---

## 1. `--bare` Mode

**What it does:** Minimal startup — skips hooks, LSP, plugin sync, attribution, auto-memory,
background prefetches, keychain reads, and CLAUDE.md auto-discovery. Sets CLAUDE_CODE_SIMPLE=1.

**Tested:** `claude --help` confirms flag exists. Cannot test `-p` mode (no API key for direct
invocation — CCA runs on Claude Max subscription, not API key). Flag is real and documented.

**Verdict: USEFUL for CCA tooling.** Any CCA script that shells out to `claude -p` (e.g.,
batch operations, agent spawning from Python) would benefit from --bare for faster startup.
Currently no CCA scripts use `claude -p`, but this is relevant for Phase 4 agent design.
Key caveat: --bare skips CLAUDE.md loading, so agents need context provided via
`--system-prompt-file`, `--add-dir`, or `--agents` flag explicitly.

---

## 2. `/btw` Side Query

**What it does:** Allows asking an unrelated question without polluting the main context.
The side query runs in a separate context and returns the answer.

**Tested:** Available in interactive mode only. Cannot test via `-p` pipe mode.
Per Boris Cherny tips (Mar 30), this preserves main conversation context.

**Verdict: NICE-TO-HAVE.** Useful for Matthew interactively (quick lookup without
derailing a deep implementation session). Not relevant for CCA automation — our
agents already use separate context windows. No action needed.

---

## 3. `--max-turns` CLI Flag

**What it does:** Does NOT exist as a CLI flag. `maxTurns` is a **frontmatter-only field**
for agent `.md` files. Confirmed by checking `claude --help` — no `--max-turns` flag.

**Correct usage:** Set `maxTurns: N` in `.claude/agents/*.md` frontmatter to cap how many
agentic turns a spawned subagent can take. This prevents runaway agents.

**Verdict: CRITICAL for 11B agent design.** Every CCA custom agent should have a maxTurns
cap. GSD agents currently have NO maxTurns set — potential runaway risk.

---

## 4. Agent Frontmatter Fields (Full Inventory)

**Tested:** Read claude-howto/04-subagents/README.md + all 11 GSD agent files.

**16 available fields:**
| Field | GSD Uses? | CCA Should Use? |
|-------|-----------|-----------------|
| name | Yes | Yes |
| description | Yes | Yes (optimize as trigger mechanism) |
| tools | Yes | Yes |
| disallowedTools | No | YES — scope down for safety |
| model | No (inherit) | YES — sonnet for cheap tasks, opus for quality |
| permissionMode | No | Maybe — bypassPermissions for fully autonomous agents |
| maxTurns | No | YES — prevent runaway |
| skills | No | YES — preload domain knowledge |
| mcpServers | No | Maybe — scope MCP per agent |
| hooks | No | Maybe — agent-scoped safety hooks |
| memory | No | Maybe — project-scoped memory |
| background | No | Maybe — background research agents |
| effort | No | YES — high for review, low for quick tasks |
| isolation | No | Maybe — worktree for risky operations |
| initialPrompt | No | YES — auto-start for automated agents |
| color | Yes | Yes — visual distinction |

**Key insight:** GSD agents only use 4 of 16 fields (name, description, tools, color).
CCA custom agents should use at least 8-10 fields for proper scoping and safety.

**`--agents` JSON flag:** Allows defining agents inline at session launch without `.md` files.
Format: `claude --agents '{"name": {"description": "...", "prompt": "...", "tools": [...]}}'`
This is useful for ephemeral/session-specific agents.

---

## Summary

| Feature | Verdict | Action |
|---------|---------|--------|
| `--bare` | USEFUL | Use when CCA scripts shell out to `claude -p` |
| `/btw` | NICE-TO-HAVE | No CCA action; useful for Matthew interactively |
| `--max-turns` | DOES NOT EXIST | Use `maxTurns` frontmatter in agents instead |
| Agent frontmatter | CRITICAL GAP | 12 unused fields in GSD agents; CCA agents should use 8-10 |
