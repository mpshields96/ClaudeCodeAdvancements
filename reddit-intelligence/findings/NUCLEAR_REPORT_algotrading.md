# Nuclear Deep-Dive Report: r/algotrading Top Year
Generated: 2026-03-16
Posts scanned: 98 of 98 | Sessions used: 1 | COMPLETE

## Summary Stats
| Metric | Count |
|--------|-------|
| Posts fetched | 100 |
| Already reviewed | 2 |
| BUILD | 0 |
| ADAPT | 0 |
| REFERENCE | 4 |
| REFERENCE-PERSONAL | 3 |
| FAST-SKIP | 91 |
| Polybot-relevant | 3 |

## Key Finding: r/algotrading is domain-specific, low CCA overlap

This subreddit is dominated by:
- Individual strategy showcases (backtests, live results) ~40%
- Career/learning questions ~15%
- Memes/humor about overfitting/losses ~10%
- LLM/AI trading discussions ~10%
- Prediction market specific ~5%
- Infrastructure/tools ~10%
- Books/roadmaps ~10%

For CCA frontiers: 0 BUILD, 0 ADAPT. The AI/agent posts are interesting architecturally but don't translate to CCA features. However, 3 posts are directly useful for Polybot prediction market work.

**Recommendation: Do NOT re-scan r/algotrading for CCA.** Signal is off-domain. For Polybot, monitor prediction-market tagged posts only (via /cca-scout with keyword filter).

## Polybot-Relevant Findings (ranked by actionability)

### 1. PMXT: Open-Source Prediction Market Data (680 pts) — CRITICAL for Polybot
- **What:** Free historical orderbook data for Polymarket (Kalshi coming soon)
- **Repo:** github.com/pmxt-dev/pmxt
- **Data:** archive.pmxt.dev/Polymarket — every orderbook event captured, Parquet format
- **Cost savings:** DomeAPI $40/mo, Telonex $79/mo — PMXT is FREE
- **Coming:** Part 2 (Kalshi + Limitless + Opinion), Part 3 (trade-level data)
- **Action:** Integrate PMXT as Polybot data source for backtesting and live monitoring
- URL: https://www.reddit.com/r/algotrading/comments/1rdhw2n/

### 2. Kalshi-Polymarket Arbitrage Bot (369 pts) — Strategy Reference
- **What:** Open-source synthetic arb bot using PMXT
- **Repo:** github.com/realfishsam/prediction-market-arbitrage-bot
- **Strategy:** Buy YES on one platform, NO on other when spread widens. Active convergence, not hold-to-maturity
- **Reality check:** Kalshi fees eat most 2c spread. Legging risk real. $250→$5k anecdote on Kalshi SPX hourly
- **Key:** Polymarket US app coming with API access
- URL: https://www.reddit.com/r/algotrading/comments/1qebxud/

### 3. 5-Cent Arb Spreads (142 pts) — Execution Patterns
- **What:** More arb examples with same PMXT library
- **Key insight:** 0.3% per 15-min interval on Kalshi, 95% win rate but 5% losses > gains without safeguards
- **Security warning:** Some prediction market repos contain private key exfiltration — Claude Code catches this
- URL: https://www.reddit.com/r/algotrading/comments/1q83w3d/

## REFERENCE Findings (general knowledge)

### LLM Trading Limitations (2 posts, 167 + 256 pts)
- predictionarena.ai: All LLMs lost money (Gemini 3 Pro: -30%)
- LLMs encode "midwit consensus" which is already priced in
- Better AI use: alternative data processing, regime detection — not raw prediction
- "Brought an LLM to an ML fight" — LLMs are wrong tool for trading
- URLs: /comments/1rtgsff/ and /comments/1p6a95y/

### Multi-Agent Trading System (188 pts)
- PrimoAgent: 4 LangGraph agents (data, TA, news NLP, portfolio)
- Requires 4 APIs — interesting architecture but high dependency count
- URL: /comments/1nf6ghg/

### Research Agent Quality Loop (183 pts)
- Quality evaluator pattern: if analysis weak, auto-fetch more data, rebuild report
- PocketQuant: stock research agent with sector-specific "playbooks"
- URL: /comments/1l82has/

## Recurring Patterns
| Pattern | Mentions | Relevance |
|---------|----------|-----------|
| "If it made money you wouldn't share it" | 8+ | Social proof skepticism |
| Overfitting/survivorship bias | 6+ | Trading fundamental |
| LLMs bad at trading | 4 | Validates specialized tools > general LLMs |
| Prediction market arb is thin | 3 | Execution > strategy for Polybot |
| Fees destroy theoretical alpha | 5 | Must model fees in Polybot |

## Recommendations for Polybot
1. **Integrate PMXT** — free orderbook data, replaces paid DomeAPI ($40/mo savings)
2. **Model Kalshi fees explicitly** — taker fee formula: `round_up(0.07 * C * P * (1-P))`
3. **Don't use LLMs for raw price prediction** — use for research/analysis, not trading decisions
4. **Quality evaluator loop** from research agent — apply to Polybot market research phase
5. **Security scan all open-source trading repos** — exfiltration risk is real

## Tools/Repos Discovered
| Tool | URL | Relevance |
|------|-----|-----------|
| PMXT | github.com/pmxt-dev/pmxt | Prediction market unified API |
| Arb Bot | github.com/realfishsam/prediction-market-arbitrage-bot | Cross-platform arb |
| PrimoAgent | github.com/ivebotunac/PrimoAgent | Multi-agent trading (LangGraph) |
| mcp-agent | github.com/lastmile-ai/mcp-agent | MCP financial analyzer |
| PocketQuant | pocket-quant.com | Stock research agent |
| Adanos Sentiment | adanos.org/polymarket-stock-sentiment | Polymarket sentiment tracker |
| ArbTerminalAI | x.com/ArbTerminalAI | Cross-platform arb scanner |
| Implied Data | implied-data.com | Prediction market dashboard |
