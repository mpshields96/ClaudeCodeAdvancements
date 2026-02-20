# /spec:requirements

Run a structured interview to produce a `requirements.md` file before any code is written.

## What This Command Does

Guides you through a Socratic interview about what you're building. At the end, produces a `requirements.md` document that Claude will use as the authoritative definition of the feature — before design, before code.

**You review and approve `requirements.md` before anything else happens.**

---

## Interview Questions

Work through each section below. Ask one section at a time. Wait for the user's answer before proceeding to the next. Do not skip sections.

### Section 1 — Purpose

Ask:
1. "What does this feature/tool/app do? Describe it in one sentence as if explaining to someone who has never seen it."
2. "Who uses it? (e.g., you alone, a team, end users of an app, Claude Code itself?)"
3. "What problem does it solve? What is the user doing today without this, and why is that worse?"

### Section 2 — Scope

Ask:
4. "What does this feature do? List everything it must do to be considered complete."
5. "What does this feature explicitly NOT do? Name at least two things that are out of scope."
6. "Are there any hard constraints? (e.g., must work offline, must use only stdlib, must complete in < 2 seconds, must not require any installation)"

### Section 3 — Inputs and Outputs

Ask:
7. "What are the inputs? What does the user or system provide to trigger this?"
8. "What are the outputs? What does the user see or receive when it works correctly?"
9. "What does success look like? Describe the happy path in one sentence."

### Section 4 — Failure Modes

Ask:
10. "What can go wrong? Name the three most likely failure modes."
11. "For each failure: what should happen? (e.g., show an error message, silently skip, abort and explain)"
12. "Is there any data or state that must never be lost or corrupted, even if the tool crashes?"

### Section 5 — Acceptance Criteria

Ask:
13. "How will you know this is done? Describe the test you would run to confirm it works."
14. "Are there any performance requirements? (e.g., must handle 1000 files, must respond in < 500ms)"
15. "Any other constraints or requirements we haven't covered?"

---

## After the Interview

Once all sections are answered, generate the `requirements.md` file using the template below. Write it to the project root (or the path the user specifies).

Then say: **"Here is your `requirements.md`. Review it carefully. When you're satisfied, say 'approved' and we'll generate `design.md`. Do NOT start implementing until requirements and design are both approved."**

Do NOT generate design.md yet. Do NOT suggest implementation approaches. Do NOT write any code.

---

## Output Template

Write `requirements.md` with exactly this structure:

```markdown
# Requirements: [Feature Name]
Generated: [YYYY-MM-DD]
Status: DRAFT — not yet approved

---

## Purpose
**One-sentence description:** [from Q1]
**Users:** [from Q2]
**Problem solved:** [from Q3]

---

## Scope

### In Scope
[Numbered list from Q4 — everything this must do]

### Out of Scope
[Numbered list from Q5 — at least 2 explicit exclusions]

### Hard Constraints
[List from Q6 — technical constraints, e.g., stdlib only, offline, etc.]

---

## Interface

### Inputs
[From Q7 — what triggers this feature, what data is provided]

### Outputs
[From Q8 — what the user receives]

### Happy Path
[One sentence from Q9]

---

## Failure Modes

| Failure | Expected Behavior |
|---------|------------------|
| [from Q10/Q11, one row per failure] | |

**Data integrity:** [from Q12 — what must never be lost]

---

## Acceptance Criteria

- [ ] [From Q13 — the test that confirms it works]
- [ ] [From Q14 — performance requirements, if any]
- [ ] [Any additional from Q15]

---

## Approved
[ ] Approved by user on [date]
```

---

## Rules for This Command

- Never skip the interview to jump to implementation
- Never generate code during this command
- Never generate `design.md` during this command
- If the user tries to skip to implementation, redirect: "Let's finish requirements first — it takes 5 minutes and prevents hours of rework."
- If an answer is vague, ask one clarifying follow-up before moving on
- The `Status: DRAFT — not yet approved` line stays until the user says "approved"
- When the user says "approved", update the file: change `Status: DRAFT` → `Status: APPROVED` and fill in the date
