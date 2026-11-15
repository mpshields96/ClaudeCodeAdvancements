# Community research status (R3)

Worker: community research (Claude). Written after the 22:28:59Z clock check on November 14, 2026 (`date -u`). Research has stopped. Nothing was committed, and this worker wrote only inside `nov14-sprint/reddit/`.

## Result

- `LEADS.md` holds **92 Reddit leads across 25 communities**: 73 for the trading bot (T1 to T65, D1 to D8) and 19 for NFL (N1 to N19).
- It also holds **21 primary pages** that were opened and read (P1 to P21), a top-5 list per lane with a "how to use it" line each, and a section on free bar data and its terms.
- An earlier count of 87 leads and 24 communities is out of date. Batch 5 (22:27Z) added T61 to T65, including the first r/quantresearch lead.

## R3 pass check

| R3 wording | Status | Evidence |
|---|---|---|
| "Over 25 distinct leads across at least 5 communities" | Met | 92 lead entries, 93 distinct post IDs (one is a cross-post shown inside N9), 25 communities |
| "every claim is cited or labeled unverified" | Met, with the limits below | Every entry has its Reddit URL, is labeled a lead, and has a "Primary:" line that says what a primary page confirms or "none". Papers that were not opened carry [UNVERIFIED] |
| "no 403 bypass" | Met | No request was sent to reddit.com. No proxy, mirror, alternate front-end, scraper or user-agent trick was used. The one 403 seen (a Coinbase legal page) was not retried |

Matthew's words for R3: "research for trading bot on reddit heavily, similar subreddits like algotrading and AI trading". 73 of the 92 leads are for the trading bot. r/algotrading has 28 and r/ai_trading has 8.

## Leads per community

Counted from the URL line of each entry.

| Lane | Community (leads) |
|---|---|
| Trading bot | r/algotrading 28, r/ai_trading 8, r/TradingView 6, r/Daytrading 6, r/pinescript 4, r/quant 3, r/algotradingcrypto 2, r/algorithmictrading 2, r/CryptoTradingBot 2, r/ClaudeAI 2, r/BitcoinMarkets 2, and one each in r/quantresearch, r/quantfinance, r/vibecoding, r/learnmachinelearning, r/buildinpublic, r/TradeAutomationHub, r/IndiaAlgoTrading, r/BuildWithClaude |
| NFL | r/algobetting 10, r/sportsbook 3, r/sportsbetting 2, r/sportsanalytics 2, and one each in r/sportsbettingzone and r/propunters |

Every community named in the brief has at least one lead. The thin ones are r/quantresearch (one lead, T61, besides the thread Codex used) and r/BitcoinMarkets (two leads, both weak pairings; its discussion sits mostly in daily megathreads, which are not listed).

## What was checked at source

- **Reddit threads read at source: three, by Codex.** Codex opened T1, T2 and T6 at 21:34Z (`codex/Reddit_Source_Check.md`). It reports that the posts support the engineering ideas and that each author's figures stay self-reported.
- **Reddit threads read by this worker: none.** Reddit returns 403 from this Mac and the brief forbids going around it.
- **Primary pages read by this worker: 21** (the "Primary pages inspected" table in `LEADS.md`). They are TradingView's Pine documentation, terms and webhook help page, exchange market-data documentation, the nflverse documentation and licence file, one arXiv paper, and the title pages of the two overfitting papers.
- The top-5 items say which of their points rest on a primary page and which rest on threads alone.

## Method

1. WebSearch cannot return Reddit threads here: it refuses a reddit.com domain filter, and unfiltered searches returned none.
2. Thread discovery therefore used the `gemini-public-research` tool (Google Search through Gemini), with public questions only.
3. Gemini returns Google redirect links. For each one I read the `Location` header from Google and did not follow it, so the only host contacted was `vertexaisearch.cloud.google.com`. That gave the real Reddit URL. Codex should judge whether this fits the "as search returned it" rule. I read it as taking a search result's link target, and no Reddit page was fetched.
4. Each lead's claim is Gemini's short summary of the thread. Each title comes from the URL slug or from Gemini.
5. Claims that matter to the lanes were then checked against primary pages with WebFetch.

## Calls made

| Tool | Calls | Outcome |
|---|---|---|
| WebSearch | 14 | 8 refused (reddit.com filter); 6 ran and returned no Reddit threads |
| Gemini public research | 14, plus 1 through a subagent | 13 answered; 1 refused because another request was running; the subagent attempt failed |
| WebFetch | 23 | 20 usable; 1 HTTP 403 (Coinbase legal page); 2 PDFs it could not read |
| Read tool on saved PDF pages | 3 | Title pages of the two overfitting papers |
| Redirect lookups (Google only, not followed) | 95 | 83 gave thread links used in the file; 12 were dropped (duplicates, Codex's thread, one expired link, one listing page, one megathread, one thread with no claim attached) |

## What is not verified

- **Thread content.** 89 of the 92 threads were opened by no one. Their claims are Gemini's summaries and may be wrong or generic.
- **Ten links.** T4, T5, T10, T13, T16, T26, T27, T28, T29 and T34 (all r/algotrading) carry a URL that Gemini wrote in its answer text, with no redirect lookup behind it. In the last sweep, all six URLs Gemini wrote that way had a wrong post ID. Any of these ten may open the wrong thread. They are named at the top of `LEADS.md`.
- **Claim-to-thread pairing.** Where the claim and the title do not clearly match, the entry says so ("weak pairing" or similar wording). Gemini's subreddit labels were often wrong; the file uses the subreddit in the resolved URL.
- **Dates.** No thread date was confirmed. Dates are Gemini's or are hints from the post ID.
- **Authors' numbers.** Every return, win rate, fee share and trade count in a thread is self-reported.
- **Papers.** The Deflated Sharpe Ratio and backtest-overfitting papers were confirmed by title page only; their formulas were not read. The AQuA work (T52) and the study behind T51 were not found or opened and are marked [UNVERIFIED].
- **Primary pages.** WebFetch reads a page through a small summarizing model, so the short quotes in the table were not seen as raw page text by me.
- **TradingView commission default.** Two readings of the same page disagree. P19 quotes that a strategy with no commission set "applies no commission to filled orders". A later part (P20) was first reported as a 1% built-in default, but that sentence sits beside an example script that sets 1% itself. P19 stands for now. The lane's instruction is the same either way: set commission and slippage explicitly.
- **Webhook retries.** TradingView's webhook page confirms the three-second cancel and says nothing about retries, so "retries cause duplicate orders" is unverified.
- **Terms not read.** Coinbase market-data terms (403), Kraken API terms, Binance's general Terms of Use, Yahoo, Alpaca, Stooq, Dukascopy and Histdata terms, and the Kaggle NFL lines file and its licence. The terms readings that are in the file are not legal advice, and Codex owns the call.

## Coverage limits

- Gemini takes one request at a time and some of its sub-searches errored (r/sportsbetting once, r/Daytrading once, and one crypto data-source query), so coverage depends on what Google surfaced on the day.
- Redirect links expire; one did and was dropped.
- Codex's seven threads (IDs listed at the top of `LEADS.md`) are not repeated in the 92.
- The TikTok ideas in `codex/TikTok_Early.txt` are not listed here. They would not count toward the Reddit total.
- Webhook-to-bot threads (T24, T55, T56, T57) are context only. Under the sprint's reading of TradingView's terms, TradingView values must not feed an external model or the paper ledger.
- Leads about live trading, leverage, perpetual futures or broker accounts are kept only for the transferable safeguard. None is a suggestion to do those things.

## Unexpected states

Nothing forced a stop. Three things a reviewer should know: the ten unconfirmed links, the TradingView commission reading, and Gemini's wrong post IDs and subreddit labels. All three are described above.

## Files

- `nov14-sprint/reddit/LEADS.md`: the leads, top-5 lists, primary-page table and free bar data section.
- `nov14-sprint/reddit/STATUS.md`: this file.
- `nov14-sprint/reddit/REAL_DATA_SOURCES.md` (line added 2026-11-15T09:35:32Z at wrap; this file was written before it existed): real-bar data sources for the trading bot, with "Addendum 06:00Z" at line 227 (exact Twelve Data terms wording and a key-in-header request; no ruling made, request never run, no real bars fetched). Passed to the TradingView lane at 09:31Z on November 15 (queued, not confirmed read). Nothing of this worker's is open.
- Hand-over status, checked 2026-11-15T09:45:00Z: the parent session marked the 09:31Z hand-over "confirmed by content" at 09:44Z. What the lane's files show: `nov14-sprint/tvbot/STATUS.md` (last written 06:40:30Z, before the hand-over) cites `REAL_DATA_SOURCES.md` at line 171, and its lines 82 to 84 still list header auth as awaited. The answer (Twelve Data documents a key header) is in this folder's addendum and has not been copied into the lane's files. The lane's `START_TONIGHT.md` (09:43:33Z) carries no Twelve Data fetch command, so the gap changes nothing a person would run today. The 09:31Z message itself was queued and not confirmed read.
