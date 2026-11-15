# Alpaca paper + free IEX data: facts the adapter relies on

Owner: W2 (feed). Every fact below was read on the primary page on **2026-11-15** (UTC). Gemini
(`gemini-public-research`) was used only to find pages and as a second opinion; where it claimed
something no primary page confirmed, the item is marked **[UNVERIFIED]**. No Alpaca API host was
called; only public documentation pages were read.

## 1. Hosts and authentication

| Fact | Source |
|---|---|
| Paper trading base URL is `https://paper-api.alpaca.markets`; paper keys are separate from live keys. | https://docs.alpaca.markets/docs/paper-trading |
| Order endpoint server list shows paper `https://paper-api.alpaca.markets` and live `https://api.alpaca.markets` (the adapter refuses the live host). | https://docs.alpaca.markets/reference/postorder |
| Market data host is `https://data.alpaca.markets` (stock bars endpoints are served there). | https://docs.alpaca.markets/reference/stockbars |
| Auth headers are `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`. | https://docs.alpaca.markets/us/v1.1/docs/authentication-1 ; https://docs.alpaca.markets/docs/about-market-data-api |
| Paper key id prefix (`PK...`) vs live (`AK...`). | **[UNVERIFIED]**: Gemini claimed it; no primary page read states it. Code must not rely on the prefix. |

## 2. Free data scope (IEX only)

| Fact | Source |
|---|---|
| Plans: Basic (free) and Algo Trader Plus ($99/mo). Basic equities coverage is IEX only. | https://docs.alpaca.markets/docs/about-market-data-api |
| Basic historical limit is "latest 15 minutes" (read as: recent SIP data is withheld); Algo Trader Plus has no restriction. | same page |
| Basic: 200 historical API calls/min; Algo Trader Plus: 10,000/min. | same page |
| IEX is "the only feed that can be used without a subscription"; IEX is about 2.5% of market volume, SIP 100%. The `feed` parameter applies to all stock endpoints. | https://docs.alpaca.markets/docs/historical-stock-data-1 |
| Paper-only accounts receive IEX data only. | https://docs.alpaca.markets/docs/paper-trading |

Consequence for the desk: every bar is labeled `DATA_LABEL_IEX` ("IEX-only volume, not consolidated").
IEX volume is a small slice of the tape, so volume filters and VWAP are IEX-local, not market-wide.

## 3. Bars endpoints

Single symbol, used by `alpaca/feed.py`: `GET /v2/stocks/{symbol}/bars`
(https://docs.alpaca.markets/us/reference/stockbarsingle-1)
- `timeframe` required; minute bars are `[1-59]Min` (the feed uses `1Min`).
- `feed` **defaults to `sip`** (options iex/otc/sip/boats). The feed therefore always sends `feed=iex`.
- `start`/`end` are inclusive, RFC-3339 or `YYYY-MM-DD`. Without real-time access, `start` defaults to
  the beginning of the current day but at least 15 minutes ago, and `end` to now minus 15 minutes.
- `limit` default 1000, min 1, max 10000; counts total data points. Paging via `page_token`.
- `adjustment` default `raw`; `sort` asc/desc; `asof`; `currency`.
- Response keys: `bars` (array of `{t,o,h,l,c,v,n,vw}`), `symbol`, `next_page_token` (string or null),
  `currency` (optional).

Multi symbol: `GET /v2/stocks/bars` with required `symbols`; response `bars` is an object keyed by
symbol. Same parameters and paging. (https://docs.alpaca.markets/reference/stockbars)

- `t` is an RFC-3339 timestamp with nanosecond precision (the feed parser accepts 0-9 fraction digits).
- **Bar `t` marks the start of the minute: [UNVERIFIED].** No primary page read states start vs end.
  The feed assumes start and only accepts a 1Min bar into a slot when `slot_open <= t` and
  `t + 1min <= slot_close`. If `t` were the end, every slot would shift by one minute; a live smoke
  test against a known minute should settle it before any reliance.
- Whether 1Min IEX bars include pre/post-market minutes: **[UNVERIFIED]**. The slot filter drops any
  minute outside the calendar's regular session either way.
- Whether a minute with no IEX trade produces a bar: **[UNVERIFIED]**. The feed marks a slot
  `partial: True` when it has fewer 1Min bars than minutes, and emits no bar for a slot with none
  (intake then reports `GAP_IN_SESSION` on the next bar).

## 4. Clock and calendar (trading host)

| Fact | Source |
|---|---|
| `GET /v2/clock` returns `{timestamp, is_open, next_open, next_close}`; example timestamp `2025-06-24T14:15:22-04:00` (offset given, zone not named). | https://docs.alpaca.markets/us/reference/legacyclock |
| `GET /v2/calendar?start&end&date_type` (TRADING default, or SETTLEMENT) returns rows `{date "YYYY-MM-DD", open "HH:MM", close "HH:MM", session_open "HHMM", session_close "HHMM", settlement_date}`; example open 09:30, close 16:00. Zone not stated; values read as US Eastern **[UNVERIFIED zone]**. | https://docs.alpaca.markets/us/reference/legacycalendar |

## 5. NYSE holidays and early closes (calendar coverage 2026-01-01..2027-12-31)

Source: https://www.nyse.com/markets/hours-calendars (read 2026-11-15).

- 2026 closed: Jan 1, Jan 19, Feb 16, Apr 3 (Good Friday), May 25, Jun 19, Jul 3 (Independence Day
  observed), Sep 7, Nov 26, Dec 25. Early close 1:00 p.m. ET: Nov 27, Dec 24.
- 2027 closed: Jan 1, Jan 18, Feb 15, Mar 26 (Good Friday), May 31, Jun 18 (Juneteenth observed),
  Jul 5 (Independence Day observed), Sep 6, Nov 25, Dec 24 (Christmas observed). Early close 1:00 p.m.
  ET: Nov 26.
- Independent arithmetic check: Easter 2027 is Mar 28 (so Good Friday Mar 26); Jun 19, Jul 4 and
  Dec 25 of 2027 fall on weekends, matching the observed dates.
- 2028 is also published but the desk claims nothing past 2027-12-31.

## 6. Orders (used by W1; recorded here as the shared citation)

| Fact | Source |
|---|---|
| Statuses: new, partially_filled, filled, done_for_day, canceled, expired, replaced, pending_cancel, pending_replace, accepted, pending_new, accepted_for_bidding, stopped, rejected, suspended, calculated (schema also lists `held`). | https://docs.alpaca.markets/docs/orders-at-alpaca ; https://docs.alpaca.markets/reference/postorder |
| `client_order_id` is "<= 128 characters", auto-generated if omitted. | https://docs.alpaca.markets/reference/postorder |
| No reduce-only flag exists for equities (none in the order parameters). | https://docs.alpaca.markets/docs/orders-at-alpaca ; postorder |
| Fractional qty only with market and `day` (postorder); fractional orders only with `day` (orders-at-alpaca). The desk uses whole shares. Equity types: market, limit, stop, stop_limit, trailing_stop. `extended_hours` only with limit + day/gtc; market orders cannot be extended-hours. | postorder ; orders-at-alpaca |
| A `day` order not filled by the close is canceled; non-extended orders submitted after 4:00 p.m. ET queue for the next trading day. | orders-at-alpaca |
| POST responses: 200; 403 "Buying power or shares is not sufficient"; 422 "Input parameters are not recognized". | postorder |
| `DELETE /v2/orders/{order_id}`: 204 No Content; 422 "The order status is not cancelable". A 404 for an unknown id is **[UNVERIFIED]** (not documented on the page). | https://docs.alpaca.markets/us/reference/deleteorderbyorderid-1 |

## 7. Paper-account behavior

From https://docs.alpaca.markets/docs/paper-trading:
- Orders fill only when marketable, against the NBBO. Quantity is not checked against NBBO size.
- Random-size partial fills occur 10% of the time.
- Not simulated: dividends, regulatory fees, market impact, latency slippage, queue position, price
  improvement. Borrow fees "coming soon".

From https://docs.alpaca.markets/docs/user-protection:
- Wash-trade protection applies in paper and returns 403. If either order is market or stop, the new
  order is rejected; for two limit/stop-limit orders, only when buy limit >= sell limit. Bracket, OCO
  and trailing stops are exempt.
- Pattern day trader rule on paper: **[UNVERIFIED]** (not stated on the pages read; intraday margin
  rule page: https://docs.alpaca.markets/us/docs/the-intraday-margin-rule, not relied on).

## 8. Rate limits

Exceeding a limit returns HTTP 429 with `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
`X-RateLimit-Reset`. (https://docs.alpaca.markets/docs/rate-limits) The desk is manual (one fetch per
operator click, a handful of pages per day), far below 200/min.

## Open items to settle at Matthew's first authenticated smoke test (not run by agents)

1. Bar `t` = minute start (compare one known minute's 1Min bar against the 1Hour bar).
2. Extended-hours minutes in 1Min IEX bars.
3. Minutes without IEX trades: absent bar vs zero-volume bar.
4. `/v2/calendar` time zone (expect ET).
5. Cancel of an unknown id: status code.
6. Whether Basic's "latest 15 minutes" historical restriction also applies to `feed=iex` (read here as
   SIP-only). If it applies to IEX, a fetch right after a slot close returns 403 or no minutes, and the
   feed raises FeedError or reports `empty_slots`; it never invents a bar.

## Trading-API facts relayed by W1 (2026-11-15, not re-checked by W2)

Full citations are S1-S14 in `alpaca/STATUS_W1.md`.

1. `GET /v2/orders` takes `limit` up to 500 (default 50). Source: docs.alpaca.markets/reference/getallorders
2. `GET /v2/orders:by_client_order_id?client_order_id=...` looks up one order by client id. Source:
   docs.alpaca.markets/reference/getorderbyclientorderid
3. `DELETE /v2/orders/{id}` returns 204 when the cancel is accepted and 422 when the order cannot be canceled;
   an order in `pending_cancel` can still fill. Sources: docs.alpaca.markets/reference/deleteorderbyorderid and
   docs.alpaca.markets/docs/orders-at-alpaca
4. [UNVERIFIED, third-party only] A duplicate `client_order_id` returns 422 "must be unique".
