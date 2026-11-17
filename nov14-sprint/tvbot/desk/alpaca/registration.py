"""Exact private registration of desk-placed PAPER orders that the broker book does not hold.

An operator-run PAPER trial can place SPY orders through the desk's own paper transport without the
desk's broker book (alpaca_broker.json) knowing their client ids. The next listing then sees them as
foreign and the adapter locks (FOREIGN_ORDER) until their trade date has ended. A registration lets
the PAPER broker settle exactly those rows earlier, but only when the whole registration is
authenticated against the broker:

- the file is private: a regular file (not a symlink) named FILE in the paper state folder, readable
  by its owner only (no group or other bits), never in git or a release ZIP;
- every registered row is present in a COMPLETE listing and matches the broker row exactly
  (ids, symbol, side, quantities, average price, status and every registered timestamp);
- every row is terminal and clean: filled with filled_qty == qty, or canceled / expired / rejected
  with exactly zero shares. A working, partially filled or unknown status is refused;
- the broker's FILL activities (terminal broker events) agree with every row: the executions of a
  filled row sum to its filled quantity on the same side and symbol, exactly one of them is the
  final "fill" with nothing left, and a zero-share row has no executions at all;
- the registered orders net to zero shares, and the broker's SPY position equals the desk book's own
  net, so the registered orders leave nothing behind (flat reconciliation).

If any part fails, nothing in the registration settles and every one of its rows keeps locking under
the existing foreign-order rule. The live broker never reads a registration. This module is pure:
no network, clock or environment; the broker supplies the listing, activities and positions.
"""
import json
import os
import stat
from decimal import Decimal, InvalidOperation

FILE = "paper_registration.json"
FORMAT = "paper-desk-registration-1"
REASON_PREFIX = "registered desk PAPER order"
MAX_ROWS = 200
SYMBOL = "SPY"
SIDES = ("buy", "sell")
ZERO_STATUSES = ("canceled", "expired", "rejected")
TERMINAL_STAMP = {"filled": "filled_at", "canceled": "canceled_at", "expired": "expired_at",
                  "rejected": "failed_at"}
TEXT_KEYS = ("id", "client_order_id", "symbol", "side", "status", "submitted_at")
OPTIONAL_STAMPS = ("filled_at", "canceled_at", "expired_at", "failed_at")
QTY_KEYS = ("qty", "filled_qty")


class RegistrationInvalid(ValueError):
    """The registration file exists but cannot be trusted; nothing in it settles."""


def exact(v):
    """Exact non-negative Decimal from an Alpaca string or int; None for float, bool or malformed."""
    if isinstance(v, bool) or not isinstance(v, (int, str, Decimal)):
        return None
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d < 0:
        return None
    return d


def _text(v):
    return isinstance(v, str) and 0 < len(v) <= 200 and v == v.strip()


def path(state_dir):
    return os.path.join(os.path.abspath(state_dir), FILE)


def load(state_dir):
    """The validated registration rows, None when there is no file, or RegistrationInvalid."""
    p = path(state_dir)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RegistrationInvalid("registration file cannot be read: %s" % exc.__class__.__name__)
    if not stat.S_ISREG(st.st_mode):
        raise RegistrationInvalid("registration must be a regular file, not a link or folder")
    if st.st_mode & 0o077:
        raise RegistrationInvalid("registration file must be readable by its owner only (mode 600)")
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        raise RegistrationInvalid("registration file must belong to the desk's user")
    try:
        with open(p) as fh:
            doc = json.load(fh, parse_float=lambda s: float("nan"))   # a float quantity never matches
    except (OSError, ValueError):
        raise RegistrationInvalid("registration file is unreadable or not JSON")
    return validate(doc)


def validate(doc):
    """Normalized registered rows (list of dicts) or RegistrationInvalid."""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise RegistrationInvalid("registration format must be %s" % FORMAT)
    if doc.get("mode") != "paper":
        raise RegistrationInvalid("a registration applies to PAPER only")
    rows = doc.get("orders")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        raise RegistrationInvalid("registration needs 1 to %d orders" % MAX_ROWS)
    out, ids, cids = [], set(), set()
    net = Decimal(0)
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RegistrationInvalid("registered order %d is not an object" % i)
        for k in TEXT_KEYS:
            if not _text(row.get(k)):
                raise RegistrationInvalid("registered order %d has no usable %s" % (i, k))
        if row["symbol"] != SYMBOL:
            raise RegistrationInvalid("registered order %d is not SPY" % i)
        if row["side"] not in SIDES:
            raise RegistrationInvalid("registered order %d has an unknown side" % i)
        status = row["status"]
        if status not in TERMINAL_STAMP:
            raise RegistrationInvalid("registered order %d is not terminal (%s)" % (i, status))
        qty, filled = exact(row.get("qty")), exact(row.get("filled_qty"))
        if qty is None or qty <= 0 or filled is None:
            raise RegistrationInvalid("registered order %d needs exact qty and filled_qty strings" % i)
        if status == "filled":
            if filled != qty:
                raise RegistrationInvalid("registered order %d is filled but not completely" % i)
            if exact(row.get("filled_avg_price")) in (None, Decimal(0)):
                raise RegistrationInvalid("registered order %d needs its exact filled_avg_price" % i)
        elif filled != 0:
            raise RegistrationInvalid("registered order %d executed shares before it ended" % i)
        stamps = {}
        for k in OPTIONAL_STAMPS:
            if row.get(k) is not None:
                if not _text(row[k]):
                    raise RegistrationInvalid("registered order %d has a malformed %s" % (i, k))
                stamps[k] = row[k]
        if status != "rejected" and TERMINAL_STAMP[status] not in stamps:
            raise RegistrationInvalid("registered order %d has no %s" % (i, TERMINAL_STAMP[status]))
        if row["id"] in ids or row["client_order_id"] in cids:
            raise RegistrationInvalid("registered order %d repeats an id" % i)
        ids.add(row["id"])
        cids.add(row["client_order_id"])
        net += filled if row["side"] == "buy" else -filled
        norm = {k: row[k] for k in TEXT_KEYS}
        norm.update(qty=qty, filled_qty=filled, stamps=stamps,
                    filled_avg_price=exact(row.get("filled_avg_price")) if status == "filled" else None)
        out.append(norm)
    if net != 0:
        raise RegistrationInvalid("registered orders are not flat (net %s shares)" % net)
    return out


def match_row(reg, row):
    """None when the broker row is exactly the registered order, else why not."""
    if not isinstance(row, dict):
        return "registered order %s is not in the listing" % reg["client_order_id"]
    for k in TEXT_KEYS:
        if row.get(k) != reg[k]:
            return "registered order %s differs from the broker on %s" % (reg["client_order_id"], k)
    for k in QTY_KEYS:
        if exact(row.get(k)) != reg[k]:
            return "registered order %s differs from the broker on %s" % (reg["client_order_id"], k)
    if reg["filled_avg_price"] is not None and exact(row.get("filled_avg_price")) != reg["filled_avg_price"]:
        return "registered order %s differs from the broker on filled_avg_price" % reg["client_order_id"]
    for k in OPTIONAL_STAMPS:
        if row.get(k) != reg["stamps"].get(k):
            return "registered order %s differs from the broker on %s" % (reg["client_order_id"], k)
    return None


def check_fills(regs, activities):
    """None when the FILL activities authenticate every registered order, else why not."""
    if not isinstance(activities, list):
        return "fill activities are not a list"
    by_order = {}
    for a in activities:
        if not isinstance(a, dict):
            return "a fill activity is malformed"
        by_order.setdefault(a.get("order_id"), []).append(a)
    for reg in regs:
        acts = by_order.get(reg["id"], [])
        cid = reg["client_order_id"]
        if reg["filled_qty"] == 0:
            if acts:
                return "registered order %s shows executions but is registered with none" % cid
            continue
        total, finals = Decimal(0), 0
        for a in acts:
            if a.get("activity_type", "FILL") != "FILL" or a.get("symbol") != SYMBOL or a.get("side") != reg["side"]:
                return "a fill activity for registered order %s is not a %s SPY execution" % (cid, reg["side"])
            q, cum, left = exact(a.get("qty")), exact(a.get("cum_qty")), exact(a.get("leaves_qty"))
            if q is None or q <= 0 or cum is None or left is None or cum > reg["filled_qty"] \
                    or cum + left != reg["qty"]:
                return "a fill activity for registered order %s has unusable quantities" % cid
            total += q
            if a.get("type") == "fill":
                if left != 0 or cum != reg["filled_qty"]:
                    return "the final fill of registered order %s leaves shares open" % cid
                finals += 1
            elif a.get("type") != "partial_fill":
                return "a fill activity for registered order %s has an unknown type" % cid
        if total != reg["filled_qty"] or finals != 1:
            return "fill activities for registered order %s total %s shares, registered %s" % (
                cid, total, reg["filled_qty"])
    return None


def reason(reg, events):
    return "%s (%s, %s shares), authenticated against %d fill event(s) and a flat reconcile" % (
        REASON_PREFIX, reg["status"], reg["filled_qty"], events)


KEEP = TEXT_KEYS + QTY_KEYS + ("filled_avg_price",) + OPTIONAL_STAMPS


def build(rows):
    """A registration document from broker order rows (GET /v2/orders JSON), validated."""
    doc = {"format": FORMAT, "mode": "paper",
           "orders": [dict((k, r.get(k)) for k in KEEP if r.get(k) is not None) for r in rows]}
    validate(doc)
    return doc


def write(out_path, doc):
    """Write a validated registration privately (mode 600, no overwrite)."""
    validate(doc)
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.chmod(out_path, 0o600)


def main(argv):
    """python3 -I -B alpaca/registration.py <orders.json> <out path>: build from a list of broker order
    rows (or {"orders": [...]}) and write it mode 600. Run from desk/. Prints only the count, never an id."""
    if len(argv) != 2:
        print("usage: python3 -I -B alpaca/registration.py <orders.json> <out path>")
        return 2
    with open(argv[0]) as fh:
        src = json.load(fh)
    rows = src.get("orders") if isinstance(src, dict) else src
    try:
        doc = build(rows if isinstance(rows, list) else [])
        write(argv[1], doc)
    except (RegistrationInvalid, OSError) as exc:
        print("refused: %s" % exc)
        return 1
    print("wrote a registration of %d PAPER order(s), mode 600" % len(doc["orders"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
