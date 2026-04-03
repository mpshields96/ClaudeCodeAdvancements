# Kalshi REQ-63 / Non-Sniper Market Scan
# Date: 2026-04-03
# Author: Codex acting as CCA research support

## Goal

Help the Kalshi bot find supplementary, lower-variance income sources beyond the current
sniper engine, with emphasis on markets that are:

- structurally repeatable
- supported by public/clean source data
- less dependent on pure discretionary guessing
- realistic for a small bankroll and current bot architecture

## Bottom Line

The current public signal does **not** support chasing generic "AI prediction" or
"find any new market" ideas. The repeatable edges people keep converging on are narrower:

1. compare Kalshi to sharper external prices or venue references
2. trade markets with clean public settlement sources and low narrative ambiguity
3. avoid thin/penny contracts where paper performance overstates live edge
4. use incentives/rebates as an EV booster, not as a standalone strategy

## High-Probability Candidates

### 1. Weather promotion from paper to tightly-gated live

Why this ranks high:

- Existing bot infrastructure already has `weather_forecast.py` and weather data feeds.
- Kalshi weather contracts settle from a deterministic public source: the final National
  Weather Service Daily Climate Report.
- Settlement is cleaner than narrative/political markets and less latency-sensitive than
  cross-venue arbitrage.

Why it is still not live yet:

- Weather is paper-only in current polybot state.
- It still needs a pre-live audit and explicit thresholds that keep variance contained.

Suggested live gating:

- only trade markets with a clean source-link match to NWS climate reports
- only trade when ensemble uncertainty is small enough to justify live capital
- prefer late-day or near-resolution setups where forecast uncertainty has compressed
- avoid contracts whose edge depends on app/weather-site displays instead of the NWS source

Suggested first live scope:

- one city
- one contract family
- hard daily cap
- straight positions only

### 2. Sports line-value expansion using sharp-book consensus

Why this ranks high:

- Reddit traders discussing systematic Kalshi edges kept pointing to sports value via
  comparison against sharp or broader sportsbook consensus, not narrative AI guessing.
- The bot already has sports infrastructure (`sports_game.py`, Odds API, ESPN, injury
  leverage tooling).
- This is a true non-sniper path that can be run as a supplement on slow sniper days.

What public signal says:

- the repeatable retail edge is not "predict winners better than everyone"
- it is "compare Kalshi price to better external reference prices and size carefully"
- liquidity is still thin enough that large size is not realistic, but small size is
  realistic for the current bankroll

Suggested scope:

- prioritize NHL and MLB first
- keep NBA on probation until recalibration is cleaner
- add UFC as a medium-term candidate only after sports-game infrastructure is generalized

Suggested gating:

- require book consensus from multiple books
- require a minimum edge after fees
- require a narrow dispersion across books so the consensus is not stale/noisy
- favor mid-range prices over extreme pennies or near-100c contracts

### 3. Mentions / deterministic culture markets in paper

Why this ranks high:

- Kalshi currently exposes deterministic public-source markets such as Top App, Spotify,
  Netflix, and X-post count markets.
- These markets resolve off public charts or APIs rather than hard-to-model latent events.
- They are not 15-minute crypto and do not require the bot to beat headline-driven crowd
  narratives in politics.

Best first candidates:

- earnings/mention-style markets when source terms are explicit and transcript windows are known
- Top App markets (public chart snapshot)
- Spotify/Netflix chart markets (published chart source)
- X-post count markets only if the source/rules are stable enough for automated counting

Why this is paper-first:

- current bot does not yet have specialized source adapters for these markets
- resolution-rule parsing matters a lot
- these are lower-frequency but potentially cleaner opportunities

## Useful Support Layers, Not Primary Engines

### 4. Cross-venue gap monitor

This should be built as a **read-only monitor first**, not a live execution engine.

Why:

- multiple threads said cross-venue gaps exist
- the same threads also said large gaps are often thin, close in seconds, or reflect rule
  mismatches rather than true arbitrage
- the bot does not have a practical live Polymarket execution path for this to become a
  reliable primary engine right now

Use instead:

- compare Kalshi against Polymarket and sportsbook references as a signal-quality overlay
- if Kalshi is far from both sharp books and Polymarket, confidence increases
- if Kalshi only differs from Polymarket but rules differ, do nothing

### 5. Incentive/rebate-aware order selection

Kalshi now has both liquidity and volume incentive programs. These should not drive trade
selection by themselves, but they can improve borderline EV decisions.

Use case:

- expected edge from price mispricing is small but positive
- incentive eligibility adds a few extra basis points
- the trade becomes acceptable after incorporating rebate math

Do not use this as a reason to trade no-edge markets.

## Weak Candidates / Skip For Now

### Cross-venue arbitrage as a core live engine

Reason to skip:

- public traders report the real gaps close very quickly
- many spreads are fake arbitrages caused by different rules
- platform mismatch and latency constraints make this a poor fit for the current bot

### Generic AI-forecasting on prediction markets

Reason to skip:

- public paper-trading examples repeatedly got criticized for slippage, thin markets,
  insider risk, and unrealistic fills
- the edge seems concentrated in low-liquidity categories where paper results overstate live returns

### Thin penny contracts

Reason to skip:

- multiple Reddit threads flagged that the paper edge is usually strongest exactly where
  live execution quality is worst
- the current bankroll should not be used to validate paper-only low-liquidity claims

### Combos as a near-term main engine

Reason to skip:

- combos are RFQ-based and limited to specific categories
- they add more pricing and execution complexity than the current bot needs
- they may become valuable later, but they are not the fastest route to a stable +5 to +10/day add-on

## Ranked Build Order

1. Promote weather from paper to tightly-gated live after a pre-live audit.
2. Expand sports value logic around sharper external reference prices, starting with NHL/MLB.
3. Build a read-only cross-venue / external-reference monitor to score market quality.
4. Paper-trade deterministic culture/mentions markets: Top App, Spotify, Netflix, X-posts.
5. Add incentive-aware EV adjustment to maker/orderbook logic where eligible.

## Concrete Polybot Build Tasks

### Task A: Market selection score

Add a market-selection layer that scores each market on:

- `source_clarity_score`
- `liquidity_score`
- `reference_price_quality`
- `rule_ambiguity_penalty`
- `incentive_bps`

The bot should prefer markets with:

- public deterministic source
- strong liquidity
- clean external reference
- low ambiguity

### Task B: Sports value gate hardening

For sports:

- require at least N books in consensus
- require dispersion below a chosen threshold
- compare Kalshi implied probability against consensus after fee adjustment
- cap size harder in lower-liquidity leagues

### Task C: Weather live graduation audit

Before live weather:

- verify all live candidate markets map to the correct NWS source
- verify daylight-savings handling for settlement windows
- add one-day paper/live shadow logging for live candidate thresholds

### Task D: Deterministic-market source adapters

Build paper-only adapters for:

- Apple App Store top chart
- Spotify chart page
- Netflix chart page
- X-post count via source-compatible counting rules

### Task E: Incentive overlay

For every candidate market:

- detect whether liquidity incentive or volume incentive is active
- estimate rebate contribution per contract
- include rebate in EV calculations, but never let rebate override a negative-edge trade

## Sources

### Reddit / community signal

- r/PredictionMarkets: "Kalshi and Polymarket regularly show 10-15% probability gaps on the same event - I built a dashboard to track this"
  https://www.reddit.com/r/PredictionMarkets/comments/1rp4nep/kalshi_and_polymarket_regularly_show_1015/
- r/PredictionMarkets: "Who's taking a systematic approach to Kalshi?"
  https://www.reddit.com/r/PredictionMarkets/comments/1s1ld2a/whos_taking_a_systematic_approach_to_kalshi/
- r/PredictionMarkets: "I pulled 5GB of Kalshi trade data and the liquidity provider economics don't look like market making — they look like underwriting"
  https://www.reddit.com/r/PredictionMarkets/comments/1roaqkl/i_pulled_5gb_of_kalshi_trade_data_and_the/
- r/PredictionMarkets: "Has anyone actually figured out a consistent edge in prediction markets?"
  https://www.reddit.com/r/PredictionMarkets/comments/1s57cfw/has_anyone_actually_figured_out_a_consistent_edge/
- r/PredictionMarkets: "How I built a tool to find mathematical 'risk-free' profits in sports markets (Arbitrage & +EV)"
  https://www.reddit.com/r/PredictionMarkets/comments/1s47ln7/how_i_built_a_tool_to_find_mathematical_riskfree/
- r/algotrading: "60 days live paper trading results - LLMs exploiting misspricing between Polymarket traders and AI rationale"
  https://www.reddit.com/r/algotrading/comments/1rsj22d/60_days_live_paper_trading_results_llms/
- r/sportsbook: "The betting advice you wish to give beginners?"
  https://www.reddit.com/r/sportsbook/comments/1s67d0e/the_betting_advice_you_wish_to_give_beginners/

### Official Kalshi sources

- Finding Markets
  https://help.kalshi.com/navigating-the-exchange/finding-markets
- Weather Markets
  https://help.kalshi.com/markets/popular-markets/weather-markets
- Top App Markets
  https://help.kalshi.com/markets/popular-markets/top-app-markets
- Spotify Markets
  https://help.kalshi.com/markets/popular-markets/spotify-markets
- Netflix Markets
  https://help.kalshi.com/en/articles/13823840-netflix-markets
- X Posts
  https://help.kalshi.com/markets/popular-markets/x-posts
- Combos
  https://help.kalshi.com/markets/combos
- Market Maker Program
  https://help.kalshi.com/markets/market-maker-program
- Liquidity Incentive Program
  https://help.kalshi.com/incentive-programs/liquidity-incentive-program
- Volume Incentive Program
  https://help.kalshi.com/en/articles/13823850-what-is-the-kalshi-volume-incentive-program
- Consumer Spending tag page with live mentions examples
  https://kalshi.com/tag/consumer-spending
- E-Commerce tag page with live mentions examples
  https://kalshi.com/tag/e-commerce
