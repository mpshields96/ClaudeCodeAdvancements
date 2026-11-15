# Real SPY bar sources and their terms

Worker: reddit-research (Claude), acting as the real-data source and terms worker for the 04:41:26Z restart window.
Pages were retrieved on 2026-11-15 between 04:45:03Z and 04:56:01Z (`date -u`). The file was written after that.

**The question.** Which source could Matthew connect tonight for real SPY bars that a personal paper signal model may use automatically, and what would he have to do himself?

**Short answer.** Twelve Data's free Basic plan. It is the only source checked whose free plan card names non-display use, and its documented output is already a CSV of `datetime, open, high, low, close, volume` with a UTC option. Matthew has to sign up and fetch the file himself (about five minutes). The request has not been run, and three terms points need Codex's call. They are listed under "The pick".

**Addendum 06:00Z (end of this file).** It gives the exact wording for the three terms points, read directly from Twelve Data's pages, and a request form that keeps the key out of the URL. Where it differs from the sections below, the addendum is the later reading. It makes no ruling: Matthew decides the three points.

## How to read this file

- **"Paraphrased"** means I saw the page only through WebFetch, which answers through a small summarizing model. The short quotes are that model's quotes, not raw page text I read myself. Only the Alpha Vantage Terms of Service was read directly (as PDF page images).
- **"Snippet"** means a search-result summary. It is weaker than a paraphrased page.
- The "Automated personal use" line is my reading. It is not legal advice, and Codex owns the call.
- Nothing was signed up for, no key was made or used, no request was sent to any data endpoint, and no data file was downloaded. Reddit was not contacted.
- Retrieval times are given as a window per source: A = 04:45Z to 04:49Z, B = 04:49Z to 04:53Z, C = 04:53Z to 04:56Z, all on 2026-11-15 UTC.

## Summary table

| Source | Cost | Key or signup | Automated personal use | Bars and delay | Verdict for tonight |
|---|---|---|---|---|---|
| **Twelve Data Basic** | Free | Email signup, API key | Plan card lists "Internal non-display usage"; free tier barred from commercial use | 1min to 1month; plan says real-time US equities and ETFs; CSV with UTC option | **Pick** |
| Tiingo free | Free | Signup, API token | "internal and personal use only"; no wording on automation | Daily (30+ years) and IEX intraday from August 2017; IEX-only volume | Runner-up |
| Alpaca Basic | Free | Broker account (paper or live), key pair | Snippet only: personal, non-commercial | Minute to day, IEX only, real-time | Blocked by the sprint's no-broker-account limit unless Matthew decides otherwise |
| Massive (was Polygon) Basic | Free | Signup, API key | "personal and non-professional use"; operative terms not read | Minute aggregates, end-of-day only, 2 years | Usable for history, not for a live session |
| Alpha Vantage free | Free | Key via "Get Free API Key" | Yes for private research and testing (read directly) | Daily only, last 100 bars; intraday is premium | Too thin for an hourly strategy |
| Marketdata.app free | Free | Signup | "Internal Use"; nothing more stated | All resolutions, 1 year, 24-hour delay | Weaker than the pick |
| EODHD free | Free | Registration | Not stated | End-of-day only, 1 year, 20 calls a day | Too thin |
| Finnhub free | Free | Signup, key | "strictly for personal use"; data must be deleted when a subscription ends | Candle access on the free plan not verified | Not verified |
| Nasdaq Data Link | Free account, paid price data | Signup, key | Not read | US end-of-day prices are a premium table | No free SPY bars found |
| FRED (SP500) | Free | Key for the API | Personal use implied; S&P owns the series | Daily index close only, 10 years | Not SPY and not bars |
| Stooq | Free | None seen | No terms found | Pages came back empty | Unusable tonight |
| Yahoo (unofficial) | Download is paid | Yahoo account for the paid download | **No**: automated collection is prohibited | n/a | Excluded |

## Source records

### 1. Twelve Data (Basic plan)

- **Free or paid:** Free. Basic is "$0", described as "For testing and side projects". Paid personal plans exist above it.
- **Key or signup:** Email signup and an API key. The key is passed in the request URL (`apikey=`).
- **Automated personal or non-display use:** The Basic plan card lists "Internal non-display usage". The terms define Non-Display Use as "any use of Data that does not involve displaying the Data to natural persons" and allow a customer to "Access, receive, process, and store Data solely for Internal Use" (§2.2(a)) and to "Use Data for Non-Display Use only as permitted by your subscription tier" (§2.2(d)). §2.3(l) bars "Use Free Tier data for commercial purposes". §17.1(h) bars use "for high-frequency trading without appropriate license", which does not describe an hourly paper model.
- **Bars and delay:** Intervals `1min`, `5min`, `15min`, `30min`, `45min`, `1h`, `2h`, `4h`, `8h`, `1day`, `1week`, `1month`. Up to 5000 rows per request, one credit per symbol. Limits: "API requests: 8 (800 a day)". The plan card says "Real-time US equities and ETFs". History depth on Basic is not stated. Which exchanges feed the volume figure is not stated.
- **Redistribution:** §2.3(b) bars "Redistribute, resell, sublicense, or transfer any Data". §2.3(g) bars "Store or cache Data beyond permitted timeframes specified in the Documentation"; I did not find those timeframes.
- **Open points:** §5.6 says "Free Trial limited to evaluation purposes only" and "No commercial use permitted during Free Trial", and the pricing page says "Free trial is available under the Basic plan". The terms define "Free Trial" and never define "Free Tier", so Basic may be the Free Trial. "Internal Use" is defined as "internal business purposes", while the pricing page has a personal-use view.
- **URLs (all paraphrased):** `https://twelvedata.com/pricing` (A); `https://twelvedata.com/terms`, "Last updated: January 1, 2026" (A); `https://twelvedata.com/docs/market-data/time-series` (C).

### 2. Tiingo (free account)

- **Free or paid:** Free ("$0/month"). Power is $30 a month.
- **Key or signup:** "In order to use the API, you must sign-up to create an account." An API token is assigned to the account.
- **Automated personal or non-display use:** "For Basic and Power accounts, data is for internal and personal use only." The pricing page says "Internal use means you may only use the data for your own personal use" and "you may not display or share the data with another person or organization". No page addresses automated use in words; the product is an API.
- **Bars and delay:** Daily end-of-day bars with 30+ years of history, CSV supported (`format=csv`), available "at 5:30 PM EST" with corrections "until 8 PM EST". IEX intraday bars "from August 2017"; the page shows `resampleFreq=5min` and does not list other values. Intraday volume is "The number of shares traded on IEX only" and is returned only if asked for in `columns`. The timezone of the intraday `date` field is not stated. Limits: 50 requests an hour, 1,000 a day, 1 GB a month (the pricing page also showed 500 unique symbols a month).
- **Redistribution:** "You may not redistribute the data in any form."
- **Terms page:** Not read. `https://www.tiingo.com/about/terms` returned HTTP 404 and `https://app.tiingo.com/tos/` returned HTTP 403. Neither was retried.
- **URLs (all paraphrased):** `https://www.tiingo.com/about/pricing` (A); `https://www.tiingo.com/documentation/general/overview`, `https://www.tiingo.com/documentation/iex`, `https://www.tiingo.com/documentation/end-of-day`, `https://www.tiingo.com/products/iex-api` (C).

### 3. Alpaca (Basic market data)

- **Free or paid:** Free ("$0/mo", "For developers and researchers"). Algo Trader Plus is $99 a month.
- **Key or signup:** An Alpaca account and a key pair. "all market data endpoints require authentication". "The Basic plan serves as the default option for both Paper and Live trading accounts". Alpaca is a broker, so this is a broker account. Whether an email-only paper account is enough was not confirmed on any page I read.
- **Automated personal or non-display use:** Not stated on the documentation or pricing pages. Snippet only, from Alpaca's terms PDFs: "you agree to use the Services and Content solely for your own personal and non-commercial purposes". The PDFs were not opened.
- **Bars and delay:** Minute to day bars from "only the IEX exchange", real-time. History "Since 2016". "200 / min" historical calls. Recent consolidated (SIP) data needs the paid plan. Bar timestamps are "the left side of the interval"; sample responses end in "Z" (UTC).
- **Redistribution:** Snippet only: "I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca."
- **Sprint status:** Codex has prepared this request (`codex/real-intake/Get_Real_Data.md`, one-hour IEX bars through `provider_capture.py spy-hours`), not run. The restart record keeps "No orders, accounts, keys" for agents, and `SPRINT.md` rules out broker accounts. Only Matthew can decide to open one.
- **URLs (paraphrased):** `https://docs.alpaca.markets/docs/about-market-data-api`, `https://alpaca.markets/data` (A); `https://docs.alpaca.markets/docs/market-data-faq` (B). Terms PDF not read: `https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf`.

### 4. Massive, formerly Polygon.io (Stocks Basic)

- **Free or paid:** Free ("$0/month", "Great for trying our APIs"). The 15-minute delayed plan is paid (snippet: $29 Starter).
- **Key or signup:** Account and API key (not shown on the pages read; standard for this API).
- **Automated personal or non-display use:** The stocks page labels Basic "Individual use" and says "Individual plans (Basic → Advanced) are licensed for personal and non-professional use." The operative Individuals terms were not read; `https://massive.com/terms` is only an index and says the Individuals terms "apply to your personal, individual, and non-business use".
- **Bars and delay:** "Minute Aggregates" are included. Data is "End-of-day", history "2 years", "5 / min" API calls. "The Basic plan does not include the current trading day at any hour"; the previous day "can be requested after midnight Eastern Time", and an earlier request "returns HTTP 403".
- **Redistribution:** Not read.
- **URLs (paraphrased):** `https://massive.com/pricing`, `https://massive.com/terms` (A); `https://massive.com/stocks`, `https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data` (B).

### 5. Alpha Vantage (free key)

- **Free or paid:** Free, capped at 25 API requests a day. Premium plans are paid.
- **Key or signup:** A key from the "Get Free API Key" form. §3 of the terms makes the licence effective at that click.
- **Automated personal or non-display use:** **Read directly.** §2a grants use "for personal, non-commercial use, unless you and Alpha Vantage have agreed otherwise in writing". Commercial use includes "any purpose that goes beyond investment analysis, research, testing, monitoring, and any other activities that are private and individual in nature". A private paper model fits the allowed side of that line.
- **Bars and delay:** Daily bars only on the free key, and only "the latest 100 data points" ("The "compact" outputsize is available to both free and premium API keys."). Intraday is "a premium endpoint". Adjusted daily is premium. CSV is supported (`datatype=csv`).
- **Redistribution:** No explicit redistribution or storage clause seen in the four pages.
- **URLs:** `https://www.alphavantage.co/terms_of_service/` (read directly as PDF page images, undated, A); `https://www.alphavantage.co/premium/` and `https://www.alphavantage.co/documentation/` (paraphrased; the documentation page was read for its first 100,000 characters only, A).

### 6. Finnhub (free plan)

- **Free or paid:** Free plan exists; the pricing page loaded only a tagline, so the plan table was not read.
- **Key or signup:** Signup and API key (not read from a page; the terms assume an account).
- **Automated personal or non-display use:** "All plan listed on Finnhub website is strictly for personal use unless explicitly stated otherwise." "Personal plan can't be used by any business even internally without a written approval."
- **Bars and delay:** Not verified. The candle documentation page did not load, so I cannot say whether US stock candles are on the free plan.
- **Redistribution:** "You hereby agree to not redistribute or share access to data or derived results from the data obtained from Finnhub with anyone or any 3rd party without written approval from Finnhub." Also "All data must be deleted should your subscription to that data ends."
- **URLs:** `https://finnhub.io/terms-of-service` (paraphrased, undated, A); `https://finnhub.io/pricing` (A) and `https://finnhub.io/docs/api/stock-candles` (B) did not load.

### 7. Nasdaq Data Link

- **Free or paid:** Free account; US end-of-day stock prices appear as a premium table ("QuoteMedia End of Day US Prices | EOD | Tables | Premium").
- **Key or signup:** Account and API key.
- **Automated personal or non-display use, redistribution:** Not read.
- **Bars and delay:** No free SPY bars found.
- **URLs:** Snippets only (A). `https://docs.data.nasdaq.com/docs/data-organization` redirected to `https://data.nasdaq.com/accesstools`, which returned HTTP 404 (B, C).

### 8. FRED (series SP500)

- **Free or paid:** Free.
- **Key or signup:** "In order to use the FRED® API, you must have register for an API Key."
- **Automated personal or non-display use:** The API terms say "Before using data series owned by third parties for anything other than your own personal use" ... "you must contact the data owner to obtain permission." That implies personal use is acceptable. The series page carries "Reproduction of S&P 500 in any form is prohibited except with the prior written permission of S&P Dow Jones Indices LLC".
- **Bars and delay:** "Daily, Close" only: the S&P 500 index level, with no open, high, low or volume, and 10 years of history. Latest value on the page was 7,561.67 for 2026-11-13. It is an index, not SPY.
- **Redistribution:** Restricted by S&P as quoted. Required notice for API products: "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."
- **URLs (paraphrased):** `https://fred.stlouisfed.org/series/SP500`, `https://fred.stlouisfed.org/docs/api/terms_of_use.html` (undated) (A).

### 9. Stooq

- **Status:** `https://stooq.com/q/d/?s=spy.us&i=d` and `https://stooq.com/db/h/` both returned empty page text (A). No terms page was found. Codex's earlier CSV attempt also "came back empty" (`codex/real-intake/SPY_SOURCE.md`). Nothing about cost, permitted use, bars or redistribution is verified.

### 10. Yahoo (unofficial)

- **Free or paid:** "Downloading historical data is available with a Yahoo Finance Gold subscription."
- **Automated personal or non-display use:** **Prohibited.** The Yahoo terms §2(d)(9) bar anyone to "access or collect data, or attempt to access or collect data, from our Services using any automated means" ... "for any purpose without our express, prior permission." §2(e) bars access by "a method other than the interface and the instructions that we provide".
- **Redistribution:** §2(d)(10)(a) bars building a "database, archive, mobile application, data feed, widget or any other aggregated data source".
- **URLs (paraphrased):** `https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html` (first 100,000 of 126,993 characters; cites version "January 2, 2026 or later") and `https://help.yahoo.com/kb/SLN2311.html` (A).

### 11. Marketdata.app (added)

- **Free or paid:** "Free Forever", "$0". 30-day trial of paid features with no card.
- **Key or signup:** Signup.
- **Automated personal or non-display use:** The licence row reads "Internal Use". Nothing more is stated for the free plan.
- **Bars and delay:** "Access historical stock data across all resolutions — 1-minute, hourly, daily, and more." "100 Daily API Credits", "1 Year Historical Data", "24h Delayed Stock Data".
- **Redistribution:** Not stated on the pricing page; terms not read.
- **URL (paraphrased):** `https://www.marketdata.app/pricing/` (B).

### 12. EODHD (added)

- **Free or paid:** "$0/mo".
- **Key or signup:** "Once you register you get 20 free API calls per day."
- **Automated personal or non-display use, redistribution:** Not stated on the pricing page; terms not read.
- **Bars and delay:** End-of-day only with 1 year of history. Intraday is not included.
- **URL (paraphrased):** `https://eodhd.com/pricing` (B).

## Not verified

- Every "paraphrased" quote above. Codex should open the pick's two pages before acceptance.
- Twelve Data: whether Basic is the "Free Trial" in §5.6; the storage timeframes; history depth on Basic; the exchanges behind the volume figure; whether signup asks for a card; the exact CSV header (the docs show JSON samples only).
- Tiingo: the terms page (404 and 403); `1hour` as a `resampleFreq` value; CSV on the IEX endpoint; the timezone of intraday stamps.
- Alpaca: the terms PDFs; whether a paper-only account needs identity details.
- Massive: the Individuals terms; redistribution wording.
- Finnhub: the free plan's candle access.
- Stooq: everything.
- Not looked at: a manual history download from Nasdaq.com, Databento, Financial Modeling Prep.
- No request was run against any provider, so no real bar has been seen.

## The pick: Twelve Data Basic

**Why this one.**

1. Its free plan card names the use the paper model needs: "Internal non-display usage".
2. It is a data vendor, not a broker, so it does not touch the sprint's broker-account limit.
3. One request returns hourly SPY bars as CSV with the six fields the adapter wants, stamped in UTC.
4. The plan says real-time, so the same key can serve a live paper session on Monday. Massive's free plan cannot do that.

**What Codex should decide before the data goes into the model.**

1. Whether a personal paper model is within "evaluation purposes" if Basic is the Free Trial (§5.6). My reading is yes: no money, no customers, one person testing signals.
2. Whether "Internal Use" as "internal business purposes" covers an individual. The pricing page's personal view and "For testing and side projects" suggest it does.
3. Storage. The docs' permitted timeframes were not found, so keep the file local.

If Codex rejects that reading, the runner-up is Tiingo's free account. Its permitted-use wording is the plainest ("internal and personal use only"), but its intraday volume is IEX-only and three request details are unverified.

**Handling rules that follow from the terms.**

- Keep the CSV on this Mac. Do not commit it, push it, publish it or put the raw series in a shared artifact (§2.3(b)).
- Reports may show the model's signals and results. They should not republish the raw bars.
- The model must not use the data for anything commercial (§2.3(l)).
- TradingView stays display-only as before. These bars, not TradingView values, feed the model and the ledger.

## Matthew's steps (he does all of these himself)

No agent signs up, sees the key or runs the request. The request below is taken from the documentation and has not been run.

1. Open `https://twelvedata.com/pricing`, choose **Basic** (free) and sign up with an email address. Read `https://twelvedata.com/terms` before accepting. If the signup asks for a card or any payment, stop.
2. Open the API key page in the Twelve Data dashboard and copy the key. Do not paste it into any Claude or Codex chat, and do not save it in a project file.
3. Open the macOS Terminal app (not a Claude terminal tab) and run this. It waits silently; paste the key and press Return.

```bash
read -s TD_KEY
```

4. Run the request. It writes hourly SPY bars, oldest first, in UTC. **Preferred form:** the command under "Addendum 06:00Z" at the end of this file, which sends the key in a header and not in the URL. The command below is the fallback.

```bash
curl -s --create-dirs -o "nov14-sprint/tvbot/real/spy_1h_twelvedata.csv" "https://api.twelvedata.com/time_series?symbol=SPY&interval=1h&outputsize=5000&order=asc&timezone=UTC&format=CSV&delimiter=,&apikey=${TD_KEY}"
```

5. Check the first lines. The first line should be a header beginning `datetime`. If it begins with `{`, it is an error message from Twelve Data and not data.

```bash
head -3 "nov14-sprint/tvbot/real/spy_1h_twelvedata.csv"
```

6. Tell the coordinator chat that the SPY file is in place. Say nothing about the key.

The output folder `nov14-sprint/tvbot/real/` is my suggestion. tvbot-lead should name the folder it wants before Matthew runs step 4.

## Mapping onto the adapter schema (`ts, open, high, low, close, volume`, UTC)

| Adapter column | Twelve Data column | Rule |
|---|---|---|
| `ts` | `datetime` | A value such as `2026-11-13 14:30:00` with no zone marker. With `timezone=UTC` in the request it is UTC. Parse as UTC and write `2026-11-13T14:30:00Z`. |
| `open` | `open` | Same name. Decimal text. |
| `high` | `high` | Same name. |
| `low` | `low` | Same name. |
| `close` | `close` | Same name. |
| `volume` | `volume` | Same name. Treat as indicative: the feed behind it is not stated. |

Points the adapter should handle:

- **The stamp is the bar's opening time.** The docs describe `datetime` as "when the bar with specified interval was opened". If the adapter expects close-stamped bars, add one interval.
- **Delimiter.** The CSV default is a semicolon. The request sets `delimiter=,`. If the first line has semicolons, the parameter was dropped; split on `;`.
- **Order.** The default is newest first. The request sets `order=asc`. Sort ascending anyway and reject duplicate stamps.
- **Session alignment.** Do not assume where hourly bars start. Read the stamps: a US session opens at 14:30Z in winter and 13:30Z in summer, and the last bar of a day may be shorter than an hour. This was not verified from the docs.
- **Partial bar.** A request made during market hours ends with a bar that is still forming. Drop the last row unless the market is closed. Tonight the market is closed, so the last row should be Friday, November 13.
- **Daily bars.** For `1day` and longer the `timezone` parameter is ignored and `datetime` is a date only. The adapter needs its own rule for the time of day, so hourly is the cleaner first file.
- **Adjustment.** The default is `adjust=splits`. SPY has no recent split, so prices are as traded. Dividends are not adjusted.
- **Limits.** One request costs one credit; the plan allows 8 a minute and 800 a day.

## Addendum 06:00Z: exact terms wording and the API key header

Written 2026-11-15T05:35:29Z (`date -u`) by reddit-research (Claude), for the coordinator's follow-up due 06:00Z. It covers two things: the exact wording on Twelve Data's own pages for the three open terms points, and whether the API key can go in a header instead of the URL.

**This addendum makes no ruling.** It sets out what the pages say and what they do not say. Matthew decides the three points and fills `terms_quote` himself.

### How the pages were read

- **Read directly, word for word.** Each page was fetched with `curl` to standard output and the HTML tags were stripped in memory. Every quote in this addendum is text I read in the page as served. None of it is a WebFetch paraphrase.
- Nothing was saved to disk. There was no signup, no key, no request to a data endpoint and no download. Every page returned HTTP 200.
- Limits of this method: I read the HTML as served, not the page as a browser draws it. Text that a page adds later by script would be missing, and I cannot say where a sentence appears on screen (for example, only on hover).
- Quotation marks, capitals and punctuation are as on the page. Where the page has a list, each list line is quoted separately.

| Page | Retrieved (2026-11-15 UTC) |
|---|---|
| `https://twelvedata.com/terms` ("Last updated: January 1, 2026") | 05:28:07Z, 05:28:24Z, 05:32:55Z |
| `https://twelvedata.com/pricing` | 05:28:31Z, 05:28:39Z, 05:29:17Z |
| `https://twelvedata.com/docs` (index only) | 05:28:48Z |
| `https://twelvedata.com/docs/introduction` and `/docs/introduction/quickstart` | 05:29:04Z to 05:29:06Z |
| `https://twelvedata.com/docs/advanced` and `/docs/advanced/api-usage` | 05:29:17Z to 05:29:19Z |
| `https://support.twelvedata.com/en/articles/5335783-trial` | 05:29:25Z |

### (a) Is Basic a free trial for evaluation only?

**Terms of Use**

- §1 Definitions: `"Free Trial" means evaluative use of the Platform for testing purposes prior to purchasing a subscription.`
- §5.6, headed `Free trial terms`:
  - `(a) Free Trial limited to evaluation purposes only`
  - `(b) No commercial use permitted during Free Trial`
  - `(c) Twelve Data may terminate Free Trial at any time`
  - `(d) No service level commitments during Free Trial`
- §2.3, under `Customer shall not, and shall ensure its Authorized Users do not:`
  - `(l) Use Free Tier data for commercial purposes`

**Pricing page**

- Basic plan card, top lines: `Basic`, `For testing and side projects`, `$0`, `/month`, `Start with Basic`.
- Same card, the usage line and the sentence that follows it in the HTML: `Internal non-display usage`, then `Data may be used internally for testing, evaluation, or development purposes only. The data cannot be displayed to users, shared externally, or used in production systems.`
- FAQ, under the question `Do you offer discounts or free trials?`: `We do offer 20% students and startups discounts. Free trial is available under the Basic plan. Learn more`, then `Besides, we never run discounts and offer free trials on upper-tier plans.` The "Learn more" link goes to the support article below.

**Support article "Trial"** (subtitle `Experience features of premium plans for free`)

- `Twelve Data offers several subscription tiers: a Basic (Free) plan with limited daily credits, Grow, Pro (individual) and Venture (business) plans with increasing data access, and Ultra (individual) and Enterprise (business) plans for comprehensive market coverage and advanced features.`
- `The trial is designed to help you get started with API and WebSocket by using the specific symbols from all international markets.`
- `Once you feel comfortable with the API and WebSocket, you may upgrade to the plan that suits your needs best.`

**What the pages do and do not say (observations, not a ruling)**

- The word "Basic" does not appear in the Terms of Use.
- "Free Trial" is defined in the terms. "Free Tier" appears once (§2.3(l)) and has no entry in the Definitions.
- The pricing FAQ sentence is the only place I found that ties the words "Free trial" to "the Basic plan".
- The support article describes the trial as trial symbols and trial WebSocket credits, and calls Basic `a Basic (Free) plan`.
- I found no end date or time limit for Basic on any of these pages.

### (b) Does "internal use" cover one person's personal paper model?

**Terms of Use**

- Opening sentence: `This Twelve Data Terms of Use (the "Agreement") is a legally binding contract between Twelve Data Pte. Ltd. ("Twelve Data", "we", "our", or "us") (UEN No. 202006058W) and you ("Customer", "you", or "your"), whether as an individual or on behalf of an entity you represent.`
- §1: `"Internal Use" means use solely for Customer's internal business purposes and not for redistribution or external commercial purposes.`
- §1: `"Non-Display Use" means any use of Data that does not involve displaying the Data to natural persons.`
- §2.1: `Subject to the terms of this Agreement and payment of applicable Fees, Twelve Data grants Customer a limited, revocable, non-exclusive, non-transferable, non-sublicensable license to access and use the Platform solely for Internal Use during the subscription term, except as otherwise expressly permitted by your Subscription Tier, Data add-ons, or a separate written agreement with Twelve Data.`
- §2.2, under `Customer is granted a limited, non-exclusive license to:`
  - `(a) Access, receive, process, and store Data solely for Internal Use (or as otherwise permitted by your Subscription Tier or add-ons)`
  - `(d) Use Data for Non-Display Use only as permitted by your subscription tier`
- §2.3(l), quoted under (a).

**Pricing page**

- Page title: `Individual Pricing - Twelve Data`. The plan view has two labels, `Personal use` and `Commercial use`.
- Add-ons note: `Pricing depends on your license type: personal or commercial.`
- Basic card wording, quoted under (a).
- For contrast, wording elsewhere on the same page (not on the Basic card):
  - `Internal non-display data access`, with `Use the data internally for programmatic processing, analysis, system integration, and internal display. The data may not be redistributed or made available to external parties.`
  - `Internal display data access`, with `View-only access for internal use within your applications and dashboards. The data may be displayed but cannot be programmatically processed, stored, transformed, or redistributed.`

**What the pages do and do not say (observations, not a ruling)**

- The terms define "Internal Use" by `internal business purposes`. They do not use the phrase "personal use". The word "personal" appears on the terms page only in a footer privacy link.
- The "personal" wording is on the pricing page, not in the terms.
- **New point for Matthew.** The Basic card sentence says the data `cannot be displayed to users` and cannot be `used in production systems`. That bears on two things: whether these bars may be drawn on the desk or dashboard (as distinct from feeding the model), and what counts as a production system for a paper model. I am not ruling on either.

### (c) How long may data be stored?

**Terms of Use**

- §2.2(a), quoted under (b): the licence includes `store Data solely for Internal Use`.
- §2.3, in the "shall not" list: `(g) Store or cache Data beyond permitted timeframes specified in the Documentation`
- §1: `"Documentation" means the online user guide and technical documentation available at https://twelvedata.com/docs.`
- §16, headed `Data retention and deletion`:
  - §16.1 `Retention limits`: `Customer may retain Data only:`
    - `(a) For duration permitted by subscription`
    - `(b) As required for regulatory compliance`
    - `(c) Subject to any Third-Party Provider restrictions`
  - §16.2 `Data Deletion`: `Upon termination or expiration:`
    - `(a) All Data must be deleted within 30 days`
    - `(b) Certification of deletion required if requested`
    - `(c) Audit trail data may be retained for compliance`
- §12.5 `Effect of termination`: `Upon termination:`
  - `(a) All access rights cease immediately`
  - `(b) Customer must delete all Data`
- Derived data: §1 `"Derived Data" means data created by Customer from the Data, provided such data cannot be reverse-engineered to arrive at the underlying Data.` §2.2 `(c) Create Derived Data that cannot be reverse-engineered to recreate the original Data`. §6.2 `Customer retains rights to Derived Data created in compliance with this Agreement.`

**Documentation**

- The only storage-related sentence I found is a best-practice tip on `/docs/introduction`: `Caching: Cache responses for frequently accessed data to reduce API calls and improve performance.`

**What was not found**

- No number of hours, days or months for the "permitted timeframes" in §2.3(g). I searched `/docs`, `/docs/introduction`, `/docs/advanced` and `/docs/advanced/api-usage` for cache, retain, retention, timeframe, store and persist. Other documentation pages were not searched, so a timeframe may be stated elsewhere.
- No statement of the `duration permitted by subscription` (§16.1(a)) for Basic, on the pricing page or in the support article.
- The pages I read state what happens at the end (§12.5 and §16.2 above). They do not state how long the SPY file may be kept while the account is open.

### Sentences Matthew may want for `terms_quote`

He chooses. These are the sentences on Twelve Data's own pages that say what the free plan's data may be used for. He should open the page and copy the text himself, so the quote is one he has seen. The browser's find function on a few words will locate each one; the Basic card sentence may show only on hover or tap.

1. Pricing page, Basic card: `Data may be used internally for testing, evaluation, or development purposes only. The data cannot be displayed to users, shared externally, or used in production systems.`
2. Terms §2.2(a): `Access, receive, process, and store Data solely for Internal Use (or as otherwise permitted by your Subscription Tier or add-ons)`
3. Terms §2.3(l): `Use Free Tier data for commercial purposes` (from the "shall not" list).
4. Terms §5.6(a) and (b), if he treats Basic as the Free Trial: `Free Trial limited to evaluation purposes only` and `No commercial use permitted during Free Trial`.

### API key in a header

**Yes, the docs accept the key in a header and recommend it.**

Doc URL: `https://twelvedata.com/docs/introduction` (the same text is at `https://twelvedata.com/docs/introduction/quickstart`), read at 05:29:04Z to 05:29:06Z.

Exact wording, under the heading `Authentication`:

- `Authenticate your requests using one of these methods:`
- `Query parameter method`, then `GET https://api.twelvedata.com/endpoint?symbol=AAPL&apikey=your_api_key`
- `HTTP header method (recommended)`, then `Authorization: apikey your_api_key`

The same page also says: `Secure storage: Store your API key securely and never expose it in client-side code or public repositories.`

What the header changes, and what it does not:

- With the header, the key is not part of the URL, so it does not appear in logs that record URLs.
- A header typed on the command line (`curl -H "Authorization: apikey ..."`) is still an argument to `curl`, so it can still show in the process list while `curl` runs.
- The form below gives the header to `curl` on standard input, so the key is in neither the URL nor the argument list. `printf` is built into zsh and bash and starts no separate process.
- The key still goes to Twelve Data inside the HTTPS request. That cannot be avoided.

Replacement for step 4. Run it in the same Terminal window as step 3:

```bash
printf 'Authorization: apikey %s\n' "$TD_KEY" | curl -s --create-dirs -H @- -o "nov14-sprint/tvbot/real/spy_1h_twelvedata.csv" "https://api.twelvedata.com/time_series?symbol=SPY&interval=1h&outputsize=5000&order=asc&timezone=UTC&format=CSV&delimiter=,"
```

Then clear the key from that Terminal window:

```bash
unset TD_KEY
```

What was and was not checked:

- **Not run:** the request itself. No agent has a key. The docs present the header as a general method and do not say separately that it works with `format=CSV`.
- **Checked:** that this Mac's `curl` (version 8.7.1) reads a header from standard input. Its manual says `Using @- makes curl read the header file from stdin. Added in 7.55.0.` At 05:32:35Z I sent a made-up header named `X-Demo-Header` that way to the public docs page and saw it in the outgoing request (HTTP 200). No key and no `Authorization` header was sent.
- If the header form fails for Matthew (the file starts with `{`), the step 4 command with `apikey=` in the URL is the documented fallback, with the exposure the advisor described.

### Also seen, outside the three points

- The support article says: `Other symbols are fully available on the upper-tier plans! Features like complete historical market data, advanced analytics, and support for mutual funds and ETFs are unlocked with higher tiers.` The Basic card on the pricing page lists `Real-time US equities and ETFs`. SPY is an ETF. Whether Basic returns hourly SPY bars, and how far back they go, stays unverified until Matthew runs the request.
- Terms §17.1, in the prohibited list: `(h) Use data for high-frequency trading without appropriate license`. This confirms the wording quoted in the Twelve Data record above.

### What this changes in the sections above

- **Now confirmed word for word** (they were marked "paraphrased"): the Non-Display Use definition, §2.2(a), §2.2(d), §2.3(g), §2.3(l), §5.6(a) and (b), §17.1(h), "Last updated: January 1, 2026", and the pricing page's "For testing and side projects", "Internal non-display usage", "API requests: 8 (800 a day)", "Real-time US equities and ETFs" and "Free trial is available under the Basic plan".
- **§2.3(b) was quoted short.** The full line is `(b) Redistribute, resell, sublicense, or transfer any Data or access rights to third parties except as expressly permitted by your Subscription Tier, Data Add-ons, or a separate agreement with Twelve Data`.
- **Correction, key handling.** The Twelve Data record says the key is passed in the request URL. The docs also accept it in a header and recommend that.
- **Narrower than first reported.** "Why this one", point 1, rests on the label "Internal non-display usage". The sentence under that label limits use to `testing, evaluation, or development purposes only` and bars display to users and use in production systems.
- **Readings withdrawn.** Under "What Codex should decide", items 1 and 2 give my own reading ("My reading is yes", "suggest it does"). Set those aside. The coordinator asked for wording without a ruling, and the decision is Matthew's.
- **Still not verified for Twelve Data:** the storage timeframes; whether Basic is the "Free Trial", the "Free Tier" or both; how much history Basic returns; whether Basic serves SPY given the support article's ETF sentence; the exchanges behind the volume figure; whether signup asks for a card; the exact CSV header.
