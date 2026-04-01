# /cca-scout — Find High-Signal Posts Across Claude Subreddits

Spawn the cca-scout agent to scan subreddits autonomously.

---

## Run

Launch the scout agent:

```
Agent(subagent_type="cca-scout", prompt="Scan r/ClaudeCode (top 50), r/ClaudeAI (top 50), and r/vibecoding (top 25) for high-signal posts. Dedup against FINDINGS_LOG.md. Return a ranked shortlist.")
```

The agent handles all scanning, filtering, and dedup autonomously.

## After scout returns

Review the shortlist. For each post worth a full review, run:
```
/cca-review <url>
```

Or to review all at once, spawn cca-reviewer agents in parallel for each URL.
