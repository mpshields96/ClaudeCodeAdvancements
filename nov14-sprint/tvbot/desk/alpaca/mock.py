"""In-process fake of Alpaca's paper trading API (CONTRACT.md section 2). No sockets.

MockAlpacaTransport has the same request() shape as HttpsTransport and applies the same origin, path,
query and feed refusals (it reuses the transport's validators), then routes by origin_key:
"trading" -> MockTrading.handle, "data" -> MockData.handle (W2's alpaca/mock_data.py) when given.

Every identifier is synthetic: orders are mock-ord-0001..., the account is MOCK-ACCT. JSON shapes follow
Alpaca's public docs (numbers as strings, order "status" strings, 204 on accepted cancel, 404 for an
unknown order or a flat position, 422 for a non-cancelable order or a duplicate client_order_id,
403 for insufficient buying power).

Fault knobs (all off by default):
  fault(method, kind, count=1, path_prefix="/v2/")  kind: "lost_ack" (POST only: order created, the
      answer dropped), "5xx", "timeout". Raised exactly as HttpsTransport would raise them.
  partial_next = q          the next fill of each order is capped at q shares
  cancel_mode = "pending"   DELETE answers 204 but the order sits in pending_cancel; the next
                            advance() may still fill it (fill after cancel request), then it cancels
  reject_next = "http"      next POST answers 403 insufficient buying power
  reject_next = "status"    next POST creates an order whose status is "rejected"
  add_foreign_order(...)    an order the desk did not place
  listing_cap = n           the server returns at most n rows from GET /v2/orders (truncated listing)
  advance(price)            moves the market: fills working orders that can trade at `price`
"""
import time

from alpaca.transport import TransportRefused, check_data_query, encode_query, resolve_origin, validate_path
from orders.fake_broker import BrokerOutage, BrokerUncertain

MOCK_ACCOUNT = "MOCK-ACCT"
OPEN_STATUSES = ("new", "accepted", "pending_new", "partially_filled", "pending_cancel")
CANCELABLE = ("new", "accepted", "pending_new", "partially_filled")


def _iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def _num(v):
    return None if v is None else ("%.6f" % float(v)).rstrip("0").rstrip(".")


class MockTrading(object):
    def __init__(self, buying_power=100000.0, clock=None):
        self.orders = {}            # order id -> internal row
        self.by_client = {}         # client_order_id -> order id
        self.seq = 0
        self.pos_qty = 0
        self.pos_avg = 0.0
        self.other_positions = {}   # symbol -> (qty, avg) for foreign-position tests
        self.price = None
        self.buying_power = float(buying_power)
        self.faults = []            # [{"method","kind","left","prefix"}]
        self.partial_next = None
        self.cancel_mode = "immediate"
        self.reject_next = None
        self.listing_cap = None
        self.hide_next = 0          # lost-response knob: the next N created orders stay invisible
        self.hidden = set()         # client ids invisible to lookup, GET by id and listings until reveal()
        self.clock = clock or {"timestamp": "2026-06-01T14:00:00Z", "is_open": True,
                               "next_open": "2026-06-02T13:30:00Z", "next_close": "2026-06-01T20:00:00Z"}
        self.calendar = [{"date": "2026-06-01", "open": "09:30", "close": "16:00"},
                         {"date": "2026-06-02", "open": "09:30", "close": "16:00"}]
        self.calls = []
        self._t = float(int(time.time()))  # created_at ordering; starts at wall time so "after" filters work

    # ---- knobs ----
    def fault(self, method, kind, count=1, path_prefix="/v2/"):
        if kind not in ("lost_ack", "5xx", "timeout"):
            raise ValueError("unknown fault kind")
        if kind == "lost_ack" and method != "POST":
            raise ValueError("lost_ack applies to POST only")
        self.faults.append({"method": method, "kind": kind, "left": int(count), "prefix": path_prefix})

    def add_foreign_order(self, symbol="SPY", client_order_id="foreign-manual-0001", qty=1, side="buy",
                          status="new"):
        row = self._new_row(client_order_id, symbol, side, qty, "market", None, None)
        row["status"] = status
        return row["id"]

    def set_position(self, qty, avg):
        self.pos_qty, self.pos_avg = int(qty), float(avg)

    # ---- helpers ----
    def _tick(self):
        self._t = max(self._t + 1.0, float(int(time.time())) + 1.0)
        return _iso(self._t)

    def _new_row(self, client_order_id, symbol, side, qty, otype, limit, stop):
        self.seq += 1
        oid = "mock-ord-%04d" % self.seq
        ts = self._tick()
        row = {"id": oid, "client_order_id": client_order_id, "symbol": symbol, "asset_class": "us_equity",
               "side": side, "qty": int(qty), "type": otype, "order_type": otype, "time_in_force": "day",
               "limit_price": limit, "stop_price": stop, "status": "new", "filled_qty": 0,
               "filled_avg_price": None, "created_at": ts, "submitted_at": ts, "updated_at": ts,
               "filled_at": None, "canceled_at": None, "extended_hours": False}
        self.orders[oid] = row
        self.by_client[client_order_id] = oid
        if self.hide_next > 0:
            self.hide_next -= 1
            self.hidden.add(client_order_id)
        return row

    def reveal(self):
        """The order the venue accepted becomes visible (the lost response is over)."""
        self.hidden = set()

    def _visible(self, row):
        return row is not None and row.get("client_order_id") not in self.hidden

    def _out(self, row):
        r = dict(row)
        r["qty"] = _num(row["qty"])
        r["filled_qty"] = _num(row["filled_qty"])
        r["filled_avg_price"] = _num(row["filled_avg_price"])
        r["limit_price"] = _num(row["limit_price"])
        r["stop_price"] = _num(row["stop_price"])
        return r

    def _take_fault(self, method, path):
        for f in self.faults:
            if f["left"] > 0 and f["method"] == method and path.startswith(f["prefix"]):
                f["left"] -= 1
                return f["kind"]
        return None

    @staticmethod
    def _err(code, message, http=None):
        return http, {"code": code, "message": message}

    # ---- routing ----
    def handle(self, method, path, query=None, body=None):
        query = query or {}
        self.calls.append((method, path, dict(query), None if body is None else dict(body)))
        kind = self._take_fault(method, path)
        if kind in ("5xx", "timeout"):
            exc = BrokerUncertain if method == "POST" else BrokerOutage
            raise exc("%s trading %s: mock %s" % (method, path, "server error 503" if kind == "5xx" else "timed out"))
        if method == "POST" and path == "/v2/orders":
            status, payload = self._post_order(body or {})
            if kind == "lost_ack" and status == 200:
                raise BrokerUncertain("POST trading /v2/orders: mock timed out after the order was created")
            return status, payload
        if method == "GET" and path == "/v2/orders":
            return self._list(query)
        if method == "GET" and path == "/v2/orders:by_client_order_id":
            oid = self.by_client.get(query.get("client_order_id"))
            if oid is None or not self._visible(self.orders.get(oid)):
                return 404, {"code": 40410000, "message": "order not found"}
            return 200, self._out(self.orders[oid])
        if path.startswith("/v2/orders/"):
            oid = path[len("/v2/orders/"):]
            row = self.orders.get(oid)
            if not self._visible(row):
                row = None
            if method == "GET":
                return (200, self._out(row)) if row else (404, {"code": 40410000, "message": "order not found"})
            if method == "DELETE":
                return self._cancel(row)
        if method == "GET" and path == "/v2/positions":
            out = []
            if self.pos_qty:
                out.append(self._pos_row("SPY", self.pos_qty, self.pos_avg))
            for sym, (q, a) in sorted(self.other_positions.items()):
                if q:
                    out.append(self._pos_row(sym, q, a))
            return 200, out
        if method == "GET" and path.startswith("/v2/positions/"):
            sym = path[len("/v2/positions/"):]
            if sym == "SPY" and self.pos_qty:
                return 200, self._pos_row("SPY", self.pos_qty, self.pos_avg)
            if sym in self.other_positions and self.other_positions[sym][0]:
                return 200, self._pos_row(sym, *self.other_positions[sym])
            return 404, {"code": 40410000, "message": "position does not exist"}
        if method == "GET" and path == "/v2/account":
            return 200, {"id": "mock-account-id-0001", "account_number": MOCK_ACCOUNT, "status": "ACTIVE",
                         "currency": "USD", "buying_power": _num(self.buying_power),
                         "cash": _num(self.buying_power), "pattern_day_trader": False,
                         "trading_blocked": False, "account_blocked": False}
        if method == "GET" and path == "/v2/clock":
            return 200, dict(self.clock)
        if method == "GET" and path == "/v2/calendar":
            return 200, [dict(d) for d in self.calendar]
        return 404, {"code": 40400000, "message": "endpoint not found"}

    @staticmethod
    def _pos_row(sym, q, avg):
        return {"symbol": sym, "asset_class": "us_equity", "qty": _num(abs(q)),
                "side": "long" if q > 0 else "short", "avg_entry_price": _num(avg),
                "market_value": None, "exchange": "MOCK"}

    def _post_order(self, b):
        cid = b.get("client_order_id")
        if not cid or len(cid) > 128:
            return 422, {"code": 40010001, "message": "client_order_id is invalid"}
        if cid in self.by_client:
            return 422, {"code": 40010001, "message": "client_order_id must be unique"}
        if b.get("symbol") is None or b.get("side") not in ("buy", "sell"):
            return 422, {"code": 40010001, "message": "invalid order"}
        if b.get("time_in_force") != "day" or b.get("type") not in ("market", "limit", "stop"):
            return 422, {"code": 40010001, "message": "invalid order type or time_in_force"}
        try:
            qty = int(str(b.get("qty")))
        except ValueError:
            return 422, {"code": 40010001, "message": "qty must be a whole number"}
        limit = float(b["limit_price"]) if b.get("limit_price") is not None else None
        stop = float(b["stop_price"]) if b.get("stop_price") is not None else None
        if self.reject_next == "http":
            self.reject_next = None
            return 403, {"code": 40310000, "message": "insufficient buying power"}
        ref = limit or stop or self.price or 0.0
        if b["side"] == "buy" and qty * ref > self.buying_power:
            return 403, {"code": 40310000, "message": "insufficient buying power"}
        row = self._new_row(cid, b["symbol"], b["side"], qty, b["type"], limit, stop)
        if self.reject_next == "status":
            self.reject_next = None
            row["status"] = "rejected"
        else:
            row["status"] = "accepted"
        return 200, self._out(row)

    def _cancel(self, row):
        if row is None:
            return 404, {"code": 40410000, "message": "order not found"}
        if row["status"] not in CANCELABLE:
            return 422, {"code": 42210000, "message": "order is not cancelable"}
        if self.cancel_mode == "pending":
            row["status"] = "pending_cancel"
        else:
            row["status"] = "canceled"
            row["canceled_at"] = self._tick()
        row["updated_at"] = self._tick()
        return 204, None

    def _list(self, q):
        status = q.get("status", "open")
        limit = int(q.get("limit", 50))
        if limit > 500:
            return 422, {"code": 40010001, "message": "limit must be 500 or less"}
        rows = sorted((r for r in self.orders.values() if self._visible(r)), key=lambda r: r["created_at"], reverse=q.get("direction") != "asc")
        if status == "open":
            rows = [r for r in rows if r["status"] in OPEN_STATUSES]
        elif status == "closed":
            rows = [r for r in rows if r["status"] not in OPEN_STATUSES]
        if q.get("after"):
            rows = [r for r in rows if r["submitted_at"] > q["after"]]
        if q.get("symbols"):
            syms = set(q["symbols"].split(","))
            rows = [r for r in rows if r["symbol"] in syms]
        cap = limit if self.listing_cap is None else min(limit, int(self.listing_cap))
        return 200, [self._out(r) for r in rows[:cap]]

    # ---- market ----
    def _can_trade(self, row, price):
        t, side = row["type"], row["side"]
        if t == "market":
            return True
        if t == "limit":
            return price <= row["limit_price"] if side == "buy" else price >= row["limit_price"]
        if t == "stop":
            return price >= row["stop_price"] if side == "buy" else price <= row["stop_price"]
        return False

    def _fill(self, row, q, price):
        cum0, avg0 = row["filled_qty"], row["filled_avg_price"] or 0.0
        cum1 = cum0 + q
        row["filled_avg_price"] = round((avg0 * cum0 + price * q) / cum1, 6)
        row["filled_qty"] = cum1
        row["updated_at"] = self._tick()
        signed = q if row["side"] == "buy" else -q
        if row["symbol"] != "SPY":
            oq, oa = self.other_positions.get(row["symbol"], (0, 0.0))
            self.other_positions[row["symbol"]] = (oq + signed, price)
            return
        p0 = self.pos_qty
        p1 = p0 + signed
        if p0 == 0 or (p0 > 0) != (signed > 0):
            if p1 == 0:
                self.pos_avg = 0.0
            elif (p0 > 0) != (p1 > 0) or p0 == 0:
                self.pos_avg = price
        else:
            self.pos_avg = round((self.pos_avg * abs(p0) + price * q) / abs(p1), 6)
        self.pos_qty = p1

    def advance(self, price):
        """Move the synthetic market to `price` and fill what can trade there."""
        self.price = float(price)
        for row in sorted(self.orders.values(), key=lambda r: r["created_at"]):
            if row["status"] not in ("new", "accepted", "partially_filled", "pending_cancel"):
                continue
            if not self._can_trade(row, self.price):
                if row["status"] == "pending_cancel":
                    row["status"] = "canceled"
                    row["canceled_at"] = self._tick()
                continue
            remaining = row["qty"] - row["filled_qty"]
            q = remaining if self.partial_next is None else min(remaining, int(self.partial_next))
            if q > 0:
                self._fill(row, q, self.price)
            if row["filled_qty"] >= row["qty"]:
                row["status"] = "filled"
                row["filled_at"] = row["updated_at"]
            elif row["status"] == "pending_cancel":
                row["status"] = "canceled"
                row["canceled_at"] = self._tick()
            else:
                row["status"] = "partially_filled"


class MockAlpacaTransport(object):
    """Same request() shape and refusals as HttpsTransport, served in process."""

    injected = True

    def __init__(self, trading=None, data=None):
        self.trading = trading if trading is not None else MockTrading()
        self.data = data

    def __repr__(self):
        return "MockAlpacaTransport(in-process, synthetic ids)"

    def request(self, method, origin_key, path, query=None, body=None):
        if method not in ("GET", "POST", "DELETE"):
            raise TransportRefused("method refused")
        resolve_origin(origin_key)
        validate_path(path)
        encode_query(origin_key, query)          # same key/value/feed refusals as the real transport
        if body is not None and method != "POST":
            raise TransportRefused("body only allowed on POST")
        q = {k: (str(v) if not isinstance(v, str) else v) for k, v in (query or {}).items()}
        if origin_key == "trading":
            return self.trading.handle(method, path, q, body)
        check_data_query(q)
        if self.data is None:
            return 404, {"code": 40400000, "message": "no mock data configured"}
        return self.data.handle(method, path, q)
