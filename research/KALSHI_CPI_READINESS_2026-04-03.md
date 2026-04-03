# Kalshi CPI Readiness Audit — 2026-04-03

Purpose: turn REQ-66 from a vague CPI idea into a specific go/no-go checklist for the April 10, 2026 CPI release.

## Verdict

Current status: `WATCH`

Interpretation:
- the bot already has the structural CPI/economics pieces needed for a paper-first April 10 run
- it is not yet a blind "go live" because two live dependencies remain: actual KXCPI market availability on April 8-10 and observed Kalshi repricing speed during the event

## Structural Checks That Passed

- `economics_sniper.py` already has the intended paper-trial guardrails:
  - 88c floor
  - 48h entry gate
  - 5m hard skip
  - 0.50 USD paper calibration size
- `main.py` already wires `economics_sniper_loop` into the normal async task set
- `economics_sniper_loop` uses `PaperExecutor` and `kill_switch.check_paper_order_allowed()`
- `scripts/cpi_release_monitor.py` already names the next CPI release as `2026-04-10 at 08:30 ET (13:30 UTC)`
- targeted test files already exist for both the economics sniper and the CPI monitor
- `config.yaml` still defaults Kalshi to `demo`

## What Still Blocks Real Confidence

- KXCPI contracts may or may not be open in the exact April 8-10 window; code readiness is not the same as market availability
- the CPI monitor is still a research tool, not an execution path
- the rate-sensitive speed-play thesis depends on actual Kalshi lag after the release, which has not yet been observed

## Action Plan

1. On April 8, confirm open `KXCPI-*` contracts exist and match the expected settlement window.
2. On April 10 at about `08:28 ET`, run:

```bash
cd /Users/matthewshields/Projects/polymarket-bot
python3 scripts/cpi_release_monitor.py
```

3. Keep `economics_sniper` paper-only through the first CPI cycle.
4. After the event, write the observed lag, repricing direction, and whether the edge was real back into the bridge files.

## CCA Helper

CCA now has a cheap audit command for this:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 kalshi_cpi_readiness.py
```

Use it before April 8 and again on April 10 morning. If it ever returns `blocked`, fix the structural gap before treating CPI as deployable.
