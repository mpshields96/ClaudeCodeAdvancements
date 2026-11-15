# desk/ui: status (worker B, CONTRACT v2)

Updated 2026-11-15 ~17:58Z. Paper/offline only. Stdlib only, `/usr/bin/python3 -I` 3.9.6. No commits made; the coordinator publishes.

## Files

| File | What it is |
|---|---|
| `ui/__init__.py` | package marker |
| `ui/server.py` | loopback-only HTTP server: reads state files, takes control POSTs, builds the review |
| `ui/index.html` | the whole page (inline CSS and JS, canvas chart of desk replay bars) |
| `ui/make_sample_state.py` | regenerates `ui/sample_state/` from `tvbot/fixtures/normal_bars.jsonl` (70 bars) |
| `ui/sample_state/` | v2-shaped sample: phase ARMED, preflight, schedule, refusal_checks on all 70 decisions |
| `tests/test_ui_server.py` | 31 tests |

## Run

```
cd nov14-sprint/tvbot/desk
/usr/bin/python3 -I -m unittest discover -s tests -p 'test_ui*'      # 31 tests, OK at 17:55Z
/usr/bin/python3 -I ui/server.py --state-dir ui/sample_state --port 8781   # sample view
/usr/bin/python3 -I launch.py --no-browser --fresh --state-dir <dir> --port 8783   # real controller
```

## Entry points

- `serve(state_dir, host="127.0.0.1", port=8765, controller=None)` (CONTRACT v2).
- `make_server(state_dir, host, port, controller=None, verbose=False, manager=None)`. `manager=` is an alias for `controller=` (launch.py passes `manager=`). Non-loopback hosts raise ValueError; a foreign Host header gets 403.

## API

GET: `/`, `/api/health` (lists routes), `/api/session`, `/api/bars` (only bars with `ts_close <= replay_clock_utc`), `/api/decisions` (outcome hidden until `?reveal=<id>`), `/api/ledger`, `/api/audit`, `/api/review` (`?reveal_pass=1` adds the hypothetical path), `/api/control_requests`.

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

Every POST appends `{ts, action, body, request_id, ...}` to `state_dir/control_requests.jsonl` with fsync **before** the controller is called, then a second line with `status` (`controller_ok`, `controller_refused`, `controller_error`, `controller_missing_method`). The reply is `{ok, session, controller_called, error, simulated:true, ...}`. A controller result of `{"ok": false, "reason": X}` returns `ok:false, error:X` (HTTP 200). Missing confirm, a bad body or a cross-origin request return 4xx and call nothing.

## What was verified

- 31/31 UI tests: all nine routes with arguments, request line written before the call, play 0, caps, confirm refusal, controller refusal, no-argument fallbacks (DeskControls shape), missing method, bars clock filter, best pass and reveal hiding, CSP, page labels.
- Live, through `launch.py` on port 8783 (DeskControls on a real SessionController, scratch state): arm, advance 3, pause, resume, schedule on/off, Stop & Close without confirm (refused), with confirm (STOPPED), clear_stop (PRE_SESSION), close_session (CLOSED). Every call returned ok with the phase expected.
- Browser, sample state and live state, at desktop and 900px: no console errors, no horizontal scroll, no iframe and no external script loaded (TradingView toggle left off). Flow buttons enable by phase. Best pass shows trend_filter_down (2 of 8 refusal checks failed), and its hypothetical path appears only after Reveal, labeled never in P&L.

## Fixed in this pass

- Expiry is judged on the replay clock: session.py writes `expires_utc` on the simulated clock, so wall-clock comparison showed SESSION EXPIRED and would have blocked re-Arm after Clear Stop.
- The review's broker row read "NOT CONNECTED" because v2 has no `connected` field. It now reads "OFFLINE (in-process fake)" when `external` is false.
- Moved legacy-hook stray files (`.claude-compact-*.md`, `self-learning/`) out of `ui/` so they are not published.

## Gaps and notes for the coordinator

1. **Desk suite has failures outside ui/** (17:54Z run of all tests: 144 tests, 38 errors). 33 are in `test_orders_manager` (`max_loss_per_trade` is None in its LIMITS). 5 are in `test_integration` (`fake_broker._fill_price()` takes 3 positional args but gets 4, via `session.advance`). Neither file is mine. UI tests pass.
2. My routes take precedence over launch.py's `advance`, `play`, `clear_stop` and `close_session`, because `install_routes` skips existing routes. That works with DeskControls (tested live). One difference: `/api/clear_stop` needs `{confirm:true}`, which the page sends.
3. `play(0)`: launch.py treats 0 as the default 4 bars/s. The UI maps 0 to `stop_play`, then `pause_play`, per CONTRACT v2.
4. There is no "playing" flag in session.json, so Play and Stop playing are both enabled while ARMED. A `playing: bool` field would let the page show which one is active.
5. Port 8765 is also the pokemon-viewer port in `.claude/launch.json`; launch.py's `free_port` avoids the clash.
6. The TradingView embed (official Advanced Chart widget, off by default, CSP-allowed) was not exercised, because verification stays offline. The "Open my TradingView chart" link is plain and opens in the user's browser.
7. The comparison table adds a cash row (0 trades, $0) when the session's review has none.
8. The stale banner ("runner has not written state for N min") appears on the static sample by design; it hides once a runner writes state.
