"""Paper engine for rule EMAX. Standard library only, Python 3.9.

What it does, in order, for every bar of a permitted feed:

1. Checks the bar (fields, types, timestamps, duplicate, clock, order, gaps).
   A bar that fails is refused and logged. It never produces a decision.
2. Fills an order that was decided on an EARLIER bar, at this bar's open, with
   spread, slippage and commission added. It does so only if this bar opened
   at or after the moment that decision was ready: the time the signal bar was
   delivered, plus processing latency. An open that printed before the
   decision was ready is never used; the order waits for the next eligible
   open. A decision can never fill on the bar that produced it.
3. Updates the two averages, marks the book, and records exactly one decision
   for this bar with a plain-English explanation.

Nothing here opens the network, calls a model, or reads the claude_notes
folder. Paper only: the "orders" are rows in a local file.
"""
import copy
import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone

import explain as explain_mod
import provenance
import rules

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


class EngineError(Exception):
    """Unexpected state. The run stops instead of guessing."""


class ConfigRefused(Exception):
    """A config that is malformed or tries to loosen a risk limit."""


DEFAULT_CONFIG = {
    "start_cash": 10000.0,
    "order_notional": 5000.0,
    "half_spread_bps": 1.0,
    "slippage_bps": 2.0,
    "commission_per_share": 0.005,
    "commission_min": 1.0,
    "delay_bars": 0,
    "latency_seconds": 5,
    "max_lag_seconds": 120,
    "limits": {
        "max_position_notional": 6000.0,
        "max_qty": 100,
        "max_daily_loss": 100.0,
        "cooldown_bars": 3,
        "max_positions_per_symbol": 1,
    },
}

# A config file may only tighten these. They live in code on purpose.
HARD_CEILINGS = {
    "max_position_notional": 6000.0,
    "max_qty": 100,
    "max_daily_loss": 100.0,
    "max_positions_per_symbol": 1,
    "max_lag_seconds": 120,
}
HARD_FLOORS = {"cooldown_bars": 3}

BAR_REQUIRED = ("seq", "symbol", "ts_open", "ts_close", "delivered_ts",
                "open", "high", "low", "close", "volume")
HASHED_FIELDS = ("seq", "symbol", "ts_open", "ts_close", "open", "high", "low", "close", "volume")


def parse_ts(s):
    if not isinstance(s, str) or not TS_RE.match(s):
        raise ValueError("timestamp must look like 2026-06-01T14:30:00Z, got %r" % (s,))
    return datetime.strptime(s, TS_FMT).replace(tzinfo=timezone.utc)


def fmt_ts(dt):
    return dt.strftime(TS_FMT)


def r6(x):
    return None if x is None else round(float(x), 6)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_config(overrides=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    ov = overrides or {}
    if not isinstance(ov, dict):
        raise ConfigRefused("config must be a JSON object")
    for k, v in ov.items():
        if k == "limits":
            if not isinstance(v, dict):
                raise ConfigRefused("limits must be a JSON object")
            for lk, lv in v.items():
                if lk not in cfg["limits"]:
                    raise ConfigRefused("unknown limit %r" % (lk,))
                cfg["limits"][lk] = lv
        elif k in cfg:
            cfg[k] = v
        else:
            raise ConfigRefused("unknown config key %r" % (k,))

    def need(name, val, lo, hi, whole=False):
        ok = _is_int(val) if whole else _is_num(val)
        if not ok or not (lo <= val <= hi):
            raise ConfigRefused("%s must be %s between %s and %s, got %r"
                                % (name, "a whole number" if whole else "a number", lo, hi, val))

    need("start_cash", cfg["start_cash"], 1.0, 1000000.0)
    need("order_notional", cfg["order_notional"], 1.0, 100000000.0)
    need("half_spread_bps", cfg["half_spread_bps"], 0.0, 1000.0)
    need("slippage_bps", cfg["slippage_bps"], 0.0, 1000.0)
    need("commission_per_share", cfg["commission_per_share"], 0.0, 100.0)
    need("commission_min", cfg["commission_min"], 0.0, 100.0)
    need("delay_bars", cfg["delay_bars"], 0, 5, whole=True)
    need("latency_seconds", cfg["latency_seconds"], 1, 3600, whole=True)
    need("max_lag_seconds", cfg["max_lag_seconds"], 1, 1000000, whole=True)
    lim = cfg["limits"]
    need("limits.max_position_notional", lim["max_position_notional"], 0.01, 1e12)
    need("limits.max_qty", lim["max_qty"], 1, 10 ** 9, whole=True)
    need("limits.max_daily_loss", lim["max_daily_loss"], 0.01, 1e12)
    need("limits.cooldown_bars", lim["cooldown_bars"], 0, 100000, whole=True)
    need("limits.max_positions_per_symbol", lim["max_positions_per_symbol"], 1, 10 ** 6, whole=True)
    for name, ceiling in HARD_CEILINGS.items():
        val = cfg[name] if name == "max_lag_seconds" else lim[name]
        if val > ceiling:
            raise ConfigRefused("%s=%r is looser than the hard ceiling %r; a config may only "
                                "tighten limits" % (name, val, ceiling))
    for name, floor in HARD_FLOORS.items():
        if lim[name] < floor:
            raise ConfigRefused("%s=%r is looser than the hard floor %r; a config may only "
                                "tighten limits" % (name, lim[name], floor))
    return cfg


def config_hash(cfg):
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def bar_hash(bar):
    blob = json.dumps([bar.get(k) for k in HASHED_FIELDS], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def decision_id(rule, symbol, bar_ts_open):
    blob = ("%s|%s|%s" % (rule, symbol, bar_ts_open)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def risk_check(intent, portfolio, limits):
    """Pure function. Returns (allowed, code, detail). An order that breaks a
    limit is refused whole. It is never trimmed to fit."""
    qty = intent["qty"]
    px = intent["ref_price"]
    notional = qty * px
    problems = []
    if qty <= 0:
        problems.append(("zero_quantity", "the order size works out to zero shares"))
    if portfolio["qty"] != 0 or portfolio["pending"]:
        problems.append(("one_position_per_symbol",
                         "a position or an order is already open for this symbol (limit %d)"
                         % limits["max_positions_per_symbol"]))
    if portfolio["halted"] or portfolio["day_pnl"] <= -limits["max_daily_loss"]:
        problems.append(("daily_loss_halt",
                         "the daily loss limit of %s was reached this session (day profit and "
                         "loss %s), so no new position today"
                         % (explain_mod.money(limits["max_daily_loss"]),
                            explain_mod.money(portfolio["day_pnl"]))))
    bse = portfolio["bars_since_exit"]
    if bse is not None and bse < limits["cooldown_bars"]:
        problems.append(("cooldown",
                         "only %d bars since the last exit fill and the cooldown is %d bars"
                         % (bse, limits["cooldown_bars"])))
    if notional > limits["max_position_notional"]:
        problems.append(("over_limit_notional",
                         "%d shares at about %.4f is %s, over the position limit of %s"
                         % (qty, px, explain_mod.money(notional),
                            explain_mod.money(limits["max_position_notional"]))))
    if qty > limits["max_qty"]:
        problems.append(("over_limit_quantity",
                         "%d shares is over the share limit of %d" % (qty, limits["max_qty"])))
    if notional * (1.0 + portfolio["cost_rate"]) + portfolio["min_commission"] > portfolio["cash"]:
        problems.append(("insufficient_cash",
                         "about %s is needed and only %s of paper cash is free"
                         % (explain_mod.money(notional), explain_mod.money(portfolio["cash"]))))
    if problems:
        return False, problems[0][0], "; ".join(p[1] for p in problems)
    return True, "ok", "all risk checks passed"


def reprice_net(fills, last_close, cfg, mult):
    """Net profit and loss of the SAME fills if every cost were `mult` times
    the configured cost. Uses the raw opens stored on each fill."""
    bps = (cfg["half_spread_bps"] + cfg["slippage_bps"]) * mult
    cash = cfg["start_cash"]
    qty = 0
    for f in fills:
        commission = max(cfg["commission_min"] * mult, f["qty"] * cfg["commission_per_share"] * mult)
        if f["side"] == "buy":
            cash -= f["qty"] * f["raw_open"] * (1.0 + bps / 1e4) + commission
            qty += f["qty"]
        else:
            cash += f["qty"] * f["raw_open"] * (1.0 - bps / 1e4) - commission
            qty -= f["qty"]
    equity = cash + qty * (last_close or 0.0)
    return equity - cfg["start_cash"]


class Engine(object):
    # The only files this runner creates in a state folder.
    FILES = ("decisions.jsonl", "ledger.jsonl", "rejections.jsonl", "state.json",
             "summary.json", "decision_packet.md")

    def __init__(self, params=None, config=None, as_of=None, state_dir=None,
                 permitted_sources=None):
        self.params = rules.validate_params(params)
        self.rule_id = rules.rule_id(params)
        self.cfg = validate_config(config)
        self.cfg_hash = config_hash(self.cfg)
        if as_of is None:
            raise EngineError("an as-of clock is required; nothing is assumed about 'now'")
        self.as_of = parse_ts(as_of) if isinstance(as_of, str) else as_of
        self.state_dir = state_dir
        self.permitted_sources = permitted_sources
        self.decisions = []
        self.ledger = []
        self.rejections = []       # this run only; the file keeps every run
        self.decision_ids = set()
        self._current_seq = None
        self.state = self._new_state()
        if state_dir:
            self._load()

    # ------------------------------------------------------------ state

    def _new_state(self):
        c = self.cfg["start_cash"]
        return {
            "schema": 1, "rule_id": self.rule_id, "config_hash": self.cfg_hash,
            "symbol": None, "timeframe_minutes": None,
            "last_seq": None, "last_ts_close": None, "bar_hashes": {},
            "ind": rules.new_indicator_state(),
            "cash": c, "qty": 0, "entry_ref": None, "entry_fill_price": None,
            "entry_commission": None, "entry_seq": None,
            "pending": None, "last_close": None, "first_open": None,
            "equity": c, "peak_equity": c, "max_drawdown": 0.0,
            "session": None, "day_start_equity": c, "halted": False,
            "last_exit_seq": None, "gap_exit_needed": False,
            "bars_accepted": 0,
            "open_tods": [], "source": None,
            "counts": {"decisions": 0, "ledger": 0},
        }

    def _path(self, name):
        return os.path.join(self.state_dir, name)

    def _read_jsonl(self, name):
        p = self._path(name)
        out = []
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                for ln in fh:
                    if ln.strip():
                        out.append(json.loads(ln))
        return out

    def _load(self):
        os.makedirs(self.state_dir, exist_ok=True)
        dec = self._read_jsonl("decisions.jsonl")
        led = self._read_jsonl("ledger.jsonl")
        sp = self._path("state.json")
        if os.path.exists(sp):
            with open(sp, "r", encoding="utf-8") as fh:
                st = json.load(fh)
            if st.get("rule_id") != self.rule_id:
                raise EngineError("this state folder belongs to rule %s and this run is %s; "
                                  "use another folder or --fresh" % (st.get("rule_id"), self.rule_id))
            if st.get("config_hash") != self.cfg_hash:
                raise EngineError("this state folder was made with a different config; "
                                  "use another folder or --fresh")
            if st["counts"]["decisions"] != len(dec) or st["counts"]["ledger"] != len(led):
                raise EngineError("state.json and the ledger files disagree (%d/%d decisions, "
                                  "%d/%d ledger rows); refusing to continue"
                                  % (st["counts"]["decisions"], len(dec),
                                     st["counts"]["ledger"], len(led)))
            self.state = st
        elif dec or led:
            raise EngineError("ledger files exist without state.json; refusing to continue")
        self.decisions, self.ledger = dec, led
        self.decision_ids = set(d["decision_id"] for d in dec)

    def _append(self, name, rec):
        if self.state_dir:
            with open(self._path(name), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def _save_state(self):
        if self.state_dir:
            tmp = self._path("state.json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, sort_keys=True)
            os.replace(tmp, self._path("state.json"))

    def _ledger(self, rec):
        self.ledger.append(rec)
        self._append("ledger.jsonl", rec)
        self.state["counts"]["ledger"] += 1

    def _reject(self, scope, code, detail, **ctx):
        rec = {"scope": scope, "code": code, "detail": detail}
        rec.update(dict((k, v) for k, v in ctx.items() if v is not None))
        self.rejections.append(rec)
        self._append("rejections.jsonl", rec)
        return code

    # ------------------------------------------------------------- feed

    def process_feed(self, path):
        """Run the provenance gate, then every bar. A refused feed reads zero bars."""
        base = os.path.basename(path)
        res = provenance.check_feed(path, self.permitted_sources)
        if not res.ok:
            code = res.primary_code()
            self._reject("feed", code, "; ".join(res.reasons), feed=base)
            return {"accepted": False, "code": code, "reasons": list(res.reasons),
                    "bars_accepted": 0, "bar_results": {}, "manifest": None}
        m = res.manifest
        tf, sym = m.get("timeframe_minutes"), m.get("symbol")
        st = self.state
        problem = None
        if not _is_int(tf) or tf < 1:
            problem = "manifest timeframe_minutes must be a whole number of minutes"
        elif st["symbol"] is not None and (st["symbol"] != sym or st["timeframe_minutes"] != tf):
            problem = ("this state folder holds %s at %s minutes; the feed is %s at %s"
                       % (st["symbol"], st["timeframe_minutes"], sym, tf))
        if problem:
            self._reject("feed", "schema_rejected", problem, feed=base)
            return {"accepted": False, "code": "schema_rejected", "reasons": [problem],
                    "bars_accepted": 0, "bar_results": {}, "manifest": m}
        if st["symbol"] is None:
            st["symbol"], st["timeframe_minutes"] = sym, tf
        st["source"] = m.get("source")
        counts = {}
        for line_no, rec in res.records:
            r = self.process_bar(rec, line_no=line_no, feed=base)
            counts[r] = counts.get(r, 0) + 1
        return {"accepted": True, "code": None, "reasons": [],
                "bars_accepted": counts.get("accepted", 0), "bar_results": counts, "manifest": m}

    def _validate_bar(self, bar):
        st = self.state
        if not isinstance(bar, dict):
            return "malformed_input", "bar is not an object", None
        missing = [k for k in BAR_REQUIRED if bar.get(k) is None]
        if missing:
            return "missing_input", "bar is missing %s" % ", ".join(missing), None
        if not _is_int(bar["seq"]) or bar["seq"] < 1:
            return "malformed_input", "seq must be a whole number from 1 up", None
        if bar["symbol"] != st["symbol"]:
            return "malformed_input", "bar symbol %r is not %r" % (bar["symbol"], st["symbol"]), None
        for k in ("open", "high", "low", "close"):
            if not _is_num(bar[k]) or bar[k] <= 0:
                return "malformed_input", "%s must be a positive finite number, got %r" % (k, bar[k]), None
        if not _is_num(bar["volume"]) or bar["volume"] < 0:
            return "malformed_input", "volume must be a number from 0 up", None
        if bar["high"] < max(bar["open"], bar["close"]) or bar["low"] > min(bar["open"], bar["close"]):
            return "malformed_input", "high/low do not contain open and close", None
        try:
            t_open, t_close, t_del = (parse_ts(bar[k]) for k in ("ts_open", "ts_close", "delivered_ts"))
        except ValueError as exc:
            return "bad_timestamps", str(exc), None
        if t_close - t_open != timedelta(minutes=st["timeframe_minutes"]):
            return "bad_timestamps", "bar does not span %d minutes" % st["timeframe_minutes"], None
        if t_del < t_close:
            return "bad_timestamps", "bar claims delivery before it closed", None
        return None, None, (t_open, t_close, t_del)

    def process_bar(self, bar, line_no=None, feed=None):
        st = self.state
        if st["symbol"] is None:
            raise EngineError("no feed manifest was accepted before this bar")
        seq_hint = bar.get("seq") if isinstance(bar, dict) else None
        ctx = {"line": line_no, "feed": feed, "seq": seq_hint if _is_int(seq_hint) else None}
        code, detail, parsed = self._validate_bar(bar)
        if code:
            return self._reject("bar", code, detail, **ctx)
        seq = bar["seq"]
        h = bar_hash(bar)
        known = st["bar_hashes"].get(str(seq))
        if known is not None:
            if known == h:
                return self._reject("bar", "duplicate_bar",
                                    "bar %d was already processed; the repeat changes nothing" % seq, **ctx)
            return self._reject("bar", "conflicting_duplicate",
                                "bar %d arrived again with different values; the first version "
                                "stands and the second is ignored" % seq, **ctx)
        t_open, t_close, t_del = parsed
        if t_close > self.as_of or t_del > self.as_of:
            return self._reject("bar", "future_dated",
                                "bar closes %s, after the clock %s" % (bar["ts_close"], fmt_ts(self.as_of)),
                                **ctx)
        lag = (t_del - t_close).total_seconds()
        if lag > self.cfg["max_lag_seconds"]:
            return self._reject("bar", "stale_input",
                                "bar was delivered %d seconds after it closed; the limit is %d"
                                % (lag, self.cfg["max_lag_seconds"]), **ctx)
        if st["last_seq"] is not None and (seq <= st["last_seq"] or bar["ts_open"] < st["last_ts_close"]):
            return self._reject("bar", "out_of_order",
                                "bar %d (%s) is not after bar %d (%s)"
                                % (seq, bar["ts_open"], st["last_seq"], st["last_ts_close"]), **ctx)
        gap = st["last_seq"] is not None and seq > st["last_seq"] + 1
        if gap:
            self._reject("gap", "missing_input",
                         "bars %d to %d never arrived as usable input; the averages restart and "
                         "need a fresh warmup" % (st["last_seq"] + 1, seq - 1), **ctx)
            self._on_gap(seq)
        self._accept(bar, h)
        return "accepted"

    def _on_gap(self, seq):
        st = self.state
        st["ind"] = rules.new_indicator_state()
        p = st["pending"]
        if p is not None and p["side"] == "buy":
            self._ledger({"type": "cancel", "order_id": p["order_id"],
                          "decision_id": p["decision_id"], "reason": "data_gap", "at_seq": seq})
            st["pending"] = None
        elif p is not None:
            p["after_gap"] = True
        if st["qty"] > 0 and st["pending"] is None:
            st["gap_exit_needed"] = True

    # -------------------------------------------------------------- bar

    def _accept(self, bar, h):
        st = self.state
        seq = bar["seq"]
        self._current_seq = seq
        session = bar["ts_open"][:10]
        if st["session"] != session:
            st["session"] = session
            st["day_start_equity"] = st["equity"]
            st["halted"] = False
        if st["first_open"] is None:
            st["first_open"] = bar["open"]
        tod = bar["ts_open"][11:19]
        if tod not in st.setdefault("open_tods", []):
            st["open_tods"].append(tod)
        p = st["pending"]
        # The fill gate is the actual bar: it must come after the signal bar and
        # open at or after the ready time. earliest_fill_seq is only the plan.
        if (p is not None and seq >= p.get("min_fill_seq", p["earliest_fill_seq"])
                and bar["ts_open"] >= p["earliest_fill_ts"]):
            self._fill(p, bar)
        st["ind"] = rules.step_indicators(st["ind"], bar["close"], self.params)
        st["last_close"] = bar["close"]
        st["equity"] = st["cash"] + st["qty"] * bar["close"]
        st["peak_equity"] = max(st["peak_equity"], st["equity"])
        st["max_drawdown"] = max(st["max_drawdown"], st["peak_equity"] - st["equity"])
        day_pnl = st["equity"] - st["day_start_equity"]
        self.submit_decision(self._decide(bar, day_pnl))
        st["bar_hashes"][str(seq)] = h
        st["last_seq"], st["last_ts_close"] = seq, bar["ts_close"]
        st["bars_accepted"] += 1
        self._current_seq = None
        self._save_state()

    def _fill(self, p, bar):
        st, cfg, lim = self.state, self.cfg, self.cfg["limits"]
        seq = bar["seq"]
        # The price used is this bar's open, which printed at ts_open. It is
        # usable only because the decision was ready by then.
        fill_dt = parse_ts(bar["ts_open"])
        if seq <= p["signal_seq"] or fill_dt < parse_ts(p["earliest_fill_ts"]):
            raise EngineError("a fill must use a price printed after its decision was ready "
                              "(signal bar %d ready %s, fill bar %d opens %s)"
                              % (p["signal_seq"], p["earliest_fill_ts"], seq, bar["ts_open"]))
        bps = cfg["half_spread_bps"] + cfg["slippage_bps"]
        raw, qty = bar["open"], p["qty"]
        commission = max(cfg["commission_min"], qty * cfg["commission_per_share"])
        realized = None
        if p["side"] == "buy":
            px = raw * (1.0 + bps / 1e4)
            problem = None
            if st["qty"] != 0:
                problem = "one_position_per_symbol"
            elif qty * px > lim["max_position_notional"] or qty > lim["max_qty"]:
                problem = "over_limit_at_fill"
            elif qty * px + commission > st["cash"]:
                problem = "insufficient_cash_at_fill"
            if problem:
                self._ledger({"type": "cancel", "order_id": p["order_id"],
                              "decision_id": p["decision_id"], "reason": problem, "at_seq": seq})
                st["pending"] = None
                return
            st["cash"] -= qty * px + commission
            st["qty"] = qty
            st["entry_ref"], st["entry_fill_price"] = raw, px
            st["entry_commission"], st["entry_seq"] = commission, seq
        else:
            if qty != st["qty"] or qty <= 0:
                raise EngineError("sell order for %d shares but the book holds %d" % (qty, st["qty"]))
            px = raw * (1.0 - bps / 1e4)
            realized = (qty * px - commission) - (qty * st["entry_fill_price"] + st["entry_commission"])
            st["cash"] += qty * px - commission
            st["qty"] = 0
            st["entry_ref"] = st["entry_fill_price"] = st["entry_commission"] = st["entry_seq"] = None
            st["last_exit_seq"] = seq
        rec = {"type": "fill", "fill_id": "F-" + p["decision_id"], "order_id": p["order_id"],
               "decision_id": p["decision_id"], "rule_id": self.rule_id, "symbol": st["symbol"],
               "side": p["side"], "qty": qty, "raw_open": raw, "fill_price": r6(px),
               "commission": r6(commission), "signal_seq": p["signal_seq"],
               "signal_ts": p["signal_ts"], "available_ts": p["available_ts"],
               "decision_ready_ts": p["earliest_fill_ts"],
               "fill_seq": seq, "fill_ts": fmt_ts(fill_dt),
               "price_basis": "open of bar %d, the first bar to open at or after the "
                              "decision was ready" % seq,
               "reason_code": p["reason_code"], "cash_after": r6(st["cash"]),
               "position_after": st["qty"]}
        if realized is not None:
            rec["realized_pnl"] = r6(realized)
        if p.get("after_gap"):
            rec["after_gap"] = True
        self._ledger(rec)
        st["pending"] = None

    def _plan_fill_bar(self, bar, min_seq, ready_ts):
        """Name the first bar expected to open at or after the ready time.

        Returns (seq, expected_open). The bar after the signal bar normally opens
        at the signal bar's close, which is before the decision is ready, so it
        cannot be the fill bar. This walks forward one bar length at a time on the
        cadence seen so far. If the next slot is a time of day at which no bar has
        ever opened, the next bar belongs to a later session; its open time is not
        known in advance, so expected_open is None. This is a plan only: the fill
        itself is decided by the real bar's open time in _accept and _fill."""
        st = self.state
        ready = parse_ts(ready_ts)
        step = timedelta(minutes=st["timeframe_minutes"])
        tods = set(st.get("open_tods") or [])
        c, t = bar["seq"] + 1, parse_ts(bar["ts_close"])
        for _ in range(5000):
            if fmt_ts(t)[11:19] not in tods:
                return max(c, min_seq), None
            if c >= min_seq and t >= ready:
                return c, fmt_ts(t)
            c, t = c + 1, t + step
        return max(c, min_seq), None

    def _decide(self, bar, day_pnl):
        st, lim, ind = self.state, self.cfg["limits"], self.state["ind"]
        seq, close = bar["seq"], bar["close"]
        sig = rules.signals(ind, self.params)
        stop_level = None
        if st["qty"] > 0 and st["entry_ref"] is not None:
            stop_level = st["entry_ref"] * (1.0 - self.params["stop_pct"] / 100.0)
        if day_pnl <= -lim["max_daily_loss"]:
            st["halted"] = True
        d = {
            "decision_id": decision_id(self.rule_id, st["symbol"], bar["ts_open"]),
            "rule_id": self.rule_id, "symbol": st["symbol"], "bar_seq": seq,
            "bar_ts_open": bar["ts_open"], "signal_ts": bar["ts_close"], "order": None,
            "inputs": {
                "close": close, "ema_fast": r6(ind["fast"]), "ema_slow": r6(ind["slow"]),
                "prev_ema_fast": r6(ind["prev_fast"]), "prev_ema_slow": r6(ind["prev_slow"]),
                "position_qty": st["qty"], "entry_ref": st["entry_ref"],
                "stop_level": r6(stop_level), "day_pnl": r6(day_pnl),
                "bars_since_reset": ind["n"], "warmup_bars": self.params["warmup_bars"],
                "limit_position_notional": lim["max_position_notional"],
                "limit_daily_loss": lim["max_daily_loss"],
            },
        }
        min_seq = seq + 1 + self.cfg["delay_bars"]
        ready_ts = fmt_ts(parse_ts(bar["delivered_ts"])
                          + timedelta(seconds=self.cfg["latency_seconds"]))
        earliest, expected_open = self._plan_fill_bar(bar, min_seq, ready_ts)
        plan = {"min_fill_seq": min_seq, "earliest_fill_seq": earliest,
                "earliest_fill_ts": ready_ts, "earliest_fill_open_expected": expected_open}
        d["available_ts"], d["decision_ready_ts"] = bar["delivered_ts"], ready_ts
        if st["pending"] is not None:
            d["action"], d["reason_code"] = "HOLD", "order_pending"
        elif st["qty"] > 0:
            reason = None
            if st["gap_exit_needed"]:
                reason = "data_gap"
            elif day_pnl <= -lim["max_daily_loss"]:
                reason = "daily_loss_limit"
            elif close <= stop_level:
                reason = "stop"
            elif sig["cross_down"]:
                reason = "cross_down"
            if reason:
                d["action"], d["reason_code"] = "EXIT_LONG", reason
                d["order"] = dict({"side": "sell", "qty": st["qty"]}, **plan)
            else:
                d["action"], d["reason_code"] = "HOLD", "in_position"
        elif not sig["ready"]:
            d["action"], d["reason_code"] = "STAND_ASIDE", "warmup"
        elif sig["cross_up"]:
            qty = int(self.cfg["order_notional"] // close)
            bse = None if st["last_exit_seq"] is None else seq - st["last_exit_seq"]
            portfolio = {
                "cash": st["cash"], "qty": st["qty"], "pending": st["pending"] is not None,
                "halted": st["halted"], "day_pnl": day_pnl, "bars_since_exit": bse,
                "cost_rate": (self.cfg["half_spread_bps"] + self.cfg["slippage_bps"]) / 1e4,
                "min_commission": self.cfg["commission_min"],
            }
            ok, code, detail = risk_check({"side": "buy", "qty": qty, "ref_price": close},
                                          portfolio, lim)
            if ok:
                d["action"], d["reason_code"] = "ENTER_LONG", "cross_up"
                d["order"] = dict({"side": "buy", "qty": qty}, **plan)
            else:
                d["action"], d["reason_code"], d["risk_detail"] = "BLOCKED", code, detail
                d["blocked_order"] = {"side": "buy", "qty": qty}
        else:
            d["action"], d["reason_code"] = "STAND_ASIDE", "no_signal"
        return d

    def submit_decision(self, d):
        """The only door to the ledger. One decision per bar, made by the engine
        while that bar is being processed. A repeat, or a decision that arrives
        from anywhere else, is refused and creates no order."""
        st = self.state
        did = d.get("decision_id")
        if did in self.decision_ids:
            self._reject("decision", "duplicate_decision",
                         "decision %s was already recorded; the repeat creates no order" % did,
                         seq=d.get("bar_seq"))
            return False
        expect = decision_id(self.rule_id, st["symbol"], d.get("bar_ts_open"))
        if self._current_seq is None or d.get("bar_seq") != self._current_seq or did != expect:
            self._reject("decision", "not_engine_decision",
                         "decisions are made by the engine while a bar is processed; this one "
                         "came from outside and creates no order", seq=d.get("bar_seq"))
            return False
        d = dict(d)
        d["explanation"] = explain_mod.explain(d)
        self.decision_ids.add(did)
        self.decisions.append(d)
        self._append("decisions.jsonl", d)
        st["counts"]["decisions"] += 1
        if d["action"] in ("ENTER_LONG", "EXIT_LONG"):
            o = d["order"]
            rec = {"type": "order", "order_id": "O-" + did, "decision_id": did,
                   "rule_id": self.rule_id, "symbol": st["symbol"], "side": o["side"],
                   "qty": o["qty"], "signal_seq": d["bar_seq"], "signal_ts": d["signal_ts"],
                   "available_ts": d["available_ts"],
                   "min_fill_seq": o.get("min_fill_seq", o["earliest_fill_seq"]),
                   "earliest_fill_seq": o["earliest_fill_seq"],
                   "earliest_fill_ts": o["earliest_fill_ts"],
                   "earliest_fill_open_expected": o.get("earliest_fill_open_expected"),
                   "reason_code": d["reason_code"]}
            self._ledger(rec)
            st["pending"] = {"order_id": rec["order_id"], "decision_id": did, "side": o["side"],
                             "qty": o["qty"], "signal_seq": d["bar_seq"],
                             "signal_ts": d["signal_ts"],
                             "available_ts": d["available_ts"],
                             "min_fill_seq": o.get("min_fill_seq", o["earliest_fill_seq"]),
                             "earliest_fill_seq": o["earliest_fill_seq"],
                             "earliest_fill_ts": o["earliest_fill_ts"],
                             "earliest_fill_open_expected":
                                 o.get("earliest_fill_open_expected"),
                             "reason_code": d["reason_code"], "after_gap": False}
            if d["reason_code"] == "data_gap":
                st["gap_exit_needed"] = False
        return True

    # ---------------------------------------------------------- summary

    def fills(self):
        return [r for r in self.ledger if r["type"] == "fill"]

    def summary(self):
        st, cfg = self.state, self.cfg
        fills = self.fills()
        trips, open_buy = [], None
        gross = 0.0
        for f in fills:
            if f["side"] == "buy":
                open_buy = f
            elif open_buy is not None:
                g = f["qty"] * (f["raw_open"] - open_buy["raw_open"])
                gross += g
                trips.append({"entry_fill_seq": open_buy["fill_seq"], "entry_fill_ts": open_buy["fill_ts"],
                              "exit_fill_seq": f["fill_seq"], "exit_fill_ts": f["fill_ts"],
                              "qty": f["qty"], "entry_raw_open": open_buy["raw_open"],
                              "exit_raw_open": f["raw_open"], "gross_pnl": r6(g),
                              "net_pnl": f.get("realized_pnl"), "exit_reason": f["reason_code"]})
                open_buy = None
        unreal = 0.0
        if st["qty"] > 0 and st["last_close"] is not None:
            unreal = st["qty"] * (st["last_close"] - st["entry_ref"])
        slip = sum(f["qty"] * abs(f["fill_price"] - f["raw_open"]) for f in fills)
        comm = sum(f["commission"] for f in fills)
        net = st["equity"] - cfg["start_cash"]
        hold = None
        if st["first_open"] and st["last_close"]:
            bps = cfg["half_spread_bps"] + cfg["slippage_bps"]
            px = st["first_open"] * (1.0 + bps / 1e4)
            shares = int(cfg["order_notional"] // px)
            hcomm = max(cfg["commission_min"], shares * cfg["commission_per_share"])
            hold = {"shares": shares, "bought_at": r6(px), "marked_at": st["last_close"],
                    "net_pnl": r6(shares * (st["last_close"] - px) - hcomm),
                    "note": "same order size bought once at the first bar's open with the same "
                            "costs, never sold, marked at the last close"}
        by_action, by_code = {}, {}
        for d in self.decisions:
            by_action[d["action"]] = by_action.get(d["action"], 0) + 1
        for r in self.rejections:
            by_code[r["code"]] = by_code.get(r["code"], 0) + 1
        wins = len([t for t in trips if (t["net_pnl"] or 0) > 0])
        return {
            "rule_id": self.rule_id, "symbol": st["symbol"], "bars_accepted": st["bars_accepted"],
            "start_cash": cfg["start_cash"], "end_equity": r6(st["equity"]), "net_pnl": r6(net),
            "gross_pnl_at_raw_opens": r6(gross + unreal),
            "spread_and_slippage_cost": r6(slip), "commission_cost": r6(comm),
            "round_trips": trips, "round_trip_count": len(trips), "wins": wins,
            "losses": len(trips) - wins, "max_drawdown": r6(st["max_drawdown"]),
            "open_position_qty": st["qty"],
            "pending_order": None if st["pending"] is None else st["pending"]["order_id"],
            "orders": len([r for r in self.ledger if r["type"] == "order"]),
            "fills": len(fills),
            "cancels": len([r for r in self.ledger if r["type"] == "cancel"]),
            "decisions": len(self.decisions), "decisions_by_action": by_action,
            "rejections_this_run": by_code, "buy_and_hold": hold,
            "fill_assumption": "a decision is ready when its bar was delivered plus %d seconds "
                               "of processing; it fills at the open of the first bar that "
                               "opens at or after that moment, plus costs. On a continuous "
                               "hourly feed that is one full bar after the signal bar closes."
                               % cfg["latency_seconds"],
            "data_note": ("TEST ONLY: synthetic bars made by a script; this is a mechanics "
                          "check, not evidence of an edge")
            if st.get("source") in (None, "synthetic") else
            ("REAL BARS, PAPER ONLY, from the source named '%s'; one run on one file is not "
             "evidence of an edge" % st.get("source")),
        }
