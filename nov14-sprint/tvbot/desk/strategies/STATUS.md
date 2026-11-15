# Desk strategies: status (worker C)

Updated 2026-11-15 by worker C. Paper and offline only. Every number is simulated.

## Headline

**No strategy beats cash.** That holds on the synthetic harness and on the private gold cross-check.

- **Gold basket** (all variants): −$1.00 a day on the 90 normal sessions and −$0.69 a day on the first-look holdout. It fails every part of the pass criterion.
- **EMA crossover** (existing EMAX): +$0.94 a day on normal, positive in F1, F2 and F3. It is −$0.15 a day on a holdout that was already claimed on 2026-11-14, so that is not a first look. It fails.
- **ema_overnight:** +$1.57 a day on normal, but F1 is −$2.32 and bootstrap p05 is −$1.63. It fails.
- **Cash:** $0, a valid result.

The synthetic numbers are harness evidence only. They say nothing about gold or any real market.

## CONTRACT v2 and the purity fix (about 17:45Z)

- **Pure decide.** Codex found a cache bug at 17:25Z: a bar corrected to volume 0 after an EMA entry still gave a warm HOLD_IN_TREND, while a cold replay gave NO_SIGNAL. The registry cache now continues only when every earlier bar equals, in every field, a copy taken at the earlier call. A corrected, removed or in-place-edited bar forces a cold replay. The Decision returned is a deep copy, and `now` only selects bars. Codex's probe now reports no difference at any of its 9 indices.
- **Line fields.** trigger, intended_entry, intended_exit and invalidation are each `{"price": float or None, "text": str}`. `est_cost` is a dict with `usd`, `per_side_usd`, `basis` and `simulated: true`.
- **Stops.** Every entry carries a numeric `invalidation.price`. An entry without one is refused as NO_STOP.
- **MAX_LOSS_WOULD_BREACH.** The rule is qty × |intended_entry − invalidation| + est_cost.usd <= `cfg["limits"]["max_loss_per_trade"]` (or `cfg["max_loss_per_trade"]`). The strategy refuses the entry and never resizes it, so a refused entry leaves no phantom position. With no cap in cfg, the check passes with a note and the order manager enforces the cap. **The desk must put `limits` in strategy_cfg** for the strategy-side check to fire.
- **At TEST VALUES size on the fixture:**
  - Every EMA entry risks about $33 (20 × 1.49 + $3.20), above the $10 test cap, so with the cap EMA never enters.
  - Gold entries risk about $6 and fit.
- **Research unchanged.** The new check is off without a cap, and research passes none. A dry run written to scratch (not to `out/research/`) differs from the published result only in holdout fields, the rule hash and the timestamp.
- **UI gap (not in my scope).** `_num()` in `ui/server.py` and `num()` in `ui/index.html` read the line fields as plain numbers, so they show null for these dicts. They should read `["price"]`.

## Files

| File | What it is |
|---|---|
| `__init__.py`, `base.py` | Decision shape (DECISION_FIELDS plus `refusal_checks`), cost model, sessions, TEST VALUES sizing |
| `engine.py` | One replayer for desk and research: decide at a bar's close, fill at the next open; zero-volume bars never fill; one netted basket |
| `registry.py` | `STRATEGIES`: ema, gold_basket, fixed_risk_single, bounded_fixed, cash. Signature `decide(bars_so_far, position, cfg) -> Decision`, a pure function of its inputs. Escalation is forced off |
| `RULES.md` | Frozen rules, written before any result. Covers ChoCh, timestamps, add-on/netting, XAUUSD to GLD/1OZ/MGC, escalation (research only), refusal tests and the pass criterion |
| `research.py` | Synthetic research. Output: `desk/out/research/RESEARCH_RESULT.{json,md}` and `HOLDOUT_CLAIM.json` |
| `private_gold.py` | Private cross-check on Codex's XAUUSD minute data. Output, local only: `desk/out/research_private/` (with a `*` .gitignore) |
| `../tests/test_strategies_core.py` | 18 tests |
| `../tests/test_strategies_v2.py` | 12 tests: warm equals cold, including Codex's zero-volume case and corrected, removed, in-place-edited and dropped bars; the stop and cap rules |

## Commands (from the CCA repo root)

```bash
/usr/bin/python3 -I -m unittest discover -s nov14-sprint/tvbot/desk/tests -p 'test_strategies*'
```

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/strategies/research.py --no-holdout
```

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/strategies/research.py
```

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/desk/strategies/private_gold.py
```

- Tests: 35 OK, about 19 s (adds 5 for the fixed_qty demo preset).
- fixed_qty (18:00Z): `base_qty` uses a positive int `cfg["fixed_qty"]` (HYPOTHETICAL demo preset, TEST VALUE) only while fixed_qty x price <= the TEST per-trade notional cap; above it returns 0 so ZERO_SIZE shows. Anything else falls back to floor(notional/price).
- Weekly report: `desk/report.py --state-dir D [--week YYYY-Www]` writes D/reports/report_<week>.{html,pdf}, 3 pages on the scratch mock state.
- `--no-holdout` is a dry run that never reads the holdout. It overwrites `out/research/RESEARCH_RESULT.*`, so the published file then loses its holdout section.
- The full `research.py` run needs the rule hash to match `HOLDOUT_CLAIM.json`. It no longer matches (see Holdout), so the full run refuses.
- `private_gold.py` is local only.

## Holdout

- Claimed 2026-11-15T17:29:56Z, rule hash `d3056d25d4bae654857cf1f468c1ad050a7efb8da1d9df801a7eeba5e2dbee03`.
- The hash covers engine.py, base.py, registry.py and RULES.md. Editing any of them makes the holdout refuse.
- That holdout has now been seen. Any rule change needs fresh untouched data.
- **The hash has changed.** The CONTRACT v2 edits (about 17:42Z) and the purity fix changed engine.py, registry.py and RULES.md after the claim. The full run now refuses, as designed. The published `RESEARCH_RESULT.*` is still the 17:29:56Z run, and the dry run shows that its non-holdout numbers are unchanged.

## Private gold cross-check

**Verdict on the declared primary: does not beat cash.** The primary is 2023, the escalating basket with pivots reset each session, at base costs of $0.30 spread plus $0.05 slip per oz. Codex's own 2023 replay agrees in sign.

- The run covers 2021–2023 and 27 configurations.
- **Base costs:** every configuration loses money.
- **Double costs:** every configuration loses money.
- **Zero costs:** gross is small and mostly slightly positive. Its bootstrap p05 is below 0 in all but one configuration.
- So the round-trip costs remove whatever gross edge there is.

**How this differs from Codex's replay:**
- Basket checks and fills here use 5-minute bars; Codex's use 1 minute.
- The source data has no volume, so volume is None here.
- At the TEST VALUES size, gold at or above $2,000/oz gets 0 oz, so some 2023 entries are refused as ZERO_SIZE.

**Where the numbers are:** only in `desk/out/research_private/PRIVATE_GOLD_RESULT.{json,md}`, which is git-ignored. They are derived from third-party data, so don't copy them into tracked files and never commit or publish them.

The source is Codex's workspace. I checked each archive's sha256 against Codex's receipts.

## Gaps and limits

- **Gold variants are identical on synthetic data.** No synthetic basket reached a second leg, so escalation, alternating and fixed size could not be told apart there.
- **Close-only stop.** On hourly bars the basket's −$6 stop is checked only at closes. One bar can jump far past it: the worst synthetic day is −$96.23. This is disclosed, not fixed, because the rule is frozen.
- **The per-session pivot reset gives 0 trades on the 7-bar hourly fixture.** A 13-bar pivot window cannot fit in a 7-bar session. It does trade on five-minute gold bars.
- **COST_EXCEEDS_EDGE.** At costs ×2 and ×3 the synthetic gold round trip is at least $6, so the strategy refuses and the result is $0. That is a refusal, not an edge.
- **Instrument facts** in RULES.md §5 (GLD ratio, 1OZ and MGC contract sizes, fees) are marked [UNVERIFIED] and need primary-source checks.
- **TEST VALUES size.** At $2,000 notional the gold size is 0 oz at or above $2,000/oz. Size is Matthew's to set, and it was not tuned.
- **Holdout junction.** The synthetic holdout starts at a price gap from the end of normal (101.55 to 99.87). This is disclosed in RULES.md.
- **Multiple testing.** 112 configurations were evaluated. The candidate was declared first.
- **Not done:** broker fills, real US instruments (GLD, 1OZ, MGC), and TradingView data. TradingView data never enters any decision or ledger.
