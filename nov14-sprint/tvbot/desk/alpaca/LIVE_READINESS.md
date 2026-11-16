# Live readiness (Alpaca, real money)

Written 2026-11-16 by night worker W-B. It covers software only. No agent has sent any paper or live
request, read any key or placed any order. Every check below ran against an in-process fake
(FakeOpener / MockTrading) with synthetic keys.

**Bottom line:** real-money trading is **off and cannot be switched on by any flag, URL or argument
on the paper path**. A separate live command exists. It checks your limits and your typed
confirmation and then **stops (exit 3)** without sending anything, because the live session controller
is not wired yet. Nothing here shows the strategy has an edge.

## 1. What you can run now

| Command (from `desk/`) | What it does | Touches the broker? |
|---|---|---|
| `/usr/bin/python3 -I launch.py --check` | The paper desk's offline self-check (unchanged) | No |
| `/usr/bin/python3 -I alpaca/live_launch.py approve-limits --draft-from MY_LIVE_LIMITS.json` | Saves **your** live limits (`fixed_shares`, `max_loss_per_trade`, `daily_loss`, `per_trade_notional`, `gross_exposure`) into `state-alpaca-live/`. You must type `APPROVE LIVE LIMITS` and a one-line reason at a real terminal | No |
| `/usr/bin/python3 -I alpaca/live_launch.py start --limits state-alpaca-live/limits_approved.json` | Runs the whole live gate, asks you to type `LIVE SPY <shares> SHARES <today's Chicago date>`, then prints `LIVE GATE PASSED ... Nothing was sent` and exits 3 | No (no key read, no socket) |
| `/usr/bin/python3 -I alpaca/live_launch.py start` | No limits, so it is refused: exit 2, `REFUSED (live): ... Nothing was sent; no key was read; no connection was opened.` | No |

Exit codes for `live_launch.py`: 0 limits saved, 2 refused (nothing sent), 3 gate passed but live
session not wired.

## 2. How live is kept apart from paper

| Boundary | Paper | Live |
|---|---|---|
| Command | `launch.py` (choices `offline`, `alpaca-paper` only) | `alpaca/live_launch.py` only |
| Trading host | `https://paper-api.alpaca.markets` | `https://api.alpaca.markets`, fixed at import; an edited origin is refused |
| Key names | Keychain `alpaca-paper`, env `APCA_*` | Keychain `alpaca-live`, env `ALPACA_LIVE_API_KEY_ID` / `ALPACA_LIVE_API_SECRET_KEY` |
| Key shape | A key id starting `AK` (live style) is refused before sending | A key id starting `PK` (paper style) is refused before sending |
| Provider | Paper providers refuse the live names | Live providers never read the paper names |
| State folder | `state/`, `state-alpaca-paper/`, `state-alpaca-mock/` | must be named `state-alpaca-live/` and must not hold paper adapter state |
| Port | 8765 | 8795; 8765 is refused |
| Limits | paper approval | separate approval by the live command, stored inside the live folder; a paper-approved or edited file is refused |
| Confirmation | none | typed every session at a real terminal (piped input refused); yesterday's phrase or a different share count is refused; the authorization lapses after 16 hours |
| Broker object | `AlpacaPaperBroker` refuses any live transport (ValueError) | not built yet (see section 4) |

The `AK`/`PK` prefix is only a hint. The host check and the separate providers are the real boundary.

## 3. Verified offline only

All tests are in `tests/test_alpaca_live.py` (43 tests). They use a fake opener, so they show the
code's behaviour, not Alpaca's.

| Protection | Evidence on the live request path |
|---|---|
| One order request per decision; a repeated decision id sends nothing new | `test_one_post_per_intent_and_duplicate_decision_ignored` |
| A lost acknowledgment is found by query, not re-sent | `test_lost_ack_adopted_by_query_not_resent` |
| After a restart the desk rebuilds from the venue and re-sends nothing | `test_restart_reconciles_from_the_venue_without_resending` |
| Notional, per-trade loss and gross exposure caps refuse **before** any request | `test_caps_refuse_before_any_send` |
| Stop & Close cancels the protective stop, sends one market close and confirms flat | `test_stop_and_close_cancels_protection_then_closes_flat` |
| A stale bar (901 s with a 900 s window) blocks entries with `BAR_STALE_EXCHANGE_TS` | `test_window_900_refuses_a_901s_bar_and_blocks_entries` |
| The manager uses its own freshness window (the 23:11Z finding, now at `on_bar` level) | `test_window_900_accepts_a_61s_bar_default_5_refuses_it` |
| Every request goes to `api.alpaca.markets` only | `assert_live_host_only` in each rehearsal test |
| Records made in rehearsal still say `simulated`, so they cannot pass for live evidence | `test_records_still_say_simulated_so_this_cannot_pass_for_live_evidence` |
| Every gate refusal happens with sockets and the Keychain reader disabled | `LiveGateTests` (uses `NoNetworkNoKeys`) and a real subprocess run |

The rehearsal uses a test-only subclass that lets the paper broker's order logic run over the live
transport. Production code never sets that flag.

## 4. Needs your own first broker test (agents will not do these)

1. **Store your live keys** in Keychain under service `alpaca-live`. Agents never handle keys.
2. **Wire the live session.** `alpaca_session.py` (coordinator-owned) labels every Alpaca session as
   paper and keeps paper state, so the gate stops at exit 3. The suggested change is in the
   coordinator's shared notes (`W-B_LIVE_WIRING_PATCH_NOTE.md`). It needs review before anyone uses it.
3. **Set every limit yourself.** The values in the tests are TEST VALUES, not advice.
4. **Your first live order**, at a size you choose, while you watch. Check fills, the protective stop
   and Stop & Close against your Alpaca dashboard.
5. **Account checks only you can do:** live trading enabled, buying power, and day-trading rules such as
   FINRA's pattern-day-trader rule for margin accounts under $25,000 (not checked tonight).

## 5. Sessions

From Alpaca's documentation (24/5 Trading, Orders at Alpaca):

| Session (Eastern) | What the desk does |
|---|---|
| Regular 09:30-16:00, NYSE calendar with holidays and early closes | Supported |
| Pre-market 04:00-09:30 | Labeled NOT supported; bars refused (`OUT_OF_SESSION`) |
| After-hours 16:00-20:00 | Labeled NOT supported; bars refused |
| Overnight 20:00 Sun to 04:00 Fri (limit orders only, Blue Ocean ATS) | Labeled NOT supported, never traded silently |
| Weekends, holidays | Closed |

The desk never sends `extended_hours`, and uses day orders only. Per Alpaca's documentation, a day order
sent outside regular hours waits for the next regular session. The desk does not send new entries then.
The UI can show `session_window` (from `alpaca/sessions.py: status_field`).

## 6. Known limits

- **No edge has been shown.** Paper or rehearsal results say nothing about live profit.
- The live session is not wired (section 4, item 2).
- The calendar covers 2026-2027. Outside it, the desk fails closed (market treated as closed).
- Holiday changes to the overnight session are not modeled; overnight is refused anyway.
- The free IEX feed shows a fraction of market volume, so its prices can differ from the full market.
  Whether the free feed covers extended or overnight hours, and whether paper accounts support overnight,
  came from a Gemini summary and are **unverified**. The desk does not rely on either.
- The confirmation date is Chicago time. If you type it across midnight, the gate refuses, so retype.
