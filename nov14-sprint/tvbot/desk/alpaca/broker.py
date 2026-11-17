"""AlpacaPaperBroker: the FakeBroker interface on Alpaca's PAPER trading API (CONTRACT.md section 3).

SPY only, whole shares, time_in_force=day, market/limit/stop. It talks only through an injected
transport (HttpsTransport for the fixed paper host, MockAlpacaTransport in tests); it never reads
credentials, environment variables or the Keychain, and starts no thread, timer or background job.

Fail-safe rules:
- New exposure is refused (no network) when the adapter is disabled (the held AdapterState or a fresh
  read of its file), or recovery is ambiguous: an unresolved uncertain submit, an incomplete last
  listing, or a blocking last reconcile (note_reconcile). Reads, cancels and a protective reduce_only
  order capped to a position read fresh in the same call still work.
- Alpaca has no reduce-only flag for equities, so reduce_only is enforced here: the quantity is capped
  to the shares this desk owns in the reducing direction (the fresh venue position, never more than the
  desk's own booked fills), minus same-side desk orders still working. Shares the desk did not trade are
  never closed (REDUCE_ONLY_NOT_DESK_OWNED).
- The gate is checked again after the fresh position read and before any order record is written, so a
  read that disables the adapter (for example a position mismatch) stops that same call's new exposure.
- Integrity faults (foreign SPY order, position mismatch that survives a re-poll, overfill, fill
  regression, fractional quantity, refused transport) disable the adapter; it stays off until the
  operator enables it again.
- Fills are derived from cumulative filled_qty. The last seen cumulative quantity per order is
  persisted (fsync + atomic replace) BEFORE a fill event is queued, so a restart never books twice.
"""
import datetime as _dt
import json
import math
import os
import re
import tempfile
import time
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from zoneinfo import ZoneInfo

from alpaca import (LABEL_ALPACA_PAPER, LABEL_INJECTED, LABEL_MOCK_LOCAL, ORDER_TYPES, SYMBOL,
                    TIME_IN_FORCE)
from alpaca import live as _live
from alpaca.live import LABEL_ALPACA_LIVE
from alpaca.state import AdapterState
from alpaca.transport import TransportRefused
from orders import qty as _qty
from orders.fake_broker import BrokerOutage, BrokerUncertain

BOOK_FILE = "alpaca_broker.json"
BOOK_FORMAT = "alpaca-broker-book-1"
SNAPSHOT_FORMAT = "alpaca-paper-broker-snapshot-1"
LIST_LIMIT = 500                    # Alpaca's documented maximum page size for GET /v2/orders
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-.:]{1,128}$")   # Alpaca allows <= 128 characters

WORKING = ("new", "accepted", "pending_new", "partially_filled", "accepted_for_bidding", "calculated",
           "pending_replace", "pending_cancel", "held", "stopped", "suspended")
CANCELED = ("canceled", "expired", "done_for_day", "replaced")
TERMINAL = ("filled", "canceled", "rejected")
# Submit states that may exist at Alpaca without the desk knowing. A 404 or an empty listing
# never proves "not placed"; only a refusal before sending does.
UNRESOLVED = ("sending", "uncertain", "not_found")
PRICE_BASIS = {LABEL_ALPACA_PAPER: "Alpaca paper fill", LABEL_MOCK_LOCAL: "MOCK LOCAL fill",
               LABEL_INJECTED: "INJECTED TRANSPORT fill", LABEL_ALPACA_LIVE: "Alpaca LIVE fill (real money)"}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------- settled foreign rows (paper only)
# A SPY order this desk did not place still disables the adapter (FOREIGN_ORDER), with two narrow
# paper-only exceptions that stop an already-reconciled history from re-locking after every operator
# enable. Both need a COMPLETE listing and an exactly parsed filled_qty (unknown is never zero):
#   (a) canceled / expired / rejected with zero shares executed: nothing happened at the venue;
#   (b) filled, or canceled / expired after a partial fill, whose every timestamp (submit, fill and
#       terminal) is before the start of the current trade date. Anything executed on the current
#       trade date keeps locking, so a foreign fill can never be hidden from that day's controls.
# The current trade date starts at the EARLIEST of the latest New York midnight, the latest Chicago
# midnight (the calendar default) and the latest 20:00 New York time: Alpaca assigns executions in
# its overnight session (after 20:00 ET) to the NEXT trade date. Fri 20:00 ET to Sun 20:00 ET has no
# session, so a row in that gap is treated like the Friday-evening boundary (it settles later, never
# earlier). Live brokers and non-paper transports never settle a foreign row. Nothing here enables
# the adapter: an operator enable is still required after any FOREIGN_ORDER disable.
FOREIGN_SETTLED_ZERO = ("canceled", "expired", "rejected")
FOREIGN_SETTLED_FILLED = ("filled", "canceled", "expired")
FOREIGN_STAMP_KEYS = ("submitted_at", "filled_at", "canceled_at", "expired_at", "failed_at", "updated_at")
FOREIGN_TERMINAL_STAMP = {"filled": "filled_at", "canceled": "canceled_at", "expired": "expired_at"}
FOREIGN_SETTLED_CAP = 500
_NY = ZoneInfo("America/New_York")
_CHI = ZoneInfo("America/Chicago")
_STAMP_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$")


def _utcnow_dt():
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_utc(v):
    """An Alpaca RFC 3339 timestamp as an aware UTC datetime, or None when absent or malformed."""
    if not isinstance(v, str):
        return None
    m = _STAMP_RE.match(v.strip())
    if not m:
        return None
    y, mo, d, h, mi, sec, frac, tz = m.groups()
    try:
        if tz == "Z":
            tzinfo = _dt.timezone.utc
        else:
            sign = 1 if tz[0] == "+" else -1
            tzinfo = _dt.timezone(sign * _dt.timedelta(hours=int(tz[1:3]), minutes=int(tz[4:6])))
        out = _dt.datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec),
                           int((frac or "0")[:6].ljust(6, "0")), tzinfo=tzinfo)
    except ValueError:
        return None
    return out.astimezone(_dt.timezone.utc)


def _foreign_qty(v):
    """Exact executed quantity, or None when absent, boolean, malformed, non-finite or negative."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
        return None
    try:
        q = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        return None
    if not q.is_finite() or q < 0:
        return None
    return q


def _latest_local(now, tz, hour):
    local = now.astimezone(tz)
    start = _dt.datetime(local.year, local.month, local.day, hour, tzinfo=tz)
    if start > local:
        prev = local.date() - _dt.timedelta(days=1)
        start = _dt.datetime(prev.year, prev.month, prev.day, hour, tzinfo=tz)
    return start.astimezone(_dt.timezone.utc)


def _foreign_day_start(now):
    """Earliest plausible start (UTC) of the trade date that contains now."""
    return min(_latest_local(now, _NY, 0), _latest_local(now, _CHI, 0), _latest_local(now, _NY, 20))


def map_status(alpaca_status):
    if alpaca_status in WORKING:
        return "working"
    if alpaca_status == "filled":
        return "filled"
    if alpaca_status in CANCELED:
        return "canceled"
    if alpaca_status == "rejected":
        return "rejected"
    return alpaca_status            # unknown statuses pass through; the manager flags UNKNOWN_STATUS


def cent_price(v, side):
    """A price on Alpaca's $0.01 tick, rounded toward the safe side, as a Decimal from the
    lexical value (never a raw float cast). The same rule serves limits and stops:
    sell UP (a sell limit never sells for less; a long's protective sell stop sits a fraction
    of a cent closer, so it never risks more than the strategy's level), buy DOWN (a buy
    limit never pays more; a short's protective buy stop likewise). None if not a positive
    finite price."""
    f = _num(v)
    if f is None or f <= 0:
        return None
    # First drop binary-float noise (0.1 + 0.2 = 0.30000000000000004 is 0.30, not a reason to
    # move a cent), then round to the tick in the safe direction.
    d = Decimal(repr(f)).quantize(Decimal("0.000001"))
    d = d.quantize(Decimal("0.01"), rounding=ROUND_CEILING if side == "sell" else ROUND_FLOOR)
    return d if d > 0 else None


def _num(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


class _Fault(Exception):
    pass


ONE_DOLLAR = Decimal("1.00")       # Alpaca's minimum notional for a fractional buy; never on a reduction
ENTRY_LISTING_LIMIT = 500
QTY_KEYS = ("qty", "requested_qty", "cum_qty")


def _xq(v):
    """Exact book quantity (int or Decimal) from a stored or venue value; None or '' is 0."""
    if v is None or v == "":
        return 0
    return _qty.parse(v, allow_zero=True)


def _jsonable(v):
    return _qty.to_json(v) if isinstance(v, Decimal) else v


def _money(v):
    """Exact Decimal from a venue money string, or None when missing or unparseable."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v).strip())
    except Exception:
        return None
    return d if d.is_finite() else None


class AlpacaPaperBroker(object):
    symbol = SYMBOL
    exits_hold_position = True    # a working sell holds its shares (no reduce-only flag for equities)

    _ALLOW_LIVE_TRANSPORT = False     # True only on AlpacaLiveBroker (and offline rehearsal tests)
    _REAL_LABEL = LABEL_ALPACA_PAPER  # the one label that needs the real (non-injected) transport
    SIMULATED = True                  # every record this class writes says simulated

    def __init__(self, transport, state_dir, evidence_label, adapter_state, fractional=False):
        if fractional not in (True, False):
            raise ValueError("fractional must be True or False")
        if evidence_label not in PRICE_BASIS \
                or (evidence_label == LABEL_ALPACA_LIVE) != (self._REAL_LABEL == LABEL_ALPACA_LIVE):
            raise ValueError("unknown evidence label")
        if getattr(transport, "MODE", "paper") != "paper" and not self._ALLOW_LIVE_TRANSPORT:
            raise ValueError("this is the PAPER broker: it labels every record simulated and cannot carry a "
                             "live-money transport (live is not wired in this build; see LIVE_READINESS.md)")
        injected = bool(getattr(transport, "injected", False))
        if (evidence_label == self._REAL_LABEL) == injected:
            raise ValueError("evidence label does not match the transport (paper label needs the real "
                             "transport; mock/injected labels need an injected transport)")
        if not isinstance(adapter_state, AdapterState):
            raise ValueError("adapter_state must be an AdapterState")
        # Paper never takes LiveAdapterState. The live broker may hold alpaca_session.py's own on/off class
        # over alpaca_live.json, so for the live label the file name decides.
        live_file = os.path.basename(str(getattr(adapter_state, "path", ""))) == _live.LiveAdapterState.FILE
        is_live = self._REAL_LABEL == LABEL_ALPACA_LIVE
        if (not is_live and isinstance(adapter_state, _live.LiveAdapterState)) or \
                (is_live and not (isinstance(adapter_state, _live.LiveAdapterState) or live_file)):
            raise ValueError("paper and live keep separate adapter state (alpaca_paper.json / alpaca_live.json)")
        self.transport = transport
        self.adapter_state = adapter_state
        self.NAME = self.label = evidence_label
        self.mock = evidence_label != self._REAL_LABEL
        self.price_basis = PRICE_BASIS[evidence_label]
        self.state_dir = os.path.abspath(state_dir)
        self.path = os.path.join(self.state_dir, BOOK_FILE)
        # Fractional mode: the approved size is fractional and this is a connected Alpaca desk. Whole
        # mode (the default) keeps every whole-share check and fault exactly as before.
        self.fractional = fractional
        self.exec_caps = {}
        self.exec_refusals = []
        self.list_limit = LIST_LIMIT
        self.last_poll_error = None
        self._events = []
        self._last_close = None
        self._last_bar_ts = None
        self._reconcile_blocking = False
        self.book = self._load_book()

    # ------------------------------------------------------------------ persistence
    def _load_book(self):
        if not os.path.exists(self.path):
            book = {"format": BOOK_FORMAT, "created_utc": _now(), "orders": {}, "integrity": [],
                    "listing_incomplete": False, "foreign_settled": {}}
            self._write(book)
            return book
        try:
            with open(self.path) as fh:
                book = json.load(fh)
            if not isinstance(book, dict) or book.get("format") != BOOK_FORMAT or \
                    not isinstance(book.get("orders"), dict):
                raise ValueError("bad format")
            for rec in book["orders"].values():          # quantities re-parsed exactly (int or Decimal)
                for k in QTY_KEYS:
                    if rec.get(k) is not None:
                        rec[k] = _xq(rec[k])
                for f in rec.get("fills") or []:
                    for k in ("qty", "cum_qty"):
                        if f.get(k) is not None:
                            f[k] = _xq(f[k])
        except (OSError, ValueError):
            self.adapter_state.disable("BOOK_UNREADABLE: %s is unreadable or malformed" % BOOK_FILE)
            raise ValueError("%s is unreadable or malformed; the adapter is disabled" % BOOK_FILE)
        for rec in book["orders"].values():
            if rec.get("state") == "sending":       # crashed between persist and POST: may exist
                rec["state"] = "uncertain"
        book.setdefault("integrity", [])
        book.setdefault("listing_incomplete", False)
        if not isinstance(book.get("foreign_settled"), dict):
            book["foreign_settled"] = {}
        return book

    def _write(self, book):
        os.makedirs(self.state_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".alpaca_broker.", dir=self.state_dir)
        with os.fdopen(fd, "w") as fh:
            json.dump(book, fh, indent=1, sort_keys=True, default=_qty.json_default)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
        try:
            dfd = os.open(self.state_dir, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

    def _save(self):
        self._write(self.book)

    # ------------------------------------------------------------------ integrity and gating
    def _integrity(self, code, detail):
        reason = "%s: %s" % (code, detail)
        self.book["integrity"].append({"utc": _now(), "code": code, "detail": str(detail)})
        self.book["integrity"] = self.book["integrity"][-200:]
        self._save()
        if self.adapter_state.enabled or self.adapter_state.data.get("disabled_reason") != reason:
            self.adapter_state.disable(reason)

    def _fresh_enabled(self):
        if not self.adapter_state.enabled:
            return False
        fresh = type(self.adapter_state)(os.path.dirname(self.adapter_state.path))
        if not fresh.enabled:
            self.adapter_state.data = fresh.data      # another writer disabled it; adopt that
            return False
        return True

    def block_reason(self, exclude=None):
        """None when new exposure may be sent, else ADAPTER_DISABLED or RECOVERY_AMBIGUOUS."""
        if not self._fresh_enabled():
            return "ADAPTER_DISABLED"
        if self.recovery_ambiguous(exclude)[0]:
            return "RECOVERY_AMBIGUOUS"
        return None

    def uncertain_client_ids(self):
        return sorted(c for c, r in self.book["orders"].items() if r.get("state") in UNRESOLVED)

    def recovery_ambiguous(self, exclude=None):
        """(True, reason) while new exposure must wait for recovery, else (False, None).
        `exclude`: a resend of that same client id is idempotent at Alpaca, so it does not block itself."""
        ids = [c for c in self.uncertain_client_ids() if c != exclude]
        if ids:
            return True, "SUBMIT_UNRESOLVED: %d submit(s) not yet seen at Alpaca (%s)" % (len(ids), ", ".join(ids))
        if self.book.get("listing_incomplete"):
            return True, "LISTING_INCOMPLETE: the last order listing was truncated"
        if self._reconcile_blocking:
            return True, "RECONCILE_BLOCKING: the last reconcile raised a blocking alarm or failed"
        return False, None

    def _reserved(self, rec):
        """Shares a desk order may still trade: working remainder, or the full qty while unresolved."""
        if rec.get("state") in UNRESOLVED or rec.get("status") == "working":
            return _qty.norm(_qty.dec(_xq(rec["qty"])) - _qty.dec(_xq(rec.get("cum_qty"))))
        return 0

    def note_reconcile(self, report):
        """The session passes each OrderManager.reconcile() report here: a blocking or failed reconcile
        makes recovery ambiguous until a clean one."""
        self._reconcile_blocking = not (isinstance(report, dict) and report.get("ok") is True)

    # ------------------------------------------------------------------ transport helpers
    def _get(self, path, query=None):
        try:
            return self.transport.request("GET", "trading", path, query)
        except TransportRefused as exc:
            self._integrity("TRANSPORT_REFUSED", str(exc))
            raise BrokerOutage("GET %s refused by the transport: %s" % (path, exc))

    # ------------------------------------------------------------------ public views
    def _public(self, cid, rec):
        return {"client_id": cid, "order_id": rec.get("order_id"), "symbol": SYMBOL, "side": rec["side"],
                "qty": rec["qty"], "requested_qty": rec.get("requested_qty", rec["qty"]),
                "limit": rec.get("limit"), "stop": rec.get("stop"), "tag": rec.get("tag"),
                "reduce_only": bool(rec.get("reduce_only")), "submit_ts": rec.get("submit_ts"),
                "status": rec.get("status"), "alpaca_status": rec.get("alpaca_status"),
                "filled_qty": _xq(rec.get("cum_qty")), "avg_fill_price": rec.get("avg"),
                "fills": [dict(f) for f in rec.get("fills", [])], "evidence": self.label,
                "mock": self.mock, "simulated": self.SIMULATED}

    def _row_qty(self, v, missing):
        """A venue row quantity: whole mode truncates as before; fractional mode keeps it exact."""
        q = _num(v)
        if q is None:
            return missing
        if self.fractional:
            try:
                return _xq(v)
            except _qty.QtyError:
                pass
        return int(q)

    def _foreign_settled(self, row, complete):
        """Why a foreign SPY row no longer needs to lock the adapter, or None (it still locks)."""
        if self._REAL_LABEL == LABEL_ALPACA_LIVE or self._ALLOW_LIVE_TRANSPORT or \
                getattr(self.transport, "MODE", "paper") != "paper":
            return None
        if complete is not True or not isinstance(row, dict):
            return None
        status = row.get("status")
        filled = _foreign_qty(row.get("filled_qty"))
        if filled is None:
            return None
        if filled == 0:
            if status in FOREIGN_SETTLED_ZERO:
                return "terminal %s with zero shares executed" % status
            return None
        if status not in FOREIGN_SETTLED_FILLED:
            return None
        if row.get("submitted_at") is None or row.get(FOREIGN_TERMINAL_STAMP[status]) is None:
            return None
        stamps = []
        for key in FOREIGN_STAMP_KEYS:
            if row.get(key) is None:
                continue
            ts = _parse_utc(row.get(key))
            if ts is None:
                return None
            stamps.append(ts)
        day_start = _foreign_day_start(_utcnow_dt())
        if max(stamps) >= day_start:
            return None
        return "%s with %s shares executed before the current trade date (started %s)" % (
            status, filled, day_start.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def _record_foreign_settled(self, row, reason):
        """Keep provenance for a settled foreign row once (again only if the row changes)."""
        settled = self.book.setdefault("foreign_settled", {})
        oid = str(row.get("id"))
        rec = {"client_id": row.get("client_order_id"), "status": row.get("status"),
               "filled_qty": str(row.get("filled_qty")), "submitted_at": row.get("submitted_at"),
               "reason": reason}
        old = settled.get(oid)
        if old is not None and all(old.get(k) == rec[k] for k in ("client_id", "status", "filled_qty",
                                                                   "submitted_at")):
            return
        rec["first_seen_utc"] = _now()
        settled[oid] = rec
        if len(settled) > FOREIGN_SETTLED_CAP:
            for k in sorted(settled, key=lambda k: settled[k].get("first_seen_utc") or "")[
                    :len(settled) - FOREIGN_SETTLED_CAP]:
                del settled[k]
        self.book["integrity"].append({"utc": rec["first_seen_utc"], "code": "FOREIGN_ORDER_SETTLED",
                                       "detail": "SPY order %s (%s, filled %s) was not placed by this desk: %s"
                                                 % (rec["client_id"], rec["status"], rec["filled_qty"], reason)})
        self.book["integrity"] = self.book["integrity"][-200:]
        self._save()

    def _public_foreign(self, row):
        return {"client_id": row.get("client_order_id"), "order_id": row.get("id"), "symbol": row.get("symbol"),
                "side": row.get("side"), "qty": self._row_qty(row.get("qty"), None),
                "status": map_status(row.get("status")), "alpaca_status": row.get("status"),
                "filled_qty": self._row_qty(row.get("filled_qty"), 0), "fills": [], "external": True,
                "evidence": self.label, "mock": self.mock, "simulated": self.SIMULATED}

    def _emit(self, ev):
        ev = dict(ev)
        ev["evidence"] = self.label
        ev["simulated"] = self.SIMULATED
        self._events.append(ev)

    def _reject(self, client_id, reason, **extra):
        out = {"status": "rejected", "client_id": client_id, "reason": reason, "evidence": self.label,
               "simulated": self.SIMULATED}
        out.update({k: _jsonable(v) for k, v in extra.items()})
        self._emit({"type": "rejected", "client_id": client_id, "reason": reason})
        return out

    # ------------------------------------------------------------------ absorb a broker order row
    def _absorb(self, cid, rec, row):
        """Fold an Alpaca order row into the book. Returns new fill dicts (already persisted and queued)."""
        alp = row.get("status")
        rec["alpaca_status"] = alp
        if row.get("id") and not rec.get("order_id"):
            rec["order_id"] = row["id"]
        rec["state"] = "acked"
        new = []
        cum0 = _xq(rec.get("cum_qty"))
        raw_cum = _num(row.get("filled_qty"))
        avg1 = _num(row.get("filled_avg_price"))
        cum1 = cum0
        if raw_cum is None or raw_cum < 0:
            self._integrity("BAD_RECORD", "order %s has no usable filled_qty" % rec.get("order_id"))
        elif raw_cum != int(raw_cum) and not self.fractional:
            self._integrity("FRACTIONAL_QTY", "order %s filled %s shares" % (rec.get("order_id"), raw_cum))
        elif not self.fractional:
            cum1 = int(raw_cum)
        else:
            try:
                cum1 = _xq(row.get("filled_qty"))      # exact from the venue's own text
            except _qty.QtyError as exc:
                self._integrity("BAD_RECORD", "order %s filled_qty %s: %s" % (
                    rec.get("order_id"), row.get("filled_qty"), exc))
        if cum1 < cum0:
            self._integrity("FILL_REGRESSION", "order %s filled_qty fell from %s to %s" % (
                rec.get("order_id"), _qty.text(cum0), _qty.text(cum1)))
        elif cum1 > cum0:
            if avg1 is None or avg1 <= 0:
                self._integrity("BAD_RECORD", "order %s filled without a usable average price" % rec.get("order_id"))
            else:
                avg0 = rec.get("avg") or 0.0
                price = round((avg1 * float(cum1) - avg0 * float(cum0)) / float(cum1 - cum0), 6)
                ts = row.get("updated_at") or row.get("filled_at") or _now()
                fill = {"type": "fill", "exec_id": "%s:%s" % (rec["order_id"], _qty.text(cum1)), "client_id": cid,
                        "order_id": rec["order_id"], "side": rec["side"],
                        "qty": _qty.norm(_qty.dec(cum1) - _qty.dec(cum0)), "price": price,
                        "fee": 0.0, "ts": ts, "event_ts": ts, "report_ts": _now(), "base_price": price,
                        "half_spread_bps": 0.0, "slip_bps": 0.0, "price_basis": self.price_basis,
                        "mock": self.mock, "simulated": self.SIMULATED, "evidence": self.label, "cum_qty": cum1,
                        "alpaca_status": alp}
                rec.setdefault("fills", []).append(fill)
                rec["cum_qty"] = cum1
                rec["avg"] = avg1
                new.append(fill)
                if cum1 > _xq(rec["qty"]):
                    self._integrity("OVERFILL", "order %s filled %s of %s" % (
                        rec["order_id"], _qty.text(cum1), _qty.text(_xq(rec["qty"]))))
        rec["status"] = map_status(alp)
        self._save()                                     # persisted before any event is queued
        for f in new:
            self._events.append(dict(f))
        if rec["status"] in ("canceled", "rejected") and not rec.get("terminal_emitted"):
            rec["terminal_emitted"] = True
            self._save()
            if rec["status"] == "canceled":
                self._emit({"type": "canceled", "client_id": cid, "order_id": rec.get("order_id"),
                            "filled_qty": _xq(rec.get("cum_qty"))})
            else:
                self._emit({"type": "rejected", "client_id": cid, "order_id": rec.get("order_id"),
                            "reason": "ALPACA_REJECTED"})
        return new

    def _adopt_row(self, row):
        cid = row.get("client_order_id")
        rec = {"state": "acked", "order_id": row.get("id"), "side": row.get("side"),
               "qty": self._row_qty(row.get("qty"), 0), "limit": _num(row.get("limit_price")),
               "stop": _num(row.get("stop_price")), "tag": None, "reduce_only": False,
               "submit_ts": row.get("submitted_at"), "cum_qty": 0, "avg": None, "fills": [],
               "adopted": True}
        self.book["orders"][cid] = rec
        return cid, rec

    # ------------------------------------------------------------------ positions
    def _book_net(self):
        net = Decimal(0)
        for rec in self.book["orders"].values():
            q = _qty.dec(_xq(rec.get("cum_qty")))
            net += q if rec.get("side") == "buy" else -q
        return _qty.norm(net)

    def _read_positions(self):
        st, rows = self._get("/v2/positions")
        if st != 200 or not isinstance(rows, list):
            raise BrokerOutage("GET /v2/positions answered HTTP %s" % st)
        out = {SYMBOL: {"qty": 0, "avg_price": 0.0, "evidence": self.label, "simulated": self.SIMULATED}}
        for row in rows:
            if not isinstance(row, dict) or not row.get("symbol"):
                raise BrokerOutage("positions listing has a malformed row")
            q = _num(row.get("qty"))
            if q is None:
                raise BrokerOutage("position %s has no usable qty" % row.get("symbol"))
            fractional = q != int(q)
            if fractional and not self.fractional:
                self._integrity("FRACTIONAL_QTY", "position %s is %s shares" % (row["symbol"], row.get("qty")))
            sign = -1 if (row.get("side") == "short" or q < 0) else 1
            exact = str(row.get("qty")).lstrip("-")
            if self.fractional:
                try:
                    mag = _xq(exact)
                except _qty.QtyError as exc:
                    raise BrokerOutage("position %s qty %s is not usable: %s" % (row.get("symbol"), exact, exc))
                qi = _qty.norm(-_qty.dec(mag)) if sign < 0 else mag
            else:
                qi = sign * int(abs(q))
            # "fractional" means a fractional row this desk will not trade. In fractional mode a
            # fractional row is supported, so it is False there; qty_is_fractional says what it is.
            out[row["symbol"]] = {"qty": qi, "qty_exact": ("-" if sign < 0 else "") + exact,
                                  "fractional": fractional and not self.fractional,
                                  "qty_is_fractional": fractional,
                                  "avg_price": _num(row.get("avg_entry_price")) or 0.0,
                                  "evidence": self.label, "simulated": self.SIMULATED}
        return out

    def positions(self):
        out = self._read_positions()
        if out[SYMBOL]["qty"] != self._book_net():
            self._poll_open()                      # a fill may simply not have been seen yet
            out = self._read_positions()
            if out[SYMBOL]["qty"] != self._book_net():
                self._integrity("POSITION_MISMATCH", "Alpaca SPY position %s, desk fills net %s" % (
                    _qty.text(abs(_qty.dec(out[SYMBOL]["qty"]))) if out[SYMBOL]["qty"] >= 0 else
                    "-" + _qty.text(abs(_qty.dec(out[SYMBOL]["qty"]))),
                    _qty.text(abs(_qty.dec(self._book_net()))) if self._book_net() >= 0 else
                    "-" + _qty.text(abs(_qty.dec(self._book_net())))))
        return out

    # ------------------------------------------------------------------ submit
    def submit(self, client_id, side, qty, limit=None, stop=None, tag=None, reduce_only=False):
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        if self.fractional:
            try:
                qty = _qty.parse(qty)
            except _qty.QtyError as exc:
                if "decimal places" in str(exc) or "significant digits" in str(exc):
                    return self._reject(client_id, "QTY_PRECISION", detail="%s; nothing was sent" % exc)
                raise ValueError("qty must be a positive number of shares: %s" % exc)
        else:
            # An exact fractional quantity (the manager's Decimal) is refused as a reason, not raised;
            # a float stays a caller error exactly as before.
            if isinstance(qty, Decimal) and qty.is_finite() and qty > 0 and qty != qty.to_integral_value():
                return self._reject(client_id, "FRACTIONAL_NOT_ENABLED",
                                    detail="this broker is in whole-share mode; nothing was sent")
            if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
                raise ValueError("qty must be a positive whole number of shares")
        if not isinstance(client_id, str) or not CLIENT_ID_RE.match(client_id):
            return self._reject(client_id, "BAD_CLIENT_ID")
        if limit is not None and stop is not None:
            return self._reject(client_id, "UNSUPPORTED_ORDER_TYPE")
        if side == "buy" and limit is None and not reduce_only:
            return self._reject(client_id, "UNPRICED_ENTRY")      # an opening buy needs its own price bound
        # Every price goes on the $0.01 tick toward the safe side (cent_price), from its lexical
        # value: a strategy level such as an EMA-derived stop of 101.6914 becomes a sell stop of
        # 101.70, never a BAD_PRICE that leaves the shares uncovered.
        requested_px = {"limit": limit, "stop": stop}
        limit_d = stop_d = None
        if limit is not None:
            limit_d = cent_price(limit, side)
            if limit_d is None:
                return self._reject(client_id, "BAD_PRICE")
            limit = float(limit_d)
        if stop is not None:
            stop_d = cent_price(stop, side)
            if stop_d is None:
                return self._reject(client_id, "BAD_PRICE")
            stop = float(stop_d)
        otype = "limit" if limit is not None else ("stop" if stop is not None else "market")
        if otype not in ORDER_TYPES:
            return self._reject(client_id, "UNSUPPORTED_ORDER_TYPE")
        if self.fractional:
            # Entry: buy limit. Protective: reduce-only sell stop. Exit / Stop & Close: reduce-only
            # sell market. Every other shape is refused here, before any record or POST.
            ok = (side == "buy" and not reduce_only and otype == "limit") or \
                 (side == "sell" and reduce_only and otype in ("stop", "market"))
            if not ok:
                return self._reject(client_id, "FRACTIONAL_ORDER_SHAPE",
                                    detail="fractional mode sends only a buy limit entry or a reduce-only "
                                    "sell stop/market; nothing was sent")
            if side == "buy" and limit_d * _qty.dec(qty) < ONE_DOLLAR:
                return self._reject(client_id, "BELOW_MIN_NOTIONAL",
                                    notional=str(limit_d * _qty.dec(qty)),
                                    detail="limit x qty is below $1.00; the size is never raised; nothing was sent")
        prior = self.book["orders"].get(client_id)
        if prior is not None and prior.get("state") in ("acked", "rejected"):
            return self._reject(client_id, "DUPLICATE_CLIENT_ORDER_ID", order_id=prior.get("order_id"))
        if prior is not None and prior.get("state") in UNRESOLVED:
            # A sent but unseen submit is never re-POSTed, whoever asks: only finding it resolves it.
            return self._reject(client_id, "SUBMIT_UNRESOLVED",
                                detail="%s was already sent and is not visible yet; nothing was resent" % client_id)
        blocked = self.block_reason(exclude=client_id)
        if blocked and not reduce_only:
            return self._reject(client_id, blocked)
        try:
            positions = self.positions()                 # fresh read in this same operation
        except BrokerOutage as exc:
            if reduce_only:
                return self._reject(client_id, "POSITION_UNREADABLE",
                                    detail="positions could not be read (%s); nothing was sent" % exc)
            raise
        pos = positions[SYMBOL]["qty"]
        if not reduce_only:
            # The fresh read above may itself have disabled the adapter (a position mismatch, a
            # fractional row). Re-check before writing any record, so this same call sends nothing.
            blocked = self.block_reason(exclude=client_id)
            if blocked:
                return self._reject(client_id, blocked,
                                    detail="the position read in this call stopped new exposure; nothing was sent")
        working_same = sum(self._reserved(r) for c, r in self.book["orders"].items()
                           if c != client_id and r.get("side") == side)
        if positions[SYMBOL].get("fractional") and not self.fractional:
            return self._reject(client_id, "POSITION_UNSUPPORTED_FRACTIONAL",
                                qty_exact=positions[SYMBOL].get("qty_exact"),
                                detail="SPY position %s is fractional; the desk does not trade it" %
                                positions[SYMBOL].get("qty_exact"))
        if reduce_only:
            owned = self._book_net()
            if side == "sell":
                venue_room = pos if pos > 0 else 0
                reducible = min(pos, owned) if pos > 0 and owned > 0 else 0
            else:
                venue_room = -pos if pos < 0 else 0
                reducible = min(-pos, -owned) if pos < 0 and owned < 0 else 0
            room = reducible - working_same
            if room <= 0:
                if venue_room > reducible:
                    return self._reject(client_id, "REDUCE_ONLY_NOT_DESK_OWNED", venue=pos, desk_booked=owned,
                                        detail="Alpaca shows %s SPY, the desk booked %s; shares it did not "
                                        "trade are not closed; nothing was sent" % (pos, owned))
                return self._reject(client_id, "REDUCE_ONLY_NO_POSITION")
            requested, qty = qty, min(qty, room)
        else:
            requested = qty
            if side == "sell" and qty > pos - working_same:
                return self._reject(client_id, "SHORT_OPEN_BLOCKED",
                                    detail="selling %s against position %s (%s already working) would open a short"
                                    % (qty, pos, working_same))
            why = self._exec_cap_refusal(client_id, side, qty, pos, limit, stop)
            if why:
                return self._reject(client_id, why["reason"], cap=why["cap"], notional=why["notional"],
                                    limit=why["exec_price"])
            if self.fractional:
                why = self._cash_refusal(client_id, qty, limit_d)
                if why:
                    return self._reject(client_id, why.pop("reason"), **why)
        rec = {"state": "sending", "order_id": None, "side": side, "qty": qty, "requested_qty": requested,
               "limit": limit, "stop": stop, "tag": tag, "reduce_only": bool(reduce_only),
               "submit_ts": _now(), "status": None, "alpaca_status": None, "cum_qty": 0, "avg": None,
               "fills": []}
        if any(requested_px[k] is not None and _num(requested_px[k]) != rec[k] for k in ("limit", "stop")):
            rec["price_requested"] = {k: _num(v) for k, v in requested_px.items() if v is not None}
            rec["price_rule"] = "rounded to the $0.01 tick: sell up, buy down"
        self.book["orders"][client_id] = rec
        self._save()
        body = {"symbol": SYMBOL, "qty": _qty.text(qty), "side": side, "type": otype,
                "time_in_force": TIME_IN_FORCE, "client_order_id": client_id}
        if limit_d is not None:
            body["limit_price"] = str(limit_d)
        if stop_d is not None:
            body["stop_price"] = str(stop_d)
        try:
            st, payload = self.transport.request("POST", "trading", "/v2/orders", None, body)
        except BrokerUncertain:
            rec["state"] = "uncertain"
            self._save()
            raise
        except TransportRefused as exc:
            self._integrity("TRANSPORT_REFUSED", str(exc))
            if exc.sent:
                rec["state"] = "uncertain"
                self._save()
                raise BrokerUncertain("POST /v2/orders refused after sending: %s" % exc)
            rec["state"] = "rejected"
            rec["status"] = "rejected"
            self._save()
            return self._reject(client_id, "TRANSPORT_REFUSED")
        return self._on_post(client_id, rec, st, payload)

    def _on_post(self, client_id, rec, st, payload):
        msg = str((payload or {}).get("message", "")).lower() if isinstance(payload, dict) else ""
        if st == 200 and isinstance(payload, dict) and payload.get("id"):
            if payload.get("client_order_id") not in (None, client_id) or payload.get("symbol") not in (None, SYMBOL):
                self._integrity("BAD_RECORD", "order answer does not match the request")
            rec["order_id"] = payload["id"]
            self._emit({"type": "ack", "client_id": client_id, "order_id": rec["order_id"]})
            self._absorb(client_id, rec, payload)
            if rec["status"] == "rejected":
                return {"status": "rejected", "client_id": client_id, "reason": "ALPACA_REJECTED",
                        "order_id": rec["order_id"], "evidence": self.label, "simulated": self.SIMULATED}
            return {"status": "accepted", "client_id": client_id, "order_id": rec["order_id"],
                    "evidence": self.label, "simulated": self.SIMULATED}
        if 200 <= st < 300:                               # success without a usable order: unknown
            rec["state"] = "uncertain"
            self._save()
            raise BrokerUncertain("POST /v2/orders answered %d without an order id" % st)
        if st == 422 and "unique" in msg:
            rec["state"] = "uncertain"                   # an earlier attempt landed; adopt by query
            self._save()
            found = self.query(client_id)
            return self._reject(client_id, "DUPLICATE_CLIENT_ORDER_ID",
                                order_id=(found or {}).get("order_id"))
        rec["state"] = "rejected"
        rec["status"] = "rejected"
        self._save()
        if st == 403:
            reason = "INSUFFICIENT_BUYING_POWER" if ("buying power" in msg or "not sufficient" in msg) \
                else "ALPACA_FORBIDDEN"
        elif st == 401:
            reason = "AUTH_FAILED"
        elif st == 429:
            reason = "RATE_LIMITED"
        else:
            reason = "ALPACA_HTTP_%d" % st
        if self.fractional:
            venue = (payload or {}).get("message") if isinstance(payload, dict) else None
            return self._reject(client_id, reason, http_status=st, venue_message=venue,
                                detail="Alpaca refused this order; it is not retried with a changed size")
        return self._reject(client_id, reason)

    def _opening_qty(self, side, qty, pos):
        if side == "buy":
            return qty if pos >= 0 else max(0, qty - abs(pos))
        return qty if pos <= 0 else max(0, qty - pos)

    def _exec_cap_refusal(self, client_id, side, qty, pos, limit, stop):
        """Priced at the order's own limit (an opening buy always has one). Gross counts the position,
        working desk entries and unresolved submits at their own prices. None when it fits."""
        per = self.exec_caps.get("per_trade_notional")
        gross_cap = self.exec_caps.get("gross_exposure")
        if per is None and gross_cap is None:
            return None
        opening = self._opening_qty(side, qty, pos)
        if opening <= 0:
            return None
        px = float(limit if limit is not None else stop)
        opening_f = float(opening)
        others = 0.0
        for c, r in self.book["orders"].items():
            if c == client_id or r.get("side") != side or r.get("reduce_only"):
                continue
            left = self._reserved(r)
            if left > 0:
                others += float(left) * float(r.get("limit") or r.get("stop") or px)
        notional = opening_f * px
        gross_after = abs(float(pos)) * px + others + notional
        cap_name = None
        if per is not None and notional > float(per) + 1e-9:
            cap_name = "per_trade_notional"
        elif gross_cap is not None and gross_after > float(gross_cap) + 1e-9:
            cap_name = "gross_exposure"
        if cap_name is None:
            return None
        rec = {"client_id": client_id, "order_id": None, "side": side, "qty": _jsonable(opening), "exec_price": px,
               "per_trade_cap": per, "gross_cap": gross_cap, "bar_ts_close": self._last_bar_ts,
               "notional": round(notional, 6), "gross_after": round(gross_after, 6), "reason": "EXEC_CAP",
               "cap": cap_name, "simulated": self.SIMULATED, "evidence": self.label,
               "note": "refused before sending, at the order's own limit price; nothing was sent"}
        self.exec_refusals.append(rec)
        self.exec_refusals = self.exec_refusals[-200:]
        return rec

    def _cash_refusal(self, client_id, qty, limit_d):
        """Fresh GET /v2/account just before the POST. Available = min(cash, non_marginable_buying_power),
        exact Decimals. The new notional plus working buys' remaining notional must fit. Fails closed."""
        try:
            st, acct = self._get("/v2/account")
        except (BrokerOutage, BrokerUncertain) as exc:
            return {"reason": "CASH_UNAVAILABLE", "detail": "account read failed (%s); nothing was sent" % exc}
        if st != 200 or not isinstance(acct, dict):
            return {"reason": "CASH_UNAVAILABLE", "detail": "GET /v2/account answered HTTP %s; nothing was sent" % st}
        cash = _money(acct.get("cash"))
        nmbp = _money(acct.get("non_marginable_buying_power"))
        if cash is None or nmbp is None:
            return {"reason": "CASH_UNAVAILABLE",
                    "detail": "cash or non_marginable_buying_power is missing or unreadable; nothing was sent"}
        effective = _money(acct.get("buying_power")) if "buying_power" in acct else nmbp
        if effective is None:
            return {"reason": "CASH_UNAVAILABLE", "detail": "unreadable effective buying power"}
        available = min(cash, nmbp, effective)
        working = Decimal(0)
        for c, r in self.book["orders"].items():
            if c == client_id or r.get("side") != "buy" or r.get("reduce_only"):
                continue
            left = self._reserved(r)
            if left > 0:
                px = r.get("limit") or r.get("stop") or limit_d
                working += _qty.dec(left) * Decimal(str(px))
        notional = limit_d * _qty.dec(qty)
        if notional + working > available:
            return {"reason": "INSUFFICIENT_CASH", "notional": str(notional), "working_buys": str(working),
                    "detail": "this buy plus working buys exceed available cash; the size is never "
                              "changed; nothing was sent"}
        return None

    # ------------------------------------------------------------------ manager reads (fractional contract)
    def funding(self):
        """GET /v2/account -> {"cash": str|None, "non_marginable_buying_power": str|None}: Alpaca's raw
        strings, None when a field is missing. The manager checks risk and funding before reserving a daily attempt; the broker also rechecks before a wire POST. This method only
        reads. Any failure raises BrokerOutage. The values are never logged, audited or put in a message."""
        try:
            st, acct = self._get("/v2/account")
        except BrokerUncertain:
            raise BrokerOutage("GET /v2/account did not answer")
        if st != 200 or not isinstance(acct, dict):
            raise BrokerOutage("GET /v2/account answered HTTP %s" % st)

        def raw(key):
            v = acct.get(key)
            return None if v is None else str(v)
        self._last_account_id = acct.get("id")
        vals = {"cash": raw("cash"), "non_marginable_buying_power": raw("non_marginable_buying_power")}
        if "buying_power" in acct:
            vals["buying_power"] = raw("buying_power")
        return vals

    def entry_buys_since(self, after_iso):
        """Every SPY BUY order Alpaca has after after_iso, any status, newest first. Not filtered by this
        book's created_utc: an order from an earlier book still counts. complete is False when the venue
        page is full (500 rows), so the caller must not treat the list as exhaustive. A non-200 answer,
        bad JSON or a non-list body raises BrokerOutage; there is never an empty fallback."""
        if not isinstance(after_iso, str) or not after_iso:
            raise ValueError("after_iso must be an ISO-8601 timestamp string")
        query = {"status": "all", "after": after_iso, "symbols": SYMBOL, "direction": "desc",
                 "nested": "false", "limit": ENTRY_LISTING_LIMIT}
        try:
            st, rows = self._get("/v2/orders", query)
        except BrokerUncertain:
            raise BrokerOutage("GET /v2/orders did not answer")
        if st != 200 or not isinstance(rows, list):
            raise BrokerOutage("GET /v2/orders answered HTTP %s without an order list" % st)
        out = []
        for o in rows:
            if not isinstance(o, dict):
                raise BrokerOutage("GET /v2/orders returned a row that is not an order")
            if o.get("side") != "buy":
                continue
            out.append({"client_id": o.get("client_order_id"), "side": o.get("side"),
                        "symbol": o.get("symbol"), "status": o.get("status"),
                        "submitted_at": o.get("submitted_at")})
        st_open, opened = self._get("/v2/orders", {"status": "open", "symbols": SYMBOL, "nested": "false",
                                                     "limit": ENTRY_LISTING_LIMIT})
        if st_open != 200 or not isinstance(opened, list):
            raise BrokerOutage("open-order reservations are unverifiable")
        foreign = False
        for o in opened:
            if not isinstance(o, dict) or o.get("side") not in ("buy", "sell"):
                raise BrokerOutage("open-order reservation is malformed")
            if o["side"] == "buy" and o.get("symbol") == SYMBOL and (o.get("client_order_id") not in self.book["orders"] or self.book["orders"][o["client_order_id"]].get("external") is True):
                foreign = True
        return {"orders": out, "foreign_working_buy": foreign,
                "complete": len(rows) < ENTRY_LISTING_LIMIT and len(opened) < ENTRY_LISTING_LIMIT}

    def reserve_entry_attempt(self, day, client, maximum, seen):
        if self._REAL_LABEL != LABEL_ALPACA_LIVE:
            return None
        from .attempts import reserve
        return reserve(getattr(self, "_last_account_id", None), SYMBOL, day, client, maximum, seen)

    # ------------------------------------------------------------------ query / cancel / listing
    def query(self, client_id):
        st, row = self._get("/v2/orders:by_client_order_id", {"client_order_id": client_id})
        rec = self.book["orders"].get(client_id)
        if st == 200 and isinstance(row, dict) and row.get("id"):
            if row.get("client_order_id") not in (None, client_id):
                self._integrity("BAD_RECORD", "query answer is for a different client id")
                raise BrokerOutage("query answer did not match the client id")
            if rec is None:
                client_id, rec = self._adopt_row(dict(row, client_order_id=client_id))
            self._absorb(client_id, rec, row)
            return self._public(client_id, rec)
        if st == 404:
            if rec is not None and rec.get("state") in UNRESOLVED:
                rec["state"] = "uncertain"            # a 404 is not proof the order was never placed
                self._save()
                raise BrokerUncertain("order %s is not visible at Alpaca; the submit stays unresolved" % client_id)
            return None
        raise BrokerOutage("order query answered HTTP %s" % st)

    def cancel(self, client_id):
        rec = self.book["orders"].get(client_id)
        if rec is None or not rec.get("order_id"):
            try:
                found = self.query(client_id)
            except BrokerUncertain:
                return self._cancel_result(client_id, None, "rejected", "SUBMIT_UNRESOLVED")
            if found is None:
                return self._cancel_result(client_id, None, "rejected", "UNKNOWN_ORDER")
            rec = self.book["orders"][client_id]
        oid = rec["order_id"]
        try:
            st, payload = self.transport.request("DELETE", "trading", "/v2/orders/%s" % oid)
        except TransportRefused as exc:
            self._integrity("TRANSPORT_REFUSED", str(exc))
            raise BrokerOutage("DELETE refused by the transport: %s" % exc)
        except BrokerUncertain as exc:
            raise BrokerOutage(str(exc))
        if st == 404:
            return self._cancel_result(client_id, oid, "rejected", "UNKNOWN_ORDER")
        try:
            gst, row = self._get("/v2/orders/%s" % oid)
            if gst == 200 and isinstance(row, dict):
                self._absorb(client_id, rec, row)
        except BrokerOutage:
            pass
        alp = rec.get("alpaca_status")
        if st in (200, 204):
            if rec.get("status") == "filled":
                return self._cancel_result(client_id, oid, "rejected", "ALREADY_FILLED")
            return self._cancel_result(client_id, oid, "canceled", None, filled_qty=_xq(rec.get("cum_qty")),
                                       alpaca_status=alp)
        if st == 422:
            if rec.get("status") == "filled":
                return self._cancel_result(client_id, oid, "rejected", "ALREADY_FILLED")
            if rec.get("status") in ("canceled", "rejected"):
                return self._cancel_result(client_id, oid, "rejected", "ALREADY_DONE")
            if alp == "pending_cancel":
                return self._cancel_result(client_id, oid, "canceled", None,
                                           filled_qty=_xq(rec.get("cum_qty")), alpaca_status=alp)
        return self._cancel_result(client_id, oid, "rejected", "CANCEL_REFUSED", http_status=st)

    def _cancel_result(self, client_id, order_id, status, reason, **extra):
        out = {"status": status, "client_id": client_id, "order_id": order_id, "evidence": self.label,
               "simulated": self.SIMULATED}
        if reason:
            out["reason"] = reason
        out.update(extra)
        return out

    def _list(self, query):
        st, rows = self._get("/v2/orders", query)
        if st != 200 or not isinstance(rows, list):
            raise BrokerOutage("GET /v2/orders answered HTTP %s" % st)
        return rows

    def list_orders(self):
        limit = int(self.list_limit)
        base = {"limit": limit, "direction": "desc", "nested": "false"}
        open_rows = self._list(dict(base, status="open"))            # every open order, however old
        recent = self._list(dict(base, status="all", after=self.book["created_utc"]))
        complete = len(open_rows) < limit and len(recent) < limit
        merged = {}
        for row in open_rows + recent:
            if isinstance(row, dict) and row.get("id"):
                merged[row["id"]] = row
        out = []
        for row in merged.values():
            cid = row.get("client_order_id")
            rec = self.book["orders"].get(cid)
            if rec is not None:
                self._absorb(cid, rec, row)
                out.append(self._public(cid, rec))
                continue
            out.append(self._public_foreign(row))
            if row.get("symbol") == SYMBOL:
                settled = self._foreign_settled(row, complete)
                if settled is not None:
                    self._record_foreign_settled(row, settled)
                else:
                    self._integrity("FOREIGN_ORDER", "SPY order %s (%s) was not placed by this desk" % (
                        cid, row.get("status")))
        self.book["listing_incomplete"] = not complete
        self._save()
        return {"orders": out, "complete": complete, "total": len(out) if complete else "unknown",
                "evidence": self.label, "simulated": self.SIMULATED}

    # ------------------------------------------------------------------ polling
    def _poll_open(self):
        new = []
        for cid, rec in list(self.book["orders"].items()):
            if rec.get("status") in TERMINAL:
                continue
            if not rec.get("order_id"):
                if rec.get("state") in UNRESOLVED:      # re-ask by client id on every step
                    seen = len(rec.get("fills", []))
                    try:
                        self.query(cid)
                    except BrokerUncertain:
                        continue
                    new.extend(self.book["orders"][cid].get("fills", [])[seen:])
                continue
            st, row = self._get("/v2/orders/%s" % rec["order_id"])
            if st == 200 and isinstance(row, dict):
                new.extend(self._absorb(cid, rec, row))
            elif st == 404:
                self._integrity("ORDER_MISSING", "order %s is gone from Alpaca" % rec["order_id"])
            else:
                raise BrokerOutage("GET order answered HTTP %s" % st)
        return new

    def step(self, bar):
        """Not a simulation: record the bar close, poll open desk orders once, return new fills."""
        if isinstance(bar, dict):
            c = _num(bar.get("close"))
            if c is not None and c > 0:
                self._last_close = c
            self._last_bar_ts = bar.get("ts_close", self._last_bar_ts)
        try:
            fills = self._poll_open()
            self.last_poll_error = None
            return fills
        except BrokerOutage as exc:
            self.last_poll_error = str(exc)
            return []

    def events(self):
        out, self._events = self._events, []
        return out

    # ------------------------------------------------------------------ session state
    def snapshot(self):
        return {"format": SNAPSHOT_FORMAT, "evidence": self.label, "exec_caps": dict(self.exec_caps),
                "exec_refusals": list(self.exec_refusals[-200:]), "last_close": self._last_close,
                "last_bar_ts": self._last_bar_ts}

    def restore(self, d):
        if not isinstance(d, dict) or d.get("format") != SNAPSHOT_FORMAT:
            raise ValueError("not an Alpaca paper broker snapshot")
        if d.get("evidence") != self.label:
            raise ValueError("snapshot evidence label differs from this broker")
        self.exec_caps = dict(d.get("exec_caps") or {})
        self.exec_refusals = list(d.get("exec_refusals") or [])
        self._last_close = d.get("last_close")
        self._last_bar_ts = d.get("last_bar_ts")
        return self

    def recovery_view(self):
        return {"evidence": self.label, "adapter": self.adapter_state.view(), "block_reason": self.block_reason(),
                "uncertain_client_ids": self.uncertain_client_ids(),
                "listing_incomplete": bool(self.book.get("listing_incomplete")),
                "reconcile_blocking": self._reconcile_blocking, "last_poll_error": self.last_poll_error,
                "integrity": list(self.book.get("integrity", [])[-20:]), "simulated": self.SIMULATED}


class AlpacaLiveBroker(AlpacaPaperBroker):
    """REAL MONEY. The paper broker's order logic (one POST per intent, query-not-resend on a lost
    acknowledgment, restart reconcile, caps before send, Stop & Close) over LiveHttpsTransport only.
    Every record says simulated False and carries the live label. It is built only around a transport
    holding this session's LiveAuthorization (alpaca/live_launch.py start); launch.py never builds it."""

    _ALLOW_LIVE_TRANSPORT = True
    _REAL_LABEL = LABEL_ALPACA_LIVE
    SIMULATED = False

    def __init__(self, transport, state_dir, evidence_label, adapter_state, fractional=False):
        if not isinstance(transport, _live.LiveHttpsTransport) or getattr(transport, "injected", True):
            raise ValueError("the LIVE broker runs only over the real LiveHttpsTransport")
        auth = transport.authorization
        if not auth.valid(transport._monotonic()):
            raise ValueError("the live authorization has expired; run alpaca/live_launch.py start again")
        if evidence_label != LABEL_ALPACA_LIVE:
            raise ValueError("live records must carry the live label")
        try:
            _live.check_live_state_dir(state_dir)
        except _live.LiveGateRefused as exc:
            raise ValueError(str(exc)) from None
        if os.path.realpath(state_dir) != os.path.realpath(auth.state_dir):
            raise ValueError("the live broker must use the state folder the live gate authorized")
        # Judged by its file, not its class: alpaca_session.py keeps its own on/off class over the same
        # alpaca_live.json. A paper file (alpaca_paper.json) or one in another folder is refused.
        path = getattr(adapter_state, "path", None)
        if not isinstance(adapter_state, AdapterState) or not isinstance(path, str) \
                or os.path.basename(path) != _live.LiveAdapterState.FILE \
                or os.path.realpath(os.path.dirname(path)) != os.path.realpath(state_dir):
            raise ValueError("the live broker needs the live adapter state (alpaca_live.json) in its own folder")
        AlpacaPaperBroker.__init__(self, transport, state_dir, evidence_label, adapter_state,
                                   fractional=fractional)
