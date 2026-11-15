# Real NFL data: 2026 week 10

PAPER ONLY. No bets, no accounts, no money. Written by `real_intake.py` at 2026-11-15T05:14:24Z (system clock).

## Where every number came from

- Games, teams, kickoff times and finals: DraftKings Sports Scores, search_games_v1, page https://www.nfl.com/schedules/2026/by-week/week-10, captured 2026-11-14T22:51:42Z (file sha256 `f6fa22769799e21af1e76155a3583f99c6c77a6e56916c874e0151815958ad19`).
- Prices: DraftKings as shown on the public ESPN scoreboard, observed 2026-11-14T22:53:42Z (file sha256 `206d164be40574fa78cb9a1fca8f0db3b3c8d8ef0a5b56431f3f975682d60e9e`). URLs: https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261115, https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261116.
- Capture note carried from the price file: "Public ESPN display. Actual book update time and Louisiana availability unknown. Prices may move. No closing line, wager or pick inferred."
- Rest days: nflverse schedule file https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv, retrieved 2026-11-14T21:16:58Z.
- These prices were read before kickoff. They are not closing lines, and nobody has checked that they are offered in Louisiana.

## What is real and what is missing

- Real games: 14. Finals in the source: 1. Games with a real price: 13. Games with no price: 1.
- Rule rows (frozen rules x games): 56.
  - real price recorded, awaiting final: 44
  - no price, not scored: 4
  - rule has no side here, nothing to price: 8
- Compared with the paper ledger rows: same decision, side, line and price as the real source: 52.
- Ledger writes this run: 0 real prices recorded on identical contracts, 44 already there, 0 refused, 0 not recorded because the line differs; settle: settle not run; 1 final(s) held back from settle, no real price on the identical ledger contract: 2026_10_WAS_NYG.

## Games

| Kickoff (UTC) | Game | Status | Final | Real spread (home) | Real total |
|---|---|---|---|---|---|
| 2026-11-13T01:15:00Z | WAS at NYG | ScoresOfficial | WAS 24, NYG 21 | no price | no price |
| 2026-11-15T14:30:00Z | NE at DET | Upcoming | not played yet | DET -2.5 | 49.5 |
| 2026-11-15T18:00:00Z | KC at ATL | Upcoming | not played yet | ATL +3 | 47.5 |
| 2026-11-15T18:00:00Z | HOU at CLE | Upcoming | not played yet | CLE +4.5 | 40.5 |
| 2026-11-15T18:00:00Z | MIN at GB | Upcoming | not played yet | GB -2.5 | 42.5 |
| 2026-11-15T18:00:00Z | JAX at TEN | Upcoming | not played yet | TEN +10.5 | 46.5 |
| 2026-11-15T18:00:00Z | MIA at IND | Upcoming | not played yet | IND -4.5 | 37.5 |
| 2026-11-15T18:00:00Z | CAR at NO | Upcoming | not played yet | NO -2.5 | 48.5 |
| 2026-11-15T18:00:00Z | BUF at NYJ | Upcoming | not played yet | NYJ +7.5 | 50.5 |
| 2026-11-15T21:05:00Z | SEA at LV | Upcoming | not played yet | LV +6.5 | 40.5 |
| 2026-11-15T21:05:00Z | LA at ARI | Upcoming | not played yet | ARI +9.5 | 39.5 |
| 2026-11-15T21:25:00Z | SF at DAL | Upcoming | not played yet | DAL +3.5 | 55.5 |
| 2026-11-16T01:20:00Z | PIT at CIN | Upcoming | not played yet | CIN -3.5 | 49.5 |
| 2026-11-17T01:15:00Z | LAC at BAL | Upcoming | not played yet | BAL -4.5 | 38.5 |

## Frozen rules on the real games

A take is a paper pick. A pass is scored on its shadow side so passes are counted too. Spread lines are shown for the picked side.

| Game | Rule | Decision | Pick | Real price | Score |
|---|---|---|---|---|---|
| WAS at NYG | HOME_DOG-v1.T7 | - | - | - | no price, not scored |
| WAS at NYG | BIG_DOG-v1.T10 | - | - | - | no price, not scored |
| WAS at NYG | REST_EDGE-v1.D6 | - | - | - | no price, not scored |
| WAS at NYG | HIGH_TOTAL_UNDER-v1.T47 | - | - | - | no price, not scored |
| NE at DET | HOME_DOG-v1.T7 | pass | DET -2.5 | -118 | real price recorded, awaiting final |
| NE at DET | BIG_DOG-v1.T10 | pass | NE +2.5 | -102 | real price recorded, awaiting final |
| NE at DET | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| NE at DET | HIGH_TOTAL_UNDER-v1.T47 | take | under 49.5 | -108 | real price recorded, awaiting final |
| KC at ATL | HOME_DOG-v1.T7 | pass | ATL +3 | -108 | real price recorded, awaiting final |
| KC at ATL | BIG_DOG-v1.T10 | pass | ATL +3 | -108 | real price recorded, awaiting final |
| KC at ATL | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| KC at ATL | HIGH_TOTAL_UNDER-v1.T47 | take | under 47.5 | -118 | real price recorded, awaiting final |
| HOU at CLE | HOME_DOG-v1.T7 | pass | CLE +4.5 | -112 | real price recorded, awaiting final |
| HOU at CLE | BIG_DOG-v1.T10 | pass | CLE +4.5 | -112 | real price recorded, awaiting final |
| HOU at CLE | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| HOU at CLE | HIGH_TOTAL_UNDER-v1.T47 | pass | under 40.5 | -112 | real price recorded, awaiting final |
| MIN at GB | HOME_DOG-v1.T7 | pass | GB -2.5 | -120 | real price recorded, awaiting final |
| MIN at GB | BIG_DOG-v1.T10 | pass | MIN +2.5 | +100 | real price recorded, awaiting final |
| MIN at GB | REST_EDGE-v1.D6 | pass | GB -2.5 | -120 | real price recorded, awaiting final |
| MIN at GB | HIGH_TOTAL_UNDER-v1.T47 | pass | under 42.5 | -115 | real price recorded, awaiting final |
| JAX at TEN | HOME_DOG-v1.T7 | take | TEN +10.5 | -105 | real price recorded, awaiting final |
| JAX at TEN | BIG_DOG-v1.T10 | take | TEN +10.5 | -105 | real price recorded, awaiting final |
| JAX at TEN | REST_EDGE-v1.D6 | pass | TEN +10.5 | -105 | real price recorded, awaiting final |
| JAX at TEN | HIGH_TOTAL_UNDER-v1.T47 | pass | under 46.5 | -110 | real price recorded, awaiting final |
| MIA at IND | HOME_DOG-v1.T7 | pass | IND -4.5 | -108 | real price recorded, awaiting final |
| MIA at IND | BIG_DOG-v1.T10 | pass | MIA +4.5 | -112 | real price recorded, awaiting final |
| MIA at IND | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| MIA at IND | HIGH_TOTAL_UNDER-v1.T47 | pass | under 37.5 | -110 | real price recorded, awaiting final |
| CAR at NO | HOME_DOG-v1.T7 | pass | NO -2.5 | -105 | real price recorded, awaiting final |
| CAR at NO | BIG_DOG-v1.T10 | pass | CAR +2.5 | -115 | real price recorded, awaiting final |
| CAR at NO | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| CAR at NO | HIGH_TOTAL_UNDER-v1.T47 | take | under 48.5 | -105 | real price recorded, awaiting final |
| BUF at NYJ | HOME_DOG-v1.T7 | take | NYJ +7.5 | -108 | real price recorded, awaiting final |
| BUF at NYJ | BIG_DOG-v1.T10 | pass | NYJ +7.5 | -108 | real price recorded, awaiting final |
| BUF at NYJ | REST_EDGE-v1.D6 | pass | NYJ +7.5 | -108 | real price recorded, awaiting final |
| BUF at NYJ | HIGH_TOTAL_UNDER-v1.T47 | take | under 50.5 | -105 | real price recorded, awaiting final |
| SEA at LV | HOME_DOG-v1.T7 | pass | LV +6.5 | -108 | real price recorded, awaiting final |
| SEA at LV | BIG_DOG-v1.T10 | pass | LV +6.5 | -108 | real price recorded, awaiting final |
| SEA at LV | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| SEA at LV | HIGH_TOTAL_UNDER-v1.T47 | pass | under 40.5 | -108 | real price recorded, awaiting final |
| LA at ARI | HOME_DOG-v1.T7 | take | ARI +9.5 | -108 | real price recorded, awaiting final |
| LA at ARI | BIG_DOG-v1.T10 | pass | ARI +9.5 | -108 | real price recorded, awaiting final |
| LA at ARI | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| LA at ARI | HIGH_TOTAL_UNDER-v1.T47 | pass | under 39.5 | -112 | real price recorded, awaiting final |
| SF at DAL | HOME_DOG-v1.T7 | pass | DAL +3.5 | -105 | real price recorded, awaiting final |
| SF at DAL | BIG_DOG-v1.T10 | pass | DAL +3.5 | -105 | real price recorded, awaiting final |
| SF at DAL | REST_EDGE-v1.D6 | pass | - | - | rule has no side here, nothing to price |
| SF at DAL | HIGH_TOTAL_UNDER-v1.T47 | take | under 55.5 | -102 | real price recorded, awaiting final |
| PIT at CIN | HOME_DOG-v1.T7 | pass | CIN -3.5 | -108 | real price recorded, awaiting final |
| PIT at CIN | BIG_DOG-v1.T10 | pass | PIT +3.5 | -112 | real price recorded, awaiting final |
| PIT at CIN | REST_EDGE-v1.D6 | take | PIT +3.5 | -112 | real price recorded, awaiting final |
| PIT at CIN | HIGH_TOTAL_UNDER-v1.T47 | take | under 49.5 | -115 | real price recorded, awaiting final |
| LAC at BAL | HOME_DOG-v1.T7 | pass | BAL -4.5 | -108 | real price recorded, awaiting final |
| LAC at BAL | BIG_DOG-v1.T10 | pass | LAC +4.5 | -112 | real price recorded, awaiting final |
| LAC at BAL | REST_EDGE-v1.D6 | pass | BAL -4.5 | -108 | real price recorded, awaiting final |
| LAC at BAL | HIGH_TOTAL_UNDER-v1.T47 | pass | under 38.5 | -110 | real price recorded, awaiting final |

Files beside this one: `week10_games.csv`, `week10_finals.csv`, `week10_prices.csv`, `week10_rule_scores.csv`, `INTAKE_RECEIPT.json`. Every row in them carries its source URL and retrieval time.

Paper output never implies a real edge or authorizes real money.
