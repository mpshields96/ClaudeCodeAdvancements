"""Order manager and operator controls for the paper desk (offline, simulated).

OrderManager(state_dir, broker, limits)
  submit_intent(intent) -> intent_id
  poll() / on_bar(bar)  drain broker events, book fills, advance Pause / Stop & Close
  reconcile() -> report   runs at startup and again after a reconnect
  pause() / resume() / arm() / disarm() / stop_and_close()
  state() -> dict for session.json

Order path rules (ported from the BTC order-live-r8b design, see BTC_REUSE.md):
  * Every intent is written to state_dir/intents.jsonl (fsync) BEFORE the broker
    sees it. Its id and client order id are derived from decision_id, so a
    repeated decision is a no-op and a retried submit carries the same client id.
  * An uncertain submit (lost ack, timeout, outage) is never blindly resent: the
    manager queries the client id first. Found -> adopt. Not visible (a 404 or
    empty lookup from a broker whose query raises BrokerUncertain, e.g. Alpaca)
    -> held as "uncertain" with NO re-POST: a stable client id alone never
    justifies resending. Only a later lookup that finds the order (adopt)
    resolves it. Cleanly absent on a broker whose query returns None as proof
    (the FakeBroker contract) -> one resend with the same client id.
    Unreachable -> held as "uncertain"; new entries are blocked meanwhile.
  * Fills are booked once per exec_id, whatever order or how often they arrive.
    A fill for an unacknowledged intent counts as its acknowledgment.
  * reconcile() compares the broker's listing, fills and position with the
    booked state. Blocking alarms: ORDER_MISSING (acknowledged order vanished),
    INCOMPLETE_LISTING, POSITION_EXCESS / POSITION_MISMATCH, FOREIGN_ORDER,
    FOREIGN_FILL, FOREIGN_POSITION, FILL_TOTAL_MISMATCH, OVERFILL,
    UNKNOWN_STATUS, BAD_RECORD, BROKER_UNREACHABLE. Any blocking alarm stops
    new entries until a clean reconcile.
  * Risk: per-trade notional, gross exposure and daily loss. Gross counts the
    position plus working entries plus reserved (persisted, unresolved) entries.
    The daily-loss check uses realized + unrealized - fees for the day and, when
    an entry carries a stop, the worst case of every working or reserved stop.
    The limits are TEST VALUES supplied by the caller; this module never changes them.

Controls (state_dir/controls.json, atomic write, also mirrored into intents.jsonl):
  pause()          block new entries, cancel entry remainders, keep protective exits.
  stop_and_close() disable entries, arming and the schedule; cancel entries; read
                   the broker position through reconcile (late and partial fills
                   included); cancel protective exits and close it at market while
                   the calendar says the market is open. When the market is closed
                   the protective exits stay and the close waits for the next open.
                   A failed cancel or an unreachable broker leaves flat_confirmed
                   False and is retried on the next poll. flat_confirmed is set only
                   when the broker reports position 0 and no working desk orders.
                   A fill that lands after that clears flat_confirmed and the close
                   starts again.
  Stop survives restart and session expiry. Session expiry runs stop_and_close.
  arm() is refused while stopped; clear_stop() needs flat_confirmed first.

Every audit row, state field and fill carries "simulated": <self.simulated>, which is True
unless the constructor gets simulated=False (or the broker sets rows_simulated = False, as the
live Alpaca controller does). Fills keep the broker's "mock": true.
"""
import datetime as _dt
import fcntl
import hashlib
import json
import math
import os
from decimal import Decimal

from orders import qty as Q
from orders.calendar import parse_ts, iso
from orders.fake_broker import BrokerError, BrokerOutage, BrokerUncertain
from orders.intake import check_bar, DEFAULT_MAX_AGE_S

# Bar codes after which the bar's prices are not used as the mark.
UNTRUSTED_BAR_CODES = ("BAD_BAR", "OUT_OF_ORDER", "STALE_EXCHANGE_TS", "FUTURE_EXCHANGE_TS",
                       "NOT_CLOSED_AT_RECEIPT", "EXCHANGE_TS_BEFORE_CLOSE")
# Default armed-session expiry: this long before the calendar session ends, so the
# close fills inside the session on hourly bars (one bar of lead plus a margin).
DEFAULT_FLATTEN_LEAD_S = 3900

MODE = "REPLAY (OFFLINE, SIMULATED)"
MIN_FRACTIONAL_BUY = Decimal("1.00")   # venue minimum for a new fractional buy; never applied to reductions
LIMIT_KEYS = ("per_trade_notional", "max_loss_per_trade", "daily_loss", "gross_exposure")
LIMITS_LABEL = "TEST VALUES"
ENTRY = "entry"
EXIT_KINDS = ("exit", "protective", "close")
KINDS = (ENTRY,) + EXIT_KINDS
OPEN_STATUSES = ("pending", "uncertain", "acked")
TERMINAL_STATUSES = ("filled", "canceled", "rejected", "not_placed")
BROKER_STATUSES = ("working", "filled", "canceled", "rejected")
BROKER_DONE = ("filled", "canceled", "rejected")
NOT_FLAT_TEXT = "currently 0, working/unknown, stop unresolved"
AUDIT_KINDS = ("knew", "requested", "acked", "filled", "canceled", "rejected", "alarm", "control")

DEFAULT_CONTROLS = {
    "paused": False, "stopped": False, "flat_confirmed": False, "armed": False,
    "session_id": None, "expires_utc": None, "schedule_enabled": False,
    "stop_reason": None, "stop_utc": None, "close_pending": None, "close_attempts": 0,
    "day_stop": None, "alarms": [], "pending_cancels": [], "last_reconcile_utc": None,
    "broker_confirmed_utc": None, "updated_utc": None, "simulated": True,
}


def stable_intent_id(decision_id):
    digest = hashlib.sha256(("tvbot-desk-intent|%s" % (decision_id,)).encode("utf-8")).hexdigest()
    return "I-" + digest[:20]


def _refuse_link(path):
    if os.path.islink(path):
        raise RuntimeError("refusing symlinked state path: %s" % path)
    if os.path.exists(path) and os.path.isfile(path) and os.lstat(path).st_nlink > 1:
        raise RuntimeError("refusing hard-linked state file: %s" % path)


def _fsync_dir(d):
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_json(path, obj):
    """Temp file, fsync, rename, fsync the directory (BTC ledger-store pattern)."""
    _refuse_link(path)
    d = os.path.dirname(path)
    tmp = os.path.join(d, ".%s.tmp-%d" % (os.path.basename(path), os.getpid()))
    data = (json.dumps(obj, sort_keys=True, indent=2, default=Q.json_default) + "\n").encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(d)


def _record_hash(rec):
    body = dict(rec)
    body.pop("sha", None)
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=Q.json_default).encode("utf-8")).hexdigest()[:16]



def _dec(x):
    """Lexical Decimal of a number (shortest repr), for cap comparisons without float drift."""
    return Decimal(repr(float(x)))

class JsonlLog(object):
    """Append-only JSONL with seq + per-record hash; each append is fsynced."""

    def __init__(self, path):
        self.path = path
        _refuse_link(path)
        self.seq = 0

    def append(self, rec):
        _refuse_link(self.path)
        self.seq += 1
        rec = dict(rec)
        rec["seq"] = self.seq
        rec["sha"] = _record_hash(rec)
        line = json.dumps(rec, sort_keys=True, default=Q.json_default) + "\n"
        with open(self.path, "a") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return rec

    @staticmethod
    def _parse(raw):
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if isinstance(rec, dict) and rec.get("sha") == _record_hash(rec):
            return rec
        return None

    def read(self, repair=False):
        """(records, problems). Bytes after the last newline are a torn write: the
        record was being persisted before dispatch, so nothing was sent for it.
        With repair=True they are moved to <file>.torn and the file is truncated
        so later appends stay clean. A bad complete line is a BAD_RECORD problem."""
        records, problems = [], []
        if not os.path.exists(self.path):
            return records, problems
        with open(self.path, "rb") as fh:
            raw = fh.read()
        body, sep, tail = raw.rpartition(b"\n")
        lines = body.split(b"\n") if (body or sep) else []
        for i, line in enumerate(lines):
            rec = self._parse(line)
            if rec is None:
                problems.append({"line": i + 1, "torn_tail": False})
                continue
            records.append(rec)
            self.seq = max(self.seq, int(rec.get("seq", 0)))
        if tail:
            rec = self._parse(tail)
            if rec is not None:
                records.append(rec)
                self.seq = max(self.seq, int(rec.get("seq", 0)))
                if repair:
                    with open(self.path, "ab") as fh:
                        fh.write(b"\n")
                        fh.flush()
                        os.fsync(fh.fileno())
            else:
                problems.append({"line": len(lines) + 1, "torn_tail": True})
                if repair:
                    with open(self.path + ".torn", "ab") as fh:
                        fh.write(tail + b"\n")
                    os.truncate(self.path, len(body) + len(sep))
        return records, problems


class OrderManager(object):

    def __init__(self, state_dir, broker, limits, symbol=None, calendar=None, clock=None,
                 strategy=None, data_label=None, multiplier=1.0, reconcile_on_start=True,
                 flatten_lead_s=DEFAULT_FLATTEN_LEAD_S, bar_max_age_s=DEFAULT_MAX_AGE_S, simulated=None):
        # The value every row, state field and fill records as "simulated". Paper and mock keep
        # True; only a caller (or broker) that says False explicitly gets False.
        if simulated is None:
            simulated = getattr(broker, "rows_simulated", True)
        if not isinstance(simulated, bool):
            raise ValueError("simulated must be True or False")
        self.simulated = simulated
        # Fractional mode: only a connected broker that says so (the Alpaca broker built with
        # fractional=True). The offline fake broker stays whole-share only.
        self.fractional = getattr(broker, "fractional", False) is True
        self.limits = self._check_limits(limits)
        # Bar freshness for routing. Offline keeps intake's 5 s default; the Alpaca session binds its
        # advertised window (900 s) so an ordinary manual Check inside that window can still route.
        self.bar_max_age_s = float(bar_max_age_s)
        self.limits_label = (limits.get("label") if isinstance(limits, dict) else None) or LIMITS_LABEL
        self.broker = broker
        self.symbol = symbol or getattr(broker, "symbol", "SYNTH")
        self.calendar = calendar
        # Optional callable -> True/False/None: the venue's own market-open flag. False holds Stop &
        # Close exactly as a closed calendar does; None (unreadable) leaves the calendar to decide.
        self.venue_open = None
        self._clock = clock
        self.strategy = strategy
        self.data_label = data_label
        self.multiplier = float(multiplier)
        self.flatten_lead_s = float(flatten_lead_s)
        self._broker_position = None
        self._prev_bar = None
        self._bar_status = None
        self.state_dir = os.path.abspath(state_dir)
        if os.path.islink(self.state_dir):
            raise RuntimeError("refusing symlinked state_dir")
        os.makedirs(self.state_dir, exist_ok=True)
        self._lock_fh = None
        self._take_lock()
        self.audit_log = JsonlLog(os.path.join(self.state_dir, "audit.jsonl"))
        self.audit_log.read(repair=True)
        self.intent_log = JsonlLog(os.path.join(self.state_dir, "intents.jsonl"))
        self.controls_path = os.path.join(self.state_dir, "controls.json")
        self.connected = None
        self.mark = None
        self._sim_now = None
        self._last_bar_ts = None
        self._last_report = None
        self._reset_book()
        self.controls = dict(DEFAULT_CONTROLS)
        self._load()
        self.controls["simulated"] = self.simulated
        self._audit("control", action="startup", controls=self._controls_view())
        if reconcile_on_start:
            self.reconcile(reason="startup")

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _check_limits(limits):
        if not isinstance(limits, dict):
            raise ValueError("limits must be a dict with %s" % (LIMIT_KEYS,))
        out = {}
        for k in LIMIT_KEYS:
            v = limits.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0:
                raise ValueError("limit %s must be a positive number (TEST VALUES), got %r" % (k, v))
            out[k] = float(v)
        # Optional: at most this many new entry attempts per trading day. Absent = no daily count
        # (whole-share behaviour unchanged). Never defaulted.
        mx = limits.get("max_daily_entries")
        if mx is not None:
            if not isinstance(mx, int) or isinstance(mx, bool) or mx <= 0:
                raise ValueError("limit max_daily_entries must be a positive whole number, got %r" % (mx,))
            out["max_daily_entries"] = mx
        return out

    def _take_lock(self):
        path = os.path.join(self.state_dir, ".orders.lock")
        _refuse_link(path)
        fh = open(path, "a")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise RuntimeError("state_dir is in use by another OrderManager: %s" % self.state_dir)
        self._lock_fh = fh

    def close(self):
        """Release the state_dir lock. Writes nothing (a restart reads the logs)."""
        if self._lock_fh is not None:
            try:
                fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._lock_fh.close()
                self._lock_fh = None

    def _reset_book(self):
        self.intents = {}
        self.by_client = {}
        self.booked = set()
        self.fills = []
        self.pos_qty = 0
        self.pos_avg = 0.0
        self.realized = 0.0
        self.fees = 0.0
        self.by_day = {}

    def _load(self):
        records, problems = self.intent_log.read(repair=True)
        last_control = None
        for rec in records:
            kind = rec.get("rec")
            if kind == "intent":
                it = dict(rec)
                try:
                    it["qty"] = Q.parse(it.get("qty"))
                except Q.QtyError:
                    pass
                it.setdefault("filled_qty", 0)
                it["fill_ids"] = []
                it["fees"] = 0.0
                self.intents[it["intent_id"]] = it
                self.by_client[it["client_id"]] = it["intent_id"]
            elif kind == "status" and rec.get("intent_id") in self.intents:
                it = self.intents[rec["intent_id"]]
                for k, v in rec.items():
                    if k not in ("rec", "seq", "sha", "ts", "intent_id", "simulated"):
                        it[k] = v
            elif kind == "fill" and rec.get("intent_id") in self.intents:
                self._apply_fill_rec(rec)
            elif kind == "control":
                last_control = rec.get("controls")
        controls_problem = None
        if os.path.exists(self.controls_path):
            try:
                _refuse_link(self.controls_path)
                with open(self.controls_path) as fh:
                    loaded = json.load(fh)
                if not isinstance(loaded, dict):
                    raise ValueError("controls.json is not an object")
                self.controls.update(loaded)
            except (ValueError, OSError, RuntimeError) as exc:
                controls_problem = str(exc)
        elif last_control:
            # controls.json missing but the log has the last control snapshot.
            self.controls.update(last_control)
        # Load alarms describe this load only; a previous run's are recomputed now.
        self.controls["alarms"] = [a for a in (self.controls.get("alarms") or [])
                                   if isinstance(a, dict) and a.get("source") != "load"]
        if controls_problem is not None:
            # Fail closed: an unreadable control file is treated as a stop.
            self.controls.update({"paused": True, "stopped": True, "armed": False,
                                  "schedule_enabled": False, "flat_confirmed": False,
                                  "stop_reason": "CONTROLS_UNREADABLE"})
            self._add_alarm("CONTROLS_UNREADABLE", controls_problem, source="load")
        bad = [p for p in problems if not p["torn_tail"]]
        if bad:
            self._add_alarm("BAD_RECORD", "intents.jsonl has %d unreadable record(s)" % len(bad), source="load")
        if problems:
            self._audit("alarm", code="LOG_PROBLEM", problems=problems, blocking=bool(bad))

    # ------------------------------------------------------------------ clock and logs
    def now(self):
        if self._clock is not None:
            return parse_ts(self._clock())
        if self._sim_now is not None:
            return self._sim_now
        return _dt.datetime.now(_dt.timezone.utc)

    def _audit(self, _audit_kind, **fields):
        if _audit_kind not in AUDIT_KINDS:
            raise ValueError("audit kind %r" % (_audit_kind,))
        if "kind" in fields:   # an order's kind never overwrites the audit kind
            fields["order_kind"] = fields.pop("kind")
        rec = {"ts": iso(self.now()), "kind": _audit_kind, "simulated": self.simulated}
        rec.update(fields)
        return self.audit_log.append(rec)

    def _log(self, rec):
        rec = dict(rec)
        rec["ts"] = iso(self.now())
        rec["simulated"] = self.simulated
        return self.intent_log.append(rec)

    def _save_controls(self, **changes):
        self.controls.update(changes)
        self.controls["updated_utc"] = iso(self.now())
        self.controls["simulated"] = self.simulated
        atomic_write_json(self.controls_path, self.controls)
        self._log({"rec": "control", "controls": self._controls_snapshot()})

    def _controls_snapshot(self):
        keep = ("paused", "stopped", "flat_confirmed", "armed", "session_id", "expires_utc",
                "schedule_enabled", "stop_reason", "stop_utc", "day_stop")
        return dict((k, self.controls.get(k)) for k in keep)

    def _controls_view(self):
        return {"paused": bool(self.controls["paused"]), "stopped": bool(self.controls["stopped"]),
                "flat_confirmed": bool(self.controls["flat_confirmed"])}

    # ------------------------------------------------------------------ alarms
    def _add_alarm(self, code, detail, source="events", blocking=True, persist=False):
        alarm = {"code": code, "detail": detail, "blocking": bool(blocking), "source": source,
                 "ts": iso(self.now()), "simulated": self.simulated}
        alarms = [a for a in self.controls.get("alarms", []) if not (a["code"] == code and a["detail"] == detail)]
        alarms.append(alarm)
        self.controls["alarms"] = alarms
        if persist:
            self._save_controls()
        return alarm

    def blocking_alarms(self):
        return [a for a in self.controls.get("alarms", []) if a.get("blocking")]

    def _alarm(self, code, detail, source="events", blocking=True):
        alarm = self._add_alarm(code, detail, source=source, blocking=blocking, persist=True)
        self._audit("alarm", code=code, detail=detail, blocking=blocking, source=source)
        return alarm

    # ------------------------------------------------------------------ broker calls
    def _call(self, name, *args, **kwargs):
        try:
            result = getattr(self.broker, name)(*args, **kwargs)
        except BrokerOutage:
            if self.connected is not False:
                self._audit("alarm", code="BROKER_UNREACHABLE", detail="%s failed" % name, blocking=True)
            self.connected = False
            raise
        except BrokerUncertain:
            self.connected = True
            raise
        self.connected = True
        self.controls["broker_confirmed_utc"] = iso(self.now())
        return result

    def _resync(self):
        """After an outage, reconcile before doing anything else."""
        if self.connected is False:
            self.reconcile(reason="reconnect")

    # ------------------------------------------------------------------ book
    def _day_key(self, ts):
        try:
            d = parse_ts(ts) if ts is not None else self.now()
        except (ValueError, TypeError):
            d = self.now()
        if self.calendar is not None:
            return self.calendar.local_date(d).isoformat()
        return d.date().isoformat()

    def _apply_fill_rec(self, rec):
        it = self.intents[rec["intent_id"]]
        exec_id = rec["exec_id"]
        if exec_id in self.booked:
            return False
        self.booked.add(exec_id)
        qty, price, fee = Q.parse(rec["qty"]), float(rec["price"]), float(rec.get("fee") or 0.0)
        it["filled_qty"] = Q.norm(Q.dec(it.get("filled_qty", 0)) + Q.dec(qty))
        it["fill_ids"].append(exec_id)
        it["fees"] = it.get("fees", 0.0) + fee
        self.fills.append(dict(rec))
        signed = qty if it["side"] == "buy" else -qty
        q0, a0 = self.pos_qty, self.pos_avg
        realized = 0.0
        if q0 == 0 or (q0 > 0) == (signed > 0):
            q1 = Q.norm(Q.dec(q0) + Q.dec(signed))
            self.pos_avg = (a0 * float(abs(q0)) + price * float(abs(signed))) / float(abs(q1))
            self.pos_qty = q1
        else:
            closing = float(min(abs(Q.dec(q0)), abs(Q.dec(signed))))
            realized = (price - a0) * closing * (1 if q0 > 0 else -1) * self.multiplier
            q1 = Q.norm(Q.dec(q0) + Q.dec(signed))
            if q1 == 0:
                self.pos_avg = 0.0
            elif (q1 > 0) != (q0 > 0):
                self.pos_avg = price
            self.pos_qty = q1
        self.realized += realized
        self.fees += fee
        day = self.by_day.setdefault(self._day_key(rec.get("fill_ts") or rec.get("ts")),
                                     {"realized": 0.0, "fees": 0.0})
        day["realized"] += realized
        day["fees"] += fee
        return True

    def _book_fill(self, iid, fill, how="event"):
        it = self.intents[iid]
        exec_id = fill.get("exec_id")
        if not exec_id:
            self._alarm("BAD_RECORD", "fill without exec_id for %s" % iid)
            return False
        if exec_id in self.booked:
            return False
        if fill.get("side") and fill["side"] != it["side"]:
            self._alarm("BAD_RECORD", "fill %s side %s does not match intent side %s" % (exec_id, fill["side"], it["side"]))
            return False
        if it["status"] in ("pending", "uncertain"):
            self._set_status(iid, "acked", order_id=fill.get("order_id"), how="implied by fill")
            self._audit("acked", intent_id=iid, client_id=it["client_id"], order_id=fill.get("order_id"),
                        how="implied by fill")
        rec = {"rec": "fill", "intent_id": iid, "client_id": it["client_id"], "exec_id": exec_id,
               "order_id": fill.get("order_id"), "qty": self._fill_qty(fill["qty"]), "price": float(fill["price"]),
               "fee": float(fill.get("fee") or 0.0), "fill_ts": fill.get("ts"), "mock": bool(fill.get("mock", True))}
        rec = self._log(rec)
        self._apply_fill_rec(rec)
        late = it["status"] == "canceled"
        self._audit("filled", intent_id=iid, client_id=it["client_id"], exec_id=exec_id, qty=rec["qty"],
                    price=rec["price"], fee=rec["fee"], how=how, late_after_cancel=late,
                    position_qty=self.pos_qty, mock=rec["mock"])
        if it["filled_qty"] > it["qty"]:
            self._alarm("OVERFILL", "%s filled %s of %s" % (iid, Q.text(it["filled_qty"]), Q.text(it["qty"])))
        elif it["filled_qty"] == it["qty"] and it["status"] != "filled":
            self._set_status(iid, "filled")
        if self.controls.get("flat_confirmed") and self.pos_qty != 0:
            self._save_controls(flat_confirmed=False)
            self._alarm("FILL_AFTER_FLAT", "%s filled after flat was confirmed; closing again" % exec_id,
                        blocking=False)
        return True

    def _set_status(self, iid, status, **extra):
        it = self.intents[iid]
        it["status"] = status
        it.update(extra)
        rec = {"rec": "status", "intent_id": iid, "status": status}
        rec.update(extra)
        self._log(rec)

    # ------------------------------------------------------------------ risk
    def _price_of(self, it):
        for k in ("limit", "stop", "ref_price"):
            v = it.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                return float(v)
        return self.mark

    def _remaining(self, it):
        return Q.norm(max(Decimal(0), Q.dec(it["qty"]) - Q.dec(it.get("filled_qty", 0))))

    def _fill_qty(self, v):
        """A fill quantity: int() exactly as always on a whole-share desk, exact on a fractional one."""
        return Q.parse(v) if self.fractional else int(v)

    def _bq(self, v):
        """A broker-reported quantity (order filled_qty, position qty), same rule as _fill_qty."""
        if not self.fractional:
            return int(v or 0)
        return Q.parse_signed(v if v not in (None, "") else 0)

    def _live(self, kinds=None):
        out = []
        for it in self.intents.values():
            if it["status"] in OPEN_STATUSES and self._remaining(it) > 0:
                if kinds is None or it["kind"] in kinds:
                    out.append(it)
        return out

    def gross_exposure(self):
        """Position + working entries + reserved (persisted, unresolved) entries, in notional."""
        return float(self._gross_dec())

    def _gross_dec(self):
        """gross_exposure in lexical Decimal, so a cap check accepts exact equality."""
        mark = self.mark if self.mark is not None else (self.pos_avg or 0.0)
        mult = _dec(self.multiplier)
        gross = abs(Q.dec(self.pos_qty)) * _dec(mark) * mult
        for it in self._live([ENTRY]):
            price = self._price_of(it) or 0.0
            gross += Q.dec(self._remaining(it)) * _dec(price) * mult
        return gross

    def unrealized(self):
        if self.pos_qty == 0 or self.mark is None:
            return 0.0
        return (self.mark - self.pos_avg) * float(self.pos_qty) * self.multiplier

    def day_pnl(self):
        day = self.by_day.get(self._day_key(None), {"realized": 0.0, "fees": 0.0})
        return day["realized"] + self.unrealized() - day["fees"]

    @staticmethod
    def _num(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0:
            return float(v)
        return None

    def _entry_points(self, it):
        """(intended_entry, invalidation) for an entry. invalidation falls back to stop."""
        ie = None
        for k in ("intended_entry", "limit", "ref_price"):
            ie = self._num(it.get(k))
            if ie is not None:
                break
        if ie is None:
            ie = self.mark
        inv = self._num(it.get("invalidation"))
        if inv is None:
            inv = self._num(it.get("stop"))
        return ie, inv

    def _entry_price_risk(self, it, qty=None):
        """Price risk to the stop only: qty x |intended_entry - invalidation| x multiplier.

        This is what max_loss_per_trade caps (operator rule: the per-trade
        limit is planned price loss to the stop; fees are budgeted separately)."""
        ie, inv = self._entry_points(it)
        if ie is None or inv is None:
            return None
        q = self._remaining(it) if qty is None else qty
        return float(q) * abs(ie - inv) * self.multiplier

    def _entry_max_loss(self, it, qty=None):
        """Worst-case dollars for the daily cap: price risk to the stop plus the estimated round-trip cost."""
        r = self._entry_price_risk(it, qty=qty)
        if r is None:
            return None
        return r + float(it.get("est_cost") or 0.0)

    def _open_fee_reserve(self):
        """Estimated fees still to come on the open position's already-filled entries.

        Walks the fills since the position was last flat. For each entry intent that is no longer
        working (a working entry's full est_cost is already in _stop_risk), it reserves that entry's
        est_cost, less the fees already booked since flat on those entries and on the closing side.
        Fees already booked are in day_pnl, so they are not counted twice."""
        if self.pos_qty == 0:
            return 0.0
        live = set(id(it) for it in self._live([ENTRY]))
        pos = Decimal(0)
        est, booked, seen = 0.0, 0.0, set()
        for f in self.fills:
            it = self.intents.get(f.get("intent_id"))
            if it is None:
                continue
            q = Q.dec(f["qty"])
            pos = pos + (q if it["side"] == "buy" else -q)
            if id(it) not in live:
                booked += float(f.get("fee") or 0.0)
                if it.get("kind") == ENTRY and f["intent_id"] not in seen:
                    seen.add(f["intent_id"])
                    est += float(it.get("est_cost") or 0.0)
            if pos == 0:
                est, booked, seen = 0.0, 0.0, set()
        return max(0.0, est - booked)

    def _stop_risk(self):
        """Worst-case loss to the stops of the position and of working/reserved entries."""
        risk = 0.0
        for it in self._live(["protective"]):
            if it.get("stop") is not None and self.mark is not None:
                risk += float(self._remaining(it)) * max(0.0, abs(self.mark - float(it["stop"]))) * self.multiplier
        for it in self._live([ENTRY]):
            r = self._entry_max_loss(it)
            if r is not None:
                risk += r
        return risk

    def _expired(self):
        exp = self.controls.get("expires_utc")
        if not exp:
            return False
        try:
            return self.now() >= parse_ts(exp)
        except (ValueError, TypeError):
            return True

    def entry_block_reason(self):
        c = self.controls
        if c.get("stopped"):
            return "STOPPED"
        if c.get("paused"):
            return "PAUSED"
        if not c.get("armed"):
            return "NOT_ARMED"
        if self._expired():
            return "SESSION_EXPIRED"
        if self.blocking_alarms():
            return "BLOCKING_ALARM"
        if self.connected is False:
            return "BROKER_DISCONNECTED"
        if self._bar_status is not None:
            return "BAR_" + self._bar_status
        if any(it["status"] in ("pending", "uncertain") for it in self.intents.values()):
            return "UNRESOLVED_SUBMIT"
        ds = c.get("day_stop")
        if ds and ds.get("day") == self._day_key(None):
            return "DAILY_LOSS_STOP"
        if self.calendar is not None and not self.calendar.is_open(self.now()):
            return "MARKET_CLOSED"
        return None

    def _check_entry_risk(self, it):
        price = self._price_of(it)
        if price is None:
            return "NO_PRICE"
        ie, inv = self._entry_points(it)
        if inv is None:
            return "NO_STOP"
        if ie is None or (it["side"] == "buy" and inv >= ie) or (it["side"] == "sell" and inv <= ie):
            return "BAD_STOP"     # invalidation must sit on the losing side of the entry
        cost = it.get("est_cost")
        if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool)
                                 or not math.isfinite(cost) or cost < 0):
            return "BAD_COST"
        notional_d = Q.dec(it["qty"]) * _dec(price) * _dec(self.multiplier)
        if notional_d > _dec(self.limits["per_trade_notional"]):
            return "NOTIONAL"     # lexical Decimal: exactly at the cap passes, any true excess is refused
        if self._entry_price_risk(it, qty=it["qty"]) > self.limits["max_loss_per_trade"]:
            return "MAX_LOSS"     # price risk to the stop only; fees count in the daily check below
        new_risk = self._entry_max_loss(it, qty=it["qty"])
        if self._gross_dec() + notional_d > _dec(self.limits["gross_exposure"]):
            return "RISK_GROSS"
        loss = max(0.0, -self.day_pnl())
        if loss >= self.limits["daily_loss"]:
            self._save_controls(day_stop={"day": self._day_key(None), "reason": "DAILY_LOSS",
                                          "loss": round(loss, 6)})
            self._audit("control", action="day_stop", loss=loss, limit=self.limits["daily_loss"])
            return "DAILY_LOSS_STOP"
        # daily worst case = realized/unrealized loss net of booked fees + stop risk of the position and
        # of working entries (with their est. fees) + fees still to come on the open position + this entry
        if loss + self._stop_risk() + self._open_fee_reserve() + new_risk > self.limits["daily_loss"]:
            return "RISK_DAILY_LOSS_WORST_CASE"
        return None

    def _today_start_utc(self):
        """Start of the current trading day (local midnight of the calendar's zone) in UTC."""
        now = self.now()
        if self.calendar is not None:
            day = self.calendar.local_date(now)
            return _dt.datetime(day.year, day.month, day.day, tzinfo=self.calendar.tz).astimezone(_dt.timezone.utc)
        return _dt.datetime(now.year, now.month, now.day, tzinfo=_dt.timezone.utc)

    def _entries_today(self):
        """Client ids of this book's entry attempts persisted with today's entry_attempt_day."""
        today = self._day_key(None)
        return set(it["client_id"] for it in self.intents.values()
                   if it.get("kind") == ENTRY and it.get("entry_attempt_day") == today)

    def _check_daily_entries(self):
        """DAILY_ENTRY_LIMIT when today's entry attempts reach max_daily_entries.

        Counts the union of this book's persisted attempts and, on a connected broker, every buy of
        this symbol the account shows since local midnight in any status. A second kit copy or a
        fresh state directory on the same day therefore still sees the day's entry. If the broker
        count cannot be read completely, the entry is held (ENTRY_COUNT_UNVERIFIED). Only the entry
        branch calls this: protectives, exits and Stop & Close never read the counter."""
        mx = self.limits.get("max_daily_entries")
        if mx is None:
            return None
        used = self._entries_today()
        fn = getattr(self.broker, "entry_buys_since", None)
        if fn is None:
            if self.fractional:
                return "ENTRY_COUNT_UNVERIFIED"
        else:
            start = self._today_start_utc()
            try:
                res = fn(iso(start))
                if not isinstance(res, dict) or res.get("complete") is not True \
                        or not isinstance(res.get("orders"), list):
                    raise ValueError("incomplete")
                if res.get("foreign_working_buy"):
                    return "EXTERNAL_WORKING_BUY"
                for o in res["orders"]:
                    if not isinstance(o, dict) or o.get("side") != "buy":
                        continue
                    if o.get("symbol") not in (None, self.symbol):
                        continue
                    ts = o.get("submitted_at")
                    try:
                        if ts is not None and parse_ts(ts) < start:
                            continue
                    except (ValueError, TypeError):
                        pass                         # unreadable time: counted (conservative)
                    used.add(o.get("client_id") or ("broker:%d" % len(used)))
            except Exception as exc:
                self._audit("control", action="entry_count_unverified", error=type(exc).__name__)
                return "ENTRY_COUNT_UNVERIFIED"
        self._counted_entry_ids = used
        if len(used) >= mx:
            return "DAILY_ENTRY_LIMIT"
        return None

    def _check_frac_entry(self, it):
        """Fractional mode only: the $1.00 minimum for a new buy and actual non-margin cash.

        Never upsizes. Runs before entry_attempt_day is written, so these skips do not use the day's
        entry. Values are not logged."""
        if it["side"] != "buy":
            return "FRACTIONAL_LONG_ONLY"
        price = self._price_of(it)
        if price is None:
            return "NO_PRICE"
        notional = Q.dec(it["qty"]) * _dec(price) * _dec(self.multiplier)
        if notional < MIN_FRACTIONAL_BUY:
            return "BELOW_MIN_NOTIONAL"
        fn = getattr(self.broker, "funding", None)
        if fn is None:
            return "CASH_UNAVAILABLE"
        try:
            f = fn()
            vals = []
            for k in (("cash", "non_marginable_buying_power", "buying_power") if "buying_power" in f else ("cash", "non_marginable_buying_power")):
                v = Decimal(str(f[k]).strip())
                if not v.is_finite() or v < 0:
                    raise ValueError(k)
                vals.append(v)
        except Exception:
            return "CASH_UNAVAILABLE"
        available = min(vals)
        working = Decimal(0)
        for w in self._live([ENTRY]):
            if w["side"] == "buy":
                working += Q.dec(self._remaining(w)) * _dec(self._price_of(w) or 0.0) * _dec(self.multiplier)
        if notional + working > available:
            return "INSUFFICIENT_CASH"
        return None

    def _check_exit(self, it):
        if self.connected is False:
            return "BROKER_DISCONNECTED"
        if self.pos_qty == 0:
            return "EXIT_NOT_REDUCING"
        reducing_side = "sell" if self.pos_qty > 0 else "buy"
        if it["side"] != reducing_side:
            return "EXIT_NOT_REDUCING"
        bucket = ["protective"] if it["kind"] == "protective" else ["exit", "close"]
        working = sum(self._remaining(x) for x in self._live(bucket) if x["side"] == reducing_side)
        if working + it["qty"] > abs(self.pos_qty):
            return "EXIT_EXCEEDS_POSITION"
        return None

    # ------------------------------------------------------------------ submit
    def submit_intent(self, intent):
        """Persist, gate and dispatch one intent. Returns its stable intent_id."""
        self._resync()
        if not isinstance(intent, dict) or not intent.get("decision_id"):
            raise ValueError("intent needs a decision_id")
        iid = stable_intent_id(intent["decision_id"])
        if iid in self.intents:
            self._audit("knew", intent_id=iid, decision_id=intent["decision_id"], note="duplicate decision ignored")
            return iid
        kind = intent.get("kind", ENTRY)
        side = intent.get("side")
        qty = intent.get("qty")
        if self.fractional and kind in KINDS and side in ("buy", "sell"):
            try:
                qty = Q.parse(qty)
            except Q.QtyError as exc:
                raise ValueError("bad intent: kind %r side %r qty %r (%s)" % (kind, side, qty, exc))
        elif kind not in KINDS or side not in ("buy", "sell") or not isinstance(qty, int) \
                or isinstance(qty, bool) or qty <= 0:
            frac = (isinstance(qty, (float, Decimal)) and not isinstance(qty, bool) and qty > 0
                    and qty != int(qty))
            raise ValueError("bad intent: kind %r side %r qty %r%s" % (
                kind, side, qty, " (FRACTIONAL_NOT_ENABLED on this desk)" if frac else ""))
        return self._submit(iid, intent, kind, side, qty, internal=False)

    def _submit(self, iid, intent, kind, side, qty, internal):
        it = {
            "rec": "intent", "intent_id": iid, "decision_id": intent["decision_id"],
            "client_id": iid, "kind": kind, "side": side, "qty": qty,
            "limit": intent.get("limit"), "stop": intent.get("stop"), "ref_price": intent.get("ref_price"),
            "signal_ts": intent.get("signal_ts"), "status": "pending", "retries": 0,
            "session_id": self.controls.get("session_id"),
            "intended_entry": intent.get("intended_entry"), "invalidation": intent.get("invalidation"),
            "est_cost": intent.get("est_cost"), "symbol": intent.get("symbol") or self.symbol,
            "reduce_only": kind in EXIT_KINDS,
        }
        self._audit("knew", intent_id=iid, decision_id=it["decision_id"], order_kind=kind, side=side, qty=qty,
                    limit=it["limit"], stop=it["stop"], ref_price=it["ref_price"], mark=self.mark,
                    intended_entry=it["intended_entry"], invalidation=it["invalidation"],
                    est_cost=it["est_cost"], reduce_only=it["reduce_only"],
                    bar_ts=self._last_bar_ts, position_qty=self.pos_qty,
                    gross_including_working=self.gross_exposure(), internal=internal)
        reason = None
        if not internal:
            if self.controls.get("stopped"):
                reason = "STOPPED"   # Stop & Close owns the position until clear_stop()
            elif it["symbol"] != self.symbol:
                reason = "WRONG_SYMBOL"
            elif kind == ENTRY:
                reason = self.entry_block_reason() or self._check_entry_risk(it)
                if reason is None:
                    reason = self._check_daily_entries()
                if reason is None and self.fractional:
                    reason = self._check_frac_entry(it)
                if reason is None and self.fractional and self.limits.get("max_daily_entries") is not None:
                    reserve = getattr(self.broker, "reserve_entry_attempt", None)
                    if reserve is not None:
                        try:
                            reason = reserve(self._day_key(None), it["client_id"],
                                             self.limits["max_daily_entries"], self._counted_entry_ids)
                        except Exception:
                            reason = "ENTRY_COUNT_UNVERIFIED"
                if reason is None:
                    # Persisted with the intent below, before the first possible send: from here the
                    # attempt counts whatever the broker answers (rejected, uncertain, working, filled).
                    it["entry_attempt_day"] = self._day_key(None)
            else:
                reason = self._check_exit(it)
        if reason:
            it["status"] = "rejected"
            it["reason"] = reason
        # Persist BEFORE dispatch (or record the refusal).
        self._log(it)
        mem = dict(it)
        mem["filled_qty"] = 0
        mem["fill_ids"] = []
        mem["fees"] = 0.0
        self.intents[iid] = mem
        self.by_client[iid] = iid
        if reason:
            self._audit("rejected", intent_id=iid, reason=reason, by="desk")
            return iid
        self._audit("requested", intent_id=iid, client_id=iid, side=side, qty=qty, limit=it["limit"],
                    stop=it["stop"], order_kind=kind)
        self._dispatch(iid)
        return iid

    def _dispatch(self, iid):
        it = self.intents[iid]
        try:
            ack = self._call("submit", it["client_id"], it["side"], it["qty"], limit=it["limit"],
                             stop=it["stop"], tag=it["kind"], reduce_only=bool(it.get("reduce_only")))
        except BrokerUncertain as exc:
            self._set_status(iid, "uncertain", reason=str(exc))
            self._audit("alarm", code="SUBMIT_UNCERTAIN", intent_id=iid, detail=str(exc), blocking=False)
            self._resolve_uncertain(iid, allow_retry=True)
            return
        except BrokerOutage as exc:
            self._set_status(iid, "uncertain", reason="outage during submit: %s" % exc)
            return
        self._on_submit_result(iid, ack)

    def _on_submit_result(self, iid, ack):
        status = ack.get("status")
        if status == "accepted":
            self._set_status(iid, "acked", order_id=ack.get("order_id"))
            self._audit("acked", intent_id=iid, client_id=ack.get("client_id"), order_id=ack.get("order_id"),
                        how="submit")
        elif status == "rejected" and ack.get("reason") == "DUPLICATE_CLIENT_ORDER_ID":
            # An earlier attempt landed. Adopt it rather than sending another.
            self._resolve_uncertain(iid, allow_retry=False)
        else:
            self._set_status(iid, "rejected", reason=ack.get("reason"))
            self._audit("rejected", intent_id=iid, reason=ack.get("reason"), by="broker")

    def _resolve_uncertain(self, iid, allow_retry):
        """Query before any retry. Returns True when the intent is no longer uncertain."""
        it = self.intents[iid]
        unseen = False
        try:
            order = self._call("query", it["client_id"])
        except BrokerUncertain:
            order, unseen = None, True      # not visible yet: never proof that it was not placed
        except BrokerError:
            return False
        if order is not None:
            self._adopt(iid, order, how="query")
            return True
        if unseen:
            # Not visible is never proof of "not placed", and the venue gives no bounded visibility
            # guarantee: hold the intent (and its reserved exposure) with no re-POST.
            self._audit("alarm", code="SUBMIT_UNRESOLVED", intent_id=iid, blocking=True,
                        detail="%s was sent but is not visible at the broker; no resend" % iid)
            return False
        if allow_retry and int(it.get("retries", 0)) < 1 and \
                (it["kind"] != ENTRY or self.entry_block_reason() in (None, "UNRESOLVED_SUBMIT")):
            self._set_status(iid, "pending", retries=int(it.get("retries", 0)) + 1)
            self._audit("requested", intent_id=iid, client_id=it["client_id"], retry=it["retries"],
                        note="query found no order; resending with the same client id")
            self._dispatch(iid)
            return self.intents[iid]["status"] != "uncertain"
        self._set_status(iid, "not_placed", reason="broker has no order for this client id")
        self._audit("rejected", intent_id=iid, reason="NOT_PLACED", by="reconcile")
        return True

    def _adopt(self, iid, order, how):
        it = self.intents[iid]
        bstatus = order.get("status")
        if it["status"] in ("pending", "uncertain"):
            self._set_status(iid, "acked", order_id=order.get("order_id"), how=how)
            self._audit("acked", intent_id=iid, client_id=it["client_id"], order_id=order.get("order_id"), how=how)
        recovered = 0
        for f in order.get("fills") or []:
            if self._book_fill(iid, f, how=how):
                recovered += 1
        if bstatus in ("canceled", "rejected") and it["status"] == "acked":
            self._set_status(iid, bstatus)
            self._audit("canceled" if bstatus == "canceled" else "rejected", intent_id=iid, by="broker", how=how)
        if bstatus == "filled" and it["status"] != "filled" and it["filled_qty"] >= it["qty"]:
            self._set_status(iid, "filled")
        return recovered

    # ------------------------------------------------------------------ events
    def poll(self):
        """Drain broker events, book fills, then advance Pause / Stop & Close."""
        self._resync()
        summary = {"events": 0, "fills_booked": 0, "duplicates": 0, "connected": True, "simulated": self.simulated}
        try:
            events = self._call("events")
        except BrokerOutage:
            summary["connected"] = False
            return summary
        summary["events"] = len(events)
        for ev in events:
            r = self._on_event(ev)
            if r == "booked":
                summary["fills_booked"] += 1
            elif r == "duplicate":
                summary["duplicates"] += 1
        self._retry_pending_cancels()
        if self.controls.get("stopped") and not self.controls.get("flat_confirmed"):
            summary["stop"] = self._progress_stop()
        return summary

    def on_bar(self, bar):
        """Call after broker.step(bar). Updates the mark and the simulated clock.

        With a calendar, the bar goes through intake.check_bar first. A failed
        check blocks new entries on this bar (entry_block_reason "BAR_<code>");
        a stale, future, out-of-order or malformed bar does not move the mark."""
        self._last_bar_ts = bar.get("ts_close")
        when = bar.get("delivered_ts") or bar.get("ts_close")
        if when and self._clock is None:
            self._sim_now = parse_ts(when)
        code = "OK"
        if self.calendar is not None:
            ok, code, detail = check_bar(bar, self._prev_bar, self.calendar, max_age_s=self.bar_max_age_s)
            self._bar_status = None if ok else code
            if not ok:
                self._audit("alarm", code="BAR_" + code, blocking=False, bar_ts_open=bar.get("ts_open"),
                            detail=detail.get("msg"), codes=detail.get("codes"))
            if code not in ("BAD_BAR", "OUT_OF_ORDER"):
                self._prev_bar = bar
        if code not in UNTRUSTED_BAR_CODES and bar.get("close") is not None:
            self.mark = float(bar["close"])
        if self.controls.get("armed") and not self.controls.get("stopped") and self._expired():
            self._audit("control", action="session_expired", expires_utc=self.controls.get("expires_utc"))
            self.stop_and_close(reason="SESSION_EXPIRED")
        return self.poll()

    def _on_event(self, ev):
        etype = ev.get("type")
        cid = ev.get("client_id")
        iid = self.by_client.get(cid)
        if etype == "fill":
            if iid is None:
                self._alarm("FOREIGN_FILL", "fill %s for unknown client id %s" % (ev.get("exec_id"), cid))
                return "foreign"
            if ev.get("exec_id") in self.booked:
                return "duplicate"
            return "booked" if self._book_fill(iid, ev) else "ignored"
        if iid is None:
            if etype == "ack":
                self._alarm("FOREIGN_ORDER", "ack for unknown client id %s" % cid)
            return "foreign"
        it = self.intents[iid]
        if etype == "ack":
            if it["status"] in ("pending", "uncertain"):
                self._set_status(iid, "acked", order_id=ev.get("order_id"), how="event")
                self._audit("acked", intent_id=iid, client_id=cid, order_id=ev.get("order_id"), how="event")
            return "ack"
        if etype == "canceled":
            if it["status"] in OPEN_STATUSES:
                self._set_status(iid, "canceled")
                self._audit("canceled", intent_id=iid, by="broker", filled_qty=it.get("filled_qty", 0))
            return "canceled"
        if etype == "rejected":
            if ev.get("reason") != "DUPLICATE_CLIENT_ORDER_ID" and it["status"] in ("pending", "uncertain"):
                self._set_status(iid, "rejected", reason=ev.get("reason"))
                self._audit("rejected", intent_id=iid, reason=ev.get("reason"), by="broker")
            return "rejected"
        return "ignored"

    # ------------------------------------------------------------------ reconcile
    def reconcile(self, reason="manual"):
        """Compare broker orders, fills and position with the book. Returns a report."""
        alarms = []
        report = {"ts": iso(self.now()), "reason": reason, "adopted": [], "not_placed": [],
                  "fills_recovered": 0, "status_updates": [], "alarms": alarms, "simulated": self.simulated}

        def flag(code, detail, blocking=True):
            alarms.append({"code": code, "detail": detail, "blocking": blocking, "source": "reconcile",
                           "ts": report["ts"], "simulated": self.simulated})

        try:
            listing = self._call("list_orders")
            positions = self._call("positions")
        except BrokerOutage:
            flag("BROKER_UNREACHABLE", "list_orders/positions failed")
            return self._finish_reconcile(report, alarms, connected=False)
        orders = listing.get("orders") if isinstance(listing, dict) else None
        complete = isinstance(listing, dict) and listing.get("complete") is True
        if not isinstance(orders, list):
            flag("BAD_RECORD", "listing has no orders list")
            orders = []
        if not complete:
            flag("INCOMPLETE_LISTING", "broker listing truncated (%s of %s)" % (
                len(orders), listing.get("total") if isinstance(listing, dict) else "?"))
        by_client = {}
        for o in orders:
            if not isinstance(o, dict) or not o.get("client_id"):
                flag("BAD_RECORD", "listing row without client id")
                continue
            by_client[o["client_id"]] = o
        for cid, o in by_client.items():
            if cid not in self.by_client:
                # External: never canceled by the desk. Blocking while it may still trade.
                still_open = o.get("status") not in BROKER_DONE
                flag("FOREIGN_ORDER", "external broker order %s (%s) was not sent by this desk%s" % (
                    cid, o.get("status"), "; the desk will not cancel it" if still_open else ""),
                    blocking=still_open)
        try:
            for iid in list(self.intents):
                it = self.intents[iid]
                if it["status"] == "rejected" and not it.get("order_id"):
                    continue
                if it["status"] == "not_placed":
                    continue
                o = by_client.get(it["client_id"])
                if o is None:
                    try:
                        o = self._call("query", it["client_id"])
                    except BrokerUncertain:
                        # A 404 or empty listing is not proof of "not placed": keep it unresolved.
                        if it["status"] == "pending":
                            self._set_status(iid, "uncertain")
                        flag("SUBMIT_UNRESOLVED", "%s was sent but is not visible at the broker yet; "
                             "new exposure waits until it is found" % iid)
                        continue
                if o is None:
                    if it["status"] in ("pending", "uncertain"):
                        self._set_status(iid, "not_placed", reason="absent at reconcile")
                        self._audit("rejected", intent_id=iid, reason="NOT_PLACED", by="reconcile")
                        report["not_placed"].append(iid)
                    elif it.get("order_id"):
                        flag("ORDER_MISSING", "acknowledged order %s (%s) is gone from the broker" % (
                            iid, it["status"]))
                    continue
                if it["status"] in ("pending", "uncertain"):
                    report["adopted"].append(iid)
                before = len(self.booked)
                self._adopt(iid, o, how="reconcile")
                report["fills_recovered"] += len(self.booked) - before
                bstatus = o.get("status")
                if bstatus not in BROKER_STATUSES:
                    flag("UNKNOWN_STATUS", "%s has broker status %r" % (iid, bstatus))
                bfilled = self._bq(o.get("filled_qty"))
                if bfilled != Q.dec(it.get("filled_qty", 0)):
                    flag("FILL_TOTAL_MISMATCH", "%s broker filled %s, booked %s" % (
                        iid, Q.text(bfilled), Q.text(it.get("filled_qty", 0))))
                if bfilled > Q.dec(it["qty"]):
                    flag("OVERFILL", "%s broker filled %s of %s" % (iid, Q.text(bfilled), Q.text(it["qty"])))
                if bstatus in ("filled", "canceled", "rejected") and it["status"] == "acked":
                    self._set_status(iid, bstatus)
                    report["status_updates"].append([iid, bstatus])
        except BrokerOutage:
            flag("BROKER_UNREACHABLE", "query failed during reconcile")
            return self._finish_reconcile(report, alarms, connected=False)
        mine = positions.get(self.symbol) if isinstance(positions, dict) else None
        if self.fractional and isinstance(mine, dict) and mine.get("qty_exact") is not None:
            bqty = self._bq(mine.get("qty_exact"))
        else:
            bqty = self._bq((mine or {}).get("qty"))
        for sym, p in (positions or {}).items():
            if sym == self.symbol:
                continue
            try:
                foreign = self._bq((p or {}).get("qty")) != 0
            except (ValueError, TypeError):
                foreign = True
            if foreign:
                flag("FOREIGN_POSITION", "position in %s" % sym)
        if bqty != self.pos_qty:
            excess = abs(bqty) > abs(self.pos_qty) or (bqty > 0) != (self.pos_qty > 0)
            flag("POSITION_EXCESS" if excess else "POSITION_MISMATCH",
                 "broker position %s, booked %s" % (Q.text(bqty), Q.text(self.pos_qty)))
        report["positions"] = {"broker": Q.to_json(bqty), "booked": Q.to_json(self.pos_qty)}
        if isinstance(mine, dict) and mine.get("fractional") and not self.fractional:
            exact = str(mine.get("qty_exact"))
            report["positions"]["broker_exact"] = exact
            report["positions"]["fractional"] = True
            flag("POSITION_UNSUPPORTED_FRACTIONAL",
                 "broker shows %s %s, a fractional position this desk did not open and will not trade; "
                 "arming and new orders stay refused until it is gone" % (exact, self.symbol))
        # Anything not known to be done counts as working: "working" and unknown statuses alike.
        report["working_orders"] = [o["client_id"] for o in by_client.values() if o.get("status") not in BROKER_DONE]
        report["desk_working_orders"] = [c for c in report["working_orders"] if c in self.by_client]
        report["external_orders"] = [
            {"client_id": c, "status": by_client[c].get("status"), "side": by_client[c].get("side"),
             "qty": by_client[c].get("qty"), "class": "external", "simulated": self.simulated}
            for c in report["working_orders"] if c not in self.by_client]
        report["complete"] = complete
        return self._finish_reconcile(report, alarms, connected=True)

    def _finish_reconcile(self, report, alarms, connected):
        keep = [a for a in self.controls.get("alarms", []) if a.get("source") == "load"]
        self.controls["alarms"] = keep + alarms
        report["connected"] = connected
        report["ok"] = connected and not any(a["blocking"] for a in alarms)
        if connected:
            self.controls["last_reconcile_utc"] = report["ts"]
            self._broker_position = report.get("positions", {}).get("broker")
        self._save_controls()
        for a in alarms:
            self._audit("alarm", code=a["code"], detail=a["detail"], blocking=a["blocking"], source="reconcile")
        self._audit("knew", what="reconcile", reason=report["reason"], ok=report["ok"],
                    positions=report.get("positions"), adopted=report["adopted"],
                    not_placed=report["not_placed"], fills_recovered=report["fills_recovered"])
        self._last_report = report
        return report

    # ------------------------------------------------------------------ controls
    def _cancel(self, iid):
        it = self.intents[iid]
        try:
            res = self._call("cancel", it["client_id"])
        except BrokerOutage:
            return "failed"
        if res.get("status") == "canceled":
            if it["status"] in OPEN_STATUSES:
                self._set_status(iid, "canceled")
            self._audit("canceled", intent_id=iid, by="desk", filled_qty=it.get("filled_qty", 0))
            return "canceled"
        reason = res.get("reason")
        if reason == "UNKNOWN_ORDER" and it["status"] in ("pending", "uncertain"):
            self._set_status(iid, "not_placed", reason="cancel found no order")
            return "canceled"
        self._audit("knew", what="cancel_refused", intent_id=iid, reason=reason)
        return "refused:%s" % reason

    def _cancel_kinds(self, kinds):
        done, failed, refused = [], [], []
        for it in self._live(kinds):
            r = self._cancel(it["intent_id"])
            if r == "canceled":
                done.append(it["intent_id"])
            elif r == "failed":
                failed.append(it["intent_id"])
            else:
                refused.append([it["intent_id"], r])
        if failed:
            pend = sorted(set(self.controls.get("pending_cancels", [])) | set(failed))
            self._save_controls(pending_cancels=pend)
        return done, failed, refused

    def _retry_pending_cancels(self):
        pend = list(self.controls.get("pending_cancels", []))
        if not pend:
            return
        left = []
        for iid in pend:
            it = self.intents.get(iid)
            if it is None or it["status"] not in OPEN_STATUSES:
                continue
            if self._cancel(iid) == "failed":
                left.append(iid)
        self._save_controls(pending_cancels=left)

    def pause(self, reason="OPERATOR"):
        self._save_controls(paused=True)
        self._audit("control", action="pause", reason=reason)
        done, failed, refused = self._cancel_kinds([ENTRY])
        return {"paused": True, "entries_canceled": done, "cancel_failed": failed, "cancel_refused": refused,
                "protective_kept": [it["intent_id"] for it in self._live(["protective"])], "simulated": self.simulated}

    def resume(self):
        if self.controls.get("stopped"):
            return {"ok": False, "reason": "STOPPED", "simulated": self.simulated}
        self._save_controls(paused=False)
        self._audit("control", action="resume")
        return {"ok": True, "simulated": self.simulated}

    def arm(self, session_id=None, expires_utc=None):
        if self.controls.get("stopped"):
            self._audit("control", action="arm_refused", reason="STOPPED")
            return {"ok": False, "reason": "STOPPED", "simulated": self.simulated}
        report = self.reconcile(reason="arm")
        if not report["ok"]:
            self._audit("control", action="arm_refused", reason="RECONCILE_NOT_CLEAN")
            return {"ok": False, "reason": "RECONCILE_NOT_CLEAN", "report": report, "simulated": self.simulated}
        if expires_utc is not None:
            expires_utc = iso(parse_ts(expires_utc))
        else:
            expires_utc = self._default_expiry()
        self._save_controls(armed=True, session_id=session_id or self.controls.get("session_id"),
                            expires_utc=expires_utc, flat_confirmed=False)
        self._audit("control", action="arm", session_id=self.controls["session_id"], expires_utc=expires_utc)
        return {"ok": True, "simulated": self.simulated}

    def _default_expiry(self):
        """Finish each armed session flat: expire flatten_lead_s before the session ends."""
        if self.calendar is None:
            return None
        nxt = self.calendar.next_open(self.now())
        if nxt is None:
            return None
        for start, end in self.calendar.windows(self.calendar.local_date(nxt)):
            if start <= nxt < end:
                return iso(max(start, end - _dt.timedelta(seconds=self.flatten_lead_s)))
        return None

    def disarm(self, reason="OPERATOR"):
        self._save_controls(armed=False)
        self._audit("control", action="disarm", reason=reason)
        return {"ok": True, "simulated": self.simulated}

    def enable_schedule(self, enabled):
        """Scheduled unattended mode is off unless this is called with True."""
        if enabled and self.controls.get("stopped"):
            return {"ok": False, "reason": "STOPPED", "simulated": self.simulated}
        self._save_controls(schedule_enabled=bool(enabled))
        self._audit("control", action="schedule", enabled=bool(enabled))
        return {"ok": True, "simulated": self.simulated}

    def stop_and_close(self, reason="OPERATOR"):
        first = not self.controls.get("stopped")
        self._save_controls(stopped=True, paused=True, armed=False, schedule_enabled=False,
                            flat_confirmed=False,
                            stop_reason=self.controls.get("stop_reason") if not first else reason,
                            stop_utc=self.controls.get("stop_utc") if not first else iso(self.now()))
        self._audit("control", action="stop_and_close", reason=reason)
        done, failed, refused = self._cancel_kinds([ENTRY])
        report = {"stopped": True, "entries_canceled": done, "cancel_failed": failed,
                  "cancel_refused": refused, "simulated": self.simulated}
        report["close"] = self._progress_stop()
        report["flat_confirmed"] = bool(self.controls.get("flat_confirmed"))
        report["external_orders"] = report["close"].get("external_orders", [])
        if not report["flat_confirmed"]:
            report["status_text"] = self.controls.get("close_pending") or NOT_FLAT_TEXT
        return report

    def clear_stop(self, confirm=False):
        """The only way to lift a Stop. Needs confirm=True and a fresh, complete flat check."""
        if confirm is not True:
            self._audit("control", action="clear_stop_refused", reason="CONFIRM_REQUIRED")
            return {"ok": False, "reason": "CONFIRM_REQUIRED", "simulated": self.simulated}
        rep = self.reconcile(reason="clear-stop")
        blockers = self._flat_blockers(rep)
        if blockers or not self.controls.get("flat_confirmed"):
            if blockers:
                self._save_controls(flat_confirmed=False,
                                    close_pending="%s (%s)" % (NOT_FLAT_TEXT, "; ".join(blockers)))
            self._audit("control", action="clear_stop_refused", reason="NOT_FLAT_CONFIRMED", blockers=blockers)
            return {"ok": False, "reason": "NOT_FLAT_CONFIRMED", "blockers": blockers,
                    "status_text": NOT_FLAT_TEXT, "simulated": self.simulated}
        self._save_controls(stopped=False, stop_reason=None, stop_utc=None, close_pending=None, close_attempts=0)
        self._audit("control", action="clear_stop", confirm=True)
        return {"ok": True, "simulated": self.simulated}

    def _flat_blockers(self, rep):
        """Everything that stops a reconcile from proving flat. Empty list = proven flat."""
        if not rep.get("connected"):
            return ["broker unreachable"]
        why = []
        if not rep.get("complete"):
            why.append("broker order listing incomplete")
        pos = rep.get("positions") or {}
        if pos.get("fractional"):
            why.append("broker position %s %s is fractional (not this desk's; not traded)" % (
                pos.get("broker_exact"), self.symbol))
        elif pos.get("broker") != 0:
            why.append("broker position %s" % pos.get("broker"))
        if pos.get("booked") != 0:
            why.append("booked position %s" % pos.get("booked"))
        if rep.get("desk_working_orders"):
            why.append("desk orders working: %s" % ", ".join(rep["desk_working_orders"]))
        unresolved = [it["intent_id"] for it in self._live()]
        if unresolved:
            why.append("desk orders open or unknown: %s" % ", ".join(unresolved))
        ext = rep.get("external_orders") or []
        if ext:
            why.append("external orders working (not this desk's; not canceled): %s" % ", ".join(
                e["client_id"] for e in ext))
        odd = sorted({a["code"] for a in rep.get("alarms", [])
                      if a["code"] in ("BAD_RECORD", "UNKNOWN_STATUS", "ORDER_MISSING", "FOREIGN_POSITION")})
        if odd:
            why.append("unresolved broker records: %s" % ", ".join(odd))
        return why

    @staticmethod
    def _desk_owned(broker_qty, booked_qty):
        """The signed shares Stop & Close may act on: the part of the broker position this desk booked.
        Shares held outside the desk (another app, a manual trade) are never closed or covered here."""
        broker_qty, booked_qty = Q.parse_signed(broker_qty), Q.parse_signed(booked_qty)
        if broker_qty > 0 and booked_qty > 0:
            return min(broker_qty, booked_qty)
        if broker_qty < 0 and booked_qty < 0:
            return max(broker_qty, booked_qty)
        return 0

    def _stop_external_only(self, rep):
        """The broker shows SPY the desk did not book. Send no close for it. The desk's own protective,
        exit and close orders can only trade those shares now, so they are canceled (desk orders only)."""
        bqty, booked = rep["positions"]["broker"], rep["positions"]["booked"]
        if self._live(["protective", "exit", "close"]):
            self._cancel_kinds(["protective", "exit", "close"])
        why = ("broker position %s SPY is not this desk's (desk booked %s); not closed or covered. "
               "Resolve it in your Alpaca account." % (Q.text(Q.parse_signed(bqty)), Q.text(Q.parse_signed(booked))))
        self._save_controls(flat_confirmed=False, close_pending=why)
        self._audit("control", action="stop_external_position", broker=bqty, booked=booked)
        return {"state": "pending", "why": why, "external_position": bqty, "desk_booked": booked,
                "external_orders": rep.get("external_orders") or []}

    def _progress_stop(self):
        """One step toward a confirmed-flat stop. Safe to call repeatedly.

        Protective and exit orders stay working until the broker shows the position
        at zero. Every desk exit is reduce-only, so a close and a protective that
        both trade can only take the position to flat, never through it."""
        rep = self.reconcile(reason="stop")
        if not rep.get("connected"):
            self._save_controls(close_pending="broker unreachable; retrying")
            return {"state": "pending", "why": "broker unreachable"}
        self._retry_pending_cancels()
        if self._live([ENTRY]):
            self._cancel_kinds([ENTRY])
        bqty = rep["positions"]["broker"]
        if bqty == 0:
            if self._live(["protective", "exit", "close"]):
                self._cancel_kinds(["protective", "exit", "close"])     # the desk's own orders only
            rep2 = self.reconcile(reason="flat-check")
            blockers = self._flat_blockers(rep2)
            if not blockers:
                self._save_controls(flat_confirmed=True, close_pending=None)
                self._audit("control", action="flat_confirmed")
                return {"state": "flat_confirmed"}
            why = "%s (%s)" % (NOT_FLAT_TEXT, "; ".join(blockers))
            self._save_controls(flat_confirmed=False, close_pending=why)
            return {"state": "pending", "why": why, "external_orders": rep2.get("external_orders") or []}
        owned = self._desk_owned(bqty, rep["positions"]["booked"])
        if owned == 0:
            return self._stop_external_only(rep)
        closed = cal_closed = self.calendar is not None and not self.calendar.is_open(self.now())
        unverified = False
        if not closed and callable(self.venue_open):
            # Connected modes: the only protective stop is cancelled only on a fresh venue clock that
            # says open. Closed, unreadable or not a bool all keep the protection.
            try:
                v = self.venue_open()
            except Exception:
                v = None
            closed = v is not True
            unverified = v is None
        if closed:
            # Outside regular hours, or while the venue says closed, nothing is sent: no protective
            # cancel and no close order. The working stop stays, and the text says what covers it.
            nxt = self.calendar.next_open(self.now()) if self.calendar is not None else None
            pside = "sell" if owned > 0 else "buy"
            prot = sum(self._remaining(it) for it in self._live(["protective"]) if it["side"] == pside)
            held = ("held, protected by its working stop (%g of %g shares)" % (min(prot, abs(owned)), abs(owned))
                    if prot > 0 else "held with NO working protective stop (%g shares)" % abs(owned))
            if cal_closed:
                why = ("market closed: position %s; nothing sent (no protective cancel, no close order); the "
                       "operator closes at the next regular session (opens %s)" % (held, iso(nxt) if nxt else "unknown"))
            else:
                why = ("close pending (%s): position %s; protective stop kept; nothing sent (no protective "
                       "cancel, no close order); closes once a fresh venue clock says open"
                       % ("clock unverified" if unverified else "venue clock says market closed", held))
            self._save_controls(close_pending=why)
            return {"state": "pending", "why": why, "market_closed": True, "protected_shares": min(prot, abs(owned))}
        side = "sell" if owned > 0 else "buy"
        unprotected = False
        if getattr(self.broker, "exits_hold_position", False):
            # This venue holds the shares of a working exit, so a close next to the protective is
            # refused. Cancel the desk's protective/exit orders on this side, wait until the broker
            # shows them done (an accepted cancel is not proof), reconcile, then close what is left.
            held = [it for it in self._live(["protective", "exit"]) if it["side"] == side]
            if held:
                for it in held:
                    try:
                        self._call("cancel", it["client_id"])
                    except BrokerError:
                        pass
                rep = self.reconcile(reason="stop-unprotect")
                still = [it["intent_id"] for it in self._live(["protective", "exit"]) if it["side"] == side]
                if not rep.get("connected") or still:
                    why = ("protective cancel requested, not yet confirmed by the broker (%s); close waits "
                           "so nothing sells twice" % (", ".join(still) or "broker unreachable"))
                    self._save_controls(close_pending=why)
                    return {"state": "pending", "why": why, "unconfirmed_cancels": still}
                self._audit("control", action="stop_protection_canceled", intent_ids=[it["intent_id"] for it in held])
                bqty = rep["positions"]["broker"]
                owned = self._desk_owned(bqty, rep["positions"]["booked"])
                if bqty == 0 or owned == 0:
                    return self._progress_stop()           # the protective traded during the cancel
                side = "sell" if owned > 0 else "buy"
            unprotected = not any(it["side"] == side for it in self._live(["protective"]))
        closes = self._live(["close"])
        wrong = [c["intent_id"] for c in closes if c["side"] != side]
        for iid in wrong:
            self._cancel(iid)
        covered = sum(self._remaining(c) for c in closes if c["side"] == side)
        if covered >= abs(owned):
            why = ("close order working; protective canceled first" if unprotected
                   else "close order working; protective exits kept until flat")
            self._save_controls(close_pending=why)
            return {"state": "pending", "why": why, "close": [c["intent_id"] for c in closes]}
        qty = Q.norm(Q.dec(abs(owned)) - Q.dec(covered))
        attempt = int(self.controls.get("close_attempts", 0)) + 1
        self._save_controls(close_attempts=attempt)
        decision_id = "close|%s|%s|%d" % (self.controls.get("session_id"), self.controls.get("stop_utc"), attempt)
        iid = self._submit(stable_intent_id(decision_id), {"decision_id": decision_id, "ref_price": self.mark},
                           "close", side, qty, internal=True)
        it = self.intents.get(iid) or {}
        st = it.get("status")
        if st == "acked":
            if unprotected:
                why = "closing %s at market (reduce-only); protective canceled first" % Q.text(qty)
            else:
                why = "closing %s at market (reduce-only); protective exits kept until flat" % Q.text(qty)
            self._save_controls(close_pending=why)
            return {"state": "closing", "intent_id": iid, "qty": Q.to_json(qty), "why": why}
        if unprotected:
            why = "position %s SPY UNPROTECTED: protective canceled, close pending" % Q.text(abs(owned))
            self._save_controls(close_pending=why)
            return {"state": "closing_unprotected", "why": why, "intent_id": iid, "qty": Q.to_json(qty),
                    "close_status": st, "close_reason": it.get("reason")}
        if st in ("rejected", "not_placed"):
            why = "close rejected (%s); protective exits kept; retry next poll" % it.get("reason")
        else:
            why = "close sent, broker answer unknown (%s); protective exits kept" % st
        self._save_controls(close_pending=why)
        return {"state": "pending", "why": why, "intent_id": iid, "qty": Q.to_json(qty)}

    # ------------------------------------------------------------------ views
    def _order_view(self, it):
        return {"intent_id": it["intent_id"], "client_id": it["client_id"], "order_id": it.get("order_id"),
                "kind": it["kind"], "side": it["side"], "qty": Q.to_json(it["qty"]),
                "filled_qty": Q.to_json(it.get("filled_qty", 0)),
                "remaining": Q.to_json(self._remaining(it)), "limit": it.get("limit"), "stop": it.get("stop"),
                "status": it["status"], "simulated": self.simulated}

    def ledger_rows(self):
        """Per-intent rows with mock fills, for the desk ledger writer."""
        rows = []
        fills_by = {}
        for f in self.fills:
            fills_by.setdefault(f["intent_id"], []).append({
                "exec_id": f["exec_id"], "qty": Q.to_json(f["qty"]), "price": f["price"], "fee": f["fee"],
                "ts": f.get("fill_ts"), "mock": bool(f.get("mock", True)), "simulated": self.simulated})
        for it in self.intents.values():
            rows.append({"trade_id": it["intent_id"], "decision_id": it["decision_id"], "intent_id": it["intent_id"],
                         "order_id": it.get("order_id"), "signal_ts": it.get("signal_ts"),
                         "quote": it.get("ref_price"), "kind": it["kind"], "side": it["side"],
                         "status": it["status"], "fills": fills_by.get(it["intent_id"], []),
                         "fees": round(it.get("fees", 0.0), 6), "simulated": self.simulated})
        return rows

    def state(self):
        c = self.controls
        working = [self._order_view(it) for it in self._live() if it["kind"] != "protective"]
        protective = [self._order_view(it) for it in self._live(["protective"])]
        unreal = self.unrealized()
        return {
            "mode": MODE,
            "armed": bool(c.get("armed")),
            "session_id": c.get("session_id"),
            "expires_utc": c.get("expires_utc"),
            "symbol": self.symbol,
            "strategy": self.strategy,
            "data_label": self.data_label,
            "controls": {"paused": bool(c.get("paused")), "stopped": bool(c.get("stopped")),
                         "flat_confirmed": bool(c.get("flat_confirmed")),
                         "schedule_enabled": bool(c.get("schedule_enabled")),
                         "stop_reason": c.get("stop_reason"), "close_pending": c.get("close_pending")},
            "daily_entries": {"used": len(self._entries_today()), "max": self.limits.get("max_daily_entries"),
                              "day": self._day_key(None), "counts_broker_buys": self.fractional},
            "exposure": {"position_qty": Q.to_json(self.pos_qty), "avg_price": round(self.pos_avg, 6),
                         "working_orders": working,
                         "gross_including_working": round(self.gross_exposure(), 6),
                         "broker_position_qty": getattr(self, "_broker_position", None),
                         "broker_confirmed_utc": c.get("last_reconcile_utc")},
            "protective_orders": protective,
            "pnl": {"realized": round(self.realized, 6), "unrealized": round(unreal, 6),
                    "fees": round(self.fees, 6), "after_cost": round(self.realized + unreal - self.fees, 6),
                    "day_after_cost": round(self.day_pnl(), 6)},
            "limits": dict(self.limits, label=self.limits_label),
            "broker": {"name": getattr(self.broker, "name", "FakeBroker (offline)"),
                       "connected": self.connected is True,
                       "last_call_ok_utc": c.get("broker_confirmed_utc"),
                       "last_reconcile_utc": c.get("last_reconcile_utc")},
            "alarms": list(c.get("alarms", [])),
            "entry_block_reason": self.entry_block_reason(),
            "updated_utc": iso(self.now()),
            "simulated": self.simulated,
        }
