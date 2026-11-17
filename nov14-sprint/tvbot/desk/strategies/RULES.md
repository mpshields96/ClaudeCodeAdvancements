# Desk strategy rules (frozen before results)

Frozen 2026-11-15 ~17:25Z by worker C, before `research.py` ran and before
`holdout_bars.jsonl` was opened by any strategy code here. The only output
seen before this file was a smoke test on `fixtures/normal_bars.jsonl`,
which confirmed that the code imports and runs. No rule or parameter was
changed after that test.

All of this is paper and offline. Every number is simulated. TradingView
data never enters a decision, order or ledger.

Code: `engine.py` (replay), `base.py` (Decision, costs, session clock),
`registry.py` (desk entry point). Rule ids, which are hashes of the
parameters:

| Strategy | Rule id |
|---|---|
| `ema` | `EMAX-1.0.0-14251ac3` |
| `gold_basket` (desk) | `CHOCH-GOLD_BASKET-1.0.0-baba554b` |
| `cash` | `CASH-1.0.0` |

The other gold strategies print their own ids through `engine.rule_id`.

## 1. Common mechanics (all strategies)

1. **Decision time.** A decision is made at a bar's close using only bars
   with `ts_close <= now`. Its `ts_knowable` is the later of `ts_close` and
   `delivered_ts`, so a late-delivered bar is not used before it arrived.
2. **Fills.** An order fills at the next bar's open. Research can add a
   delay. A bar with zero volume never fills: an entry that meets one is
   dropped, and an exit waits for the next bar. Only one order works at a
   time. While it works, the strategy says `ORDER_WORKING`.
3. **Costs.** The cost assumptions are mirrored from the
   `tvbot/bot/engine.py` defaults:
   - a half spread of 1.0 bps plus slippage of 2.0 bps against us on each
     side;
   - a commission of $0.005 a share, with a $1.00 minimum per order.

   These are assumptions, not broker quotes. A gold spot replay uses a
   per-ounce bid model instead: buying pays bid + $0.30 spread + $0.05
   slippage, and selling gets bid − $0.05. Those are Codex's preregistered
   base costs.
4. **Size.** One base leg is `floor(order_notional / decision close)`
   whole units, with `order_notional` = 2000 taken from
   `tvbot/config/smaller_size.json`. These are **TEST VALUES**, and the
   strategies never tune them. If the result is zero units, the strategy
   passes with `ZERO_SIZE`.
5. **Desk sessions end flat.**
   - No entries at or after the close of the session's second-to-last bar.
     The refusal code is `NEAR_CLOSE`.
   - At that close, any position is exited (`SESSION_FLAT`) and fills at
     the final bar's open.
   - A position that is still open at the final bar's close is exited as
     `OVERNIGHT_RESIDUAL` at the next open, which carries gap risk.
   - The session schedule comes from cfg `session_tz` (default `UTC`) and
     `session_close` (default `21:30`, the SYNTH-FUND-60M fixture's last
     close).
   - Overnight holding exists only in research (`ema_overnight`).
6. **Real position.** The registry caps an exit at the desk's real position
   and turns an exit into a pass (`NOTHING_TO_EXIT`) when the real position
   is 0.
7. **Escalation is research-only.** The registry forces
   `research_escalation` off, so every desk leg is exactly one TEST-size
   base leg.

## 2. Swing confirmation: change of character (frozen)

This follows Codex's preregistered reading of the secondhand Reddit capture
(`nov14-sprint/codex/REDDIT_ai_trading_Y4g3W8rErU_CAPTURE.md`, via Codex
relay, not read by Claude), with SWING = 6.

- **Pivot high** at bar c: `high[c]` is strictly greater than the high of
  each of the 6 bars before it and the 6 bars after it. **Pivot low** is
  the same with lows, strictly lower.
- **First knowable timestamp.** A pivot at bar c is first knowable at the
  close of bar c+6, the sixth bar after it. It is never used earlier.
- The most recent confirmed pivot high and pivot low are the live levels.
  A newer pivot replaces an older one of the same kind.
- **Break.** A close strictly above the live pivot high is an up break. A
  close strictly below the live pivot low is a down break. A broken level
  is consumed and can never signal again.
- **Both on one bar.** If a single close breaks both levels, both are
  consumed and there is no signal (`BOTH_BROKEN_SAME_BAR`).
- **Entry and exit timing.** A break at bar t's close is the signal. The
  leg fills at bar t+1's open.
- **Hourly bars.** A 13-bar pivot window cannot fit inside a 7-bar session,
  so the desk rule chains pivots across the scheduled overnight break
  (`reset_pivots_each_session = False`). It still forces flat at each
  session end. Codex's 5-minute gold replay reset pivots every session.
  That reset is a declared research variant here, not the desk rule.

## 3. Strategies

### `gold_basket`: the Reddit gold idea

- **Add-on rule.** The post is ambiguous about whether to add on repeated
  or alternating signals. The frozen reading adds a leg on **every** break,
  in the break's direction, whether it repeats the last leg's direction or
  reverses it. The leg cap is 3 per basket.
- The alternating-only reading is the research variant `gold_alternating`.
  It adds only when the break reverses the last leg.
- **Netting.** All legs net into **one signed position**:
  - Same-direction fills update a volume-weighted average fill price.
  - An opposite leg reduces the position at the fill price and realizes
    P&L on the part it closes. In the desk this is an `exit` of the leg's
    size, with reason `BASKET_REVERSE_LEG`.
  - A leg larger than the net position flips it, with the average reset to
    the fill price. This can only happen with research escalation.
  - When the net position returns to 0, the basket closes, and the next
    break starts a new one.
- **Position-level exits** use the basket's P&L: cash flow since the
  basket opened, plus the liquidation value of the net position at the
  decision close after spread, slippage and the estimated exit commission.
  - At or above **+$3.00**, exit everything (`BASKET_TARGET`).
  - At or below **−$6.00**, exit everything (`BASKET_STOP`).
  - These are strategy-rule parameters frozen from Codex's preregistration.
    They are not Matthew's account limits.
  - They are checked only at bar closes, so one bar can move far past the
    stop. That is gap and jump risk, and it is reported, not hidden.
  - An exit takes priority. A break on a bar that triggers an exit is not
    acted on.
- **Escalation.** Research only: leg n is base × 2^(n−1), so 1/2/4. Desk:
  every leg is base size, which makes the desk `gold_basket` behave like
  `bounded_fixed`. That is stated plainly rather than hidden.

### `fixed_risk_single`

One base leg on a break, and only when flat. Other breaks are ignored while
in (`SINGLE_ALREADY_IN`). It uses the same +$3 / −$6 exits and the
session-flat rule.

### `bounded_fixed`

The same as `gold_basket`, but every leg is always one base leg (1/1/1),
including in research. The cap is 3 and the exits are the same.

### `ema`: the existing EMAX-1.0.0 rule

The rule is mirrored read-only by importing `tvbot/bot/rules.py`, which
this worker does not edit. The averages are an 8-bar fast and a 21-bar
slow EMA, seeded with the first close, with 63 warm-up bars.

- **Entry:** long only, at the next open after a cross-up.
- **Exit:** at the next open after either a close at or below 1.5% under
  the entry open (`STOP`, checked first) or a cross-down.
- **Desk addition:** the session-flat rule.
- **Research variant:** `ema_overnight` is EMAX exactly as frozen, with no
  session flat.

EMAX's registry shows its holdout was already claimed on
2026-11-14T22:17:06Z. Its holdout result here is therefore not a first
look.

### `cash`

Always `pass` with `CASH_ALWAYS_PASSES`. Its result is $0, and a $0 day is
a valid outcome.

## 4. Refusal tests (`refusal_checks`, `passed = true` means not blocked)

| Strategy | Tests in order |
|---|---|
| all | `NO_BARS`; `ORDER_WORKING`; `OUTSIDE_SESSION`; `NEAR_CLOSE`; registry `NOTHING_TO_EXIT` |
| gold kinds | `NO_SIGNAL` (including `BOTH_BROKEN_SAME_BAR`); `SINGLE_ALREADY_IN`/`LEG_CAP`; `ALTERNATING_ONLY` (variant); `ZERO_SIZE`; `COST_EXCEEDS_EDGE`; `NO_STOP`/`MAX_LOSS_WOULD_BREACH` (entries and flips, not reverse-leg exits) |
| ema | `NO_SIGNAL` (also while holding); `WARMUP`; `ZERO_SIZE`; `NO_STOP`/`MAX_LOSS_WOULD_BREACH` |
| cash | `CASH_BASELINE` (always false) |

`COST_EXCEEDS_EDGE` refuses a gold leg when its estimated round-trip cost
is at least the $6 basket stop, because the leg would start at its stop.

`MAX_LOSS_WOULD_BREACH` (added 2026-11-15 ~17:42Z for desk CONTRACT v2,
after the holdout claim, so the rule hash changed) mirrors the desk's
plain-dollar cap: price risk to the stop, qty × |intended_entry − invalidation|,
must be at most `max_loss_per_trade`. Under the operator rule the
estimated round-trip cost is not part of this cap; it is counted
against the daily loss cap in the order manager. The cap is read from
`cfg["limits"]["max_loss_per_trade"]` (or `cfg["max_loss_per_trade"]`), a
TEST VALUE the desk passes in ($10 in CONTRACT.md). The strategy refuses;
it never shrinks the TEST size to fit. With no cap in cfg the check passes
with a note and the order manager enforces its cap. `NO_STOP` refuses an
entry with no stop price (none occur by rule). Research runs pass no cap,
so research results are unchanged by this test.

Purity: `decide(bars_so_far, position, cfg)` depends only on its inputs.
The registry's incremental cache continues only when every earlier bar is
identical in every field to a snapshot from the earlier call; a corrected,
removed or edited bar forces a cold replay, and the returned Decision is a
copy.

## 5. XAUUSD spot to US instruments (research translation only)

| | XAUUSD spot (Codex replay) | GLD (ETF) | 1OZ (1-ounce gold futures) | MGC (COMEX Micro Gold) |
|---|---|---|---|---|
| Unit | 1 troy oz | 1 share ≈ 1/10 oz less fees [UNVERIFIED] | 1 oz per contract [UNVERIFIED; named in the build prompt only] | 10 oz per contract, $10 per $1/oz (tvbot/feasibility/TV_FEASIBILITY.md) |
| Base leg vs the prereg 1 oz | 1 | about 10 shares [UNVERIFIED] | 1 [UNVERIFIED] | 0.1, which is impossible: the minimum is 10 oz, 10× the base |
| Hours | about 23h on weekdays | US equity session; overnight gaps against spot | futures hours [UNVERIFIED] | about 23h with a daily break [UNVERIFIED] |
| Costs | bid/ask + $0.05 slippage per oz | equity spread + commission | futures commission + spread [UNVERIFIED] | $0.09–0.75 per side commission range (TV_FEASIBILITY.md) + spread |

- US retail access to spot gold (OANDA US) is not available, per
  TV_FEASIBILITY.md.
- The $3/$6 basket thresholds were set for 1 oz. With TEST notional $2,000,
  a gold leg is `floor(2000 / price)`. At any price above $2,000 an ounce
  that is 0 units, so the strategy passes `ZERO_SIZE`. Changing that is
  Matthew's sizing call.
- Prop-firm notes from TV_FEASIBILITY.md: Top One Trader bans martingale,
  and Topstep counts real-time open losses. The escalating basket is
  martingale-like.
- The figure from Codex's private 2023 replay (−$104.78 on 127 complete
  sessions; causal run −$137.17) is historical spot bid/ask. It is not a
  broker fill and not a US-instrument result.

## 6. Research declaration (fixed before running)

- **Data.** `tvbot/fixtures/normal_bars.jsonl` (90 sessions) and
  `holdout_bars.jsonl` (30 sessions), both synthetic SYNTH-FUND-60M.
  Results are labeled **HARNESS EVIDENCE (SYNTHETIC)**, and nothing from
  them is evidence about gold or any market.
- **Candidate:** `gold_basket` with research escalation 1/2/4.
  **Baseline:** `cash`. **Comparators:** `fixed_risk_single`,
  `bounded_fixed`, `ema` (desk, session-flat), `ema_overnight`,
  `gold_alternating`, and `gold_basket` with per-session pivot reset.
- **Metric:** mean daily net USD after base costs, counting every session,
  including $0 sessions. Avoided losses never count as profit.
- **Walk-forward.** The rules are frozen with no refit, so the folds are
  chronological, sequential evaluation windows:
  - F1 = sessions 1–30
  - F2 = sessions 31–60
  - F3 = sessions 61–90 of `normal_bars`

  The untouched final period is the whole of `holdout_bars`, claimed once
  in `desk/out/research/HOLDOUT_CLAIM.json` together with the rule-set
  hash. A changed rule hash refuses the holdout.
- **Stress scenarios** (variant count grows with each):
  - base costs
  - zero commission
  - costs × 2
  - costs × 3
  - fills one bar late
  - every 5th entry missed
  - entries half-filled (partial)
- **Path checks from every start session:**
  - Worst intrabar marks: longs at the low and shorts at the high.
  - Maximum drawdown.
  - Margin breach on a $10,000 research reference balance. That is Codex's
    research assumption, not Matthew's limit. A breach is gross exposure
    above 2× equity, or equity below 25% of gross (a Reg-T-style
    assumption).
  - Barrier hits at −6% and +10% of the reference balance (the Reddit
    challenge numbers, as research assumptions).
- **Uncertainty.** Weekly-block bootstrap of daily net, 2000 resamples,
  with a fixed seed of 20261115.
- **Variant count.** Every strategy × scenario × data-split run is
  counted and reported.
- **Pass criterion, declared before running.** A strategy counts as "beats
  cash" only if all of these hold:
  - mean daily net > $0 on `normal_bars` overall and in each of F1, F2 and
    F3;
  - mean daily net > $0 on the holdout;
  - the bootstrap 5th percentile of the normal-period mean > $0;
  - mean daily net > $0 under costs × 2.

  Otherwise the honest answer is "does not beat cash", and $0 is a valid
  outcome.
- **Holdout replay.** `normal_bars` is replayed first as warm-up and is not
  scored. Then `holdout_bars` follows, with seq offset by 630, and only
  holdout sessions are scored. The two files are separate synthetic paths,
  so the junction is a price gap.
- **Unavailable path information.** Bars are hourly OHLC, so the order of
  high and low inside a bar is unknown. Fills are at the open; basket
  checks happen at closes. Intrabar marks are a worst case, not a path.
