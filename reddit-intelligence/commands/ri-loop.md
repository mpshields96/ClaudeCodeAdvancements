# /reddit-intel:ri-loop — Schedule Weekly Reddit Intelligence Runs

Set up an automated weekly Reddit scan using Anthropic's `/loop` command
(shipped March 2026). The scan runs on schedule and delivers a structured
findings report each week.

**Security contract:** read-only, no login, no form submission, no data leaves
the machine. See SECURITY.md for full constraints.

---

## What this does

Wires `/reddit-intel:ri-scan` to Anthropic's native `/loop` scheduler so
the scan runs automatically — no cron job, no daemon, no external service.

`/loop` schedules Claude Code tasks to recur up to 3 days out. For weekly
cadence the user re-invokes after each run, or triggers manually anytime.

---

## Usage

```
/reddit-intel:ri-loop              → schedule default subreddits weekly
/reddit-intel:ri-loop claude       → schedule Claude-track only
/reddit-intel:ri-loop betting      → schedule betting-track only
/reddit-intel:ri-loop all          → schedule all subreddits weekly
```

---

## STEP 1 — Confirm the scan profile

Parse the argument using the same rules as ri-scan:

- No argument → default (ClaudeCode, ClaudeAI, algobetting)
- `claude` → ClaudeCode, ClaudeAI, Claude, vibecoding
- `betting` → algobetting, PredictionMarkets
- `all` → all six subreddits

---

## STEP 2 — Run an immediate scan

Before scheduling, run one scan now to confirm the setup works.

Invoke ri-scan inline with the chosen profile:

```
/reddit-intel:ri-scan [profile]
```

If the scan completes without errors, proceed to scheduling.

If the scan fails (Chrome not open, Reddit blocked), resolve the issue
before scheduling — a failing immediate run will also fail when looped.

---

## STEP 3 — Schedule the recurring run with /loop

Tell the user to invoke `/loop` with the following task description:

```
Run /reddit-intel:ri-scan [profile] and save the findings report to
/Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/
with filename YYYY-MM-DD-scan.md (today's date). Do not prompt for confirmation.
```

**Important notes for the user:**
- `/loop` schedules up to 3 days out. For weekly runs, re-invoke
  `/reddit-intel:ri-loop` after each run to schedule the next one.
- If the loop fails silently (Chrome not running), the user will not be
  notified — check `findings/` to confirm output was written.
- The scan writes to `findings/` only when the loop invokes it with
  explicit save instructions (ri-scan itself never auto-saves).

---

## STEP 4 — Confirm scheduling output

After the user invokes `/loop`, confirm:

1. The task is scheduled (Claude Code will confirm in the UI)
2. The profile matches what was requested
3. The save path is `reddit-intelligence/findings/YYYY-MM-DD-scan.md`

Report back to the user:

```
Scheduled: /reddit-intel:ri-scan [profile]
Profile: [subreddits list]
Save path: reddit-intelligence/findings/YYYY-MM-DD-scan.md
Next run: [when /loop says it will run]

To check findings: ls reddit-intelligence/findings/
To run immediately: /reddit-intel:ri-scan [profile]
```

---

## Manual run (no loop)

To run without scheduling:

```
/reddit-intel:ri-scan                 → scan, display results, do not save
/reddit-intel:ri-scan all             → all subreddits, display only
```

To scan and save manually:

```
/reddit-intel:ri-scan
→ then ask: "Save this to findings/YYYY-MM-DD-scan.md"
```

ri-scan will only write to `findings/` when explicitly asked.

---

## Findings directory

All saved scans go here:

```
reddit-intelligence/findings/
├── 2026-03-08-scan.md
├── 2026-03-15-scan.md
└── ...
```

Each file is a dated snapshot. Files are never overwritten — each scan
gets its own dated filename.

---

## Troubleshooting

**`/loop` not available:**
The `/loop` command requires Claude Code ≥ the March 2026 release. Update
Claude Code (`claude update`) and confirm the command is listed in `/help`.

**Loop ran but findings/ is empty:**
ri-scan only writes files when explicitly asked. The loop task description
must include explicit save instructions (see Step 3 template above).

**Loop failed silently:**
Chrome must be open when the loop fires. If it's not running, the
`mcp__Control_Chrome__open_url` call will fail. No error will surface unless
the user checks manually. Keep Chrome running or schedule during known
active hours.
