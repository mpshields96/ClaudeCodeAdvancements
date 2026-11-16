# Live readiness (Alpaca, real money)

Written 2026-11-16 by night worker W-B. It covers software only. No agent has sent any paper or live
request, read any key or placed any order. Every check below ran against an in-process fake
(FakeOpener / MockTrading) with synthetic keys.

**Bottom line:** real-money trading is **off and cannot be switched on by any flag, URL or argument
on the paper path**. A separate live command exists. It checks your limits and your typed
confirmation and then **stops (exit 3)** without sending anything, because the live session controller
is not wired yet. The live broker class (`AlpacaLiveBroker`) exists and is tested offline, but no launcher
builds it. Nothing here shows the strategy has an edge.

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
| Broker object | `AlpacaPaperBroker` refuses any live transport, the live label and live adapter state (ValueError) | `AlpacaLiveBroker`: only the real (non-injected) `LiveHttpsTransport` with an unexpired authorization, only the live label, only the folder the gate authorized. Records say `simulated: false`. No launcher builds it yet (section 4) |
| On/off state | `alpaca_paper.json` | `alpaca_live.json` (`LiveAdapterState`), so a live folder never gains the paper file the gate refuses |

The `AK`/`PK` prefix is only a hint. The host check and the separate providers are the real boundary.

## 3. Verified offline only

All tests are in `tests/test_alpaca_live.py` (54 tests). They use a fake opener, so they show the
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
| Limits swapped or re-approved while the confirmation prompt is open are refused; the authorization carries the exact snapshot you were shown, so a controller never re-reads the file (Codex 02:40Z finding) | `test_start_refuses_limits_swapped_during_the_prompt`, `test_limits_reapproved_after_they_were_shown_are_refused`, `test_authorization_carries_the_shown_snapshot_not_a_later_file` |

| `AlpacaLiveBroker` refuses a paper, mock or injected transport, any non-live label, another folder, paper adapter state and an expired authorization | `test_refuses_a_paper_or_injected_transport`, `test_refuses_other_labels_other_folders_paper_state_and_expired_auth`, `test_paper_broker_refuses_the_live_label_and_live_state` |
| Live records say `simulated: false` with the live label; requests go to `api.alpaca.markets` only | `test_live_records_say_real_money_and_go_only_to_the_live_host` |
| On the live broker: one request per decision, and a restart re-sends nothing | `test_one_post_per_intent_and_restart_resends_nothing` |
| Live on/off state stays in `alpaca_live.json`; the next session's gate still passes; a stop by another writer is adopted before any send | `test_live_state_never_writes_the_paper_file_so_the_next_gate_still_passes`, `test_a_disable_by_another_writer_is_adopted_from_the_live_file` |

The `AlpacaLiveBroker` tests build the real live transport class and then swap its opener for the fake
one, with sockets and the Keychain reader disabled. Four mutation checks (records marked simulated, the
paper file re-read, the paper file written, an injected transport accepted) each made a test fail.

The rehearsal uses a test-only subclass that lets the paper broker's order logic run over the live
transport. Production code never sets that flag.

## 4. Needs your own first broker test (agents will not do these)

1. **Store your live keys** in Keychain under service `alpaca-live`. Agents never handle keys.
2. **Wire the live session.** `alpaca_session.py` (coordinator-owned) labels every Alpaca session as
   paper and keeps paper state, so the gate stops at exit 3. The broker side is ready
   (`AlpacaLiveBroker`, `LiveAdapterState`). The suggested controller change is in the coordinator's
   shared notes (`W-B_LIVE_WIRING_PATCH_NOTE.md`). It needs review before anyone uses it.
   The live adapter starts disabled, as paper does; you enable it yourself.
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
