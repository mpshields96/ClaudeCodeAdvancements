# Alpaca paper adapter: shared contract (window 21:50:46 to 23:50:46 UTC, Nov 15)

Owner and sole publisher: the Claude coordinator chat. Base: `nov14-sprint-release` at c0d96ae.
Publish branch: `nov15-alpaca-paper`. The desk's existing CONTRACT.md and INTEGRATION.md still hold.

## What Matthew asked for, and what are build rules

Matthew's own requests, as relayed by his lead Codex chat (agent relays, not typed here by him):

1. 21:50Z: "Build the Alpaca paper connection for SPY using free data. I'll set my limits before the first broker test."
2. ~22:00Z: "Be sure to impress and amaze me … Work on improving this bot to somewhere I would have only ever wished it was capable of doing in the past."
3. ~22:05Z: "Have an infrastructure of sizing and dollar limits ready to go, I just get final say."

Everything below is **implementation rules from the Codex supervisor and the coordinator**, not Matthew's
words. The rules still bind every worker:

- No real broker-account or network tests, and no lookups of or access to credentials, in this window. No agent opens a
  socket to any Alpaca host, reads env vars or Keychain items holding keys, or runs
  `security find-generic-password`. Tests use injected transport or the in-process mock only.
- Mock or injected transport with fully synthetic ids, keys, account numbers and bars. Reading Alpaca's
  public docs is fine.
- Matthew has final say on sizing and limits. Agents build the infrastructure: a worksheet, calculated
  effects, read-only suggested alternatives and clearly labeled test examples. Nothing activates
  automatically, changes his size or caps, or treats an example as his choice. Only his explicit local
  approval makes a snapshot real (section 5).
- No secrets in chat, logs or git. Keys never enter a log, audit row, exception text, state file, UI
  payload or repo.
- Fixed paper host; redirects and foreign origins refused; free IEX only; SPY only; no paid route.
- Manual paper session first. No timers, daemons, cron or threads that trade while nobody is watching.
  Bars advance only when the operator acts. Do not imply a background job.
- The first authenticated smoke test is Matthew's, after he approves his limits.
- One writer per file (table below). No NFL or other projects. No commits or pushes by workers.

## Package layout and file owners

| Path (under `nov14-sprint/tvbot/desk/`) | Owner |
|---|---|
| `alpaca/__init__.py` (constants, labels), `alpaca/state.py` (enable/disabled), `alpaca/CONTRACT.md` | coordinator |
| `alpaca/transport.py`, `alpaca/mock.py`, `alpaca/broker.py`, `tests/test_alpaca_broker.py`, `orders/manager.py` (only if needed) | W1 broker |
| `alpaca/feed.py`, `alpaca/mock_data.py`, `alpaca/RESEARCH.md`, `orders/calendar.py`, `tests/test_alpaca_feed.py` | W2 feed |
| `alpaca/setup.py`, `alpaca/sizing.py`, `alpaca/SETUP.md`, `alpaca/limits.template.json`, `ui/index.html`, `ui/server.py`, `tests/test_ui_server.py`, `tests/test_alpaca_setup.py`, `tests/test_alpaca_sizing.py`, `alpaca/QA.md` | W3 operator |
| `lab/` (new package), `strategies/challenger.py`, `ui/lab.html`, `report.py` (lab section only), `tests/test_lab.py` | W2 after its feed unit (section 7) |
| `session.py`, `launch.py`, `INTEGRATION.md`, `tests/test_integration.py`, `.gitignore`, `Open Paper Desk.command`, `Open Alpaca Paper Desk.command` | coordinator |

Need a change in a file you don't own? Write the exact ask in your STATUS file and message the
coordinator. Stdlib only, `/usr/bin/python3 -IB` (3.9.6; no `X | Y` type syntax). Tests run from
`desk/`: `/usr/bin/python3 -IB -m unittest discover -s tests` (184 OK at c0d96ae; keep it green).
Modules import as `from alpaca import ...` and `from orders.fake_broker import ...` with `desk/` on sys.path.

## 1. Transport (W1, `alpaca/transport.py`)

One call shape for everything:

```
transport.request(method, origin_key, path, query=None, body=None) -> (status:int, payload:dict|list|None)
```

- `origin_key` is `"trading"` or `"data"`; the URL is `ORIGINS[origin_key] + path`. Anything else raises
  `TransportRefused`. `path` must start with `/v2/`, contain no `://`, `@`, `..`, `\`, whitespace or
  control chars. Query values are urlencoded by the transport, never by callers.
- `HttpsTransport(credentials_provider, timeout_s=10, opener=None)`: urllib with a redirect handler that
  refuses every 3xx (`TransportRefused("redirect refused")`), and a final-URL check that the response host
  equals the requested fixed host. TLS verification stays on (default context). A host in
  `REFUSED_HOSTS` is refused even if `ORIGINS` were edited. `opener` is injectable for tests; tests never
  use a real socket. Credentials are fetched from the provider per request and sent only as the two
  Alpaca auth headers (verify header names in the docs). Exception and repr text never include them.
- Timeouts, connection errors and 5xx on a POST that could have created an order raise
  `BrokerUncertain` (from `orders.fake_broker`); on GET/DELETE they raise `BrokerOutage`.
  4xx returns `(status, payload)` for the caller to map.
- Credentials provider interface (W3 writes the real ones in `alpaca/setup.py`):
  `provider.get() -> (key_id, secret)`; `provider.describe() -> str` (no secret material, e.g.
  "macOS Keychain item alpaca-paper"). Tests use `StaticTestProvider("PKTEST...", "synthetic")`.

## 2. In-process mock (W1 `alpaca/mock.py`, W2 `alpaca/mock_data.py`)

`MockAlpacaTransport(trading=MockTrading(...), data=MockData(...))` implements the same `request()` and
routes by `origin_key`. No sockets. Synthetic ids only (e.g. `mock-ord-0001`, account `MOCK-ACCT`).
`MockTrading` covers: `POST /v2/orders`, `GET /v2/orders`, `GET /v2/orders/{id}`,
`GET /v2/orders:by_client_order_id`, `DELETE /v2/orders/{id}`, `GET /v2/positions`,
`GET /v2/positions/SPY`, `GET /v2/account`, `GET /v2/clock`, `GET /v2/calendar`. Fault knobs: lost ack
(order created, response dropped), 5xx, timeout, partial fills, fill after cancel request, reject,
foreign order, truncated listing. A method `advance(price)` lets tests and the mock session move fills.
`MockData.handle(method, path, query)` serves `/v2/stocks/SPY/bars` (and `/v2/stocks/bars`) with
synthetic 1Min bars, refusing `feed` other than `iex` with a 4xx.

## 3. Broker (W1, `alpaca/broker.py`)

`AlpacaPaperBroker(transport, state_dir, evidence_label, adapter_state)` mirrors `orders/fake_broker.py`
so `orders/manager.py` and `session.py` work unchanged:

- `submit(client_id, side, qty, limit=None, stop=None, tag=None, reduce_only=False)` returns the ack dict
  shape FakeBroker returns. Maps `client_id` to Alpaca `client_order_id`. SPY only, whole shares,
  `time_in_force=day`, market/limit/stop. Refuses (status rejected, no network) when the symbol, qty or
  type is invalid, or when reduce_only would increase exposure (cap to the current position; Alpaca has
  no reduce-only flag for equities: verify).
- Disabled or halted (`adapter_state.enabled` False, Stop active, or recovery ambiguous): **new
  exposure is refused** (`ADAPTER_DISABLED` / `RECOVERY_AMBIGUOUS`), but these still work, including
  during gaps with no new bar: read-only `query`/`list_orders`/`positions`/reconcile; `cancel`; and a
  protective reduction (`reduce_only=True`) whose qty is capped to a position **verified by a fresh
  `positions()` call** in the same operation. Recovery is ambiguous while any submit is uncertain and
  unresolved, the last listing was incomplete, or the last reconcile raised a blocking alarm.
- Lost ack: on `BrokerUncertain` from POST, raise `BrokerUncertain`; the manager then queries.
- `query(client_id)`: `GET /v2/orders:by_client_order_id?client_order_id=...`; 404 returns None.
- `cancel(client_id)`: allowed even while disabled (flattening must work). Map Alpaca outcomes to
  FakeBroker's results (canceled / rejected UNKNOWN_ORDER / ALREADY_FILLED / ALREADY_DONE).
- `list_orders()`: `{"orders": [...], "complete": bool, "total": int}`; `complete` is False when the page
  limit is hit. Order dicts use the FakeBroker shape: `client_id, order_id, symbol, side, qty, limit,
  stop, tag, reduce_only, submit_ts, status in (working, filled, canceled, rejected), filled_qty,
  avg_fill_price, fills[]`, plus `"evidence": <label>`, `"alpaca_status": <raw>`. Map every Alpaca status;
  unknown ones pass through unchanged so the manager flags UNKNOWN_STATUS.
- Fills: derived from `filled_qty` / `filled_avg_price` deltas per order (or the activities endpoint if
  you verify it is simpler), each with a stable `exec_id` such as `<order_id>:<cum_qty>` so a restart
  never double-books or loses a partial. Per-order last-seen cumulative qty is persisted in
  `<state_dir>/alpaca_broker.json` (fsync + replace). Fill dicts match FakeBroker's keys; set
  `"mock": <True only for mock/injected>`, `"evidence": <label>`, `"price_basis": "Alpaca paper fill"`
  (or `"MOCK LOCAL fill"`), `fee` 0.0 unless verified otherwise.
- `positions()`: `{"SPY": {"qty": int, "avg_price": float}}` from `/v2/positions` (empty means flat).
- `step(bar)`: no simulation. Polls open orders, emits fill/canceled/rejected events once each.
- `events()`: drains the queued events (ack/fill/canceled/rejected), each with `"evidence"`.
- `snapshot()` / `restore(d)` for the session's persisted state; `exec_caps` dict and `exec_refusals`
  list attributes kept for the session (pre-trade caps are checked at submit from the latest bar close).
- `NAME` and `label` = the evidence label. Integrity faults (foreign order on SPY, position mismatch,
  OVERFILL) call `adapter_state.disable(reason)`; the session also disables on Stop.

### 3a. Priced, bounded entries (Codex adviser cap finding, ~22:12Z; adopted)

- An unpriced market entry sized from the last hourly close can fill above a notional cap. On the Alpaca
  path every **buy entry is a limit order**. The session sets `limit = floor_to_tick(min(decision entry
  price, per_trade_notional/qty, remaining_gross/qty, stop + (max_loss_per_trade - est_cost)/qty))`
  (tick $0.01; remaining_gross = gross_exposure - |position| x price - working entry notional). If that
  bound is at or below zero, or under the stop, the entry is refused before submit (`ENTRY_BOUND`).
- The broker is a second wall: it refuses an entry with no limit (`UNPRICED_ENTRY`), and one whose
  qty x limit exceeds per-trade or remaining gross caps (`EXEC_CAP`), with no POST.
- **Short-opening exposure is blocked** on the SPY first-test path (`SHORT_OPEN_BLOCKED`): a sell that is
  not reduce_only and would take the position below zero. Exits, protective reductions, cancel and Stop
  stay available, also while disabled.
- Test against the actual serialized POST body (`test_gap_over_cap_serialized_post`).
- Data labels stay distinct: the production free-IEX quote/bar feed (`DATA_LABEL_IEX`), mock bars
  (`DATA_LABEL_MOCK`), and the historical SPY trade-bar research set that Codex holds and replays
  privately (not copied into this repo).

## 4. Feed and calendar (W2, `alpaca/feed.py`, `orders/calendar.py`)

- `IexSpyFeed(transport, calendar, minutes=60)`; `fetch_closed_bars(after_ts_close, now_utc)` returns
  desk bars for slots fully closed by `now_utc`. Each bar has the intake fields
  (`ts_open, ts_close, open, high, low, close, volume`) plus `symbol: "SPY"`, `feed: "iex"`,
  `source: <DATA_LABEL_IEX or DATA_LABEL_MOCK>`, `received_ts` (when fetched), `exchange_ts` if known,
  `bar_count_1min`, and `partial: True` if minutes are missing.
- The desk calendar anchors hourly slots on the 09:30 ET open (14:30Z in winter), last slot 15:30 to
  16:00. Alpaca 1Hour bars are clock-aligned, so build slots from `feed=iex` 1Min bars aggregated into
  `calendar.bar_slots(day, 60)`. Verify bar timestamp semantics (start vs end) in the docs.
- Refuse `feed != "iex"`, `symbol != "SPY"`, any SIP or paid parameter. Page with `next_page_token`.
- Calendar: extend `orders/calendar.py` coverage past 2026-12-31 only from a verified public NYSE
  holiday list (cite it in RESEARCH.md), and add a cross-check against `GET /v2/calendar` responses
  (mock in tests). `CalendarNotCovered` must still raise outside coverage.
- RESEARCH.md: primary-source citations (Alpaca docs URLs, date read) for every fact the code relies
  on: hosts, auth header names, IEX free-plan scope, bar timestamp meaning, order statuses, client order
  id rules and length, reduce-only, fractional/whole shares, PDT and paper-account behavior, rate limits.
  Use the Gemini MCP (`mcp__gemini-public-research__research_public_question`) for discovery and a
  second opinion, then confirm against the primary page. Mark anything unconfirmed [UNVERIFIED].

## 5. Operator setup, limits, UI, QA (W3)

- `alpaca/setup.py`: `KeychainProvider(service="alpaca-paper")` (reads via `/usr/bin/security` only when
  `get()` is called at Matthew's runtime) and `EnvProvider()` (`APCA_API_KEY_ID`/`APCA_API_SECRET_KEY`).
  Refuse a key id that looks like a live key (verify the paper prefix in docs).
- **Sizing and limits worksheet** (`alpaca/sizing.py` plus a Setup panel in the UI). Flow:
  draft, then inspect and change, then explicit operator approval for paper.
  - Fields: `fixed_shares` (whole shares, required; never defaults to the demo `--qty 1` or any
    formula), `max_loss_per_trade` (per-trade dollar risk), `daily_loss`, `per_trade_notional`
    (per-order notional) and `gross_exposure` (aggregate exposure).
  - Calculated effects at a chosen reference price and illustrative stop distance: notional; payoff
    per $1 SPY move; estimated loss at the stop, plus assumed fees and slippage (labeled as assumed);
    remaining capacity; worst case if every working order fills; and plain-English pass/fail reasons
    for a proposed trade against each cap.
  - Read-only suggested alternatives (e.g. "shares that fit your $X risk at this stop") and clearly
    labeled TEST EXAMPLE presets are allowed. They never fill the draft unless the operator clicks to
    copy one in, and they never approve anything.
  - Approval is an explicit local operator action. The operator reviews an old-to-new diff, types a
    confirmation and gives a reason. It writes `<state_dir>/limits_approved.json` with
    `provenance: "operator-approved"`, `approved_utc`, `reason`, the diff, and a content hash. The new
    session binds that snapshot through the session config lock. Drafts live in
    `<state_dir>/limits_draft.json`, `provenance: "draft"`.
  - **A genuine config is decided by provenance plus explicit local confirmation, never by numerical
    equality.** Matthew may choose the same dollar amounts as a demo. Refused on the real paper path:
    no approved snapshot; provenance `draft`, `template` or `test-example`; a hash mismatch (edited after
    approval); any null or non-positive value; a missing `fixed_shares`.
  - An incomplete draft is usable with no keys and no network. The mock mode can rehearse with an
    approved snapshot or with a draft, banner-labeled "DRAFT LIMITS (not approved)". The real paper
    path requires an approved snapshot. Mock verification must enforce whatever is active.
  - `load_limits()` returns `{values, provenance, approved_utc, hash}` or raises a plain reason. It never
    invents a default.
- `limits.template.json`: every value null, `provenance: "template"`.
- `SETUP.md`: plain-English, step-by-step for Matthew: make a paper account and paper keys himself,
  store them in Keychain with the exact `security add-generic-password` commands (he types them; we never
  see the values), write his limits file, then start a manual paper session. States what is not tested:
  no authenticated call has ever been made.
- UI: a broker-mode banner from `session_state()` fields `broker_mode`
  (`offline-fake` / `alpaca-mock` / `alpaca-paper`), `evidence_label`, `data_label`, `adapter` (state view),
  `limits_source`; Enable (confirm) and Disable controls calling `POST /api/alpaca/enable` and
  `POST /api/alpaca/disable`; a "Check for new closed bar" button that calls the existing advance route;
  no auto-poll timer in alpaca modes. Show reconcile alarms, uncertain orders and partial fills plainly.
- Fix the blank decision-price lines: `ui/index.html` `num()` and `ui/server.py` `_num()` must unwrap
  `{"price": float, "text": str}` before the numeric test, with tests.
- QA.md at the end: run the mock-mode desk end to end (launcher with `--broker alpaca-paper --transport
  mock`), record what you exercised and what failed.

## 6. Coordinator integration (session.py, launch.py)

- `launch.py --broker {offline,alpaca-paper}` (default offline, unchanged behavior) and
  `--transport {mock,https}` (default mock). `https` additionally needs `--limits <Matthew's file>` and a
  credentials provider; it is never run by agents.
- Alpaca modes use the wall clock and `IexSpyFeed` instead of the fixture replay clock; Advance becomes
  "check for new closed bar"; the simulated schedule and Play are off. Stop disables the adapter.
- `session_state()` gains the fields in section 5.
- Stop, reconcile and protective reduction are available on demand from the UI without a new bar
  (controller methods `reconcile_now()`, `stop_and_close()`), and are allowed while the adapter is
  disabled. New exposure is refused while recovery is ambiguous.
- `Open Alpaca Paper Desk.command` (Finder double-click): opens the desk in mock mode, with a
  readiness checklist (limits approved? calendar covered? keys: "checked only when you start a real
  session") and the mock walkthrough. Nothing is hunted in Terminal.

## 7. Decision lab (W2 after its feed unit; merge point session.py `_step_one`)

A frozen shadow challenger, recorded before outcomes, scored only on later observations, visible in the
normal Alpaca desk. It never routes orders, never auto-promotes, never changes size or limits.

- `strategies/challenger.py`: one frozen rule set, for example trend (EMA slope) plus a volatility
  filter (ATR or a range percentile) plus a measured cost hurdle (expected move must clear the spread,
  slippage and fees, doubled for the sensitivity view). Its parameters are fixed in the file with a
  `FROZEN_AT` date and a cfg hash, and are not tuned on outcomes. It uses the same `make_decision`/`line()`
  shapes as the other strategies (from `strategies/base.py`), so every action or pass carries its price
  and indicator thresholds, its friction (measured, or explicitly assumed and labeled) and "what must
  change to trade". **Do not add it to `STRATEGIES`** (that list feeds `strategy_names()`,
  `load_strategy()` and `launch --strategy`, so it would become routable). Expose it from a separate
  shadow registry (`lab.SHADOW = {"challenger": decide}`). The session and CLI must reject
  "challenger" as an active strategy in every mode. EMA behavior is unchanged.
- `lab/record.py`: `LabRecorder(state_dir)`. `record(bar_window, decisions)` appends one row per
  strategy (challenger, EMA baseline, cash) to `<state_dir>/lab_forecasts.jsonl`. Each row holds:
  `forecast_id`, `ts_recorded` (wall), `ts_knowable` (the bar close), the sha256 of the exact input bars,
  the action or pass, thresholds, assumed costs, and `prev_hash` (a hash chain, so later edits are
  detectable). It is written **before** the broker step for that bar. Identical inputs feed all three.
- `lab/score.py`: scores a forecast only against bars with `ts_close` after its `ts_knowable`, written
  to `lab_scores.jsonl` with the forecast_id and the hashes of the later bars used. It reports net of
  costs, doubled-friction sensitivity and the comparison against EMA and against cash. A pass is never
  realized P&L; hypothetical pass outcomes are labeled HYPOTHETICAL.
- `lab/verify.py`: `verify(state_dir, forecast_id)` recomputes the input hash, the chain, the decision
  (by re-running the frozen challenger on the stored bars) and the score, and returns pass/fail per
  check. A skeptic clicks one opportunity in `ui/lab.html` and sees the before record, the after
  record and the verify result.
- UI: `ui/lab.html` (W2's) is a standalone page in the desk's style. W3 adds a "Decision lab" link plus
  routes in `server.py`: `GET /api/lab` returns `ctl.lab_view()` and `GET /api/lab/verify?id=` returns
  `ctl.lab_verify(id)`, both guarded with `hasattr`. The weekly report gets a small lab section
  (`report.py`, W2) that reuses the existing views. No broad redesign.
- Empirical claims: only on data whose source, rights and period are verified. Fixture or mock bars
  are labeled synthetic. Matthew's Codex chat is sourcing free historical SPY research data; do not
  duplicate that search.
- First vertical slice, ahead of extras: challenger, recorder and verify on the mock feed, with one
  opportunity clickable end to end in `lab.html`.

## Milestones (UTC)

- 22:05 workers started. 22:40 worker checkpoint 1: modules plus green tests, STATUS updated.
- 22:55 coordinator integration; first runnable checkpoint pushed by 23:05.
- 23:15 worker finals. 23:25 W3 QA pass in mock mode. 23:35 clean clone, full tests, package, push.
- 23:50:46 window ends. Workers stop writing at 23:30 unless asked.

Worker status files: `alpaca/STATUS_W1.md`, `alpaca/STATUS_W2.md`, `alpaca/STATUS_W3.md` (each worker owns its own).
