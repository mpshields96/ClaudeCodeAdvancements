"""Session runner for the offline paper desk (coordinator integration unit).

Replay only. Offline, in-process FakeBroker. Every fill is a mock fill and
every number is SIMULATED. Nothing here opens a network connection to a
broker or data vendor, reads a key, or places a real order. TradingView is
never an input: bars come from the synthetic fixture under tvbot/fixtures.

SessionController drives one replay bar at a time:

  1. broker.step(bar)   fills only orders that existed before this bar
  2. mgr.on_bar(bar)    intake guards, mark, simulated clock, expiry fail-safe
  3. bars.jsonl         gets the bar (the UI never sees bars past the replay clock)
  4. decide(...)        strategy decision from bars so far, logged to decisions.jsonl
  5. routing            when armed and not paused or stopped, an entry/exit decision
                        becomes an order intent (persisted by the order engine before
                        dispatch); every entry needs an invalidation price, and the
                        plain-dollar max loss is checked before the intent is sent
  6. protective stop    after an entry fills, a stop at the invalidation price
  7. session end        the calendar knows the session end in advance: one bar before
                        it, any open position gets a market exit; after the final bar
                        a flat session disarms, a non-flat one gets Stop & Close
  8. state files        session.json, ledger.jsonl and review.json, written atomically

Only clear_stop() clears a Stop. Restarting, the simulated schedule and session
expiry never do.
"""
import datetime as _dt
import json
import os
import sys
import threading
import time

DESK = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.dirname(DESK)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from orders import manager as _mgr_mod  # noqa: E402
from orders.manager import OrderManager  # noqa: E402
from orders import qty as Q  # noqa: E402
from orders.fake_broker import FakeBroker  # noqa: E402
from orders.calendar import SessionCalendar, parse_ts, iso  # noqa: E402
from orders.intake import check_bar, DEFAULT_MAX_AGE_S  # noqa: E402

try:
    from strategies.base import DEFAULT_COSTS as _COSTS  # noqa: E402
except Exception:  # pragma: no cover - mirrors tvbot/bot/engine.py DEFAULT_CONFIG
    _COSTS = {"kind": "bps", "half_spread_bps": 1.0, "slippage_bps": 2.0,
              "commission_per_share": 0.005, "commission_min": 1.0}
FILL_COSTS = dict(_COSTS)
FILL_MODEL = ("MOCK FILLS, SIMULATED. Market orders fill at the CLOSE of the first bar after the decision "
              "(the first price known to come after it), never at a price stamped before the order. Stops and "
              "limits fill inside the bar by the order engine's touch rules. Every fill price is moved against "
              "the order by half spread %.1f bps + slippage %.1f bps (limits never past their limit). Commission "
              "$%.3f a share, $%.2f minimum per fill. Assumptions mirrored from tvbot/bot/engine.py, not broker "
              "quotes." % (FILL_COSTS["half_spread_bps"], FILL_COSTS["slippage_bps"],
                           FILL_COSTS["commission_per_share"], FILL_COSTS["commission_min"]))
# Bars with these intake codes are not shown to the strategy and are not given to
# the fake broker. All but ZERO_VOLUME / OUT_OF_SESSION also restart the strategy's
# history (indicators re-warm) because the series is no longer continuous.
NO_RESET_CODES = ("ZERO_VOLUME", "OUT_OF_SESSION")
FIXED_QTY_LABEL = "HYPOTHETICAL FIXED %s-SHARE DEMO PRESET (TEST VALUE, not Matthew's sizing)"
# Used when the caller passes no strategy_cfg. Pass strategy_cfg={} for the strategy's own sizing
# (ema then sizes ~20 shares and the $10 TEST max loss refuses every entry, by design).
DEMO_STRATEGY_CFG = {"fixed_qty": 1}
# Real-market chart the operator may open beside the replay. REFERENCE ONLY: the desk
# replays synthetic bars and never reads TradingView data.
TRADINGVIEW_REFERENCE_SYMBOL = "AMEX:SPY"
TRADINGVIEW_REFERENCE_LABEL = ("AMEX:SPY REFERENCE ONLY. Real-market chart for context beside a SYNTHETIC replay; "
                               "the desk never reads TradingView data and its prices are not the replay's.")

FIXTURE = os.path.join(TVBOT, "fixtures", "normal_bars.jsonl")
DEFAULT_STATE_DIR = os.path.join(DESK, "state")
DEFAULT_STRATEGY = "ema"
LIMITS_LABEL = "TEST VALUES (not Matthew's limits; Matthew sets real ones)"
TEST_LIMITS = {
    "per_trade_notional": 2000.0,   # tvbot/config/smaller_size.json
    "max_loss_per_trade": 10.0,     # 0.5% of a $2,000 hypothetical balance
    "daily_loss": 30.0,             # 1.5% of a $2,000 hypothetical balance
    "gross_exposure": 2000.0,
    "label": LIMITS_LABEL,
}
DATA_LABEL = "SYNTHETIC FIXTURE BARS (no market data; not TradingView)"
BROKER_LABEL = "FakeBroker (offline, in-process)"
EXTERNAL_BROKER = "NONE (offline in-process fake broker)"
SESSION_GRACE_S = 300          # expiry fail-safe: session end + 5 minutes
MAX_PLAY_RATE = 50.0
PASS_RULE = ("Best reasoned pass = the pass decision with the most failed refusal checks "
             "recorded at decision time; ties go to the earliest ts_knowable. Chosen only from "
             "facts known when the pass was made. What happened afterwards is shown separately, "
             "labeled HYPOTHETICAL, and never counted in P&L.")


# --------------------------------------------------------------------- helpers
def _atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=Q.json_default_str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _atomic_jsonl(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=Q.json_default_str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _append_jsonl(path, row):
    with open(path, "a") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=Q.json_default_str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
    return out


def load_bars(path=FIXTURE):
    manifest, bars = None, []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            rec = json.loads(ln)
            if rec.get("type") == "manifest":
                manifest = rec
            elif rec.get("type") == "bar":
                bars.append(rec)
    return manifest, bars


def _qty_positive(v):
    """True for a positive exact quantity (whole or fractional); False for zero, negative or junk."""
    try:
        return Q.dec(Q.parse(v or 0, allow_zero=True)) > 0
    except Q.QtyError:
        return False


def _price(line_obj):
    if isinstance(line_obj, dict):
        return line_obj.get("price")
    if isinstance(line_obj, (int, float)):
        return float(line_obj)
    return None


def _cost_usd(d):
    est = d.get("est_cost")
    if isinstance(est, dict):
        return float(est.get("usd") or 0.0)
    if isinstance(est, (int, float)):
        return float(est)
    return 0.0


class DeskFakeBroker(FakeBroker):
    """The offline FakeBroker with the desk's labeled fill-cost model and its own
    persisted book. The book (orders, fills, exec ids, position, rng) is written to
    broker_state.json after every broker call, separately from the order engine's
    journal, so a full process restart sees the same simulated venue state."""

    def __init__(self, seed, persist_path=None, costs=None, exec_caps=None, **kw):
        FakeBroker.__init__(self, seed, **kw)
        self.costs = dict(costs or FILL_COSTS)
        self.persist_path = persist_path
        # Hard caps re-checked at the simulated execution price (gap protection).
        self.exec_caps = dict(exec_caps or {})
        self.exec_refusals = []

    # ---- execution-time cap (a gap between decision and fill must not breach a hard cap)
    def _opening_qty(self, order, remaining):
        pos = self._pos_qty
        if order["side"] == "buy":
            return remaining if pos >= 0 else max(0, remaining - abs(pos))
        return remaining if pos <= 0 else max(0, remaining - pos)

    def _refuse_over_cap(self, bar):
        """Cancel any exposure-increasing order whose fill at this bar's simulated price
        would exceed the per-trade notional or gross exposure cap. Reductions always pass."""
        per = self.exec_caps.get("per_trade_notional")
        gross_cap = self.exec_caps.get("gross_exposure")
        if per is None and gross_cap is None:
            return
        live = [o for o in sorted(self._orders.values(), key=lambda o: o["seq"]) if o["status"] == "working"]
        for order in live:
            timing = self._timing(order, bar) if hasattr(self, "_timing") else (False, None)
            if timing is None:
                continue
            raw = self._fill_price(order, bar, timing[0])
            if raw is None:
                continue
            px = self._with_costs(order, raw)
            remaining = order["qty"] - order["filled_qty"]
            opening = self._opening_qty(order, remaining)
            if opening <= 0:
                continue
            notional = opening * px
            others = sum(self._opening_qty(o, o["qty"] - o["filled_qty"]) for o in live
                         if o is not order and o["status"] == "working" and o["side"] == order["side"])
            gross_after = (abs(self._pos_qty) + opening + others) * px
            why = None
            if per is not None and notional > float(per) + 1e-9:
                why = "EXEC_NOTIONAL_OVER_CAP"
            elif gross_cap is not None and gross_after > float(gross_cap) + 1e-9:
                why = "EXEC_GROSS_OVER_CAP"
            if why is None:
                continue
            order["status"] = "canceled"
            order["cancel_reason"] = why
            rec = {"client_id": order["client_id"], "order_id": order["order_id"], "side": order["side"],
                   "qty": opening, "exec_price": px, "notional": round(notional, 6),
                   "gross_after": round(gross_after, 6), "per_trade_cap": per, "gross_cap": gross_cap,
                   "reason": why, "bar_ts_close": bar.get("ts_close"), "simulated": True,
                   "note": "refused at the simulated execution price; nothing filled"}
            self.exec_refusals.append(rec)
            self._emit({"type": "canceled", "client_id": order["client_id"], "order_id": order["order_id"],
                        "filled_qty": order["filled_qty"], "reason": why})

    # ---- fill model
    # The base FakeBroker decides WHETHER and at what bar price an order fills
    # (_timing / opened_before / reduce_only). The desk then applies its labeled
    # SIMULATED costs exactly once, in _apply_fill. The base's own half_spread_bps
    # and slip_bps stay 0 so costs are never applied twice.
    def _fill_price(self, order, bar, opened_before=False):
        """Raw bar price before costs. A market order fills at the bar's close (the first
        price after a decision made on the previous bar's close), never at its open."""
        if order["stop"] is None and order["limit"] is None:
            return float(bar["close"])
        return FakeBroker._fill_price(order, bar, opened_before)

    def _cost_bps(self):
        return float(self.costs["half_spread_bps"]) + float(self.costs["slippage_bps"])

    def _with_costs(self, order, raw):
        """The simulated execution price: raw moved against the order, kept inside a limit."""
        bps = self._cost_bps() / 1e4
        px = raw * (1.0 + bps) if order["side"] == "buy" else raw * (1.0 - bps)
        if order["limit"] is not None and order["stop"] is None:
            lim = float(order["limit"])
            px = min(px, lim) if order["side"] == "buy" else max(px, lim)
        return round(px, 6)

    def _apply_fill(self, order, qty, base_price, event_ts=None):
        fee = max(float(self.costs["commission_min"]), float(self.costs["commission_per_share"]) * qty)
        self.fee_per_fill, self.fee_per_unit = fee, 0.0
        raw = float(base_price)
        price = self._with_costs(order, raw)
        fill = FakeBroker._apply_fill(self, order, qty, price, event_ts=event_ts)
        bar = self._last_bar or {}
        market = order["limit"] is None and order["stop"] is None
        extra = {"report_ts": fill.get("report_ts") or fill.get("ts"),
                 "event_ts": bar.get("ts_close") if market else (fill.get("event_ts") or bar.get("ts_close")),
                 "event_window": [bar.get("ts_open"), bar.get("ts_close")],
                 "fill_model": "market@next-bar-close+cost" if market else "resting-order touch+cost",
                 "base_price": raw,
                 "half_spread_bps": float(self.costs["half_spread_bps"]),
                 "slip_bps": float(self.costs["slippage_bps"]),
                 "cost_bps": self._cost_bps(),
                 "price_basis": "SIMULATED: bar price moved against the order by half spread + slippage"
                                + (" (kept inside the limit)" if order["limit"] is not None and order["stop"] is None else "")}
        fill.update(extra)
        if order["fills"]:
            order["fills"][-1].update(extra)
        return fill

    # ---- persistence
    def snapshot(self):
        d = {}
        for k, v in self.__dict__.items():
            if k in ("rng", "persist_path"):
                continue
            d[k] = v
        st = self.rng.getstate()
        d["rng_state"] = [st[0], list(st[1]), st[2]]
        return json.loads(json.dumps(d, default=Q.json_default_str))

    def restore(self, d):
        d = dict(d)
        rs = d.pop("rng_state", None)
        for k, v in d.items():
            setattr(self, k, v)
        if rs:
            self.rng.setstate((rs[0], tuple(rs[1]), rs[2]))

    def persist(self):
        if self.persist_path:
            _atomic_json(self.persist_path, self.snapshot())

    def submit(self, *a, **kw):
        try:
            return FakeBroker.submit(self, *a, **kw)
        finally:
            self.persist()

    def cancel(self, *a, **kw):
        try:
            return FakeBroker.cancel(self, *a, **kw)
        finally:
            self.persist()

    def step(self, bar):
        try:
            if (bar.get("volume") or 0) > 0:
                self._last_bar = dict(bar)
                self._refuse_over_cap(bar)
            return FakeBroker.step(self, bar)
        finally:
            self.persist()


def strategy_names():
    try:
        from strategies.registry import STRATEGIES  # noqa: F401
        return sorted(STRATEGIES)
    except Exception:
        from strategies import engine
        return list(engine.EMA_KINDS) + list(engine.GOLD_KINDS) + ["cash"]


def _shadow_names():
    """Shadow (lab-only) strategies. They are never loadable as the active strategy."""
    names = {"challenger"}
    try:
        import lab  # noqa: F401
        names |= set(getattr(lab, "SHADOW", {}) or {})
    except Exception:
        pass
    return names


def load_strategy(name, cfg):
    """Return (source, decide). decide(bars_so_far, position, cfg) -> Decision."""
    if name in _shadow_names():
        raise ValueError("strategy %r is a shadow challenger for the decision lab only; it can never be "
                         "the active strategy (no auto-promotion)" % (name,))
    try:
        from strategies.registry import STRATEGIES
        if name in STRATEGIES:
            return "strategies.registry", STRATEGIES[name]
    except ImportError:
        pass
    from strategies import engine
    known = set(engine.EMA_KINDS) | set(engine.GOLD_KINDS) | {"cash"}
    if name not in known:
        raise ValueError("unknown strategy %r (known: %s)" % (name, ", ".join(sorted(known))))
    rep = engine.Replayer(name, cfg)

    def decide(bars_so_far, position, _cfg, _rep=rep):
        # The Replayer keeps its own research book; the desk routes from the
        # order engine's actual position, never from the Replayer's.
        return _rep.step(bars_so_far[-1])
    return "strategies.engine.Replayer (registry not present)", decide


# ------------------------------------------------------------------ session config lock
SESSION_CONFIG_FILE = "session_config.json"
SESSION_CONFIG_FORMAT = "desk-session-config-1"
_STATE_MARKERS = ("progress.json", "broker_state.json", "decisions.jsonl", "ledger.jsonl", "intents.jsonl")


class SessionConfigChanged(RuntimeError):
    """Refused: a state dir is bound to one strategy, sizing, limit set and cost model."""


def _norm(obj):
    return json.loads(json.dumps(obj, sort_keys=True, default=Q.json_default_str))


def session_config_for(strategy, strategy_cfg, limits):
    return _norm({"format": SESSION_CONFIG_FORMAT, "strategy": strategy, "strategy_cfg": strategy_cfg,
                  "limits": limits, "fill_costs": FILL_COSTS,
                  "label": "TEST VALUES, SIMULATED. Sizing and limits are fixed for this state dir. "
                           "Matthew alone sets real sizing and limits."})


def _config_diff(old, new):
    keys = sorted(set(old) | set(new))
    return {k: {"recorded": old.get(k), "requested": new.get(k)} for k in keys
            if k not in ("label", "created_utc") and old.get(k) != new.get(k)}


# ------------------------------------------------------------------ controller
class SessionController(object):
    def __init__(self, state_dir=DEFAULT_STATE_DIR, strategy=DEFAULT_STRATEGY, bars_path=FIXTURE,
                 broker_seed=20261115, faults=None, limits=None, strategy_cfg=None, simulated=True):
        # The value desk rows, session.json, progress.json and the review/status views record as
        # "simulated". The replay desk and paper keep True; only live passes False.
        if not isinstance(simulated, bool):
            raise ValueError("simulated must be True or False")
        self.simulated = simulated
        self.state_dir = os.path.abspath(state_dir)
        os.makedirs(self.state_dir, exist_ok=True)
        self.lock = threading.RLock()
        self.manifest, self.bars = self._load_bars(bars_path)
        self.symbol = (self.manifest or {}).get("symbol") or (self.bars[0]["symbol"] if self.bars else "SYNTH")
        self.minutes = int((self.manifest or {}).get("timeframe_minutes") or 60)
        self.calendar = self._make_calendar()
        self.strategy = strategy
        self.strategy_cfg = dict(DEMO_STRATEGY_CFG if strategy_cfg is None else strategy_cfg)
        self.strategy_source, self.decide = load_strategy(strategy, self.strategy_cfg)
        self.limits = dict(limits or TEST_LIMITS)
        self.session_config = self._bind_session_config()
        self.broker, self.broker_restored = self._make_broker(broker_seed, faults)
        self.broker.exec_caps = {k: self.limits.get(k) for k in ("per_trade_notional", "gross_exposure")}
        if not isinstance(getattr(self.broker, "exec_refusals", None), list):
            self.broker.exec_refusals = []
        mgr_limits = {k: self.limits[k] for k in _mgr_mod.LIMIT_KEYS if k in self.limits}
        for k in _mgr_mod.LIMIT_KEYS:
            mgr_limits.setdefault(k, self.limits.get(k))
        mgr_limits["label"] = self.limits.get("label", LIMITS_LABEL)
        if self.limits.get("max_daily_entries") is not None:     # optional DAILY_ENTRY_LIMIT
            mgr_limits["max_daily_entries"] = self.limits["max_daily_entries"]
        if "max_loss_per_trade" in _mgr_mod.LIMIT_KEYS:
            mgr_limits["max_loss_per_trade"] = self.limits["max_loss_per_trade"]
        self.engine_checks_max_loss = "max_loss_per_trade" in _mgr_mod.LIMIT_KEYS
        self.mgr = OrderManager(self.state_dir, self.broker, mgr_limits, symbol=self.symbol,
                                calendar=self.calendar, strategy=strategy, data_label=self.data_label,
                                bar_max_age_s=self.bar_max_age_s)
        self.paths = {k: os.path.join(self.state_dir, v) for k, v in {
            "session": "session.json", "bars": "bars.jsonl", "decisions": "decisions.jsonl",
            "ledger": "ledger.jsonl", "review": "review.json", "progress": "progress.json",
            "desk_audit": "desk_audit.jsonl"}.items()}
        prog = {}
        if os.path.exists(self.paths["progress"]):
            try:
                with open(self.paths["progress"]) as fh:
                    prog = json.load(fh)
            except ValueError:
                prog = {}
        if prog and prog.get("strategy") not in (None, strategy):
            raise RuntimeError("state dir %s was run with strategy %r; use a fresh --state-dir"
                               % (self.state_dir, prog.get("strategy")))
        self.i = int(prog.get("bars_done", 0))
        self.phase = prog.get("phase") or "PRE_SESSION"
        self.session_seq = int(prog.get("session_seq", 0))
        self.restarts = int(prog.get("restarts", -1)) + 1
        self.seen = self.bars[:self.i]
        # Rebuild the trusted strategy history deterministically from the same intake rules.
        self.hist, self._intake_prev, self.intake_log = [], None, []
        for b in self.seen:
            self._intake(b)
        self.decisions = _read_jsonl(self.paths["decisions"])
        self._stop_play = threading.Event()
        self._play_thread = None
        self.play_rate = None
        if self.i and self.restarts:
            # The fake broker's book was restored from broker_state.json (its own file),
            # so the order engine's start-up reconciliation compares against the same
            # simulated venue a real broker would still hold.
            self._desk_audit("restart", bars_done=self.i, broker_restored=self.broker_restored,
                             note="fake broker book restored from its own state file; order engine reconciled "
                                  "on start")
            if self.seen:
                self.mgr.on_bar(self.seen[-1])
            self.mgr.reconcile(reason="restart")
        self._write_state()

    # ------------------------------------------------------ subclass hooks
    # The offline replay desk uses these defaults unchanged; desk/alpaca_session.py
    # overrides them for the opt-in Alpaca paper adapter.
    data_label = DATA_LABEL
    bar_max_age_s = DEFAULT_MAX_AGE_S
    fixed_qty_label = FIXED_QTY_LABEL

    def _load_bars(self, bars_path):
        return load_bars(bars_path)

    def _make_calendar(self):
        return SessionCalendar.fixture_profile()

    def _make_broker(self, broker_seed, faults):
        broker_path = os.path.join(self.state_dir, "broker_state.json")
        broker = DeskFakeBroker(broker_seed, persist_path=broker_path, faults=faults, symbol=self.symbol)
        restored = False
        if os.path.exists(broker_path):
            with open(broker_path) as fh:
                broker.restore(json.load(fh))
            restored = True
        return broker, restored

    def _row_flags(self):
        """Evidence flags written on every bars.jsonl / decisions.jsonl row."""
        return {"simulated": self.simulated}

    def _lab_observe(self, bar, d):
        """Called after the decision is recorded and before it is routed (no-op offline)."""
        return None

    def _entry_bounds(self, d, bar, st, qty, side, entry, inval):
        """Return (limit_price_or_None, refusal_or_None). Offline: unpriced, no refusal."""
        return None, None

    def _intake_max_age(self, bar):
        return self.bar_max_age_s

    def _warmup_only(self, bar):
        """True for a valid closed bar that may warm strategy features but must never be routed."""
        return False

    def _ledger_flags(self):
        return {"mock_fills": True}

    def _warmup_step(self, bar):
        """A valid but late (catch-up) bar warms the strategy's history only. It never reaches the
        broker, the strategy is not asked to trade on it, and working entries are cancelled.
        Calendar-driven exits (EOD flatten, session end) still run: they only reduce exposure."""
        cancelled = self.mgr._cancel_kinds(["entry"])
        self.i += 1
        self.seen.append(bar)
        _append_jsonl(self.paths["bars"], dict(bar, trusted=True, warmup_only=True, **self._row_flags()))
        try:
            late_s = int((parse_ts(bar["delivered_ts"]) - parse_ts(bar["ts_close"])).total_seconds())
        except (KeyError, TypeError, ValueError):
            late_s = None
        d = {"decision_id": "dec-warmup-%d" % self.i, "action": "pass", "qty": 0,
             "reason_code": "WARMUP_ONLY_LATE_BAR",
             "reason_text": "valid closed bar fetched %ss after its close (trading limit %ds): it warms "
                            "strategy history only; never routed, no order" % (late_s, int(self.bar_max_age_s)),
             "refusal_checks": [{"id": "FRESH_FOR_TRADING", "passed": False,
                                 "detail": "received %s, closed %s" % (bar.get("delivered_ts"), bar.get("ts_close"))}],
             "ts_knowable": bar.get("delivered_ts"), "bar_seq": bar.get("seq"), "bar_ts_close": bar.get("ts_close"),
             "warmup": {"history_bars": len(self.hist)},
             "routing": {"status": "no_order", "why": "WARMUP_ONLY",
                         "entries_cancelled": len((cancelled or ([],))[0])}}
        d.update(self._row_flags())
        _append_jsonl(self.paths["decisions"], d)
        self.decisions.append(d)
        self._desk_audit("warmup_bar", bar_seq=bar.get("seq"), late_s=late_s, history_bars=len(self.hist))
        self._session_roles(bar)

    def _intake(self, bar):
        """Run the intake guard on a delivered bar. Returns (ok, code, detail).
        A failed bar never reaches the fake broker or the strategy."""
        ok, code, detail = check_bar(bar, self._intake_prev, self.calendar, max_age_s=self._intake_max_age(bar))
        if ok:
            # A completed bar's high/low/close are not knowable before ts_close. Refuse a bar
            # whose receipt time is earlier than its close (reviewer case: fresh exchange_ts and
            # receipt 58m59s before the stated close let a limit fill at the future low).
            try:
                recv = bar.get("delivered_ts")
                early = recv is None or parse_ts(recv) < parse_ts(bar["ts_close"])
            except (ValueError, TypeError, KeyError):
                early = True
            if early:
                ok, code = False, "NOT_CLOSED_AT_RECEIPT"
                detail = dict(detail or {}, received=bar.get("delivered_ts"), ts_close=bar.get("ts_close"),
                              rule="receipt must be at or after the bar close before its OHLC is used")
        if code not in ("BAD_BAR", "OUT_OF_ORDER"):
            self._intake_prev = bar
        if ok:
            self.hist.append(bar)
        elif code not in NO_RESET_CODES:
            self.hist = []
        self.intake_log.append({"seq": bar.get("seq"), "ts_open": bar.get("ts_open"), "ok": ok, "code": code})
        if len(self.intake_log) > 200:
            del self.intake_log[:-200]
        return ok, code, detail

    # ------------------------------------------------------------ bookkeeping
    def _exec_alarms(self):
        return [{"code": r["reason"], "severity": "warn", "blocking": False, "simulated": self.simulated,
                 "detail": "%s %d at simulated %.4f = $%.2f; caps per-trade $%s, gross $%s; refused, nothing filled"
                           % (r["side"], r["qty"], r["exec_price"], r["notional"], r["per_trade_cap"], r["gross_cap"]),
                 "client_id": r["client_id"], "bar_ts_close": r["bar_ts_close"]}
                for r in self.broker.exec_refusals]

    def _bind_session_config(self):
        """Bind strategy, sizing, TEST limits and fill costs to this state dir, once.

        Runs before the fake broker or the order engine touch the state dir. A later
        start with different values (CLI flags included) is refused, never applied
        mid-session: the operator starts a clearly labeled fresh scenario instead."""
        path = os.path.join(self.state_dir, SESSION_CONFIG_FILE)
        want = session_config_for(self.strategy, self.strategy_cfg, self.limits)
        audit = os.path.join(self.state_dir, "desk_audit.jsonl")
        now = iso(_dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc))
        fresh_hint = ("Start a clearly labeled fresh scenario instead: launch.py --fresh (the old state dir "
                      "is renamed aside, never deleted) or a new --state-dir.")
        if os.path.exists(path):
            with open(path) as fh:
                have = json.load(fh)
            diff = _config_diff(have, want)
            if diff:
                _append_jsonl(audit, {"ts_wall_utc": now, "kind": "session_config_change_refused",
                                      "simulated": self.simulated, "diff": diff})
                raise SessionConfigChanged(
                    "REFUSED: %s is bound to its recorded session config; this start asked to change %s. "
                    "Recorded vs requested: %s. Sizing, limits, strategy and costs never change inside a "
                    "session. %s" % (self.state_dir, ", ".join(sorted(diff)),
                                     json.dumps(diff, sort_keys=True), fresh_hint))
            return have
        used = [m for m in _STATE_MARKERS if os.path.exists(os.path.join(self.state_dir, m))]
        if used:
            _append_jsonl(audit, {"ts_wall_utc": now, "kind": "session_config_missing_refused",
                                  "simulated": self.simulated, "existing": used})
            raise SessionConfigChanged(
                "REFUSED: %s already holds session state (%s) but no %s, so its sizing and limits "
                "can't be shown to match this start. %s" % (self.state_dir, ", ".join(used),
                                                            SESSION_CONFIG_FILE, fresh_hint))
        rec = dict(want, created_utc=now)
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(rec, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
        _append_jsonl(audit, {"ts_wall_utc": now, "kind": "session_config_bound", "simulated": self.simulated,
                              "strategy": self.strategy, "strategy_cfg": want["strategy_cfg"],
                              "limits": want["limits"], "fill_costs": want["fill_costs"]})
        return rec

    def _desk_audit(self, kind, **fields):
        rec = {"ts_wall_utc": iso(_dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc)),
               "ts_sim_utc": self.replay_clock(), "kind": kind, "simulated": self.simulated}
        rec.update(fields)
        _append_jsonl(self.paths["desk_audit"], rec)

    def replay_clock(self):
        if not self.seen:
            return None
        b = self.seen[-1]
        return b.get("delivered_ts") or b.get("ts_close")

    def _day(self, bar):
        return self.calendar.local_date(parse_ts(bar["ts_open"]))

    def _session_end(self, bar):
        t = parse_ts(bar["ts_open"])
        for start, end in self.calendar.windows(self._day(bar)):
            if start <= t < end:
                return end
        return None

    def _bar_role(self, bar):
        """'last' if this bar closes at the session end, 'flatten' if the next
        bar is the last one, else 'open'. Uses the calendar only (known in advance)."""
        end = self._session_end(bar)
        if end is None:
            return "outside"
        close = parse_ts(bar["ts_close"])
        if close >= end:
            return "last"
        if close + _dt.timedelta(minutes=self.minutes) >= end:
            return "flatten"
        return "open"

    def _controls(self):
        return self.mgr.state()["controls"]

    # --------------------------------------------------------------- controls
    def preflight(self):
        st = self.mgr.state()
        nxt = self.bars[self.i] if self.i < len(self.bars) else None
        checks = []
        if nxt is None:
            checks.append({"check": "data", "ok": False, "detail": "replay finished: no bars left"})
        else:
            checks.append({"check": "data", "ok": True,
                           "detail": "next replay bar %s (%s)" % (nxt["ts_open"], self.data_label)})
        checks.append({"check": "broker reconciled", "ok": not any(a.get("blocking", True) for a in st["alarms"]),
                       "detail": "%s; alarms: %d" % (BROKER_LABEL, len(st["alarms"]))})
        checks.append({"check": "limits loaded", "ok": True,
                       "detail": "max loss/trade $%.2f, notional $%.0f, daily loss $%.2f, gross $%.0f (%s)" % (
                           self.limits["max_loss_per_trade"], self.limits["per_trade_notional"],
                           self.limits["daily_loss"], self.limits["gross_exposure"], self.limits["label"])})
        if nxt is not None:
            is_day = self.calendar.is_trading_day(self._day(nxt))
            checks.append({"check": "calendar", "ok": bool(is_day),
                           "detail": "%s on %s calendar (fixture hours, UTC 14:30-21:30)" % (
                               "trading day" if is_day else "not a trading day", self._day(nxt))})
            end = self._session_end(nxt)
            checks.append({"check": "mode and expiry", "ok": end is not None,
                           "detail": "REPLAY (OFFLINE, SIMULATED); session ends %s, expiry fail-safe %s" % (
                               iso(end) if end else "?",
                               iso(end + _dt.timedelta(seconds=SESSION_GRACE_S)) if end else "?")})
        checks.append({"check": "stop", "ok": not st["controls"]["stopped"],
                       "detail": "Stop active (%s): only Clear Stop clears it" % st["controls"]["stop_reason"]
                       if st["controls"]["stopped"] else "no Stop active"})
        return checks

    def arm(self, session_id=None, expires_utc=None, auto=False):
        with self.lock:
            checks = self.preflight()
            failed = [c for c in checks if not c["ok"]]
            if failed:
                self._desk_audit("arm_refused", failed=failed, auto=auto)
                self._write_state()
                return {"ok": False, "reason": "PREFLIGHT", "failed": failed, "simulated": self.simulated}
            nxt = self.bars[self.i]
            end = self._session_end(nxt)
            self.session_seq += 1
            sid = session_id or "replay-%s-%d" % (self._day(nxt), self.session_seq)
            exp = expires_utc or iso(end + _dt.timedelta(seconds=SESSION_GRACE_S))
            res = self.mgr.arm(session_id=sid, expires_utc=exp)
            if res.get("ok"):
                if self.mgr.state()["controls"]["paused"]:
                    self.mgr.resume()
                self.phase = "ARMED"
            self._desk_audit("arm", result=res, auto=auto, session_id=sid, expires_utc=exp)
            self._write_state()
            return res

    def pause(self):
        with self.lock:
            self.stop_play()
            res = self.mgr.pause(reason="OPERATOR")
            if not self._controls()["stopped"]:
                self.phase = "PAUSED"
            self._write_state()
            return res

    def resume(self):
        with self.lock:
            res = self.mgr.resume()
            if res.get("ok"):
                self.phase = "ARMED" if self.mgr.state()["armed"] else "PRE_SESSION"
            self._write_state()
            return res

    def stop_and_close(self, reason="OPERATOR"):
        with self.lock:
            self.stop_play()
            res = self.mgr.stop_and_close(reason=reason)
            self.phase = "STOPPED"
            self._desk_audit("stop_and_close", reason=reason, result=res)
            self._write_state()
            return res

    def clear_stop(self, confirm=False):
        with self.lock:
            if confirm is not True:
                return {"ok": False, "reason": "CONFIRM_REQUIRED", "simulated": self.simulated}
            res = self.mgr.clear_stop(confirm=True)
            if res.get("ok"):
                self.phase = "PRE_SESSION"
            self._desk_audit("clear_stop", result=res)
            self._write_state()
            return res

    def set_schedule(self, enabled=False):
        with self.lock:
            res = self.mgr.enable_schedule(bool(enabled))
            self._desk_audit("schedule", enabled=bool(enabled), result=res)
            self._write_state()
            return res

    def close_session(self):
        with self.lock:
            st = self.mgr.state()
            if st["exposure"]["position_qty"] != 0 or st["exposure"]["working_orders"]:
                return {"ok": False, "reason": "NOT_FLAT", "simulated": self.simulated}
            self.stop_play()
            self.mgr.disarm(reason="CLOSE_SESSION")
            self.phase = "CLOSED"
            self._desk_audit("close_session")
            self._write_state()
            return {"ok": True, "simulated": self.simulated}

    # ---------------------------------------------------------------- replay
    def advance(self, n=1):
        with self.lock:
            done = 0
            for _ in range(max(0, int(n))):
                if self.i >= len(self.bars):
                    break
                self._step_one()
                done += 1
            self._write_state()
            return {"ok": True, "bars_advanced": done, "bars_done": self.i, "simulated": self.simulated}

    def play(self, bars_per_sec=4.0):
        rate = max(0.1, min(float(bars_per_sec or 4.0), MAX_PLAY_RATE))
        with self.lock:
            self.stop_play()
            self._stop_play.clear()
            self.play_rate = rate

            def run():
                while not self._stop_play.is_set():
                    with self.lock:
                        if self.i >= len(self.bars) or self._controls()["stopped"]:
                            break
                        self._step_one()
                        self._write_state()
                    self._stop_play.wait(1.0 / rate)
                with self.lock:
                    self.play_rate = None
                    self._write_state()
            self._play_thread = threading.Thread(target=run, name="desk-play", daemon=True)
            self._play_thread.start()
            return {"ok": True, "bars_per_sec": rate, "simulated": self.simulated}

    def stop_play(self):
        t = self._play_thread
        self._stop_play.set()
        if t is not None and t is not threading.current_thread() and t.is_alive():
            # Release our lock while the thread finishes its current bar.
            try:
                self.lock.release()
                released = True
            except RuntimeError:
                released = False
            t.join(timeout=5)
            if released:
                self.lock.acquire()
        self._play_thread = None
        self.play_rate = None

    def run_to_end(self):
        return self.advance(len(self.bars) - self.i)

    def _step_one(self):
        bar = self.bars[self.i]
        prev = self.seen[-1] if self.seen else None
        new_day = prev is None or self._day(prev) != self._day(bar)
        ctl = self._controls()
        if new_day:
            if self.phase == "CLOSED":
                self.phase = "PRE_SESSION"
            if ctl["schedule_enabled"] and not ctl["stopped"] and not self.mgr.state()["armed"]:
                self.arm(auto=True)    # simulated clock only; refuses while a Stop is active
        # Intake guard FIRST: a bar that fails it never reaches the fake broker (so no
        # order can fill on it) or the strategy, and working entries are cancelled.
        ok, code, detail = self._intake(bar)
        if not ok:
            cancelled = self.mgr._cancel_kinds(["entry"])
            self.mgr.on_bar(bar)                 # order engine records its own BAR_ alarm
            self.i += 1
            self.seen.append(bar)
            _append_jsonl(self.paths["bars"], dict(bar, trusted=False, intake=code, **self._row_flags()))
            ts_k = bar.get("delivered_ts") or bar.get("ts_close")
            d = {"decision_id": "dec-rejected-%s-%d" % (code, self.i), "action": "pass", "qty": 0,
                 "reason_code": "DATA_REJECTED_" + str(code),
                 "reason_text": "bar failed intake (%s); not shown to the strategy or the fake broker%s"
                                % (code, "" if code in NO_RESET_CODES else "; strategy history restarts"),
                 "refusal_checks": [{"id": "DATA_" + str(code), "passed": False,
                                     "detail": (detail or {}).get("msg") if isinstance(detail, dict) else detail}],
                 "ts_knowable": ts_k, "bar_seq": bar.get("seq"), "bar_ts_close": bar.get("ts_close"),
                 "routing": {"status": "no_order", "why": "DATA_REJECTED",
                             "entries_cancelled": len((cancelled or ([],))[0])}}
            d.update(self._row_flags())
            _append_jsonl(self.paths["decisions"], d)
            self.decisions.append(d)
            self._desk_audit("data_rejected", code=code, bar_seq=bar.get("seq"),
                             entries_cancelled=d["routing"]["entries_cancelled"])
            self._session_roles(bar)
            return
        if self._warmup_only(bar):
            self._warmup_step(bar)
            return
        n_ref = len(self.broker.exec_refusals)
        self.broker.step(bar)
        for rec in self.broker.exec_refusals[n_ref:]:
            self._desk_audit("alarm", code=rec["reason"], severity="warn", bar_seq=bar.get("seq"), **{
                k: v for k, v in rec.items() if k not in ("reason",)})
        self.mgr.on_bar(bar)
        self.i += 1
        self.seen.append(bar)
        _append_jsonl(self.paths["bars"], dict(bar, trusted=True, **self._row_flags()))
        self._ensure_protective(bar)
        st = self.mgr.state()
        pos = st["exposure"]["position_qty"]
        position = {"qty": pos, "avg_price": st["exposure"]["avg_price"]}
        cfg = dict(self.strategy_cfg, now=bar.get("delivered_ts") or bar.get("ts_close"))
        try:
            d = dict(self.decide(list(self.hist), position, cfg))
        except Exception as exc:  # a strategy fault must not trade
            d = {"decision_id": "dec-error-%d" % bar.get("seq", self.i), "action": "pass", "qty": 0,
                 "reason_code": "STRATEGY_ERROR", "reason_text": "strategy raised %s" % exc,
                 "refusal_checks": [{"id": "STRATEGY_ERROR", "passed": False, "detail": str(exc)}],
                 "ts_knowable": bar.get("delivered_ts") or bar.get("ts_close")}
        d.setdefault("bar_seq", bar.get("seq"))
        d.setdefault("bar_ts_close", bar.get("ts_close"))
        fq = self.strategy_cfg.get("fixed_qty")
        if fq and str(d.get("action", "")).startswith(("enter", "add")) and _qty_positive(d.get("qty")):
            # HYPOTHETICAL fixed-quantity demo preset (TEST). Exits stay capped at the real position.
            # Exact: an int stays an int, a fraction stays that fraction (never rounded to a share).
            d["engine_qty"] = d.get("qty")
            d["qty"] = Q.to_json(Q.parse(fq))
            d["qty_basis"] = self.fixed_qty_label % Q.text(Q.parse(fq))
        d.update(self._row_flags())
        self._lab_observe(bar, d)
        d["routing"] = self._route(d, bar, st)
        _append_jsonl(self.paths["decisions"], d)
        self.decisions.append(d)
        self._session_roles(bar)

    def _session_roles(self, bar):
        """Calendar-driven actions (EOD flatten, session end). They depend on the
        clock, not on the bar's prices, so they also run on a rejected bar."""
        role = self._bar_role(bar)
        st = self.mgr.state()
        if role == "flatten" and st["exposure"]["position_qty"] != 0:
            self._eod_exit(bar, st)
        if role == "last":
            st = self.mgr.state()
            if st["armed"] or st["exposure"]["position_qty"] != 0:
                if st["exposure"]["position_qty"] == 0 and not st["exposure"]["working_orders"]:
                    self.mgr.disarm(reason="SESSION_END")
                    self._cancel_protectives()
                    self.phase = "CLOSED"
                    self._desk_audit("session_end", flat=True)
                else:
                    self.stop_and_close(reason="SESSION_END_NOT_FLAT")
            elif not st["controls"]["stopped"]:
                self.phase = "CLOSED"

    def _route(self, d, bar, st):
        action = d.get("action")
        qty = d.get("qty") or 0
        if action not in ("enter_long", "enter_short", "exit") or qty <= 0 and action != "exit":
            return {"status": "no_order", "why": "decision is %s" % action}
        ctl = st["controls"]
        if not st["armed"]:
            return {"status": "not_routed", "why": "NOT_ARMED (decision recorded only)"}
        if ctl["stopped"]:
            return {"status": "not_routed", "why": "STOPPED"}
        pos = st["exposure"]["position_qty"]
        ref = float(bar["close"])
        if action == "exit":
            if pos == 0:
                return {"status": "not_routed", "why": "NOTHING_TO_EXIT (order engine position is flat)"}
            self._cancel_protectives()
            side = "sell" if pos > 0 else "buy"
            iid = self.mgr.submit_intent({"decision_id": d["decision_id"], "kind": "exit", "side": side,
                                          "qty": abs(pos), "ref_price": ref,
                                          "signal_ts": d.get("ts_knowable")})
            return self._intent_result(iid)
        if ctl["paused"]:
            return {"status": "not_routed", "why": "PAUSED"}
        qv = Q.parse(qty)
        if Q.is_fractional(qv) and not getattr(self.broker, "fractional", False):
            # Fractional orders need a connected Alpaca desk whose broker was built for them. The
            # offline desk and a whole-share broker refuse; the size is never rounded to a share.
            return self._desk_reject(d, "FRACTIONAL_NOT_ENABLED",
                                     "a %s-share entry needs a connected Alpaca desk built for fractional "
                                     "DAY simple orders; this desk's broker is not" % Q.text(qv))
        entry = _price(d.get("intended_entry")) or ref
        inval = _price(d.get("invalidation"))
        if inval is None:
            return self._desk_reject(d, "NO_STOP", "entry has no invalidation price")
        risk = qty * abs(entry - float(inval)) + _cost_usd(d)
        if not self.engine_checks_max_loss and risk > self.limits["max_loss_per_trade"]:
            return self._desk_reject(d, "MAX_LOSS", "qty %s x |%.4f - %.4f| + cost $%.2f = $%.2f > max loss $%.2f (%s)"
                                     % (Q.text(qv), entry, float(inval), _cost_usd(d), risk,
                                        self.limits["max_loss_per_trade"], self.limits["label"]))
        side = "buy" if action == "enter_long" else "sell"
        limit, refusal = self._entry_bounds(d, bar, st, Q.to_json(qv), side, entry, float(inval))
        if refusal:
            return self._desk_reject(d, refusal[0], refusal[1])
        intent = {"decision_id": d["decision_id"], "kind": "entry", "side": side,
                  "qty": Q.to_json(qv), "ref_price": ref, "signal_ts": d.get("ts_knowable"),
                  "invalidation": float(inval), "max_loss_usd": round(risk, 4)}
        if limit is not None:
            intent["limit"] = float(limit)
        iid = self.mgr.submit_intent(intent)
        res = self._intent_result(iid)
        if limit is not None:
            res["limit"] = float(limit)
        res["risk_usd"] = round(risk, 4)
        res["invalidation"] = float(inval)
        return res

    def _intent_result(self, iid):
        it = self.mgr.intents.get(iid, {})
        out = {"status": it.get("status"), "intent_id": iid}
        if it.get("reason"):
            out["why"] = it["reason"]
        return out

    def _desk_reject(self, d, code, detail):
        d.setdefault("refusal_checks", []).append({"id": code, "passed": False, "detail": detail})
        self._desk_audit("rejected", decision_id=d.get("decision_id"), reason=code, detail=detail)
        return {"status": "rejected", "why": code, "detail": detail, "by": "desk risk check"}

    def _entry_invalidation(self):
        """Invalidation of the latest filled entry (from its decision)."""
        for it in reversed(list(self.mgr.intents.values())):
            if it.get("kind") == "entry" and it.get("filled_qty", 0) > 0:
                for d in reversed(self.decisions):
                    if d.get("decision_id") == it.get("decision_id"):
                        return _price(d.get("invalidation")), it
                return None, it
        return None, None

    def _ensure_protective(self, bar):
        st = self.mgr.state()
        pos = st["exposure"]["position_qty"]
        if pos == 0 or st["protective_orders"]:
            return
        if any(o["kind"] in ("exit", "close") for o in st["exposure"]["working_orders"]):
            return
        inval, it = self._entry_invalidation()
        if inval is None or it is None:
            self._desk_audit("alarm", code="NO_PROTECTIVE", detail="open position without an invalidation price")
            return
        side = "sell" if pos > 0 else "buy"
        did = "protect|%s|%d" % (it["decision_id"], abs(pos))
        self.mgr.submit_intent({"decision_id": did, "kind": "protective", "side": side, "qty": abs(pos),
                                "stop": float(inval), "ref_price": float(bar["close"]),
                                "signal_ts": bar.get("delivered_ts") or bar.get("ts_close")})

    def _cancel_protectives(self):
        live = [x for x in self.mgr._live(["protective"])]
        if live:
            self.mgr._cancel_kinds(["protective"])

    def _eod_exit(self, bar, st):
        if any(o["kind"] in ("exit", "close") for o in st["exposure"]["working_orders"]):
            return
        pos = st["exposure"]["position_qty"]
        self._cancel_protectives()
        did = "eod|%s|%s" % (self._day(bar), bar.get("seq"))
        iid = self.mgr.submit_intent({"decision_id": did, "kind": "exit", "side": "sell" if pos > 0 else "buy",
                                      "qty": abs(pos), "ref_price": float(bar["close"]),
                                      "signal_ts": bar.get("delivered_ts") or bar.get("ts_close")})
        self._desk_audit("eod_exit", intent_id=iid, qty=abs(pos), reason="one bar before the calendar session end")

    # ---------------------------------------------------------------- review
    def _round_trips(self):
        """Pair entry fills with the exit/protective/close fills that flatten them."""
        fills = []
        for it in self.mgr.intents.values():
            for f in self.mgr.fills:
                if f.get("intent_id") == it["intent_id"]:
                    fills.append((f.get("fill_ts") or "", it, f))
        fills.sort(key=lambda x: (x[0], x[2].get("exec_id", "")))
        trips, cur = [], None
        pos = 0
        for ts, it, f in fills:
            qty = Q.parse(f["qty"])  # journal may contain pre-restart JSON numbers
            signed = qty if it["side"] == "buy" else -qty
            if cur is None:
                cur = {"entry_decision_id": it["decision_id"], "entry_ts": ts, "side": it["side"],
                       "fills": [], "cash": 0.0, "fees": 0.0, "simulated": self.simulated}
            cur["fills"].append({"intent_id": it["intent_id"], "kind": it["kind"], "side": it["side"],
                                 "qty": f["qty"], "price": f["price"], "fee": f.get("fee", 0.0),
                                 "ts": ts, "mock": getattr(self, "mock", True), **self._row_flags()})
            cur["cash"] += -float(signed) * float(f["price"])
            cur["fees"] += float(f.get("fee", 0.0))
            pos += signed
            if pos == 0:
                cur["exit_ts"] = ts
                cur["exit_kind"] = it["kind"]
                cur["gross_pnl"] = round(cur["cash"], 4)
                cur["net_pnl"] = round(cur["cash"] - cur["fees"], 4)
                del cur["cash"]
                trips.append(cur)
                cur = None
        return trips

    def _hypothetical(self, d):
        """Path after a pass, shown only after Reveal. Never counted in P&L."""
        seq = d.get("bar_seq")
        later = [b for b in self.seen if b.get("seq") is not None and seq is not None and b["seq"] > seq]
        if not later:
            return {"label": "HYPOTHETICAL", "note": "no later bars yet", "counted_in_pnl": False}
        nxt = later[:7]
        c0 = float(nxt[0]["open"])
        return {"label": "HYPOTHETICAL", "counted_in_pnl": False,
                "next_open": c0, "max_high_next_7": max(float(b["high"]) for b in nxt),
                "min_low_next_7": min(float(b["low"]) for b in nxt),
                "close_after_7": float(nxt[-1]["close"]), "bars": len(nxt)}

    def sizing(self):
        fq = self.strategy_cfg.get("fixed_qty")
        if fq:
            return {"mode": "fixed", "fixed_qty": Q.to_json(Q.parse(fq)), "label": self.fixed_qty_label % Q.text(Q.parse(fq)),
                    "note": "Entries use this quantity; exits are capped at the open mock position."}
        return {"mode": "strategy", "fixed_qty": None,
                "label": "strategy's own sizing (TEST order notional), checked against TEST limits"}

    def _week_of(self, ts):
        """ISO week ("YYYY-Www") of the local session date for a UTC timestamp."""
        if not ts:
            return None
        try:
            y, w, _ = self.calendar.local_date(parse_ts(ts)).isocalendar()
        except (ValueError, TypeError):
            return None
        return "%04d-W%02d" % (y, w)

    def review(self, week=None):
        """Weekly review. Top level is one ISO week of local sessions (default: the last
        available week); "by_week" holds every week so the UI can pick a prior one."""
        dec_week = {}
        for d in self.decisions:
            dec_week[d.get("decision_id")] = self._week_of(d.get("bar_ts_close") or d.get("ts_knowable"))
        weeks = sorted({w for w in dec_week.values() if w})
        trips = self._round_trips()
        rows = self.mgr.ledger_rows()
        audit_rows = _read_jsonl(self.paths["desk_audit"])

        def part(w):
            ds = [d for d in self.decisions if w is None or dec_week.get(d.get("decision_id")) == w]
            ts = [t for t in trips if w is None or self._week_of(t.get("entry_ts")) == w]
            rs = [r for r in rows if w is None or (dec_week.get(r.get("decision_id"))
                                                   or self._week_of(r.get("signal_ts"))) == w]
            au = [a for a in audit_rows if w is None or self._week_of(a.get("ts_sim_utc")) == w]
            gross = round(sum(t["gross_pnl"] for t in ts), 4)
            fees = round(sum(t["fees"] for t in ts), 4)
            pnl = {"after_cost": round(gross - fees, 4), "gross": gross, "fees": fees}
            out = self._review_part(ds, ts, rs, au, pnl)
            out["scope"] = ("week %s (local sessions, America/Chicago)" % w) if w else "all replayed weeks"
            out["week"] = w
            out["fills"] = sum(len(t["fills"]) for t in ts)
            out["sessions"] = sorted({self.calendar.local_date(parse_ts(d["bar_ts_close"])).isoformat()
                                      for d in ds if d.get("bar_ts_close")})
            return out
        by_week = {w: part(w) for w in weeks}
        default_week = weeks[-1] if weeks else None
        chosen = week if week in by_week else default_week
        top = dict(by_week[chosen]) if chosen else part(None)
        top["weeks"] = weeks
        top["default_week"] = default_week
        top["by_week"] = by_week
        allrun = part(None)
        top["all_weeks_summary"] = {"scope": allrun["scope"], "comparison": allrun["comparison"],
                                    "round_trips": len(allrun["round_trips"]), "fills": allrun["fills"]}
        return top

    def _review_part(self, decisions, trips, rows, audit_rows, pnl):
        passes = [d for d in decisions if d.get("action") == "pass"]

        def failed_n(d):
            return sum(1 for c in d.get("refusal_checks") or [] if not c.get("passed", True))
        best_pass = None
        if passes:
            best = sorted(passes, key=lambda d: (-failed_n(d), str(d.get("ts_knowable"))))[0]
            best_pass = {"decision": best, "failed_refusal_checks": failed_n(best),
                         "hypothetical_after_reveal": self._hypothetical(best)}
        refused = [{"decision_id": d.get("decision_id"), "bar_ts_close": d.get("bar_ts_close"),
                    "action": d.get("action"), "qty": d.get("qty"),
                    "why": (d.get("routing") or {}).get("why"), "detail": (d.get("routing") or {}).get("detail"),
                    "label": "REFUSED BY RISK CHECK - NOT SENT, NOT FILLED"}
                   for d in decisions if (d.get("routing") or {}).get("status") == "rejected"]
        best_trade = max(trips, key=lambda t: t["net_pnl"]) if trips else None
        worst_trade = min(trips, key=lambda t: t["net_pnl"]) if trips else None
        anomalies = [r for r in rows if r["status"] in ("rejected", "uncertain")]
        no_trade_filled = not any(r["fills"] for r in rows if r["kind"] == "entry")
        st = self.mgr.state()
        rejects = {}
        for r in rows:
            if r["status"] == "rejected":
                it = self.mgr.intents.get(r["intent_id"], {})
                rejects[it.get("reason", "?")] = rejects.get(it.get("reason", "?"), 0) + 1
        for a in audit_rows:
            if a.get("kind") == "rejected":
                rejects[a.get("reason", "?")] = rejects.get(a.get("reason", "?"), 0) + 1
        return {
            "simulated": self.simulated,
            "label": "SIMULATED REPLAY REVIEW (mock fills, synthetic bars)",
            "strategy": self.strategy,
            "pass_rule": PASS_RULE,
            "best_pass": best_pass,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "round_trips": trips,
            "refused_decisions": refused,
            "sizing": self.sizing(),
            "session_config": self.session_config,
            "no_trade_filled": no_trade_filled,
            "no_trade_note": ("No entry filled. A $0 no-trade session is a valid outcome; see the pass reasons "
                              "and rejections below.") if no_trade_filled else None,
            "comparison": [{"metric": "after-cost P&L of closed mock round trips (simulated)",
                            "value": pnl["after_cost"]},
                           {"metric": "gross P&L before costs (simulated)", "value": pnl["gross"]},
                           {"metric": "fees (simulated)", "value": pnl["fees"]},
                           {"metric": "cash baseline (no trades)", "value": 0.0},
                           {"metric": "round trips", "value": len(trips)},
                           {"metric": "decisions", "value": len(decisions)},
                           {"metric": "passes", "value": len(passes)}],
            "operating_audit": [
                {"check": "fills vs intents", "intents": len(rows),
                 "filled": sum(1 for r in rows if r["fills"]),
                 "rejected": sum(1 for r in rows if r["status"] == "rejected")},
                {"check": "rejections by reason", "counts": rejects},
                {"check": "refused decisions (never filled)", "count": len(refused)},
                {"check": "alarms (whole run, not per week)", "alarms": list(st["alarms"]) + self._exec_alarms()},
                {"check": "entries refused at the execution price (gap over a hard cap)",
                 "count": len(self.broker.exec_refusals), "rows": list(self.broker.exec_refusals)[-10:]},
                {"check": "anomalies", "rows": anomalies[:20]},
            ],
        }

    # ---------------------------------------------------------------- state
    def session_state(self):
        st = self.mgr.state()
        nxt = self.bars[self.i] if self.i < len(self.bars) else None
        ctl = st["controls"]
        phase = self.phase
        if ctl["stopped"]:
            phase = "STOPPED"
        elif ctl["paused"] and st["armed"]:
            phase = "PAUSED"
        elif st["armed"]:
            phase = "ARMED"
        nopen = ncl = None
        if nxt is not None:
            nopen = self.calendar.next_open(parse_ts(nxt["ts_open"]) - _dt.timedelta(seconds=1))
            end = self._session_end(nxt)
            ncl = end
        sim = {
            "mode": st["mode"],
            "phase": phase,
            "badge": "SIMULATION: %s" % ("STOPPED" if phase == "STOPPED" else
                                          "PAUSED" if phase == "PAUSED" else
                                          "ARMED" if phase == "ARMED" else "DISARMED"),
            "external_broker_badge": "EXTERNAL BROKER: %s" % EXTERNAL_BROKER,
            "armed": st["armed"],
            "session_id": st["session_id"],
            "expires_utc": st["expires_utc"],
            "replay_clock_utc": self.replay_clock(),
            "bars_total": len(self.bars),
            "bars_done": self.i,
            "play_rate_bars_per_sec": self.play_rate,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "strategy_source": self.strategy_source,
            "sizing": self.sizing(),
            "session_config": self.session_config,
            "tradingview_symbol": TRADINGVIEW_REFERENCE_SYMBOL,
            "tradingview_label": TRADINGVIEW_REFERENCE_LABEL,
            "strategies_available": strategy_names(),
            "data_label": self.data_label,
            "preflight": self.preflight(),
            "schedule": {"enabled": ctl["schedule_enabled"], "clock": "SIMULATED",
                         "next_open_utc": iso(nopen) if nopen else None,
                         "next_close_utc": iso(ncl) if ncl else None,
                         "calendar": "fixture-utc-1430-2130 (fixture hours, not an exchange calendar)",
                         "note": "Auto-arms at each simulated session open when enabled; never clears a Stop. "
                                 "No launchd or cron job is installed."},
            "controls": ctl,
            "exposure": st["exposure"],
            "protective_orders": st["protective_orders"],
            "pnl": st["pnl"],
            "limits": dict(self.limits, label=self.limits.get("label", LIMITS_LABEL),
                           max_loss_checked_by="order engine" if self.engine_checks_max_loss
                           else "desk session runner (before the order engine)"),
            "broker": dict(st["broker"], name=BROKER_LABEL, external=False,
                           book_restored_from_file=self.broker_restored,
                           book_file="broker_state.json (separate from the order engine journal)"),
            "fill_model": FILL_MODEL,
            "fill_costs": FILL_COSTS,
            "intake": {"last": self.intake_log[-1] if self.intake_log else None,
                       "rejected_recent": [x for x in self.intake_log if not x["ok"]][-10:],
                       "rule": "a bar that fails intake is not given to the fake broker or the strategy; "
                               "working entries are cancelled; protective stops stay working"},
            "alarms": list(st["alarms"]) + self._exec_alarms(),
            "exec_refusals": list(self.broker.exec_refusals)[-20:],
            "entry_block_reason": st["entry_block_reason"],
            "restarts": self.restarts,
            "updated_utc": st["updated_utc"],
            "simulated": self.simulated,
        }
        return sim

    def _write_state(self):
        with self.lock:
            sess = self.session_state()
            _atomic_json(self.paths["session"], sess)
            rows = self.mgr.ledger_rows()
            flags = self._ledger_flags()
            for r in rows:
                r.update(flags)
            _atomic_jsonl(self.paths["ledger"], rows)
            _atomic_json(self.paths["review"], self.review())
            _atomic_json(self.paths["progress"], {"bars_done": self.i, "phase": self.phase,
                                                  "session_seq": self.session_seq, "strategy": self.strategy,
                                                  "restarts": self.restarts, "simulated": self.simulated})

    def close(self):
        self.stop_play()
        self._write_state()
        self.mgr.close()
