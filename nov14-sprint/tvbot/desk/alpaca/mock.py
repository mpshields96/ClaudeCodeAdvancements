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
  partial_next = q          the next fill of each order is capped at q shares (exact; may be fractional)
  MockTrading(fractional=True)  accepts fractional qty up to 9 decimal places and keeps every quantity
                            exact (Decimal); whole mode (the default) answers 422 for a fraction as before
  cash / non_marginable_buying_power  account fields (default: buying_power, so "100000" for a default
                            mock; a str is answered raw); account_omit = {"cash"} drops fields
  account_fail = kind       GET /v2/account fails every time: "outage" raises BrokerOutage, "http" answers
                            503, "bad_json" answers a non-object body (None restores it)
  orders_fail = kind        GET /v2/orders fails the same way ("outage" / "http" / "bad_json")
  fractionable = False      SPY is not fractionable: GET /v2/assets/SPY says so and a fractional qty
                            answers 422 (default True)
  min_buy_notional = 1.0    fractional mode: a buy below this notional answers 422 (Alpaca's $1 minimum)
  reject_sell_below = n     fractional mode: a sell whose notional is below n answers 422 with a venue
                            message (a tiny reduction the venue will not take)
  cancel_mode = "pending"   DELETE answers 204 but the order sits in pending_cancel; the next
                            advance() may still fill it (fill after cancel request), then it cancels
  reject_next = "http"      next POST answers 403 insufficient buying power
  reject_next = "status"    next POST creates an order whose status is "rejected"
  add_foreign_order(...)    an order the desk did not place
  listing_cap = n           the server returns at most n rows from GET /v2/orders (truncated listing)
  advance(price)            moves the market: fills working orders that can trade at `price`
"""
import calendar as _cal
import time
from decimal import Decimal, InvalidOperation

from alpaca.transport import TransportRefused, check_data_query, encode_query, resolve_origin, validate_path
from orders.fake_broker import BrokerOutage, BrokerUncertain

MOCK_ACCOUNT = "MOCK-ACCT"
OPEN_STATUSES = ("new", "accepted", "pending_new", "partially_filled", "pending_cancel")
CANCELABLE = ("new", "accepted", "pending_new", "partially_filled")


def _iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def _num(v):
    return None if v is None else ("%.6f" % float(v)).rstrip("0").rstrip(".")


def _q(v):
    """Exact quantity: int when whole, else a normalized Decimal. Raises ValueError when unusable."""
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("not a number: %r" % (v,))
    if not d.is_finite():
        raise ValueError("not finite: %r" % (v,))
    return int(d) if d == d.to_integral_value() else d.normalize()


def _qnum(v):
    """A quantity as Alpaca's JSON string, exact (no float rounding, no exponent)."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return format(v.normalize(), "f") if v != v.to_integral_value() else str(int(v))
    return _num(v)


class MockTrading(object):
    def __init__(self, buying_power=100000.0, clock=None, fractional=False, cash=None,
                 non_marginable_buying_power=None):
        self.orders = {}            # order id -> internal row
        self.by_client = {}         # client_order_id -> order id
        self.seq = 0
        self.pos_qty = 0
        self.pos_avg = 0.0
        self.other_positions = {}   # symbol -> (qty, avg) for foreign-position tests
        self.price = None
        self.buying_power = float(buying_power)
        self.fractional = bool(fractional)
        self.cash = buying_power if cash is None else cash
        self.non_marginable_buying_power = buying_power if non_marginable_buying_power is None \
            else non_marginable_buying_power
        self.account_omit = set()
        self.account_fail = None
        self.orders_fail = None
        self.activities = []        # test hook: FILL account activities, as Alpaca's strings
        self.activities_fail = None
        self.fractionable = True
        self.min_buy_notional = 1.0
        self.reject_sell_below = None
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
        # Fill (event) times. The desk's mock session sets event_ts to each synthetic bar's time so
        # mock fills land in the mock week; order created/submitted times stay on _tick() above.
        self.event_ts = None
        self._ev_t = 0.0

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

    def add_fill_activity(self, order_id, qty, cum_qty, leaves_qty, kind, transaction_time, price="500",
                          side=None, symbol=None):
        """Test hook: one FILL activity row (kind "fill" or "partial_fill") for an order id."""
        row = self.orders.get(order_id) or {}
        act = {"activity_type": "FILL", "id": "mock-act-%04d" % (len(self.activities) + 1),
               "order_id": order_id, "symbol": symbol or row.get("symbol", "SPY"),
               "side": side or row.get("side", "buy"), "qty": str(qty), "cum_qty": str(cum_qty),
               "leaves_qty": str(leaves_qty), "price": str(price), "type": kind,
               "transaction_time": transaction_time, "order_status": "filled" if kind == "fill" else "partially_filled"}
        self.activities.append(act)
        return act

    def _activities(self, q):
        size = int(q.get("page_size", 100))
        if size > 100:
            return 422, {"code": 42210000, "message": "page_size must be 100 or less"}
        rows = sorted(self.activities, key=lambda a: a["transaction_time"], reverse=q.get("direction") != "asc")
        if q.get("after"):
            rows = [a for a in rows if a["transaction_time"] > q["after"]]
        return 200, [dict(a) for a in rows[:size]]

    def set_position(self, qty, avg):
        self.pos_qty, self.pos_avg = (_q(qty) if self.fractional else int(qty)), float(avg)

    # ---- helpers ----
    def _tick(self):
        self._t = max(self._t + 1.0, float(int(time.time())) + 1.0)
        return _iso(self._t)

    def _event_tick(self):
        if not self.event_ts:
            return self._tick()
        try:
            base = float(_cal.timegm(time.strptime(str(self.event_ts)[:19], "%Y-%m-%dT%H:%M:%S")))
        except (TypeError, ValueError):
            return self._tick()
        self._ev_t = max(self._ev_t + 1.0, base)
        return _iso(self._ev_t)

    def _new_row(self, client_order_id, symbol, side, qty, otype, limit, stop):
        self.seq += 1
        oid = "mock-ord-%04d" % self.seq
        ts = self._tick()
        row = {"id": oid, "client_order_id": client_order_id, "symbol": symbol, "asset_class": "us_equity",
               "side": side, "qty": qty if self.fractional else int(qty), "type": otype, "order_type": otype, "time_in_force": "day",
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
        r["qty"] = _qnum(row["qty"])
        r["filled_qty"] = _qnum(row["filled_qty"])
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
            failed = self._read_fail(self.orders_fail, path, {"not": "a list"})
            return failed if failed is not None else self._list(query)
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
        if method == "GET" and path == "/v2/account/activities/FILL":
            failed = self._read_fail(self.activities_fail, path, {"not": "a list"})
            return failed if failed is not None else self._activities(query)
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
        if method == "GET" and path.startswith("/v2/assets/"):
            sym = path[len("/v2/assets/"):]
            return 200, {"symbol": sym, "class": "us_equity", "tradable": True, "status": "active",
                         "fractionable": bool(self.fractionable) if sym == "SPY" else False}
        if method == "GET" and path == "/v2/account":
            failed = self._read_fail(self.account_fail, path, ["not", "an", "account"])
            if failed is not None:
                return failed
            acct = {"id": "mock-account-id-0001", "account_number": MOCK_ACCOUNT, "status": "ACTIVE",
                    "currency": "USD", "buying_power": _num(self.buying_power),
                    "cash": self.cash if isinstance(self.cash, str) else _num(self.cash),
                    "non_marginable_buying_power": self.non_marginable_buying_power
                    if isinstance(self.non_marginable_buying_power, str) else _num(self.non_marginable_buying_power),
                    "pattern_day_trader": False, "trading_blocked": False, "account_blocked": False}
            eq = getattr(self, "equity", None)
            acct["equity"] = (eq if isinstance(eq, str) else _num(eq)) if eq is not None else acct["cash"]
            for k in self.account_omit:
                acct.pop(k, None)
            return 200, acct
        if method == "GET" and path == "/v2/clock":
            return 200, dict(self.clock)
        if method == "GET" and path == "/v2/calendar":
            return 200, [dict(d) for d in self.calendar]
        return 404, {"code": 40400000, "message": "endpoint not found"}

    @staticmethod
    def _read_fail(kind, path, bad_body):
        """A standing read failure for one route: None (works), "outage", "http" or "bad_json"."""
        if kind is None:
            return None
        if kind == "outage":
            raise BrokerOutage("GET trading %s: mock outage" % path)
        if kind == "http":
            return 503, {"code": 50300000, "message": "mock service unavailable"}
        if kind == "bad_json":
            return 200, bad_body
        raise ValueError("unknown read failure kind %r" % (kind,))

    @staticmethod
    def _pos_row(sym, q, avg):
        return {"symbol": sym, "asset_class": "us_equity", "qty": _qnum(abs(q)),
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
        if self.fractional:
            try:
                qty = _q(b.get("qty"))
            except ValueError:
                return 422, {"code": 40010001, "message": "qty is invalid"}
            if qty <= 0:
                return 422, {"code": 40010001, "message": "qty must be > 0"}
            if isinstance(qty, Decimal) and -qty.as_tuple().exponent > 9:
                return 422, {"code": 40010001, "message": "qty must have at most 9 decimal places"}
            if isinstance(qty, Decimal) and not self.fractionable:
                return 422, {"code": 42210000, "message": "asset SPY is not fractionable"}
        else:
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
        if self.fractional and b["side"] == "buy" and float(qty) * ref < self.min_buy_notional:
            return 422, {"code": 40010001, "message": "order notional must be at least $1"}
        if self.fractional and b["side"] == "sell" and self.reject_sell_below is not None \
                and float(qty) * ref < float(self.reject_sell_below):
            return 422, {"code": 40010001, "message": "mock venue: sell notional too small to route"}
        if b["side"] == "buy" and float(qty) * ref > self.buying_power:
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
        row["filled_avg_price"] = round((avg0 * float(cum0) + price * float(q)) / float(cum1), 6)
        row["filled_qty"] = cum1
        row["updated_at"] = self._event_tick()
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
            self.pos_avg = round((self.pos_avg * float(abs(p0)) + price * float(q)) / float(abs(p1)), 6)
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
            cap = None if self.partial_next is None else (
                _q(self.partial_next) if self.fractional else int(self.partial_next))
            q = remaining if cap is None else min(remaining, cap)
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
