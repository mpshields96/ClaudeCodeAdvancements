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
  to the fresh position in the reducing direction, minus same-side desk orders still working.
- Integrity faults (foreign SPY order, position mismatch that survives a re-poll, overfill, fill
  regression, fractional quantity, refused transport) disable the adapter; it stays off until the
  operator enables it again.
- Fills are derived from cumulative filled_qty. The last seen cumulative quantity per order is
  persisted (fsync + atomic replace) BEFORE a fill event is queued, so a restart never books twice.
"""
import json
import math
import os
import re
import tempfile
import time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from alpaca import (LABEL_ALPACA_PAPER, LABEL_INJECTED, LABEL_MOCK_LOCAL, ORDER_TYPES, SYMBOL,
                    TIME_IN_FORCE)
from alpaca.state import AdapterState
from alpaca.transport import TransportRefused
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
               LABEL_INJECTED: "INJECTED TRANSPORT fill"}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


class AlpacaPaperBroker(object):
    symbol = SYMBOL
    exits_hold_position = True    # a working sell holds its shares (no reduce-only flag for equities)

    def __init__(self, transport, state_dir, evidence_label, adapter_state):
        if evidence_label not in PRICE_BASIS:
            raise ValueError("unknown evidence label")
        injected = bool(getattr(transport, "injected", False))
        if (evidence_label == LABEL_ALPACA_PAPER) == injected:
            raise ValueError("evidence label does not match the transport (paper label needs the real "
                             "transport; mock/injected labels need an injected transport)")
        if not isinstance(adapter_state, AdapterState):
            raise ValueError("adapter_state must be an AdapterState")
        self.transport = transport
        self.adapter_state = adapter_state
        self.NAME = self.label = evidence_label
        self.mock = evidence_label != LABEL_ALPACA_PAPER
        self.price_basis = PRICE_BASIS[evidence_label]
        self.state_dir = os.path.abspath(state_dir)
        self.path = os.path.join(self.state_dir, BOOK_FILE)
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
                    "listing_incomplete": False}
            self._write(book)
            return book
        try:
            with open(self.path) as fh:
                book = json.load(fh)
            if not isinstance(book, dict) or book.get("format") != BOOK_FORMAT or \
                    not isinstance(book.get("orders"), dict):
                raise ValueError("bad format")
        except (OSError, ValueError):
            self.adapter_state.disable("BOOK_UNREADABLE: %s is unreadable or malformed" % BOOK_FILE)
            raise ValueError("%s is unreadable or malformed; the adapter is disabled" % BOOK_FILE)
        for rec in book["orders"].values():
            if rec.get("state") == "sending":       # crashed between persist and POST: may exist
                rec["state"] = "uncertain"
        book.setdefault("integrity", [])
        book.setdefault("listing_incomplete", False)
        return book

    def _write(self, book):
        os.makedirs(self.state_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".alpaca_broker.", dir=self.state_dir)
        with os.fdopen(fd, "w") as fh:
            json.dump(book, fh, indent=1, sort_keys=True)
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
        fresh = AdapterState(os.path.dirname(self.adapter_state.path))
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
        if rec.get("state") in UNRESOLVED:
            return int(rec["qty"]) - int(rec.get("cum_qty") or 0)
        if rec.get("status") == "working":
            return int(rec["qty"]) - int(rec.get("cum_qty") or 0)
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
                "filled_qty": int(rec.get("cum_qty") or 0), "avg_fill_price": rec.get("avg"),
                "fills": [dict(f) for f in rec.get("fills", [])], "evidence": self.label,
                "mock": self.mock, "simulated": True}

    def _public_foreign(self, row):
        q = _num(row.get("qty"))
        return {"client_id": row.get("client_order_id"), "order_id": row.get("id"), "symbol": row.get("symbol"),
                "side": row.get("side"), "qty": int(q) if q is not None else None,
                "status": map_status(row.get("status")), "alpaca_status": row.get("status"),
                "filled_qty": int(_num(row.get("filled_qty")) or 0), "fills": [], "external": True,
                "evidence": self.label, "mock": self.mock, "simulated": True}

    def _emit(self, ev):
        ev = dict(ev)
        ev["evidence"] = self.label
        ev["simulated"] = True
        self._events.append(ev)

    def _reject(self, client_id, reason, **extra):
        out = {"status": "rejected", "client_id": client_id, "reason": reason, "evidence": self.label,
               "simulated": True}
        out.update(extra)
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
        cum0 = int(rec.get("cum_qty") or 0)
        raw_cum = _num(row.get("filled_qty"))
        avg1 = _num(row.get("filled_avg_price"))
        cum1 = cum0
        if raw_cum is None or raw_cum < 0:
            self._integrity("BAD_RECORD", "order %s has no usable filled_qty" % rec.get("order_id"))
        elif raw_cum != int(raw_cum):
            self._integrity("FRACTIONAL_QTY", "order %s filled %s shares" % (rec.get("order_id"), raw_cum))
        else:
            cum1 = int(raw_cum)
        if cum1 < cum0:
            self._integrity("FILL_REGRESSION", "order %s filled_qty fell from %d to %d" % (
                rec.get("order_id"), cum0, cum1))
        elif cum1 > cum0:
            if avg1 is None or avg1 <= 0:
                self._integrity("BAD_RECORD", "order %s filled without a usable average price" % rec.get("order_id"))
            else:
                avg0 = rec.get("avg") or 0.0
                price = round((avg1 * cum1 - avg0 * cum0) / (cum1 - cum0), 6)
                ts = row.get("updated_at") or row.get("filled_at") or _now()
                fill = {"type": "fill", "exec_id": "%s:%d" % (rec["order_id"], cum1), "client_id": cid,
                        "order_id": rec["order_id"], "side": rec["side"], "qty": cum1 - cum0, "price": price,
                        "fee": 0.0, "ts": ts, "event_ts": ts, "report_ts": _now(), "base_price": price,
                        "half_spread_bps": 0.0, "slip_bps": 0.0, "price_basis": self.price_basis,
                        "mock": self.mock, "simulated": True, "evidence": self.label, "cum_qty": cum1,
                        "alpaca_status": alp}
                rec.setdefault("fills", []).append(fill)
                rec["cum_qty"] = cum1
                rec["avg"] = avg1
                new.append(fill)
                if cum1 > int(rec["qty"]):
                    self._integrity("OVERFILL", "order %s filled %d of %d" % (rec["order_id"], cum1, rec["qty"]))
        rec["status"] = map_status(alp)
        self._save()                                     # persisted before any event is queued
        for f in new:
            self._events.append(dict(f))
        if rec["status"] in ("canceled", "rejected") and not rec.get("terminal_emitted"):
            rec["terminal_emitted"] = True
            self._save()
            if rec["status"] == "canceled":
                self._emit({"type": "canceled", "client_id": cid, "order_id": rec.get("order_id"),
                            "filled_qty": int(rec.get("cum_qty") or 0)})
            else:
                self._emit({"type": "rejected", "client_id": cid, "order_id": rec.get("order_id"),
                            "reason": "ALPACA_REJECTED"})
        return new

    def _adopt_row(self, row):
        cid = row.get("client_order_id")
        q = _num(row.get("qty"))
        rec = {"state": "acked", "order_id": row.get("id"), "side": row.get("side"),
               "qty": int(q) if q is not None else 0, "limit": _num(row.get("limit_price")),
               "stop": _num(row.get("stop_price")), "tag": None, "reduce_only": False,
               "submit_ts": row.get("submitted_at"), "cum_qty": 0, "avg": None, "fills": [],
               "adopted": True}
        self.book["orders"][cid] = rec
        return cid, rec

    # ------------------------------------------------------------------ positions
    def _book_net(self):
        net = 0
        for rec in self.book["orders"].values():
            q = int(rec.get("cum_qty") or 0)
            net += q if rec.get("side") == "buy" else -q
        return net

    def _read_positions(self):
        st, rows = self._get("/v2/positions")
        if st != 200 or not isinstance(rows, list):
            raise BrokerOutage("GET /v2/positions answered HTTP %s" % st)
        out = {SYMBOL: {"qty": 0, "avg_price": 0.0, "evidence": self.label, "simulated": True}}
        for row in rows:
            if not isinstance(row, dict) or not row.get("symbol"):
                raise BrokerOutage("positions listing has a malformed row")
            q = _num(row.get("qty"))
            if q is None:
                raise BrokerOutage("position %s has no usable qty" % row.get("symbol"))
            fractional = q != int(q)
            if fractional:
                self._integrity("FRACTIONAL_QTY", "position %s is %s shares" % (row["symbol"], row.get("qty")))
            sign = -1 if (row.get("side") == "short" or q < 0) else 1
            exact = str(row.get("qty")).lstrip("-")
            qi = sign * int(abs(q))
            out[row["symbol"]] = {"qty": qi, "qty_exact": ("-" if sign < 0 else "") + exact,
                                  "fractional": fractional,
                                  "avg_price": _num(row.get("avg_entry_price")) or 0.0,
                                  "evidence": self.label, "simulated": True}
        return out

    def positions(self):
        out = self._read_positions()
        if out[SYMBOL]["qty"] != self._book_net():
            self._poll_open()                      # a fill may simply not have been seen yet
            out = self._read_positions()
            if out[SYMBOL]["qty"] != self._book_net():
                self._integrity("POSITION_MISMATCH", "Alpaca SPY position %d, desk fills net %d" % (
                    out[SYMBOL]["qty"], self._book_net()))
        return out

    # ------------------------------------------------------------------ submit
    def submit(self, client_id, side, qty, limit=None, stop=None, tag=None, reduce_only=False):
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
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
        working_same = sum(self._reserved(r) for c, r in self.book["orders"].items()
                           if c != client_id and r.get("side") == side)
        if positions[SYMBOL].get("fractional"):
            return self._reject(client_id, "POSITION_UNSUPPORTED_FRACTIONAL",
                                qty_exact=positions[SYMBOL].get("qty_exact"),
                                detail="SPY position %s is fractional; the desk does not trade it" %
                                positions[SYMBOL].get("qty_exact"))
        if reduce_only:
            room = (pos if side == "sell" else -pos) - working_same
            if room <= 0:
                return self._reject(client_id, "REDUCE_ONLY_NO_POSITION")
            requested, qty = qty, min(qty, room)
        else:
            requested = qty
            if side == "sell" and qty > pos - working_same:
                return self._reject(client_id, "SHORT_OPEN_BLOCKED",
                                    detail="selling %d against position %d (%d already working) would open a short"
                                    % (qty, pos, working_same))
            why = self._exec_cap_refusal(client_id, side, qty, pos, limit, stop)
            if why:
                return self._reject(client_id, why["reason"], cap=why["cap"], notional=why["notional"],
                                    limit=why["exec_price"])
        rec = {"state": "sending", "order_id": None, "side": side, "qty": int(qty), "requested_qty": requested,
               "limit": limit, "stop": stop, "tag": tag, "reduce_only": bool(reduce_only),
               "submit_ts": _now(), "status": None, "alpaca_status": None, "cum_qty": 0, "avg": None,
               "fills": []}
        if any(requested_px[k] is not None and _num(requested_px[k]) != rec[k] for k in ("limit", "stop")):
            rec["price_requested"] = {k: _num(v) for k, v in requested_px.items() if v is not None}
            rec["price_rule"] = "rounded to the $0.01 tick: sell up, buy down"
        self.book["orders"][client_id] = rec
        self._save()
        body = {"symbol": SYMBOL, "qty": str(int(qty)), "side": side, "type": otype,
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
                        "order_id": rec["order_id"], "evidence": self.label, "simulated": True}
            return {"status": "accepted", "client_id": client_id, "order_id": rec["order_id"],
                    "evidence": self.label, "simulated": True}
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
        others = 0.0
        for c, r in self.book["orders"].items():
            if c == client_id or r.get("side") != side or r.get("reduce_only"):
                continue
            left = self._reserved(r)
            if left > 0:
                others += left * float(r.get("limit") or r.get("stop") or px)
        notional = opening * px
        gross_after = abs(pos) * px + others + notional
        cap_name = None
        if per is not None and notional > float(per) + 1e-9:
            cap_name = "per_trade_notional"
        elif gross_cap is not None and gross_after > float(gross_cap) + 1e-9:
            cap_name = "gross_exposure"
        if cap_name is None:
            return None
        rec = {"client_id": client_id, "order_id": None, "side": side, "qty": opening, "exec_price": px,
               "per_trade_cap": per, "gross_cap": gross_cap, "bar_ts_close": self._last_bar_ts,
               "notional": round(notional, 6), "gross_after": round(gross_after, 6), "reason": "EXEC_CAP",
               "cap": cap_name, "simulated": True, "evidence": self.label,
               "note": "refused before sending, at the order's own limit price; nothing was sent"}
        self.exec_refusals.append(rec)
        self.exec_refusals = self.exec_refusals[-200:]
        return rec

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
            return self._cancel_result(client_id, oid, "canceled", None, filled_qty=int(rec.get("cum_qty") or 0),
                                       alpaca_status=alp)
        if st == 422:
            if rec.get("status") == "filled":
                return self._cancel_result(client_id, oid, "rejected", "ALREADY_FILLED")
            if rec.get("status") in ("canceled", "rejected"):
                return self._cancel_result(client_id, oid, "rejected", "ALREADY_DONE")
            if alp == "pending_cancel":
                return self._cancel_result(client_id, oid, "canceled", None,
                                           filled_qty=int(rec.get("cum_qty") or 0), alpaca_status=alp)
        return self._cancel_result(client_id, oid, "rejected", "CANCEL_REFUSED", http_status=st)

    def _cancel_result(self, client_id, order_id, status, reason, **extra):
        out = {"status": status, "client_id": client_id, "order_id": order_id, "evidence": self.label,
               "simulated": True}
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
                self._integrity("FOREIGN_ORDER", "SPY order %s (%s) was not placed by this desk" % (
                    cid, row.get("status")))
        self.book["listing_incomplete"] = not complete
        self._save()
        return {"orders": out, "complete": complete, "total": len(out) if complete else "unknown",
                "evidence": self.label, "simulated": True}

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
                "integrity": list(self.book.get("integrity", [])[-20:]), "simulated": True}
