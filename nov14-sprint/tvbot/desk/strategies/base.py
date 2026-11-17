"""Decision record, cost model and bar helpers shared by every desk strategy.

Paper and offline only. Standard library, Python 3.9. Every value here is
simulated.

Decision fields (fixed by desk/CONTRACT.md):
  decision_id, ts_knowable, symbol, strategy, action, qty, reason_code,
  reason_text, case_for, case_against, est_cost, pass_condition, trigger,
  intended_entry, intended_exit, invalidation, and [v2] refusal_checks:
  a list of {id, passed, detail}; passed=True means that test did not block.

Shapes used by this worker (the UI draws the four price lines):
  action          one of enter_long | enter_short | exit | pass | hold
  qty             whole units (shares, ounces or contracts), 0 for pass/hold;
                  an exact fraction (JSON float via orders/qty.to_json, plus
                  qty_text) only on the opt-in fractional EMA path
  est_cost        {"usd": round-trip estimate for this action's quantity,
                   "per_side_usd", "basis", "simulated": True}
  trigger, intended_entry, intended_exit, invalidation
                  {"price": float or None, "text": plain English}
Extra keys (allowed, never required by the contract): simulated, rule_id,
bar_seq, bar_ts_close, net_qty_after, basket.

Sizing: the per-order notional is Matthew's TEST VALUE in
tvbot/config/smaller_size.json. Strategies read it and never change it.
"""
import hashlib
import json
import math
import os
import re
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - 3.9 ships zoneinfo
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
try:
    from orders import qty as Q
except ImportError:  # strategies imported without desk/ on sys.path
    import sys as _sys
    _sys.path.insert(0, DESK)
    from orders import qty as Q
TVBOT = os.path.dirname(DESK)
SIZE_PATH = os.path.join(TVBOT, "config", "smaller_size.json")

ACTIONS = ("enter_long", "enter_short", "exit", "pass", "hold")
DECISION_FIELDS = (
    "decision_id", "ts_knowable", "symbol", "strategy", "action", "qty",
    "reason_code", "reason_text", "case_for", "case_against", "est_cost",
    "pass_condition", "trigger", "intended_entry", "intended_exit",
    "invalidation", "refusal_checks",
)
LINE_FIELDS = ("trigger", "intended_entry", "intended_exit", "invalidation")

# Cost model mirrored from tvbot/bot/engine.py DEFAULT_CONFIG (read only):
# half spread 1.0 bps, slippage 2.0 bps per side, commission $0.005 a share
# with a $1.00 minimum per order. These are assumptions, not broker quotes.
DEFAULT_COSTS = {
    "kind": "bps",
    "half_spread_bps": 1.0,
    "slippage_bps": 2.0,
    "commission_per_share": 0.005,
    "commission_min": 1.0,
}

# Named profile for Alpaca US equities, selected ONLY by cfg["cost_profile"] ==
# "alpaca_equity" (W-D sets it in fractional connected mode). DEFAULT_COSTS above
# stays the offline/whole-share stress. Spread and slippage are the same modeled
# bps. Commission is 0 because Alpaca's fee schedule says it "does not charge
# commissions" outside index options, Elite routing and non-retail flow. The
# pass-through regulatory fees are added per order (sources and fetch time in
# alpaca-acceptance/WINDOW90_W-A_RESULT.md):
#   SEC Section 31: $0.0000206 x trade value, sells only (Alpaca schedule).
#   FINRA TAF: Alpaca's Oct 12, 2026 schedule lists retail TAF "$0 per share",
#     so the profile charges $0 (W120 correction: the former $0.000195/share
#     FINRA member-rate reserve is not an Alpaca retail charge).
#   CAT: $0.000003 per executed equivalent share, buys and sells (Alpaca schedule).
#   Rounding: Alpaca's schedule aggregates each fee type daily per account and
#     rounds it UP to $0.01. A ROUND-TRIP estimate (est_cost sides=2) is therefore
#     one trading day's total: each fee type summed over the buy and the sell,
#     then rounded up once (W120 correction). This holds because desk sessions end
#     flat, so the exit is the same day as the entry; with max_daily_entries 1 the
#     round trip is the whole day's activity. reg_fees (one order, fill accounting)
#     still rounds per order, which is never lower.
# These are estimates, never broker quotes or account fees.
ALPACA_EQUITY_COSTS = {
    "kind": "bps",
    "profile": "alpaca_equity",
    "half_spread_bps": 1.0,
    "slippage_bps": 2.0,
    "commission_per_share": 0.0,
    "commission_min": 0.0,
    "sec_rate": 0.0000206,
    "taf_per_share": 0.0,        # Alpaca Oct 12, 2026 schedule: retail TAF $0 per share
    "taf_max": 9.79,
    "cat_per_share": 0.000003,
    "fee_round": "daily_per_type_penny_up",
}
ALPACA_FEE_SOURCES = (
    "https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf",
    "https://docs.alpaca.markets/us/docs/regulatory-fees",
    "https://www.finra.org/sites/default/files/2024-11/NOF-IMM-EFF-FINRA-2024-019.pdf",
)
_CENT = Decimal("0.01")


def load_test_size(path=None):
    """Matthew's TEST VALUE for the per-order notional. Read only."""
    p = path or SIZE_PATH
    with open(p, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    val = raw.get("order_notional")
    if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
        raise ValueError("order_notional in %s must be a positive number" % p)
    return {"order_notional": float(val), "label": "TEST VALUES", "source": p}


_FRAC = re.compile(r"^(.*T\d{2}:\d{2}:\d{2}\.)(\d+)(.*)$")


def parse_ts(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    t = str(s).strip()
    if t.endswith("Z") or t.endswith("z"):
        t = t[:-1] + "+00:00"
    # Same rule as orders/calendar.parse_ts: RFC 3339 allows any fraction length but
    # Python 3.9's fromisoformat takes exactly 3 or 6 digits. Keep six: truncate extra
    # digits (never rounds into the next second or day), right-pad short ones with zeros.
    m = _FRAC.match(t)
    if m:
        t = m.group(1) + m.group(2)[:6].ljust(6, "0") + m.group(3)
    d = datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def fmt_ts(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_bar(rec):
    return isinstance(rec, dict) and rec.get("type", "bar") == "bar" and "ts_close" in rec


def knowable_bars(bars_so_far, now=None):
    """Bars that had closed by `now` (all bars when now is None), in order.
    Manifest lines and anything without ts_close are skipped."""
    out = [b for b in (bars_so_far or []) if is_bar(b)]
    if now is not None:
        cut = parse_ts(now)
        out = [b for b in out if parse_ts(b["ts_close"]) <= cut]
    return out


def ts_knowable(bar):
    """First moment this bar's close was knowable to the desk: its close,
    or the later delivery time when the feed records one."""
    t = parse_ts(bar["ts_close"])
    if bar.get("delivered_ts"):
        d = parse_ts(bar["delivered_ts"])
        if d > t:
            t = d
    return fmt_ts(t)


def timeframe(bar):
    return parse_ts(bar["ts_close"]) - parse_ts(bar["ts_open"])


def cost_cfg(cfg):
    prof = (cfg or {}).get("cost_profile")
    c = dict(ALPACA_EQUITY_COSTS if prof == "alpaca_equity" else DEFAULT_COSTS)
    c.update((cfg or {}).get("costs") or {})
    mult = float((cfg or {}).get("cost_mult", 1.0))
    c["mult"] = mult
    return c


def side_price(raw, side, costs):
    """Fill price for a buy (+1) or sell (-1) at raw price `raw`.
    bps model: raw is a mid; adverse half spread + slippage.
    per_unit_bid model: raw is a bid; buys pay spread + slip, sells give slip."""
    m = costs.get("mult", 1.0)
    if costs["kind"] == "per_unit_bid":
        if side > 0:
            return raw + (costs["spread"] + costs["slip"]) * m
        return raw - costs["slip"] * m
    bps = (costs["half_spread_bps"] + costs["slippage_bps"]) * m / 1e4
    return raw * (1.0 + bps) if side > 0 else raw * (1.0 - bps)


def commission(qty, costs):
    if costs["kind"] == "per_unit_bid":
        return float(costs.get("commission_per_unit", 0.0)) * abs(qty) * costs.get("mult", 1.0)
    if qty == 0:
        return 0.0
    m = costs.get("mult", 1.0)
    return max(costs["commission_min"] * m, abs(qty) * costs["commission_per_share"] * m)


def liq_linear(qty, costs):
    """Liquidation value of a signed position as a*p + c per unit, so
    thresholds can be solved for a price. Returns (a, c)."""
    m = costs.get("mult", 1.0)
    if costs["kind"] == "per_unit_bid":
        if qty > 0:
            return 1.0, -costs["slip"] * m
        return 1.0, (costs["spread"] + costs["slip"]) * m
    bps = (costs["half_spread_bps"] + costs["slippage_bps"]) * m / 1e4
    return (1.0 - bps, 0.0) if qty > 0 else (1.0 + bps, 0.0)


def _dq(x):
    """Exact Decimal of a quantity or price (int, Decimal, or float via repr)."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int) and not isinstance(x, bool):
        return Decimal(x)
    return Decimal(repr(float(x)))


def _cent_up(d):
    if d <= 0:
        return Decimal(0)
    return (d / _CENT).to_integral_value(rounding=ROUND_CEILING) * _CENT


def _reg_fees_raw(qty, price, side, costs):
    """Unrounded (sec, taf, cat) Decimals for ONE order under the alpaca_equity profile."""
    q = abs(_dq(qty))
    cat = q * _dq(costs["cat_per_share"])
    sec = taf = Decimal(0)
    if side < 0:
        sec = q * _dq(price) * _dq(costs["sec_rate"])
        taf = min(q * _dq(costs["taf_per_share"]), _dq(costs["taf_max"]))
    return sec, taf, cat


def reg_fees(qty, price, side, costs):
    """Pass-through regulatory fees for ONE order (side +1 buy, -1 sell) under
    a profile that defines them; all zero otherwise (DEFAULT_COSTS has none).
    Fees use the exact quantity; each fee type is rounded UP to $0.01 for this
    order, then the cost_mult stress applies."""
    out = {"sec": 0.0, "taf": 0.0, "cat": 0.0, "total": 0.0}
    if costs.get("profile") != "alpaca_equity" or not qty or price is None:
        return out
    m = _dq(costs.get("mult", 1.0))
    sec, taf, cat = _reg_fees_raw(qty, price, side, costs)
    for k, v in (("sec", sec), ("taf", taf), ("cat", cat)):
        out[k] = float(_cent_up(v) * m)
    out["total"] = round(out["sec"] + out["taf"] + out["cat"], 4)
    return out


def day_fees(qty, price, costs):
    """One same-day round trip (a buy and a sell of qty) as Alpaca bills it: each fee
    type summed over both orders, rounded UP to $0.01 once for the day, then the
    cost_mult stress. All zero outside the alpaca_equity profile."""
    out = {"sec": 0.0, "taf": 0.0, "cat": 0.0, "total": 0.0}
    if costs.get("profile") != "alpaca_equity" or not qty or price is None:
        return out
    m = _dq(costs.get("mult", 1.0))
    b, s = _reg_fees_raw(qty, price, 1, costs), _reg_fees_raw(qty, price, -1, costs)
    for i, k in enumerate(("sec", "taf", "cat")):
        out[k] = float(_cent_up(b[i] + s[i]) * m)
    out["total"] = round(out["sec"] + out["taf"] + out["cat"], 4)
    return out


def _alpaca_est(qty, price, costs, sides, note):
    q = abs(float(qty))
    spread = abs(side_price(price, 1, costs) - price) * q
    buy = reg_fees(qty, price, 1, costs)
    sell = reg_fees(qty, price, -1, costs)
    # Round trip: one same-day buy and sell, billed per fee type per day (desk sessions end
    # flat). One side: the dearer single order (a sell for a long), rounded per order.
    day = day_fees(qty, price, costs)
    fees = day["total"] if sides >= 2 else max(buy["total"], sell["total"])
    usd = spread * sides + fees
    basis = ("ESTIMATE, Alpaca equity profile: modeled half spread %.1f bps + slippage %.1f bps per side; "
             "commission $0 (Alpaca fee schedule: no commissions on retail equity orders); regulatory "
             "pass-through fees: SEC $0.0000206 x sell value, CAT $0.000003/share each side, TAF $0 "
             "(Alpaca's schedule lists retail TAF $0); each fee type aggregated per day and rounded UP to "
             "$0.01 (Alpaca's daily rounding; a round trip is one session-flat day); fees this estimate: "
             "%s $%.2f; x%.1f stress; sources: %s"
             % (costs["half_spread_bps"], costs["slippage_bps"],
                "same-day round trip" if sides >= 2 else "one order", fees,
                costs.get("mult", 1.0), " and ".join(ALPACA_FEE_SOURCES[:2])))
    return {"usd": round(usd, 4), "per_side_usd": round(usd / sides, 4) if sides else 0.0,
            "basis": (note + "; " if note else "") + basis, "simulated": True,
            "fees": {"buy": buy, "sell": sell, "day": day, "rounding": costs.get("fee_round"),
                     "estimate": True}}


def est_cost(qty, price, costs, sides=2, note=""):
    """Estimated execution cost in dollars for `qty` units at `price`,
    relative to filling at the raw price, for `sides` sides."""
    if not qty or price is None:
        return {"usd": 0.0, "per_side_usd": 0.0, "basis": note or "no order",
                "simulated": True}
    if costs.get("profile") == "alpaca_equity":
        return _alpaca_est(qty, price, costs, sides, note)
    if isinstance(qty, Decimal):
        qty = float(qty)
    per_side = abs(side_price(price, 1, costs) - price) * abs(qty)
    if costs["kind"] == "per_unit_bid":
        # Buy pays spread+slip, sell pays slip: average the two sides.
        per_side = (abs(side_price(price, 1, costs) - price) + abs(side_price(price, -1, costs) - price)) / 2.0 * abs(qty)
    per_side += commission(qty, costs)
    if costs["kind"] == "per_unit_bid":
        basis = ("spread %.2f + slip %.2f per unit per side, x%.1f stress"
                 % (costs["spread"], costs["slip"], costs.get("mult", 1.0)))
    else:
        basis = ("half spread %.1f bps + slippage %.1f bps per side, commission $%.3f/share "
                 "(min $%.2f), x%.1f stress; mirrored from tvbot/bot/engine.py defaults"
                 % (costs["half_spread_bps"], costs["slippage_bps"], costs["commission_per_share"],
                    costs["commission_min"], costs.get("mult", 1.0)))
    return {"usd": round(per_side * sides, 4), "per_side_usd": round(per_side, 4),
            "basis": (note + "; " if note else "") + basis, "simulated": True}


def line(price, text):
    return {"price": None if price is None else round(float(price), 6), "text": text}


def _fixed_qty(cfg, allow_fraction=False):
    fq = cfg.get("fixed_qty")
    if allow_fraction and cfg.get("fractional") is True and not isinstance(fq, (bool, int)) and fq is not None:
        try:
            q = Q.parse(fq)
        except Q.QtyError:
            return None
        return q
    if isinstance(fq, bool) or not isinstance(fq, int) or fq <= 0:
        return None
    return fq


def _frac_floor(cap, price):
    """Largest quantity at Q.MAX_DP decimals with qty * price <= cap (never rounded up)."""
    q = (_dq(cap) / _dq(price)).quantize(Decimal(1).scaleb(-Q.MAX_DP), rounding=ROUND_DOWN)
    while q > 0 and q * _dq(price) > _dq(cap):
        q -= Decimal(1).scaleb(-Q.MAX_DP)
    if q <= 0:
        return 0
    try:
        return Q.parse(q)
    except Q.QtyError:
        # More than MAX_DIGITS significant digits: drop decimals, still rounding down.
        for dp in range(Q.MAX_DP - 1, -1, -1):
            r = q.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_DOWN)
            try:
                return Q.parse(r) if r > 0 else 0
            except Q.QtyError:
                continue
        return 0


def base_qty(price, cfg, allow_fraction=False):
    """Whole units for one base leg: floor(TEST order_notional / price).

    HYPOTHETICAL fixed-quantity demo preset (TEST VALUE): a positive integer
    cfg["fixed_qty"] is used as is, but only while fixed_qty * price stays
    within the TEST per-trade notional cap. Otherwise it is 0, and the
    ZERO_SIZE refusal shows. It never exceeds the cap and is never resized.

    Fractional (opt-in): only when the caller passes allow_fraction=True (the
    EMA path) AND cfg["fractional"] is True, an exact fractional fixed_qty is
    accepted via orders/qty.parse, and the notional path returns the exact
    floor(cap / price) at 9 decimals as an int-or-Decimal, never rounded up.
    Every other caller and config keeps the int-only behavior.
    """
    c = cfg or {}
    size = c.get("test_size") or load_test_size()
    if not price or price <= 0:
        return 0
    cap = float(size["order_notional"])
    lims = c.get("limits")
    if isinstance(lims, dict) and lims.get("per_trade_notional") is not None:
        cap = min(cap, float(lims["per_trade_notional"]))
    frac = bool(allow_fraction) and c.get("fractional") is True
    fq = _fixed_qty(c, allow_fraction=frac)
    if fq is not None:
        if isinstance(fq, Decimal):
            return fq if fq * _dq(price) <= _dq(cap) else 0
        # Lexical Decimal: 3 x $501.04 is exactly $1503.12, not 1503.1200000000001 > cap.
        # A true excess (3 x $501.05 against $1503.12) is still refused.
        return int(fq) if Decimal(fq) * Decimal(repr(float(price))) <= Decimal(repr(cap)) else 0
    if frac:
        return _frac_floor(cap, price)
    return int(math.floor(cap / float(price)))


def qty_json(qty):
    """Decision qty: int for whole units (unchanged), an exact JSON float for a fraction."""
    if isinstance(qty, float) and not qty.is_integer():
        qty = Q.parse(qty)
    if Q.is_fractional(qty):
        return Q.to_json(qty)
    return int(qty)


def qty_str(qty):
    """'%d'-style text for whole units, exact text for a fraction."""
    if isinstance(qty, float) and not qty.is_integer():
        qty = Q.parse(abs(qty))
    if Q.is_fractional(qty):
        return Q.text(qty)
    return "%d" % qty


def decision_id(strategy, rule_id, bar, action, qty):
    blob = json.dumps([strategy, rule_id, bar.get("symbol"), bar.get("ts_close"),
                       bar.get("seq"), action,
                       qty_str(qty) if not float(qty).is_integer() else int(qty)], separators=(",", ":"))
    return "dec-%s-%s" % (strategy, hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16])


def position_qty(position):
    """Signed quantity from whatever the runner passes: None, a number, or a
    dict with qty / position_qty / net_qty."""
    if position is None:
        return None
    if isinstance(position, (int, float)) and not isinstance(position, bool):
        return position
    if isinstance(position, dict):
        for k in ("qty", "position_qty", "net_qty"):
            if k in position and position[k] is not None:
                return position[k]
    return None


def make_decision(strategy, rule_id, bar, action, qty, reason_code, reason_text,
                  case_for, case_against, est, pass_condition, trigger,
                  intended_entry, intended_exit, invalidation, extra=None,
                  refusal_checks=None):
    if action not in ACTIONS:
        raise ValueError("bad action %r" % (action,))
    d = {
        "decision_id": decision_id(strategy, rule_id, bar, action, qty),
        "ts_knowable": ts_knowable(bar),
        "symbol": bar.get("symbol", "UNKNOWN"),
        "strategy": strategy,
        "action": action,
        "qty": qty_json(qty),
        "reason_code": reason_code,
        "reason_text": reason_text,
        "case_for": case_for,
        "case_against": case_against,
        "est_cost": est,
        "pass_condition": pass_condition,
        "trigger": trigger,
        "intended_entry": intended_entry,
        "intended_exit": intended_exit,
        "invalidation": invalidation,
        "refusal_checks": list(refusal_checks or []),
        "simulated": True,
        "rule_id": rule_id,
        "bar_seq": bar.get("seq"),
        "bar_ts_close": bar.get("ts_close"),
    }
    if isinstance(d["qty"], float):
        d["qty_text"] = qty_str(qty)
    if extra:
        for k, v in extra.items():
            if k not in d:
                d[k] = v
    return d


def no_data_decision(strategy, rule_id, cfg):
    """Decision when no bar has closed yet."""
    stub = {"ts_close": (cfg or {}).get("now") or "1970-01-01T00:00:00Z",
            "symbol": (cfg or {}).get("symbol", "UNKNOWN"), "seq": None}
    return make_decision(
        strategy, rule_id, stub, "pass", 0, "NO_BARS",
        "No bar has closed yet, so there is nothing to decide on.",
        "None: there is no information.",
        "Trading without a closed bar would use unknowable prices.",
        est_cost(0, None, cost_cfg(cfg)),
        "Passes until the first bar closes.",
        line(None, "none"), line(None, "none"), line(None, "none"), line(None, "none"))


# ------------------------------------------------------------ session clock
def session_key(bar, cfg):
    tz = (cfg or {}).get("session_tz", "UTC")
    t = parse_ts(bar["ts_close"])
    if tz != "UTC" and ZoneInfo is not None:
        t = t.astimezone(ZoneInfo(tz))
    return t.date().isoformat()


def session_last_close(bar, cfg):
    """Scheduled close of the session's final bar, as an aware datetime.
    cfg: session_tz (default UTC) and session_close (HH:MM local, default
    21:30, the SYNTH-FUND-60M fixture schedule of 7 hourly bars)."""
    tz = (cfg or {}).get("session_tz", "UTC")
    hhmm = (cfg or {}).get("session_close", "21:30")
    hh, mm = [int(x) for x in hhmm.split(":")]
    t = parse_ts(bar["ts_close"])
    if tz != "UTC" and ZoneInfo is not None:
        z = ZoneInfo(tz)
        lt = t.astimezone(z)
        return lt.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return t.replace(hour=hh, minute=mm, second=0, microsecond=0)


def session_phase(bar, cfg):
    """'open' while entries are allowed; 'flatten' at the close of the bar
    whose successor is the session's final bar (exits fill at that final
    bar's open, so the session ends flat); 'closed' at or after the final
    bar's close (any position left is a residual)."""
    last = session_last_close(bar, cfg)
    t = parse_ts(bar["ts_close"])
    tf = timeframe(bar)
    if t >= last:
        return "closed"
    if t + tf >= last:
        return "flatten"
    return "open"


def same_session(a, b, cfg):
    return session_key(a, cfg) == session_key(b, cfg)


def contiguous(prev, bar):
    """True when `bar` opens exactly where `prev` closed (no missing bar)."""
    return parse_ts(bar["ts_open"]) == parse_ts(prev["ts_close"])


def cfg_hash(cfg):
    keep = {k: v for k, v in (cfg or {}).items() if k not in ("now", "test_size")}
    try:
        blob = json.dumps(keep, sort_keys=True, default=str)
    except TypeError:
        blob = repr(sorted(keep.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


__all__ = [n for n in dir() if not n.startswith("_")] + ["timedelta"]
