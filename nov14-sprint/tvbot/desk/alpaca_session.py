"""Opt-in Alpaca PAPER session for the desk (alpaca/CONTRACT.md; coordinator-owned).

The offline replay desk (session.SessionController) is unchanged. This subclass swaps three
parts through the hooks session.py exposes:

  bars      closed SPY bars from the free IEX feed (alpaca/feed.py), fetched only when the
            operator clicks "Check for new bars". There is no background job, no schedule and
            no Play in this mode.
  calendar  the NYSE 2026-2027 calendar (America/New_York, holidays and early closes).
  broker    alpaca/broker.py AlpacaPaperBroker over either the in-process mock (default,
            synthetic ids, no network) or the HTTPS transport fixed to the paper host.

Entries are priced and bounded (CONTRACT section 3a): a buy entry is a LIMIT at
floor_to_tick(min(decision price, notional cap / qty, remaining gross / qty,
stop + (max loss - est cost) / qty)). Opening a short is blocked in this first SPY path.
Exits, protective reductions, reconcile and Stop stay available while the adapter is disabled.

Agents never run --transport https. It needs Matthew's own paper keys and his approved limits.
"""
import datetime as _dt
import importlib
import json
import math
import os

import session as S
import alpaca as A
from alpaca.state import AdapterState
from alpaca.broker import cent_price
from alpaca.readiness import read_quote
from orders.calendar import SessionCalendar, parse_ts, iso

MODE_MOCK = "mock"
MODE_HTTPS = "https"
TICK = 0.01
# A manual session cannot react within the streaming desk's 5 s staleness rule. A closed bar
# received more than this long after its close is rejected (STALE) and never trades.
BAR_MAX_AGE_S = 900.0
WARMUP_MAX_AGE_S = 21 * 86400.0   # catch-up bars older than BAR_MAX_AGE_S warm features only (9 sessions + holidays)
WARMUP_BARS_DEFAULT = 63          # bot/rules.py DEFAULT_PARAMS["warmup_bars"]
FILL_TIMING_NOTE = ("Manual desk: a broker fill that happens between your Checks is booked, and any uncovered shares get a protective stop, only at your next Check for new bars. Until then those shares may be unprotected. Reconcile is read-only and never sends an order.")
VENUE_CLOCK_SKEW_S = 120.0
SNAPSHOT_FILE = "alpaca_broker_snapshot.json"
MOCK_START_DAY = "2026-11-16"     # synthetic walkthrough day (a Monday on the NYSE calendar)
MOCK_TEST_LABEL = ("MOCK WALKTHROUGH TEST VALUE: fixed %d share(s); not Matthew's sizing "
                   "(no approved or draft limits in this state dir)")
MOCK_DRAFT_LABEL = "MOCK REHEARSAL ON DRAFT LIMITS: fixed %d share(s) (draft, not approved)"
APPROVED_QTY_LABEL = "OPERATOR-APPROVED fixed %%d share(s) (limits snapshot %s)"
SHORT_OPEN_DETAIL = ("opening a short is blocked in the first SPY paper path (no borrow/locate or "
                     "short-sale semantics verified); exits and Stop still work")


class AdapterUnavailable(RuntimeError):
    """A worker module the Alpaca mode needs is missing or incomplete."""


def _need(modname, attr):
    try:
        mod = importlib.import_module(modname)
        return getattr(mod, attr)
    except (ImportError, AttributeError) as exc:
        raise AdapterUnavailable("Alpaca paper mode needs %s.%s, which is not available in this build (%s)"
                                 % (modname, attr, exc.__class__.__name__))


def floor_tick(x):
    """Round DOWN to the $0.01 tick (never up past a cap)."""
    return math.floor(round(float(x) / TICK, 6)) * TICK


def _now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


# ------------------------------------------------------------------ limits
def resolve_limits(mode, state_dir, limits_path=None):
    """Return (session_limits, fixed_shares, limits_source).

    https: only an operator-approved snapshot (explicit path) is accepted; nothing is invented.
    mock:  explicit path (approved or draft), else this state dir's approved/draft, else the
           desk's TEST limits with a 1-share TEST label (rehearsal only)."""
    sizing = importlib.import_module("alpaca.sizing")
    if mode == MODE_HTTPS:
        if not limits_path:
            raise sizing.LimitsError("the paper path needs --limits pointing at your approved limits file")
        loaded = sizing.load_limits(path=limits_path, allow_draft=False)
    else:
        loaded = None
        if limits_path:
            loaded = sizing.load_limits(path=limits_path, allow_draft=True)
        else:
            try:
                loaded = sizing.load_limits(state_dir=state_dir, allow_draft=True)
            except sizing.LimitsError:
                loaded = None
        if loaded is None:
            lim = dict(S.TEST_LIMITS)
            lim["label"] = "MOCK WALKTHROUGH TEST LIMITS (%s)" % S.LIMITS_LABEL
            return lim, 1, {"provenance": "desk-test-limits", "label": MOCK_TEST_LABEL % 1,
                            "hash": None, "approved_utc": None, "mock_only": True}
    lim = sizing.as_session_limits(loaded)
    fixed = int(lim.pop("fixed_shares"))
    source = {k: v for k, v in loaded.items() if k != "values"}
    session_lim = {k: float(lim[k]) for k in sizing.CAP_FIELDS}
    session_lim["label"] = lim.get("label") or ""
    session_lim["limits_hash"] = lim.get("hash")
    return session_lim, fixed, source


# ------------------------------------------------------------------ clocks
class WallClock(object):
    name = "WALL CLOCK (manual checks only)"

    def now(self):
        return _now_utc()

    def on_check(self, calendar, minutes):
        return self.now()


class MockClock(object):
    """Synthetic market clock for the mock walkthrough. Each manual check moves it to just after
    the next bar close on the NYSE calendar. Persisted, so a restart resumes where it was."""
    name = "MOCK CLOCK (synthetic; advances one bar per manual check)"

    def __init__(self, state_dir, calendar, start_day=MOCK_START_DAY):
        self.path = os.path.join(state_dir, "mock_clock.json")
        t = None
        try:
            with open(self.path) as fh:
                t = parse_ts(json.load(fh)["now"])
        except (OSError, ValueError, KeyError, TypeError):
            t = None
        if t is None:
            bounds = calendar.session_bounds(start_day)
            t = bounds[0] if isinstance(bounds, (tuple, list)) else parse_ts(start_day + "T14:30:00Z")
        self.t = t

    def now(self):
        return self.t

    def _save(self):
        S._atomic_json(self.path, {"now": iso(self.t), "label": self.name})

    def on_check(self, calendar, minutes):
        day = calendar.local_date(iso(self.t)) if hasattr(calendar, "local_date") else self.t.date()
        if not isinstance(day, _dt.date):
            day = _dt.date.fromisoformat(str(day)[:10])
        for _ in range(15):
            try:
                slots = calendar.bar_slots(day, minutes) if calendar.is_trading_day(day) else []
            except Exception:
                slots = []
            for _open, close in slots:
                if close > self.t - _dt.timedelta(seconds=2):
                    if close + _dt.timedelta(seconds=2) > self.t:
                        self.t = close + _dt.timedelta(seconds=2)
                        self._save()
                        return self.t
            day = day + _dt.timedelta(days=1)
        self._save()
        return self.t


# ------------------------------------------------------------------ controller
class AlpacaSessionController(S.SessionController):
    bar_max_age_s = BAR_MAX_AGE_S

    def __init__(self, state_dir=S.DEFAULT_STATE_DIR, strategy=S.DEFAULT_STRATEGY, mode=MODE_MOCK,
                 transport=None, limits_path=None, feed=None, broker_factory=None, clock=None,
                 lab=None, strategy_cfg=None, mock_days=None):
        if mode not in (MODE_MOCK, MODE_HTTPS):
            raise ValueError("mode must be mock or https")
        state_dir = os.path.abspath(state_dir)
        os.makedirs(state_dir, exist_ok=True)
        self.mode = mode
        self.mock = mode == MODE_MOCK
        self.evidence_label = A.LABEL_MOCK_LOCAL if self.mock else A.LABEL_ALPACA_PAPER
        self.data_label = A.DATA_LABEL_MOCK if self.mock else A.DATA_LABEL_IEX
        self.broker_mode = "alpaca-mock" if self.mock else "alpaca-paper"
        self.adapter_state = AdapterState(state_dir)
        self._bars_file = os.path.join(state_dir, "alpaca_bars.jsonl")
        limits, fixed, self.limits_source = resolve_limits(mode, state_dir, limits_path)
        if self.mock and self.limits_source.get("provenance") == "draft":
            self.fixed_qty_label = MOCK_DRAFT_LABEL
        elif self.limits_source.get("mock_only"):
            self.fixed_qty_label = MOCK_TEST_LABEL
        else:
            self.fixed_qty_label = APPROVED_QTY_LABEL % (str(self.limits_source.get("hash") or "")[:12],)
        if transport is None:
            if self.mock:
                Mock = _need("alpaca.mock", "MockAlpacaTransport")
                Trading = _need("alpaca.mock", "MockTrading")
                Data = _need("alpaca.mock_data", "MockData")
                transport = Mock(trading=Trading(), data=Data(days=list(mock_days or self._mock_days())))
            else:
                raise ValueError("the https transport is built by launch.py from Matthew's own credential "
                                 "provider; it is never built implicitly")
        self.transport = transport
        self._broker_factory = broker_factory
        self.lab = lab
        cfg = dict(S.DEMO_STRATEGY_CFG if strategy_cfg is None else strategy_cfg)
        cfg["fixed_qty"] = int(fixed)
        # Strategy sizing basis = this session's chosen limits, never the offline $2,000 TEST
        # cap (Codex 22:5xZ: base_qty(500) returned 0 for 10 shares under a $6,000 per-order
        # cap). The offline DeskSession keeps its old contract: it never sets these keys.
        cfg["test_size"] = {"order_notional": float(limits["per_trade_notional"]),
                            "label": "SESSION LIMITS (%s)" % (self.limits_source.get("provenance") or "?"),
                            "source": "alpaca session limits"}
        cfg["limits"] = {k: float(limits[k]) for k in
                         ("per_trade_notional", "max_loss_per_trade", "daily_loss", "gross_exposure")}
        # Everything session_state()/preflight() read is built BEFORE the base init, which
        # publishes state at its end (Codex 22:24Z: clock was missing at that point).
        self._calendar = SessionCalendar.nyse_2026_2027()
        self.clock = clock or (MockClock(state_dir, self._calendar) if self.mock else WallClock())
        if feed is None:
            Feed = _need("alpaca.feed", "IexSpyFeed")
            feed = Feed(self.transport, self._calendar, minutes=60, source=self.data_label)
        self.feed = feed
        self.last_check = None
        self.snapshot_error = None
        if self.lab is None:
            self.lab = self._default_lab(state_dir)
        self.config_revision = None
        S.SessionController.__init__(self, state_dir=state_dir, strategy=strategy, limits=limits,
                                     strategy_cfg=cfg)
        if self.config_revision is not None:
            # A changed sizing snapshot never inherits an armed state: the operator re-arms.
            self.mgr.disarm(reason="SESSION_CONFIG_REVISED")
        # Every manager reconcile report (start-up, restart, reconnect, arm, Stop, operator) also
        # reaches the adapter, so a failed or incomplete reconcile blocks new exposure there too.
        raw_reconcile = self.mgr.reconcile

        def reconcile(*a, **kw):
            rep = raw_reconcile(*a, **kw)
            note = getattr(self.broker, "note_reconcile", None)
            if note is not None:
                note(rep)
            return rep
        self.mgr.reconcile = reconcile
        note = getattr(self.broker, "note_reconcile", None)
        last = getattr(self.mgr, "_last_report", None)
        if note is not None and last is not None:
            note(last)
        self._write_state()

    # ---------------------------------------------------------------- hooks
    @staticmethod
    def _mock_days():
        # Synthetic minutes from two weeks before the walkthrough day (warm-start history)
        # to the end of that week. Non-trading days produce no minutes.
        day = _dt.date.fromisoformat(MOCK_START_DAY)
        return [(day + _dt.timedelta(days=k)).isoformat() for k in range(-15, 5)]

    def _warm_start_after(self, now):
        """ts_close boundary so the first check fetches enough closed history to warm the
        strategy (warmup_bars + 1). Those catch-up bars arrive late, so they are warm-up only."""
        need = int(self.strategy_cfg.get("warmup_bars") or WARMUP_BARS_DEFAULT) + 1
        cal, day, count, first_open = self.calendar, self.calendar.local_date(iso(now)), 0, None
        for _ in range(40):
            try:
                slots = [sl for sl in cal.bar_slots(day, self.minutes) if sl[1] <= now] \
                    if cal.is_trading_day(day) else []
            except Exception:       # before calendar coverage: use what is covered
                break
            if slots:
                count += len(slots)
                first_open = slots[0][0]
            if count >= need:
                break
            day = day - _dt.timedelta(days=1)
        return iso(first_open - _dt.timedelta(seconds=1)) if first_open is not None else None

    def _fetch(self, after, now):
        """One manual check's fetch. With no history yet it walks back in <=9-day chunks (the
        feed refuses longer gaps). Every bar carries this check's receipt time."""
        recv = iso(now)
        if after is not None:
            return list(self.feed.fetch_closed_bars(after, now, received_ts=recv)), []
        cur = self._warm_start_after(now)
        if cur is None:
            return list(self.feed.fetch_closed_bars(None, now, received_ts=recv)), []
        out, empty = [], []
        while True:
            end = min(now, parse_ts(cur) + _dt.timedelta(days=9))
            out.extend(self.feed.fetch_closed_bars(cur, end, received_ts=recv))
            lf = getattr(self.feed, "last_fetch", None) or {}
            empty.extend(lf.get("empty_slots") or [])
            if end >= now:
                return out, empty
            cur = iso(end)

    def _load_bars(self, bars_path):
        rows = S._read_jsonl(self._bars_file) if os.path.exists(self._bars_file) else []
        return {"symbol": A.SYMBOL, "timeframe_minutes": 60, "source": self.data_label}, rows

    @staticmethod
    def _default_lab(state_dir):
        try:
            mod = importlib.import_module("lab")
        except Exception:
            return None
        for name in ("Lab", "LabRecorder", "DecisionLab"):
            cls = getattr(mod, name, None)
            if cls is not None:
                try:
                    return cls(state_dir)
                except Exception:
                    return None
        return None

    def _make_calendar(self):
        return getattr(self, "_calendar", None) or SessionCalendar.nyse_2026_2027()

    def _make_broker(self, broker_seed, faults):
        factory = self._broker_factory or _need("alpaca.broker", "AlpacaPaperBroker")
        restored = os.path.exists(os.path.join(self.state_dir, "alpaca_broker.json"))
        broker = factory(self.transport, self.state_dir, self.evidence_label, self.adapter_state)
        restored = restored or bool(getattr(broker, "restored", False))
        snap = os.path.join(self.state_dir, SNAPSHOT_FILE)
        if os.path.exists(snap) and hasattr(broker, "restore"):
            try:
                with open(snap) as fh:
                    broker.restore(json.load(fh))
            except (ValueError, OSError) as exc:     # keep going; the venue book is authoritative
                self.snapshot_error = "%s: %s" % (exc.__class__.__name__, str(exc)[:120])
        return broker, restored

    def _row_flags(self):
        return {"simulated": self.mock, "evidence": self.evidence_label, "data_source": self.data_label}

    def _ledger_flags(self):
        return {"mock_fills": self.mock, "evidence": self.evidence_label, "data_source": self.data_label}

    def _late_s(self, bar):
        try:
            return (parse_ts(bar["delivered_ts"]) - parse_ts(bar["ts_close"])).total_seconds()
        except (KeyError, TypeError, ValueError):
            return None

    def _warmup_only(self, bar):
        late = self._late_s(bar)
        return late is not None and late > self.bar_max_age_s

    def _intake_max_age(self, bar):
        # A late catch-up bar is still checked for shape, order and session; it may join the
        # strategy history (feature warm-up) but _warmup_only() keeps it away from routing.
        return WARMUP_MAX_AGE_S if self._warmup_only(bar) else self.bar_max_age_s

    def warmup_view(self):
        need = int(self.strategy_cfg.get("warmup_bars") or WARMUP_BARS_DEFAULT)
        have = len(self.hist)
        return {"bars": have, "needed": need, "ready": have >= need,
                "text": ("strategy warm-up ready (%d/%d closed bars)" % (have, need)) if have >= need else
                        ("strategy warm-up %d/%d closed bars: entries wait until ready; late catch-up bars "
                         "count toward warm-up but are never routed" % (have, need))}

    def _write_state(self):
        S.SessionController._write_state(self)
        snap = getattr(self.broker, "snapshot", None) if hasattr(self, "broker") else None
        if snap is not None:
            S._atomic_json(os.path.join(self.state_dir, SNAPSHOT_FILE), snap())

    def _lab_observe(self, bar, d):
        if self.lab is None or not hasattr(self.lab, "observe"):
            return None
        try:
            self.lab.observe(list(self.hist), {self.strategy: dict(d)}, bar)
        except Exception as exc:   # the lab is a shadow: it can never block or alter trading
            self._desk_audit("lab_error", error=exc.__class__.__name__, detail=str(exc)[:200])
        return None

    def _entry_bounds(self, d, bar, st, qty, side, entry, inval):
        if side != "buy":
            return None, ("SHORT_OPEN_BLOCKED", SHORT_OPEN_DETAIL)
        if not self.mock:
            # HTTPS entries only: one free-IEX latest-quote read per BUY candidate. Protective
            # stops, residual cover and Stop & Close never pass through here, so they are never held.
            q = read_quote(self.transport, self.clock.now())
            self.latest_quote = d["quote_observation"] = q
            self._desk_audit("entry_quote_observed", decision_id=d.get("decision_id"), quote=q)
            if not (q.get("valid") and q.get("fresh")):
                return None, ("QUOTE_GATE", "new entry held: SPY IEX quote %s; no order"
                              % (q.get("reason") or "unavailable"))
        lim = self.limits
        cost = S._cost_usd(d)
        gross_used = float(st["exposure"].get("gross_including_working") or 0.0)
        remaining = float(lim["gross_exposure"]) - gross_used
        bounds = {
            "decision": float(entry),
            "notional": float(lim["per_trade_notional"]) / qty,
            "gross": remaining / qty,
            "risk_stop": float(inval) + (float(lim["max_loss_per_trade"]) - cost) / qty,
        }
        raw = min(bounds.values())
        limit = round(floor_tick(raw), 2)
        binding = min(bounds, key=lambda k: bounds[k])
        d["entry_bound"] = {"limit": limit, "binding": binding,
                            "bounds": {k: round(v, 4) for k, v in bounds.items()}, "tick": TICK}
        if limit <= 0 or limit <= float(inval):
            return None, ("ENTRY_BOUND", "bounded limit $%.2f (binding: %s) is not above the stop $%.2f; "
                                         "no order" % (limit, binding, float(inval)))
        if qty * limit > float(lim["per_trade_notional"]) + 1e-9 or qty * limit > remaining + 1e-9:
            return None, ("ENTRY_BOUND", "qty %d x $%.2f exceeds a cap; no order" % (qty, limit))
        return limit, None

    # ---------------------------------------------------------------- manual bar checks
    def _move_mock_market(self, bar):
        trading = getattr(self.transport, "trading", None)
        if not self.mock or trading is None or not hasattr(trading, "advance"):
            return
        if hasattr(trading, "event_ts"):
            trading.event_ts = bar.get("ts_close") or bar.get("ts")   # mock fills follow the mock clock
        o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
        for p in ((o, l, h, c) if c >= o else (o, h, l, c)):
            trading.advance(p)

    def check_new_bars(self):
        """Operator action: fetch closed SPY bars once and process them. Never loops or schedules."""
        with self.lock:
            # Honest pre-check exposure: what the desk had booked before this click (a broker fill
            # since the previous Check is not booked until now).
            before = self._protection_view()
            prev = (self.last_check or {}).get("utc") if getattr(self, "last_check", None) else None
            now = self.clock.on_check(self.calendar, self.minutes)
            since = None
            if prev:
                try:
                    since = round((now - parse_ts(prev)).total_seconds(), 1)
                except Exception:
                    since = None
            self._sync_mock_venue_clock(now)
            after = self.bars[-1]["ts_close"] if self.bars else None
            warm_start = after is None
            try:
                # The receipt time is this check's clock reading (mock: synthetic clock); a bar
                # never claims it arrived at its past close.
                new, warm_empty = self._fetch(after, now)
            except Exception as exc:
                self.last_check = {"utc": iso(now), "ok": False, "error": exc.__class__.__name__,
                                   "detail": str(exc)[:200], "bars": 0,
                                   "exposure_before_check": before, "since_previous_check_s": since}
                # The data feed failing does not stop the order side: book later fills and cover
                # uncovered shares anyway (reduce-only; never a new entry).
                self.last_check["orders"] = self._order_pass()
                self._desk_audit("check_bars_failed", **self.last_check)
                self._write_state()
                return dict(self.last_check, simulated=self.mock)
            received = iso(now)
            added = 0
            for b in new:
                if after is not None and parse_ts(b["ts_close"]) <= parse_ts(after):
                    continue
                row = dict(b)
                row.setdefault("symbol", A.SYMBOL)
                row["seq"] = len(self.bars) + 1
                row["delivered_ts"] = b.get("received_ts") or received
                S._append_jsonl(self._bars_file, row)
                self.bars.append(row)
                after = row["ts_close"]
                self._move_mock_market(row)
                self._step_one()
                added += 1
            lf = getattr(self.feed, "last_fetch", None) or {}
            self.last_check = {"utc": received, "ok": True, "bars": added, "clock": self.clock.name,
                               "source": self.data_label, "warm_start": warm_start,
                               "empty_slots": list(warm_empty or lf.get("empty_slots") or []),
                               "partial_slots": list(lf.get("partial_slots") or []),
                               "warmup": self.warmup_view(),
                               "exposure_before_check": before, "since_previous_check_s": since,
                               "fill_timing_note": FILL_TIMING_NOTE}
            # Even with zero new bars: book later fills of known orders, then cover the residual.
            self.last_check["orders"] = self._order_pass()
            self._desk_audit("check_bars", **self.last_check)
            self._write_state()
            return dict(self.last_check, bars_done=self.i, simulated=self.mock)

    def advance(self, n=1):
        # The replay "step" control maps to one manual check in Alpaca mode.
        return self.check_new_bars()

    def play(self, bars_per_sec=4.0):
        return {"ok": False, "reason": "NO_PLAY_IN_ALPACA_MODE",
                "detail": "bars arrive only when you click Check for new bars", "simulated": self.mock}

    # ---------------------------------------------------------------- sizing-only revision
    SIZING_CFG_KEYS = ("fixed_qty", "test_size", "limits")
    _REVISION_KEYS = ("label", "created_utc", "revision", "revised_utc", "revisions", "limits_source")

    @classmethod
    def _non_sizing(cls, cfg):
        out = {k: v for k, v in cfg.items() if k not in cls._REVISION_KEYS and k != "limits"}
        out["strategy_cfg"] = {k: v for k, v in (cfg.get("strategy_cfg") or {}).items()
                               if k not in cls.SIZING_CFG_KEYS}
        return out

    def _bind_session_config(self):
        """Alpaca restart with a new verified sizing snapshot (Codex 23:1xZ): the same state dir
        keeps every journal, the day's P&L, working orders and Stop; only sizing and limits are
        revised, recorded with the old values, and the desk starts DISARMED. The snapshot was
        already verified by resolve_limits (connected: operator-approved only). A change to the
        strategy, its non-sizing settings or the cost model is still refused, and the offline
        scenario keeps its immutable lock (the base class)."""
        path = os.path.join(self.state_dir, S.SESSION_CONFIG_FILE)
        if os.path.exists(path):
            with open(path) as fh:
                have = json.load(fh)
            want = S.session_config_for(self.strategy, self.strategy_cfg, self.limits)
            diff = S._config_diff({k: v for k, v in have.items() if k not in self._REVISION_KEYS}, want)
            if not diff:
                return have                                   # same config (revised or not): resume
            if self._non_sizing(have) == self._non_sizing(want):
                now = iso(_dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc))
                prior = {k: have.get(k) for k in ("strategy_cfg", "limits", "limits_source")}
                prior.update(revision=int(have.get("revision") or 0), bound_utc=have.get("revised_utc")
                             or have.get("created_utc"))
                src = {k: self.limits_source.get(k) for k in ("provenance", "hash", "approved_utc", "label")}
                rec = dict(want, created_utc=have.get("created_utc"), revised_utc=now,
                           revision=prior["revision"] + 1, limits_source=src,
                           revisions=list(have.get("revisions") or []) + [prior])
                tmp = path + ".tmp"
                with open(tmp, "w") as fh:
                    json.dump(rec, fh, indent=2, sort_keys=True)
                os.replace(tmp, path)
                S._append_jsonl(os.path.join(self.state_dir, "desk_audit.jsonl"), {
                    "ts_wall_utc": now, "kind": "session_config_revised", "simulated": self.mock,
                    "revision": rec["revision"], "diff": diff, "limits_source": src,
                    "kept": "journals, day P&L, working orders, Stop and adapter on/off state",
                    "armed_after": False})
                self.config_revision = {"revision": rec["revision"], "diff": diff, "revised_utc": now,
                                        "limits_source": src}
                return rec
        return S.SessionController._bind_session_config(self)

    def run_to_end(self):
        return self.play()

    def set_schedule(self, enabled=False):
        return {"ok": False, "reason": "NO_SCHEDULE_IN_ALPACA_MODE",
                "detail": "manual paper session only; no launchd, cron or background job", "simulated": self.mock}

    # ---------------------------------------------------------------- protection on every Check
    def _protection_view(self):
        """Booked position against shares covered by working reducing orders (protective stop,
        exit or close). Uncertain orders count as covering: they may be live, so never double-sell."""
        try:
            st = self.mgr.state()
        except Exception as exc:
            return {"available": False, "error": exc.__class__.__name__, "simulated": self.mock}
        pos = int(st["exposure"]["position_qty"] or 0)
        side = "sell" if pos > 0 else "buy"
        prot = sum(int(o.get("remaining") or 0) for o in st["protective_orders"] if o.get("side") == side)
        exits = sum(int(o.get("remaining") or 0) for o in st["exposure"]["working_orders"]
                    if o.get("kind") in ("exit", "close") and o.get("side") == side)
        covered = min(abs(pos), prot + exits) if pos else 0
        out = {"available": True, "position_qty": pos, "protective_qty": prot, "exit_working_qty": exits,
               "covered_qty": covered, "uncovered_qty": abs(pos) - covered,
               "stopped": bool(st["controls"]["stopped"]), "simulated": self.mock}
        if out["uncovered_qty"] > 0:
            out["warning"] = ("%d of %d booked SPY shares have no working protective stop or exit order"
                              % (out["uncovered_qty"], abs(pos)))
            ref = [x for x in self.mgr.intents.values()
                   if x.get("kind") == "protective" and x.get("status") == "rejected"]
            if ref:
                last = ref[-1]
                out["last_refusal"] = {"decision_id": last.get("decision_id"), "reason": last.get("reason")}
        return out

    def _ensure_protective(self, bar):
        """Residual-aware protective (Codex 23:00Z). The base attaches a stop only when NO protective
        exists, so a 1-to-4 share partial fill left 3 shares bare. Here: cover the uncovered residual
        only; nothing while Stop & Close owns the position or an exit/close is working; no duplicate
        (an open attempt counts as covering); a refused attempt is retried on a later Check at most
        three times, then the uncovered count stays on screen."""
        st = self.mgr.state()
        pos = int(st["exposure"]["position_qty"] or 0)
        if pos == 0:
            return
        if st["controls"]["stopped"] or st["controls"].get("close_pending"):
            return
        if any(o["kind"] in ("exit", "close") for o in st["exposure"]["working_orders"]):
            return
        pv = self._protection_view()
        if pv.get("uncovered_qty", 0) <= 0:
            return
        inval, it = self._entry_invalidation()
        if inval is None or it is None:
            self._desk_audit("alarm", code="NO_PROTECTIVE", detail="open position without an invalidation price",
                             uncovered_qty=pv["uncovered_qty"])
            return
        # Initial (nothing covered) and residual share one path: the first attempt keeps the
        # base id, a refused attempt is retried under a NEW id (|tryN), never the rejected one.
        if pv["covered_qty"] == 0:
            base = "protect|%s|%d" % (it["decision_id"], abs(pos))
        else:
            base = "protect|%s|%d|res%d" % (it["decision_id"], abs(pos), pv["covered_qty"])
        tries = [x for x in self.mgr.intents.values()
                 if x.get("decision_id") == base or str(x.get("decision_id", "")).startswith(base + "|try")]
        if any(x.get("status") in ("pending", "uncertain", "acked") for x in tries):
            return
        if len(tries) >= 3:
            self._desk_audit("alarm", code="PROTECTIVE_RESIDUAL_REFUSED", uncovered_qty=pv["uncovered_qty"],
                             detail="protective refused %d times; %d shares stay uncovered"
                                    % (len(tries), pv["uncovered_qty"]))
            return
        side = "sell" if pos > 0 else "buy"
        # Recheck the crossing on the price the venue will actually see (cent tick, safe side):
        # a long's sell stop at or above the last close (a short's buy stop at or below) would
        # trigger at once or be refused. Refuse here, visibly; the operator decides (Stop & Close).
        cent = cent_price(inval, side)
        last = bar.get("close") if bar else None
        if cent is not None and last is not None:
            crossed = (float(cent) >= float(last)) if side == "sell" else (float(cent) <= float(last))
            if crossed:
                self._desk_audit("alarm", code="PROTECTIVE_STOP_CROSSED", uncovered_qty=pv["uncovered_qty"],
                                 stop_level=float(inval), stop_on_tick=str(cent), last_close=float(last),
                                 detail="%s stop %s is already through the last close %.2f; not sent, "
                                        "%d shares uncovered; use Stop & Close to exit"
                                        % (side, cent, float(last), pv["uncovered_qty"]))
                return
        did = base if not tries else "%s|try%d" % (base, len(tries) + 1)
        self._desk_audit("protective_residual" if pv["covered_qty"] else "protective_initial",
                         position_qty=pos, covered_qty=pv["covered_qty"], residual_qty=pv["uncovered_qty"],
                         decision_id=did, stop_level=float(inval),
                         stop_on_tick=str(cent) if cent is not None else None)
        self.mgr.submit_intent({"decision_id": did, "kind": "protective", "side": side,
                                "qty": int(pv["uncovered_qty"]), "stop": float(inval),
                                "ref_price": float(bar["close"]),
                                "signal_ts": bar.get("delivered_ts") or bar.get("ts_close")})

    def _order_pass(self):
        """Every manual Check, even with zero new bars or a failed data fetch: book later fills of
        known orders (poll), then cover any uncovered shares (reduce-only). Never a new entry."""
        out = {}
        try:
            # step(None): the adapter's one read of open desk orders, with no bar recorded and no
            # mark moved (the per-bar path does the same read inside step(bar)).
            self.broker.step(None)
            res = self.mgr.poll()
            out["poll"] = {k: res.get(k) for k in ("events", "fills_booked", "duplicates", "connected")}
        except Exception as exc:
            out["poll_error"] = exc.__class__.__name__
        if self.bars:
            try:
                self._ensure_protective(self.bars[-1])
            except Exception as exc:
                out["protective_error"] = "%s: %s" % (exc.__class__.__name__, str(exc)[:160])
        out["protection"] = self._protection_view()
        out["latest_quote"] = getattr(self, "latest_quote", None)
        return out

    # ---------------------------------------------------------------- operator controls
    def _recovery(self):
        """(ambiguous, why). Ambiguous = the adapter cannot prove what the venue holds for a desk
        order (uncertain submit, incomplete listing, or a failed/incomplete reconcile)."""
        # Read the recovery facts directly: block_reason() reports ADAPTER_DISABLED first, which
        # would hide an unresolved submit or failed reconcile while the adapter is off.
        try:
            view = self.broker.recovery_view() if hasattr(self.broker, "recovery_view") else {}
        except Exception as exc:
            return True, "recovery check failed: %s" % exc.__class__.__name__
        if not (view.get("uncertain_client_ids") or view.get("listing_incomplete")
                or view.get("reconcile_blocking") or view.get("block_reason") == "RECOVERY_AMBIGUOUS"):
            return False, None
        parts = []
        if view.get("uncertain_client_ids"):
            parts.append("unresolved submit(s): %s" % ", ".join(view["uncertain_client_ids"]))
        if view.get("listing_incomplete"):
            parts.append("broker order listing incomplete")
        if view.get("reconcile_blocking"):
            parts.append("last reconcile not OK")
        return True, "; ".join(parts) or "recovery ambiguous"

    def alpaca_enable(self, confirm=False, by="operator (local desk)"):
        with self.lock:
            if confirm is not True:
                return {"ok": False, "reason": "CONFIRM_REQUIRED", "simulated": self.mock}
            amb, why = self._recovery()
            if amb:
                return {"ok": False, "reason": "RECOVERY_AMBIGUOUS", "detail": why, "simulated": self.mock}
            if self._controls()["stopped"]:
                return {"ok": False, "reason": "STOPPED", "detail": "Clear Stop first", "simulated": self.mock}
            self.adapter_state.enable(by=by)
            self._desk_audit("adapter_enable", by=by, mode=self.mode)
            self._write_state()
            return {"ok": True, "adapter": self.adapter_state.view(), "simulated": self.mock}

    def alpaca_disable(self, reason="OPERATOR"):
        with self.lock:
            self.adapter_state.disable(reason, by="operator (local desk)")
            self._desk_audit("adapter_disable", reason=reason)
            self._write_state()
            return {"ok": True, "adapter": self.adapter_state.view(), "simulated": self.mock}

    def stop_and_close(self, reason="OPERATOR"):
        try:
            return S.SessionController.stop_and_close(self, reason=reason)
        finally:
            self.adapter_state.disable("STOP: %s" % reason, by="desk Stop")
            self._write_state()

    def reconcile_now(self):
        """Read-only broker reconciliation. Allowed while disabled, paused or stopped."""
        with self.lock:
            res = self.mgr.reconcile(reason="operator")
            self._desk_audit("reconcile_now", result=res if isinstance(res, (dict, list, str)) else str(res))
            self._write_state()
            return {"ok": True, "result": res, "recovery": self._recovery_view(), "simulated": self.mock}

    def _recovery_view(self):
        amb, why = self._recovery()
        out = {"ambiguous": bool(amb), "reason": why}
        try:
            out.update(self.broker.recovery_view())
        except Exception:
            pass
        out["ambiguous"], out["reason"] = bool(amb), why
        out["simulated"] = self.mock
        return out

    def _sync_mock_venue_clock(self, now):
        """Mock only: the in-process venue's /v2/clock follows the synthetic desk clock."""
        trading = getattr(self.transport, "trading", None)
        if not self.mock or trading is None or not hasattr(trading, "clock"):
            return
        cal = self.calendar
        try:
            is_open = bool(cal.is_open(now))
            nxt_open = cal.next_open(now)
            day = cal.local_date(iso(now))
            b = cal.session_bounds(day) if cal.is_trading_day(day) else None
            nxt_close = b[1] if (b and now < b[1]) else cal.session_bounds(cal.local_date(iso(nxt_open)))[1]
            trading.clock = {"timestamp": iso(now), "is_open": is_open, "next_open": iso(nxt_open),
                             "next_close": iso(nxt_close)}
        except Exception:
            pass

    def _venue_clock_check(self, now):
        try:
            c = self.feed.clock()
        except Exception as exc:
            return {"check": "venue clock", "ok": False,
                    "detail": "venue clock unavailable (%s); no new exposure" % exc.__class__.__name__}
        skew = abs((parse_ts(c["timestamp"]) - now).total_seconds())
        ok = bool(c["is_open"]) and skew <= VENUE_CLOCK_SKEW_S
        return {"check": "venue clock", "ok": ok,
                "detail": "%s clock %s, market %s, skew %.0fs (limit %.0fs)" % (
                    "mock venue" if self.mock else "Alpaca paper", c["timestamp"],
                    "open" if c["is_open"] else "closed", skew, VENUE_CLOCK_SKEW_S)}

    def lab_view(self):
        if self.lab is not None and hasattr(self.lab, "view"):
            return self.lab.view()
        try:
            return importlib.import_module("lab").view(self.state_dir)
        except Exception:
            return {"ok": False, "reason": "LAB_NOT_AVAILABLE"}

    def lab_verify(self, forecast_id):
        try:
            return importlib.import_module("lab.verify").verify(self.state_dir, forecast_id)
        except ImportError:
            return {"ok": False, "reason": "LAB_NOT_AVAILABLE"}

    # ---------------------------------------------------------------- arming and state
    def _today(self):
        now = self.clock.now()
        day = self.calendar.local_date(iso(now)) if hasattr(self.calendar, "local_date") else now.date()
        return now, day if isinstance(day, _dt.date) else _dt.date.fromisoformat(str(day)[:10])

    def preflight(self):
        st = self.mgr.state()
        now, day = self._today()
        checks = []
        checks.append({"check": "adapter enabled", "ok": self.adapter_state.enabled,
                       "detail": "%s; %s" % (self.evidence_label, "enabled" if self.adapter_state.enabled
                                             else "disabled (%s)" % self.adapter_state.view()["disabled_reason"])})
        amb, why = self._recovery()
        checks.append({"check": "recovery unambiguous", "ok": not amb, "detail": why or "no unresolved submit"})
        checks.append({"check": "broker reconciled", "ok": not any(a.get("blocking", True) for a in st["alarms"]),
                       "detail": "alarms: %d" % len(st["alarms"])})
        checks.append({"check": "limits loaded", "ok": True,
                       "detail": "fixed %d share(s); max loss/trade $%.2f, notional $%.0f, daily loss $%.2f, "
                                 "gross $%.0f (%s)" % (int(self.strategy_cfg.get("fixed_qty") or 0),
                                                       self.limits["max_loss_per_trade"],
                                                       self.limits["per_trade_notional"], self.limits["daily_loss"],
                                                       self.limits["gross_exposure"],
                                                       self.limits_source.get("label") or self.limits["label"])})
        try:
            is_day = self.calendar.is_trading_day(day)
            bounds = self.calendar.session_bounds(day) if is_day else None
        except Exception as exc:
            is_day, bounds = False, None
            checks.append({"check": "calendar", "ok": False, "detail": "calendar: %s" % exc})
        else:
            open_ = bounds is not None and bounds[0] <= now + _dt.timedelta(minutes=60) and now < bounds[1]
            checks.append({"check": "calendar", "ok": bool(open_),
                           "detail": "%s %s (NYSE regular hours, America/New_York; clock %s)" % (
                               day.isoformat(), "session open" if open_ else "market closed now",
                               self.clock.name)})
        if self.mock:
            self._sync_mock_venue_clock(now)
        checks.append(self._venue_clock_check(now))
        wv = self.warmup_view()
        checks.append({"check": "strategy warm-up", "ok": True, "detail": wv["text"]})
        checks.append({"check": "stop", "ok": not st["controls"]["stopped"],
                       "detail": "Stop active (%s): only Clear Stop clears it" % st["controls"]["stop_reason"]
                       if st["controls"]["stopped"] else "no Stop active"})
        return checks

    def arm(self, session_id=None, expires_utc=None, auto=False):
        with self.lock:
            if auto:
                return {"ok": False, "reason": "NO_AUTO_ARM_IN_ALPACA_MODE", "simulated": self.mock}
            checks = self.preflight()
            failed = [c for c in checks if not c["ok"]]
            if failed:
                self._desk_audit("arm_refused", failed=failed)
                self._write_state()
                return {"ok": False, "reason": "PREFLIGHT", "failed": failed, "simulated": self.mock}
            now, day = self._today()
            end = self.calendar.session_bounds(day)[1]
            self.session_seq += 1
            sid = session_id or "%s-%s-%d" % (self.broker_mode, day.isoformat(), self.session_seq)
            exp = expires_utc or iso(end + _dt.timedelta(seconds=S.SESSION_GRACE_S))
            res = self.mgr.arm(session_id=sid, expires_utc=exp)
            if res.get("ok"):
                if self.mgr.state()["controls"]["paused"]:
                    self.mgr.resume()
                self.phase = "ARMED"
            self._desk_audit("arm", result=res, session_id=sid, expires_utc=exp)
            self._write_state()
            return res

    def session_state(self):
        sim = S.SessionController.session_state(self)
        word = "ALPACA MOCK" if self.mock else "ALPACA PAPER"
        sim["badge"] = sim["badge"].replace("SIMULATION", word)
        sim["external_broker_badge"] = ("EXTERNAL BROKER: NONE (in-process mock, synthetic ids)" if self.mock
                                        else "EXTERNAL BROKER: ALPACA PAPER (simulated account, no real money)")
        sim["broker_mode"] = self.broker_mode
        sim["evidence_label"] = self.evidence_label
        sim["data_label"] = self.data_label
        sim["adapter"] = self.adapter_state.view()
        sim["limits_source"] = dict(self.limits_source)
        sim["recovery"] = self._recovery_view()
        sim["last_check"] = self.last_check if hasattr(self, "last_check") else None
        sim["protection"] = dict(self._protection_view(), fill_timing_note=FILL_TIMING_NOTE)
        sim["latest_quote"] = getattr(self, "latest_quote", None)
        clock = getattr(self, "clock", None)
        sim["clock_utc"] = iso(clock.now()) if clock else None
        sim["schedule"] = {"enabled": False, "clock": clock.name if clock else None,
                           "calendar": "NYSE 2026-2027 (America/New_York; holidays and early closes)",
                           "note": "Manual paper session: bars arrive only when you click Check for new bars. "
                                   "No launchd, cron or background job; no auto-arm."}
        sim["broker"] = dict(sim["broker"], name=self.evidence_label, external=not self.mock,
                             book_file="alpaca_broker.json (adapter journal)",
                             transport=repr(self.transport))
        sim["fill_model"] = ("MOCK in-process fills on the synthetic path (open, low/high, close)" if self.mock
                             else "Alpaca paper simulator fills (not real money; not a live-fill claim)")
        sim["entry_pricing"] = ("buy entries are LIMIT orders bounded by the decision price and every cap "
                                "(rounded down to $0.01); opening a short is blocked")
        sim["bar_max_age_s"] = self.bar_max_age_s
        sim["warmup"] = self.warmup_view() if hasattr(self, "hist") else None
        sim["snapshot_error"] = self.snapshot_error
        lq = getattr(self, "latest_quote", None)
        sim["quote"] = (dict(lq, available=True, observed_at="last HTTPS BUY entry check") if lq else
                        {"available": False,
                         "detail": "no IEX quote read yet: the HTTPS path reads alpaca/readiness.py "
                                   "read_quote once per BUY candidate and holds the entry if it is "
                                   "invalid, crossed or stale; the mock path reads no quotes"})
        sim["simulated"] = self.mock
        return sim
