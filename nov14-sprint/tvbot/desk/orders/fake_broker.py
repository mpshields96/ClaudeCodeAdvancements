"""In-process fake broker for the paper desk. No network, no account, no real order.

FakeBroker(seed, faults=None)
  submit(client_id, side, qty, limit=None, stop=None, tag=None) -> ack dict
  cancel(client_id) -> dict
  query(client_id) -> order dict or None
  list_orders() -> {"orders": [...], "complete": bool, "total": int}
  positions() -> {symbol: {"qty": int, "avg_price": float}}
  step(bar) -> list of fills made on this bar
  events() -> drained list of ack / fill / canceled / rejected events

Fill rule (applied in step(bar), to orders accepted before that bar):
  - a zero-volume bar never fills anything;
  - market: fills at bar open;
  - buy limit: fills when bar low <= limit, at min(limit, open);
    sell limit: fills when bar high >= limit, at max(limit, open);
  - stop sell: triggers when low <= stop, fills at min(stop, open) (gaps through);
    stop buy: triggers when high >= stop, fills at max(stop, open);
  - fill quantity is capped by bar volume and, under the "partial" fault, by
    max_fill_qty per bar;
  - a reduce_only order never fills past flat: its fill is capped to the opposite
    position, and it does not fill while that is zero (the position never reverses);
  - timing: an order is stamped submit_ts (the latest bar time the broker has seen).
    If a bar opened before submit_ts, its open price is not available to that order:
    a market order fills at the bar close instead, a limit fills at its limit (no gap
    improvement), and a bar that closed before submit_ts fills nothing. Every fill
    carries event_ts (never before submit_ts) and report_ts (when it was reported);
  - costs: half_spread_bps and slip_bps (constructor, SIMULATED test values, default 0)
    move every fill price against the order side. Each fill records base_price and
    price_basis.

snapshot() -> JSON-able dict; FakeBroker.restore(dict) rebuilds the broker exactly
(positions, orders, fills and exec ids, sequence counters, rng state and faults).

Faults (pass a list of names or {name: config}):
  lost_ack              submit creates the order but raises BrokerUncertain (ack lost)
                        config {"count": n} (default 1)
  partial               each bar fills at most max_fill_qty (default half, rounded up)
  cancel_fill_race      cancel() on a working order fills its remainder first at the
                        last bar's close, then rejects the cancel as ALREADY_FILLED
  duplicate_event       every event is emitted twice
  out_of_order          each events() batch is shuffled (seeded)
  margin_reject         submit is rejected INSUFFICIENT_BUYING_POWER; config {"count": n}
                        (default: every submit)
  outage                every API call raises BrokerOutage; config {"calls": n} for the
                        next n calls, or set_outage(True/False) by hand
  late_fill_after_cancel cancel() answers "canceled", then the next bar fills the
                        remainder anyway and reports it after the cancel event
  truncated_listing     list_orders() returns at most config {"limit": n} orders
                        with complete=False

Every event is marked "simulated": true and every fill "mock": true.
"""
import copy
import random

from orders.calendar import parse_ts

NAME = "FakeBroker (offline)"
FAULT_NAMES = ("lost_ack", "partial", "cancel_fill_race", "duplicate_event", "out_of_order",
               "margin_reject", "outage", "late_fill_after_cancel", "truncated_listing")


class BrokerError(Exception):
    pass


class BrokerOutage(BrokerError):
    """The broker could not be reached. Whether a submit landed is unknown."""


class BrokerUncertain(BrokerError):
    """The request may have been applied; the answer was lost."""


def _norm_faults(faults):
    out = {}
    if not faults:
        return out
    if isinstance(faults, dict):
        items = faults.items()
    else:
        items = ((f, True) for f in faults)
    for name, cfg in items:
        if name not in FAULT_NAMES:
            raise ValueError("unknown fault %r" % (name,))
        if cfg is False or cfg is None:
            continue
        out[name] = dict(cfg) if isinstance(cfg, dict) else {}
    return out


class FakeBroker(object):
    name = NAME

    def __init__(self, seed, faults=None, symbol="SYNTH", fee_per_unit=0.0, fee_per_fill=0.0,
                 buying_power=None, half_spread_bps=0.0, slip_bps=0.0):
        for nm, v in (("half_spread_bps", half_spread_bps), ("slip_bps", slip_bps)):
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0 <= v < 10000):
                raise ValueError("%s must be a number in [0, 10000)" % nm)
        self.half_spread_bps = float(half_spread_bps)
        self.slip_bps = float(slip_bps)
        self.seed = seed
        self.rng = random.Random(seed)
        self.symbol = symbol
        self.faults = _norm_faults(faults)
        self.fee_per_unit = float(fee_per_unit)
        self.fee_per_fill = float(fee_per_fill)
        self.buying_power = buying_power
        self._orders = {}          # client_id -> order dict
        self._order_seq = 0
        self._exec_seq = 0
        self._event_queue = []
        self._pos_qty = 0
        self._pos_avg = 0.0
        self._last_bar = None
        self._outage = False
        self._outage_calls = int(self.faults.get("outage", {}).get("calls", 0)) if "outage" in self.faults else 0
        if "outage" in self.faults and not self._outage_calls:
            self._outage = True
        self._lost_ack_left = int(self.faults.get("lost_ack", {}).get("count", 1)) if "lost_ack" in self.faults else 0
        mr = self.faults.get("margin_reject")
        self._margin_left = int(mr.get("count", -1)) if mr is not None else 0
        self.calls = 0

    # ----- persistence -----
    _STATE_FIELDS = ("seed", "symbol", "faults", "fee_per_unit", "fee_per_fill", "buying_power",
                     "half_spread_bps", "slip_bps", "_orders", "_order_seq", "_exec_seq", "_event_queue",
                     "_pos_qty", "_pos_avg", "_last_bar", "_outage", "_outage_calls", "_lost_ack_left",
                     "_margin_left", "calls")

    def snapshot(self):
        """A JSON-able copy of the whole simulated broker, including the rng state."""
        d = {k: copy.deepcopy(getattr(self, k)) for k in self._STATE_FIELDS}
        ver, internal, gauss = self.rng.getstate()
        d["rng_state"] = [ver, list(internal), gauss]
        d["format"] = "fakebroker-snapshot-1"
        d["simulated"] = True
        return d

    @classmethod
    def restore(cls, d):
        if not isinstance(d, dict) or d.get("format") != "fakebroker-snapshot-1":
            raise ValueError("not a FakeBroker snapshot")
        b = cls(d["seed"], faults=None, symbol=d["symbol"], fee_per_unit=d["fee_per_unit"],
                fee_per_fill=d["fee_per_fill"], buying_power=d["buying_power"],
                half_spread_bps=d["half_spread_bps"], slip_bps=d["slip_bps"])
        for k in cls._STATE_FIELDS:
            setattr(b, k, copy.deepcopy(d[k]))
        _norm_faults(b.faults)          # refuses unknown fault names
        ver, internal, gauss = d["rng_state"]
        b.rng.setstate((ver, tuple(internal), gauss))
        return b

    # ----- fault switches (test helpers) -----
    def set_fault(self, name, cfg=True):
        self.faults.update(_norm_faults({name: cfg}))
        if name == "lost_ack":
            self._lost_ack_left = int(self.faults[name].get("count", 1))
        if name == "margin_reject":
            self._margin_left = int(self.faults[name].get("count", -1))

    def clear_fault(self, name):
        self.faults.pop(name, None)
        if name == "outage":
            self._outage = False
            self._outage_calls = 0

    def set_outage(self, down):
        self._outage = bool(down)
        self._outage_calls = 0

    def inject_foreign_order(self, client_id, side, qty, limit=None):
        """Test helper: an order this desk did not send."""
        self._orders[client_id] = self._new_order(client_id, side, qty, limit, None, "foreign")
        return dict(self._orders[client_id])

    def vanish_order(self, client_id):
        """Test helper: the broker forgets an order (it was acknowledged before)."""
        self._orders.pop(client_id, None)

    def force_position(self, qty, avg_price=0.0):
        """Test helper: change the broker-side position behind the desk's back."""
        self._pos_qty = int(qty)
        self._pos_avg = float(avg_price)

    # ----- internals -----
    def _gate(self):
        self.calls += 1
        if self._outage_calls > 0:
            self._outage_calls -= 1
            raise BrokerOutage("simulated outage")
        if self._outage:
            raise BrokerOutage("simulated outage")

    def _ts(self):
        if self._last_bar is not None:
            return self._last_bar.get("delivered_ts") or self._last_bar.get("ts_close")
        return None

    def _emit(self, ev):
        ev = dict(ev)
        ev["simulated"] = True
        ev.setdefault("ts", self._ts())
        self._event_queue.append(ev)

    def _new_order(self, client_id, side, qty, limit, stop, tag, reduce_only=False):
        self._order_seq += 1
        return {
            "client_id": client_id, "order_id": "FB-%d-%d" % (self.seed, self._order_seq), "seq": self._order_seq,
            "symbol": self.symbol, "side": side, "qty": int(qty), "limit": limit, "stop": stop,
            "tag": tag, "reduce_only": bool(reduce_only), "submit_ts": self._ts(),
            "status": "working", "filled_qty": 0, "avg_fill_price": None,
            "fills": [], "late_fill_pending": False, "simulated": True,
        }

    def _reduce_cap(self, order, qty):
        """A reduce-only order may fill only toward flat, never past it."""
        if not order.get("reduce_only"):
            return qty
        room = max(0, self._pos_qty) if order["side"] == "sell" else max(0, -self._pos_qty)
        return min(qty, room)

    def _cost_adjust(self, side, base):
        bps = self.half_spread_bps + self.slip_bps
        adj = base * bps / 10000.0
        return round(base + adj if side == "buy" else base - adj, 6)

    @staticmethod
    def _public(order):
        o = dict(order)
        o["fills"] = [dict(f) for f in order["fills"]]
        o.pop("late_fill_pending", None)
        return o

    def _apply_fill(self, order, qty, base_price, event_ts=None):
        self._exec_seq += 1
        fee = round(self.fee_per_fill + self.fee_per_unit * qty, 6)
        price = self._cost_adjust(order["side"], float(base_price))
        report_ts = self._ts()
        fill = {
            "type": "fill", "exec_id": "EX-%d-%d" % (self.seed, self._exec_seq),
            "client_id": order["client_id"], "order_id": order["order_id"], "side": order["side"],
            "qty": int(qty), "price": price, "fee": fee, "ts": report_ts,
            "event_ts": event_ts or report_ts, "report_ts": report_ts,
            "base_price": float(base_price), "half_spread_bps": self.half_spread_bps, "slip_bps": self.slip_bps,
            "price_basis": "SIMULATED: bar price moved against the order by half_spread_bps + slip_bps",
            "mock": True, "simulated": True,
        }
        prev = order["filled_qty"]
        order["filled_qty"] = prev + qty
        if order["avg_fill_price"] is None:
            order["avg_fill_price"] = float(price)
        else:
            order["avg_fill_price"] = (order["avg_fill_price"] * prev + price * qty) / float(prev + qty)
        order["fills"].append(dict(fill))
        signed = qty if order["side"] == "buy" else -qty
        self._update_position(signed, price)
        if order["filled_qty"] >= order["qty"]:
            order["status"] = "filled"
        self._emit(fill)
        return fill

    def _update_position(self, signed, price):
        q0, a0 = self._pos_qty, self._pos_avg
        q1 = q0 + signed
        if q0 == 0 or (q0 > 0) == (signed > 0):
            self._pos_avg = (a0 * abs(q0) + price * abs(signed)) / float(abs(q1)) if q1 else 0.0
        elif abs(signed) > abs(q0):
            self._pos_avg = float(price)
        elif q1 == 0:
            self._pos_avg = 0.0
        self._pos_qty = q1

    # ----- API -----
    def submit(self, client_id, side, qty, limit=None, stop=None, tag=None, reduce_only=False):
        self._gate()
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ValueError("qty must be a positive int")
        if client_id in self._orders:
            ev = {"type": "rejected", "client_id": client_id, "reason": "DUPLICATE_CLIENT_ORDER_ID"}
            self._emit(ev)
            return {"status": "rejected", "client_id": client_id, "reason": "DUPLICATE_CLIENT_ORDER_ID",
                    "order_id": self._orders[client_id]["order_id"], "simulated": True}
        if self._margin_left != 0:
            if self._margin_left > 0:
                self._margin_left -= 1
            ev = {"type": "rejected", "client_id": client_id, "reason": "INSUFFICIENT_BUYING_POWER"}
            self._emit(ev)
            return {"status": "rejected", "client_id": client_id, "reason": "INSUFFICIENT_BUYING_POWER",
                    "simulated": True}
        order = self._new_order(client_id, side, qty, limit, stop, tag, reduce_only=reduce_only)
        self._orders[client_id] = order
        self._emit({"type": "ack", "client_id": client_id, "order_id": order["order_id"]})
        if self._lost_ack_left > 0:
            self._lost_ack_left -= 1
            # The order exists at the broker; only the answer is lost.
            self._event_queue.pop()
            raise BrokerUncertain("simulated timeout after submit; ack lost")
        return {"status": "accepted", "client_id": client_id, "order_id": order["order_id"], "simulated": True}

    def cancel(self, client_id):
        self._gate()
        order = self._orders.get(client_id)
        if order is None:
            return {"status": "rejected", "client_id": client_id, "reason": "UNKNOWN_ORDER", "simulated": True}
        if order["status"] in ("filled", "canceled", "rejected"):
            reason = "ALREADY_FILLED" if order["status"] == "filled" else "ALREADY_DONE"
            return {"status": "rejected", "client_id": client_id, "reason": reason, "simulated": True}
        remaining = order["qty"] - order["filled_qty"]
        race_qty = self._reduce_cap(order, remaining)
        if "cancel_fill_race" in self.faults and self._last_bar is not None and \
                self._last_bar.get("volume", 0) > 0 and race_qty > 0:
            self._apply_fill(order, race_qty, float(self._last_bar["close"]))
            if order["status"] == "filled":
                return {"status": "rejected", "client_id": client_id, "reason": "ALREADY_FILLED",
                        "simulated": True}
        order["status"] = "canceled"
        self._emit({"type": "canceled", "client_id": client_id, "order_id": order["order_id"],
                    "filled_qty": order["filled_qty"]})
        if "late_fill_after_cancel" in self.faults and remaining > 0:
            order["late_fill_pending"] = True
        return {"status": "canceled", "client_id": client_id, "order_id": order["order_id"], "simulated": True}

    def query(self, client_id):
        self._gate()
        order = self._orders.get(client_id)
        return self._public(order) if order is not None else None

    def list_orders(self):
        self._gate()
        orders = [self._public(o) for o in sorted(self._orders.values(), key=lambda o: o["seq"])]
        total = len(orders)
        limit = self.faults.get("truncated_listing", {}).get("limit") if "truncated_listing" in self.faults else None
        if limit is not None and total > int(limit):
            return {"orders": orders[:int(limit)], "complete": False, "total": total, "simulated": True}
        return {"orders": orders, "complete": True, "total": total, "simulated": True}

    def positions(self):
        self._gate()
        return {self.symbol: {"qty": self._pos_qty, "avg_price": self._pos_avg if self._pos_qty else 0.0,
                              "simulated": True}}

    def events(self):
        self._gate()
        batch, self._event_queue = self._event_queue, []
        if "duplicate_event" in self.faults:
            doubled = []
            for ev in batch:
                doubled.append(ev)
                doubled.append(dict(ev))
            batch = doubled
        if "out_of_order" in self.faults and len(batch) > 1:
            self.rng.shuffle(batch)
        return batch

    def step(self, bar):
        """Advance the simulated market by one bar. Not an API call; outages do not block it."""
        fills = []
        volume = bar.get("volume") or 0
        tradable = volume > 0
        self._last_bar = dict(bar)
        if not tradable:
            return fills
        volume_left = int(volume)
        part = self.faults.get("partial") if "partial" in self.faults else None
        # Every order that exists when step() is called was placed before this bar.
        for order in sorted(self._orders.values(), key=lambda o: o["seq"]):
            if volume_left <= 0:
                break
            late = order.get("late_fill_pending")
            if order["status"] != "working" and not late:
                continue
            timing = self._timing(order, bar)
            if timing is None:
                continue          # the bar closed before this order existed
            opened_before, event_ts = timing
            if opened_before and order["limit"] is None and order["stop"] is None:
                event_ts = bar.get("ts_close") or event_ts    # a late market order fills at the close
            price = self._fill_price(order, bar, opened_before)
            if price is None:
                continue
            remaining = order["qty"] - order["filled_qty"]
            qty = min(remaining, volume_left)
            if part is not None:
                cap = int(part.get("max_fill_qty") or max(1, (order["qty"] + 1) // 2))
                qty = min(qty, cap)
            qty = self._reduce_cap(order, qty)
            if qty <= 0:
                continue
            if late:
                order["late_fill_pending"] = False
                order["status"] = "working"   # reopened by the late fill, then filled
            fills.append(self._apply_fill(order, qty, price, event_ts=event_ts))
            if late and order["status"] != "filled":
                order["status"] = "canceled"
            volume_left -= qty
        return fills

    @staticmethod
    def _parse(ts):
        try:
            return parse_ts(ts) if ts else None
        except (ValueError, TypeError):
            return None

    def _timing(self, order, bar):
        """(opened_before_submit, event_ts), or None when the bar closed before the submit."""
        sub = self._parse(order.get("submit_ts"))
        t_open = self._parse(bar.get("ts_open"))
        t_close = self._parse(bar.get("ts_close"))
        if sub is None or t_open is None:
            return False, bar.get("ts_open") or bar.get("ts_close")
        if t_open >= sub:
            return False, bar.get("ts_open")
        if t_close is not None and t_close < sub:
            return None
        return True, order.get("submit_ts")

    @staticmethod
    def _fill_price(order, bar, opened_before=False):
        o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
        side, limit, stop = order["side"], order["limit"], order["stop"]
        if opened_before:
            # The open was printed before this order existed: no fill at it.
            if stop is None and limit is None:
                return float(bar["close"])
            if stop is None:
                if side == "buy" and l <= limit:
                    return float(limit)
                if side == "sell" and h >= limit:
                    return float(limit)
                return None
        if stop is not None:
            if side == "sell" and l <= stop:
                return min(float(stop), o)
            if side == "buy" and h >= stop:
                return max(float(stop), o)
            return None
        if limit is None:
            return o
        if side == "buy" and l <= limit:
            return min(float(limit), o)
        if side == "sell" and h >= limit:
            return max(float(limit), o)
        return None
