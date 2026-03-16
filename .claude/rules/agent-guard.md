---
globs: agent-guard/**
---

# Agent Guard Rules (Frontier 4)

- Credential regex MUST include hyphens: `sk-[A-Za-z0-9\-]{20,}` (keys contain `sk-ant-api03-...`)
- PreToolUse deny format: `hookSpecificOutput.permissionDecision: "deny"`
- Top-level `decision: "block"` on PreToolUse silently fails — wrong format
- Mobile approver uses ntfy.sh — fails open if no network or no topic configured
- Ban list approach preferred over --dangerously-skip-permissions (safer, scoped)
- Never log API keys, account balances, trade data, or wallet addresses
