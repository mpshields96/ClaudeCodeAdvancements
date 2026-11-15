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
  mismatch (edited after approval); a null or non-positive value; a missing or fractional fixed_shares.
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

FIELDS = ("fixed_shares", "max_loss_per_trade", "daily_loss", "per_trade_notional", "gross_exposure")
CAP_FIELDS = ("per_trade_notional", "max_loss_per_trade", "daily_loss", "gross_exposure")
FIELD_HELP = {
    "fixed_shares": "Whole shares per entry. Required. There is no default and no formula.",
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
    canon = {k: (values or {}).get(k) for k in FIELDS}
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _check(field, value, allow_null):
    """(clean value, problem or None)."""
    if value is None:
        return None, (None if allow_null else "%s is empty; only you can set it" % field)
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
    if field == "fixed_shares":
        if float(value) != int(float(value)):
            return None, "fixed_shares must be whole shares (no fractions)"
        value = int(float(value))
        if value <= 0:
            return None, "fixed_shares must be at least 1"
        return value, None
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
    return clean, problems


def is_complete(values):
    return not validate(values, allow_null=False)[1]


def diff(old_values, new_values):
    old_values = old_values or {}
    return [{"field": k, "old": old_values.get(k), "new": (new_values or {}).get(k)}
            for k in FIELDS if old_values.get(k) != (new_values or {}).get(k)]


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


def approve(state_dir, confirm, reason, by="operator (local)"):
    """Turn the current draft into the approved snapshot. Only the operator calls this."""
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
    old = read_approved(state_dir) or {}
    snap = {"provenance": PROV_APPROVED, "label": APPROVED_LABEL, "values": clean,
            "approved_utc": _now(), "reason": reason[:500], "by": str(by)[:80],
            "diff": diff(old.get("values"), clean), "hash": content_hash(clean),
            "previous_hash": old.get("hash")}
    _write_json(approved_path(state_dir), snap)
    return snap


def _loaded(obj, label):
    clean, problems = validate(obj.get("values"), allow_null=False)
    if problems:
        raise LimitsError("; ".join(problems))
    return {"values": clean, "provenance": obj.get("provenance"), "approved_utc": obj.get("approved_utc"),
            "hash": content_hash(clean), "label": label}


def check_snapshot(obj, allow_draft=False):
    """Validate a parsed limits document. Returns the load_limits() dict or raises LimitsError."""
    if not isinstance(obj, dict):
        raise LimitsError("limits file must be a JSON object")
    prov = obj.get("provenance")
    if prov == PROV_APPROVED:
        values = obj.get("values")
        if obj.get("hash") != content_hash(values):
            raise LimitsError("limits were edited after approval (hash mismatch); approve them again")
        return _loaded(obj, APPROVED_LABEL)
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
    out["provenance"] = loaded.get("provenance")
    out["hash"] = loaded.get("hash")
    return out


def _pos(x, name):
    try:
        x = float(x)
    except (TypeError, ValueError):
        raise LimitsError("%s must be a number" % name)
    if not math.isfinite(x) or x <= 0:
        raise LimitsError("%s must be more than zero" % name)
    return x


def _nonneg(x, name):
    try:
        x = float(x or 0.0)
    except (TypeError, ValueError):
        raise LimitsError("%s must be a number" % name)
    if not math.isfinite(x) or x < 0:
        raise LimitsError("%s cannot be negative" % name)
    return x


def effects(values, ref_price, stop_distance, fee_per_share=0.0, slippage_per_share=0.0,
            open_exposure=0.0, realized_loss_today=0.0, working_notional=0.0):
    """Calculated effects of a draft at a chosen reference price and illustrative stop distance.

    Pure arithmetic; it reads no files and changes nothing. Fees and slippage are the operator's
    assumptions and are labeled as such."""
    price = _pos(ref_price, "reference price")
    stop = _pos(stop_distance, "stop distance")
    fee = _nonneg(fee_per_share, "fee per share")
    slip = _nonneg(slippage_per_share, "slippage per share")
    open_exp = _nonneg(open_exposure, "open exposure")
    realized = _nonneg(realized_loss_today, "realized loss today")
    working = _nonneg(working_notional, "working orders notional")
    v, _ = validate(values or {}, allow_null=True)
    shares = v.get("fixed_shares")
    per_share_cost = 2.0 * (fee + slip)   # entry and exit
    out = {"inputs": {"reference_price": price, "stop_distance": stop},
           "assumptions": {"fee_per_share": fee, "slippage_per_share": slip, "label": ASSUMED_LABEL,
                           "note": "costs counted on entry and exit"},
           "shares": shares, "checks": [], "suggestions": [], "simulated": True}
    if shares is not None:
        notional = shares * price
        loss = shares * stop + shares * per_share_cost
        worst = open_exp + working + notional
        out.update(notional=round(notional, 2), payoff_per_1usd_move=float(shares),
                   est_loss_at_stop=round(loss, 2), est_costs=round(shares * per_share_cost, 2),
                   worst_case_if_all_working_fill=round(worst, 2))
    caps = {k: v.get(k) for k in CAP_FIELDS}
    rem = {}
    if caps["daily_loss"] is not None:
        rem["daily_loss_remaining"] = round(caps["daily_loss"] - realized, 2)
    if caps["gross_exposure"] is not None:
        rem["gross_exposure_remaining"] = round(caps["gross_exposure"] - open_exp - working, 2)
    out["remaining_capacity"] = rem

    def add(cap, ok, reason):
        out["checks"].append({"cap": cap, "ok": ok, "reason": reason})

    if shares is None:
        add("fixed_shares", False, "fixed_shares is not set, so no trade can be sized")
    for cap in CAP_FIELDS:
        limit = caps[cap]
        if limit is None:
            add(cap, False, "%s is not set; the real paper path refuses until you set it" % cap)
            continue
        if shares is None:
            continue
        if cap == "per_trade_notional":
            ok = out["notional"] <= limit
            add(cap, ok, "order value $%.2f %s your per-trade cap $%.2f"
                % (out["notional"], "is within" if ok else "is OVER", limit))
        elif cap == "max_loss_per_trade":
            ok = out["est_loss_at_stop"] <= limit
            add(cap, ok, "estimated loss at the stop $%.2f %s your per-trade loss cap $%.2f"
                % (out["est_loss_at_stop"], "is within" if ok else "is OVER", limit))
        elif cap == "daily_loss":
            after = realized + out["est_loss_at_stop"]
            ok = after <= limit
            add(cap, ok, "today's realized loss $%.2f plus this stop-out $%.2f = $%.2f, %s your daily cap $%.2f"
                % (realized, out["est_loss_at_stop"], after, "within" if ok else "OVER", limit))
        elif cap == "gross_exposure":
            ok = out["worst_case_if_all_working_fill"] <= limit
            add(cap, ok, "if every working order filled, exposure would be $%.2f, %s your gross cap $%.2f"
                % (out["worst_case_if_all_working_fill"], "within" if ok else "OVER", limit))
    out["all_pass"] = bool(out["checks"]) and all(c["ok"] for c in out["checks"])

    def suggest(text, n):
        out["suggestions"].append({"text": text, "shares": max(0, int(n)), "label": SUGGESTION_LABEL})

    if caps["max_loss_per_trade"] is not None:
        suggest("shares that fit your $%.2f risk at a $%.2f stop" % (caps["max_loss_per_trade"], stop),
                math.floor(caps["max_loss_per_trade"] / (stop + per_share_cost)))
    if caps["per_trade_notional"] is not None:
        suggest("shares that fit your $%.2f per-trade cap at $%.2f" % (caps["per_trade_notional"], price),
                math.floor(caps["per_trade_notional"] / price))
    if caps["gross_exposure"] is not None:
        suggest("shares that fit the gross exposure you have left at $%.2f" % price,
                math.floor(max(0.0, caps["gross_exposure"] - open_exp - working) / price))
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
    return {"fields": list(FIELDS), "help": FIELD_HELP, "draft": draft, "approved": approved,
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
    old = (read_approved(args.state_dir) or {}).get("values")
    print("Changes (old -> new):")
    for row in diff(old, draft.get("values")) or [{"field": "(none)", "old": "", "new": ""}]:
        print("  %-20s %s -> %s" % (row["field"], row["old"], row["new"]))
    confirm = input('Type "%s" to approve: ' % CONFIRM_PHRASE)
    reason = input("Reason: ")
    try:
        snap = approve(args.state_dir, confirm, reason)
    except LimitsError as exc:
        print("Not approved: %s" % exc)
        return 2
    print("Approved. hash %s written to %s" % (snap["hash"][:12], approved_path(args.state_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
