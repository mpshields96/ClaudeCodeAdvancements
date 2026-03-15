---
created: 2026-03-15T06:46:08.047Z
title: Adopt Ouro Loop IRON LAWS + DANGER ZONES + hook enforcement (exit 2) pattern for agent-guard Frontier 4
area: general
files: []
---

## Problem

agent-guard (Frontier 4) currently handles multi-agent file conflict prevention but lacks a structured enforcement contract. Ouro Loop (github.com/VictorVVedtion/ouro-loop) introduces:
- IRON LAWS: non-negotiable behavioral constraints the agent must obey
- DANGER ZONES: categorized high-risk operations that trigger extra scrutiny
- Hook enforcement via exit code 2: hooks return exit 2 to block/deny tool calls rather than soft-failing

Current agent-guard hooks use the approved PreToolUse deny format (`hookSpecificOutput.permissionDecision: "deny"`) but do not apply a tiered IRON LAWS / DANGER ZONES conceptual layer. Adopting Ouro Loop's pattern would give agent-guard a clearer enforcement contract and make the deny logic more maintainable.

## Solution

1. Review github.com/VictorVVedtion/ouro-loop for the exact IRON LAWS + DANGER ZONES schema
2. Map Ouro Loop's exit 2 enforcement to agent-guard's existing PreToolUse deny format (confirmed: `hookSpecificOutput.permissionDecision: "deny"`)
3. Define agent-guard IRON LAWS (e.g. "never write outside owned paths") and DANGER ZONES (e.g. "write to .env, delete, overwrite cross-agent files")
4. Update credential_guard.py and ownership.py hooks to enforce via these tiers
5. Add tests covering each IRON LAW and DANGER ZONE trigger
