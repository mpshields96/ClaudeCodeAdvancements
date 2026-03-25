# MT-37 Phase 1: Academic Foundation — Literature Review

**Status:** IN PROGRESS
**Phase:** 1 of 7 (Deep Academic Research Survey)
**Estimated Sessions:** 3-5
**This Session:** Areas 1-3 of 10 (Modern Portfolio Theory, Factor Models, Risk Parity)
**Rigor Standard:** Structural basis + math validation + 20yr backtest + statistical significance

---

## Progress Tracker

| # | Area | Key Works | Status |
|---|------|-----------|--------|
| 1 | Modern Portfolio Theory | Markowitz 1952, Sharpe 1964, Black-Litterman 1992 | COMPLETE |
| 2 | Factor Models | FF 3-factor 1993, Carhart 4-factor 1997, FF 5-factor 2015 | COMPLETE |
| 3 | Risk Parity | Qian 2005/2016, Bridgewater All Weather, Maillard et al. 2010 | COMPLETE |
| 4 | Momentum & Value | Asness et al. 2013, AQR research | NOT STARTED |
| 5 | Behavioral Finance | Kahneman & Tversky 1979, Shiller 2000, Thaler 2015 | NOT STARTED |
| 6 | Tax-Loss Harvesting | Constantinides 1983, Berkin & Ye 2003 | NOT STARTED |
| 7 | Retirement Planning | Bengen 1994, Kitces 2008, ERN 2017 | NOT STARTED |
| 8 | Kelly Criterion (Long-Horizon) | Thorp 2006, MacLean et al. 2011 | NOT STARTED |
| 9 | Index Investing | Bogle 2007, Sharpe 1991 | NOT STARTED |
| 10 | Alternative Risk Premia | Ilmanen 2011, Ang 2014 | NOT STARTED |

**Papers synthesized so far:** 15 of 50+ target

---

## Area 1: Modern Portfolio Theory

The theoretical foundation for all quantitative portfolio construction. Three landmark
papers define the progression: Markowitz establishes mean-variance optimization (1952),
Sharpe derives an equilibrium pricing model from it (1964), and Black-Litterman fixes
the practical problems that made Markowitz unusable in production (1992).

### 1.1 Markowitz (1952) — Portfolio Selection

| Field | Detail |
|-------|--------|
| **Title** | Portfolio Selection |
| **Authors** | Harry Markowitz |
| **Year** | 1952 |
| **Journal** | The Journal of Finance, Vol. 7, No. 1, pp. 77-91 |
| **DOI** | 10.1111/j.1540-6261.1952.tb01525.x |
| **URL** | https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1952.tb01525.x |

**Core Thesis:**
Investors should select portfolios based on the trade-off between expected return (mean)
and risk (variance of return), not by maximizing expected return alone. By combining
assets with imperfect correlations, investors can construct portfolios on an "efficient
frontier" — the set of portfolios offering maximum expected return for each level of
variance. This was the first formal mathematical treatment of diversification.

**Key Contributions:**
- Formalized portfolio selection as a quadratic optimization problem
- Introduced the efficient frontier concept
- Demonstrated that diversification reduces risk only when asset correlations are < 1
- Showed that optimal portfolios depend on the full covariance matrix, not just individual variances

**Practical Implications for Portfolio Construction:**
- Diversification across imperfectly correlated assets is the only "free lunch" in finance
- The investor's job is to find their preferred point on the efficient frontier
- Asset allocation (the mix of asset classes) matters more than security selection
- Covariance estimation is critical — portfolio composition changes dramatically with inputs

**Out-of-Sample Evidence:**
The theoretical framework is universally accepted. However, the practical implementation
via sample-based mean-variance optimization performs poorly out of sample. DeMiguel,
Garlappi, and Uppal (2009) showed that none of 14 optimization methods consistently beat
a naive 1/N equal-weight portfolio in terms of Sharpe ratio, certainty-equivalent return,
or turnover across seven empirical datasets. The estimation window needed for sample-based
MVO to outperform 1/N is approximately 3,000 months for 25 assets and 6,000 months for
50 assets — far exceeding available data history.

**Key Criticisms and Limitations:**
1. **Estimation error dominance ("error maximizer"):** MVO overweights assets with large
   estimated returns, small variances, and negative correlations — precisely the estimates
   most likely to be contaminated by noise. Small changes in inputs produce large changes
   in optimal weights, making the output unstable and impractical.
2. **Extreme portfolio weights:** Unconstrained MVO produces extreme long/short positions
   that portfolio managers cannot implement.
3. **Variance is a flawed risk measure:** Penalizes upside and downside equally. Most
   investors care about downside risk (semivariance, CVaR) more than upside.
4. **Assumes normal returns:** Real asset returns exhibit fat tails, skewness, and
   time-varying volatility — all violating the Gaussian assumption.
5. **Static single-period model:** Does not account for rebalancing, transaction costs,
   taxes, or multi-period dynamics.

**Verdict for MT-37:** The conceptual framework (diversification, efficient frontier) is
foundational and correct. The naive implementation (sample MVO) is unusable in practice.
Must be augmented with shrinkage estimators, Bayesian priors (Black-Litterman), or
constraints to produce implementable portfolios.

---

### 1.2 Sharpe (1964) — Capital Asset Pricing Model (CAPM)

| Field | Detail |
|-------|--------|
| **Title** | Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk |
| **Authors** | William F. Sharpe |
| **Year** | 1964 |
| **Journal** | The Journal of Finance, Vol. 19, No. 3, pp. 425-442 |
| **DOI** | 10.1111/j.1540-6261.1964.tb02865.x |
| **URL** | https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1964.tb02865.x |

**Core Thesis:**
In equilibrium, the expected return of any asset is linearly related to its systematic
risk (beta) relative to the market portfolio. The risk premium an asset earns above the
risk-free rate equals its beta times the market risk premium:
E(R_i) = R_f + beta_i * (E(R_m) - R_f). Only systematic (non-diversifiable) risk is
compensated; idiosyncratic risk can be eliminated through diversification and therefore
earns no premium.

**Key Contributions:**
- Derived equilibrium asset pricing from Markowitz's portfolio theory
- Introduced beta as the single measure of systematic risk
- Established that the market portfolio is mean-variance efficient in equilibrium
- Created the Security Market Line (SML) as the benchmark for expected returns
- Provided the theoretical foundation for the Sharpe ratio (reward-to-variability)

**Practical Implications for Portfolio Construction:**
- The market portfolio (e.g., a total market index fund) is the theoretically optimal
  risky portfolio for all investors
- Investors adjust risk by blending the market portfolio with risk-free assets
- Active management must generate alpha (returns above the SML) to justify fees
- Beta is the correct risk measure for an asset held within a diversified portfolio

**Out-of-Sample Evidence:**
The CAPM has been extensively tested and largely rejected as a complete description of
expected returns. Fama and French (2004) summarize the evidence in "The Capital Asset
Pricing Model: Theory and Evidence" (Journal of Economic Perspectives, Vol. 18, No. 3,
pp. 25-46):

- The empirical SML is too flat: low-beta stocks earn higher returns than CAPM predicts;
  high-beta stocks earn lower returns (the "low beta anomaly" or "betting against beta")
- Size effect (Banz, 1981): small-cap stocks earn excess returns unexplained by beta
- Value effect (Fama & French, 1992): high book-to-market stocks outperform after
  controlling for beta
- Momentum (Jegadeesh & Titman, 1993): past winners continue to outperform — entirely
  unexplained by CAPM

**Key Criticisms and Limitations:**
1. **Empirically rejected:** "The empirical record of the CAPM model is poor — poor enough
   to invalidate the way it is used in applications" — Fama & French (2004)
2. **Market portfolio is unobservable:** Roll's Critique (1977) — we cannot test CAPM
   because the true market portfolio includes all investable assets (real estate, human
   capital, etc.), not just equities
3. **Single factor is insufficient:** Multiple factors (size, value, profitability,
   momentum) explain cross-sectional return variation beyond beta alone
4. **Assumes frictionless markets:** No transaction costs, taxes, or short-sale constraints

**Verdict for MT-37:** CAPM is theoretically elegant but empirically inadequate as a
standalone model. Its core insight — that systematic risk matters, not total risk — is
valid and foundational. The equilibrium returns implied by CAPM serve as the starting
point for Black-Litterman. Factor models (Fama-French) supersede CAPM for cross-sectional
return prediction. For MT-37's portfolio construction, CAPM's main contribution is the
argument for holding broad market index funds as the base allocation.

---

### 1.3 Black & Litterman (1992) — Global Portfolio Optimization

| Field | Detail |
|-------|--------|
| **Title** | Global Portfolio Optimization |
| **Authors** | Fischer Black, Robert Litterman |
| **Year** | 1992 |
| **Journal** | Financial Analysts Journal, Vol. 48, No. 5, pp. 28-43 |
| **DOI** | 10.2469/faj.v48.n5.28 |
| **URL** | https://www.tandfonline.com/doi/abs/10.2469/faj.v48.n5.28 |

**Also see:** He, G. & Litterman, R. (1999). "The Intuition Behind Black-Litterman
Model Portfolios." Goldman Sachs Asset Management Working Paper. Available at SSRN:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=334304

**Core Thesis:**
Traditional mean-variance optimization fails in practice because small changes in
expected return estimates produce wild swings in portfolio weights. Black-Litterman
solves this by using a Bayesian approach: start with market-implied equilibrium returns
(derived by reverse-optimizing the CAPM market portfolio) as a prior, then blend in
the investor's specific views with a confidence level. The posterior expected returns
produce stable, intuitive, and implementable portfolio weights.

**How It Works (Mechanics):**
1. **Reverse optimization:** Compute implied equilibrium excess returns from observed
   market capitalization weights using the covariance matrix:
   Pi = delta * Sigma * w_mkt (where delta = risk aversion, Sigma = covariance matrix,
   w_mkt = market cap weights)
2. **Specify investor views:** Express K views as P * mu = Q + epsilon, where P is a
   pick matrix, Q is the expected return vector for views, and epsilon ~ N(0, Omega)
   captures view uncertainty
3. **Bayesian combination:** Compute posterior expected returns:
   E[R] = [(tau*Sigma)^-1 + P'*Omega^-1*P]^-1 * [(tau*Sigma)^-1*Pi + P'*Omega^-1*Q]
4. **Optimize:** Use posterior returns in standard MVO — weights are now stable

**Key Contributions:**
- Eliminated the "error maximizer" problem by anchoring to equilibrium
- Introduced a principled way to blend quantitative views with market consensus
- Made MVO practically usable for institutional investors
- Produced portfolios that tilt intuitively toward views without extreme weights
- When no views are specified, the model defaults to the market portfolio — a sensible
  neutral starting point

**Practical Implications for Portfolio Construction:**
- Start with market-cap-weighted allocation as neutral baseline (this IS the equilibrium)
- Deviate from market weights only when you have a specific, quantifiable view
- The magnitude of deviation is proportional to conviction level
- Views can be absolute ("US equities will return 8%") or relative ("US will outperform
  Europe by 2%")
- Without strong views, the model recommends something close to a global market portfolio

**Out-of-Sample Evidence:**
Black-Litterman is widely adopted by institutional investors (Goldman Sachs, where it
was developed, and many others). Its out-of-sample performance depends on the quality
of investor views, making controlled academic testing difficult. The framework itself
is mathematically sound — the question is whether the views add value. When views are
omitted, the model reduces to holding the market portfolio, which has strong empirical
support. The Bayesian machinery prevents the estimation-error catastrophe that plagues
raw MVO.

**Key Criticisms and Limitations:**
1. **Garbage in, garbage out:** The model is only as good as the investor's views. Bad
   views produce bad portfolios — the Bayesian framework dampens but doesn't eliminate
   the impact
2. **Sensitivity to tau parameter:** The scalar tau controls the weight given to
   equilibrium vs. views — its choice is ad hoc (typically 0.025 to 0.05)
3. **Omega specification is subjective:** The uncertainty in views (Omega matrix) must
   be specified by the investor — there's no consensus on how
4. **Assumes normal returns:** Inherits the Gaussian assumption from MVO
5. **CAPM equilibrium may be wrong:** If the market portfolio is not efficient (as
   factor models suggest), the equilibrium prior is biased

**Verdict for MT-37:** Black-Litterman is the strongest candidate for MT-37's portfolio
construction engine. It provides a principled framework to start with a sensible baseline
(market-cap weights) and tilt based on quantified views. For a passive investor with no
strong views, it reduces to holding the market portfolio — which aligns with the index
investing evidence. For factor tilts (value, momentum, quality), views can be expressed
as factor loadings. The Bayesian framework is directly compatible with the Kalshi bot's
existing Bayesian infrastructure.

---

## Area 2: Factor Models

Factor models explain why different stocks earn different average returns. CAPM says
only market beta matters; Fama-French showed size and value also matter; Carhart added
momentum; the five-factor model added profitability and investment. These models are
the empirical backbone of cross-sectional asset pricing.

### 2.1 Fama & French (1993) — Three-Factor Model

| Field | Detail |
|-------|--------|
| **Title** | Common Risk Factors in the Returns on Stocks and Bonds |
| **Authors** | Eugene F. Fama, Kenneth R. French |
| **Year** | 1993 |
| **Journal** | Journal of Financial Economics, Vol. 33, No. 1, pp. 3-56 |
| **DOI** | 10.1016/0304-405X(93)90023-5 |
| **URL** | https://www.sciencedirect.com/science/article/abs/pii/0304405X93900235 |
| **Data** | Factor returns publicly available at Kenneth French's data library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html |

**Core Thesis:**
Stock returns are explained by three factors, not just one (market beta). The three
factors are: (1) the excess return on the market (Mkt-RF), (2) the return of small
stocks minus large stocks (SMB — Small Minus Big), and (3) the return of high
book-to-market stocks minus low book-to-market stocks (HML — High Minus Low). The
model also identifies two bond-market factors related to maturity and default risk.

**The Model:**
E(R_i) - R_f = b_i*(R_m - R_f) + s_i*SMB + h_i*HML

Where:
- b_i = sensitivity to market factor
- s_i = sensitivity to size factor (small-cap premium)
- h_i = sensitivity to value factor (value premium)

**Key Findings:**
- The size premium (SMB): small-cap stocks earn ~2-3% annual premium over large-caps,
  historically, though the premium has weakened significantly since publication
- The value premium (HML): high book-to-market (value) stocks earn ~3-5% annual premium
  over low book-to-market (growth) stocks, historically
- Together, the three factors explain the cross-section of stock returns far better than
  CAPM alone
- The model also captures bond return variation via term and default factors

**Practical Implications for Portfolio Construction:**
- Investors can harvest size and value premia by tilting portfolios toward small-cap
  value stocks
- Factor exposure is the primary determinant of portfolio returns — not stock picking
- Index funds and ETFs that target specific factors (value ETFs, small-cap ETFs) allow
  systematic factor harvesting
- Factor loadings should be measured and monitored for any portfolio

**Out-of-Sample Evidence:**
The three-factor model has been tested extensively across international markets:

- **US out-of-sample (post-1993):** The size premium has been weak to nonexistent since
  publication. The value premium was strong through 2006 but turned sharply negative
  during 2007-2020, with growth stocks dramatically outperforming value. Value staged a
  recovery in 2021-2022.
- **International evidence:** Fama & French (1998, 2012, 2017) found value premia in
  most developed markets. Size premium is weaker internationally. The model works better
  with local factors than global factors for regional portfolios.
- **Emerging markets:** Book-to-market retains explanatory power; size factor is less
  reliable (varies by country).
- **Japan:** The value premium has gradually disappeared over time.
- **Time instability:** Factor premia are not constant — they vary significantly across
  decades and market regimes.

**Key Criticisms and Limitations:**
1. **Risk vs. mispricing debate:** Are size and value premia compensation for bearing
   risk (rational) or the result of systematic mispricing (behavioral)? Unresolved after
   30+ years.
2. **Value premium erosion:** Since publication, the HML factor has delivered weak or
   negative returns in several extended periods, raising questions about whether the
   premium was data-mined or has been arbitraged away.
3. **Size premium weakness:** The SMB premium has been essentially zero in the US since
   the early 1980s when it was first documented. Publication itself may have caused
   capital flows that eliminated the premium.
4. **Omits momentum:** The most robust anomaly (Jegadeesh & Titman, 1993) is entirely
   absent from the model.
5. **Factor definitions are arbitrary:** Why book-to-market and not earnings-to-price?
   Why market cap breakpoints at the median NYSE?

**Verdict for MT-37:** The three-factor model is foundational for understanding return
drivers but insufficient as a complete model. The value premium is real but unreliable
in any given decade. The size premium is weak. For MT-37's portfolio construction, factor
tilts toward value should be modest and patient — prepared to underperform for 5-10 year
stretches. The publicly available factor data at Ken French's library is an invaluable
free resource for backtesting.

---

### 2.2 Carhart (1997) — Four-Factor Model (Adding Momentum)

| Field | Detail |
|-------|--------|
| **Title** | On Persistence in Mutual Fund Performance |
| **Authors** | Mark M. Carhart |
| **Year** | 1997 |
| **Journal** | The Journal of Finance, Vol. 52, No. 1, pp. 57-82 |
| **DOI** | 10.1111/j.1540-6261.1997.tb03808.x |
| **URL** | https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1997.tb03808.x |
| **SSRN** | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=8036 |

**Core Thesis:**
Apparent persistence in mutual fund performance is almost entirely explained by common
factors in stock returns and investment expenses — not by stock-picking skill. Carhart
extends the Fama-French three-factor model by adding a fourth factor: momentum (WML —
Winners Minus Losers), which captures the tendency of stocks with high past returns to
continue outperforming and stocks with low past returns to continue underperforming.

**The Model:**
E(R_i) - R_f = b_i*(R_m - R_f) + s_i*SMB + h_i*HML + w_i*WML

Where:
- WML (or UMD — Up Minus Down) = return of past 12-month winners minus past 12-month
  losers (skipping the most recent month to avoid microstructure effects)

**Key Findings:**
- The "hot hands" effect in mutual funds (Hendricks, Patel & Zeckhauser, 1993) is
  mostly explained by the momentum factor, not manager skill
- Individual funds do not earn higher returns from following momentum strategies in
  stocks — the premium exists at the factor level
- The four-factor model substantially explains persistence in mutual fund returns
- The results do not support the existence of skilled or informed mutual fund portfolio
  managers — a devastating finding for active management

**Practical Implications for Portfolio Construction:**
- Momentum is a distinct, compensated factor that adds explanatory power beyond
  market, size, and value
- Fund performance attribution should use four factors, not three — otherwise momentum
  loading masquerades as alpha
- The evidence further strengthens the case for passive (index) investing over active
  management
- Momentum-tilted ETFs (e.g., MTUM) allow systematic harvesting of this premium

**Out-of-Sample Evidence:**
Momentum has been extensively validated:

- **Asness, Moskowitz & Pedersen (2013)** — "Value and Momentum Everywhere" (Journal of
  Finance, Vol. 68, No. 3, pp. 929-985): Finds consistent momentum premia across eight
  asset classes and markets globally. Momentum and value are negatively correlated with
  each other, suggesting a combined value+momentum strategy benefits from diversification.
- **International evidence:** Momentum works in most developed and emerging markets,
  though it experienced a severe crash in 2009 (the "momentum crash" — see Daniel &
  Moskowitz, 2016).
- **Duration:** The premium has persisted for 100+ years in US data and across many
  international markets.

**Key Criticisms and Limitations:**
1. **Momentum crashes:** Momentum strategies experience rare, severe drawdowns — most
   notably in 2009 when the long-short momentum portfolio lost ~40% in a few months.
   These crashes tend to occur during market reversals after sharp downturns.
2. **High turnover and costs:** Monthly rebalancing required to capture momentum generates
   high transaction costs that erode the paper premium.
3. **Behavioral vs. risk explanation:** Is momentum compensation for crash risk, or a
   behavioral anomaly driven by under-reaction and herding? No consensus.
4. **Tax inefficiency:** High turnover generates short-term capital gains.
5. **Capacity constraints:** Large-scale momentum strategies may move prices and erode
   the premium.

**Verdict for MT-37:** Momentum is one of the two strongest documented anomalies (with
value). For MT-37, a modest momentum tilt is justified — but implementation must account
for high turnover costs and tax drag. The negative correlation between momentum and value
means a combined tilt provides better risk-adjusted returns than either alone. Factor ETFs
that implement momentum (MTUM, IMTM) are the most practical vehicle for retail investors.

---

### 2.3 Fama & French (2015) — Five-Factor Model

| Field | Detail |
|-------|--------|
| **Title** | A Five-Factor Asset Pricing Model |
| **Authors** | Eugene F. Fama, Kenneth R. French |
| **Year** | 2015 |
| **Journal** | Journal of Financial Economics, Vol. 116, No. 1, pp. 1-22 |
| **DOI** | 10.1016/j.jfineco.2014.10.010 |
| **URL** | https://www.sciencedirect.com/science/article/abs/pii/S0304405X14002323 |
| **SSRN** | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287202 |

**Core Thesis:**
The original three-factor model is incomplete. Two additional factors — profitability
(RMW — Robust Minus Weak) and investment (CMA — Conservative Minus Aggressive) —
substantially improve the model's ability to explain the cross-section of average stock
returns. Profitable firms that invest conservatively earn higher returns than unprofitable
firms that invest aggressively.

**The Model:**
E(R_i) - R_f = b_i*(R_m - R_f) + s_i*SMB + h_i*HML + r_i*RMW + c_i*CMA

Where:
- RMW = return of firms with robust (high) operating profitability minus firms with weak
  (low) operating profitability
- CMA = return of firms that invest conservatively (low asset growth) minus firms that
  invest aggressively (high asset growth)

**Key Findings:**
- The five-factor model captures size, value, profitability, and investment patterns in
  average stock returns better than the three-factor model
- With profitability and investment factors added, the value factor (HML) becomes
  redundant for describing average returns in the US sample — its explanatory power is
  subsumed by RMW and CMA
- The model's main failure is its inability to capture the low average returns of small
  stocks whose returns behave like those of firms that invest a lot despite low
  profitability ("small growth" stocks)

**Practical Implications for Portfolio Construction:**
- Quality (profitability) and conservative investment are independent return drivers
- A portfolio tilted toward profitable, conservatively-investing firms has earned a
  premium historically
- Quality/profitability ETFs (e.g., QUAL, JQUA) provide exposure to the RMW factor
- The investment factor (CMA) can be accessed through low-asset-growth stock selection
- Factor tilts should be multi-dimensional: value + quality + conservative investment

**Out-of-Sample Evidence:**
- **International:** Fama & French (2017) tested the five-factor model internationally
  and found that HML retains independent explanatory power in non-US data — the value
  factor redundancy is US-specific, not universal.
- **Robeco (2024):** Identified five major concerns with the model, noting that the
  investment factor was defined using asset growth, which Fama and French themselves
  deemed a "less robust" phenomenon in 2008.
- **AQR:** Asness et al. proposed a six-factor model that restores value's independence
  by using an improved HML definition, arguing the redundancy finding is fragile.

**Key Criticisms and Limitations:**
1. **Momentum still omitted:** The most glaring omission. Fama and French argue momentum
   is a short-lived microstructure phenomenon, but this is contested — Carhart (1997) and
   Asness et al. (2013) show it is persistent and pervasive. In practice, most
   practitioners use a six-factor model (FF5 + momentum).
2. **Value factor redundancy is fragile:** International evidence contradicts the US
   finding that HML is subsumed. The redundancy may be sample-specific.
3. **Investment factor robustness questioned:** Asset growth as the investment measure
   is debatable and was previously considered "less robust" by Fama and French themselves.
4. **Cannot explain accruals anomaly or momentum:** The model leaves significant
   anomalies unexplained.
5. **Factor zoo problem:** With five factors, the risk of data mining increases. Why
   these five and not others from the 400+ factors documented in the literature?

**Verdict for MT-37:** The five-factor model identifies profitability and investment as
legitimate return drivers beyond value and size. For portfolio construction, the
practical takeaway is to favor quality stocks (high profitability, conservative
investment) alongside value tilts. However, momentum should be included as a sixth
factor — the omission is a model weakness, not a reason to ignore momentum. For ETF
selection, QUAL (quality/profitability) and VLUE/VTV (value) combined with MTUM
(momentum) capture the key premia.

---

## Area 3: Risk Parity

Risk parity is a portfolio construction methodology that allocates risk (not capital)
equally across asset classes. It directly addresses the observation that traditional
60/40 portfolios are 90%+ equity risk despite appearing "balanced" in dollar terms.

### 3.1 Qian (2005) — Risk Parity Portfolios

| Field | Detail |
|-------|--------|
| **Title** | Risk Parity Portfolios: Efficient Portfolios through True Diversification |
| **Authors** | Edward Qian |
| **Year** | 2005 |
| **Publisher** | PanAgora Asset Management, Boston |
| **URL** | https://www.panagora.com/assets/PanAgora-Risk-Parity-Portfolios-Efficient-Portfolios-Through-True-Diversification.pdf |

**Also see:** Qian, E. (2016). "Risk Parity Fundamentals." CRC Press / Taylor & Francis.
ISBN: 9781498738798. https://www.routledge.com/Risk-Parity-Fundamentals/Qian/p/book/9781032925424

**Core Thesis:**
Traditional portfolio allocation by capital weights (e.g., 60% stocks / 40% bonds)
creates extreme risk concentration — roughly 90% of portfolio volatility comes from the
equity allocation alone. True diversification requires equalizing the risk contribution
from each asset class, not the dollar allocation. A "risk parity" portfolio assigns
weights such that each asset class contributes equally to total portfolio volatility.

**Key Concepts:**
- **Risk contribution:** For asset i in a portfolio, its risk contribution = w_i *
  (partial sigma_p / partial w_i), where sigma_p is portfolio volatility. In a risk
  parity portfolio, all risk contributions are equal.
- **No return forecasts required:** Risk parity does not rely on expected return
  estimates. Without views on risk-adjusted returns, equal risk allocation is the natural
  neutral starting point.
- **Leverage as a feature:** Because bonds have lower volatility than equities, achieving
  equal risk contribution typically requires overweighting bonds (often with leverage) and
  underweighting equities relative to a 60/40 portfolio.

**Practical Implications for Portfolio Construction:**
- A 60/40 portfolio is NOT balanced from a risk perspective — it's ~90% equity risk
- Equal risk contribution produces portfolios between minimum-variance and equal-weight
  in terms of volatility (Maillard, Roncalli & Teiletche, 2010)
- Risk parity typically results in: ~25-30% equities, ~40-55% bonds, ~10-15% commodities,
  ~5-10% gold/inflation-linked, with leverage applied to achieve target return
- For unlevered retail investors, the insight is still valuable: traditional allocations
  are far more equity-concentrated in risk terms than they appear

**Out-of-Sample Evidence:**
- Risk parity strategies have been implemented by large institutional investors since
  the mid-2000s, with Bridgewater's All Weather (see below) as the most prominent example
- An S&P risk-parity index targeting 12% volatility returned 4.5% YTD in early 2025,
  outperforming a 60/40 Bloomberg index (2.2%)
- The approach demonstrated strong resilience during the 2008-2009 financial crisis
- However, 2022 was a severe stress test (see Criticisms below)

---

### 3.2 Bridgewater All Weather Portfolio

| Field | Detail |
|-------|--------|
| **Title** | The All Weather Story |
| **Authors** | Bridgewater Associates (Ray Dalio) |
| **Year** | Developed ~1996, public description ~2011 |
| **URL** | https://www.bridgewater.com/research-and-insights/the-all-weather-story |

**Core Thesis:**
Markets are driven by two key variables: growth (rising/falling) and inflation
(rising/falling). This creates four economic environments (quadrants). Each asset class
performs differently across these quadrants. All Weather allocates risk equally across
all four environments, producing a portfolio that performs reasonably well regardless
of which regime materializes — because we cannot reliably predict regime transitions.

**The Four Quadrants:**

| Environment | Assets that perform well |
|-------------|------------------------|
| Rising growth | Equities, corporate credit, commodities |
| Falling growth | Nominal bonds, inflation-linked bonds |
| Rising inflation | Commodities, inflation-linked bonds, EM |
| Falling inflation | Nominal bonds, equities |

**Simplified All Weather Allocation (retail approximation):**
- 30% Stocks (e.g., VTI)
- 40% Long-term bonds (e.g., TLT)
- 15% Intermediate bonds (e.g., IEF)
- 7.5% Gold (e.g., GLD)
- 7.5% Commodities (e.g., DJP/GSG)

**Performance Characteristics:**
- During the 2008-2009 financial crisis: All Weather declined ~6% vs. the S&P 500's
  ~37% decline and a 60/40's ~22% decline — dramatically reduced drawdown
- Lower return than 100% equities during bull markets (the trade-off for stability)
- Lower volatility than 60/40 across most periods
- The levered institutional version targets higher returns while maintaining the risk
  balance

---

### 3.3 Maillard, Roncalli & Teiletche (2010) — ERC Portfolio Theory

| Field | Detail |
|-------|--------|
| **Title** | On the Properties of Equally-Weighted Risk Contributions Portfolios |
| **Authors** | Sebastien Maillard, Thierry Roncalli, Jerome Teiletche |
| **Year** | 2010 |
| **Journal** | The Journal of Portfolio Management, Vol. 36, No. 4, pp. 60-70 |
| **DOI** | 10.3905/jpm.2010.36.4.060 |
| **URL** | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1271972 |

**Core Thesis:**
The paper provides the formal mathematical derivation and theoretical properties of
equally-weighted risk contribution (ERC) portfolios — the academic formalization of
the "risk parity" concept. The ERC portfolio's volatility lies between the
minimum-variance portfolio and the equally-weighted portfolio, providing a principled
middle ground.

**Key Contributions:**
- Proved that the ERC portfolio exists and is unique under standard conditions
- Demonstrated that ERC maximizes the diversification of risk contributions on an ex
  ante basis
- Showed the theoretical relationship: minimum-variance <= ERC volatility <= equal-weight
  volatility
- Provided computational methods for solving the ERC optimization problem

---

### 3.4 Risk Parity: Criticisms and Limitations (Consolidated)

The following criticisms apply to risk parity as an approach (Qian, All Weather, ERC):

1. **Leverage requirement:** Equalizing risk contributions across asset classes with
   very different volatilities (bonds ~5% vol, equities ~15% vol, commodities ~20% vol)
   requires substantial leverage on the low-volatility assets. Leverage introduces
   financing costs, margin risk, and regulatory constraints. Retail investors cannot
   easily implement leveraged risk parity.

2. **2022 stress test failure:** Most risk parity products significantly underperformed
   the -16.1% return of a global 60/40 benchmark in 2022. The cause: stock-bond
   correlations moved sharply positive (reaching 0.65), breaking the fundamental
   assumption that bonds hedge equity risk. When both stocks and bonds decline
   simultaneously (as in inflationary tightening cycles), risk parity portfolios suffer
   disproportionately due to their heavy bond allocation.

3. **Rising rate vulnerability:** Risk parity's bond overweight means it underperforms
   during sustained rate-rising periods. The 2022 rate-hiking cycle exposed this
   structural weakness. Risk parity relies on bonds as a low-risk diversifier — when
   bonds become a source of losses, the entire framework breaks down.

4. **Correlation regime dependence:** The strategy assumes relatively stable correlations
   between asset classes. During crises, correlations tend to spike toward +1 across all
   risk assets, reducing the diversification benefit precisely when it's needed most.

5. **Backward-looking risk estimates:** Volatility used to assign weights is estimated
   from historical data. If volatility regimes shift (as they did in 2022 when bond
   volatility spiked), the portfolio is slow to adapt. Risk was estimated from a 40-year
   bond bull market, making bond risk look artificially low.

6. **Performance attribution ambiguity:** It's debated whether risk parity's strong
   historical performance (pre-2022) was driven by the framework itself or by the
   secular decline in interest rates from 1981-2020, which produced a massive tailwind
   for levered bond positions.

**Verdict for MT-37:** Risk parity provides a valuable conceptual framework — the insight
that traditional allocations are not truly diversified is correct and important. However,
pure risk parity implementation is problematic for retail investors (leverage requirement)
and vulnerable to correlation regime breaks (2022). For MT-37, the practical takeaway is:
(1) measure risk contribution, not just capital allocation; (2) aim for genuine
diversification across uncorrelated return streams; (3) do not assume bonds always hedge
equities — the stock-bond correlation is regime-dependent. The All Weather simplified
allocation (without leverage) is a reasonable reference portfolio but not the optimal
solution in all environments.

---

## Cross-Cutting Themes (Areas 1-3)

After reviewing the foundational theory (MPT, CAPM, Black-Litterman) and the empirical
factor/risk parity literature, several themes emerge that will guide MT-37's portfolio
construction:

### Theme 1: Estimation Error Is the Central Problem
Markowitz showed how to optimize. Black-Litterman showed that naive optimization fails.
DeMiguel et al. showed that 1/N beats optimization out of sample. The lesson: the
mathematically optimal portfolio is unknowable in practice. Robust methods (shrinkage,
Bayesian priors, constraints) are essential. Simple portfolios (3-fund, equal-weight)
often outperform complex ones net of estimation error.

### Theme 2: Factor Premia Are Real but Unreliable
Value, size, momentum, profitability, and investment factors have strong in-sample
evidence. But:
- Size premium has been near-zero since discovery
- Value premium was negative for a decade (2010-2020)
- Momentum crashes can wipe out years of gains in weeks
- Factor timing is as hard as market timing

Implication: Tilt toward factors, but modestly. Do not bet the portfolio on any single
factor delivering in any given decade.

### Theme 3: Risk Allocation > Capital Allocation
A 60/40 portfolio is ~90% equity risk. Risk parity corrects this conceptually. But
pure risk parity has its own problems (leverage, correlation regime breaks). The
practical middle ground: measure risk contribution, aim for genuine diversification, but
don't require mathematical equality of risk contributions.

### Theme 4: Simple Beats Complex Out of Sample
Across all three areas, simple approaches (market portfolio, 1/N, 3-fund Bogle) tend
to match or beat complex optimization out of sample. Complexity should be added only
when it demonstrably improves risk-adjusted returns net of costs.

### Theme 5: The Market Portfolio Is the Default
CAPM says hold the market. Black-Litterman defaults to the market without views.
Index investing evidence (Bogle, Sharpe) shows most active managers underperform the
market after fees. The burden of proof is on any deviation from the market portfolio.

---

## Key References (Verified)

All citations below have been verified via web search. DOIs and URLs confirmed.

### Area 1: Modern Portfolio Theory
1. Markowitz, H. (1952). "Portfolio Selection." Journal of Finance, 7(1), 77-91. DOI: 10.1111/j.1540-6261.1952.tb01525.x
2. Sharpe, W.F. (1964). "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk." Journal of Finance, 19(3), 425-442. DOI: 10.1111/j.1540-6261.1964.tb02865.x
3. Black, F. & Litterman, R. (1992). "Global Portfolio Optimization." Financial Analysts Journal, 48(5), 28-43. DOI: 10.2469/faj.v48.n5.28
4. He, G. & Litterman, R. (1999). "The Intuition Behind Black-Litterman Model Portfolios." Goldman Sachs Working Paper. SSRN: 334304
5. DeMiguel, V., Garlappi, L. & Uppal, R. (2009). "Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?" Review of Financial Studies, 22(5), 1915-1953.
6. Fama, E.F. & French, K.R. (2004). "The Capital Asset Pricing Model: Theory and Evidence." Journal of Economic Perspectives, 18(3), 25-46.

### Area 2: Factor Models
7. Fama, E.F. & French, K.R. (1993). "Common Risk Factors in the Returns on Stocks and Bonds." Journal of Financial Economics, 33(1), 3-56. DOI: 10.1016/0304-405X(93)90023-5
8. Carhart, M.M. (1997). "On Persistence in Mutual Fund Performance." Journal of Finance, 52(1), 57-82. DOI: 10.1111/j.1540-6261.1997.tb03808.x
9. Fama, E.F. & French, K.R. (2015). "A Five-Factor Asset Pricing Model." Journal of Financial Economics, 116(1), 1-22. DOI: 10.1016/j.jfineco.2014.10.010
10. Asness, C.S., Moskowitz, T.J. & Pedersen, L.H. (2013). "Value and Momentum Everywhere." Journal of Finance, 68(3), 929-985. DOI: 10.1111/jofi.12021

### Area 3: Risk Parity
11. Qian, E. (2005). "Risk Parity Portfolios: Efficient Portfolios through True Diversification." PanAgora Asset Management.
12. Qian, E. (2016). "Risk Parity Fundamentals." CRC Press / Taylor & Francis. ISBN: 9781498738798
13. Maillard, S., Roncalli, T. & Teiletche, J. (2010). "On the Properties of Equally-Weighted Risk Contributions Portfolios." Journal of Portfolio Management, 36(4), 60-70. DOI: 10.3905/jpm.2010.36.4.060
14. Bridgewater Associates. "The All Weather Story." https://www.bridgewater.com/research-and-insights/the-all-weather-story

### Supporting References (cited in analysis)
15. Banz, R. (1981). "The Relationship Between Return and Market Value of Common Stocks." Journal of Financial Economics, 9(1), 3-18. [UNVERIFIED — widely cited, not independently confirmed via search]

---

## Next Steps (Areas 4-10)

The next session should cover:
- **Area 4:** Momentum & Value — Asness et al. 2013 (deeper dive), AQR research library
- **Area 5:** Behavioral Finance — Kahneman & Tversky 1979, Shiller 2000, Thaler 2015
- **Area 6:** Tax-Loss Harvesting — Constantinides 1983, Berkin & Ye 2003

Target: 50+ papers synthesized across all 10 areas.
