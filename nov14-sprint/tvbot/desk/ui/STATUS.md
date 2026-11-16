# desk/ui: status (worker B, CONTRACT v2 + 18:20Z release list + Codex QA)

Updated 2026-11-15 18:14Z. Paper/offline only. Stdlib only, `/usr/bin/python3 -I` 3.9.6. No commits made; the coordinator publishes.

## Files

| File | What it is |
|---|---|
| `ui/__init__.py` | package marker |
| `ui/server.py` | loopback-only HTTP server: reads state files, takes control POSTs, builds the weekly review, serves reports |
| `ui/index.html` | the whole page (inline CSS and JS, canvas chart of desk replay bars) |
| `ui/make_sample_state.py` | regenerates `ui/sample_state/` from `tvbot/fixtures/normal_bars.jsonl` (70 bars) |
| `ui/sample_state/` | v2-shaped sample: phase ARMED, preflight, schedule, refusal_checks on all 70 decisions |
| `tests/test_ui_server.py` | 40 tests |

## Run

```
cd nov14-sprint/tvbot/desk
/usr/bin/python3 -I -m unittest discover -s tests -p 'test_ui*'      # 40 tests, OK at 18:13Z
/usr/bin/python3 -I ui/server.py --state-dir ui/sample_state --port 8781   # sample view
/usr/bin/python3 -I launch.py --no-browser --fresh --state-dir <dir> --port 8783   # real controller
```

## Entry points

- `serve(state_dir, host="127.0.0.1", port=8765, controller=None)` (CONTRACT v2).
- `make_server(state_dir, host, port, controller=None, verbose=False, manager=None)`. `manager=` is an alias for `controller=` (launch.py passes `manager=`). Non-loopback hosts raise ValueError; a foreign Host header gets 403.

## API

GET:
- `/`, `/api/health` (lists `routes`), `/api/session`, `/api/bars` (only bars with `ts_close <= replay_clock_utc`), `/api/ledger`, `/api/audit`, `/api/control_requests`.
- `/api/decisions`: outcome hidden until `?reveal=<id>`. On reveal, if the decision row has no `outcome`, the server joins `review.json` round trips (top level plus every `by_week` entry) on `entry_decision_id` or `exit_decision_id`. The outcome then carries entry/exit fill IDs, fill times, average prices, gross, fees, net, `simulated: true` and its source.
- `/api/review?week=<YYYY-Www>` (`&reveal_pass=1` adds the hypothetical path). It returns `weeks`, `default_week` (latest), `week`, `reports`, `week_report`. With `by_week`, the selected week's values are authoritative; an unknown week falls back to the default. best/worst trade carry `signal_ts` = the decision's `ts_knowable` and `first_fill_ts` = entry fill time.
- `/api/reports` lists report files. `/reports/<name>` serves only `.pdf`/`.html` from `<state_dir>/reports/`. The name must match `^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.(pdf|html)$` and resolve via realpath inside that folder; anything else is 404. Responses are inline, no-store and nosniff; HTML gets a sandboxed CSP.

POST (JSON, same-origin only, body up to 64 KB):

| Route | Body | Controller call |
|---|---|---|
| `/api/arm` | | `arm()` |
| `/api/advance` | `{n}` (1-500) | `advance(n=n)`; if `advance()` takes no args it is called n times |
| `/api/play` | `{bars_per_sec}` (cap 50) | `play(bars_per_sec)`; `<= 0` calls `stop_play()`, else `pause_play()` |
| `/api/pause` | | `pause()` |
| `/api/resume` | | `resume()` |
| `/api/stop_close` | `{confirm:true}` required | `stop_and_close()` |
| `/api/clear_stop` | `{confirm:true}` required | `clear_stop(confirm=True)` |
| `/api/schedule` | `{enabled}` | `set_schedule(enabled)`, else `schedule_on()` / `schedule_off()` |
| `/api/close_session` | | `close_session()` |

`/api/run_to_end` comes from launch.py's EXTRA_ROUTES. The page calls it from the "Run to end" button.

Every POST appends `{ts, action, body, request_id, ...}` to `state_dir/control_requests.jsonl` with fsync **before** the controller is called, then a second line with `status`. Missing confirm, a bad body or a cross-origin request return 4xx and call nothing.

## Page

- **Flow buttons:** Step 1, Step 10, Run to end, Play, Stop playing, Pause, Resume, Stop & Close and Clear Stop (both behind a confirm dialog, sending `{confirm:true}`), plus the Schedule toggle. Each button is disabled and struck through when its route is missing from `/api/health` routes, or after a 404, as on a bare server without the launcher.
- **TradingView reference:** a header picker offers AMEX:SPY (default), NASDAQ:QQQ, AMEX:IWM and AMEX:DIA. The link and the optional embed use only that operator symbol, never the desk's SYNTH-FUND-60M. Labels read "REFERENCE ONLY, real market, not the desk's data, nothing flows into the bot", "independent comparison" and "no alerts, no webhooks, nothing read back"; `allow_symbol_change: false`. The desk chart carries a SYNTHETIC pill.
- **Weekly review:** a week picker (latest marked), a Prior week button, a "Weekly report (PDF)" link for the selected week (or "not written yet"), and scope and label. The comparison is a readable Metric/Value table with no raw JSON. No-fill weeks show their note faithfully.
- **Trade cards:** before Reveal they show only the decision ID, side, qty and Signal (knowable time). After "Reveal outcome" they show net, gross, fees, entry/exit, first fill, exit kind and time, and filled IDs, with "Hide outcome again".
- **Decision view after Replay:** the chart is masked after `ts_knowable`. Before Reveal, the trail shows only entries at or before `ts_knowable`, with a count of hidden later entries, and the ledger is hidden. After Reveal, it shows the joined outcome (fill IDs, exit, net) and the flag "SIMULATED, MOCK FILL".

## Added 18:10-18:14Z (runner hooks and QA polish)

- `/api/weekly_report` (launcher route) now takes `{"week": "YYYY-Www"}`. `week` is in BODY_KEYS, and `_plan_call` checks it with `[0-9]{4}-W[0-9]{2}` fullmatch; anything else is a 400. It is passed as `{"week": ...}`. The review's week row has a **Build weekly PDF** button for the selected week, disabled without the route. On success it links the returned `/reports/...` url, shows the label and page count, and refreshes the review. A Reports line links every `/api/reports` file.
- The header shows `tradingview_label` beside the link. `tradingview_symbol` sets the reference symbol only if it is in the allowed list (SPY/QQQ/IWM/DIA), and the operator's own pick wins.
- Exposure panel: compact limits (`daily loss $30 · gross exposure $2,000 · ...`, full text in the tooltip) on a full-width row. Sizing and session_config (strategy, strategy_cfg, limits, fill_costs) appear read-only. `exec_refusals`, `refused_decisions` and EXEC_*_OVER_CAP alarms show as "REFUSED, no fill", never as fills.
- When the phase is CLOSED or COMPLETE, a static "Session complete" banner replaces the stale-runner warning, and the expiry reads "session complete: no expiry".
- `/?chart=1` opens with the TradingView reference visible, and the toggle is remembered in localStorage (`desk.tvOn`).
- Verified offline at 18:13Z on demo state: complete banner, no expiry countdown, compact limits, sizing and config shown, Build disabled on the bare server, Reports links listed. No iframe, no external script, no JS errors. `?chart=1` was not opened, so the session stayed offline.

## What was verified

- 38/38 UI tests at 18:08Z. The 7 new tests cover: the default week is the latest, a no-fill week is faithful and doesn't leak a hypothetical, an unknown week falls back, signal = ts_knowable, the reveal join from round trips, report path safety (txt, `..`, encoded traversal, missing file, dotfile and a pdf outside reports/ all 404), and the page strings (no `tradingview_symbol || symbol` fallback).
- Browser check on the bare server, with demo state from a `--demo` run (weeks W23-W40, reports only for W40). Network off; no iframe and no external script.
  - Run to end is disabled (no route without the launcher).
  - The link points to AMEX:SPY.
  - The review defaults to W40, and the comparison shows ema with 1 trade, fees 2.00 and net -1.33.
  - The best trade card hides its outcome; Signal reads 2026-09-28 17:30:02Z. After Reveal it shows net -1.33 and both MOCK FILL IDs.
  - The PDF link returns 200 application/pdf. Prior week moves to W39 and shows "No entry filled" and "report not written yet".
  - Replay of `dec-ema-febefb2a7d64f0b4`: before Reveal, 1 later trail entry and the ledger are hidden, and no net or exit fill appears. Only the KNEW row's intent ID shows, which is knowable at 17:30:02. After Reveal, both fill IDs and -1.33 appear, and "No outcome recorded" is gone.
- Earlier (17:55Z): live through `launch.py` with a real SessionController, all nine POST routes returned the expected phases.

## Fixed in this pass

- Codex QA: the reveal join for decisions without an outcome, outcome and fills moved behind Reveal on cards and trail, the comparison rendered as a table with a week selector, the TradingView link mapped to an operator reference symbol (AMEX:SPY), and the trade-card Signal uses `ts_knowable`.
- The comparison Trades column matched "after-cost P&L of closed mock round trips" (showed -1.33). An exact metric name ("round trips") now wins over a substring.
- Earlier: expiry judged on the replay clock; the broker row reads OFFLINE (in-process fake).

## Notes for the coordinator

1. Reports exist only for weeks the launcher wrote (W40 in the demo); other weeks show "Weekly report not written yet".
2. Hook stray files (`.claude-compact-anchor.md`, `.claude-compact-recovery.md`, `self-learning/`) sit in `desk/`, outside `ui/`, and were left alone. Exclude them from the publish.
3. My routes take precedence over launch.py's `advance`, `play`, `clear_stop` and `close_session` (`install_routes` skips existing keys). Tested live with DeskControls.
4. There is no `playing` flag in session.json, so Play and Stop playing are both enabled while ARMED.
5. The TradingView embed (official widget, off by default, CSP-allowed) was not exercised, because verification stays offline.

## Night redesign (W-A, 2026-11-16)

Worker W-A, branch `claude/night-dashboard-09ac67` on base f40e154. Only `ui/index.html` and this file changed; `server.py`, the tests and every W-B path are untouched.

What changed on the main page:
- **Chart first.** The desk replay chart leads the page, with the current decision and after-cost net P&L beside it (stacked under it at narrow widths).
- **One next action.** A banner at the top (`#nextAct`: `#nextTitle`, `#nextDetail`, `#nextBtn`) picks a single step from the real state: enable the adapter, arm, check for new bars, resume, finish Stop & Close, or review. The button clicks the existing control, so the IDs and API calls are unchanged. It mirrors that control's disabled or hidden state.
  - Stop & Close in progress points at **Check for new bars** while that step is enabled. The mock books the closing fill only at the next Check; Reconcile only re-reads the broker.
  - After the in-process mock has used all its bars, the banner reads **Mock bars used up** and offers the session review, instead of a misleading "Arm session".
  - Pre-session limits come from the preflight. This fixes a false "Approve your limits" when limits were already set.
- **Status and limits strip.** It shows mode, broker/venue, armed/disarmed, position, and the limits or "not set", with the limits source in full.
- **Progressive detail.** Trades, passes, audit and lab sit behind the existing view tabs and expanders. Session controls, worksheet and approval links, /spy-study, the lab, review/replay and the rehearsal flow are all kept.
- **Theme.** A header selector offers auto/light/dark (stored in localStorage `desk.theme`). The chart redraws when the OS theme changes. No external scripts or fonts; the timer count is unchanged (2 `setInterval`).

Verified:
- `cd nov14-sprint/tvbot/desk && /usr/bin/python3 -I -m unittest discover -s tests -p 'test_ui*'` gives 66 tests, OK (03:03Z, after the last edit). `node --check` on the extracted page script passes.
- A MOCK desk on 127.0.0.1:18871 (`launch.py --broker alpaca-paper --transport mock --fresh`, scratch state dir) was clicked through: Enable adapter → Arm → Check for new bars → Pause → Resume → Stop & Close (dialog, confirm) → Reconcile (still LONG) → Check → FLAT, "Stopped and flat". A second fresh run checked Enable → Arm → Check → "Mock bars used up".
- No horizontal scroll at 1440 or at 390 wide. Dark and light are both readable (body rgb(15,18,22) dark, rgb(243,245,248) light).
- Screenshots are kept in the private acceptance folder (night-dashboard, 01-17).

Follow-ups (not fixed here):
1. The broker banner can take the `draft` class because `/DRAFT/i` matches the mock limits_source text "no approved or draft limits". This is cosmetic: an amber banner.
2. Chart pass markers that map to the same bar stack downward and can run below the plot at narrow widths. The marker code is unchanged from f40e154.
3. When the mock bars are used up, the session-flow strip still highlights "2 Arm" while the banner says "Mock bars used up".
4. W-B scope: `test_alpaca_integration.test_mock_fill_time_follows_bar_clock` fails in the full suite. The in-process mock's bar supply also depends on the wall clock: around 03:00Z a fresh run had 67 of 68 bars already done.
5. The launcher fell back to port 18872 when 18871 had just been released. Wait until the port is bindable before restarting.

### Second pass (W-A, 03:19Z) — first viewport, truthful mode, lab badge

Changed `ui/index.html`, `ui/lab.html`, the UI tests in `tests/test_ui_server.py`, and this file. `server.py`, `alpaca/`, `orders/`, `strategies/`, `session.py` and `launch.py` are untouched.

- **One mode badge.** The header shows one badge, which reads `Local rehearsal`, `Paper (no real money)`, `LIVE: REAL MONEY` (red) or `Mode not reported`. `alpaca-live` renders as live and nothing else does. A paper or mock session never shows live. A broker mode the desk doesn't know shows `Mode not reported`, and its Arm label says the mode is unconfirmed.
- **One status line** (`#statusLine`), e.g. "Disarmed · Flat · Limits: demo" or "Armed · Short 20 sh · Limits: test values". The full strip (mode, venue, limits, evidence) and the broker detail (`#bbDetail`) sit behind **Details ▾** (`#modeDet`). The broker banner shows only when recovery needs action (uncertain client ids, reconcile blocking or ambiguous).
- **Overflow menus.** Historical study, the lab, /spy-study and the TradingView controls live in **Research ▾** (`#resPop`). A plain `Alpaca dashboard ↗` link goes to https://app.alpaca.markets/, separate from Setup. The Arm/Pause/adapter controls card is collapsed under "More controls and broker detail". Stop & Close stays in the session flowbar.
- **Empty chart** reads "No bars yet." plus the next step, with no filenames.
- **Wording.** Partial protection reads "PARTIALLY PROTECTED: k of n sh protected, u UNCOVERED". The quote reads "Latest IEX bid/ask (indicative, not a tradable price)". The stale-runner alarm no longer shows for a connected Alpaca session, where no background runner is expected.
- **lab.html** shows the same mode badge, read from `/api/session` with the same mapping.
- **Fix.** A global `[hidden]{display:none !important}`, because `.banner.bb{display:flex}` was overriding `hidden`. The limits `draft` class no longer matches "no approved or draft limits" (follow-up 1 above).

Chart position (#chartPane top / canvas top, px):

| Viewport | Before | After |
|---|---|---|
| 1280x720 | 427 (Codex, 02:53Z) | 124 / 159 |
| 1440x900 | — | 124 / 159 |
| 390x844, empty | — | 309 / 369 |
| 390x844, populated with stale banner | — | 364 / 423 |

No horizontal scroll at any of these sizes.

Verified: 67 UI tests OK (03:19Z). `node --check` passes on both pages' scripts. index.html has 2 `setInterval` and lab.html none. Neither page has an `<iframe` or `<link`. A JS probe with no network confirmed badge and broker words for live, paper, mock and unknown modes. Screenshots 10-15 are kept in the private acceptance folder (night-dashboard).

### Third pass (W-A, 03:25Z)

1. **Used-up mock bars.** When an alpaca-mock run has checked every bar, the session flow no longer points at "2 Arm". It highlights "Close & review", the step the banner's "Mock bars used up" card sends you to. Arm also loses its filled primary style in that state only. Both read the same `mockUsedUp(s)` helper as the banner.
2. **Markers at 390px.** Stacked entry, exit and pass markers are clamped inside the price plot. Their meaning is unchanged: long and pass sit below the bar, short and exit above.
3. **Live badge.** The page shows the red "LIVE: REAL MONEY" badge if any one of the controller's live strings appears: `broker_mode` "alpaca-live", adapter `path_name` "alpaca_live.json", or adapter `mode` "live". A conflicting paper label never hides a live signal. lab.html uses the same three checks.

Verified: 70 UI tests OK (03:25Z). They include a fake live `/api/session` test. It serves a live payload over loopback and runs the page's own mode helpers in node. It asserts the red LIVE badge and no "Paper" wording, for the full payload and for each live string alone. `node --check` passes on both pages. index.html has 2 `setInterval` and lab.html none. Neither page has an `<iframe` or `<link`. Screenshots 16 (used-up flow) and 17 (markers at 390px) are kept in the private acceptance folder (night-dashboard). The live badge has been checked only by test and probe. No live session was used.

### Fourth pass (W-A, 03:37Z): truthful banners, one disclosure

Codex's Chromium probe against ba4b3d6 reproduced two false banners. Both are fixed, along with the tab title and the first screen.

1. **No false "used up".** In the Alpaca modes, `bars_total` counts the bars fetched so far, not what the feed can still produce. `barsUsedUp(s)` (it replaces `mockUsedUp`) is therefore false for every Alpaca payload: mock, paper and live. It is true only for an offline replay whose end is known (`bars_done >= bars_total > 0`). The banner and the session flow both read it, so a paper session with 64 of 64 bars keeps Arm or Check as its next step, and the next Check still advances to bar 65. A finished replay that still holds a position now points at Stop & Close, not at a disabled Close & review.
2. **No false "Stop & Close finished".** "Stopped and flat / Stop & Close finished" now requires all four: local position 0, `controls.flat_confirmed` true, no `close_pending`, and recovery neither ambiguous nor blocking. Otherwise the banner reads **Stop & Close not confirmed** and says why: the broker has not confirmed flat, recovery is ambiguous, or a close is still pending, in which case "The desk keeps retrying the close". In the Alpaca modes it offers Reconcile now.
3. **Tab title and brand.** `document.title` follows the same mode helper as the badge, e.g. "Local rehearsal · SPY Desk". The static title is "SPY Desk", and the header brand is "SPY Desk" (no longer "SPY Paper Desk"), so a live page never says Paper.
4. **One next step plus Stop & Close.** Pause, Resume, Clear Stop, Close & review and the rehearsal steps sit in one `<details id="flowMore">` disclosure, "More session actions (n)". Its summary is keyboard-focusable and opens with Enter or Space. Below 561px the disclosure starts closed, shows only the enabled actions (never a row of disabled buttons), and says "none now" when nothing applies. Stop & Close sits outside the disclosure, first in the row, and hides only while it is disabled. At 561px and wider the summary is hidden and the full strip shows inline as before.
5. **Empty chart.** It says only "Waiting for the first SPY bar". Its source is the chip in the chart header ("Desk replay chart" with SYNTHETIC, or "SPY bars" with the feed's source tag in the Alpaca modes).
6. Rehearsal labeling, early Stop, the accessibility labels and every earlier test are kept.

Verified: 78 UI tests OK. New probes run the page's own `nextStep` and `barsUsedUp` in node against these payloads: paper, mock and live at 64 of 64 bars; armed at bar 65; a finished and a midway replay; a finished replay holding a position; and Stop & Close unconfirmed, confirmed-but-ambiguous and clean. Static tests cover the disclosure, the title and the empty chart. `node --check` passes on both pages. index.html has 2 `setInterval` and lab.html none. Neither page has an `<iframe` or `<link`. At 390x844 a populated replay shows the next step, the chart, Stop & Close and "More session actions (3)", with no horizontal scroll. Screenshots 18 (390px) and 19 (1280x720) are kept outside the repo.
