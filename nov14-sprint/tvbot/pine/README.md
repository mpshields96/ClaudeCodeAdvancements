# EMAX-1.0.0 human-visible alerts (Pine script)

Status: Compiles in TradingView. At 21:29Z on 2026-11-14, Codex pasted this exact 140-line file (SHA-256 a04cdd26…7b957) into the Pine Editor as an unsaved indicator on a SPY 1-hour chart. It added to the chart, and the legend "EMAX-1.0.0 human-visible alerts(paper research)" appeared, as Codex recorded it. No alert was created and nothing was saved to the account. Evidence: `../../codex/Pine_Native_Verification.md`. If the file changes, its hash changes, and this check no longer covers it.

Claude did not load this script into Matthew's TradingView account and did not create any alert.

## What it is

A TradingView Pine v6 indicator, `emax_alerts.pine`. It draws one simple rule on the chart and raises alerts that Matthew reads himself. It is the human-visible half of a paper-only research project. It places no orders and is not a strategy. Paper research, not advice.

- Symbol: AMEX:SPY
- Timeframe: 60 minutes
- Chart link (readable): https://www.tradingview.com/chart/?symbol=AMEX:SPY&interval=60
- Chart link (URL-encoded, used inside the alert text): https://www.tradingview.com/chart/?symbol=AMEX%3ASPY&interval=60

## The rule in plain words

Rule id EMAX-1.0.0. Long only, one position at a time, no shorts.

- Two moving averages of the closing price: fast = 8 bars, slow = 21 bars. They are written by hand (not the built-in `ta.ema`) and start from the first loaded bar's close.
- Stop = 1.5 percent below the entry price. Warmup = 63 bars.
- Nothing counts until a bar has closed and at least 63 bars have been seen.
- When the fast average crosses above the slow one on a closed bar and no position is open, the chart shows LONG SETUP. The hypothetical position starts at the next bar's open.
- While in the hypothetical position, on each closed bar: if the close is at or below entry times (1 - 1.5 percent), the chart shows STOP EXIT. Otherwise, if the fast average crosses below the slow one, it shows TREND EXIT. The position ends at the next bar's open.
- A new cross up while already in a position is ignored.

On the chart: the two averages, a teal up-triangle for LONG SETUP, amber or navy down-triangles for the exits, a faint tint while the hypothetical position is open, and an amber line at the stop level.

## Adding it later (steps for Matthew, or for Codex's chart-side test)

1. Open the chart link above in TradingView.
2. Open the Pine Editor (bottom panel), paste the contents of `emax_alerts.pine`, then click Add to chart. It compiled cleanly in Codex's check on this exact file. If you edit it and it reports an error, fix that error first.
3. Create an alert: right-click the chart or use the alarm-clock icon, set the condition to "EMAX alerts", and choose ONE of the three EMAX entries (long setup, stop exit, trend exit) with the trigger "Once per bar close", or choose "Any alert() function call". Do not set up both kinds, or you will get each message twice.

## Alert setup warning

Leave "Webhook URL" unticked. These alerts are for reading only. They must never be sent to a webhook, a bot, a model or a ledger. Each message says so: "For Matthew to read. Not an order. Do not send to a webhook or bot."

## Pine side versus the offline paper runner

The Pine script shows raw rule signals only. The offline Python paper runner implements the same rule and additionally applies risk limits (max position, daily loss stop, cooldown) and trading costs. Its paper ledger can therefore differ from the chart markers by design. The runner starts its averages from its own first synthetic bar, while the chart starts from the first bar TradingView has loaded, so early values and signals can also differ slightly.
