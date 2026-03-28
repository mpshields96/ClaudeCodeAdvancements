# 3-Way Bridge Protocol — CCA Hub <-> Codex <-> Kalshi
# Created: S107 (2026-03-21)
# Updated: S217 (2026-03-27)
# Status: ACTIVE HUB MODEL

---

## Topology

CCA is the authoritative router/hub.

Codex and Kalshi do not need a direct file lane yet. The supported production
topology is:

1. CCA <-> Codex via repo-local bridge files
2. CCA <-> Kalshi via `~/.claude/cross-chat/` bridge files
3. CCA relays anything important across lanes so no context stays trapped

This keeps one source of operational truth while still enabling durable
bidirectional communication with both external chats.

## Bridge Files

| Lane | File | Writer | Reader | Location |
|------|------|--------|--------|----------|
| CCA -> Codex | `CLAUDE_TO_CODEX.md` | CCA / Claude Code | Codex | CCA repo |
| Codex -> CCA | `CODEX_TO_CLAUDE.md` | Codex | CCA / Claude Code | CCA repo |
| CCA -> Kalshi | `CCA_TO_POLYBOT.md` | CCA / Claude Code | Kalshi chats | `~/.claude/cross-chat/` |
| Kalshi -> CCA | `POLYBOT_TO_CCA.md` | Kalshi chats | CCA / Claude Code | `~/.claude/cross-chat/` |

## Routing Rules

### CCA <-> Codex

1. CCA writes requests, directives, and durable context to `CLAUDE_TO_CODEX.md`
2. Codex reads it at session start
3. Codex writes durable outcomes, risks, or relay-worthy notes to `CODEX_TO_CLAUDE.md`
4. CCA reads `CODEX_TO_CLAUDE.md` at session start and during wrap review

### CCA <-> Kalshi

1. CCA writes research findings, task briefs, and directives to `CCA_TO_POLYBOT.md`
2. Kalshi reads it at session start
3. Kalshi writes requests, status, and findings to `POLYBOT_TO_CCA.md`
4. CCA reads `POLYBOT_TO_CCA.md` at session start

### Cross-Lane Relay

CCA is responsible for relay when a message should propagate across lanes:

- Codex result relevant to trading or research -> relay to Kalshi
- Kalshi finding relevant to implementation or architecture -> relay to Codex
- Shared operational risk -> relay to both

Relay can be concise, but it must be explicit. Silence is not a relay.

### Codex Dual-Notify Rule

When Codex changes the Kalshi bot repo (`/Users/matthewshields/Projects/polymarket-bot/`):

- Codex notifies CCA directly
- Codex notifies Kalshi directly
- Codex leaves a durable note in `CODEX_TO_CLAUDE.md`

This is a standing rule for all Codex chats working on Kalshi-bot code or docs.
Do not rely on one recipient to forward it later. Dual notification is required
because the change affects both coordination lanes operationally.

## Session-Start Requirements

### CCA

CCA init/wrap should treat these as mandatory coordination context:
- `CLAUDE_TO_CODEX.md`
- `CODEX_TO_CLAUDE.md`
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md`
- `~/.claude/cross-chat/POLYBOT_TO_CCA.md`

### Codex

Codex init should read:
- `CLAUDE_TO_CODEX.md`
- `SESSION_RESUME.md`
- relevant Kalshi bridge notes when the task touches trading coordination

### Kalshi

Kalshi session start should read:
- `CCA_TO_POLYBOT.md`
- any relay CCA includes from Codex

## Message Style

All bridge files should be:
- Append-only
- Timestamped
- Concise but actionable
- Safe for future-session replay

Preferred content:
- What changed
- Why it matters
- What the receiving lane should do next
- Verification status when relevant

Avoid:
- Credentials or secrets
- Raw API keys
- Long conversational back-and-forth
- Hidden assumptions with no explicit action request

## Current State

### Working

- `CLAUDE_TO_CODEX.md` exists
- `CODEX_TO_CLAUDE.md` exists
- `CCA_TO_POLYBOT.md` exists
- `POLYBOT_TO_CCA.md` exists
- `SESSION_RESUME.md` generation now surfaces recent Codex/Kalshi bridge headings

### Still Manual

- CCA is still the manual relay point between Codex and Kalshi
- No direct Codex <-> Kalshi bridge file exists yet
- No polling/daemon sync exists across all four bridge files

## Phase-Up Path

If the hub model proves reliable, the next optional upgrade is a direct Codex
summary lane for Kalshi. Do that only if CCA relay becomes the bottleneck.

Until then, the rule is simple:

CCA stays aware of both external lanes and relays intentionally.

## Safety

- CCA remains the authority for cross-lane routing
- Codex should not assume live-trading authority
- Kalshi should not assume repo-state authority
- Durable bridge notes should complement, not replace, repo tests and commits
