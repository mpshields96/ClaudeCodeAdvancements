# Paper desk: integration and normal commands

SIMULATED paper desk. Mock fills only. No broker account, no credentials, no real
orders, no network order path. TradingView is a display link the operator opens
in their own browser; the desk never reads TradingView data. Limits and the
1-share size are TEST VALUES. Matthew sets real sizing and limits himself.

## Normal commands (macOS system Python, stdlib only)

Run from the repository root.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/launch.py
```
Start the desk (state in `desk/state`, resumes where it stopped) and open the UI at
`http://127.0.0.1:8765/`.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/launch.py --demo
```
Fresh scratch state in `desk/state-demo` (any previous one is renamed, never
deleted), replay all 630 bars, write the weekly review (and the weekly PDF when
`desk/report.py` is present), then serve the UI.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/launch.py --check
```
Offline self-check in a temporary directory. Exit 0 and `CHECK PASS` on success.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/launch.py --no-browser --state-dir /tmp/desk-qa --fresh --port 8765
```
Targeted QA in a scratch state directory.

```bash
/usr/bin/python3 -IB -m unittest discover -s nov14-sprint/tvbot/desk/tests
```
All desk tests.

## Flags

| flag | default | meaning |
|---|---|---|
| `--state-dir` | `desk/state` | scratch state directory |
| `--strategy` | `ema` | `ema`, `gold_basket`, `fixed_risk_single`, `bounded_fixed`, `cash` |
| `--qty` | `1` | HYPOTHETICAL fixed entry size in shares (TEST VALUE). `0` = the strategy's own sizing |
| `--port` | `8765` | loopback port (the next free one is used if taken) |
| `--fresh` | off | rename the existing state dir aside and start clean |
| `--demo` | off | fresh scratch run to the end, weekly review, then serve |
| `--play-rate` | `4` | bars per second for Play |
| `--autoplay` | off | enable the simulated schedule and start Play |
| `--no-browser` | off | do not open the browser |
| `--check` | off | offline self-check, then exit |

With `--qty 0`, `ema` sizes about 20 shares and the $10 TEST max loss refuses every
entry. The review lists those as `refused_decisions` ("REFUSED BY RISK CHECK - NOT
SENT, NOT FILLED"). That is the limit working, not a bug.

## Session config lock

Scenario lock: each launcher holds `<state-dir>.launch.lock` (a sibling file, so `--fresh`/`--demo` rotation cannot move it) for its whole lifetime, and checks the order manager lock inside the dir before any rename. A second launcher on the same scenario, with or without `--fresh`, `--demo` or a new `--qty`, prints `REFUSED: ... is in use`, renames and writes nothing, and exits 2. Use a unique new `--state-dir` instead.

At creation each state dir records `session_config.json` (strategy, strategy
settings including `fixed_qty`, limits and fill costs). Reopening the same dir with
a different `--qty`, `--strategy` or limits is refused: launch.py prints the recorded
and requested values and exits 2, and `desk_audit.jsonl` gets a
`session_config_change_refused` row with both. A non-empty state dir without a
config is also refused. To try a different size, start a clearly labeled fresh
scenario with `--fresh` (the old dir is renamed aside, never deleted) or a new
`--state-dir`.

## Controls (UI buttons and POST routes)

`arm`, `pause`, `resume`, `play`, `stop_play`, `advance`, `advance10`, `run_to_end`,
`schedule_on`, `schedule_off`, `close_session`, `preflight`, `stop_close` and
`clear_stop` (both need body `{"confirm": true}`). Stop survives a restart and
blocks re-arming until Clear Stop is confirmed.

`weekly_report` (POST `/api/weekly_report`, body `{"week": "2026-W40"}`, or no week
for the default) writes `reports/report_<week>.html` and `.pdf` (at most 3 pages)
and returns the `/reports/...` link. CLI equivalent:
`/usr/bin/python3 -I desk/report.py --state-dir <dir> --week 2026-W40`.

The TradingView panel uses `AMEX:SPY` as a REFERENCE ONLY real-market chart beside
the synthetic replay (`tradingview_symbol`, `tradingview_label` in `/api/session`).
The desk never reads TradingView data, and its prices are not the replay's.

## Fill model

- A decision made on bar N's close is filled at bar N+1's close, never at bar N+1's
  open. The open is stamped before the decision exists. Each fill carries
  `event_ts`, `report_ts` and `fill_model`.
- Costs per side: half spread 1 bps, slippage 2 bps, and a commission of $0.005/share
  with a $1 minimum.
- Bar intake refuses `BAD_BAR`, `OUT_OF_ORDER`, `GAP_IN_SESSION`, `STALE_EXCHANGE_TS`,
  `FUTURE_EXCHANGE_TS`, `ZERO_VOLUME`, `OUT_OF_SESSION` and `NOT_CLOSED_AT_RECEIPT`
  (receipt earlier than the bar's close, so its high/low/close aren't knowable yet).
  A refused bar never fills an order and never reaches the strategy.

## Weekly review

`review.json` covers one ISO week of local sessions (America/Chicago); by default
it's the last replayed week. `weeks`, `default_week` and `by_week` hold every week,
including weeks with no fills, so a prior week can be picked.
`all_weeks_summary` is the whole-run total. The fixture spans 18 weeks
(2026-06-01 to 2026-10-02).

## State files (in the state dir)

`session_config.json` (the frozen sizing, limits and strategy), `session.json`, `decisions.jsonl`, `ledger.jsonl`, `intents.jsonl`, `audit.jsonl`,
`desk_audit.jsonl`, `controls.json`, `control_requests.jsonl`, `broker_state.json`
(the fake broker's book, kept apart from the order engine's journal), `review.json`,
and `reports/` (the weekly PDF and HTML).
