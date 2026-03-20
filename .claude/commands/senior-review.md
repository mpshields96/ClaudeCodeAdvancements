# /senior-review — On-Demand Senior Developer Code Review

Review a file (or the most recent Write/Edit target) as a senior developer would.
Produces a structured verdict: APPROVE / CONDITIONAL / RETHINK.

---

## Usage

```
/senior-review path/to/file.py
/senior-review                    # reviews most recently written/edited file
```

The argument `$ARGUMENTS` contains the file path (if provided).

---

## Step 1 — Determine target file

If `$ARGUMENTS` is provided and non-empty, use that as the file path.

If no argument, check the conversation for the most recent Write or Edit tool call
and use that file path. If no recent file is found, ask the user which file to review.

---

## Step 2 — Run the review engine

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 -c "
import json, sys
sys.path.insert(0, 'agent-guard')
from senior_review import review_file
result = review_file('TARGET_FILE_PATH')
print(json.dumps(result, indent=2))
"
```

Replace `TARGET_FILE_PATH` with the resolved file path from Step 1.

---

## Step 3 — Read the file yourself

Also read the target file directly so you can provide qualitative feedback beyond
what the automated metrics catch. Look for:

- Does this file follow the project's "one file = one job" principle?
- Are there implicit dependencies that should be explicit?
- Is the error handling appropriate (not over-engineered, not missing)?
- Would a new team member understand this code without extra context?
- Are there naming choices that could be clearer?

---

## Step 4 — Deliver the review

Output a structured review in this format:

```
SENIOR REVIEW — [filename]

Verdict: [APPROVE / CONDITIONAL / RETHINK]

Metrics:
  LOC: [n]  |  Quality: [grade] ([score]/100)  |  Effort: [label] ([n]/5)
  SATD: [n] markers ([n] HIGH)

[If CONDITIONAL or RETHINK — list concerns as bullet points]

Concerns:
- [concern 1]
- [concern 2]

[If any suggestions from quality dimensions]

Suggestions:
- [suggestion 1]

[Your qualitative assessment — 2-3 sentences max, written as a senior developer
would speak to a colleague. Direct, specific, actionable.]

Senior take: [your qualitative paragraph here]
```

---

## Rules

- Be direct and specific, not generic. "This function mixes I/O with logic" beats "consider refactoring."
- Never soften a RETHINK verdict. If the code has structural problems, say so clearly.
- APPROVE does not mean perfect — it means "good enough to ship, no blocking issues."
- CONDITIONAL means "fix these specific things, then it's good."
- RETHINK means "step back and reconsider the approach before writing more code."
- Do not add suggestions that are purely stylistic preferences.
- Keep the entire review under 30 lines.
