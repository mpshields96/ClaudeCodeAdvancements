# Kalshi Main Chat — Productive Task Catalog

Tasks that CCA desktop can assign to Kalshi main chat via `cca_comm.py task km "<task>"`.
These define what "productive work" means for Kalshi main beyond passive monitoring.

## Prerequisites

For Kalshi main to receive and execute these tasks:
1. `queue_injector.py` must be wired into Kalshi main's UserPromptSubmit hooks
2. `polybot-auto` must check the cross_chat_queue and act on task assignments
3. Kalshi main must have `CCA_CHAT_ID=km` set (already done in launch_kalshi.sh)

**Current status (S118):** Step 1 done (routing exists in cca_comm.py). Steps 2-3 need polybot-side changes. Until then, Kalshi main runs independently and these tasks are queued but not yet consumed.

---

## Task Categories

### Pre-Check: Bridge Gate

Before assigning or acting on bridge work, use the cheap JSON gate first:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_board.py kalshi-check
```

Interpretation:
- `should_read_outbox=true` → read `~/.claude/cross-chat/CCA_TO_POLYBOT.md` now
- `latest_delivery_req_ids` / `latest_request_req_ids` → which request the latest bridge activity is about
- `req66_answered=true` → REQ-66 already has a CCA answer on file; use that delivery instead of re-asking
- after reading: `python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_board.py kalshi-mark-seen`

### Category 1: Bridge Processing

Process research findings that CCA sent via CCA_TO_POLYBOT.md.

```bash
python3 cca_comm.py task km "Process new bridge items in CCA_TO_POLYBOT.md. Check for new research findings, paper digests, or strategy recommendations. Implement any that are actionable."
```

**When to assign:** After CCA desktop updates CCA_TO_POLYBOT.md with new research.
**Expected output:** Implementation of actionable findings, or response explaining why items were skipped.

### Category 2: Self-Learning Analysis

Run trade pattern analysis on recent bot performance.

```bash
python3 cca_comm.py task km "Run self-learning analysis: python3 self-learning/trade_reflector.py --recent 50. Report findings. If any patterns detected, propose parameter adjustments."
```

**When to assign:** Every 3-4 sessions, or after a losing streak.
**Expected output:** Pattern analysis report with actionable proposals.

### Category 3: Sniper Bucket Analysis

Analyze sniper bet performance by market type and time window.

```bash
python3 cca_comm.py task km "Analyze sniper bucket performance by market type over the last 7 days. Which buckets are profitable? Which should be paused? Report win rates, ROI, and sample sizes per bucket."
```

**When to assign:** Weekly, or when overall performance dips.
**Expected output:** Per-bucket performance summary with CONTINUE/PAUSE/INVESTIGATE verdicts.

### Category 4: Calibration Check

Verify model calibration hasn't drifted.

```bash
python3 cca_comm.py task km "Run calibration check on current model parameters. Compare predicted probabilities vs actual outcomes for the last 100 resolved bets. Report any systematic bias (overconfident/underconfident)."
```

**When to assign:** Bi-weekly, or after strategy changes.
**Expected output:** Calibration curve analysis with bias direction and magnitude.

### Category 5: Research Implementation

Implement a specific CCA research finding.

```bash
python3 cca_comm.py task km "Implement CCA research finding: [specific description from paper_digest or nuclear scan]. Start with a backtest on historical data before modifying live parameters."
```

**When to assign:** When CCA identifies a high-confidence research finding.
**Expected output:** Backtest results and (if positive) parameter update PR.

### Category 6: Page-Hinkley Drift Detection

Apply change-point detection to sniper outcomes.

```bash
python3 cca_comm.py task km "Run Page-Hinkley drift detection on sniper bet outcomes for the last 30 days. Report any detected regime changes (shift in win rate, shift in ROI, shift in market conditions)."
```

**When to assign:** Monthly, or when sniper performance changes unexpectedly.
**Expected output:** Drift detection report with change points and recommended actions.

### Category 7: Event-Day Readiness

Audit whether a specific economics event is actually deployable before the chat improvises.

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/kalshi_cpi_readiness.py
```

**When to assign:** Before April CPI, GDP, or any economics-event micro-live discussion.
**Expected output:** `blocked` or `watch` verdict with structural checks, live dependencies, and the next 2-3 exact actions.

---

## Assignment Protocol

1. CCA desktop checks if Kalshi main has pending tasks: `python3 cca_comm.py inbox km`
2. Run the bridge gate first:
   `python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_board.py kalshi-check`
3. If `should_read_outbox=true`, process the latest CCA delivery before assigning anything else
4. If no pending tasks and Kalshi main is running: assign from this catalog
5. Priority order: Bridge > Self-Learning > Sniper Analysis > Calibration > Research > Drift
6. Never assign more than 2 tasks at once (Kalshi main has its own monitoring duties)
7. Track assigned tasks in SESSION_STATE.md under "Kalshi task assignments"

## Measuring Success

A task is successful if Kalshi main:
- Reads and acknowledges the task
- Executes the analysis/implementation
- Reports results back via `cca_comm.py done "summary"`
- Results are actionable (not just "everything looks fine")

Track task completion rate to measure 3-chat coordination health.
