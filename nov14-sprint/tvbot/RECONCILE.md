# RECONCILE: TradingView policy text against Codex's summary

Written 2026-11-14 by the TV bot lane (Claude). Pages were fetched on 2026-11-14 by a research
subagent through a summarising web fetch, not a raw download. The short phrases in quotation
marks are what that fetch returned as the page's own words. Treat them as close but not
letter-perfect, and open the page before relying on any one phrase. Nothing here is legal advice.

## The rule this lane was given (Codex's reading of sections 3 and 27)

1. TradingView alerts and values must not feed an external model or a paper-order ledger. Pine and
   its alerts stay human-visible, for Matthew to read.
2. The paper runner is fed only by explicitly synthetic data or by an independently permitted
   non-TradingView source.
3. Any TradingView-origin input fails closed.

## What the policy pages say

Source: https://www.tradingview.com/policies/ (Terms of Use, Policies and Disclaimers)

| Section | What it says, in plain words | Short phrase from the page |
|---|---|---|
| 3, licence and prohibited uses | The licence is for viewing the data on screen. It lists uses that are not allowed, including feeding the data to a machine that acts on it. | "automated order generation" |
| 3, same list | Decisions made by a program from the data are also on the list. | "algorithmic decision-making" |
| 3, webhooks | Webhook alerts are allowed only inside that same display-only scope. | "intended solely for permissible uses within the scope of display" |
| 12 | No scraping, and no using the content to train models or build datasets. | (paraphrase only) |
| 26, AI features | Rules for TradingView's own AI features. Nothing there widens section 3. | (paraphrase only) |
| 27.3, MCP server | No automated trading or decision-making through the connector, including joining an alert to an outside program. | "a webhook, bot or other system" |
| 27.4, MCP server | A narrow exception: answering the user's own request in human-readable form. | (paraphrase only) |

Webhook help page: https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
Facts used by this lane's refusal list: webhook alerts come from four published addresses
(52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7), go only to ports 80 and 443, time out
after 3 seconds and need two-factor sign-in on the account.

## Where the page and Codex's summary differ

- The summary is a fair reading. The page bans automated orders and algorithmic decisions from
  the data and keeps webhooks inside display-only use.
- The words "paper", "ledger", "simulated" and "paid" do not appear in the policy text that was
  fetched. Applying the ban to a paper ledger is Codex's inference, not the page's wording. A
  looser reading (paper-only use is not "order generation") is possible.
- The section 27.4 exception covers a person asking a question and reading the answer. It does not
  cover a program reading alerts.
- [UNVERIFIED] Whether a paid plan changes any of this. The pricing page was not read.

## Decision

The stricter reading is kept, as the brief requires. In this lane:

- The Pine script only draws on the chart and raises alerts with text for a person to read. No
  webhook address is configured or suggested, and no listener or tunnel exists.
- The paper runner reads only files whose first record declares a permitted source. The only
  built-in permitted source is `synthetic`, and a synthetic feed must use a `SYNTH-` symbol.
- Any file, file name, field or transport note that carries a TradingView marker is refused whole
  before a single bar is read (`bot/provenance.py`). The markers are: the names TradingView and
  Pine, the token `tv`, alert placeholders such as `{{close}}`, strategy and alert field names,
  the word webhook, exchange-prefixed tickers such as `AMEX:SPY`, the four webhook addresses, and
  a chart-export CSV header.
- A different real source can be added only through a permitted-sources file that carries the
  terms URL, a quote of the terms, a named human approver and a date. None has been added.

## What code cannot catch

Someone could type TradingView numbers by hand into a file and label it synthetic. No scan can
detect that. The control is the rule above and the person following it.
