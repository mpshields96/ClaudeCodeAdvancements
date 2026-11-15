# Community leads for the Nov 14 sprint (R3)

Worker: community research (Claude). Batch 1 was written after the 21:26:08Z clock check, batch 2 after the 21:39:51Z check, batch 3 after the 21:47:56Z check, batch 4 after the 21:56:34Z check and batch 5 after the 22:27:28Z check. Batch 5 is the last one. The two top-5 lists were updated in place with each batch.

Count: 92 Reddit leads (73 tvbot, 19 nfl) across 25 communities, plus 21 primary sources inspected. Three of the 92 (T1, T2, T6) were also read at source by Codex. New in batch 2: T35 to T43, D1 to D8, N6 to N12, P13 to P16, and the rewritten "Free bar data" section. New in batch 3: N13 to N19 (the first leads from r/sportsbetting and more from r/sportsbook), P17 to P19, and both overfitting papers confirmed to exist as named. New in batch 4: T44 to T60 (bots built with Claude, paper-versus-live reports, TradingView webhook reliability), P20 and P21. New in batch 5: T61 to T65 (the first lead from r/quantresearch and four more from r/Daytrading).

## How to read this

- **lead** = a Reddit thread found through Gemini public search. The claim is a paraphrase of Gemini's search summary. Claude did not open the thread. Reddit returns 403 from this Mac and was not fetched, mirrored or scraped. Titles are the URL slug. Gemini's pairing of a claim with a link is its own inference; where the slug doesn't fit the claim, the entry says so.
- **inspected** = Claude fetched the primary page today. Quotes come from that extraction, so re-open the page before relying on exact wording.
- **[UNVERIFIED]** = not checked against a primary source.
- Dates: search returned none. Reddit post IDs rise over time, so an ID is only a rough hint (my inference: 3q... is about 2015, 41... about 2016, dy... about 2019, y6... about 2022, 12... about 2023, 1d to 1g about 2024, 1i to 1p about 2025, 1r to 1x about 2026).
- Gemini often files a thread under the wrong subreddit. The community shown here is always the one in the resolved link. One row whose link had expired was dropped, rows that resolved to a thread already listed were dropped, and a cross-post is counted once.
- Not repeated here: the six threads Codex already used in `codex/Community_Findings.md` and `codex/Trading_Bot_First_Build.md` (IDs 1xpmsgq, 1xbe0ue, 1tnl249, 1w6h2ii, 1x9xu48, 1wp9ezt). Codex later added a seventh, 1w7wzd5 (r/algobetting), which is not in this file either.
- Read at source by Codex: T1, T2 and T6, at 21:34Z (`codex/Reddit_Source_Check.md`). Codex reports that the posts support the engineering ideas and that each author's figures stay self-reported. No other thread here was opened by anyone.
- Link not confirmed: T4, T5, T10, T13, T16, T26, T27, T28, T29 and T34 carry the URL that Gemini wrote in its answer text, with no redirect lookup behind it. In the last sweep, all six URLs Gemini wrote that way had a wrong post ID, so any of these ten links may open the wrong thread. The other 82 leads' links came from a redirect lookup (see `STATUS.md`).

## Top 5 for the tvbot lane

1. **Signal only on closed bars.** Leads T1, T7, T18, T44, T50, T64. Inspected (P1, P2): TradingView says `barstate.isconfirmed` "is a simple way to avoid repainting", and that the higher-timeframe pattern needs both the `[1]` offset and `barmerge.lookahead_on` ("Neither can be removed without compromising the integrity of the function").
   *How to use it:* in the Pine indicator, gate every signal and alert on `barstate.isconfirmed`, set the alert to once per bar close, and use the `[1]` plus `lookahead_on` pattern for any higher-timeframe value. Apply the same rule in the Python paper runner: decide only on a closed bar and drop the still-forming candle (Kraken's API always returns one, see P11). Stamp every input with the time it became available, not the time it describes (lead T44), so a replay cannot see a value early.
2. **Count every variant tried, and raise the bar as the count grows.** Leads T2, T8, T11, T12, T19, T62. Primary check: both papers the threads name exist as named. The Deflated Sharpe Ratio paper (P16: Bailey and Lopez de Prado, 2014) says in its abstract that the measure "corrects for two leading sources of performance inflation": selection bias under multiple testing and non-normal returns. The Probability of Backtest Overfitting paper (P17: Bailey, Borwein, Lopez de Prado and Zhu, 2015) was read to its title page only. Neither paper's formulas were checked, so the threads' descriptions of the methods stay [UNVERIFIED]. Codex's "138 tried, 3 passed" thread points the same way.
   *How to use it:* keep a trial ledger with one row per rule, parameter set and prompt variant, including the dropped ones. Report "N tried, K passed". Require the result to survive a 15 to 20 percent nudge of each parameter, and touch the holdout once.
3. **Fill at the next bar with costs, never at the signal bar's close or the midpoint.** Leads T5, T10, T13, T14, T38, T39, T47, T50, T58, T60, T61, T65. Inspected (P3, P19, P20): TradingView's broker emulator "fills a strategy's orders using only the available chart data by default", fills market orders "on the next available tick", and assumes an intrabar price path.
   *How to use it:* store signal time and fill time as separate fields. Fill at the next bar's open plus half the spread, slippage and commission. In a Pine strategy, set commission and slippage yourself: with none set, TradingView "applies no commission to filled orders" (P19) and slippage defaults to 0 (P20). Leave `process_orders_on_close` off, which is its default, so orders fill on the next bar and not at the signal bar's close. Show a stress row in the report (double cost, one extra bar of delay). Charge the fee on every paper fill and print gross and net side by side; lead T39 describes fees taking over half of a bot's gross profit (unverified).
4. **Code computes every number; the model only explains, inside a strict schema.** Leads T3, T9, T15, T16, T49, T51, T52, T54, T63. Inspected (P6): arXiv 2605.24564 shows a model can remember the test period ("An LLM trained in 2024 may already encode how stocks moved during 2018-2020.").
   *How to use it:* hand Claude a JSON of code-computed values and validate its reply against a schema. Reject any number in the explanation that is not in the input. Never ask the model for a call on past dates; replays test frozen mechanical rules only. If Claude writes the rules, treat any "out-of-sample" period before the model's training cutoff as already seen (leads T49, T51).
5. **One recorded decision per opportunity, through one order path.** Leads T6, T17, T55, T57. T6 and T17 are post-mortems with no primary source. For T55 and T57, TradingView's webhook page confirms that a request taking longer than three seconds is cancelled but says nothing about retries (P21), so "retries cause duplicate orders" stays unverified.
   *How to use it:* key each decision on symbol, bar close time and rule version. Use one ledger writer with a lock. Reject and log any second decision for the same key. Allow no side script to write to the ledger.

**Terms note for the lane (inspected, P4 and P5).** TradingView's policies describe a display-only licence that covers "charts, alerts, webhooks, and any other forms of information" and bar "any machine-driven processes that do not involve the direct, human-readable display of such data". They also bar automated collection and use of the data to train or test a model. So the Pine and alert leads apply to the human-visible indicator only. The webhook-to-bot leads (T24, T55, T56, T57) are context, not a design to copy. The paper runner needs independent, permitted bars (see "Free bar data" below).

**Hype and scam note (leads T31, T35, T36, T43).** Threads describe "small stake into thousands" bot claims as funnels for paid courses, signal groups and subscriptions. *How to use it:* the lane's report carries no return promise, labels every result as paper, and treats any bot, indicator or signal sold by subscription as an advertisement, not as evidence.

**Paper-test note (leads T45, T46, T48, T53, T60, T61).** Threads say a paper run shows that the plumbing works, not that the rules make money: paper fills ignore queue position, depth and partial fills, and one author reports backtest results falling sharply on walk-forward data and with real money. No thread gave a checked figure for how long a paper test should run. *How to use it:* the report states the number of paper trades and days, calls the run a test of the pipeline, and claims no edge from it.

## Top 5 for the nfl lane

1. **Show the closing-favorite baseline next to the model.** Leads N1, N11, N17. N1: a walk-forward Elo/EPA model on nflverse data picked about 63% of winners against about 66% for closing favorites, with negative return after the vig.
   *How to use it:* every report shows the model, "always take the closing favorite", and the break-even rate of 52.38% at -110 odds (arithmetic: 110 / 210). Print the sample size beside every rate. A season has 272 regular-season games (32 teams x 17 games / 2), so one season's rate has a standard error near 3 points (sqrt(0.25 / 272) = 0.030). A 53 to 54% season is not evidence of an edge. Lead N17's title (a simple model that "has gone 63...") is the kind of short-run record this rule guards against.
2. **Record the line seen at decision time, and score closing line value for takes and passes.** Leads N2, N3, N6, N13, N14, N15. Primary check: none for the threads. The nflverse docs do not say whether their lines are closing lines (P8), so closing line value cannot be computed from those fields alone.
   *How to use it:* the ledger stores the timestamped line seen before the decision. Fill in closing line value only when a closing line of known origin exists; otherwise leave it blank and say so.
3. **Free game and line data: nflverse schedules.** Leads N5, N7, inspected P7 to P9. Fields include `spread_line`, `total_line`, both moneylines and spread odds. The repo's licence file is CC BY 4.0 (P18): attribution is required, and the file does not list which data it covers. The docs name no sportsbook and do not say opening or closing.
   *How to use it:* use it for results, schedules and a reference line, with attribution. Label the line "nflverse line, type not documented". Do not use it as "the line available before the decision" without a timestamp.
4. **No future information in features.** Leads N4, N10, N19. N4: commenters flag full-season averages and tuning on the same seasons being tested.
   *How to use it:* build every feature from games that ended before kickoff. Freeze the rules before the replay, and count each re-tune as a new trial. Treat any betting "trend" as one of thousands of splits somebody searched (lead N19); do not use one as a feature without counting that search.
5. **Code supplies every fact; the model explains and never picks.** Leads N9, N16 (two communities): bettors report raw models inventing traded or injured players and failing betting arithmetic. Lead N3 adds that positive closing line value can sit beside a drawdown, so a confident story proves nothing.
   *How to use it:* give Claude only code-built fields (teams, line, timestamp, model number, sample size) and have it explain those. Reject any player, injury or number in its reply that is not in the input.

**Scam note for the lane (lead N12).** Paid pick sellers are reported to fake records by deleting losses and doctoring tickets. *How to use it:* keep the paper ledger append-only, stamp each pick before kickoff, never drop a loss, and show every pick in the report.

## All leads, ranked

Every entry below is a **lead** (see "How to read this"). Format: ID, community, slug title, link, claim, primary check, red flags.

### tvbot lane

**T1. r/pinescript, "why indicator alerts and strategy alerts fire at..."**
https://www.reddit.com/r/pinescript/comments/1xrnv77/why_indicator_alerts_and_strategy_alerts_fire_at/
Claim: combine `barstate.isconfirmed` with `alert.freq_once_per_bar_close` to stop intrabar alert spam. Primary: confirmed by P1 and P2. Red flags: none seen.

**T2. r/algotrading, "your winner gets weaker every time you test"**
https://www.reddit.com/r/algotrading/comments/1xgu80j/your_winner_gets_weaker_every_time_you_test/
Claim: hundreds of sweep variants inflate false positives; penalize the Sharpe ratio by the effective number of independent trials (cluster variants by return correlation). Primary: [UNVERIFIED]. Red flags: none seen.

**T3. r/algotrading, "what's the best way to avoid AI hallucination in..."**
https://www.reddit.com/r/algotrading/comments/1xudopc/whats_the_best_way_to_avoid_ai_hallucination_in/
Claim: strict JSON or table schemas and unit-test harnesses stop inconsistent, made-up values. Primary: none. Red flags: none seen.

**T4. r/algotrading, "lookahead bias is a hell of a drug"**
https://www.reddit.com/r/algotrading/comments/1n89qg8/lookahead_bias_is_a_hell_of_a_drug/
Claim: same-bar close fills, misaligned timestamps and intrabar highs and lows make clean backtests that fail live. Primary: consistent with P1 (TradingView calls future data on historical bars "dangerously misleading"). Red flags: none seen.

**T5. r/algotrading, "how do you model slippage realistically in a..."**
https://www.reddit.com/r/algotrading/comments/1kzm0cf/how_do_you_model_slippage_realistically_in_a/
Claim: midpoint or fixed fills fail live; model spread crossing, volume limits and tail cases. Primary: none. Red flags: none seen.

**T6. r/ai_trading, "my Claude trading agent went rogue, here's what..."**
https://www.reddit.com/r/ai_trading/comments/1xst559/my_claude_trading_agent_went_rogue_heres_what/
Claim: unsynchronized scheduled loops ran several agent instances that entered the same position two or three times. Primary: none. Red flags: single anecdote; involves live orders, which this sprint excludes.

**T7. r/pinescript, "non-repainting request.security on higher..."**
https://www.reddit.com/r/pinescript/comments/1xoi3yd/nonrepainting_requestsecurity_on_higher/
Claim: even with `[1]` plus `lookahead_on`, `process_orders_on_close = true` can give fills a trader could not get. Primary: the `[1]` plus `lookahead_on` pattern is confirmed (P1); the `process_orders_on_close` part is [UNVERIFIED] (that section of P3 was not read). Red flags: none seen.

**T8. r/algorithmictrading, "3 tests that catch an overfit backtest in the..."**
https://www.reddit.com/r/algorithmictrading/comments/1tqzce8/3_tests_that_catch_an_overfit_backtest_in_the/
Claim: run cheap tests first: Deflated Sharpe Ratio, then shuffled-trade Monte Carlo, then walk-forward. Primary: [UNVERIFIED]. Red flags: possible self-promotion.

**T9. r/algotrading, "letting an LLM write your backtest: check for this"**
https://www.reddit.com/r/algotrading/comments/1tpren4/letting_an_llm_write_your_backtest_check_for_this/
Claim: model-written backtest code slips in look-ahead and off-by-one window bugs. Primary: none. Red flags: none seen.

**T10. r/algotrading, "live vs backtest parity comparison"**
https://www.reddit.com/r/algotrading/comments/1mi2h5z/live_vs_backtest_parity_comparison/
Claim: audit raw order logs and rerun the backtest over the live period to separate latency, partial fills and bugs from strategy error. Primary: none. Red flags: none seen. Paper use: rerun the replay over the paper period and diff the two ledgers.

**T11. r/algotrading, "what is your simplest useful check against..."**
https://www.reddit.com/r/algotrading/comments/1xko987/what_is_your_simplest_useful_check_against/
Claim: walk-forward plus a 15 to 20 percent parameter nudge and purged time-ordered cross-validation. Primary: [UNVERIFIED]. Red flags: none seen.

**T12. r/ai_trading, "how to know a strategy is real: an overfit gate"**
https://www.reddit.com/r/ai_trading/comments/1x43nj0/how_to_know_a_strategy_is_real_an_overfit_gate/
Claim: AI coding assistants speed up selection bias; 50 to 100 configurations with no penalty just pick noise. Primary: [UNVERIFIED]. Red flags: possible self-promotion.

**T13. r/algotrading, "backtested intraday mean reversion"**
https://www.reddit.com/r/algotrading/comments/1j78yfx/backtested_intraday_mean_reversion/
Claim: bar-close fills overstate intraday mean reversion compared with next-bar open plus spread. Primary: consistent with P3. Red flags: any return figures in the thread are unverified.

**T14. r/TradingView, "stop trusting your Pine Script strategy tester"**
https://www.reddit.com/r/TradingView/comments/1tmwq9u/stop_trusting_your_pine_script_strategy_tester/
Claim: the default Strategy Tester leaves out slippage and spread, so low-timeframe backtests beat live and paper results. Primary: P3 confirms the emulator fills from chart data only; the default cost values are [UNVERIFIED]. Red flags: none seen.

**T15. r/algotrading, "built a multi-timeframe MACD analyzer with..."**
https://www.reddit.com/r/algotrading/comments/1rnc9jn/built_a_multitimeframe_macd_analyzer_with/
Claim: hybrid design; Python computes the indicators and the model does explanation and code review off the hot path. Primary: none. Red flags: project showcase.

**T16. r/algotrading, "why LLMs (ChatGPT, Claude) struggle with Pine Script"**
https://www.reddit.com/r/algotrading/comments/1kndr32/why_llms_chatgpt_claude_struggle_with_pine_script/
Claim: models mistranslate Pine to Python (default parameters, missing-value handling, warm-up bars). Primary: none. Red flags: none seen. Use: check the Python indicator against known values on a fixed sample before trusting it.

**T17. r/algotrading, "post-mortem: my tiny market-making bot captured 1921..."**
https://www.reddit.com/r/algotrading/comments/1xinz20/postmortem_my_tiny_marketmaking_bot_captured_1921/
Claim: fee churn from over-trading, accounting bugs, and emergency exit scripts that bypassed the central order registry. Primary: none. Red flags: live trading anecdote; figures unverified.

**T18. r/pinescript, "request.security has more than one way to repaint"**
https://www.reddit.com/r/pinescript/comments/1vg501c/requestsecurity_has_more_than_one_way_to_repaint/
Claim: use `close[1]` with `barmerge.lookahead_on`. Primary: confirmed by P1. Red flags: none seen.

**T19. r/algotrading, "how do you actually know when you've overfit"**
https://www.reddit.com/r/algotrading/comments/1s37rar/how_do_you_actually_know_when_youve_overfit/
Claim: tweaking against the holdout again and again turns it into training data. Primary: none. Red flags: none seen.

**T20. r/algotradingcrypto, "redditors called out my overfit backtest, I ran..."**
https://www.reddit.com/r/algotradingcrypto/comments/1uw38by/redditors_called_out_my_overfit_backtest_i_ran/
Claim: taking the best cell of a parameter sweep picks a lucky tail; most combinations lose and the out-of-sample result collapses. Primary: none. Red flags: none seen.

**T21. r/algorithmictrading, "I'm getting more skeptical of perfect algo..."**
https://www.reddit.com/r/algorithmictrading/comments/1w3e7x5/im_getting_more_skeptical_of_perfect_algo/
Claim: adding parameters inflates in-sample fit; the thread cites the Deflated Sharpe Ratio and PBO. Primary: [UNVERIFIED]. Red flags: none seen.

**T22. r/TradingView, "how to check if a strategy is repainting"**
https://www.reddit.com/r/TradingView/comments/1lgslnj/how_to_check_if_a_strategy_is_repainting/
Claim: data from the still-forming bar creates look-ahead and unrealistic equity curves. Primary: consistent with P1. Red flags: none seen.

**T23. r/TradingView, "easiest ways to check if any indicator or..."**
https://www.reddit.com/r/TradingView/comments/1ghafaq/easiest_ways_to_check_if_any_indicator_or/
Claim: spot repainting with Bar Replay and by checking whether Alerts Log entries later vanish from the chart. Primary: none. Red flags: none seen. Both checks are manual and human-visible, so they fit the terms.

**T24. r/TradingView, "TradingView webhook request took too long error"**
https://www.reddit.com/r/TradingView/comments/1sgowt3/tradingview_webhook_request_took_too_long_error/
Claim: slow webhook receivers time out; reply 200 at once. Primary: P4 confirms the three-second limit. Red flags: **terms**. Feeding alerts to a bot conflicts with P5 and the sprint's fail-closed rule. Context only.

**T25. r/ai_trading, "we spent money and a year testing AI trading..."**
https://www.reddit.com/r/ai_trading/comments/1xvk45e/we_spent_money_and_a_year_testing_ai_trading/
Claim: polling frontier models on tick or second feeds costs one to three seconds of latency and a prohibitive token bill. Primary: none. Red flags: possible vendor post.

**T26. r/algotrading, "update on the 'Claude built me a strategy' post from..."**
https://www.reddit.com/r/algotrading/comments/1m1m7v2/update_on_the_claude_built_me_strategy_post_from/
Claim: model-generated factor mixes look like an edge through overfitting and need strict forward testing. Primary: none. Red flags: none seen.

**T27. r/algotrading, "placing orders at market open: huge edge but..."**
https://www.reddit.com/r/algotrading/comments/1mpm03v/placing_orders_at_market_open_huge_edge_but/
Claim: next-bar and market-open fills meet wide, unstable opening spreads. Primary: none. Red flags: "huge edge" claim is unverified.

**T28. r/algotrading, "how do you handle slippage in scalping algorithms"**
https://www.reddit.com/r/algotrading/comments/1iozxfv/how_do_you_handle_slippage_in_scalping_algorithms/
Claim: spread, latency and taker fees erase scalping edges. Primary: none. Red flags: none seen.

**T29. r/algotrading, "a journey"**
https://www.reddit.com/r/algotrading/comments/1kcyx3y/a_journey/
Claim: ChatGPT-written Pine hit reliability limits; the poster moved to deterministic Python with its own data. Primary: none. Red flags: single anecdote.

**T30. r/pinescript, "I keep getting alerts on every bar, I only want 1..."**
https://www.reddit.com/r/pinescript/comments/12z0264/i_keep_getting_alerts_on_every_bar_i_only_want_1/
Claim: indicator alerts fire intrabar unless "Once Per Bar Close" is set. Primary: partly confirmed. P2 says the default for `alert()` is once per bar, on the first intrabar trigger, not at close. Red flags: old thread (about 2023).

**T31. r/learnmachinelearning, "Qwen makes 51% profit compared to the other models"**
https://www.reddit.com/r/learnmachinelearning/comments/1ofeq5r/qwen_makes_51_profit_compared_to_the_other_models/
Claim: in a public contest, each model traded a live crypto account; some gained early and others drew down steeply. Primary: none. Red flags: **unrealistic returns** over a short window, one run per model, leveraged live trading. Not evidence that a model can trade.

**T32. r/vibecoding, "made a site where AI models trade against each..."**
https://www.reddit.com/r/vibecoding/comments/1p36qw1/made_a_site_where_ai_models_trade_against_each/
Claim (weak pairing; Gemini attached a claim about a different contest): models write persuasive reasons but size positions badly and contradict their own thesis. Primary: none. Red flags: self-promotion.

**T33. r/IndiaAlgoTrading, "how to create your own algo bot, 100% automatic"**
https://www.reddit.com/r/IndiaAlgoTrading/comments/1xpkj4r/how_to_create_your_own_algo_bot_100_automatic/
Claim (weak pairing; the slug does not fit): models get rolling-window indicators wrong and leak future candles; structured JSON or CSV input beats chart images. Primary: none. Red flags: "100% automatic" framing; possible promotion.

**T34. r/algotrading, "LLM for coding bots: Claude vs ChatGPT"**
https://www.reddit.com/r/algotrading/comments/1dapc5v/llm_for_coding_bots_claude_vs_chatgpt/
Claim: a comparison of the two for bot code. Primary: none. Red flags: about 2024, so the model versions are out of date.

**T35. r/ai_trading, "has anyone actually built a profitable AI trading..."**
https://www.reddit.com/r/ai_trading/comments/1xmu5b9/has_anyone_actually_built_a_profitable_ai_trading/
Claim (pairing uncertain; Gemini filed it under r/Daytrading): viral "turn $50 to $300 into thousands overnight" bot claims are funnels for paid courses, Discord groups or prompt subscriptions. Primary: none. Red flags: **paid-signal funnel and unrealistic returns** are the thread's subject.

**T36. r/ai_trading, "people are claiming AI trading bots can turn 80..."**
https://www.reddit.com/r/ai_trading/comments/1xs3mgf/people_are_claiming_ai_trading_bots_can_turn_80/
Claim (pairing uncertain; Gemini filed it under r/CryptoCurrency): someone with a profitable script would trade their own money instead of selling it for a few hundred dollars. Primary: none. Red flags: an argument, not evidence; same hype topic as T35.

**T37. r/TradingView, "most free TradingView indicators have a dirty..."**
https://www.reddit.com/r/TradingView/comments/1vh62w7/most_free_tradingview_indicators_have_a_dirty/
Claim: indicators fake past accuracy by recalculating after the candle closes, or by lacking `barstate.isconfirmed` and safe `request.security` calls. Primary: the mechanism is confirmed by P1. Red flags: "dirty secret" hook, possible self-promotion.

**T38. r/algotrading, "paper 2 live: what mistakes did your trading bot..."**
https://www.reddit.com/r/algotrading/comments/1vmdce4/paper_2_live_what_mistakes_did_your_trading_bot/
Claim: paper results break live through midpoint-fill illusions, partial limit fills, rejected orders and local state drifting out of sync with the venue. Primary: none. Red flags: none seen. Paper use: model "rejected" and "partly filled" as ledger states, and rebuild state from the ledger on restart.

**T39. r/CryptoTradingBot, "11 days running my crypto bot with real money, it's..."**
https://www.reddit.com/r/CryptoTradingBot/comments/1xeckv7/11_days_running_my_crypto_bot_with_real_money_its/
Claim: a perpetual-futures bot trading 10 to 15 times a day lost over half its gross profit to taker fees ($406 of fees on $720 gross). Primary: none. Red flags: 11 days, one account, leveraged live trading; figures unverified.

**T40. r/algotrading, "what trading strategy actually has an edge, I'm..."**
https://www.reddit.com/r/algotrading/comments/1xtq8tf/what_trading_strategy_actually_has_an_edge_im/
Claim (weak pairing; the slug is a general question): crypto backtests fail live because they leave out funding payments, understate maker and taker fees, and fit noise. Primary: none. Red flags: none seen.

**T41. r/quant, "need advise on agentic AI in QR"**
https://www.reddit.com/r/quant/comments/1s1mc6w/need_advise_on_agentic_ai_in_qr/
Claim (weak pairing; the slug is about agents in quant research): wiring a model straight to execution loses money through chart misreading, forgotten context and drift when the provider updates the model. Primary: none. Red flags: none seen. Use: record the exact model version in every decision row.

**T42. r/quantfinance, "has anyone successfully used multi-agent LLM..."**
https://www.reddit.com/r/quantfinance/comments/1rjjqnc/has_anyone_successfully_used_multiagent_llm/
Claim: models should only propose hypotheses or boilerplate behind deterministic gates (walk-forward, look-ahead checks) and never execute trades. Primary: none. Red flags: none seen.

**T43. r/BitcoinMarkets, "I built an AI to signal crypto futures"**
https://www.reddit.com/r/BitcoinMarkets/comments/1jt1ujh/i_built_an_ai_to_signal_crypto_futures/
Claim (weak pairing; Gemini filed it under r/quantresearch): fine-tuned open models underperform simpler ones (LSTM, gradient boosting) on price forecasting because they fit noise. Primary: none. Red flags: the slug reads as a **signal-product showcase**; leveraged futures.

**T44. r/ClaudeAI, "I directed 15 Claude Code agents to build a..."**
https://www.reddit.com/r/ClaudeAI/comments/1wuxxxg/i_directed_15_claude_code_agents_to_build_a/
Claim: a news-driven paper-trading bot was built in a day with Claude Code agents; the author separates when a news item was published from when the bot saw it, to avoid look-ahead. Primary: none. Red flags: a one-day build showcase with "exact prompts" (often promotional); results unverified; it uses a broker's paper account, which this sprint does not open.

**T45. r/ClaudeAI, "I connected Claude Code to a trading engine. The..."**
https://www.reddit.com/r/ClaudeAI/comments/1x81b0x/i_connected_claude_code_to_a_trading_engine_the/
Claim: backtests looked very strong, then performance fell sharply on walk-forward data and with real money. Primary: none. Red flags: real-money trading (excluded here); the "trading engine" may be a product being promoted; figures unverified.

**T46. r/Daytrading, "bot paper testing"**
https://www.reddit.com/r/Daytrading/comments/1xpklcj/bot_paper_testing/
Claim: commenters discuss how long to paper test a bot before going live, pointing to the number of variants tried, unstable parameters and costs. Primary: none. Red flags: no checked figure for "how long"; the go-live framing is outside this sprint.

**T47. r/algotradingcrypto, "crypto trading bot backtests need a cash-flow..."**
https://www.reddit.com/r/algotradingcrypto/comments/1wxgdba/crypto_trading_bot_backtests_need_a_cashflow/
Claim (Gemini filed it under r/BitcoinMarkets): a backtest that records only entry and exit prices overstates returns; it needs a timestamped ledger of every cash flow, such as funding payments on perpetual futures. Primary: none. Red flags: perpetual futures are leveraged and out of scope; the ledger idea still applies to fees on spot paper trades.

**T48. r/BuildWithClaude, "vibecoded a trading bot with Claude, here's where..."**
https://www.reddit.com/r/BuildWithClaude/comments/1wek879/vibecoded_a_trading_bot_with_claude_heres_where/
Claim: comparing a two-year backtest with two weeks of paper trading exposed bracket-order bugs and missing stop-losses in the Claude-written code. Primary: none. Red flags: two weeks is too short to judge results; "vibecoded" means the code was not reviewed line by line.

**T49. r/ai_trading, "a few months ago I said here that 'Claude, build me a...'"**
https://www.reddit.com/r/ai_trading/comments/1xtewti/a_few_months_ago_i_said_here_that_claude_build_me/
Claim: the author re-tested "ask the model for a profitable strategy" three ways and checked whether the generated breakout rules held up on locked out-of-sample data; by the title, the earlier "does not work" verdict was half wrong. Primary: none. Red flags: one author's test; the model may already know the "out-of-sample" period (P6); results unverified.

**T50. r/CryptoTradingBot, "I built a crypto trading bot and blew up my own backtests"**
https://www.reddit.com/r/CryptoTradingBot/comments/1si5z05/i_built_a_crypto_trading_bot_and_blew_up_my_own/
Claim: 20 popular crypto bot strategies stopped working once realistic exchange fees, next-candle execution and a no-look-ahead rule were enforced. Primary: none. Red flags: the count and the strategies are unverified; possible tool promotion.

**T51. r/ai_trading, "a study just measured what I've been arguing about"**
https://www.reddit.com/r/ai_trading/comments/1w2waw0/a_study_just_measured_what_ive_been_arguing_about/
Claim (weak pairing; Gemini gave this link without a title): model backtests are contaminated when the model already knows the historical period, and shifted-index bugs such as `.shift(-1)` leak the future. Primary: P6 shows the memory problem in general; the study this thread refers to was not identified. Red flags: unidentified study.

**T52. r/quant, "AQuA: recursively self-improving quantitative..."**
https://www.reddit.com/r/quant/comments/1vrb9v9/aqua_recursively_selfimproving_quantitative/
Claim (Gemini filed it under r/quantresearch): automated research loops keep factor discovery and testing in a sandbox to stop test-set leakage, and do not give the model control of execution. Primary: none; the AQuA work was not fetched, so it is [UNVERIFIED]. Red flags: "self-improving" is hype wording; likely a project announcement.

**T53. r/algotrading, "platforms to use for testing paper trade"**
https://www.reddit.com/r/algotrading/comments/1x9xvmi/platforms_to_use_for_testing_paper_trade/
Claim (weak pairing; the slug is a platform question): check that live data matches the schema the rules were built on, and treat paper trading as a test of plumbing and feature parity, not proof of an edge. Primary: none. Red flags: platform recommendations in such threads are often affiliate-driven.

**T54. r/algotrading, "after about 4 years of exploration and 1.5 year of..."**
https://www.reddit.com/r/algotrading/comments/1qklj4o/after_about_4_years_of_exploration_and_15_year_of/
Claim (weak pairing; the slug reads as a results post): practitioners use models as coding or text-parsing helpers and do not let them compute numbers or control execution. Primary: none. Red flags: any results in the post are unverified.

**T55. r/buildinpublic, "TradingView alerts are only half the job, what..."**
https://www.reddit.com/r/buildinpublic/comments/1xuggj4/tradingview_alerts_are_only_half_the_job_what/
Claim: duplicate orders come from webhook retries after a three-second timeout; the fix is `barstate.isconfirmed`, once per bar close, and a receiver that ignores a repeat. Primary: TradingView's webhook page says a request that takes longer than three seconds is cancelled, and does not mention retries (P21). Red flags: r/buildinpublic posts usually promote the author's product; webhook-to-bot use falls outside the terms reading above.

**T56. r/TradeAutomationHub, "TradingView alert delay: why your trades execute..."**
https://www.reddit.com/r/TradeAutomationHub/comments/1rt3qj6/tradingview_alert_delay_why_your_trades_execute/
Claim: sending alerts through a middleware service adds delay compared with a direct connection. Primary: none. Red flags: the community looks vendor-run; live execution is excluded here.

**T57. r/TradingView, "TradingView's webhook issue: missing webhooks still..."**
https://www.reddit.com/r/TradingView/comments/1fnesws/tradingviews_webhook_issue_missing_webhooks_still/
Claim (weak pairing): put a unique order or candle ID in the alert's JSON so the receiver can drop repeats; the slug reports missing webhooks. About 2024. Primary: P21 covers the timeout only. Red flags: reliability complaints are anecdotal.

**T58. r/algotrading, "how do I avoid fees and spread on high frequency..."**
https://www.reddit.com/r/algotrading/comments/1utn6ts/how_do_i_avoid_fees_and_spread_on_high_frequency/
Claim (Gemini filed it under r/BitcoinMarkets): bots with a high backtest win rate fail live on small accounts because fees, spread and slippage are larger than the edge per trade. Primary: none. Red flags: none seen.

**T59. r/BitcoinMarkets, "the maker-taker model is bullshit"**
https://www.reddit.com/r/BitcoinMarkets/comments/3q35ik/the_makertaker_model_is_bullshit/
Claim (weak pairing): bots that use market orders lose to taker fees; limit orders pay less but may not fill. Primary: none. Red flags: very old thread (about 2015 by its ID); exchange fee schedules have changed since.

**T60. r/algotrading, "should I run it"**
https://www.reddit.com/r/algotrading/comments/1xr3zst/should_i_run_it/
Claim (weak pairing; Gemini filed it under r/Trading): paper-trading services ignore order-book depth, queue position and partial fills, so paper profit overstates live results. Primary: none. Red flags: the slug is a go-live question, which is outside this sprint.

**T61. r/quantresearch, "$2,932 over 3,180 one-minute paper trades is 92 cents a trade. What would you check before calling it an edge?"**
https://www.reddit.com/r/quantresearch/comments/1xb69pa/2932_over_3180_oneminute_paper_trades_is_92_cents/
Claim (title as Gemini gave it; it matches the slug): commenters say an average of 92 cents per trade on one-minute paper fills will likely vanish live once spread, slippage, market impact and borrow costs are charged. Gemini dates it October 21, 2026 (unverified). Primary: none. Red flags: the dollar figures are the poster's own; the title follows the same pattern as the r/quantresearch thread Codex used (1xpmsgq), so it may be one author's series (my inference).

**T62. r/Daytrading, "If you believe backtesting will make you rich you are delusional."**
https://www.reddit.com/r/Daytrading/comments/1kzzy0c/if_you_believe_backtesting_will_make_you_rich_you/
Claim: commenters say parameters fitted to history give a hindsight picture that fails live because of slippage and changing market conditions. Gemini dates it May 31, 2025 (unverified). Primary: none for the thread; the overfitting papers are P16 and P17. Red flags: an opinion thread with no data.

**T63. r/Daytrading, "So chatGPT gave me some banging trade signals today & thought I'd share here"**
https://www.reddit.com/r/Daytrading/comments/1n7kveh/so_chatgpt_gave_me_some_banging_trade_signals/
Claim: commenters warn that trade signals taken straight from a chatbot prompt bring invented numbers and look-ahead, and lose money quickly. Gemini dates it September 3, 2025 (unverified). Primary: none. Red flags: the post itself shares model-generated signals after one good day, which is the pattern to avoid.

**T64. r/Daytrading, "I may have accidentally created the best indicator ever"**
https://www.reddit.com/r/Daytrading/comments/1kf11gd/i_may_have_accidentally_created_the_best/
Claim: commenters say "holy grail" custom indicators nearly always repaint or look ahead, and the effect disappears in real time. Gemini dates it May 5, 2025 (unverified). Primary: TradingView's repainting pages (P1, P2) describe the mechanism. Red flags: a "best indicator ever" claim; such posts often lead to an indicator being sold.

**T65. r/Daytrading, "I started building a trading BOT, for those who tried this, am I wasting my time?"**
https://www.reddit.com/r/Daytrading/comments/1qynmrq/i_started_building_a_trading_bot_for_those_who/
Claim: commenters say models help write the bot's code, but live results suffer from slippage, spread and overfitting. Gemini dates it February 7, 2026 (unverified). Primary: none. Red flags: a beginner question; the answers are opinions.

#### Data-source leads (tvbot)

**D1. r/algotrading, "worth paying Alpaca for real-time data? I tested..."**
https://www.reddit.com/r/algotrading/comments/1w86sxp/worth_paying_alpaca_for_realtime_data_i_tested/
Claim: Alpaca's free IEX feed agreed with the consolidated feed on candle direction 93 to 97% of the time for liquid ETFs at 5 to 30 minutes, but its small volume share skews VWAP and relative volume. Primary: P15 confirms the free plan is IEX only. Red flags: Alpaca needs an account and keys, which the sprint limits exclude; figures unverified.

**D2. r/algotrading, "where can I find quality datasets for algorithmic..."**
https://www.reddit.com/r/algotrading/comments/1kvm3wk/where_can_i_find_quality_datasets_for_algorithmic/
Claim: Stooq offers free daily downloads; yfinance has gaps. Primary: Stooq's terms were not checked [UNVERIFIED]; for yfinance see P14. Red flags: the paid vendors named in the thread are outside limits.

**D3. r/ai_trading, "best data source: Yahoo vs Alpaca"**
https://www.reddit.com/r/ai_trading/comments/1wf6kxi/best_data_source_yahoo_vs_alpaca/
Claim: yfinance is an unofficial wrapper that gets blocked on cloud servers; Alpaca's free API is preferred for daily bars despite a 15-minute delay. Primary: P14 and P15 confirm "unofficial" and the 15-minute exclusion. Red flags: Alpaca needs keys.

**D4. r/algotrading, "where do you get data"**
https://www.reddit.com/r/algotrading/comments/1xe28cv/where_do_you_get_data/
Claim: Dukascopy and Histdata are named for free multi-year tick and 1-minute data outside equities. Primary: terms not checked [UNVERIFIED]. Red flags: none seen.

**D5. r/algotrading, "need a better alternative to yfinance, any good..."**
https://www.reddit.com/r/algotrading/comments/1jjj6cb/need_a_better_alternative_to_yfinance_any_good/
Claim: Yahoo schema changes and rate limits make large yfinance pulls crash or return stale intraday bars. Primary: P14 (unofficial, personal use). Red flags: none seen.

**D6. r/quant, "list of free or affordable alternative datasets"**
https://www.reddit.com/r/quant/comments/1mx84ab/list_of_free_or_afforable_alternative_datasets/
Claim (weak pairing; the slug is about alternative datasets): quants use Databento trial credits for clean historical bars. Primary: none. Red flags: trial credits need an account, and paid data is outside limits.

**D7. r/algotrading, "what data source are you using for backtesting"**
https://www.reddit.com/r/algotrading/comments/1tte9ep/what_data_source_are_you_using_for_backtesting/
Claim: pull bars once and keep them locally in DuckDB or Parquet instead of pulling again. Primary: none. Red flags: none seen.

**D8. r/Daytrading, "where do you get historical data for backtesting"**
https://www.reddit.com/r/Daytrading/comments/1wu48x4/where_do_you_get_historical_data_for_backtesting/
Claim: crypto backtesters take free candles and CSV files straight from exchanges such as Binance. Primary: P10 and P13 (the files exist; the dataset terms allow personal backtesting only). Red flags: none seen.

### nfl lane

**N1. r/algobetting, "built a walk-forward NFL Elo model and backtested..."**
https://www.reddit.com/r/algobetting/comments/1we9mcf/built_a_walkforward_nfl_elo_model_and_backtested/
Claim: walk-forward Elo and EPA models on nflverse data (2002 to 2025, over 6,000 games) picked about 63% of winners against about 66% for closing favorites, and returned -1% to -3% after the vig even with 5 to 8 percent edge filters. Primary: the data source exists (P7 to P9); the figures are [UNVERIFIED]. Red flags: none; this is a negative result, which makes it more believable than most.

**N2. r/algobetting, "using CLV as proxy for ROI"**
https://www.reddit.com/r/algobetting/comments/1w8827y/using_clv_as_proxy_for_roi/
Claim: closing line value against the no-vig closing line is a faster health check than return, given about 272 games a season. Primary: none. Red flags: none seen.

**N3. r/algobetting, "beating the closing line on most bets but still..."**
https://www.reddit.com/r/algobetting/comments/1xf9i6b/beating_the_closing_line_on_most_bets_but_still/
Claim: positive closing line value can coincide with a drawdown. Primary: none. Red flags: involves real bets, which this sprint excludes.

**N4. r/algobetting, "NFL spread betting model: consistently positive ROI"**
https://www.reddit.com/r/algobetting/comments/1pn0fha/nfl_spread_betting_model_consistently_positive_roi/
Claim: replies warn of look-ahead (full-season averages) and tuning on the tested seasons (2021 to 2024). Primary: none. Red flags: **"consistently positive ROI"** is the classic overfit claim; treat the post's result as unproven.

**N5. r/algobetting, "is there an API that can let you find historical..."**
https://www.reddit.com/r/algobetting/comments/1n7o2gb/is_there_an_api_that_can_let_you_find_historical/
Claim: free historical closing lines come from nflverse; paid odds APIs are also named; clean free opening lines are scarce. Primary: nflverse has line fields (P7, P8), but "closing" is **not confirmed** by its docs. Red flags: the paid APIs and their keys are outside sprint limits.

**N6. r/algobetting, "working out the kinks on an NFL algo"**
https://www.reddit.com/r/algobetting/comments/1xkr2by/working_out_the_kinks_on_an_nfl_algo/
Claim: remove the vig from closing lines before comparing Brier scores; size with a fraction of Kelly to survive underdog variance. Primary: none. Red flags: the staking part concerns real bets, which this sprint excludes; only the calibration part applies.

**N7. r/algobetting, "where can I get historical NFL odds data"**
https://www.reddit.com/r/algobetting/comments/y6lov6/where_can_i_get_historical_nfl_odds_data/
Claim: free closing lines come from the nflfastR family of repos and a Kaggle file named `spreadspoke_scores.csv`; opening or bet-time lines need paid odds APIs. Primary: the nflverse fields are confirmed (P7, P8); the Kaggle file and its licence are [UNVERIFIED]. Red flags: old thread (about 2022); paid APIs and keys are outside limits.

**N8. r/algobetting, "I graded 8000 NFL games against the closing line"**
https://www.reddit.com/r/algobetting/comments/1twp5z4/i_graded_8000_nfl_games_against_the_closing_line/
Claim: final margins cluster on 3 and 7, and home-field advantage has drifted to about 2 points. Primary: none. The lane can recompute both from nflverse results (P7) instead of trusting the thread. Red flags: figures unverified.

**N9. r/algobetting, "how are you actually using ChatGPT/LLMs for sports..."**
https://www.reddit.com/r/algobetting/comments/1wpzcsh/how_are_you_actually_using_chatgptllms_for_sports/
Claim: raw models invent traded or injured players and fail betting arithmetic; keep them to coding and to summarizing structured data. Primary: none. Red flags: none seen. The same post also appears in r/ChatGPTPromptGenius (https://www.reddit.com/r/ChatGPTPromptGenius/comments/1wpze0o/how_are_you_actually_using_chatgptllms_for_sports/); it is counted once.

**N10. r/sportsanalytics, "I built an end-to-end NFL analytics platform for..."**
https://www.reddit.com/r/sportsanalytics/comments/1w73gwn/i_built_an_endtoend_nfl_analytics_platform_for/
Claim: a simple quarterback- and injury-adjusted Elo beats complex machine learning out of sample, and time-ordered splits prevent leakage. Primary: none. Red flags: project showcase; "beats" is unverified.

**N11. r/sportsanalytics, "NFL analytics: linear models achieving up to 53.8..."**
https://www.reddit.com/r/sportsanalytics/comments/1k11chp/nfl_analytics_linear_models_achieving_up_to_538/
Claim: -110 odds need 52.4% to break even; the post reports cross-validated accuracy against the spread of 53 to 54% (the slug suggests "up to 53.8%"). Primary: the break-even arithmetic checks (110 / 210 = 52.38%); the accuracy figure is [UNVERIFIED]. Red flags: **"up to"** means the best of several models, and a 1.4-point margin is under half of one season's standard error (about 3 points at 272 games).

**N12. r/sportsbook, "are pro bettors that sell their picks online..."**
https://www.reddit.com/r/sportsbook/comments/41s6nr/are_pro_bettors_that_sell_their_picks_online/
Claim: paid pick sellers fake their records by deleting losing posts, hiding chase staking and doctoring ticket screenshots. Primary: none. Red flags: old thread (about 2016); the **paid-pick scam** is its subject.

**N13. r/sportsbettingzone, "closing line value (CLV): what it is, why sharps..."**
https://www.reddit.com/r/sportsbettingzone/comments/1w77x9s/closing_line_value_clv_what_it_is_why_sharps/
Claim: beating the vig-free closing line of a sharp book over many bets says more about edge than a short win-loss record. Primary: none. Red flags: explainer posts in small betting subs are often written to promote a tool; the "sharp book" benchmark needs a line source the lane does not have.

**N14. r/algobetting, "CLV vs win rate: what actually matters when..."**
https://www.reddit.com/r/algobetting/comments/1rp54ks/clv_vs_win_rate_what_actually_matters_when/
Claim: NFL closing lines are efficient, so the price taken matters more than the win rate, and early-week numbers move before the close. Primary: none. Red flags: the "shop soft books early" part concerns real betting accounts, which this sprint excludes.

**N15. r/propunters, "do you guys track CLV (closing line value)? If so, how"**
https://www.reddit.com/r/propunters/comments/1s40iyp/do_you_guys_track_clv_closing_line_value_if_so_how/
Claim: bettors track picks in a spreadsheet or tracker that compares the entry price with the vig-free close; a seller with a real edge would bet it, not sell it. Primary: none. Red flags: not NFL-specific; tracker apps may be promoted in the thread.

**N16. r/sportsbetting, "what AI is actually good for in betting and what..."**
https://www.reddit.com/r/sportsbetting/comments/1uqjy0x/what_ai_is_actually_good_for_in_betting_and_what/
Claim: chat models invent rosters and injuries when asked to pick NFL games; experienced bettors use them to write data scripts or summarize numbers. Primary: none. Red flags: none seen. Same point as N9, from a second community.

**N17. r/sportsbook, "I built a very simple NFL model that has gone 63..."**
https://www.reddit.com/r/sportsbook/comments/dy4g56/i_built_a_very_simple_nfl_model_that_has_gone_63/
Claim (weak pairing; Gemini attached a general point to a showcase post): models that show 60% or more in a backtest usually got there through overfitting, leakage or correlated inputs, and fail later. Primary: none. Red flags: old thread (about 2019); the title itself is a **short-run record claim**.

**N18. r/sportsbook, "NFL betting strategy for next season w/ research"**
https://www.reddit.com/r/sportsbook/comments/1et1kub/nfl_betting_strategy_for_next_season_w_research/
Claim: margin models fail if they treat every point alike; 3 and 7 matter most, then 4, 6, 10 and 14. Primary: none. The lane can recompute the margin distribution from nflverse results (P7). Red flags: a "strategy" post (about 2024); figures unverified.

**N19. r/sportsbetting, "I built a site that tracks every NFL betting trend"**
https://www.reddit.com/r/sportsbetting/comments/1o8a41d/i_built_a_site_that_tracks_every_nfl_betting_trend/
Claim (weak pairing; the slug is a site showcase): one season (about 272 games) gives noisy results, so trends need several seasons and timestamped lines to mean anything. Primary: none (272 is arithmetic). Red flags: **self-promotion**; "every trend" is a multiple-testing machine, where enough splits searched will always turn up some that look good by chance.

## Primary pages inspected

| ID | Page | What it confirms | What it does not |
|---|---|---|---|
| P1 | [Pine repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/) | `barstate.isconfirmed`; `[1]` plus `lookahead_on`; `lookahead_on` alone "will return data from the future on historical bars, which is dangerously misleading"; `calc_on_every_tick = true` "invalidates backtesting results" | |
| P2 | [Pine alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/) | `alert.freq_once_per_bar` is the default; `alert.freq_once_per_bar_close` fires at bar close; alerts fire on realtime bars only; "There is no panacea; avoiding this type of repainting always entails waiting for confirmed information." | No latency guarantee |
| P3 | [Pine strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/) | Emulator fills from chart data; market orders fill "on the next available tick"; assumed intrabar path; non-standard charts give "unrealistic results" | Only the first 100,000 characters were read; `process_orders_on_close` and default costs not checked |
| P4 | [Webhook alerts](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/) | POST; ports 80 and 443 only; cancelled if the server "takes longer than three seconds"; two-factor sign-in required; no secrets in the body | |
| P5 | [TradingView policies](https://www.tradingview.com/policies/) | Section 3 display-only licence covering alerts and webhooks; section 12 bars automated collection and model training or testing; section 27 limits the MCP Server and bars wiring its alerts to a bot | Not legal advice; read the page |
| P6 | [arXiv 2605.24564](https://arxiv.org/abs/2605.24564) | "Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias in Financial Backtesting with Large Language Models", Weixian Waylon Li, Mengyu Wang, Tiejun Ma, submitted 23 May 2026. Models can carry memory of the test period | Small study: five 7 to 14B models, five large-cap stocks |
| P7 | [nfldata DATASETS.md](https://github.com/nflverse/nfldata/blob/master/DATASETS.md) | `spread_line` (positive means home favored), `total_line` | No sportsbook named; no opening or closing label; no licence on the page |
| P8 | [nflreadr schedules dictionary](https://cloud.r-project.org/web/packages/nflreadr/vignettes/dictionary_schedules.html) | Fields: `spread_line`, `total_line`, moneylines, spread odds, over and under odds | Does not say closing line; names no sportsbook |
| P9 | [nflverse-data repo](https://github.com/nflverse/nflverse-data) | Links a CC-BY-4.0 licence; nflreadr says the data "belong to their respective owners" | Licence text not read |
| P10 | [Binance public data README](https://github.com/binance/binance-public-data) | Bulk candles from 1s to 1mo at data.binance.vision with checksum files | Dataset use is governed by a separate terms file (see P13) |
| P11 | [Kraken OHLC endpoint](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/) | No sign-in needed; intervals from 1 minute to 15 days; "up to 720 of the most recent entries"; the last entry "is for the current, not-yet-committed timeframe" | No terms or rate limit on the page |
| P12 | [Coinbase Exchange candles](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles) | No sign-in needed; 1m, 5m, 15m, 1h, 6h, 1d; 300 candles a request; "No data is published for intervals where there are no ticks"; "Historical rate data may be incomplete" | No terms link on the page. Coinbase's market-data terms page returned 403 and was not retried |
| P13 | [Binance Vision dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) | Version 1.0, last updated 26 August 2026. Licence is CC BY-NC-SA 4.0. Permitted uses include "algorithmic historical backtesting for purely personal non-production research." Live trading execution and commercial use are barred. Derived files need attribution and the same licence | It pulls in Binance's general Terms of Use, which were not read and may hold eligibility rules. Not legal advice |
| P14 | [yfinance README](https://github.com/ranaroussi/yfinance) | Not affiliated with or vetted by Yahoo; "intended for research and educational purposes"; says Yahoo's API is for personal use only; points to Yahoo's terms | Yahoo's own terms not read |
| P15 | [Alpaca market data docs](https://docs.alpaca.markets/docs/about-market-data-api) | Keys are needed except for historical crypto data; the free plan covers IEX only for equities and leaves out the latest 15 minutes | Alpaca's terms not read |
| P16 | [Deflated Sharpe Ratio paper, title page and abstract](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) | "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", David H. Bailey and Marcos Lopez de Prado, first version 15 April 2014, this version 31 July 2014, marked as forthcoming in the Journal of Portfolio Management. Abstract: the measure "corrects for two leading sources of performance inflation", selection bias under multiple testing and non-normal returns | Title page and abstract only; the formula and results were not read |
| P17 | [Probability of Backtest Overfitting paper, title page](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) | "The Probability of Backtest Overfitting", David H. Bailey, Jonathan M. Borwein, Marcos Lopez de Prado and Qiji Jim Zhu, dated 27 February 2015 ("Revised version: February 2015") | Title page only; no journal is named on it; the method was not read |
| P18 | [nflverse-data licence file](https://github.com/nflverse/nflverse-data/blob/master/LICENSE.md) | Creative Commons Attribution 4.0 International: credit the source, link the licence and say if you changed anything; no non-commercial limit | The file does not list which data it covers, and nflreadr says the data belong to their respective owners (P9), so it may not cover the betting lines themselves. Not legal advice |
| P19 | [Pine strategies, characters 100,000 to 200,000](https://www.tradingview.com/pine-script-docs/concepts/strategies/) | `process_orders_on_close` is off by default; when on, the emulator "can fill orders created on a bar's close immediately". `calc_on_order_fills` is off by default. With no commission set, "the strategy applies no commission to filled orders". Some settings "may produce misleading backtest results" | Default slippage and margin were not found in this part |
| P20 | [Pine strategies, from character 200,000](https://www.tradingview.com/pine-script-docs/concepts/strategies/) | Slippage: "The default argument is 0". `margin_long` and `margin_short`: "The default argument for both parameters is 100". A "Commission demo" example sets `commission_value = 1`, which gives 1% per fill for that script. The page also describes `strategy.risk.*` commands and has notes on look-ahead bias, selection bias and overfitting | The reading tool first reported the 1% as a built-in default. The sentence sits in the example, so P19's "no commission" stands; check the page before relying on either. Bar magnifier text was not in this part |
| P21 | [TradingView webhooks help page](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/) | A request that "takes longer than three seconds to process" is cancelled; "only ports 80 and 443 are accepted"; webhooks need two-factor authentication; the page warns against putting credentials in the body | Retries are not mentioned, so the threads' "retry" claims are unverified |

## Free bar data for the paper runner (tvbot)

The runner cannot use TradingView values (P5 and the sprint rule). Where each candidate stands:

- **Binance bulk files (P10, P13): dataset terms read.** They list personal, non-production historical backtesting as a permitted use and bar live trading execution and any commercial use. Derived files need attribution and the same CC BY-NC-SA 4.0 licence. Good for long replays, with checksum files. Open point: the terms pull in Binance's general Terms of Use, which were not read and may limit who can use the site.
- **Kraken public OHLC (P11): terms not read.** No account or key. Only the latest 720 candles per interval, so it suits forward paper runs, not long replays. Always drop the last row; it is the unfinished candle.
- **Coinbase Exchange public candles (P12): terms not read.** The market-data terms page returned 403 and was not retried. No account or key. Gaps are real (no trades, no candle), so the runner must handle missing bars.
- **yfinance (P14; leads D2, D3, D5).** Unofficial. Its README says research, education and personal use, and points to Yahoo's terms (not read). Leads report gaps, blocks and schema breaks. Not a first choice.
- **Alpaca (P15; leads D1, D3).** Equities data needs an account and keys, which the sprint limits exclude. Only keyless historical crypto could fit, and its terms were not read.
- **Stooq, Dukascopy, Histdata (leads D2, D4).** Named in threads only; terms not checked [UNVERIFIED].
- **Practice (lead D7).** Pull once, store the file locally, record the source, pull time and a checksum, and replay from the stored file.
- Synthetic bars remain the safe default. Binance bulk files are the only source here whose dataset terms were read and name personal backtesting as allowed. That is a reading of the terms, not legal advice, and Codex owns the call.

## Next in this file

Research stopped after batch 5. Method, query counts and coverage limits are in `STATUS.md` in this folder. Known gaps: r/quantresearch has one lead here (T61) besides the thread Codex used; r/BitcoinMarkets has two weak leads, because its discussion sits mostly in daily megathreads, which are not listed; this worker read no Reddit thread directly (Codex read T1, T2 and T6).
