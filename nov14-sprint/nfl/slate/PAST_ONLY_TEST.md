# Past-only test of the Sunday picker

Run 2026-11-15T07:29:45Z. Input `nfl/data/raw/games.csv` (sha256 44f6ba50a7630386). Cutoff: games dated before 2026-11-15.

Every prediction here was made from games played before the game being scored. The model's settings were fixed in advance and were not searched. The only fitted value is the market weight in the blend, chosen on the tuning seasons alone. The 2023-2025 seasons are a longer historical comparison. The 2026 test covers completed regular-season weeks 1-9. Thursday of Week 10 is excluded from that test.

## Who predicts winners better: the market or the model?

Log loss and Brier score on every two-sided priced, decided moneyline game. Ties are excluded. Lower is better.

| Window | Games | Market log loss | Model log loss | Blend log loss | Market Brier | Model Brier | Blend Brier |
|---|---|---|---|---|---|---|---|
| Tuning seasons 2010-2022 | 3495 | 0.6101 | 0.6304 | 0.6101 | 0.2113 | 0.2204 | 0.2113 |
| Held out 2023-2025 | 854 | 0.6077 | 0.6351 | 0.6077 | 0.2102 | 0.2221 | 0.2102 |
| Held out 2026 (completed regular-season weeks 1-9) | 135 | 0.6223 | 0.6306 | 0.6223 | 0.2152 | 0.2212 | 0.2152 |

Market weight chosen on the tuning seasons: **1.00** (1.00 means the market alone). Six weights were tried, all counted: 0.00 gives 0.6304, 0.25 gives 0.6213, 0.50 gives 0.6149, 0.75 gives 0.6112, 0.90 gives 0.6102, 1.00 gives 0.6101.

**Result: the model does not beat the market in both held-out windows. Every hit likelihood on the picks page uses a stated market reference when available.**

## Does the model beat the posted spread or total?

The model takes the side its number favours against the posted line. Break-even at -110 is 52.4%. Record is wins-losses-pushes; the rate leaves pushes out. A big edge is 3 points or more.

| Window | Spread, all games | Spread, big edge | Total, all games | Total, big edge |
|---|---|---|---|---|
| Tuning seasons 2010-2022 | 1728-1690-90, 50.6% | 522-472-29, 52.5% | 1721-1749-38, 49.6% | 429-457-9, 48.4% |
| Held out 2023-2025 | 397-439-19, 47.5% | 116-113-3, 50.7% | 433-415-7, 51.1% | 122-122-3, 50.0% |
| Held out 2026 (completed regular-season weeks 1-9) | 67-63-6, 51.5% | 18-19-3, 48.6% | 65-71-0, 47.8% | 19-27-0, 41.3% |

## What picking the two most likely winners each Sunday did

Historical unrestricted benchmark across each Sunday: take the two most likely moneyline sides. Return is profit per unit risked at the archive price. Archive quote times are unknown. The 2026 sample covers nine Sundays, too few to judge the rule.

| Window | Ranked by | Sundays | Record | Both won | Return per unit |
|---|---|---|---|---|---|
| Tuning seasons 2010-2022 | market price | 222 | 356-86-2, 80.5% | 146 of 222 | -3.12% |
| Tuning seasons 2010-2022 | model rating | 222 | 350-90-4, 79.5% | 135 of 222 | +0.83% |
| Held out 2023-2025 | market price | 54 | 90-18-0, 83.3% | 39 of 54 | -1.32% |
| Held out 2023-2025 | model rating | 54 | 88-20-0, 81.5% | 35 of 54 | +1.75% |
| Held out 2026 (completed regular-season weeks 1-9) | market price | 9 | 13-5-0, 72.2% | 4 of 9 | -13.31% |
| Held out 2026 (completed regular-season weeks 1-9) | model rating | 9 | 16-2-0, 88.9% | 7 of 9 | +15.44% |

## Is the market's favourite price honest?

All priced, decided games from 2010 through completed 2026 Week 9. If the market says 80%, favourites in that band should win about 80% of the time.

| Market says | Games | Average stated chance | Favourites actually won |
|---|---|---|---|
| 50% to 60% | 1410 | 55.4% | 55.1% |
| 60% to 70% | 1498 | 64.8% | 64.0% |
| 70% to 80% | 1136 | 74.7% | 76.2% |
| 80% to 90% | 408 | 84.2% | 85.0% |
| 90% to 100% | 32 | 91.5% | 96.9% |

## Limits of this test

- The archive prices carry no quote time. They are probably near closing prices, which are sharper than a price seen the night before.
- No injury history is in the test. Health is shown on the picks page as context and is not in any number.
- Player props have no history here, so no prop number is tested.
- A good record over all games does not prove the two selected bets will win. The historical two-pick table has no price band or time windows and does not validate Sunday's cross-market process.
- Model residual spread used for cover and over chances: margin 13.39 points, total 13.64 points (tuning seasons).
