# /spec:design-review — Multi-Persona Design Review

Review a `design.md` from multiple expert perspectives before implementation begins.

## Precondition Check

Before starting, verify:
1. `design.md` exists in the project root (or path the user specifies)
2. The file contains `Status: APPROVED` or is ready for review

If design.md is missing: "Run `/spec:design` first to create the architecture design."

---

## What This Command Does

Simulates a design review panel where 4 expert personas each review the same `design.md` and provide feedback from their domain perspective. This catches blind spots that a single-perspective review misses.

**No code is written during this phase.** Output is a consolidated review with actionable feedback.

---

## The Review Panel

Adopt each persona sequentially. For each, read the full design.md and provide feedback strictly from that persona's perspective.

### Persona 1: UX Researcher
**Focus:** User experience, workflow friction, edge cases in user interaction
**Questions to answer:**
- Does this design create unnecessary steps for the user?
- Are error states handled in a way the user will understand?
- What happens when the user does something unexpected?
- Is the mental model clear — will users understand what's happening?

### Persona 2: Security & Privacy Engineer
**Focus:** Attack surface, data exposure, credential handling, trust boundaries
**Questions to answer:**
- What data flows between components? Is any of it sensitive?
- Are there trust boundary crossings that need validation?
- Could any component be abused to access unauthorized data?
- Does the design follow principle of least privilege?
- Are credentials, API keys, or PII handled safely?

### Persona 3: Performance & Scalability Architect
**Focus:** Resource usage, bottlenecks, scaling limits, token/cost efficiency
**Questions to answer:**
- What are the hot paths? Where will latency or cost concentrate?
- Are there N+1 query patterns, unbounded loops, or memory leaks?
- How does this scale with usage (10x users, 10x data)?
- For Claude Code tools: what's the token cost profile?
- Could any operation block the main flow?

### Persona 4: Maintainability & Testing Engineer
**Focus:** Code organization, testability, future extensibility, one-file-one-job
**Questions to answer:**
- Can each component be tested in isolation?
- Does the file structure follow one-file-one-job?
- Are there hidden coupling points between components?
- What happens when a dependency changes or breaks?
- Is there unnecessary abstraction or premature generalization?

---

## Output Format

For each persona, output:

```
## [Persona Name] Review

### Strengths
- [What this design does well from this perspective]

### Concerns
- [SEVERITY: HIGH/MEDIUM/LOW] [Specific concern with explanation]

### Recommendations
- [Actionable change with rationale]
```

Then produce a consolidated summary:

```
## Consolidated Review Summary

### Critical Issues (must fix before implementation)
1. [Issue] — raised by [persona]

### Recommended Changes (should fix)
1. [Change] — raised by [persona]

### Noted but Acceptable
1. [Observation] — raised by [persona]

### Review Verdict: APPROVE / REVISE / REDESIGN
[One-sentence rationale]
```

---

## After Review

- If verdict is **APPROVE**: The user can proceed to `/spec:tasks`
- If verdict is **REVISE**: Update design.md to address critical/recommended issues, then re-review
- If verdict is **REDESIGN**: Fundamental architectural issues — go back to `/spec:design`

---

## Rules

- Each persona reviews independently — don't let one persona's concerns bias another
- Be specific — "this could be a problem" is not useful; "the credential_guard.py reads env vars without sanitizing shell metacharacters" is
- Severity ratings matter — not every concern is HIGH
- Stay in character — the UX researcher doesn't opine on database indexing
- No code suggestions — this is design review, not implementation
