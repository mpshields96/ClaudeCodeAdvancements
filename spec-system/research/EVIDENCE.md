# spec-system — Research Evidence Base

## Primary Evidence

### #1 Most-Recommended Workflow Tip (Validated)
Spec-driven development is the single most consistently recommended workflow improvement across:
- r/ClaudeCode (multiple top threads)
- r/vibecoding (500+ comment analysis, solveo.co)
- Developer blogs: alexop.dev, paddo.dev, mortenvistisen.com
- Professional guides: humanlayer.dev, sankalp.bearblog.dev

### Token Optimization (Measured)
- 60-80% reduction in redundant document fetching when using spec-first workflow
- Source: developer experience reports aggregated at aitooldiscovery.com

### SWE-Bench Pro Data (Objective Benchmark)
- Best models score only 23.3% on long-horizon tasks (SWE-Bench Pro, Scale AI, Feb 2026)
- Root cause analysis: poor upfront task specification is the primary failure mode
- When tasks are well-specified, model accuracy improves substantially

### Amazon Kiro (Market Signal)
- Amazon released Kiro (January 2026) — an IDE purpose-built around spec-driven development
- Spec → implementation is the primary interaction model
- Proves the market exists; Kiro is enterprise-focused with no lightweight version

### Community Workflow Patterns (Prior Art)
- `claude-code-spec-workflow` (GitHub): automated Requirements → Design → Tasks pipeline
- `cc-sdd` (GitHub): Kiro-style spec-driven development enforcer, multi-agent compatible
- Both are unofficial workarounds proving the gap exists

### The "Plan Before Code" Consensus
- Use Plan Mode (Shift+Tab twice) before any non-trivial task — cited in top 3 tips in every beginner guide
- Source: ykdojo/claude-code-tips (45 tips), aitooldiscovery.com, redmonk.com

## Why Spec-Driven Works

### The Architecture Failure Mode
"Claude Code is excellent at bounded, well-specified tasks but struggles to maintain coherent architectural direction across long autonomous runs."
— SWE-Bench Pro analysis, Scale AI, 2026

The fix is not a smarter model — it's better upfront specification from the human.

### The Interview Pattern (Validated)
1. Have Claude ask clarifying questions about requirements
2. Write spec to `requirements.md`
3. Start a fresh session
4. Implement from spec

This pattern eliminates the largest class of failures: Claude jumping to implementation before understanding the task.

### The 500-Line Rule (Validated)
Large monolithic requests consistently underperform compared to decomposed sequential tasks.
The community standard is ~500 lines per task (empirically derived from usage patterns).
Source: aitooldiscovery.com synthesis of r/ClaudeCode threads

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| User skips the spec and goes straight to coding | High | PreToolUse hook warns (configurable: warn-only vs block) |
| Requirements document is too vague to be useful | Medium | Template with mandatory fields, validation check |
| Tasks list is too granular (analysis paralysis) | Low | Template caps at 20 tasks max, suggests merging if over |
| User abandons spec mid-session | Medium | Each command is independent — can resume at any step |
