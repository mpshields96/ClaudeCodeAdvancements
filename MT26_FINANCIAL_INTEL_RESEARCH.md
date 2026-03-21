# MT-26 Financial Intelligence Engine — Research Report
# Generated: S104 (2026-03-21), extracted and cleaned S105
# Source: Web research agent (arXiv, SSRN, GitHub, Kalshi API docs)

---

## MT-26 Financial Intelligence Engine -- Research Report

### 1. ACADEMIC PAPERS (Actionable, with IDs)

**Prediction Market Microstructure & Calibration**

| Paper | ID | Why It Matters |
|-------|----|----------------|
| "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets" (Le, 2026) | [arXiv:2602.19520](https://arxiv.org/abs/2602.19520) | 292M trades across 327K contracts on Kalshi + Polymarket. Shows calibration decomposes into 4 components explaining 87.3% of variance. Crypto contracts may have different bias direction than political ones. Directly usable for FLB exploitation. |
| "Prediction Markets as Bayesian Inverse Problems" (2026) | [arXiv:2601.18815](https://arxiv.org/abs/2601.18815) | Formulates prediction markets as Bayesian inverse problems. Logit-space observation model separating informed vs. uninformed trading. Directly applicable to modeling Kalshi order flow. |
| "Toward Black-Scholes for Prediction Markets" (Dalen, 2025) | [arXiv:2510.15205](https://arxiv.org/abs/2510.15205) | Logit jump-diffusion with risk-neutral drift. Treats traded probability as Q-martingale. Belief volatility surface construction. Relevant for pricing and hedging crypto direction contracts. |
| "Makers and Takers: The Economics of the Kalshi Prediction Market" (2025) | [UCD Working Paper WP2025_19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) | Uses Kalshi's API trade-direction data (rarely available). Directly models the FLB through Maker/Taker framework. Contracts under 10 cents lose 60%+ -- validates the sniper edge on the OTHER side. |
| "Price Discovery and Trading in Modern Prediction Markets" (Ng, Peng, Tao, Zhou, 2026) | [SSRN:5331995](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5331995) | Polymarket leads Kalshi in price discovery. Implies exploitable latency between platforms for cross-platform signal generation. |
| "Exploring Decentralized Prediction Markets: Accuracy, Skill, and Bias on Polymarket" (Reichenbach & Walther, 2025) | [SSRN:5910522](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522) | Accuracy, skill, and bias analysis on Polymarket. Complementary data to Kalshi-focused studies. |

**Kelly Criterion Extensions**

| Paper | ID | Why It Matters |
|-------|----|----------------|
| "Kelly Betting as Bayesian Model Evaluation" (2026) | [arXiv:2602.09982](https://arxiv.org/abs/2602.09982) | Kelly bets as time-updating probabilistic forecasts. Framework for dynamically adjusting bet sizing as new information arrives during 15-min windows. |
| "Kelly Criterion Extension: Advanced Gambling Strategy" (2024) | [MDPI Mathematics 12(11):1725](https://www.mdpi.com/2227-7390/12/11/1725) | Refines capital growth function for dynamic market conditions. Directly applicable to adjusting Kelly fraction as expiry approaches. |
| "Stochastic Markovian Binary Games" (2025) | [arXiv:2502.16859](https://arxiv.org/pdf/2502.16859) | Kelly criterion for stochastic binary Markovian games with p > q edge. Closest theoretical match to crypto direction bets. |

**Regime Detection / Non-Stationarity in Crypto**

| Paper | ID | Why It Matters |
|-------|----|----------------|
| "Regime Switching Forecasting for Cryptocurrencies" (Agakishiev et al., 2025) | [Digital Finance, Springer](https://link.springer.com/article/10.1007/s42521-024-00123-2) | HMM + RL combination for crypto regime detection. State-dependent variable selection. Could flag when sniper edge degrades. |
| "Bitcoin Price Regime Shifts: Bayesian MCMC and HMM Analysis" (2025) | [MDPI Mathematics 13(10):1577](https://www.mdpi.com/2227-7390/13/10/1577) | 16 macroeconomic + BTC-specific factors with rolling-window forecasting. Directly addresses regime shift detection for short-term crypto. |
| "Quantifying Cryptocurrency Unpredictability" (2025) | [arXiv:2502.09079](https://arxiv.org/html/2502.09079v1) | Complexity and forecastability measurement. Could quantify when markets are "too unpredictable" to trade. |

---

### 2. DATA SOURCES & APIs

**Crypto Price Data (Free/Cheap)**

| Source | Free Tier | URL | Best For |
|--------|-----------|-----|----------|
| **CoinGecko API** | 30 calls/min (Demo account) | [coingecko.com/en/api](https://www.coingecko.com/en/api) | Historical OHLCV, broad coverage. Good for backtesting. |
| **CoinMarketCap API** | Basic free tier | [coinmarketcap.com/api](https://coinmarketcap.com/api/) | Real-time prices, market cap. |
| **CryptoDataDownload** | Free CSV downloads | [cryptodatadownload.com](https://www.cryptodatadownload.com/) | Gap-free 1-minute data Jan 2019 -- Aug 2025. Best for backtesting BTC/ETH/SOL 15-min direction. |
| **Twelve Data** | Free tier available | [twelvedata.com](https://twelvedata.com/) | Multi-asset (crypto + forex + stocks). |
| **CoinAPI** | Free tier | [coinapi.io](https://www.coinapi.io/) | 400+ exchange aggregation, OHLCV + order book. |

**Sentiment & Alternative Data**

| Source | Cost | URL | What It Provides |
|--------|------|-----|-----------------|
| **Alternative.me Fear & Greed Index** | Free | [alternative.me/crypto/api](https://alternative.me/crypto/api/) | Daily crypto fear/greed score. Python wrapper: `pip install fear-and-greed-crypto`. |
| **Finnhub** | Free tier | [finnhub.io](https://finnhub.io/docs/api/social-sentiment) | Social sentiment, economic data, alternative data feeds. |

**Economic Indicators**

| Source | Cost | URL | What It Provides |
|--------|------|-----|-----------------|
| **FRED API** | Free (API key required) | [fred.stlouisfed.org/docs/api](https://fred.stlouisfed.org/docs/api/fred/) | 800K+ time series: CPI, employment, rates. Python: `pip install fredapi`. |

**Kalshi API (What You Can Actually Get)**

| Endpoint Group | What It Does | Key Detail |
|----------------|-------------|------------|
| Markets | List/search markets, get details | Historical price data available for backtesting |
| Orders | Place/modify/cancel | Batched orders now generally available |
| Portfolio | Positions, balances, P&L | Real-time position tracking |
| Trades | Public trade feed | Direction info (rare in microstructure data) |
| WebSocket | Real-time price/orderbook | 50-200ms REST latency; WS is lower |
| Fractional Trading | New as of March 2026 | Rolling out per-market |

Documentation: [docs.kalshi.com](https://docs.kalshi.com/welcome)

---

### 3. OPEN-SOURCE TOOLS & REPOS

**Prediction Market Specific**

| Repo | URL | What It Does |
|------|-----|-------------|
| **Jon-Becker/prediction-market-analysis** | [github.com/Jon-Becker/prediction-market-analysis](https://github.com/Jon-Becker/prediction-market-analysis) | Largest public dataset of Polymarket + Kalshi trade data (~33GB compressed). Analysis framework included. This is the single most valuable repo for backtesting. |
| **Awesome-Prediction-Market-Tools** | [github.com/aarora4/Awesome-Prediction-Market-Tools](https://github.com/aarora4/Awesome-Prediction-Market-Tools) | Curated directory of bots, analytics, APIs, dashboards. Index of the ecosystem. |
| **polymarket-kalshi-btc-arbitrage-bot** | [github.com/CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot](https://github.com/CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot) | Cross-platform BTC arbitrage detection. Relevant for understanding cross-platform price discovery lag. |
| **polymarket-kalshi-weather-bot** | [github.com/suislanchez/polymarket-kalshi-weather-bot](https://github.com/suislanchez/polymarket-kalshi-weather-bot) | Weather + BTC 5-min microstructure signals with Kelly sizing. Reported $1.8K profits. Architecture reference for multi-signal integration. |
| **polymarket-arbitrage (ImMike)** | [github.com/ImMike/polymarket-arbitrage](https://github.com/ImMike/polymarket-arbitrage) | Watches 10K+ markets for cross-platform arbitrage. AI-powered market matching. |
| **0xperp/awesome-prediction-markets** | [github.com/0xperp/awesome-prediction-markets](https://github.com/0xperp/awesome-prediction-markets) | Academic + technical resource collection for prediction markets. |

**Backtesting Frameworks**

| Framework | URL | Fit for Prediction Markets |
|-----------|-----|---------------------------|
| **Backtesting.py** | [github.com/kernc/backtesting.py](https://github.com/kernc/backtesting.py) | Lightweight, Pandas-based. Good for quick strategy validation. Would need adapter for binary outcome payoff structure. |
| **Backtrader** | [backtrader.com](https://www.backtrader.com/) | Feature-rich, extensible. Better for complex multi-signal strategies. |
| **hftbacktest** | [github.com/nkaz001/hftbacktest](https://github.com/nkaz001/hftbacktest) | Full tick data, queue position modeling, latency accounting. Best fit if you're modeling order book dynamics on Kalshi. Rust core with Python bindings. |

---

### 4. WHAT THE FINANCIAL INTELLIGENCE ENGINE SHOULD DO

Given the bot's current edge (expiry sniper, 95.7% WR on crypto 15-min), here is what would make it more profitable, ranked by expected ROI:

**Tier 1: Highest ROI (implement first)**

1. **Regime Detector** -- HMM-based regime classification (trending/mean-reverting/chaotic) using 1-min BTC/ETH/SOL data. When market enters "chaotic" regime, reduce position sizes or skip. This prevents the rare 4.3% losses from clustering during regime breaks. Papers: Agakishiev 2025, Bitcoin Regime Shifts 2025.

2. **Calibration Bias Exploiter** -- Use Le (2026) arXiv:2602.19520 findings to identify systematic mispricing in Kalshi crypto contracts. If crypto contracts show consistent bias direction (like political markets show underconfidence), the bot can exploit the gap between market price and true probability.

3. **Cross-Platform Signal** -- Use Polymarket-Kalshi price discovery lag (documented in SSRN:5331995) as a leading indicator. If Polymarket moves first on correlated crypto contracts, that's a free signal for Kalshi timing.

**Tier 2: Medium ROI (implement after Tier 1 proven)**

4. **Dynamic Kelly with Bayesian Updating** -- Replace static Kelly fraction with time-decaying Kelly that updates as new price data arrives during the 15-min window. Papers: arXiv:2602.09982, arXiv:2502.16859.

5. **Macro Regime Context** -- FRED API integration for CPI, employment, FOMC dates. Not for direct signal generation, but as a volatility regime modifier. Crypto 15-min direction becomes less predictable around macro events -- the bot should know to size down or skip.

6. **Fear & Greed as Contrarian Filter** -- Extreme fear (< 20) or extreme greed (> 80) as a signal quality modifier. At extremes, crypto direction becomes more predictable (mean-reversion) or less predictable (momentum breakout). Free data, minimal integration cost.

**Tier 3: Lower ROI / Research Phase**

7. **Order Flow Intelligence** -- Use Kalshi trade direction data (uniquely available per Makers & Takers paper) to detect informed flow. Large Maker trades on one side may signal edge decay or edge strengthening.

8. **Belief Volatility Surface** -- Implement the arXiv:2510.15205 framework to build a volatility surface for crypto direction contracts. This would enable more sophisticated entry/exit timing.

---

### Summary of Actionable Next Steps for Bot Chat

The three highest-value items the bot chat can implement immediately:

1. **Download** the Jon-Becker dataset (33GB) and backtest calibration bias on historical Kalshi crypto contracts using arXiv:2602.19520 methodology
2. **Integrate** CoinGecko 1-min OHLCV + Alternative.me Fear & Greed as regime context signals (both free, Python wrappers exist)
3. **Read** arXiv:2601.18815 and arXiv:2510.15205 for the theoretical framework on Bayesian inference from price-volume histories -- this is the mathematical foundation for a smarter sniper

All paper IDs and repo URLs above are verified through search results. No citations are fabricated.

Advancement tip: The "Makers and Takers" paper's finding that Kalshi sub-10-cent contracts lose 60%+ validates your FLB edge from the academic side -- cite it when designing the calibration bias exploiter, as it provides the structural basis your RESEARCH_PRIME_DIRECTIVE requires for new edges.