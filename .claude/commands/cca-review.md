# /cca-review — Review URL for ClaudeCodeAdvancements

Read a Reddit post, GitHub repo, or any URL and deliver a full assessment:
Is this worth incorporating into our project?

The user's message contains the URL (or multiple URLs). Process each one.

---

## Step 1 — Read the URL thoroughly

### Reddit URLs (contains `reddit.com` or starts with `r/`)

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "$URL"
```

Read EVERY comment. The best insights are often buried 3-4 levels deep in comment threads.

### GitHub URLs

Use WebFetch to read:
- The repo README in full
- The repo structure (key files/directories)
- If it's an issue/PR: title, body, and ALL comments

### Any other URL

Use WebFetch to get the full page content.

---

## Step 2 — Deep analysis

After reading, analyze the content against these criteria:

### A. Frontier mapping

Does this relate to any of the five frontiers?

| # | Frontier | What counts |
|---|----------|-------------|
| 1 | Memory | Cross-session persistence, context recall, knowledge management |
| 2 | Spec-Driven Dev | Requirements, architecture, task breakdown, structured development |
| 3 | Context Health | Token usage, context rot, compaction, handoff, session management |
| 4 | Agent Guard | Multi-agent conflicts, file locking, credential safety, permissions |
| 5 | Usage Dashboard | Token counting, cost visibility, billing transparency |

If it doesn't map to any frontier, flag it as "NEW FRONTIER CANDIDATE" or "OFF-SCOPE" with reasoning.

### B. Rat poison check

Skip/downgrade if the content is:
- Pure hype without implementation details
- Jailbreak/bypass/prompt injection content
- GPT-vs-Claude comparisons without actionable patterns
- Install tutorials for unrelated tools
- Speculation about what AI "will" do without evidence

### C. Implementation feasibility

- Can we build this as a hook, slash command, MCP server, or CLI tool?
- Does it require external dependencies? (bad — we're stdlib-first)
- How much work? (hours vs days vs weeks)
- Does it duplicate something we already have?

### D. Community signal strength

For Reddit posts:
- Score and upvote ratio
- Comment count and quality of discussion
- Are multiple people reporting the same pain point?
- Are there working implementations shared in comments?

---

## Step 3 — Deliver the verdict

Output in this exact format:

```
REVIEW: [title or repo name]
Source: [URL]
Score: [N] pts | [N] comments (Reddit only)

FRONTIER: [1-5 name] or NEW or OFF-SCOPE
RAT POISON: [CLEAN / CONTAMINATED — reason]

WHAT IT IS:
[2-3 sentences — what does this tool/post/idea actually do?]

WHAT WE CAN STEAL:
[Specific patterns, approaches, or code worth taking. Be concrete.]
[If nothing: "Nothing actionable."]

IMPLEMENTATION:
- Delivery: [hook / command / MCP / CLI / Streamlit]
- Effort: [hours / days]
- Dependencies: [none / list them]
- Duplicates: [none / what it overlaps with]

VERDICT: [BUILD / ADAPT / REFERENCE / REFERENCE-PERSONAL / SKIP]
- BUILD = we should build this or something like it
- ADAPT = take specific patterns/ideas, not the whole thing
- REFERENCE = interesting but not actionable now — save for later
- REFERENCE-PERSONAL = not CCA-frontier but useful to Matthew personally (trading/Kalshi, academic writing, psychiatry, other projects)
- SKIP = not worth our time

WHY: [1-2 sentences justifying the verdict]
```

---

## Step 4 — If verdict is BUILD or ADAPT

Automatically run:
```
/gsd:add-todo [one-line description of what to build, referencing the URL]
```

This captures the idea so it doesn't get lost.

---

## Rules

- Read the ENTIRE post including ALL comments — don't skim
- Be brutally honest in verdicts. Most things are REFERENCE or SKIP.
- BUILD verdict requires: clear user pain point + feasible implementation + maps to a frontier
- If multiple URLs provided, review each one separately
- Do not ask the user questions — deliver the full verdict autonomously
- If the Python reader fails on a Reddit URL, fall back to WebFetch
