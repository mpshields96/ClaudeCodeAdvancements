"""Sizing and dollar-limits worksheet for the Alpaca paper desk. Matthew decides every value.

Flow: draft -> inspect the calculated effects -> explicit local operator approval.

- A draft (<state_dir>/limits_draft.json, provenance "draft") may be incomplete. It needs no keys and
  no network. Nothing here fills it in: there are no defaults.
- Approval is a local operator action: type CONFIRM_PHRASE, give a reason. It writes
  <state_dir>/limits_approved.json (provenance "operator-approved", approved_utc, reason, the
  old-to-new diff and a content hash).
- Whether a config is genuine is decided by provenance plus that explicit confirmation, never by
  comparing numbers. Matthew may choose the same dollar amounts as a test example.
- The real paper path refuses: no approved snapshot; provenance draft/template/test-example; a hash
  mismatch (edited after approval); a null or non-positive value; a missing fixed_shares; more than 9
  decimal places; a fractional fixed_shares without max_daily_entries.
- fixed_shares may be fractional (an exact decimal, at most 9 places). Only a connected Alpaca desk
  trades it (DAY, simple, long-only orders); the offline desk refuses it. A fractional size also
  needs max_daily_entries, the most new entry attempts per regular trading day.
- Suggestions and TEST EXAMPLE presets are read-only. They never change the draft or approve anything.

Stdlib only (Python 3.9). No network, no credentials.
"""
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

try:
    from orders import qty as Q
except ImportError:   # run as a script from alpaca/
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from orders import qty as Q

FIELDS = ("fixed_shares", "max_loss_per_trade", "daily_loss", "per_trade_notional", "gross_exposure")
CAP_FIELDS = ("per_trade_notional", "max_loss_per_trade", "daily_loss", "gross_exposure")
# Optional fields join the content hash only when set, so approvals made before they existed keep
# their hash. max_daily_entries is required when fixed_shares is fractional.
OPTIONAL_FIELDS = ("max_daily_entries",)
ALL_FIELDS = FIELDS + OPTIONAL_FIELDS
MIN_FRACTIONAL_BUY = Decimal("1.00")   # venue rule (Alpaca fractional: "as little as $1"); new buys only
FIELD_HELP = {
    "fixed_shares": ("Shares per entry: a whole number, or a fraction with at most 9 decimal places "
                     "(fractions trade only on a connected Alpaca desk, as DAY simple long-only orders). "
                     "Required. There is no default and no formula."),
    "max_daily_entries": ("Most new entry attempts per regular trading day, counting rejected, uncertain, "
                          "working and filled attempts. Required for fractional shares, optional for whole "
                          "shares. Exits and protective stops are never limited by it."),
    "max_loss_per_trade": "Dollars you accept losing on one trade if the stop is hit.",
    "daily_loss": "Dollars of realized loss in one day after which new entries stop.",
    "per_trade_notional": "Largest dollar value of a single order (shares x price).",
    "gross_exposure": "Largest dollar value of everything open plus everything working, together.",
}

DRAFT_FILE = "limits_draft.json"
APPROVED_FILE = "limits_approved.json"
CONFIRM_PHRASE = "APPROVE PAPER LIMITS"

PROV_APPROVED = "operator-approved"
PROV_DRAFT = "draft"
PROV_TEMPLATE = "template"
PROV_TEST = "test-example"

DRAFT_LABEL = "DRAFT LIMITS (not approved)"
APPROVED_LABEL = "OPERATOR-APPROVED PAPER LIMITS"
TEST_EXAMPLE_LABEL = "TEST EXAMPLE (not Matthew's limits; copy it only if you choose to)"
SUGGESTION_LABEL = "read-only suggestion; it does not change your draft"
ASSUMED_LABEL = "ASSUMED (not measured)"

# The desk's existing demo numbers (session.TEST_LIMITS and the launcher's --qty 1), shown only as a
# labeled example. Copying one into the draft is the operator's click; it never approves anything.
TEST_EXAMPLES = (
    {"name": "desk demo test values", "label": TEST_EXAMPLE_LABEL, "provenance": PROV_TEST,
     "values": {"fixed_shares": 1, "max_loss_per_trade": 10.0, "daily_loss": 30.0,
                "per_trade_notional": 2000.0, "gross_exposure": 2000.0}},
)


class LimitsError(ValueError):
    """A plain-English reason the limits cannot be used. Never carries credentials."""


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".limits.", dir=d)
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path):
    """(obj, None) or (None, plain reason)."""
    try:
        with open(path) as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "not found"
    except (OSError, ValueError):
        return None, "unreadable or not valid JSON"


def content_hash(values):
    """Hash of the five values, plus each optional field that is set. Identifies the draft the
    operator reviewed. A record without the optional fields hashes exactly as it did before."""
    canon = {k: (values or {}).get(k) for k in FIELDS}
    for k in OPTIONAL_FIELDS:
        if (values or {}).get(k) is not None:
            canon[k] = values[k]
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def record_hash(record):
    """Hash of the whole approval record except its own "hash" field: values, provenance,
    approved_utc, reason, by, diff, previous_hash. Editing any of them breaks verification."""
    body = {k: v for k, v in (record or {}).items() if k != "hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


CENT = Decimal("0.01")
UNSET = object()   # approve() refuses unless the caller names what was reviewed


def _dec(x):
    """Decimal from the operator's input, via its decimal text (never binary float arithmetic)."""
    if isinstance(x, bool) or x is None:
        raise InvalidOperation
    if isinstance(x, float):
        x = repr(x)
    d = Decimal(x.strip()) if isinstance(x, str) else Decimal(x)
    if not d.is_finite():
        raise InvalidOperation
    return d


def _money(d, rounding=ROUND_CEILING):
    """A Decimal amount shown at cent precision; losses and exposure round up (the safe side)."""
    return float(d.quantize(CENT, rounding=rounding))


def _check(field, value, allow_null):
    """(clean value, problem or None)."""
    if value is None:
        return None, (None if allow_null else "%s is empty; only you can set it" % field)
    if field == "fixed_shares":
        try:
            q = Q.parse(value)
        except Q.QtyError as exc:
            msg = str(exc)
            if "greater than zero" in msg:
                return None, "fixed_shares must be more than zero"
            if "finite" in msg:
                return None, "fixed_shares must be a finite number"
            if "decimal places" in msg or "significant digits" in msg:
                return None, "fixed_shares " + msg.split("quantity ", 1)[-1]
            return None, "fixed_shares must be a number"
        return Q.to_json(q), None
    if field == "max_daily_entries":
        try:
            n = Q.parse(value)
        except Q.QtyError:
            return None, "max_daily_entries must be a whole number of at least 1"
        if not isinstance(n, int):
            return None, "max_daily_entries must be a whole number of at least 1"
        return n, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError:
                return None, "%s must be a number" % field
        else:
            return None, "%s must be a number" % field
    if not math.isfinite(float(value)):
        return None, "%s must be a finite number" % field
    value = float(value)
    if value <= 0:
        return None, "%s must be more than zero" % field
    return value, None


def validate(values, allow_null=False):
    """(clean {field: value}, [problems]). Unknown keys are dropped."""
    if not isinstance(values, dict):
        return {k: None for k in FIELDS}, ["limits must be an object of the five fields"]
    clean, problems = {}, []
    for field in FIELDS:
        if field not in values and not allow_null:
            clean[field] = None
            problems.append("%s is missing; only you can set it" % field)
            continue
        v, p = _check(field, values.get(field), allow_null)
        clean[field] = v
        if p:
            problems.append(p)
    for field in OPTIONAL_FIELDS:   # present in clean only when set: older records keep their shape
        v, p = _check(field, values.get(field), True)
        if p:
            problems.append(p)
        elif v is not None:
            clean[field] = v
    if is_fractional_size(clean) and clean.get("max_daily_entries") is None and not allow_null:
        problems.append("max_daily_entries is required for fractional shares; only you can set it")
    return clean, problems

def is_fractional_size(values):
    """True when fixed_shares is set and not a whole number."""
    v = (values or {}).get("fixed_shares")
    if v is None or isinstance(v, bool):
        return False
    try:
        return Q.is_fractional(Q.parse(v))
    except Q.QtyError:
        return False


def is_complete(values):
    return not validate(values, allow_null=False)[1]


def diff(old_values, new_values):
    old_values = old_values or {}
    return [{"field": k, "old": old_values.get(k), "new": (new_values or {}).get(k)}
            for k in ALL_FIELDS if old_values.get(k) != (new_values or {}).get(k)]


def draft_path(state_dir):
    return os.path.join(os.path.abspath(state_dir), DRAFT_FILE)


def approved_path(state_dir):
    return os.path.join(os.path.abspath(state_dir), APPROVED_FILE)


def read_draft(state_dir):
    obj, _ = _read_json(draft_path(state_dir))
    return obj if isinstance(obj, dict) else None


def read_approved(state_dir):
    obj, _ = _read_json(approved_path(state_dir))
    return obj if isinstance(obj, dict) else None


def save_draft(state_dir, values, copied_from=None):
    """Save the operator's draft. Nulls are allowed (incomplete draft); bad values are refused."""
    clean, problems = validate(values, allow_null=True)
    if problems:
        raise LimitsError("; ".join(problems))
    row = {"provenance": PROV_DRAFT, "label": DRAFT_LABEL, "values": clean, "saved_utc": _now(),
           "complete": is_complete(clean)}
    if copied_from:
        row["copied_from"] = str(copied_from)[:80]
    _write_json(draft_path(state_dir), row)
    return row


def approve(state_dir, confirm, reason, reviewed_draft_hash=UNSET, prior_approved_hash=UNSET,
            by="operator (local)"):
    """Turn the current draft into the approved snapshot. Only the operator calls this.

    reviewed_draft_hash: worksheet()["draft_hash"] of the draft the operator looked at.
    prior_approved_hash: worksheet()["approved_hash"] at that moment (None when nothing was approved).
    Either one differing from what is on disk now (a stale review, a concurrent edit, a second
    tab) refuses the approval."""
    if (confirm or "").strip() != CONFIRM_PHRASE:
        raise LimitsError('type exactly "%s" to approve' % CONFIRM_PHRASE)
    reason = (reason or "").strip()
    if not reason:
        raise LimitsError("give a short reason for this approval")
    draft = read_draft(state_dir)
    if not draft:
        raise LimitsError("no draft saved yet; fill in and save a draft first")
    clean, problems = validate(draft.get("values"), allow_null=False)
    if problems:
        raise LimitsError("draft is not complete: " + "; ".join(problems))
    if reviewed_draft_hash is UNSET or not reviewed_draft_hash:
        raise LimitsError("approval must name the draft you reviewed; reload the Setup panel and try again")
    if reviewed_draft_hash != content_hash(draft.get("values")):
        raise LimitsError("the draft changed after you reviewed it (another tab or edit); "
                          "reload the Setup panel, check the values again, then approve")
    old = read_approved(state_dir) or {}
    if prior_approved_hash is UNSET:
        raise LimitsError("approval must name the approved limits you saw (none, or their hash); "
                          "reload the Setup panel and try again")
    if (prior_approved_hash or None) != (old.get("hash") or None):
        raise LimitsError("the approved limits changed after you reviewed them (another tab or edit); "
                          "reload the Setup panel and try again")
    snap = {"provenance": PROV_APPROVED, "label": APPROVED_LABEL, "values": clean,
            "approved_utc": _now(), "reason": reason[:500], "by": str(by)[:80],
            "diff": diff(old.get("values"), clean), "values_hash": content_hash(clean),
            "previous_hash": old.get("hash")}
    snap["hash"] = record_hash(snap)
    _write_json(approved_path(state_dir), snap)
    return snap


def _loaded(obj, label, hash_=None):
    clean, problems = validate(obj.get("values"), allow_null=False)
    if problems:
        raise LimitsError("; ".join(problems))
    return {"values": clean, "provenance": obj.get("provenance"), "approved_utc": obj.get("approved_utc"),
            "hash": hash_ or content_hash(clean), "values_hash": content_hash(clean), "label": label}


def check_snapshot(obj, allow_draft=False):
    """Validate a parsed limits document. Returns the load_limits() dict or raises LimitsError."""
    if not isinstance(obj, dict):
        raise LimitsError("limits file must be a JSON object")
    prov = obj.get("provenance")
    if prov == PROV_APPROVED:
        if not obj.get("hash") or obj.get("hash") != record_hash(obj) \
                or obj.get("values_hash") != content_hash(obj.get("values")):
            raise LimitsError("approved limits were edited after approval (record hash mismatch); "
                              "treat them as unapproved and approve them again")
        if not obj.get("approved_utc") or not str(obj.get("reason") or "").strip():
            raise LimitsError("approved limits are missing their approval time or reason; approve them again")
        return _loaded(obj, APPROVED_LABEL, hash_=obj.get("hash"))
    if prov == PROV_DRAFT and allow_draft:
        return _loaded(obj, DRAFT_LABEL)
    if prov == PROV_DRAFT:
        raise LimitsError("these are draft limits; approve them first (the real paper path needs approval)")
    if prov == PROV_TEMPLATE:
        raise LimitsError("this is the blank template; copy it, fill it in yourself, then approve it")
    if prov == PROV_TEST:
        raise LimitsError("this is a TEST EXAMPLE, not your limits; it cannot be used")
    raise LimitsError("limits provenance is %r; only an operator-approved snapshot is accepted"
                      % (str(prov)[:40] if prov is not None else None))


def load_limits(path=None, state_dir=None, allow_draft=False):
    """{values, provenance, approved_utc, hash, label} or LimitsError. Never invents a default.

    path: an explicit approved snapshot (the launcher's --limits). state_dir: use that desk's
    limits_approved.json, falling back to its draft only when allow_draft (mock rehearsal only)."""
    if path is None and state_dir is None:
        raise LimitsError("no limits file given")
    if path is not None:
        obj, why = _read_json(path)
        if obj is None:
            raise LimitsError("limits file %s: %s" % (os.path.basename(str(path)), why))
        return check_snapshot(obj, allow_draft=allow_draft)
    obj, why = _read_json(approved_path(state_dir))
    if obj is not None:
        return check_snapshot(obj, allow_draft=allow_draft)
    if why != "not found":
        raise LimitsError("%s: %s" % (APPROVED_FILE, why))
    if not allow_draft:
        raise LimitsError("no approved limits yet; draft and approve them in the Setup panel first")
    draft = read_draft(state_dir)
    if not draft:
        raise LimitsError("no limits yet (no approved snapshot and no draft)")
    return check_snapshot(draft, allow_draft=True)


def as_session_limits(loaded):
    """The four caps in the shape session.TEST_LIMITS uses, plus fixed_shares and the provenance label."""
    v = loaded["values"]
    out = {k: v[k] for k in CAP_FIELDS}
    out["label"] = loaded.get("label") or ""
    out["fixed_shares"] = v["fixed_shares"]
    if v.get("max_daily_entries") is not None:   # absent for older records: session config unchanged
        out["max_daily_entries"] = v["max_daily_entries"]
    out["provenance"] = loaded.get("provenance")
    out["hash"] = loaded.get("hash")
    return out


# ------------------------------------------------------------------ cash-proportional size
# Each new buy is sized from this account's own verified, uncommitted cash, re-read before the buy:
# never an old balance and never margin. The shared profile (alpaca/trading_profile.py) sets the
# shares per available dollar and paper's own caps. A live desk never goes above its approved size
# or caps. A size the venue cannot take (zero, or a fraction under $1) is an explicit pass.
CASH_UNVERIFIED = "CASH_UNVERIFIED"
CASH_SCALED_TO_ZERO = "CASH_SCALED_TO_ZERO"
CASH_SCALED_BELOW_MIN = "CASH_SCALED_BELOW_MIN"
_QTY_STEP = Decimal(1).scaleb(-Q.MAX_DP)


def _balance(v):
    if v is None or isinstance(v, bool):
        raise ValueError("missing")
    d = Decimal(str(v).strip())
    if not d.is_finite() or d < 0:
        raise ValueError("not a usable amount")
    return d


def available_cash(balances, working_buy_usd):
    """min(cash, equity, non-margin buying power, and buying power when the venue sends it) minus
    every working buy commitment. A min can only lower it, so margin never adds to it. None when a
    required balance is missing, unreadable, negative or not finite."""
    try:
        keys = ("cash", "equity", "non_marginable_buying_power")
        if "buying_power" in balances:
            keys += ("buying_power",)
        vals = [_balance(balances[k]) for k in keys]
        working = _balance(working_buy_usd)
    except (KeyError, ValueError, InvalidOperation, TypeError, AttributeError):
        return None
    return max(Decimal(0), min(vals) - working)


def _profile():
    try:
        from alpaca import trading_profile as P
    except ImportError:   # run as a script from alpaca/
        import trading_profile as P
    return P


def profile_size(balances, working_buy_usd, price, stop=None, approved_qty=None, fractional=True,
                 gross_used_usd=0):
    """(qty or None, info, caps) for one new buy under the shared trading profile.

    Paper (approved_qty None): caps = trading_profile.paper_caps(available), and qty is the smallest
    of SHARES_PER_USD x available, caps notional / price, (caps gross - gross_used) / price,
    caps price risk / (price - stop) and available / price. The caller enforces these caps.
    Live (approved_qty set): qty is the smallest of the approved size, SHARES_PER_USD x available
    and available / price; caps is None, so the approved caps stand unchanged.
    The size is floored to 9 places on a fractional desk, else to a whole share. None means pass and
    info["code"] says why. info never carries a balance or the available amount."""
    P = _profile()
    approved = None if approved_qty is None else Q.parse(approved_qty)
    mode = "paper" if approved is None else "live"
    info = {"profile": P.PROFILE_ID, "profile_version": P.VERSION, "mode": mode,
            "shares_per_usd": str(P.SHARES_PER_USD),
            "approved_qty": None if approved is None else Q.to_json(approved),
            "sized_qty": None, "binding": None, "code": None}
    try:
        px = _dec(price)
        if px <= 0:
            raise InvalidOperation
        st = None if stop is None else _dec(stop)
        gross_used = _dec(gross_used_usd or 0)
    except (InvalidOperation, TypeError, ValueError):
        info["code"] = CASH_UNVERIFIED
        return None, info, None
    avail = available_cash(balances, working_buy_usd)
    if avail is None:
        info["code"] = CASH_UNVERIFIED
        return None, info, None
    bounds = {"profile": avail * P.SHARES_PER_USD, "cash": avail / px}
    caps = None
    if approved is None:
        caps = P.paper_caps(avail)
        bounds["notional"] = _dec(caps["per_trade_notional"]) / px
        bounds["gross"] = max(Decimal(0), _dec(caps["gross_exposure"]) - gross_used) / px
        if st is not None and px > st:
            bounds["stop_risk"] = _dec(caps["max_loss_per_trade"]) / (px - st)
    else:
        bounds["approved"] = Q.dec(approved)
    binding = min(bounds, key=lambda k: bounds[k])
    raw = bounds[binding]
    frac = fractional or (approved is not None and Q.is_fractional(approved))
    if frac:
        q = raw.quantize(_QTY_STEP, rounding=ROUND_FLOOR)
    else:
        q = raw.to_integral_value(rounding=ROUND_FLOOR)
    q = Q.norm(q)
    info["sized_qty"] = Q.to_json(q)
    info["binding"] = binding
    if Q.dec(q) <= 0:
        info["code"] = CASH_SCALED_TO_ZERO
        return None, info, caps
    if frac and Q.dec(q) * px < MIN_FRACTIONAL_BUY:
        info["code"] = CASH_SCALED_BELOW_MIN
        info["notional_usd"] = _money(Q.dec(q) * px, ROUND_FLOOR)
        return None, info, caps
    return q, info, caps


def _pos(x, name):
    try:
        x = _dec(x)
    except (InvalidOperation, TypeError, ValueError):
        raise LimitsError("%s must be a number" % name)
    if x <= 0:
        raise LimitsError("%s must be more than zero" % name)
    return x


def _nonneg(x, name):
    try:
        x = _dec(x if x not in (None, "") else 0)
    except (InvalidOperation, TypeError, ValueError):
        raise LimitsError("%s must be a number" % name)
    if x < 0:
        raise LimitsError("%s cannot be negative" % name)
    return x


def _floor_shares(budget, per_share):
    if per_share <= 0:
        return 0
    return max(0, int((budget / per_share).to_integral_value(rounding=ROUND_FLOOR)))


def effects(values, ref_price, stop_distance, fee_per_share=0.0, slippage_per_share=0.0,
            open_exposure=0.0, realized_loss_today=0.0, working_notional=0.0):
    """Calculated effects of a draft at a chosen reference price and illustrative stop distance.

    Pure arithmetic; it reads no files and changes nothing. Fees and slippage are the operator's
    assumptions and are labeled as such. All arithmetic is decimal from the decimal text of each
    input: each cap check compares the exact (unrounded) amount with an exact ">", share counts
    round down, and displayed losses and exposure round up to the cent."""
    price = _pos(ref_price, "reference price")
    stop = _pos(stop_distance, "stop distance")
    fee = _nonneg(fee_per_share, "fee per share")
    slip = _nonneg(slippage_per_share, "slippage per share")
    open_exp = _nonneg(open_exposure, "open exposure")
    realized = _nonneg(realized_loss_today, "realized loss today")
    working = _nonneg(working_notional, "working orders notional")
    v, _ = validate(values or {}, allow_null=True)
    shares = v.get("fixed_shares")
    per_share_cost = 2 * (fee + slip)   # entry and exit
    out = {"inputs": {"reference_price": float(price), "stop_distance": float(stop)},
           "assumptions": {"fee_per_share": float(fee), "slippage_per_share": float(slip),
                           "label": ASSUMED_LABEL, "note": "costs counted on entry and exit"},
           "shares": shares, "checks": [], "suggestions": [], "simulated": True,
           "arithmetic": "decimal; caps compare the exact amount; shares round down; losses shown rounded up"}
    caps = {}
    for k in CAP_FIELDS:
        caps[k] = _dec(v[k]) if v.get(k) is not None else None
    exact = {}
    if shares is not None:
        q = Q.dec(Q.parse(shares))
        exact["notional"] = q * price
        exact["costs"] = q * per_share_cost
        exact["price_risk"] = q * stop               # what max_loss_per_trade caps (price to the stop only)
        exact["loss"] = exact["price_risk"] + exact["costs"]   # what the daily cap budgets (fees included)
        exact["worst"] = open_exp + working + exact["notional"]
        out.update(notional=_money(exact["notional"]), payoff_per_1usd_move=float(shares),
                   est_loss_at_stop=_money(exact["loss"]), est_costs=_money(exact["costs"]),
                   stop_price_risk=_money(exact["price_risk"]),
                   worst_case_if_all_working_fill=_money(exact["worst"]))
    rem = {}
    if caps["daily_loss"] is not None:
        rem["daily_loss_remaining"] = _money(caps["daily_loss"] - realized, ROUND_FLOOR)
    if caps["gross_exposure"] is not None:
        rem["gross_exposure_remaining"] = _money(caps["gross_exposure"] - open_exp - working, ROUND_FLOOR)
    out["remaining_capacity"] = rem

    def add(cap, ok, reason):
        out["checks"].append({"cap": cap, "ok": ok, "reason": reason})

    if shares is None:
        add("fixed_shares", False, "fixed_shares is not set, so no trade can be sized")
    elif is_fractional_size(v):
        ok = not exact["notional"] < MIN_FRACTIONAL_BUY
        add("min_fractional_buy", ok, "order value $%.2f %s the venue's $%.2f minimum for a new fractional buy%s"
            % (_money(exact["notional"], ROUND_FLOOR), "meets" if ok else "is BELOW", float(MIN_FRACTIONAL_BUY),
               "" if ok else "; the desk skips such an entry and never rounds it up"))
        if v.get("max_daily_entries") is None:
            add("max_daily_entries", False, "max_daily_entries is not set; fractional shares require it")
    for cap in CAP_FIELDS:
        limit = caps[cap]
        if limit is None:
            add(cap, False, "%s is not set; the real paper path refuses until you set it" % cap)
            continue
        if shares is None:
            continue
        lim = float(limit)
        if cap == "per_trade_notional":
            ok = not exact["notional"] > limit
            add(cap, ok, "order value $%.2f %s your per-trade cap $%.2f"
                % (out["notional"], "is within" if ok else "is OVER", lim))
        elif cap == "max_loss_per_trade":
            # Price risk to the stop only; the estimated costs count against the daily cap below,
            # matching the strategy and order-manager gates.
            ok = not exact["price_risk"] > limit
            add(cap, ok, "price risk to the stop $%.2f %s your per-trade loss cap $%.2f; the estimated costs "
                "$%.2f count against the daily cap"
                % (out["stop_price_risk"], "is within" if ok else "is OVER", lim, out["est_costs"]))
        elif cap == "daily_loss":
            after = realized + exact["loss"]
            ok = not after > limit
            add(cap, ok, "today's realized loss $%.2f plus this stop-out $%.2f = $%.2f, %s your daily cap $%.2f"
                % (_money(realized), out["est_loss_at_stop"], _money(after), "within" if ok else "OVER", lim))
        elif cap == "gross_exposure":
            ok = not exact["worst"] > limit
            add(cap, ok, "if every working order filled, exposure would be $%.2f, %s your gross cap $%.2f"
                % (out["worst_case_if_all_working_fill"], "within" if ok else "OVER", lim))
    out["all_pass"] = bool(out["checks"]) and all(c["ok"] for c in out["checks"])

    def suggest(text, n):
        out["suggestions"].append({"text": text, "shares": max(0, int(n)), "label": SUGGESTION_LABEL})

    if caps["max_loss_per_trade"] is not None:
        suggest("shares that fit your $%.2f price risk at a $%.2f stop (costs count against the daily cap)"
                % (float(caps["max_loss_per_trade"]), float(stop)),
                _floor_shares(caps["max_loss_per_trade"], stop))
    if caps["per_trade_notional"] is not None:
        suggest("shares that fit your $%.2f per-trade cap at $%.2f" % (float(caps["per_trade_notional"]), float(price)),
                _floor_shares(caps["per_trade_notional"], price))
    if caps["gross_exposure"] is not None:
        suggest("shares that fit the gross exposure you have left at $%.2f" % float(price),
                _floor_shares(max(Decimal(0), caps["gross_exposure"] - open_exp - working), price))
    return out


def worksheet(state_dir):
    """Everything the Setup panel shows. Read-only."""
    draft = read_draft(state_dir)
    approved = read_approved(state_dir)
    active = None
    try:
        active = load_limits(state_dir=state_dir, allow_draft=True)
    except LimitsError as exc:
        active = {"error": str(exc)}
    approved_ok = None
    if approved:
        try:
            check_snapshot(approved)
            approved_ok = True
        except LimitsError as exc:
            approved_ok = str(exc)
    pending = diff((approved or {}).get("values"), (draft or {}).get("values")) if draft else []
    return {"fields": list(ALL_FIELDS), "required_fields": list(FIELDS),
            "optional_fields": list(OPTIONAL_FIELDS), "help": FIELD_HELP, "draft": draft, "approved": approved,
            "draft_hash": content_hash(draft.get("values")) if draft else None,
            "approved_hash": (approved or {}).get("hash") or None,
            "approved_ok": approved_ok, "active": active, "pending_diff": pending,
            "confirm_phrase": CONFIRM_PHRASE, "test_examples": [dict(e) for e in TEST_EXAMPLES],
            "labels": {"draft": DRAFT_LABEL, "approved": APPROVED_LABEL, "test": TEST_EXAMPLE_LABEL}}


def _cli(argv):
    """python3 -IB alpaca/sizing.py approve --state-dir DIR [--from-file my_limits.json]

    Interactive, for the operator at his own keyboard: shows the diff, asks for the phrase and a
    reason. 'show' prints the worksheet. Nothing here touches the network or credentials."""
    import argparse
    ap = argparse.ArgumentParser(prog="sizing.py")
    ap.add_argument("command", choices=("show", "approve"))
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--from-file", help="your filled-in copy of limits.template.json")
    args = ap.parse_args(argv)
    if args.command == "show":
        print(json.dumps(worksheet(args.state_dir), indent=2, sort_keys=True))
        return 0
    if args.from_file:
        obj, why = _read_json(args.from_file)
        if obj is None:
            print("Cannot read %s: %s" % (args.from_file, why))
            return 2
        try:
            save_draft(args.state_dir, (obj or {}).get("values"), copied_from=os.path.basename(args.from_file))
        except LimitsError as exc:
            print("Not saved: %s" % exc)
            return 2
    draft = read_draft(args.state_dir)
    if not draft:
        print("No draft in %s. Use --from-file or the Setup panel." % args.state_dir)
        return 2
    seen = worksheet(args.state_dir)   # what is shown now is what approval is bound to
    old = (read_approved(args.state_dir) or {}).get("values")
    print("Changes (old -> new):")
    for row in diff(old, draft.get("values")) or [{"field": "(none)", "old": "", "new": ""}]:
        print("  %-20s %s -> %s" % (row["field"], row["old"], row["new"]))
    confirm = input('Type "%s" to approve: ' % CONFIRM_PHRASE)
    reason = input("Reason: ")
    try:
        snap = approve(args.state_dir, confirm, reason, reviewed_draft_hash=seen["draft_hash"],
                       prior_approved_hash=seen["approved_hash"])
    except LimitsError as exc:
        print("Not approved: %s" % exc)
        return 2
    print("Approved. hash %s written to %s" % (snap["hash"][:12], approved_path(args.state_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
