# /review — Adversarial Code Review

Run a findings-only code review. No compliments. No invented issues. Only real bugs.

Adapted from the OpenAI Codex review prompt (open source). Criteria and output format
in `~/.claude/commands/references/review-criteria.md` and `review-output-format.md`.

---

## What to review

The argument after `/review` tells you what to review. Parse it:

| Argument | What to do |
|----------|-----------|
| (nothing) | Review staged diff: `git diff --cached` |
| `HEAD` | Review last commit: `git diff HEAD~1 HEAD` |
| `HEAD~N` | Review last N commits: `git diff HEAD~N HEAD` |
| A file path | Read the file and review it in full |
| `PR #N` | Run `gh pr diff N` and review that diff |
| Pasted code | Review the code pasted directly in the message |

If the argument is ambiguous, default to `git diff HEAD~1 HEAD` (last commit).

---

## Steps

### 1. Get the code to review

Run the appropriate command above to get the diff or file content.

### 2. Read the review criteria

The full criteria are in `~/.claude/commands/references/review-criteria.md`.

Key rules:
- Only flag issues **introduced by this change**, not pre-existing ones
- Only flag things the author **would definitely fix** if you told them
- P0 = blocks ship | P1 = fix this sprint | P2 = normal | P3 = nitpick
- No compliments, no LGTMs, no invented findings
- Max 10 findings — pick the highest priority if there are more

### 3. Analyze the diff

For each file/hunk in the diff:
- Check for: null/None dereferences, off-by-one errors, missing error handling at boundaries,
  race conditions, SQL/command injection, unvalidated input, type mismatches, logic inversions,
  resource leaks, incorrect algorithm
- Apply the "author would definitely fix" filter before including anything
- Assign P0/P1/P2/P3 based on criteria

### 4. Output findings using the format in `review-output-format.md`

Exact format:

```
## Code Review — [what was reviewed]

### Findings

[P0] path/file.py:L42 — One-line problem title.

Why: Exact condition that triggers this (when X / if Y is None / on concurrent write).
Fix: `concrete_fix` or a ≤3 line code block.

---

(repeat for each finding, P0 first)

### Verdict

VERDICT: [Ship / Ship with changes / Rethink]

P0 items blocking ship:
- (list P0s or "none")
```

If zero findings: output exactly `No findings. VERDICT: Ship.`

---

## Anti-patterns (never do these)

- "This looks good overall" — silence is the compliment
- "You might want to consider..." — only flag what they would definitely fix
- Flagging style that doesn't obscure meaning
- Inventing findings to seem thorough
- Saying LGTM or any variant
- Flagging pre-existing issues not introduced by this diff
