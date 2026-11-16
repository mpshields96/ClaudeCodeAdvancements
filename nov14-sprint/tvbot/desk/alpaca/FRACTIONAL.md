# Fractional SPY pilot

Fractional sizing is opt-in on a connected Alpaca equity desk. The default whole-share rehearsal keeps its existing behavior. Approve a fixed positive share quantity (up to nine decimal places), a maximum order value, maximum total exposure including working buys, planned loss per trade, realized daily loss limit, and maximum new entry attempts per trading date. No personal values ship with the desk.

The connected route sends a simple regular-hours DAY buy limit. It never raises the quantity to meet the minimum. Both the fresh IEX ask and the capped limit must value the fixed quantity at at least one dollar. The venue clock must be open, the signal bar must leave an eligible entry window on the exchange calendar, and SPY must be tradable and fractionable. The desk checks fresh cash and non-margin buying power, limits available funding by effective buying power when supplied, counts working buy reservations, and holds if a foreign SPY buy is outstanding.

Before a live fractional buy can be sent, a SQLite transaction reserves the account/date attempt on this Mac. The store is in the user's Library/Application Support/SPY Desk/live-risk directory and identifies accounts by a hash. Separate extracted kits share this store. A rejected or uncertain send still uses the attempt, even if the broker never returns an order row. Full account order history is also checked; incomplete reads or an unreadable ledger block a new entry. Do not move or delete the risk store to reset a budget. This is one-Mac protection; two trading machines do not share the local store. The cash and working-order checks see the venue as of their read, not future external orders.

Protective DAY stops and exits use the desk-owned remaining fractional quantity. The buy minimum and new-entry cap do not apply to reductions. Track a refused protective order or unconfirmed close in the desk; a stop price does not guarantee an execution price or a fill. Paper acceptance does not certify a live fill.

## Cost model

Connected fractional strategy decisions use the named Alpaca equity profile. For small orders the model reserves regulatory charges per fee class and order. The resulting reserve is deliberately conservative; it is not an account fee quotation. Published retail equity commissions can be zero, and actual regulatory charges can be aggregated. The strategy combines modeled trading costs with the distance to its frozen stop. If that sum exceeds the approved loss budget, the strategy holds without an order. Review [Alpaca's fee schedule](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf), [regulatory-fee aggregation](https://docs.alpaca.markets/us/docs/regulatory-fees), [fractional orders](https://docs.alpaca.markets/us/docs/fractional-trading), and [paper simulation](https://docs.alpaca.markets/us/docs/paper-trading).

## Operation

The live launcher requires the operator's date-specific terminal confirmation, starts disarmed with the adapter off, and does not schedule trading. Open the connected paper desk for simulated money. Its launcher prefers the dedicated paper approval; an older installation can still use its approved rehearsal worksheet. Use **Check for new bars** to evaluate a fresh completed bar. TradingView is a reference chart; the strategy uses Alpaca IEX data. Test fixtures and historical marks are not venue fills.
