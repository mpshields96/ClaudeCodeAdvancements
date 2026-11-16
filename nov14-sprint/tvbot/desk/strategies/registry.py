"""STRATEGIES registry for the desk session runner (desk/CONTRACT.md).

    from strategies.registry import STRATEGIES
    decision = STRATEGIES["gold_basket"](bars_so_far, position, cfg)

* Uses only bars with ts_close <= cfg["now"] (all given bars when no "now").
* Deterministic: the same bars and cfg always give the same Decision.
* Escalation is research-only: the registry forces research_escalation off,
  so every desk leg is one TEST-size base leg.
* `position` is the desk's real position (None, a signed number, or a dict
  with qty / position_qty / net_qty). An exit is capped at the real
  position; with no real position an exit becomes a pass.
* Pure: the Decision depends only on (bars_so_far, position, cfg). The
  cache, per (strategy, full cfg without "now"), continues incrementally
  only when every earlier bar is identical in EVERY field (volume, high,
  low, delivered_ts, ...) to a snapshot taken at the earlier call. A
  corrected, removed or in-place-edited bar forces a cold replay. The
  returned Decision is a deep copy, so callers cannot alter the cache.
"""
import copy
import json

from . import base as B
from . import engine as E

DESK_KINDS = ("ema", "gold_basket", "fixed_risk_single", "bounded_fixed", "cash")
_CACHE = {}
_CACHE_MAX = 64


def clear_cache():
    _CACHE.clear()


_SCALAR = (str, int, float, bool, type(None))


def _snap(bar):
    """Our own copy of every field of a bar, taken before the engine sees it."""
    s = dict(bar)
    for k, v in list(s.items()):
        if not isinstance(v, _SCALAR):
            s[k] = copy.deepcopy(v)
    return s


def _cfg_key(cfg):
    return json.dumps({k: v for k, v in cfg.items() if k != "now"}, sort_keys=True, default=repr)


def _replay_last(kind, bars, cfg):
    ck = (kind, _cfg_key(cfg))
    ent = _CACHE.get(ck)
    n = len(ent["snaps"]) if ent is not None else -1
    # Every field of every earlier bar must equal its snapshot (list/dict ==).
    if ent is not None and n <= len(bars) and bars[:n] == ent["snaps"]:
        r, snaps = ent["rep"], ent["snaps"]
    else:
        r, snaps, n = E.Replayer(kind, cfg), [], 0
    for b in bars[n:]:
        snaps.append(_snap(b))
        r.step(b)
    if ck not in _CACHE and len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[ck] = {"snaps": snaps, "rep": r}
    return copy.deepcopy(r.last)


def _reconcile(d, position):
    real = B.position_qty(position)
    if real is None:
        return d
    d["real_position_qty"] = real
    if d["action"] == "exit":
        if real == 0:
            d["reason_text"] = "Strategy wanted to exit (%s) but the desk's real position is 0, so it passes. %s" % (
                d["reason_code"], d["reason_text"])
            d["reason_code"] = "NOTHING_TO_EXIT"
            d["action"], d["qty"] = "pass", 0
            d["refusal_checks"] = list(d.get("refusal_checks") or []) + [
                {"id": "NOTHING_TO_EXIT", "passed": False, "detail": "real position is 0"}]
        elif d["qty"] > abs(real):
            d["qty"] = abs(real)  # cap a fractional reduction without rounding down
    return d


def _make(kind):
    def decide(bars_so_far, position=None, cfg=None):
        c = dict(cfg or {})
        c["research_escalation"] = False
        c.pop("keep_records", None)
        bars = B.knowable_bars(bars_so_far, c.get("now"))
        if not bars:
            d = B.no_data_decision(kind, E.rule_id(kind, c), c)
            d["refusal_checks"] = [{"id": "NO_BARS", "passed": False, "detail": "no closed bar yet"}]
            return d
        # "now" only selects the bars; the engine never sees it.
        ec = {k: v for k, v in c.items() if k != "now"}
        return _reconcile(_replay_last(kind, bars, ec), position)
    decide.__name__ = "decide_" + kind
    decide.__doc__ = "decide(bars_so_far, position, cfg) -> Decision for strategy %r" % kind
    return decide


STRATEGIES = {k: _make(k) for k in DESK_KINDS}

DESCRIPTIONS = {
    "ema": "Existing EMAX-1.0.0 crossover (8/21 EMA, 1.5% stop), mirrored read-only, flat at session end.",
    "gold_basket": "Reddit gold idea: change-of-character (6-bar swing) breaks add legs to one netted basket; "
                   "+$3 / -$6 basket exits; escalation 1/2/4 only in research.",
    "fixed_risk_single": "One base leg on a change-of-character break; same +$3 / -$6 exits.",
    "bounded_fixed": "Up to three equal base legs, one netted basket; same +$3 / -$6 exits.",
    "cash": "Never trades. $0 is a valid result.",
}
