"""Decision lab scorer (CONTRACT section 7). HYPOTHETICAL shadow scores only.

A forecast is scored only against later bars: bars whose ts_close is after the
forecast's ts_knowable, whose ts_open is at or after the decided bar's close, and
which entered the lab's bar store after the forecast was written (store index >=
bars_known_count). The score holds the exposure from the first later bar's open
to the horizon bar's close.

  trade (enter_long / enter_short): net of ASSUMED costs (both legs' spread and
      slippage via strategies.base.side_price, plus both commissions); the
      doubled-friction view uses cost multiplier 2.
  hold with exposure: mark-to-market over the same bars, no new cost.
  pass / flat: 0, labeled "HYPOTHETICAL (pass, not traded)", plus what a long and
      a short would have netted at the TEST-notional size.

Nothing here is realized P&L. The challenger row also carries its difference
against the EMA baseline and against cash (0) for the same bar.
"""
from strategies import base as B
from strategies import challenger as CH

from . import record as R

HORIZON = CH.PARAMS["horizon_bars"]
PASS_LABEL = "HYPOTHETICAL (pass, not traded)"
CORE_KEYS = ("horizon_bars", "exposure", "qty", "kind", "entry", "exit", "gross_bps", "net_usd",
             "net_bps", "net_usd_2x", "net_bps_2x", "hypothetical", "entry_lag_s", "entry_attainable",
             "crosses_session")


def later_bars(store, f, horizon=HORIZON):
    """(bars, shas) eligible for forecast `f`, oldest first; [] until `horizon` exist."""
    knowable = B.parse_ts(f["ts_knowable"])
    decided = B.parse_ts(f["bar_ts_close"])
    seen, cand = set(), []
    for i, r in enumerate(store.rows["bars"]):
        b = r["bar"]
        if i < f["bars_known_count"]:
            continue
        key = (b.get("ts_open"), b.get("ts_close"))
        if key in seen:
            continue          # first stored version of a slot wins
        if B.parse_ts(b["ts_close"]) > knowable and B.parse_ts(b["ts_open"]) >= decided:
            seen.add(key)
            cand.append((B.parse_ts(b["ts_close"]), i, r["bar_sha"], b))
    cand.sort(key=lambda t: (t[0], t[1]))
    cand = cand[:horizon]
    if len(cand) < horizon:
        return [], []
    return [c[3] for c in cand], [c[2] for c in cand]


def _leg(entry_raw, exit_raw, side, qty, mult):
    costs = B.cost_cfg({"cost_mult": mult})
    e = B.side_price(entry_raw, side, costs)
    x = B.side_price(exit_raw, -side, costs)
    usd = qty * side * (x - e) - 2.0 * B.commission(qty, costs)
    return e, x, usd


def compute_core(f, later):
    """Pure score of forecast row `f` on its later bars (verify recomputes this)."""
    s = int(f.get("exposure") or 0)
    first, last = later[0], later[-1]
    entry_raw, exit_raw = float(first["open"]), float(last["close"])
    lag = (B.parse_ts(f["ts_knowable"]) - B.parse_ts(first["ts_open"])).total_seconds()
    core = {"horizon_bars": len(later), "exposure": s, "qty": int(f.get("qty") or 0),
            "entry": {"raw": entry_raw, "ts": first["ts_open"], "basis": "next bar open (proxy)"},
            "exit": {"raw": exit_raw, "ts": last["ts_close"], "basis": "horizon bar close"},
            "gross_bps": round(s * (exit_raw / entry_raw - 1.0) * 1e4, 4),
            "entry_lag_s": round(max(lag, 0.0), 3), "entry_attainable": lag <= 60.0,
            "crosses_session": B.parse_ts(first["ts_open"]) > B.parse_ts(f["bar_ts_close"]),
            "hypothetical": None}
    trade = f.get("action") in ("enter_long", "enter_short") and s != 0 and core["qty"] > 0
    if trade:
        q = core["qty"]
        e, x, usd = _leg(entry_raw, exit_raw, s, q, 1.0)
        e2, x2, usd2 = _leg(entry_raw, exit_raw, s, q, 2.0)
        core["entry"]["fill"], core["exit"]["fill"] = round(e, 6), round(x, 6)
        core.update({"kind": "trade", "net_usd": round(usd, 4), "net_bps": round(usd / (q * entry_raw) * 1e4, 4),
                     "net_usd_2x": round(usd2, 4), "net_bps_2x": round(usd2 / (q * entry_raw) * 1e4, 4)})
    elif s != 0:
        core.update({"kind": "hold (mark-to-market, no new cost)", "net_usd": None,
                     "net_bps": core["gross_bps"], "net_usd_2x": None, "net_bps_2x": core["gross_bps"]})
    else:
        q = B.base_qty(entry_raw, dict(f.get("cfg") or {}))   # TEST notional, read only
        hyp = {"label": PASS_LABEL, "qty": q}
        if q > 0:
            for name, side in (("if_long", 1), ("if_short", -1)):
                _, _, usd = _leg(entry_raw, exit_raw, side, q, 1.0)
                _, _, usd2 = _leg(entry_raw, exit_raw, side, q, 2.0)
                hyp[name] = {"net_usd": round(usd, 4), "net_bps": round(usd / (q * entry_raw) * 1e4, 4),
                             "net_bps_2x": round(usd2 / (q * entry_raw) * 1e4, 4)}
        core.update({"kind": "pass/flat", "net_usd": 0.0, "net_bps": 0.0, "net_usd_2x": 0.0,
                     "net_bps_2x": 0.0, "hypothetical": hyp})
    return {k: core.get(k) for k in CORE_KEYS}


def comparison(ch_core, ema_core):
    out = {"vs_cash_net_bps": ch_core["net_bps"], "vs_cash_net_bps_2x": ch_core["net_bps_2x"]}
    if ema_core is not None:
        out["vs_ema_net_bps"] = round(ch_core["net_bps"] - ema_core["net_bps"], 4)
        out["vs_ema_net_bps_2x"] = round(ch_core["net_bps_2x"] - ema_core["net_bps_2x"], 4)
    return out


def score_pending(state_dir, store=None):
    """Score every unscored forecast whose later bars exist. Idempotent; returns new rows."""
    st = store or R.Store(state_dir)
    groups = {}
    for f in st.rows["forecasts"]:
        if f["forecast_id"] not in st.scored:
            groups.setdefault(f["group_id"], []).append(f)
    wrote = []
    for gid, rows in groups.items():
        later, shas = later_bars(st, rows[0])
        if not later:
            continue
        cores = {f["strategy"]: compute_core(f, later) for f in rows}
        ema_core = cores.get("ema")
        if ema_core is None:
            e = st.forecast_index.get("fc-ema-%s" % gid[4:])
            ema_core = None if e is None else compute_core(e, later)
        for f in rows:
            row = {"format": R.FORMAT, "label": R.SCORE_LABEL, "score_id": "sc-" + f["forecast_id"][3:],
                   "forecast_id": f["forecast_id"], "group_id": gid, "strategy": f["strategy"],
                   "scored_at": R.now_iso(), "later_bar_shas": shas, "later_bars": later,
                   "forecast_row_hash": f["row_hash"],
                   "synthetic": bool(f.get("synthetic_inputs")) or any(R._synthetic(b) for b in later)}
            row.update(cores[f["strategy"]])
            if f["strategy"] == "challenger":
                row.update(comparison(cores["challenger"], ema_core))
            wrote.append(st.append("scores", row))
            st.scored[f["forecast_id"]] = wrote[-1]
    return wrote
