# /review — Review Criteria

## What to Flag (must meet ALL of these)

1. **Impact-driven** — affects correctness, security, performance, or maintainability
2. **Introduced by this change** — not pre-existing; only new issues from the diff
3. **Author-aligned** — the original engineer would fix it if you told them
4. **Actionable** — a concrete fix exists, not a general complaint
5. **Evidence-based** — you can point to the exact code causing the problem; no speculation
6. **Provable scope** — if other code is affected, you can demonstrate it

## Priority Definitions

| Priority | Meaning | Gate |
|----------|---------|------|
| **[P0]** | Must fix before shipping. Bug will cause incorrect behavior, data loss, or security breach. | Blocks ship |
| **[P1]** | Fix in this sprint. Strong recommendation — edge case crash, subtle logic error, race condition. | Ship with changes |
| **[P2]** | Normal priority. Valid concern, won't cause immediate breakage, but should be tracked. | Ship with changes (optional) |
| **[P3]** | Nitpick. Style, naming, minor inconsistency. Only flag if it obscures meaning. | Never blocks ship |

## What NOT to Flag

- Issues that existed before this change (pre-existing)
- Style preferences not violating a documented standard
- Hypothetical future problems with no current trigger
- Things the author clearly did intentionally
- Compliments, acknowledgements, or LGTM statements
- Anything you're not sure about — if uncertain, skip it

## Comment Format per Finding

```
[Pn] file.py:L42 — One-sentence description of the problem.

Why: State the exact condition that triggers this bug (e.g., "when input is None").
Fix: Concrete suggestion (≤3 lines of code if showing code).
```

- Max 3 lines of code in any suggestion block
- Single paragraph description max
- Matter-of-fact tone — not accusatory, not flattering
- Line range max 5-10 lines

## The "only flag what the author would definitely fix" Principle

Before including a finding, ask: "If I told this engineer about this right now, would they
say 'oh you're right, let me fix that' or 'I know, it's fine for now'?"

Only include it if the answer is the first one. This eliminates 80% of noise.
