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
  qty             whole units (shares, ounces or contracts), 0 for pass/hold
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
from decimal import Decimal
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - 3.9 ships zoneinfo
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
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


def load_test_size(path=None):
    """Matthew's TEST VALUE for the per-order notional. Read only."""
    p = path or SIZE_PATH
    with open(p, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    val = raw.get("order_notional")
    if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
        raise ValueError("order_notional in %s must be a positive number" % p)
    return {"order_notional": float(val), "label": "TEST VALUES", "source": p}


def parse_ts(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    t = str(s).strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
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
    c = dict(DEFAULT_COSTS)
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


def est_cost(qty, price, costs, sides=2, note=""):
    """Estimated execution cost in dollars for `qty` units at `price`,
    relative to filling at the raw price, for `sides` sides."""
    if not qty or price is None:
        return {"usd": 0.0, "per_side_usd": 0.0, "basis": note or "no order",
                "simulated": True}
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


def _fixed_qty(cfg):
    fq = cfg.get("fixed_qty")
    if isinstance(fq, bool) or not isinstance(fq, int) or fq <= 0:
        return None
    return fq


def base_qty(price, cfg):
    """Whole units for one base leg: floor(TEST order_notional / price).

    HYPOTHETICAL fixed-quantity demo preset (TEST VALUE): a positive integer
    cfg["fixed_qty"] is used as is, but only while fixed_qty * price stays
    within the TEST per-trade notional cap. Otherwise it is 0, and the
    ZERO_SIZE refusal shows. It never exceeds the cap and is never resized.
    """
    c = cfg or {}
    size = c.get("test_size") or load_test_size()
    if not price or price <= 0:
        return 0
    cap = float(size["order_notional"])
    lims = c.get("limits")
    if isinstance(lims, dict) and lims.get("per_trade_notional") is not None:
        cap = min(cap, float(lims["per_trade_notional"]))
    fq = _fixed_qty(c)
    if fq is not None:
        # Lexical Decimal: 3 x $501.04 is exactly $1503.12, not 1503.1200000000001 > cap.
        # A true excess (3 x $501.05 against $1503.12) is still refused.
        return int(fq) if Decimal(fq) * Decimal(repr(float(price))) <= Decimal(repr(cap)) else 0
    return int(math.floor(cap / float(price)))


def decision_id(strategy, rule_id, bar, action, qty):
    blob = json.dumps([strategy, rule_id, bar.get("symbol"), bar.get("ts_close"),
                       bar.get("seq"), action, int(qty)], separators=(",", ":"))
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
        "qty": int(qty),
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
