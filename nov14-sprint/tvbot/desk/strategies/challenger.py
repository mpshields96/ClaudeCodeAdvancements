"""Frozen shadow challenger for the decision lab (desk/alpaca/CONTRACT.md section 7).

SHADOW ONLY. It is not in strategies.registry.STRATEGIES, so it can never be
loaded, routed or launched as the active strategy; the lab reaches it through
lab.SHADOW. It never sizes, never changes limits and never promotes itself.

Rule (one bar horizon, decided at a bar's close from bars closed by then):
  trend      close above a rising 8-bar EMA -> long; below a falling one -> short
  volatility 6-bar ATR, in bps of the close, must sit inside [10, 150] bps
  cost       expected move (|EMA slope| bps per bar x 1 bar) must clear the
             assumed round-trip cost; the doubled-friction view is reported
Otherwise it passes and says what must change.

PARAMS were written down on FROZEN_AT before any lab score existed and are not
tuned on outcomes. CFG_HASH pins them; tests fail if they change. Costs are the
desk's ASSUMED cost model (strategies/base.py DEFAULT_COSTS): IEX bars carry no
spread, so nothing here is a measured friction.
"""
import hashlib
import json

from . import base as B

NAME = "challenger"
FROZEN_AT = "2026-11-15"
RULE_VERSION = "1.0.0"
PARAMS = {
    "ema_len": 8,
    "slope_lookback": 3,
    "atr_len": 6,
    "vol_floor_bps": 10.0,
    "vol_cap_bps": 150.0,
    "hurdle_mult": 1.0,
    "sensitivity_mult": 2.0,
    "min_bars": 10,
    "horizon_bars": 1,
}
CFG_HASH = hashlib.sha256(json.dumps(PARAMS, sort_keys=True).encode("utf-8")).hexdigest()[:12]
RULE_ID = "CHALLENGER-%s-%s" % (RULE_VERSION, CFG_HASH[:8])
COST_LABEL = "ASSUMED desk cost model (no spread in IEX bars): " \
             "half spread 1.0 bps + slippage 2.0 bps per side + commission $0.005/share (min $1)"


def _ema(vals, n):
    a = 2.0 / (n + 1.0)
    e = vals[0]
    out = [e]
    for v in vals[1:]:
        e = a * v + (1.0 - a) * e
        out.append(e)
    return out


def _atr(bars, n):
    trs = []
    for prev, b in zip(bars[-n - 1:-1], bars[-n:]):
        h, lo, pc = float(b["high"]), float(b["low"]), float(prev["close"])
        trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    return sum(trs) / len(trs)


def _rt_bps(qty, price, mult):
    est = B.est_cost(qty, price, B.cost_cfg({"cost_mult": mult}))
    return est, (est["usd"] / (qty * price) * 1e4 if qty and price else None)


def indicators(bars):
    """Indicator values the rule reads at the last bar (None before min_bars)."""
    p = PARAMS
    if len(bars) < p["min_bars"]:
        return None
    closes = [float(b["close"]) for b in bars]
    ema = _ema(closes, p["ema_len"])
    L = p["slope_lookback"]
    slope = (ema[-1] - ema[-1 - L]) / ema[-1 - L] * 1e4 / L
    close = closes[-1]
    return {"close": round(close, 6), "ema": round(ema[-1], 6), "slope_bps_per_bar": round(slope, 4),
            "atr_bps": round(_atr(bars, p["atr_len"]) / close * 1e4, 4)}


def decide(bars_so_far, position=None, cfg=None):
    """decide(bars_so_far, position, cfg) -> Decision. `position` is ignored (shadow, stateless);
    cfg may carry "now" (bar cut-off) and "test_size" (read-only TEST notional for cost estimates).
    PARAMS never come from cfg."""
    c = dict(cfg or {})
    bars = B.knowable_bars(bars_so_far, c.get("now"))
    if not bars:
        d = B.no_data_decision(NAME, RULE_ID, c)
        d["refusal_checks"] = [{"id": "NO_BARS", "passed": False, "detail": "no closed bar yet"}]
        return _tag(d, None, None)
    bar = bars[-1]
    p = PARAMS
    ind = indicators(bars)
    size = c.get("test_size") or B.load_test_size()
    none = B.line(None, "none")
    if ind is None:
        d = B.make_decision(
            NAME, RULE_ID, bar, "pass", 0, "NOT_ENOUGH_BARS",
            "Only %d closed bars; the rule needs %d." % (len(bars), p["min_bars"]),
            "None yet.", "Indicators are undefined before %d bars." % p["min_bars"],
            B.est_cost(0, None, B.cost_cfg({})),
            "Passes until %d bars have closed (%d more)." % (p["min_bars"], p["min_bars"] - len(bars)),
            none, none, none, none,
            refusal_checks=[{"id": "BARS", "passed": False, "detail": "%d < %d" % (len(bars), p["min_bars"])}])
        return _tag(d, None, None)
    close, ema, slope, atr = ind["close"], ind["ema"], ind["slope_bps_per_bar"], ind["atr_bps"]
    qty = B.base_qty(close, {"test_size": size})
    est, rt = _rt_bps(qty, close, 1.0)
    est2, rt2 = _rt_bps(qty, close, p["sensitivity_mult"])
    exp_move = abs(slope) * p["horizon_bars"]
    side = 1 if (slope > 0 and close > ema) else (-1 if (slope < 0 and close < ema) else 0)
    hurdle = None if rt is None else rt * p["hurdle_mult"]
    checks = [
        {"id": "BARS", "passed": True, "detail": "%d bars" % len(bars)},
        {"id": "TREND", "passed": side != 0,
         "detail": "close %.4f vs EMA %.4f, slope %.2f bps/bar" % (close, ema, slope)},
        {"id": "VOL_FLOOR", "passed": atr >= p["vol_floor_bps"],
         "detail": "ATR %.2f bps vs floor %.1f" % (atr, p["vol_floor_bps"])},
        {"id": "VOL_CAP", "passed": atr <= p["vol_cap_bps"],
         "detail": "ATR %.2f bps vs cap %.1f" % (atr, p["vol_cap_bps"])},
        {"id": "COST_HURDLE", "passed": hurdle is not None and exp_move >= hurdle,
         "detail": "expected move %.2f bps vs round-trip %s bps (ASSUMED costs)"
                   % (exp_move, "n/a" if rt is None else "%.2f" % rt)},
        {"id": "SHADOW_ONLY", "passed": True, "detail": "lab shadow decision; never routed, never sized"},
    ]
    sens = {"round_trip_bps": None if rt is None else round(rt, 4),
            "round_trip_bps_2x": None if rt2 is None else round(rt2, 4),
            "expected_move_bps": round(exp_move, 4),
            "clears_1x": hurdle is not None and exp_move >= hurdle,
            "clears_2x": rt2 is not None and exp_move >= rt2 * p["hurdle_mult"]}
    if qty <= 0:
        code, why, cond = ("ZERO_SIZE", "The TEST notional buys no whole share at %.2f." % close,
                           "Passes while the TEST notional is below one share's price.")
    elif side == 0:
        code, why = "NO_TREND", "Close and EMA slope disagree (close %.2f, EMA %.2f, slope %.2f bps/bar)." % (
            close, ema, slope)
        cond = "Close above a rising EMA (long) or below a falling EMA (short)."
    elif atr < p["vol_floor_bps"]:
        code, why = "VOL_TOO_LOW", "ATR %.2f bps is under the %.1f bps floor." % (atr, p["vol_floor_bps"])
        cond = "ATR must reach %.1f bps of price (now %.2f)." % (p["vol_floor_bps"], atr)
    elif atr > p["vol_cap_bps"]:
        code, why = "VOL_TOO_HIGH", "ATR %.2f bps is over the %.1f bps cap." % (atr, p["vol_cap_bps"])
        cond = "ATR must fall to %.1f bps of price (now %.2f)." % (p["vol_cap_bps"], atr)
    elif not sens["clears_1x"]:
        code = "COST_HURDLE"
        why = "Expected move %.2f bps does not clear the %.2f bps round-trip cost." % (exp_move, rt)
        cond = "|EMA slope| must reach %.2f bps per bar (now %.2f)." % (hurdle / p["horizon_bars"], abs(slope))
    else:
        code = None
    if code is not None:
        trig = B.line(ema, "close must sit on the EMA's trend side; EMA here") if code == "NO_TREND" else none
        d = B.make_decision(
            NAME, RULE_ID, bar, "pass", 0, code, why,
            "Passing costs nothing and avoids a trade the rule cannot justify.",
            "If the move happens anyway the pass misses it (scored as HYPOTHETICAL).",
            B.est_cost(0, None, B.cost_cfg({})), cond, trig, none, none, none, refusal_checks=checks)
        return _tag(d, ind, sens)
    action = "enter_long" if side > 0 else "enter_short"
    target = close * (1.0 + side * exp_move / 1e4)
    d = B.make_decision(
        NAME, RULE_ID, bar, action, qty, "TREND_LONG" if side > 0 else "TREND_SHORT",
        "Close %s a %s EMA, ATR %.2f bps in band, expected move %.2f bps clears %.2f bps round trip%s."
        % ("above" if side > 0 else "below", "rising" if side > 0 else "falling", atr, exp_move, rt,
           "" if sens["clears_2x"] else " (fails the doubled-friction view)"),
        "Trend and volatility agree and the expected move clears assumed costs.",
        "EMA slope is a lagging estimate; one-bar moves are noisy; costs are assumed, not measured.",
        est, "Shadow forecast only; the lab scores it on the next bar.",
        B.line(close, "decided at this close; shadow entry at the next bar's open"),
        B.line(close, "next bar open (shadow, never routed)"),
        B.line(target, "close of the next bar (1-bar horizon)"),
        B.line(ema, "a close back through the EMA invalidates the trend"),
        refusal_checks=checks)
    return _tag(d, ind, sens)


def _tag(d, ind, sens):
    d.update({"shadow": True, "never_routed": True, "frozen_at": FROZEN_AT, "cfg_hash": CFG_HASH,
              "params": dict(PARAMS), "indicators": ind, "cost_view": sens, "cost_label": COST_LABEL,
              "horizon_bars": PARAMS["horizon_bars"],
              "exposure": 1 if d["action"] == "enter_long" else (-1 if d["action"] == "enter_short" else 0)})
    return d
