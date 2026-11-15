"""Rule EMAX and the registry that counts every variant ever tried.

The rule, in words: on closed bars only, a fast average (8 bars) crossing above
a slow average (21 bars) is a long setup. A hypothetical position starts at the
next bar's open. It ends at the next bar's open after a bar closes at or below
the stop (1.5 percent under the entry open), or after the fast average crosses
back below the slow one. Long only, one position.

The averages are exponential and seeded with the first close, the same
arithmetic as the Pine script in ../pine/emax_alerts.pine. The two never
exchange data: the Pine script draws on a chart for a person to read, and this
module computes on permitted (by default synthetic) bars.

Standard library only, Python 3.9.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

RULE_NAME = "EMAX"
RULE_VERSION = "1.0.0"
DEFAULT_PARAMS = {"fast_len": 8, "slow_len": 21, "stop_pct": 1.5, "warmup_bars": 63}


def validate_params(params=None):
    p = dict(DEFAULT_PARAMS)
    for k, v in (params or {}).items():
        if k not in DEFAULT_PARAMS:
            raise ValueError("unknown rule parameter %r" % (k,))
        p[k] = v
    for k in ("fast_len", "slow_len", "warmup_bars"):
        if isinstance(p[k], bool) or not isinstance(p[k], int) or p[k] < 1:
            raise ValueError("%s must be a whole number of bars, got %r" % (k, p[k]))
    if p["fast_len"] >= p["slow_len"]:
        raise ValueError("fast_len must be shorter than slow_len")
    if p["warmup_bars"] < 2:
        raise ValueError("warmup_bars must be at least 2")
    sp = p["stop_pct"]
    if isinstance(sp, bool) or not isinstance(sp, (int, float)) or not (0.1 <= sp <= 50.0):
        raise ValueError("stop_pct must be between 0.1 and 50, got %r" % (sp,))
    p["stop_pct"] = float(sp)
    return p


def rule_id(params=None):
    """Name, version and a short hash of the parameters. Change any parameter
    and the id changes, so a ledger can never mix two variants unnoticed."""
    p = validate_params(params)
    blob = json.dumps(p, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "%s-%s-%s" % (RULE_NAME, RULE_VERSION, hashlib.sha256(blob).hexdigest()[:8])


def new_indicator_state():
    return {"fast": None, "slow": None, "prev_fast": None, "prev_slow": None, "n": 0}


def step_indicators(ind, close, params):
    """Advance both averages by one closed bar and return a new state."""
    out = dict(ind)
    out["prev_fast"], out["prev_slow"] = ind["fast"], ind["slow"]
    for name, length in (("fast", params["fast_len"]), ("slow", params["slow_len"])):
        prev = ind[name]
        if prev is None:
            out[name] = float(close)
        else:
            alpha = 2.0 / (length + 1)
            out[name] = alpha * float(close) + (1.0 - alpha) * prev
    out["n"] = ind["n"] + 1
    return out


def signals(ind, params):
    have_prev = ind["prev_fast"] is not None and ind["prev_slow"] is not None
    cross_up = have_prev and ind["fast"] > ind["slow"] and ind["prev_fast"] <= ind["prev_slow"]
    cross_down = have_prev and ind["fast"] < ind["slow"] and ind["prev_fast"] >= ind["prev_slow"]
    return {
        "ready": ind["n"] >= params["warmup_bars"],
        "cross_up": bool(cross_up),
        "cross_down": bool(cross_down),
    }


# ---------------------------------------------------------------- registry

class HoldoutRefused(Exception):
    pass


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_registry():
    return {
        "schema": 1,
        "about": "Every rule variant ever run is listed here, including ones that "
                 "did badly. The count is the number of tries.",
        "variants": [],
        "frozen_rule_id": None,
        "holdout": {"used": False},
    }


def load_registry(path):
    if not path or not os.path.exists(path):
        return _empty_registry()
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_registry(path, reg):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def register_variant(path, params, note=""):
    """Record that this parameter set was run. Returns (rule_id, is_new, count)."""
    reg = load_registry(path)
    rid = rule_id(params)
    for v in reg["variants"]:
        if v["rule_id"] == rid:
            return rid, False, len(reg["variants"])
    reg["variants"].append({
        "rule_id": rid,
        "params": validate_params(params),
        "first_run_utc": _utc_now(),
        "note": note,
    })
    save_registry(path, reg)
    return rid, True, len(reg["variants"])


def freeze_rule(path, rid):
    reg = load_registry(path)
    if rid not in [v["rule_id"] for v in reg["variants"]]:
        raise ValueError("cannot freeze %s: it was never run" % rid)
    if reg.get("frozen_rule_id") not in (None, rid):
        raise ValueError("rule %s is already frozen; a new rule needs a new registry "
                         "period" % reg["frozen_rule_id"])
    reg["frozen_rule_id"] = rid
    reg.setdefault("frozen_utc", _utc_now())
    save_registry(path, reg)
    return reg


def claim_holdout(path, rid, feed_sha256):
    """Spend the untouched period. Works once. The claim is written before the
    run, so a crashed run still counts as the one use."""
    reg = load_registry(path)
    if reg.get("frozen_rule_id") != rid:
        raise HoldoutRefused("only the frozen rule (%s) may use the untouched period; "
                             "this run is %s" % (reg.get("frozen_rule_id"), rid))
    if reg.get("holdout", {}).get("used"):
        raise HoldoutRefused("the untouched period was already used on %s by %s; "
                             "it cannot be used again"
                             % (reg["holdout"].get("used_utc"), reg["holdout"].get("rule_id")))
    reg["holdout"] = {"used": True, "used_utc": _utc_now(), "rule_id": rid,
                      "feed_sha256": feed_sha256,
                      "variants_tried_before_use": len(reg["variants"])}
    save_registry(path, reg)
    return reg
