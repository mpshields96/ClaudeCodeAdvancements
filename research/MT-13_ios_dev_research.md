# MT-13: iOS App Development Capability — Research

**Date:** 2026-03-18 (Session 44)
**Status:** Research COMPLETE — prerequisites partially blocked

---

## Key Discovery: Xcode 26.3 Native Claude Integration

The iOS development landscape shifted significantly since MT-13 was created:

1. **Xcode 26.3 (Feb 2026)** — Native agentic coding with Claude Agent SDK built in
   - Claude Code runs directly inside Xcode (same harness as CLI)
   - Supports subagents, background tasks, plugins without leaving IDE
   - Can capture Xcode Previews to see SwiftUI output visually
   - Skills and MCPs supported via agents.md, skills folders, config.toml
   - Source: Apple newsroom, Anthropic announcements

2. **SwiftUI Agent Skill** (Paul Hudson / twostraws)
   - MIT-licensed skill for Claude Code, Codex, Gemini, Cursor
   - Addresses common SwiftUI mistakes made by LLMs
   - Covers accessibility, deprecated APIs, performance, navigation, state
   - Install: `npx skills add`, trigger: `/swiftui-pro`
   - Repo: github.com/twostraws/swiftui-agent-skill

3. **Claude Code iOS Dev Guide** (keskinonur)
   - PRD-driven workflow: PRD.md -> specs/ -> tasks/ -> implementation
   - Recommends MVVM with Swift 6 @Observable
   - Type-safe NavigationStack routing
   - Swift Testing framework with @Test macros
   - XcodeBuildMCP for all Xcode operations (not manual xcodebuild)
   - Repo: github.com/keskinonur/claude-code-ios-dev-guide

---

## Matthew's Machine Status

| Prerequisite | Status |
|---|---|
| Swift 6.2 | INSTALLED (Apple Swift 6.2) |
| Xcode | NOT INSTALLED (Command Line Tools only) |
| xcodebuild | NOT AVAILABLE (requires Xcode) |
| Swift Package Manager | BROKEN (missing SWBBuildService framework without Xcode) |
| iOS Simulator | NOT AVAILABLE (requires Xcode) |
| TestFlight CLI | NOT AVAILABLE (requires Xcode) |

**Blocker:** Full Xcode installation required before any iOS development work.
Xcode is ~12GB download from App Store. Matthew must install manually.

---

## Recommended Path Forward

### Option A: Install Xcode, use native Claude integration (RECOMMENDED)
- Install Xcode 26.3 from App Store
- Claude Code works natively inside Xcode (same plan Matthew already has)
- SwiftUI previews, simulator, TestFlight all available
- Add SwiftUI Agent Skill for quality guardrails
- Follow PRD-driven workflow from keskinonur guide

### Option B: CLI-only with xcodebuild (FALLBACK)
- Install Xcode for CLI tools (xcodebuild, xctest)
- Keep using Claude Code in terminal
- Use XcodeBuildMCP for build integration
- Lose visual preview capability

### Option C: Swift Package Manager only (MINIMAL)
- Server-side Swift or pure logic packages
- No SwiftUI, no simulator, no device deployment
- Not useful for Matthew's stated goals (mobile dashboards)

---

## First App Target

Per MASTER_TASKS.md: **Kalshi bot mobile dashboard**
- Reads from polybot.db via local API
- Shows P&L, active strategies, recent bets
- SwiftUI with MVVM architecture
- Requires: Xcode, iOS Simulator, device for TestFlight

---

## What CCA Should Build (once Xcode installed)

1. **SwiftUI project template** — CCA conventions (one file = one view, tests per view model)
2. **CLAUDE.md for iOS projects** — Swift/SwiftUI rules, architecture patterns
3. **XcodeBuildMCP integration** — build/test from Claude Code CLI
4. **SwiftUI Agent Skill** — install twostraws/swiftui-agent-skill

---

## Verdict

MT-13 is **blocked on Xcode installation** — a manual prerequisite Matthew must handle.
The ecosystem has matured significantly: Xcode 26.3 + Claude Agent SDK + SwiftUI skills
means the "capability gap" MT-13 was created to address has been largely solved by Apple
and the community. CCA's role shifts from "build iOS dev capability" to "configure and
template an iOS workflow using existing tools."

**Action required from Matthew:** Install Xcode 26.3 from App Store. Then CCA can:
1. Set up project template with CLAUDE.md
2. Install SwiftUI Agent Skill
3. Configure XcodeBuildMCP
4. Build Kalshi mobile dashboard

---

## Expanded Scope: macOS App Development (Matthew's request, Session 44)

Matthew noted macOS apps benefit from CCA work for obvious reasons — design skills,
general project enhancements, and native tooling for daily workflows.

### Proven: macOS Apps Shipped 100% with Claude Code

Indragie Karunaratne shipped **Context** (native macOS MCP debugger):
- 20,000 LOC, <1,000 hand-written (~95% Claude-generated)
- SwiftUI + AppKit hybrid, MVVM architecture
- Key patterns that worked:
  - "Context engineering" > prompt engineering — prime agent with docs first
  - Project-level CLAUDE.md with Swift/SwiftUI rules dramatically improved quality
  - XcodeBuildMCP for build integration
  - "ultrathink" for architectural decisions
  - Screenshot pasting for UI iteration feedback loops
  - Claude handled non-code tasks too: mock data, copy editing, release automation
- Pain points: Swift Concurrency, legacy vs modern API confusion, context compaction
- Source: indragie.com/blog

### Blitz: AI-Driven App Store Submission (Apache 2.0)

- Native macOS app with MCP servers for full iOS/macOS development lifecycle
- Capabilities via MCP: build, test, simulator management, App Store Connect submission,
  code signing, provisioning, IPA build/upload, metadata, screenshots, IAPs
- Supports Swift, Flutter, React Native projects
- 87 stars, actively maintained (v1.0.24, March 17 2026)
- Repo: github.com/blitzdotdev/blitz-mac

### Apple App Store: Vibe Coding Restrictions

- Apple blocking Replit-style apps that display generated code in embedded web views
- Guideline 2.5.2: apps may not download/install/execute code that changes functionality
- Does NOT affect apps BUILT with AI tools — only apps that ARE code execution platforms
- No impact on Matthew building his own apps with Claude Code

### macOS App Opportunities for CCA

| App Idea | Purpose | Priority |
|---|---|---|
| Kalshi mobile dashboard | P&L, strategies, bets | HIGH (MT-13 original) |
| CCA session monitor | Context health, token usage, session status | MEDIUM (like Recon Tamagotchi) |
| Design skills native preview | Live Typst/PDF preview | LOW |
| Claude Code session launcher | tmux alternative with native UI | LOW |

### Subreddit Intelligence

**r/iOSProgramming (top, month):** Mostly App Store review complaints, SwiftUI basics.
No frontier-relevant AI/Claude posts beyond the vibe coding blocking article.

**r/SwiftUI (top, month):** Mostly UI questions. One notable post: "Playing with Apple
Foundation Models in SwiftUI" — local on-device AI inference. Could be relevant for
local-first CCA tools.

**r/macapps (top, month):** Several indie macOS apps, mostly utilities. No direct
CCA relevance but validates the market for native macOS developer tools.

**r/ClaudeCode:** No specific macOS/iOS dev posts in current hot feed, but the
"Context" app story circulated widely. Strong community validation of SwiftUI + Claude Code.
