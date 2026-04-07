# Kalshi Post-Ban Feedback — 2026-04-06

This is the corrective memo for future CCA sessions working on Kalshi support.

## Matthew Feedback / Planning Correction

1. Stop defaulting to sniper bets every time the bot needs profit.
2. Sports can be a considerable share of total bets, even `30-40%`, but only if MLB/NHL/NBA
   are treated as separate calibrated lanes rather than one generic "sports" bucket.
3. We are `100%` not ignoring non-sports Kalshi markets. Untapped markets remain mandatory.
4. The Kalshi bot and Kalshi chat need a better system for seeing all relevant Kalshi markets.
   Right now market visibility is inadequate.
5. The bot struggling to see sports over the next 48 hours, then betting games days from now,
   is directly opposed to the actual daily-profit goal.
6. Daily profit matters more than long-dated exposure. Same-day and near-term market visibility
   must be a blocker priority.

## Hard Planning Rules

- Sniper is the base layer, not the roadmap.
- No new sniper variant gets priority over building a second real engine.
- Market visibility is a first-class infrastructure problem.
- Sports research order: MLB first, NHL second, NBA third.
- College baseball and UFC stay research queue until MLB/NHL/NBA are cleaner.
- Non-sports Kalshi discovery runs in parallel as a separate lane.
- If one strategy exceeds `80%` of trailing profit, CCA must enter a "build second engine"
  sprint rather than tune that strategy again.

## What CCA Should Push Next

1. Bot visibility audit:
   - what Kalshi markets are visible now
   - what sports markets are missed now
   - why same-day boards are missed
   - why days-out games are still entering the bet set
2. Sports calibration:
   - MLB clean post-bug run
   - NHL separate cap and scorecard
   - NBA probation / mapping audit before more live use
3. Non-sports discovery:
   - economics
   - politics
   - entertainment / culture
   - any daily-profit-relevant categories visible through a series scout

## Read With

- `polymarket-bot/.planning/POST_15M_CRYPTO_BAN_ANALYSIS_2026-04-06.md`
- `polymarket-bot/.planning/CCA_ACTION_MEMO_POST_BAN_OVERHAUL_2026-04-06.md`
