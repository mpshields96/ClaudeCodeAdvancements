# Strategy research result: HARNESS EVIDENCE (SYNTHETIC)

Every number below is simulated, from synthetic fixture bars (SYNTH-FUND-60M). Nothing here is evidence about gold, GLD, MGC or any real market. Paper and offline only.

Generated 2026-11-15T17:30:02Z. Rule hash `d3056d25d4bae654`. Holdout evaluated: True (claim 2026-11-15T17:29:56Z).

Size: TEST VALUES, order_notional 2000.0 from tvbot/config/smaller_size.json (never tuned).

## Declared before running

- **candidate**: gold_basket_escalating (gold_basket with research escalation 1/2/4)
- **baseline**: cash ($0 every session)
- **metric**: mean daily net USD after costs, every session counted, $0 sessions included
- **walk_forward**: rules frozen, no refit: chronological evaluation windows F1=sessions 1-30, F2=31-60, F3=61-90 of normal_bars
- **untouched_final_period**: holdout_bars.jsonl (30 sessions), claimed once with the rule hash
- **pass_criterion**: mean > 0 overall and in F1, F2, F3; holdout mean > 0; bootstrap p05 > 0; costs x2 mean > 0. Otherwise 'does not beat cash'.

## Base costs: mean daily net USD (every session counted)

| Strategy | Normal (90) | F1 | F2 | F3 | Holdout (30) | Fills normal | Fees normal | Worst day | Boot p05..p95 | Beats cash |
|---|---|---|---|---|---|---|---|---|---|---|
| gold_basket_escalating | -1.00 | -2.90 | -0.11 | +0.00 | -0.69 | 8 | 12.74 | -96.23 | -3.14..+0.17 | no |
| cash | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | 0 | 0.00 | +0.00 | +0.00..+0.00 | no |
| fixed_risk_single | -1.00 | -2.90 | -0.11 | +0.00 | -0.69 | 8 | 12.74 | -96.23 | -3.14..+0.17 | no |
| bounded_fixed | -1.00 | -2.90 | -0.11 | +0.00 | -0.69 | 8 | 12.74 | -96.23 | -3.14..+0.17 | no |
| gold_alternating | -1.00 | -2.90 | -0.11 | +0.00 | -0.69 | 8 | 12.74 | -96.23 | -3.14..+0.17 | no |
| gold_basket_session_reset | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | 0 | 0.00 | +0.00 | +0.00..+0.00 | no |
| ema | +0.94 | +1.68 | +0.54 | +0.59 | -0.15 | 18 | 28.70 | -3.19 | +0.26..+1.69 | no |
| ema_overnight | +1.57 | -2.32 | +4.45 | +2.59 | +0.25 | 21 | 33.50 | -50.68 | -1.63..+4.85 | no |

## Totals (USD, simulated)

| Strategy | Normal total | Holdout total | Sessions with fills (normal) | Zero sessions (normal) |
|---|---|---|---|---|
| gold_basket_escalating | -90.33 | -20.70 | 4 | 86 |
| cash | +0.00 | +0.00 | 0 | 90 |
| fixed_risk_single | -90.33 | -20.70 | 4 | 86 |
| bounded_fixed | -90.33 | -20.70 | 4 | 86 |
| gold_alternating | -90.33 | -20.70 | 4 | 86 |
| gold_basket_session_reset | +0.00 | +0.00 | 0 | 90 |
| ema | +84.18 | -4.59 | 9 | 81 |
| ema_overnight | +141.53 | +7.62 | 18 | 47 |

## Stress: normal-period mean daily net USD

| Strategy | base | zero_commission | costs_x2 | costs_x3 | delay_1_bar | miss_every_5th_entry | partial_half |
|---|---|---|---|---|---|---|---|
| gold_basket_escalating | -1.00 | -0.91 | +0.00 | +0.00 | +0.33 | -1.00 | -0.46 |
| cash | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| fixed_risk_single | -1.00 | -0.91 | +0.00 | +0.00 | +0.33 | -1.00 | -0.46 |
| bounded_fixed | -1.00 | -0.91 | +0.00 | +0.00 | +0.33 | -1.00 | -0.46 |
| gold_alternating | -1.00 | -0.91 | +0.00 | +0.00 | +0.33 | -1.00 | -0.46 |
| gold_basket_session_reset | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| ema | +0.94 | +1.14 | +0.62 | +0.30 | +0.93 | +0.97 | +0.36 |
| ema_overnight | +1.57 | +1.82 | +1.18 | +0.79 | +0.49 | +1.07 | +0.69 |

## Paths from every start session (normal, base costs, $10,000 research reference)

| Strategy | Starts | Worst max DD | Median max DD | Margin breaches | -6% first | +10% first | Neither |
|---|---|---|---|---|---|---|---|
| gold_basket_escalating | 90 | 99.92 | 0.00 | 0 | 0 | 0 | 90 |
| cash | 90 | 0.00 | 0.00 | 0 | 0 | 0 | 90 |
| fixed_risk_single | 90 | 99.92 | 0.00 | 0 | 0 | 0 | 90 |
| bounded_fixed | 90 | 99.92 | 0.00 | 0 | 0 | 0 | 90 |
| gold_alternating | 90 | 99.92 | 0.00 | 0 | 0 | 0 | 90 |
| gold_basket_session_reset | 90 | 0.00 | 0.00 | 0 | 0 | 0 | 90 |
| ema | 90 | 12.33 | 6.59 | 0 | 0 | 0 | 90 |
| ema_overnight | 90 | 199.50 | 39.18 | 0 | 0 | 0 | 90 |

## Variant count

8 rule variants x 7 cost/fill scenarios; 112 evaluated configurations (normal + holdout) and 720 every-start replays. Choosing the best of these after the fact overstates it; the candidate was declared first.

## Historical-spot comparison (not broker fills)

Codex private 2023 XAUUSD spot replay of the Reddit gold basket (escalating legs, +$3/-$6): net -104.78 USD over 127 sessions; causal replay -137.17 USD. 627 modeled fills; worst basket mark -$8.93; max net notional $13,587.32; with $10k and 100% collateral, short of capital on 3 entry days. Basis: historical spot bid/ask quotes with Codex's fee/slip assumptions; not broker fills, not a US-instrument result, private data not used or published here. Sources: nov14-sprint/codex/SUPERVISOR_1631Z.md, nov14-sprint/tvbot/desk/CONTRACT.md.

## Limits

- Hourly OHLC: the order of high and low inside a bar is unknown. Fills are at the next open; basket +$3/-$6 checks happen only at closes, so one bar can jump far past the stop.
- Desk `gold_basket` (no escalation) equals `bounded_fixed` by rule, so it is not run twice.
- The ema rows reuse EMAX, whose holdout was claimed 2026-11-14T22:17:06Z; its holdout row is not a first look.
- The $10,000 reference balance, margin test and -6%/+10% barriers are research assumptions, not Matthew's limits.
- Avoided losses are not counted as profit. Cash is $0, and $0 is a valid result.
