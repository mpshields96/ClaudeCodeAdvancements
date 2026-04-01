# Agentic Workflow Research — 10 Principles (JD Forsythe)
# Source: jdforsythe.github.io/10-principles/ — 17 peer-reviewed papers (2017-2026)
# Chat 13A (S245). Focus: actionable gaps for CCA's custom agent builds.

---

## Critical Findings for CCA Agent Design

### 1. PRISM Identities — Keep Under 50 Tokens

Brief identities (20-50 tokens) with real job titles outperform long personas.
Flattery degrades output — "world's best expert" routes to motivational content,
not expertise. Real titles route to real training data clusters.

**CCA gap:** Our agent designs in CUSTOM_AGENTS_DESIGN.md use only `description`
for identity. Should add a terse role line (real job title) + 15-30 domain vocabulary
terms as the primary quality lever. Vocabulary routing (Ranjan et al. 2024) shows
that expert terminology activates expert knowledge clusters.

**Action:** Each Phase 4 agent gets:
- Role: 1 line, real job title, <30 tokens
- Vocabulary payload: 15-30 domain terms (first in prompt body — front-loading)
- No flattery, no "world-class" or "expert" superlatives

### 2. 45% Multi-Agent Threshold — CCA Is Already Right-Sized

DeepMind 2025: if one agent achieves >45% optimal performance, adding more yields
diminishing returns. Team size saturates at 4 agents. At 7+, output INVERTS.

| Team Size | Token Cost | Effective Output | Efficiency |
|-----------|-----------|-----------------|-----------|
| 1 agent | 1.0x | 1.0x | 1.00 |
| 3 agents | 3.5x | 2.3x | 0.66 |
| 5 agents | 7.0x | 3.1x | 0.44 |
| 7+ agents | 12.0x+ | 3.0x or less | <0.25 |

**CCA validation:** Our 2-chat hivemind (desktop + worker) is at Cascade Level 3.
This is optimal. The plan for 4 custom agents (test-runner, reviewer, senior-reviewer,
scout) stays WITHIN the 4-agent saturation point. Do not add more.

Sequential reasoning degrades 39-70% in multi-agent vs single agent. Keep analysis
tasks (senior review, architecture decisions) single-agent.

### 3. Rubber-Stamp Prevention — Structural Fix Required

"If your review agent approves >85% in <5 seconds, you have a rubber stamp."
Self-evaluation fails: if the model missed a vulnerability while generating, it
will miss it while reviewing (Anthropic Harness Design, March 2026).

**CCA gap:** Our senior-reviewer agent design already uses disallowedTools: Edit,Write
(can't fix issues, must articulate them). But we need to add:
- Require at least 1 identified issue OR explicit evidence-based justification
- Run deterministic checks FIRST (build, lint, test) — 100% reliability, zero tokens
- Track approval rate: if >85%, the reviewer is broken

**Action for senior-reviewer agent prompt:**
```
You MUST either:
1. Identify at least one issue (real, not manufactured), OR
2. Justify clearance with specific evidence (line numbers, test coverage, etc.)
"LGTM" with no analysis is FORBIDDEN.
```

### 4. Lost-in-Middle — U-Shaped Attention Curve

Liu et al. 2024: >30% accuracy drop for mid-context info. Architectural cause
(causal masking + RoPE), not a bug. Middle of context is a measured dead zone.

**CCA gap:** Our CLAUDE.md is 11.4K tokens (Chat 12D audit). Critical rules buried
in the middle are being ignored. The 58% reduction plan in CLAUDE_MD_TOKEN_AUDIT.md
is even more urgent given this evidence.

**Agent prompt structure (from Principle 10):**
```
FRONT (highest attention):
  - Identity (real job title, <30 tokens)
  - Vocabulary payload (15-30 terms)
  - Non-negotiable constraints
  - Anti-patterns (what NOT to do)

MIDDLE (lowest attention — use structure, not prose):
  - Numbered step-by-step instructions
  - Supporting context
  - Conditional logic

END (recency boost):
  - Output format specification
  - Examples (BAD vs GOOD, most representative last)
  - Checklist / "Questions This Skill Answers"
```

Optimal context utilization: 15-40% of window. Above 60%, relevant info gets buried.

---

## Additional Principles for Phase 4

### Vocabulary Routing (Principle 6)
Expert terminology activates expert knowledge. "OWASP Top 10 audit, STRIDE threat model"
routes to security engineering. "Review the security" routes to blog posts.
Each agent needs a vocabulary payload matching what a 15-year practitioner would use.

### Hardening Principle (Principle 1)
Every fuzzy LLM step that must behave identically every time → replace with deterministic tool.
LLM orchestrates and reasons; tools execute. Reliability: ~70% → 100%.
For cca-test-runner: the test execution IS the hardened tool; the agent just orchestrates.

### Living Documentation (Principle 3)
Stale agent definitions = poisoned context. Add `last-verified` metadata.
3 well-chosen examples match 9 in effectiveness (LangChain 2024).
Format matters: up to 40% performance variation from prompt format alone.

### MAST Failure Taxonomy
14 failure modes across communication (message loss, stale context), coordination
(deadlock, role confusion), and quality (rubber-stamp, error cascading, groupthink).
Use as diagnostic checklist when agents misbehave.

---

## Immediate Actions (Phase 4 Prep)

1. **Revise agent prompts**: front-load identity + vocabulary, back-load format + examples
2. **Add vocabulary payloads**: 15-30 domain terms per agent
3. **Senior-reviewer**: add mandatory issue/justification requirement
4. **CLAUDE.md reduction**: execute Tier 1 of the 58% plan (lost-in-middle urgency)
5. **Track approval rates**: if senior-reviewer >85% approval, it's broken
6. **Keep total agents <= 4**: saturation point confirmed by research
