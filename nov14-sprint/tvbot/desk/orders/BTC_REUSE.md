# What the order engine took from the BTC order code

**Written 2026-11-15 by the orders worker. Paper desk only.**

**Source.** The private BTC order code, revision r8b, in a local agent workspace that is not published. I only read it; I didn't change any BTC file.

**Status of that source.** Its own `NOT_REVIEWED.txt` says r8b is "FROZEN ... NOT REVIEWED. NOT FOR USE" and "G1 is NOT MET". That is why nothing below is copied code. These are design patterns, reimplemented in stdlib Python 3.9 for an in-process fake broker. Using one here says nothing about whether the BTC code is ready.

## Ported (same idea, new code)

| BTC source | Pattern | Where it lives in `desk/orders/` |
|---|---|---|
| `ledger-store.js:41-79` | Atomic write: temp file, fsync, rename, then fsync the folder. | `manager.py` `atomic_write_json`, `_fsync_dir` (controls.json) |
| `ledger-store.js:93-101` | Refuse a ledger path that is a symlink. | `manager.py`: refuses a linked state dir or file |
| `ledger-store.js:105-134` | Each record carries a seq and a sha256. | `manager.py` `JsonlLog` gives each row a seq and a 16-char record hash. It doesn't port the separate `.hw` high-water file (see Not ported). |
| `ledger-store.js` owner lock, `runner-lock.js` | One writer per ledger. | `manager.py` `_take_lock`: `fcntl.flock` on `.orders.lock`. A second manager raises RuntimeError. |
| `order-core.js:700-709` | Reserve in the ledger before the order is built or sent. | `submit_intent` writes the intent to intents.jsonl (fsync) before `broker.submit` |
| `order-core.js:269` | DUPLICATE_CLIENT_ORDER_ID | The client id is a sha256 of decision_id. A repeated decision returns the same intent and sends nothing. |
| `order-core.js:295-344`, `:306` | Book only confirmed fills. A repeated fill id is DUPLICATE_CONFIRMATION. | `_book_fill` / `_on_event`: exec_id dedupe, counted in poll()["duplicates"] |
| `order-core.js:310` | Book the ack before the fill (strict ledger) | Adapted, not strict: a fill is booked only for a client id the desk wrote. An unknown client id raises a FOREIGN_FILL alarm. |
| `order-core.js:35-36`, `:604-606` | snapshotMaxAgeMs / maxFutureSkewMs of 5000 ms: refuse stale or future-stamped data | `intake.py` `check_bar`: STALE_EXCHANGE_TS, FUTURE_EXCHANGE_TS. The thresholds are sized for hourly bars. |
| `order-core.js:29` | lossCeilingUnits: a worst-case loss ceiling | `_check_entry_risk`: RISK_DAILY_LOSS_WORST_CASE (live stop risk plus the new entry's stop risk) |
| `reconcile.js:34-35` and its alarm list | Match exchange orders to the ledger by client id, and alarm on anything unexplained. | `reconcile()`: FOREIGN_ORDER, ORDER_MISSING, FILL_TOTAL_MISMATCH, OVERFILL, POSITION_* , INCOMPLETE_LISTING |
| `sender.js:236` ("ONE POST. Never repeated") | Never re-send blind after an uncertain submit | `_resolve_uncertain`: query first. A found order is adopted. An absent one is re-sent once under the same client id, so the broker's duplicate check still applies. |
| `sender.js:155,173,225,232`; `arming.js:296-301` | Check the kill switch again at each step | Each submit re-reads `stopped`/`paused`/armed/expiry (`entry_block_reason`) |
| `btc15m-bot-claude/tools/risk_gate.py` (HALT, DAY_STOP) | A halt survives restarts and only a person lifts it. A day stop clears the next day. Limits only tighten. | `stopped` persists in controls.json, and only `clear_stop(confirm=True)` lifts it, after a confirmed flat (audit-logged; a restart, expiry or schedule re-arm never clears it). `day_stop` is keyed to the trading day. Limits are read-only TEST VALUES. |

## Adapted (changed on purpose)

- **Disarm vs Stop & Close.** BTC `disarm.js` can't cancel, because its orders are immediate-or-cancel. The desk has resting orders, so it splits the job:
  - `pause()` cancels entry remainders and keeps the protective exits.
  - `stop_and_close()` cancels everything, sends a close, and only reports `flat_confirmed` once the broker shows zero.
- **Unreadable state fails closed.** BTC refuses to open. The desk opens stopped and paused, raising the alarm CONTROLS_UNREADABLE, so the UI can still show what is wrong.

## Not ported

- **The `.hw` high-water file** (`ledger-store.js:105-108`), which catches a ledger copied back from an older version. The desk has no budget ledger, so a torn tail is repaired (moved to `intents.jsonl.torn`) instead.
- **Kalshi specifics**: tickers, cents, outcome sides, fee math and the `--down`/`--sell` modes. They aren't relevant to a paper equity bar desk.
