# Senior Dev Agent — Quick Reference

## What It Is

Multi-layer code review: static analysis (free, automatic) + LLM-powered deep review (API cost, on-demand).

## Tools

### 1. Passive Hook (automatic, free)

Fires on every Write/Edit via PostToolUse hook. No action needed.

**What it catches:** TODOs/HACKs, high complexity, naming issues, missing docs, quality scores below threshold.

**Output:** Natural language advice in additionalContext (not metric dumps).

**When useful:** Always-on background safety net. Catches mechanical issues you'd miss.

### 2. On-Demand Review (`/senior-review`)

Run before committing or after building a new module.

```
/senior-review
```

**What it does:** Full static review of recently changed files — quality score, SATD count, blast radius, ADR relevance, coherence check.

**Output:** Verdict (APPROVE / CONDITIONAL / REJECT) with specific concerns and suggestions.

**When useful:** Before committing significant work. After building a new module. When unsure if code is ready.

### 3. Interactive Chat (LLM, costs tokens)

Deep-dive a design decision or get architectural advice.

```bash
source ~/.zshrc  # ensure ANTHROPIC_API_KEY is set
python3 agent-guard/senior_chat.py <file>
```

**What it does:** Opens a REPL with your file's review context. Ask follow-up questions. Multi-turn conversation with history.

**When useful:** "Should I use approach X or Y?" / "Is this over-engineered?" / "What am I missing?"

### 4. Intent Verification (LLM, built into interactive mode)

Verifies code matches its stated purpose.

**When useful:** After building something — "Does this actually do what I said it does?" Catches drift between intent and implementation.

### 5. Trade-off Analysis (LLM, built into interactive mode)

Analyzes design trade-offs in context of project stage, team size, constraints.

**When useful:** Deciding between simple vs extensible, performance vs readability, one file vs abstraction.

## Cost Guide

| Tool | Token Cost | Frequency |
|------|-----------|-----------|
| Passive hook | 0 (regex/arithmetic) | Every Write/Edit |
| /senior-review | 0 (static analysis) | Before commits |
| Interactive chat | ~2-4K tokens/turn | On-demand |
| Intent check | ~2-4K tokens | On-demand |
| Trade-off analysis | ~3-5K tokens | On-demand |

## Architecture

```
senior_dev_hook.py          <- PostToolUse orchestrator (passive)
  |-- satd_detector.py      <- TODO/HACK/FIXME scanner
  |-- effort_scorer.py      <- LOC + complexity scoring
  |-- code_quality_scorer.py <- 5-dimension quality score
  |-- fp_filter.py          <- False positive filter
  |-- review_classifier.py  <- Finding categorization
  |-- tech_debt_tracker.py  <- SATD trend analysis
  |-- adr_reader.py         <- ADR discovery + relevance

senior_review.py            <- /senior-review skill (on-demand)
  |-- coherence_checker.py  <- Module structure + pattern consistency
  |-- blast radius          <- Import dependency graph

senior_chat.py              <- Interactive REPL (LLM-powered)
  |-- LLMClient             <- Anthropic Messages API
  |-- build_intent_check_prompt()
  |-- build_tradeoff_prompt()
  |-- git_context.py        <- File history, blame, churn
```

## Requirements

- Static features: No dependencies (stdlib only)
- LLM features: `ANTHROPIC_API_KEY` environment variable set in `~/.zshrc`
