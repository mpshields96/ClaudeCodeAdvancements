# Paseo Evaluation — Mobile Claude Code Access
# Source: getpaseo/paseo (GitHub, ~356 stars, AGPL-3.0)
# Written: S241 (2026-03-30)

## Verdict: DEFER

Not ready for adoption. Monitor for maturity. Anthropic's native `/remote-control` and SSH+Tailscale are safer alternatives today.

---

## What It Is

Open-source unified interface for managing coding agents (Claude Code, Codex, OpenCode) remotely from any device. Runs agents locally on your machine, connects via WebSocket from mobile/desktop clients.

## Architecture

1. **Server/Daemon** — Express + WebSocket (port 3000), tmux-based terminal management. Runs on YOUR machine.
2. **Clients** — Expo app (iOS/Android/web), Electron desktop, CLI (`@getpaseo/cli`)
3. **Relay** — Cloudflare Worker for remote access outside LAN. Claims E2E encryption (Ed25519 + X25519 + AES-256-GCM).
4. **Voice** — Claims "fully local" but `.env.example` includes Deepgram API keys (cloud STT/TTS).

## Security Assessment

| Aspect | Status | Concern Level |
|--------|--------|---------------|
| E2E encryption | Claimed, not audited | HIGH |
| Auth protocol | Undocumented (QR pairing mentioned) | HIGH |
| Security audit | None | HIGH |
| Telemetry | None claimed | LOW |
| Token extraction | Does not extract OAuth tokens | LOW |
| AGPL-3.0 source | Auditable | LOW |

**Core concern:** This tool gives remote shell access to your development machine. The authentication and encryption protocols are not publicly documented. No security audit exists. Single-developer project.

## Maturity

- Launched publicly ~5 days ago (HN Show, late March 2026)
- 44 open issues, 0 closed
- Android: blank UI bug on latest version
- iOS: unavailable in some regions
- Bus factor: appears to be one developer
- Not mentioned in any major Claude Code mobile guide
- No Reddit/community adoption signal yet

## Alternatives

| Tool | Maturity | Security | UX |
|------|----------|----------|----|
| **Anthropic /remote-control** | Shipped Feb 2026 | Native, Anthropic-maintained | Good |
| **SSH + Tailscale** | Battle-tested | Strong (WireGuard) | Terminal only |
| **Paseo** | Alpha (days old) | Unaudited | Best (native mobile app) |
| **claude.ai/code (mobile web)** | Stable | Anthropic-maintained | Good |

## Why DEFER (not SKIP)

- The architecture is sound — local daemon + E2E relay + multi-platform clients is the right design
- Solves a real pain point (native mobile UX for coding agents)
- AGPL means the code is auditable and can be verified over time
- If it matures (security audit, community adoption, bug fixes), it could be worth adopting

## Re-evaluate When

- Security audit published
- Auth protocol documented
- 1000+ stars with active community
- Android/iOS bugs resolved
- 3+ months of stable releases
