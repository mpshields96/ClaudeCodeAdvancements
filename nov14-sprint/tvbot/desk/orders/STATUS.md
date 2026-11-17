# orders/ status

## 2026-11-15 18:09Z: Worker A, contract v2 and the Codex 16:31Z QA batch

Everything is still paper and offline. Every fill is a MOCK FILL with `"simulated": true`. The limits are TEST VALUES, and only Matthew sets the real ones.

**Result.**
- `test_orders*`: 93 tests pass (0.29 s). The breakdown is intake 27, broker 24 and manager 42.
- Full desk suite: 177 tests pass (about 30 s), and that includes the coordinator's `test_integration`.
- Codex probe `probe_stop_contract.py`:
  - foreign working order: `reported_flat: false`;
  - rejected close: `pending`, with the protective still `working` and the position kept.
- Python 3.9.6, stdlib only, `-I`.

| File | Lines | v2 change |
|---|---|---|
| `orders/calendar.py` | 246 | Dec 24 early close and Dec 25 closed. Adds a `covered` range with refusal, and `session_bounds(day)`. |
| `orders/intake.py` | 171 | Adds `NOT_CLOSED_AT_RECEIPT`, `EXCHANGE_TS_BEFORE_CLOSE` and `CALENDAR_NOT_COVERED`. |
| `orders/fake_broker.py` | 448 | `snapshot()`/`restore()`, adverse bps costs, `event_ts`/`report_ts`, and reduce-only orders. |
| `orders/manager.py` | 1267 | v2 limits, MAX_LOSS and NO_STOP, `resume()`, `clear_stop(confirm=True)`, the false-flat guards, and protection kept until the close fills. |

**Contract v2 to tests**

| Item | Where | Test |
|---|---|---|
| Limits `{per_trade_notional 2000, max_loss_per_trade 10, daily_loss 30, gross_exposure 2000}` TEST VALUES | `manager.py` gates | `GateTests` (all) |
| MAX_LOSS: `qty x abs(entry - invalidation) > max_loss_per_trade` (price only; est_cost counts in the daily worst case) | `MAX_LOSS` | `test_max_loss_per_trade` |
| RISK_PER_TRADE renamed | `NOTIONAL` | `GateTests` |
| Entry without an invalidation | `NO_STOP`; an invalidation on the wrong side is `BAD_STOP` | `test_entry_needs_an_invalidation_on_the_losing_side` |
| Gross and worst case count working orders | `RISK_GROSS`, `RISK_DAILY_LOSS_WORST_CASE` | `test_worst_case_counts_working_entries`, `test_worst_case_daily_loss_from_stops` |
| Intent fields and `kind` | intents.jsonl and the audit | `test_contract_intent_fields_and_kind_audit` |
| `resume()` | `manager.py:1038`. It refuses with `STOPPED` while a Stop stands. | `test_orders_manager.py` lines 418, 458, 468 |
| `clear_stop(confirm=True)` is the only clear, and it is audited | `manager.py:1104`. It returns `CONFIRM_REQUIRED` or `NOT_FLAT_CONFIRMED`, and logs the audit actions `clear_stop` / `clear_stop_refused`. | `test_clear_stop_needs_explicit_confirm_and_is_audited` |
| A restart, an expiry or a schedule re-arm never clears a Stop | controls.json `stopped` | `test_stop_survives_schedule_rearm_restart_and_expiry` |
| `calendar.session_bounds(day) -> (open_utc, close_utc)` or None | `calendar.py` | `test_session_bounds` |

**Codex QA 16:31Z to tests**

| # | Item | Test |
|---|---|---|
| 1 | No false flat with a same-symbol foreign or unknown working order. Status reads "currently 0, working/unknown, stop unresolved". The foreign order is listed as external and never canceled. | `test_false_flat_with_foreign_order` |
| 1 | No false flat with a truncated listing | `test_false_flat_with_truncated_listing` |
| 2 | Protection kept until the close fills; reduce-only orders never reverse | `test_rejected_close_keeps_protection`, `test_unfilled_close_keeps_protection`, `test_partial_close_keeps_protection_and_never_reverses`, `test_gap_bar_with_close_and_protective_does_not_reverse`, broker `test_reduce_only_never_reverses` |
| 3 | `_audit` doesn't raise "multiple values for kind" | `test_contract_intent_fields_and_kind_audit` |
| 4 | Refuse ts_close later than the receipt or the exchange time | `test_bar_received_before_its_close_is_refused`, `test_exchange_ts_before_close_is_refused_even_when_fresh` |
| 5a | Broker `snapshot()`/`restore()` | `test_snapshot_restore_round_trip` |
| 5b | Adverse `half_spread_bps` and `slip_bps` on every fill, labeled `price_basis "SIMULATED: ..."` | `test_spread_and_slip_move_fills_against_the_order` |
| 5c | A market order never fills at a price stamped before it was submitted; `event_ts` and `report_ts` are recorded | `test_market_order_never_fills_at_a_price_printed_before_submit`, `test_order_placed_before_the_bar_opens_fills_at_open` |
| 6 | Dec 24 2026 closes at 12:00 CT and Dec 25 is closed. Uncovered dates are refused visibly. | `test_christmas_eve_early_close_and_christmas_closed`, `test_uncovered_dates_are_refused_visibly` |
| 7 | An explicit `expires_utc` (session end + 5 min) is kept and ends flat | `test_explicit_expiry_is_kept_and_ends_flat`, `test_expiry_after_session_end_flattens_at_next_open` |

**Note for the coordinator: intake names.** `check_bar` now refuses a bar received before its close, as `NOT_CLOSED_AT_RECEIPT`. That is the same name session.py's own guard uses, so `test_integration`'s "future" case still sees `DATA_REJECTED_NOT_CLOSED_AT_RECEIPT`. session.py's guard is now a second line of defense; nothing in it was changed. Both new codes are also in the manager's `UNTRUSTED_BAR_CODES`, so a forming bar never moves the mark.

**Gaps (v2)**

- **Calendar coverage.**
  - The default Chicago calendar claims only 2026-10-01 to 2026-12-31.
  - Outside that range, `windows()`, `is_trading_day()` and `session_bounds()` raise `CalendarNotCovered`, `is_open()` returns False, `next_open()` returns None, and intake answers `CALENDAR_NOT_COVERED`.
  - The Dec 24/25 dates come from the Codex brief and NYSE's published 2026 schedule. I didn't re-fetch them here.
  - A full NYSE year is not claimed.
  - `fixture_profile()` and custom calendars stay unlimited unless they are given `covered=`.
- **Expiry at session end + 5 min with hourly bars.**
  - The fixture's last bar is delivered after the close, and no bar arrives between the close and the next open. So the expiry is first seen on the next day's first bar.
  - The position is held overnight under its protective. The close goes out on day 2's first bar and is flat on the bar after that.
  - `test_expiry_after_session_end_flattens_at_next_open` pins this behavior. A wall-clock tick, or an expiry before the last bar, would avoid the overnight hold. That is the coordinator's call in session.py.
- **Limits.** These are v2 TEST VALUES from the contract. `tvbot/config/smaller_size.json` has only `order_notional` 2000, so `daily_loss` 30, `max_loss_per_trade` 10 and `gross_exposure` 2000 come from the contract text, not from Matthew.
- **Carried from v1, unchanged.**
  - The bar grid is anchored at the session open.
  - There are no overnight sessions.
  - A clean reconcile clears earlier event alarms.
  - There is no UI wiring here; that is Worker B's.

## 2026-11-15 17:41Z: Worker A (order engine and controls), steps 1-5 done

Everything here is paper and offline. Every fill is a MOCK FILL with `"simulated": true`. The limits are TEST VALUES.

**Files**

| File | Lines | What it does |
|---|---|---|
| `orders/calendar.py` | 187 | Session calendar (America/Chicago, Nov 2026 holidays, early close) and `fixture_profile()` (UTC 14:30-21:30, weekdays) |
| `orders/intake.py` | 153 | `check_bar`: BAD_BAR, OUT_OF_ORDER, GAP_IN_SESSION, OUT_OF_SESSION, ZERO_VOLUME, STALE/FUTURE_EXCHANGE_TS. Also `bar_can_fill` and `missing_slots`. |
| `orders/fake_broker.py` | 339 | In-process, seeded broker that fills on the next bar. Faults: lost_ack, partial, cancel_fill_race, late_fill_after_cancel, duplicate_event, out_of_order, margin_reject, outage, truncated_listing. |
| `orders/manager.py` | 1153 | `OrderManager`, covered in the next section. |
| `orders/BTC_REUSE.md` | | What was ported or adapted from the BTC r8b order code, with file:line |
| `tests/test_orders_intake.py` | 22 tests | |
| `tests/test_orders_broker.py` | 19 tests | |
| `tests/test_orders_manager.py` | 28 tests | Gates, broker faults, reconcile, pause, Stop & Close, persistence, a 10-day replay |

**OrderManager covers:**
- intents written before they are sent, with idempotent decision ids;
- risk gates: per-trade, gross and daily loss, including a worst-case stop check;
- exit gates;
- reconcile and adopt on restart;
- pause, which keeps the protective exits;
- Stop & Close, which ends flat and is confirmed against the broker;
- session expiry that finishes flat;
- a lock file, torn-tail repair, and controls that fail closed.

**Test command**

```
/usr/bin/python3 -I -m unittest discover -s nov14-sprint/tvbot/desk/tests -p 'test_orders*'
```

**Result:** 69 tests, all pass (0.21 s, Python 3.9.6, stdlib only).

**How to drive it per bar:** call `broker.step(bar)`, then `mgr.on_bar(bar)`.
- An order submitted after `on_bar(N)` fills at `step(N+1)`.
- Entries need `arm()`.
- After a Stop & Close, the operator sequence is `clear_stop()`, then `resume()`, then `arm()`. Clearing the stop does not unpause; the tests pin this.

**Gaps (known, not fixed)**

- **Limits.**
  - The TEST VALUES `daily_loss` 200 and `gross_exposure` 3000 are derived. `tvbot/config/smaller_size.json` has only `order_notional` 2000. Matthew sets the real numbers.
  - The worst-case daily-loss check sees only working protective stops, and entries that carry both `limit` and `stop`.
  - A plain market or limit entry with no stop is bounded only by the per-trade and gross notional limits and by the realized daily-loss stop.
  - On an entry, `stop` is both the broker stop trigger and the risk stop.
- **Calendar.**
  - The holiday table covers only November 2026.
  - The bar grid is anchored at session open.
  - Overnight sessions are refused.
  - The t03 session-break fixture can't be expressed in a single-window calendar.
- **Session timing.**
  - `flatten_lead_s` 3900 is tuned for hourly bars: the default expiry is the session end minus 65 minutes.
  - The last fixture bar is delivered after the close, so MARKET_CLOSED blocks entries on it.
- **Bar checks.**
  - Without `exchange_ts`, `ts_close` is the fallback. With no received time, the check fails closed as STALE.
  - The timing fixtures need a 24x7 calendar.
  - The a02 alert payload is refused as BAD_BAR.
  - The b02 far-future bar is refused as GAP or OUT_OF_ORDER, not FUTURE.
- **Reconcile.** A clean reconcile clears earlier event alarms. That makes an alarm a current-state alarm, not a latched one.
- **Not built.** No UI wiring. Worker B owns the UI, and the integration point is `state()`, `ledger_rows()` and `blocking_alarms()`. There is no strategy/signal adapter.
