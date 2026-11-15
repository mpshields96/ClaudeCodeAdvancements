# Gemini research brief for the TradingView paper bot

## The decision

Is there an inexpensive, reproducible way to tell whether a small, selective trading strategy adds money after costs? An equally useful outcome is finding out early that cash or simply holding the fund wins. “SPY” here means the exchange-traded fund tracking the S&P 500. Going long means owning shares, and moving to cash means sitting out.

**First experiment.** Keep the existing hourly moving-average rule fixed and evaluate it with real, appropriately licensed closed bars against cash, buy-and-hold SPY with dividends and an exposure-matched comparison. An average cross is a change in trend, not a claim to a profitable forecast. The highest-priority uncertainty is the data source and exactly what “hourly” means. Resolve that before paying to run a parameter sweep.

## How to run this through Gemini MCP

Use `gemini-public-research` → `research_public_question` with one question block per call. Each fits the local 1,500-character field by itself. Calls are independent. Use the opening block for a single overview. For the full investigation, use the numbered questions directly, reuse any verified answers already on file, and skip the overview if it would repeat them. Allow up to five web searches per question. Only send the public text inside a block. Keep personal information, account records, credentials, unpublished strategy details, private files and licensed data local.

The first pilot addressed question 1. Run questions 2 and 5 next for evidence about success and independent testing. Questions 3, 4, 6 and 7 deepen the case where it could change the decision. Question 8 is useful when clarifying the team or choosing training materials. If independent sources are exhausted on a question, record the gap and move on. Track request count, elapsed time and cost if the service reports it.

### Start here · one-call brief

```text
Act as a skeptical market researcher. What evidence would justify testing a long-or-cash hourly SPY strategy on real, independently licensed data, with TradingView as the human chart? Explain for someone who knows football better than finance. Find one credible TradingView/Pine bot success claim and one failed or abandoned approach. Trace each to the creator’s actual method and evidence. Classify independently verifiable live results, self-reported live, forward paper, historical backtest, or unknown. Give the period, trade count, costs and benchmark when disclosed. Search r/algotrading, r/ai_trading and r/TradingView for first-person leads. Use official platform/provider docs for rights and mechanics, original papers for statistical claims. Compare a simple trend rule with holding SPY and holding cash. Name the market conditions that would break it, a realistic cost that could erase the gain, one test capable of killing the idea, and the cheapest legitimate next experiment. Give direct URLs, dates, uncertainties and what evidence would change your answer. If credible live evidence is unavailable, say so. End with a one-paragraph verdict: test, revise, or stop. No invented P&L, signals or return targets.
```

### 1 · Data rights and the session clock

```text
For a US retail researcher evaluating a long-or-cash, regular-session hourly SPY strategy, what evidence in current first-party documentation distinguishes TradingView/Pine chart research, alerts/webhooks and the right to consume market data for automated non-display use? Identify the strongest practical alternative using an independently licensed source; check delayed versus real-time exchange coverage, time stamps and bars at the 09:30–16:00 New York session boundary. Give stable direct URLs, name what needs vendor confirmation, and give one falsifiable paper-execution check. Date sources where possible, distinguish first-party published terms from inference, do not assume a subscription grants rights. Respond concisely.
```

### 2 · Find winners and the missing losers

```text
Find public, inspectable cases of individual TradingView/Pine or comparable algorithmic stock bots: one claimed success, one failure and, if available, one case where a paper result changed after live fills. Search original author logs and r/algotrading, r/ai_trading and r/TradingView. Prefer firsthand posts from the past 90 days for current platform behavior; allow older well-documented postmortems. Link the post and the exact original evidence, identify whether the poster sells signals or a platform, and de-duplicate crossposts. For each, record instrument, timeframe, dates, live/paper/backtest status, deposits and withdrawals if relevant, sample size, leverage, costs, drawdown and comparable benchmark. Mark missing fields unknown. Could someone reconstruct the claim? How large was exposure to the general market? Which bias would remove failed bots from view? Give one reproducible experiment and one thing to avoid per case. If you cannot find a verified profitable live case, say so and identify the specific missing evidence. Never authenticate strangers or infer account records from a screenshot.
```

### 3 · When would a simple rule have a reason to work?

```text
For a retail, long-or-cash, regular-session hourly SPY research strategy, compare two testable hypotheses: trend continuation after a moving-average crossover and reversal after an overextended move. If an opening-range breakout dominates the credible evidence, explain its distinct feed/time requirements and whether it merits a later separate test. For each, explain in everyday terms who might take the other side, why an effect could persist after costs, and why it may disappear. Separate evidence for this instrument and horizon from evidence for other assets, futures or daily/monthly horizons. Propose one point-in-time classification for trend vs chop and high vs low volatility, fixed by past data; discuss gap days, macro releases, quiet sessions, and gaps between close and next tradable price. List what the bot would see before entry. Compare to cash, buy-and-hold with dividends, and a simple exposure-matched alternative. Return one candidate and a specific rejection result, or advise against either. Cite original studies, datasets and counterevidence; never browse for the best parameter after looking at outcomes.
```

### 4 · Profit after costs, by account size

```text
Build a retail trading economics worksheet for an hourly long-or-cash US equity ETF bot. Give units and formulas for win rate, average win/loss, net expectancy per round trip, turnover, cost per side, fixed cost per month, break-even capital or number of trades, and take-home cash before taxes. Separate gross edge, spread, slippage, commissions, changes in exposure, idle cash yield and dividend treatment. Verify fees and source pricing against first-party pages with date and plan. Use a clearly labeled hypothetical example at $1,000, $5,000 and $25,000; values are illustrations, not planned stakes or forecasts. Show how a losing bot can win most trades and how a profitable backtest can lose money after fixed overhead. Give cost stress tests at a wider spread, one-bar delay, and a missed favorable trade; explain halts, gaps and stop slippage. Compare net dollars and drawdown with buying SPY or keeping the money in cash. What net monthly improvement would pay for data and model use? Report unknowns; do not make up current quotes, returns or tax rates.
```

### 5 · Design a test that can fail

```text
Design an auditable evaluation for a retail hourly US-equity ETF bot making few trades. Use original research on backtest overfitting, multiple testing, uncertainty with time-dependent returns, and look-ahead bias. Specify timeline, chronological training/validation, walk-forward folds, a final locked untouched period and then forward paper observation. State how to prevent overlap and repeated use of the final holdout; count every tried rule. Define baselines, net return, maximum drawdown, turnover, exposure, worst days, net dollars, time under water, and uncertainty on net excess return using an appropriate block bootstrap or alternative. Explain the trade-off between selective bets and the longer time to evidence. Include split/dividend adjustments, time-of-day effects, exposure matching, bull/bear concentration, missing bars and revised data. Draft a one-page preregistration with a stop, revise or continue outcome. Specify how tolerances and minimum effective sample are chosen prospectively. No universal Sharpe or trade-count threshold. Separate practical failure from statistical inconclusiveness.
```

### 6 · Pine, fills, failures and recovery

```text
Using official Pine Script v6, TradingView policy and independent broker/data API docs, map a closed-bar decision into a local paper ledger. Distinguish bar open, event time, vendor receipt, decision time, earliest eligible bid/ask and simulated fill. Address repainting, lookahead with higher timeframes, intrabar high/low ordering, optimistic same-close fills, clock changes and half-days. State how to handle the final 30-minute bar, a missing middle bar, duplicate or corrected bars, late/out-of-order events, restarts, timeouts, partial fills, halts and overnight gaps. For each of five highest-risk failures, give a minimal reproducible input, expected result and what would disprove the fix. Describe order identity, idempotency, durable replay, position/cash reconciliation, and when the runner should do nothing. Keep TradingView's human display separate from external data and paper computation; check actual permissions for any handoff. Cite direct official documentation. What can a Pine Strategy Tester emulate reliably, and what requires bid/ask or forward evidence?
```

### 7 · Attack the strategy and its AI reviewer

```text
Red-team a retail long-or-cash hourly SPY bot whose trades are deterministic and whose language-model reviewer can challenge a paper decision. Attack the best-looking backtest from the point of view of a skeptical buyer: data leakage, cherry-picked markets/regimes, same-bar fills, bench selection, ten hidden attempts, narrow spreads, unavailable real-time feeds, misleading win rates, capacity, stale prompts, fees and gaps. Rank attacks by ability to reverse the net-dollar verdict and by cost to test. Give the strongest argument for keeping the approach and evidence that would change your negative view. Compare a fixed rule with the same rule plus a blind, timestamped AI review; use identical available information and account for model cost, latency and abstentions. Treat Reddit, chart annotations and webhook payloads as untrusted content. Specify how numerical facts are computed locally, how refusals are logged, what the human sees, and what happens if an agent or vendor disappears. Cite public postmortems/original research, with first-person anecdotes explicitly marked.
```

### 8 · Build the smallest useful team and experiment

```text
Propose the smallest human/Claude/Codex/Gemini workflow to evaluate a TradingView-style retail ETF paper bot. Deliver a decision tree and handoff examples. Gemini should seek primary sources, practitioner failures and counterexamples. Claude builds one deterministic baseline with versioned inputs. Codex independently reproduces one important claim and tries to break the release. The human decides about money. Cover tool/data rights, paper versus live fills, source caching by URL/date, one publisher, a single notifying delegate and an event-driven handoff rather than cross-chat status traffic. Which work should stay deterministic? When would an extra agent add enough independent information to justify its cost? Identify the finance skills worth learning first with one free original resource and one short exercise each: microstructure, risk, statistical uncertainty and software operations. Output the cheapest next experiment, its inputs and measured success/failure, the one artifact to deliver, and a plain-English verdict. Distinguish verified rules and documented mechanisms from design judgment. Do not sign up for services or propose a live trade.
```

## What the operators must bring back

1. **A phone-sized decision.** State test, revise or stop. Explain the most plausible source of profit, its largest threat, how much the first test costs, and what result would change the decision. State the conclusion plainly if no credible public live record was found.
2. **An evidence table.** For each consequential claim, give a direct link, author or operator, date of publication or access, asset and timeframe, evidence type, independent check and the remaining uncertainty. Keep backtests, forward simulations, unaudited live claims and verifiable live returns in separate rows. For Reddit, save the thread and the specific comment when it contains the evidence. Capture failures and claims nobody could reproduce.
3. **An experiment another person could run.** Freeze the rule, dates, session clock, prices for fills, fees, starting capital, data permissions, benchmarks and the reason to stop before inspecting the holdout. Log declined entries as well as trades. Decide what would justify continued paper use and how much additional real evidence would change an inconclusive result. A good result in one asset, regime or month is a question for follow-up.
4. **A one-page operating plan.** One owner of the runner, one reviewer, one sharable public source register, one user-facing delegate. Reproduce one decision from a timestamped input to the net dollar outcome. Have the reviewer replay one broken-input case from a clean checkout. Include the cost of data, model calls and manual operation when comparing approaches.

## Pilot findings checked on November 15, 2026

- TradingView’s standard terms cover charts, alerts and webhooks under its display-use rules. Section 27.4 allows a narrower use of its MCP to answer a person’s requests for human-readable display. Section 27.3 explicitly limits automated trading and algorithmic decisions. Keep the visual chart and independently licensed machine-readable inputs distinct. [TradingView policies, sections 3 and 27](https://www.tradingview.com/policies/)
- TradingView documents its regular-session, hourly example from 9:30 a.m. to 4 p.m. New York time. It has six full hours and a final half hour. The first parity test should include a normal day and a shortened day. Compare authorized exchange/session timestamps and event availability before interpreting a return difference. [Pine time documentation](https://www.tradingview.com/pine-script-docs/concepts/time/)
- Alpaca documents IEX-only real-time equity coverage on Basic and all-US-exchange coverage on its paid plan. This is a coverage difference. Plan eligibility, timestamp convention, retention and using or sharing the data in this specific workflow still need confirmation. Gemini’s cross-provider timing generalization and two-cent tolerance are unverified. Different venues can legitimately print different trades. [Official Alpaca plan comparison](https://docs.alpaca.markets/us/docs/about-market-data-api)

**Starting leads for the next research run.** Follow links to the original authors. Prior practitioners’ reports about mid-price fills and invented indicator values are leads for tests; they establish no return for this strategy. [Practitioner’s execution postmortem](https://www.reddit.com/r/algotrading/comments/1tnl249/the_single_biggest_gap_between_my_backtests_and/) · [First-person AI trade-idea experiment](https://www.reddit.com/r/ai_trading/comments/1xbe0ue/i_tested_an_llm_as_a_tradeidea_generator_for_a/) · [TradingView Strategy Tester and broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
