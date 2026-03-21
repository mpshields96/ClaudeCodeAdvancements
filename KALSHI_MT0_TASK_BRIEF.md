# MT-0 Phase 2: Deploy Self-Learning to Kalshi Bot
# Task Brief for Kalshi Main Chat (Session 120)
# Written by CCA Desktop (S104) — this is your mission.

---

## CONTEXT (read this first)

CCA has built a production-quality self-learning system (1552 tests, 38 suites) in:
`/Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/`

It tracks events (journal.py), detects patterns (reflect.py), generates improvement
proposals (improver.py), and tunes strategy parameters (strategy.json). It already
has 6 trading-specific event types and 5 trading pattern detectors.

**The problem:** This system lives in CCA. The Kalshi bot places bets and records
outcomes to its own DB, but none of that data feeds back into the self-learning
system. The bot isn't learning from its own results.

**Your mission:** Wire the bot's bet outcomes into the self-learning feedback loop.

---

## WHAT TO BUILD (ordered by priority)

### Task 1: Trading Event Logger (highest priority)
**Where:** `polymarket-bot/src/self_learning/trading_journal.py` (new file)
**What:** Lightweight wrapper that logs trading events to a JSONL file using
the same schema CCA's journal.py uses.

```python
# Schema for each event (append to trading_journal.jsonl):
{
    "timestamp": "ISO 8601",
    "event_type": "bet_outcome",  # or bet_placed, edge_discovered, etc.
    "session_id": 120,
    "domain": "trading",
    "metrics": {
        "result": "win",          # win/loss/void
        "market_id": "KXBTC15M-...",
        "market_type": "crypto_15m",
        "strategy_name": "expiry_sniper",
        "pnl_cents": 35,
        "price_cents": 95,
        "cost_usd": 0.65,
        "side": "NO",
        "hour_utc": 14
    }
}
```

**Wire into:** `src/execution/live.py` — after each bet settles (win/loss),
call `trading_journal.log_event()`. Also wire into paper executor for paper bets.

**Safety:** Append-only JSONL. No reads during bet execution. Zero latency impact.
If logging fails, log the error and continue — never block a bet because of journaling.

### Task 2: Research Outcomes Tracker
**Where:** `polymarket-bot/src/self_learning/research_tracker.py` (new file)
**What:** When the bot implements something based on CCA research (e.g., a new
guard, a parameter change, a new strategy), log which research item influenced it.

```python
{
    "timestamp": "ISO 8601",
    "research_item_id": "msg_abc123",  # from cross_chat_queue.jsonl
    "action_taken": "implemented_hour_block",
    "bets_before": 797,
    "pnl_before_cents": 6321
}
```

Later, after N bets, compute the delta:
```python
{
    "research_item_id": "msg_abc123",
    "bets_after": 850,
    "pnl_after_cents": 6800,
    "delta_pnl_cents": 479,
    "delta_wr": "+0.02",
    "verdict": "profitable"
}
```

This closes the feedback loop: CCA can read these outcomes and learn which
research directions actually made money.

### Task 3: Return Channel to CCA
**Where:** Write outcomes back to CCA's cross_chat_queue.jsonl
**How:** Use the existing cross_chat_queue.py protocol:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_queue.py \
    send --from km --to cca --priority medium \
    --category research_finding \
    --subject "Research outcome: hour block revert" \
    --body "Research item msg_abc123 led to +479 cents over 53 bets. Verdict: profitable."
```

**When:** At session wrap, summarize outcomes of any CCA-recommended changes.

### Task 4: Pattern Summary at Wrap
**Where:** Add to the session wrap routine
**What:** At end of session, analyze trading_journal.jsonl for patterns:
- Win rate by hour (detect new weak hours)
- Win rate by strategy (detect degrading strategies)
- Win rate by market type (detect shifting edges)
- Compare to previous session's metrics

Report findings back to CCA via cross_chat_queue.

---

## WHAT NOT TO DO

- Do NOT copy CCA's full self-learning module into polymarket-bot
- Do NOT add LLM-powered reflection (too expensive for a bot that runs 24/7)
- Do NOT modify the betting logic itself — only ADD logging alongside it
- Do NOT read CCA files at runtime — use the cross_chat_queue for communication
- Do NOT block bet execution if logging fails — fail open, log the error

---

## TDD ORDER

1. Write test_trading_journal.py FIRST — test event logging, schema validation
2. Implement trading_journal.py to pass tests
3. Write test for the wire-up (mock live.py settlement callback)
4. Wire into live.py
5. Write test_research_tracker.py
6. Implement research_tracker.py
7. Manual integration test: place a paper bet, verify it appears in journal

---

## FILES YOU'LL TOUCH

| File | Action |
|------|--------|
| `src/self_learning/` | NEW directory |
| `src/self_learning/__init__.py` | NEW |
| `src/self_learning/trading_journal.py` | NEW — event logging |
| `src/self_learning/research_tracker.py` | NEW — research outcome tracking |
| `src/execution/live.py` | MODIFY — add journal.log_event() after settlement |
| `src/execution/paper_executor.py` | MODIFY — add journal.log_event() after paper settlement |
| `tests/test_trading_journal.py` | NEW — tests |
| `tests/test_research_tracker.py` | NEW — tests |

---

## COORDINATION WITH CCA DESKTOP

CCA Desktop (this chat) will monitor your progress via cross_chat_queue.
Report back when:
- Task 1 tests pass (I'll review the schema)
- Task 2 tests pass
- First real event logged to trading_journal.jsonl
- Any blockers or questions

Send messages via:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_queue.py \
    send --from km --to cca --priority medium \
    --category status_update --subject "Task 1 complete" \
    --body "trading_journal.py built, 15 tests passing, wired into live.py"
```

---

## SUCCESS CRITERIA

1. Every settled bet (live AND paper) produces a JSONL event in trading_journal.jsonl
2. Research outcomes can be tracked from recommendation → implementation → P&L delta
3. CCA can read the outcomes via cross_chat_queue and update its principle scores
4. Zero impact on bet execution latency or reliability
5. All new code has tests. All existing tests still pass (1698).
