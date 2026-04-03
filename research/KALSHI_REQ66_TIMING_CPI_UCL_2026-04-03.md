# Kalshi REQ-66 Timing / CPI / UCL Research
# Date: 2026-04-03
# Author: Codex acting as CCA research support

## Scope

Answer Kalshi REQ-66 with emphasis on:

1. sports market timing
2. UCL soccer market timing / game-vs-futures choice
3. CPI April 10 live decision
4. alternate market types worth building
5. MVE / combo market verdict

## Executive Verdict

### Highest-confidence operational moves

1. Do **not** rely on major sports game markets being consistently tradeable 8-14 hours before start.
2. Do **not** pre-position in UCL season-winner futures as a substitute for game markets.
3. Treat April 10 CPI as a **micro-live candidate**, not a full live rollout.
4. Treat combos/MVE as **skip for now**.
5. If a new market type must go live by April 13, the cleanest candidates are:
   - tightly-gated weather live pilot
   - micro-live economics event play
   - continued sports_game expansion once same-day game markets actually appear

## 1. Sports Timing Optimization

### What we know

- Kalshi trades 24/7 except scheduled maintenance windows, so lack of pre-game sports
  volume is **not** caused by exchange trading hours.
- Current polybot observations indicate NBA/NHL/MLB game markets are not reliably liquid
  deep in advance; they tend to become actionable later on game day.
- I did **not** find an official Kalshi source that guarantees a fixed listing/open time
  for KXNBAGAME / KXNHLGAME / KXMLBGAME markets.

### Practical conclusion

There is not enough evidence to design around an "8-14 hours before game time" edge.
The reliable behavior appears to be:

- monitor early
- expect meaningful quotes/liquidity later
- concentrate active sports scans in the same-day afternoon / pre-start window

### Recommended scan cadence

All times below are Eastern Time:

- 11:30 AM ET: first serious game-market check
- 1:00 PM ET: MLB opening wave / same-day check
- 3:00 PM ET: second same-day sports sweep
- 6:00 PM ET: heavy pre-game check for NBA/NHL evening boards
- final 60-90 min before game start: highest-priority active scan window

### Build implication

Do not try to solve this by broader overnight sports polling. Solve it by:

- heavier same-day polling windows
- better queueing of candidate markets once first quotes appear
- passive maker orders where liquidity incentives exist and edge remains positive

## 2. Alternate Market Types

### Best candidates

#### A. Economics event markets

Why:

- objective source agency
- concentrated liquidity around known release windows
- can be traded with explicit rule and timing checks

Best use:

- micro-live first
- one contract family
- no assumption that crypto-sniper FLB transfers automatically

#### B. Deterministic public-source culture markets

Why:

- source clarity is high
- rules are explicit
- outcomes are not dependent on noisy narratives

Best categories:

- Top App
- Spotify
- Netflix
- X-post count

These should begin in paper unless there is already implementation support.

#### C. Sports game markets

Still valid, but timing-constrained.

The edge here is reference-price driven, not FLB-driven. It remains useful as a
supplementary engine, but not an overnight one.

### Weak candidates

- championship futures for short-term income
- generic "AI prediction" markets
- combo / MVE structures

## 3. UCL Soccer Timing

### What is confirmed

Official Kalshi help pages do not give a dedicated public UCL trading guide, but the
official Market Maker Program page explicitly lists `KXUCLGAME`, which is strong evidence
that UCL game markets exist as a supported product line.

### What is not confirmed

I did **not** find an official source that confirms:

- exact public listing/open timing for `KXUCLGAME`
- guaranteed in-play availability for those markets

### Practical recommendation

Do **not** use season-winner futures like Arsenal 26c as the main UCL plan.

Reason:

- that is not a high-probability FLB zone
- it is a medium-probability futures position, not a near-expiry certainty trade
- current liquidity snapshot was poor
- the thesis becomes “forecast tournament path” instead of “exploit a structural near-resolution edge”

### Best UCL plan

1. Watch for `KXUCLGAME` boards around the April 7-8 quarterfinal second legs.
2. If game markets appear, evaluate them exactly like sports_game:
   - external sharp reference
   - enough books
   - enough volume
   - enough edge after fees
3. Do **not** assume in-play markets exist until the ticker is actually visible.
4. If no game-market liquidity appears, skip rather than force a futures trade.

## 4. CPI April 10 Live Decision

### Verified timing

The U.S. Bureau of Labor Statistics states that March 2026 CPI data are scheduled to be
released on **Friday, April 10, 2026 at 8:30 AM Eastern Time**.

### What that means for the bot

The release timing is real and fixed. That makes CPI a valid target for a known-window
strategy, but not automatically a full-size live deployment.

### Critical distinction

There is **not enough basis** to assume the crypto sniper's 90-93c near-expiry FLB edge
transfers cleanly to a one-off macro release contract 48 hours before data publication.

Why:

- the event is sparse, not continuous
- there is no long in-bot live sample yet
- the economics strategy has no real-money history
- macro releases can gap sharply on new information

### Recommendation

Use a staged decision:

#### If all conditions below hold on April 9-10:

- rules clearly settle off the BLS March 2026 CPI release
- price remains in the 89-91c zone
- volume remains healthy
- paper signal remains directionally consistent through the pre-release window

Then:

- go **micro-live**, not full live
- suggested size: 1-2 USD cap per bet for first live CPI event

#### If any condition fails:

- stay paper

### Why micro-live instead of full live

This preserves the learning value of a real execution without pretending one paper cycle
is sufficient validation.

## 5. MVE / Combo Verdict

Official Kalshi help docs make combos look even less attractive for the current bot:

- combos are RFQ-based
- availability is typically closer to event start
- settlement is separate from the underlying legs
- payout is the product of leg values

That means more execution complexity, more settlement complexity, and less fit with the
current objective of adding a stable new income lane quickly.

### Verdict

Skip MVE / combos for now.

## Ranked Action Plan

1. Keep sports polling but re-center it on same-day afternoon/pre-start windows.
2. Do not pre-position UCL season winners; wait for `KXUCLGAME` visibility/liquidity.
3. Treat April 10 CPI as micro-live eligible only under strict conditions.
4. Keep building deterministic public-source non-sports adapters in paper.
5. Ignore combos until core single-market engines are stronger.

## Sources

- BLS CPI release schedule:
  https://www.bls.gov/schedule/news_release/cpi.htm
- BLS CPI home:
  https://www.bls.gov/cpi/
- Kalshi trading hours:
  https://help.kalshi.com/trading/what-are-trading-hours
- Kalshi Market Maker Program:
  https://help.kalshi.com/markets/market-maker-program
- Kalshi Combos:
  https://help.kalshi.com/markets/combos
- Kalshi Market FAQs:
  https://help.kalshi.com/en/articles/13823821-market-faqs
- Kalshi Weather Markets:
  https://help.kalshi.com/markets/popular-markets/weather-markets
- Kalshi Top App Markets:
  https://help.kalshi.com/markets/popular-markets/top-app-markets
- Kalshi Spotify Markets:
  https://help.kalshi.com/markets/popular-markets/spotify-markets
- Kalshi Netflix Markets:
  https://help.kalshi.com/en/articles/13823840-netflix-markets
- Kalshi X Posts:
  https://help.kalshi.com/markets/popular-markets/x-posts

## Confidence Notes

- CPI release timing: high confidence (official BLS)
- sports game exact listing/open times: medium-low confidence; no official fixed-hour source found
- UCL game-market existence: medium confidence (official market-maker product list)
- UCL in-play availability: low confidence; not confirmed from official sources
