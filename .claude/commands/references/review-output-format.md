# /review — Output Format

## Structure

```
## Code Review — [filename or "staged diff" or "PR #N"]

### Findings

[P0] path/to/file.py:L42 — Brief problem title.

Why: The exact condition that causes this (when X happens / if Y is None / on concurrent access).
Fix: `concrete_fix_here` or a 1-3 line code block showing the fix.

---

[P1] path/to/other.py:L87 — Brief problem title.

Why: ...
Fix: ...

---

(repeat for each finding, sorted P0 → P1 → P2 → P3)

### Verdict

VERDICT: [Ship / Ship with changes / Rethink]

- Ship: No P0 or P1 findings. Patch is correct.
- Ship with changes: P1s present (list them). P0s absent.
- Rethink: P0s present (list them). Do not ship until resolved.

P0 items blocking ship:
- [P0] file.py:L42 — description
(list all P0s, or "none" if verdict is Ship)
```

## Rules

- If zero findings: output exactly `No findings. VERDICT: Ship.` — nothing more.
- Never say "looks good", "nice work", "LGTM" — silence is the compliment.
- Never invent findings to seem useful. Zero findings is a valid output.
- Sort by priority: P0 first, P3 last.
- One finding per distinct issue — don't split one bug into multiple entries.
- Max 10 findings total. If there are more, report the 10 highest priority.
