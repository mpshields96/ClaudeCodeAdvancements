# Alpaca mock-mode QA (W3), 2026-11-15, about 22:30-22:55Z

**What this proves:** the operator path through the real launcher and UI against the in-process mock (`--transport mock`). Every id and bar is synthetic, and the mock clock advances one bar per manual Check.

**What this does not prove:** anything about a real Alpaca account.
- No network host was contacted. The only socket was the loopback UI port.
- No credential, environment variable or Keychain item was read.
- The first authenticated paper smoke test stays with Matthew, after he sets his own limits.

**How it was run:**
- Command: `/usr/bin/python3 -IB launch.py --broker alpaca-paper --transport mock --state-dir <scratch>/qaN --port <p> --no-browser`, with state dirs under the session scratchpad, not the repo.
- Buttons were pressed in the built-in browser for Enable, the first Check, Arm, Stop & Close and its confirm dialog.
- Repeated Checks were sent to the same loopback routes the buttons call (`POST /api/advance {"n":1}`, `/api/arm`, `/api/alpaca/enable {"confirm":true}`). That gives the same controller path and request-id audit trail as the buttons.
- The UI's 2-second refresh is a local file read of `session.json` and friends. It is not a broker poll, and nothing runs between operator actions.

## Results

| # | Brief item | Result | Evidence |
|---|---|---|---|
| 1 | Enable | **PASS** | The dialog showed mode `alpaca-mock`, MOCK LOCAL, and the limits label "MOCK WALKTHROUGH TEST VALUE: fixed 1 share(s); not Matthew's sizing". The adapter went `enabled:true` (`ui-alpaca_enable-1e2d706100` in run qa2, `ui-alpaca_enable-2e9d0d8f0a` in run qa3). |
| 2 | Arm and preflight | **PASS, with a defect** | All preflight rows OK: adapter, recovery, broker reconciled, limits loaded, calendar 2026-11-16 open, mock clock skew 0s, warm-up, no stop. **Defect A:** arming *before* the first Check gets undone by the warm start (details below). With Check first, then Arm, the session stays ARMED (`ui-arm-2b6beeb511`, qa3). |
| 3 | Strategy submit | **PASS** | qa3 18:30Z bar: entry intent qty 1 at a limit near 500.34, acked `mock-ord-0001`. Next Check: filled 1 at 500.31. The chart shows POSITION LONG 1 sh. Qty comes from the session's `sizing.fixed_qty`. |
| 4 | Protective stop | **FAIL (defect B)** | Both runs: protective sell stop at `stop=492.839825` was rejected with `BAD_PRICE` by `alpaca/broker.py` (stop price must sit on the $0.01 tick). The position was open with no protective order. The UI showed "NONE while a position is open" in red, which is correct for the state. |
| 5 | Partial fill | **NOT EXERCISED in the UI** | The launcher exposes no partial-fill switch, and the mock walkthrough sizing is 1 share, so a partial fill is impossible here. Covered only by W1's unit test `tests/test_alpaca_broker.py::test_partial_fills_across_restart_no_double_booking` (`mock.partial_next = 1`), which passed in the full suite (362 OK). |
| 6 | Stop & Close with an open position | **PASS** | qa3: browser Stop & Close, then confirm (`ui-stop_close-fef5d928f7`). Results: phase STOPPED, armed false, adapter `enabled:false` with reason `STOP: OPERATOR`. The close order was acked `mock-ord-0002`, and `flat_confirmed` stayed **false** until the broker said 0, so there was no premature FLAT. The next manual Check (`ui-advance-78e3a50b4d`) filled the close 1 at 500.145, then `flat_confirmed:true` with broker position 0. |
| 7 | Restart shows disabled | **PASS** | qa3 was restarted after Stop. `/api/session`, `alpaca_paper.json` and the UI banner all read **"Adapter: DISABLED (STOP: OPERATOR)"**, with the history showing the enable then the desk Stop. Enable is the only way back on. |
| 7b | Restart without a Stop | **As designed** | qa2 was restarted while enabled and flat. The adapter stays enabled (`alpaca/state.py`: it stays as the operator left it), and the session is not armed (phase CLOSED). Arming is never carried across a restart. |
| 8 | Restart recovery in mock | **Defect C** | After any restart, reconcile raised blocking `ORDER_MISSING` alarms: "acknowledged order ... (filled) is gone from the broker". The banner then shows "RECOVERY AMBIGUOUS ... Enable refused until Reconcile clears it". Positions matched (booked 0, broker 0). The in-process mock starts empty on restart, while `alpaca_broker.json` remembers the acked ids. |
| 9 | Session end | **PASS** | qa2: the exit filled 1 at 500.035. At 21:00Z the session closed flat and disarmed (`SESSION_END`). Later days sat in PRE_SESSION with no auto-arm. When the mock data ran out (2026-11-23), Checks returned 0 bars and nothing else happened. |

## Defects for owners (not W3 files)

- **A. Arm before the first Check is silently undone.** Owner: coordinator, `alpaca_session.py`.
  - The warm start replays prior-day bars through `_step_one`. `_session_roles` then sees a "last" bar and calls `mgr.disarm(SESSION_END)`.
  - Evidence (qa2): `audit.jsonl` arm, then disarm SESSION_END, and the badge went to DISARMED right after the operator armed.
  - Fix idea: skip session roles for warm-up or catch-up bars older than the armed session day. Or refuse Arm until warm-up has run once.
  - Workaround: press Check once, then Arm.
- **B. Protective stop off-tick, rejected `BAD_PRICE`.** Owner: W1 (`broker.py`) or whoever builds the protective intent.
  - The stop comes through unrounded (`492.839825`). `submit()` rounds limit prices to the safe side of the tick but rejects stop prices that are off tick.
  - Fix idea: round the stop toward the safe side, as limits already are. That means up for a sell stop and down for a buy stop. Or round where the protective intent is built.
  - Until fixed, every paper position runs without a broker-side stop.
- **C. Mock restart gives a false ORDER_MISSING.** Owner: W1 (`mock.py`) or the coordinator.
  - The in-process mock forgets closed orders across a restart.
  - Real Alpaca keeps closed orders, so paper mode should find them. The real path still has not been run.
  - Fix idea: persist the mock's order book in the state dir, or have reconcile treat a filled, already-booked order on a flat book as resolved.

## UI fixes made during this QA (W3 files)

- `ui/server.py`: `/api/bars` now reads `alpaca_bars.jsonl` in Alpaca modes, with a source line naming the file. Before, the chart was empty in Alpaca mode. New tests are in `TestAlpacaBarsFile`.
- `ui/index.html` changes:
  - The mode line reads ALPACA MOCK or ALPACA PAPER instead of the inherited "REPLAY".
  - The risk line shows "Shares N" from the session's sizing.
  - The empty-chart text names the right file.
  - A new `renderModeLabels()` runs on every tab and sets these by mode:
    - the chart source tag (it was stale on non-chart tabs after a reload)
    - the Arm button text and title (was "Arm this replay session (offline)")
    - the Stop dialog note (was "in-process FakeBroker"; it now says Stop turns the adapter off and it stays off after a restart)
    - the pre-session dialog note
    - the Mode row
- Checks: `node --check` on the page script passes, and the full desk suite passes (`/usr/bin/python3 -IB -m unittest discover -s tests`: 362 tests OK at about 22:52Z).

## Wording notes

- The button now reads "Check for new bars" in Alpaca modes (it read "Check for new closed bar" during this QA), matching the docs. Same action.
- `session.json` still carries the base `mode: "REPLAY (OFFLINE, SIMULATED)"` in Alpaca modes. The UI overrides it from `broker_mode`. The coordinator may want to set `mode` properly for other readers, such as the weekly report.

Sources consulted for the security posture (docs only, no calls):
- [Alpaca key security guide](https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders)
- [Nexla Alpaca connector doc](https://docs.nexla.com/user-guides/connectors/alpaca_api)
