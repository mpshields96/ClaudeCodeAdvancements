# Paper desk build contract (v2, 17:16Z 2026-11-15)

Owner: Claude coordinator (integration, launcher, publisher). Build prompt: Codex frozen `TradingView_Build_Prompt.md` (sha256 `60f30994…4eac`). This file fixes the interfaces so three workers can build in parallel. Change it only through the coordinator.

**v2 changes (17:16Z), from Codex acceptance review 17:08Z (SUPERVISOR_1631Z.md).** Items marked **[v2]** below.
1. Best reasoned pass is chosen by a decision-time rule, never by the later move (v1 rule used hindsight; withdrawn).
2. Clicking a marker hides every later bar, exit marker and outcome until "Reveal outcome".
3. The session is playable: review → arm → advance/watch → pause or Stop & Close → close review. Not a finished replay with buttons on top.
4. A separately enabled, visible offline schedule on a simulated clock, with calendar expiry. A schedule never clears a Stop.
5. A plain-dollar max loss per trade, separate from the notional cap.
6. Armed simulation is shown separately from external broker status (there is no external broker).
7. The native TradingView chart sits beside the desk for viewing only (official embed widget or side-by-side window), labeled as a different source from the desk's replay.

## Hard limits (every worker)
- Paper and offline only. No accounts, sign-ins, credentials, keys, purchases, paid data, real orders or network calls from desk code. The fake broker is in-process.
- TradingView is the operator's chart only. No TradingView price, indicator, alert or webhook enters any decision, order or ledger, and desk code never reads from or injects into the TradingView chart. Do not edit `tvbot/pine/` or `tvbot/bot/` (existing EMAX bot, 101 tests).
- Position size, sizing formula and dollar limits are Matthew-only. Code ships test values and labels them TEST VALUES. No self-tuning of them. Any config change shows old value, new value, rationale and approval.
- Every simulated number and every mock fill carries `"simulated": true` and the UI shows SIMULATED / MOCK FILL.
- Python `/usr/bin/python3 -I` 3.9.6 standard library only. No `X | Y` types. Install nothing. Absolute paths.
- Write only inside your own directory listed below. No commits, no pushes, no messages to Matthew. Stop starting new work at 18:20Z.

## Layout
```
tvbot/desk/
  CONTRACT.md        coordinator
  launch.py          coordinator: one-action launcher
  session.py         coordinator: SessionController (bar-by-bar runner: strategy -> orders -> state files)
  orders/            worker A (order engine + controls + intake guards)
  ui/                worker B (chart-first local page + stdlib server)
  strategies/        worker C (research strategies + walk-forward)
  tests/             each worker adds test_<area>_*.py; coordinator adds test_integration.py
```
Each subdir has `__init__.py`. Imports are package-relative from `tvbot/desk` on `sys.path` (e.g. `from orders.manager import OrderManager`).

## Test values (TEST VALUES, not Matthew's limits) **[v2]**
`limits = {"per_trade_notional": 2000, "max_loss_per_trade": 10.0, "daily_loss": 30.0, "gross_exposure": 2000, "label": "TEST VALUES"}`. Notional from `tvbot/config/smaller_size.json`; max loss and daily loss are 0.5% and 1.5% of a $2,000 hypothetical balance. Matthew sets real ones.

## Bars (input to everything)
One JSON object per bar, same as `tvbot/fixtures/normal_bars.jsonl`: `ts_open`, `ts_close`, `open`, `high`, `low`, `close`, `volume`, `seq`, `delivered_ts`, plus optional `exchange_ts` (time the venue stamped the data). Manifest line (`"type": "manifest"`) is skipped. Default replay data: `tvbot/fixtures/normal_bars.jsonl` (synthetic, label "SYNTHETIC BARS").

## Worker A: `orders/`
- `intake.py`: `check_bar(bar, prev_bar, calendar) -> (ok, code, detail)`.
  - `GAP_IN_SESSION` when an expected in-session bar is missing (by calendar, not by row number). A scheduled session break or overnight closure passes.
  - `ZERO_VOLUME` when volume is 0: that bar can never justify a fill.
  - `STALE_EXCHANGE_TS` when `received_ts - exchange_ts > max_age_s`, however fast the response was.
  - `calendar.py`: `SessionCalendar(tz="America/Chicago")` with `is_open(ts)`, `expected_bars(day, minutes)`, `session_bounds(day) -> (open_ts, close_ts)` **[v2]**, holidays Nov 26 closed, Nov 27 early close; tested on a simulated clock.
- `fake_broker.py`: `FakeBroker(seed, faults=None)` in-process. Methods: `submit(client_id, side, qty, limit=None)`, `cancel(client_id)`, `query(client_id)`, `list_orders()`, `positions()`, `step(bar)` (fills against the bar under the fill rule; never on a zero-volume bar), `events()` (acks/fills with `exec_id`, may duplicate or reorder under faults). Faults: `lost_ack`, `partial`, `cancel_fill_race`, `duplicate_event`, `out_of_order`, `margin_reject`, `outage`, `late_fill_after_cancel`. Every fill has `"mock": true`.
- `manager.py`: `OrderManager(state_dir, broker, limits)`.
  - `submit_intent(intent) -> intent_id`. Persist to `state_dir/intents.jsonl` BEFORE dispatch with a stable id (`decision_id` derived). On uncertain submit, `query` before any retry. Idempotent fill booking by `exec_id`.
  - `reconcile() -> report` at startup and reconnect: positions, working orders, fills; blocking alarm on vanished acknowledged order, truncated listing, excess position, foreign order.
  - Risk: `limits` as in Test values. Gross and worst-case risk COUNT WORKING ORDERS (filled + working + reserved). **[v2]** Reject an entry when the price risk to the stop, `qty × |intended_entry − invalidation|`, exceeds `max_loss_per_trade` (reason `MAX_LOSS`). Under the operator rule the est round-trip cost is budgeted separately: it counts in the daily worst case, `day loss (net of booked fees) + stop risk of position and working entries (with their est cost) + est fees still due on the open position + this entry's price risk and est cost > daily_loss` (reason `RISK_DAILY_LOSS_WORST_CASE`), separately from the notional check (`NOTIONAL`). An entry with no invalidation is rejected (`NO_STOP`).
  - Controls persisted to `state_dir/controls.json`, surviving restart and session expiry:
    - `pause()` / `resume()`: block new entries, cancel entry remainders, keep protective exits.
    - `stop_and_close()`: disable entries and the schedule, cancel entries, close the reconciled position including late or partial fills; `flat_confirmed` only when the broker's positions say 0.
    - **[v2]** `clear_stop(confirm=True)`: the only way a Stop is cleared; audit-logged. Restart, expiry and the schedule never clear it.
  - `state() -> dict` for `session.json` (see below).
  - Append every step to `state_dir/audit.jsonl`: `{ts, kind: knew|requested|acked|filled|canceled|rejected|alarm|control, ...}`.
- Tests prove the four regressions (omitted hour, zero-volume, old exchange timestamp, working orders in gross) and lost-ack + multiple fills after restart, plus Pause and Stop & Close across restart, plus **[v2]** MAX_LOSS rejection and a Stop that survives schedule re-arm.
- BTC reuse: port the design of BTC `order-live-r8b/reconcile.js` and `ledger-store.js` (intent before send, client-id match, blocking alarms). Cite file and lines in `orders/BTC_REUSE.md`. Read paths from `tvbot/feasibility/BTC_REUSE_AUDIT.md`. Read only; never edit BTC files.

## Worker C: `strategies/`
- `base.py`: `Decision` dict fields: `decision_id, ts_knowable, symbol, strategy, action (enter_long|enter_short|exit|pass|hold), qty, reason_code, reason_text, case_for, case_against, est_cost, pass_condition, trigger, intended_entry, intended_exit, invalidation`, plus **[v2]** `refusal_checks`: list of `{id, passed: bool, detail}` for every predeclared refusal test the strategy evaluated at `ts_knowable` (e.g. `NO_SIGNAL`, `COST_EXCEEDS_EDGE`, `OUTSIDE_SESSION`, `NEAR_CLOSE`, `INTAKE_REFUSED`, `MAX_LOSS_WOULD_BREACH`). Each strategy lists its refusal tests in `strategies/RULES.md` before results. Only decision-time facts go in a Decision; nothing after `ts_knowable`.
- `registry.py`: `STRATEGIES = {"ema": ..., "gold_basket": ..., "fixed_risk_single": ..., "bounded_fixed": ..., "cash": ...}`; each is `decide(bars_so_far, position, cfg) -> Decision` using only bars with `ts_close <= now`. Deterministic. `cash` always passes.
- `gold_basket`: the Reddit gold idea with a FROZEN swing-confirmation (change-of-character) rule written in `strategies/RULES.md` before results, netting the basket as one position with average price and a position-level stop. Escalation is research-only.
- `research.py`: walk-forward with an untouched final period, costs, netting, intraday drawdown and margin breach from every start date; writes `desk/out/research/RESEARCH_RESULT.json` and `.md`. Synthetic data is labeled harness evidence. Private licensed gold data (Codex `work/gold_history`) may be read locally; its outputs stay in `desk/out/research_private/` and are never published.
- Sources: `nov14-sprint/codex/REDDIT_ai_trading_Y4g3W8rErU_CAPTURE.md` (secondhand, Reddit blocked here), Codex `outputs/Gold_Historical_Challenge.md` (−$104.78 on 127 sessions; causal −$137.17).

## Best reasoned pass (rule, **[v2]**, replaces v1)
Chosen only from facts recorded at decision time: among `action == "pass"` decisions, the one with the **most failed predeclared refusal checks** (`refusal_checks` with `passed == false`); ties go to the **earliest `ts_knowable`**. The later price path, and any hypothetical return, is shown only after "Reveal outcome", labeled HYPOTHETICAL, and never added to P&L or counted as avoided-loss profit. The rule text is shown on the review screen. The coordinator computes it in `review.json`; the UI does not re-rank.

## Worker B: `ui/`
- `server.py`: `serve(state_dir, host="127.0.0.1", port=8765, controller=None)` stdlib `http.server`. **[v2]** `controller` (replaces `manager`) is the coordinator's `SessionController`.
  - GET `/` (index.html), `/api/session`, `/api/bars`, `/api/decisions`, `/api/ledger`, `/api/audit`, `/api/review`.
  - POST (each appends `{ts, action, body}` to `state_dir/control_requests.jsonl`, then calls the controller method if a controller is attached, and returns `{ok, session}`): `/api/arm` → `arm()`, `/api/advance` `{n}` → `advance(n)`, `/api/play` `{bars_per_sec}` → `play(bars_per_sec)` (0 = stop playing), `/api/pause` → `pause()`, `/api/resume` → `resume()`, `/api/stop_close` → `stop_and_close()`, `/api/clear_stop` `{confirm: true}` → `clear_stop()`, `/api/schedule` `{enabled}` → `set_schedule(enabled)`, `/api/close_session` → `close_session()`.
  - The server never fetches anything external. Bars served are the desk's own replay data only, and only bars up to the session's current replay clock (`session.json.replay_clock_utc`).
- `index.html` (+ inline JS/CSS, no CDN): chart-first, chart at half the window or more; three views (chart, decision, session review). Main screen: mode + session expiry, phase, exposure + protective orders, realized / unrealized / after-cost P&L, reasons for actions and passes, Pause / Resume and Stop & Close buttons (Stop & Close asks once to confirm).
  - **[v2] Flow bar** across the top, in order: Review (pre-session check from `session.json.preflight`) → Arm → Step / Play → Pause or Stop & Close → Close & review. Buttons enable by `phase`.
  - **[v2] Status, two separate badges:** "SIMULATION: ARMED | DISARMED | PAUSED | STOPPED" from the desk, and "EXTERNAL BROKER: NONE (offline in-process fake broker)" from `session.json.broker`. When the page cannot reach the local server, a third, distinct "DISCONNECTED: showing last known state" banner.
  - **[v2] Schedule panel:** a visible toggle, off by default, labeled "Offline schedule (simulated clock)", showing next simulated open/close from the calendar and stating that a schedule never clears a Stop.
  - **[v2] Plain-dollar risk line:** "Max loss per trade $10.00 (TEST VALUE) · Notional cap $2,000 (TEST VALUE) · Daily loss $30.00 (TEST VALUE)", each shown separately.
- Chart: canvas candles from `/api/bars`, entry / exit / pass markers. Click a marker: (1) setup on chart (trigger, intended entry, exit, invalidation lines), (2) case for and against, costs, pass condition, refusal checks, (3) timestamped trail knew -> requested -> acked -> filled from `audit.jsonl`. **[v2] While a marker is open, the chart draws only bars with `ts_close <= ts_knowable`; later bars, exit markers, fills and outcome text are hidden until "Reveal outcome".**
- Review view: best net trade, worst net trade, best reasoned pass (rule above, from `review.json`), after-cost comparison including cash, operating audit (limits, failure handling, Stop actually worked; untested controls shown plainly). If no trade filled, say so.
- **[v2] Native TradingView chart beside the desk (display only).** Two supported ways, both labeled "TradingView chart: operator view only, not used by the desk":
  1. A toggle "Show TradingView chart" (off by default) that loads TradingView's official free Advanced Chart embed widget for the session symbol in a left panel, with TradingView's attribution kept. Nothing is read from or injected into it. This is the only external load, it happens in the browser, and the desk runs normally with it off.
  2. Link "Open my TradingView chart" to `https://www.tradingview.com/chart/?symbol=<symbol>` in his own browser, with a one-line tip for macOS side-by-side (hold the green window button → Tile to left / right).
  - Sync is by instrument and timestamp only: the desk shows the symbol and replay clock so he can line them up.

## State directory files (session runner writes, UI reads)
Default `state_dir` = `tvbot/desk/state/` (scratch, gitignored); `--state-dir` overrides.
- `session.json`: `{mode: "REPLAY (OFFLINE, SIMULATED)", phase: "PRE_SESSION|ARMED|PAUSED|STOPPED|CLOSED", armed, session_id, expires_utc, replay_clock_utc, bars_total, bars_done, symbol, strategy, data_label, preflight: [{check, ok, detail}], schedule: {enabled, clock: "SIMULATED", next_open_utc, next_close_utc}, controls: {paused, stopped, flat_confirmed}, exposure: {position_qty, avg_price, working_orders: [...], gross_including_working}, protective_orders: [...], pnl: {realized, unrealized, fees, after_cost}, limits: {..., label: "TEST VALUES"}, broker: {name: "FakeBroker (offline, in-process)", external: false, connected}, updated_utc, simulated: true}`
- `bars.jsonl` (only up to the replay clock), `decisions.jsonl` (Decision + `outcome` object kept separate, filled only after the outcome is knowable), `ledger.jsonl` (one row per trade id: `trade_id, signal_ts, quote, decision_id, intent_id, order_id, fills[], fees, pnl_net, simulated`), `audit.jsonl`, `review.json` (`best_trade, worst_trade, best_pass, pass_rule, comparison[], operating_audit[], no_trade_filled`), `controls.json`, `intents.jsonl`, `control_requests.jsonl`.

## Launch (coordinator)
`/usr/bin/python3 -I <repo>/nov14-sprint/tvbot/desk/launch.py` loads the offline replay session in PRE_SESSION, writes the state dir, starts the UI on 127.0.0.1:8765 and opens the browser. Nothing trades until Arm. `--no-browser`, `--state-dir`, `--strategy`, `--port`, `--check` (headless self-test that arms, plays to close, pauses, stops, restarts and checks Stop persisted; exit code) are supported.
