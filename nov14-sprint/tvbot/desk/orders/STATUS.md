# orders/ status

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
