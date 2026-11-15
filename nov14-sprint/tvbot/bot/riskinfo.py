"""Plain risk numbers for the gate and the result page. Stdlib only.

One place computes them so the gate, the page and STATUS.md cannot disagree.
Nothing here places an order or reads a feed.
"""

GATE_SCHEMA = "tvbot-paper-gate-1"
APPROVE_TEXT = "APPROVE PAPER ONLY"
PASS_TEXT = "PASS"
SCOPE = ("Paper mode only. This approves the runner reading a real-bar file that Matthew "
         "supplied and writing paper rows on this Mac. It approves no real order, account, "
         "key, purchase or money movement, and nothing here can place one.")


def stop_out_estimate(cfg, params):
    """What one trade loses if it exits exactly at its stop level.

    price loss = order size x stop percent
    costs      = spread and slippage on the way in and on the way out, plus two commissions.
    The stop is checked when a bar closes and the sale fills at a later open, so a real
    loss can be larger than this. The estimate is a floor for a stopped trade, not a cap.
    """
    n = float(cfg["order_notional"])
    bps = (cfg["half_spread_bps"] + cfg["slippage_bps"]) / 1e4
    stop = float(params["stop_pct"]) / 100.0
    limit = float(cfg["limits"]["max_daily_loss"])
    max_qty = cfg["limits"]["max_qty"]
    commission = max(float(cfg["commission_min"]), max_qty * float(cfg["commission_per_share"]))
    price_loss = n * stop
    costs = n * bps + n * (1.0 - stop) * bps + 2.0 * commission
    total = price_loss + costs
    return {
        "order_notional": n,
        "stop_pct": float(params["stop_pct"]),
        "price_loss_at_stop": round(price_loss, 2),
        "costs_both_sides": round(costs, 2),
        "one_stop_estimate": round(total, 2),
        "max_daily_loss": limit,
        "stop_share_of_daily_limit_pct": round(100.0 * total / limit, 1),
        "stops_before_daily_limit": int(limit // total) if total > 0 else None,
        "note": "The stop is checked on bar closes and the sale fills at a later open, so one "
                "losing trade can cost more than this estimate and more than the daily limit.",
    }


def worst_round_trip(summary):
    """The worst closed trade in a saved run summary, or None."""
    trips = (summary or {}).get("round_trips") or []
    if not trips:
        return None
    w = min(trips, key=lambda t: t["net_pnl"])
    return {"net_pnl": round(w["net_pnl"], 2), "exit_reason": w.get("exit_reason"),
            "entry_fill_ts": w.get("entry_fill_ts"), "exit_fill_ts": w.get("exit_fill_ts")}
