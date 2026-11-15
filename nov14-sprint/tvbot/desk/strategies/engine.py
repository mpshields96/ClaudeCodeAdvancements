"""Deterministic bar-by-bar replay shared by the desk strategies and research.

Paper and offline only; every number is simulated. The frozen rules are in
strategies/RULES.md. In short:

* A decision is made at a bar's close using only bars closed by then.
* Research replay: an order from that decision fills at the NEXT bar's open (plus any research
  delay), with costs. A zero-volume bar never fills: entries are dropped,
  exits wait for the next bar.
* The replayer keeps its own hypothetical book (signed quantity, average fill
  price, cash, basket legs). The desk's real position is reconciled in
  registry.py.

Kinds: ema, ema_overnight (research), gold_basket, gold_alternating
(research), fixed_risk_single, bounded_fixed, cash.
"""
import copy
import hashlib
import importlib.util
import json
import os

from . import base as B

GOLD_KINDS = ("gold_basket", "gold_alternating", "fixed_risk_single", "bounded_fixed")
EMA_KINDS = ("ema", "ema_overnight")

# Frozen strategy-rule parameters (NOT Matthew's account limits; never tuned).
# Basket target/stop are Codex's preregistered +$3 / -$6 per basket.
GOLD_PARAMS = {
    "swing": 6,
    "basket_target_usd": 3.0,
    "basket_stop_usd": -6.0,
    "leg_cap": 3,
    "reset_pivots_each_session": False,
}
RULE_VERSION = "1.0.0"

_RULES_PATH = os.path.join(B.TVBOT, "bot", "rules.py")
_EMAX = None


def emax():
    """Load tvbot/bot/rules.py read-only (it is not a package)."""
    global _EMAX
    if _EMAX is None:
        spec = importlib.util.spec_from_file_location("tvbot_bot_rules_readonly", _RULES_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _EMAX = mod
    return _EMAX


def gold_params(cfg):
    p = dict(GOLD_PARAMS)
    p.update((cfg or {}).get("gold_params") or {})
    return p


def rule_id(kind, cfg):
    if kind in EMA_KINDS:
        m = emax()
        p = m.validate_params((cfg or {}).get("ema_params"))
        rid = m.rule_id(p)
        return rid if kind == "ema" else rid + "-OVERNIGHT"
    if kind == "cash":
        return "CASH-%s" % RULE_VERSION
    p = gold_params(cfg)
    p["kind"] = kind
    p["escalation"] = bool((cfg or {}).get("research_escalation")) and kind in ("gold_basket", "gold_alternating")
    blob = json.dumps(p, sort_keys=True).encode("utf-8")
    return "CHOCH-%s-%s-%s" % (kind.upper(), RULE_VERSION, hashlib.sha256(blob).hexdigest()[:8])


def _sign(x):
    return (x > 0) - (x < 0)


class Book(object):
    def __init__(self):
        self.qty = 0
        self.avg = None
        self.cash = 0.0          # cumulative cash flow from all fills, net of commission
        self.fees = 0.0          # commission + spread/slippage paid versus raw price
        self.basket = None       # {"id", "cash0", "legs": [side,...], "start_ts"}
        self.entry_open = None   # EMAX stop reference (raw open of the entry fill)
        self.baskets_closed = 0


def apply_fill(book, side, qty, raw, costs):
    px = B.side_price(raw, side, costs)
    com = B.commission(qty, costs)
    book.cash -= side * qty * px + com
    book.fees += com + abs(px - raw) * qty
    q = book.qty
    if q == 0 or _sign(q) == side:
        tot = abs(q) + qty
        book.avg = ((book.avg or 0.0) * abs(q) + px * qty) / tot
    elif qty < abs(q):
        pass
    elif qty == abs(q):
        book.avg = None
    else:
        book.avg = px
    book.qty = q + side * qty
    return px, com


def liq_value(qty, price, costs):
    if qty == 0:
        return 0.0
    a, c = B.liq_linear(qty, costs)
    return qty * (a * price + c) - B.commission(abs(qty), costs)


def equity(book, price, costs):
    return book.cash + liq_value(book.qty, price, costs)


def basket_pnl(book, price, costs):
    if book.basket is None:
        return 0.0
    return book.cash - book.basket["cash0"] + liq_value(book.qty, price, costs)


def threshold_price(book, target, costs):
    """Price at which basket P&L (after estimated exit cost) equals target."""
    if book.basket is None or book.qty == 0:
        return None
    a, c = B.liq_linear(book.qty, costs)
    k = book.cash - book.basket["cash0"] - B.commission(abs(book.qty), costs)
    p = ((target - k) / book.qty - c) / a
    return p if p > 0 else None


class Replayer(object):
    def __init__(self, kind, cfg=None):
        self.kind = kind
        self.cfg = dict(cfg or {})
        self.costs = B.cost_cfg(self.cfg)
        self.escalate = bool(self.cfg.get("research_escalation")) and kind in ("gold_basket", "gold_alternating")
        self.session_flat = kind not in ("ema_overnight",) and not self.cfg.get("allow_overnight")
        self.gp = gold_params(self.cfg)
        self.rid = rule_id(kind, self.cfg)
        self.book = Book()
        self.pending = []
        self.i = -1
        self.prev = None
        self.win = []          # last 2*swing+1 bars (high, low, ts)
        self.ph = None         # (level, ts_close of pivot bar)
        self.pl = None
        self.entries_decided = 0
        self.fills = []
        self.events = []
        self.keep = bool(self.cfg.get("keep_records"))
        self.records = []
        self.last = None
        if kind in EMA_KINDS:
            m = emax()
            self.ep = m.validate_params(self.cfg.get("ema_params"))
            self.ind = m.new_indicator_state()
            self.sig = None

    # ---------------------------------------------------------------- fills
    def _fill_pending(self, bar):
        keep = []
        for o in self.pending:
            if o["due"] > self.i:
                keep.append(o)
                continue
            vol = bar.get("volume")
            if vol is not None and vol <= 0:
                if o["kind"] == "exit":
                    o["due"] = self.i + 1
                    keep.append(o)
                self.events.append({"seq": bar.get("seq"), "event": "NOT_FILLED_ZERO_VOLUME", "order": dict(o)})
                continue
            raw = float(bar["open"])
            if o["kind"] == "exit":
                if self.book.qty == 0:
                    continue
                side = -_sign(self.book.qty)
                qty = min(o["qty"], abs(self.book.qty))
            else:
                side = o["side"]
                qty = o["qty"]
                frac = self.cfg.get("partial_frac")
                if frac:
                    qty = int(qty * float(frac))
                if qty <= 0:
                    self.events.append({"seq": bar.get("seq"), "event": "PARTIAL_TO_ZERO", "order": dict(o)})
                    continue
            if self.book.basket is None and o.get("leg"):
                self.book.basket = {"cash0": self.book.cash, "legs": [], "start_ts": bar["ts_open"]}
            was = self.book.qty
            px, com = apply_fill(self.book, side, qty, raw, self.costs)
            if o.get("leg") and self.book.basket is not None:
                self.book.basket["legs"].append(o["side"])
            if self.kind in EMA_KINDS:
                self.book.entry_open = raw if self.book.qty != 0 else None
            self.fills.append({"seq": bar.get("seq"), "ts": bar["ts_open"], "side": side, "qty": qty,
                               "raw_open": raw, "fill_price": round(px, 6), "commission": round(com, 6),
                               "reason_code": o["reason_code"], "decision_id": o["decision_id"],
                               "qty_before": was, "qty_after": self.book.qty, "simulated": True})
            if self.book.qty == 0:
                if self.book.basket is not None:
                    self.book.baskets_closed += 1
                self.book.basket = None
                self.book.avg = None
        self.pending = keep

    # ------------------------------------------------------------ indicators
    def _update_pivots(self, bar):
        s = int(self.gp["swing"])
        self.win.append((float(bar["high"]), float(bar["low"]), bar["ts_close"]))
        n = 2 * s + 1
        if len(self.win) > n:
            self.win.pop(0)
        if len(self.win) == n:
            ch, cl, cts = self.win[s]
            others = self.win[:s] + self.win[s + 1:]
            if all(ch > h for h, _, _ in others):
                self.ph = (ch, cts)
            if all(cl < l for _, l, _ in others):
                self.pl = (cl, cts)
        close = float(bar["close"])
        up = self.ph is not None and close > self.ph[0]
        down = self.pl is not None and close < self.pl[0]
        broke = {"up": self.ph if up else None, "down": self.pl if down else None}
        if up:
            self.ph = None
        if down:
            self.pl = None
        if up and down:
            return 0, broke, "BOTH_BROKEN_SAME_BAR"
        if up:
            return 1, broke, "BREAK_UP"
        if down:
            return -1, broke, "BREAK_DOWN"
        return 0, broke, "NO_BREAK"

    # ------------------------------------------------------------------ step
    def step(self, bar):
        self.i += 1
        if self.prev is not None and not B.same_session(self.prev, bar, self.cfg):
            if self.kind in GOLD_KINDS and self.gp.get("reset_pivots_each_session"):
                self.win, self.ph, self.pl = [], None, None
        self._fill_pending(bar)
        qty_in_bar = self.book.qty
        if self.kind in GOLD_KINDS:
            d = self._decide_gold(bar)
        elif self.kind in EMA_KINDS:
            d = self._decide_ema(bar)
        else:
            d = self._decide_cash(bar)
        if d["action"] in ("enter_long", "enter_short", "exit") and d["qty"] > 0:
            o = {"kind": d.pop("_order_kind"), "side": d.pop("_side"), "qty": d["qty"],
                 "due": self.i + 1 + int(self.cfg.get("delay_bars", 0)), "leg": d.pop("_leg"),
                 "reason_code": d["reason_code"], "decision_id": d["decision_id"]}
            miss = int(self.cfg.get("miss_every") or 0)
            if o["kind"] == "entry" or o["leg"]:
                self.entries_decided += 1
                if miss and self.entries_decided % miss == 0:
                    self.events.append({"seq": bar.get("seq"), "event": "ENTRY_MISSED_STRESS", "order": dict(o)})
                    o = None
            if o is not None:
                self.pending.append(o)
        for k in ("_order_kind", "_side", "_leg"):
            d.pop(k, None)
        d["net_qty_after"] = self.book.qty + sum(
            (o["side"] if o["kind"] == "entry" else -_sign(self.book.qty)) * o["qty"] for o in self.pending
            if o["kind"] == "entry" or self.book.qty != 0)
        if self.keep:
            c, lo, hi = float(bar["close"]), float(bar["low"]), float(bar["high"])
            worst = lo if qty_in_bar > 0 else hi
            self.records.append({
                "i": self.i, "seq": bar.get("seq"), "ts_close": bar["ts_close"],
                "session": B.session_key(bar, self.cfg), "qty_in_bar": qty_in_bar,
                "qty_close": self.book.qty, "eq_close": equity(self.book, c, self.costs),
                "eq_worst": self.book.cash + (liq_value(qty_in_bar, worst, self.costs) if qty_in_bar == self.book.qty else liq_value(self.book.qty, worst, self.costs)),
                "gross_close": abs(self.book.qty) * c, "gross_worst": abs(self.book.qty) * max(c, hi),
                "action": d["action"], "reason_code": d["reason_code"], "fees": self.book.fees,
            })
        self.prev = bar
        self.last = d
        return d

    # --------------------------------------------------------------- helpers
    def _phase(self, bar):
        if not self.session_flat:
            return "open"
        return B.session_phase(bar, self.cfg)

    def _pending_kinds(self):
        return [o["kind"] for o in self.pending]

    def _mk(self, bar, action, qty, code, text, cfor, cagainst, est, pcond, trig, ent, ext, inv,
            checks, order_kind=None, side=0, leg=False, extra=None):
        d = B.make_decision(self.kind, self.rid, bar, action, qty, code, text, cfor, cagainst, est,
                            pcond, trig, ent, ext, inv, extra=extra, refusal_checks=checks)
        d["_order_kind"], d["_side"], d["_leg"] = order_kind, side, leg
        return d

    def _max_loss_check(self, qty, entry_price, stop_price, est):
        """CONTRACT v2 plain-dollar cap, mirrored so a refused entry never
        becomes a phantom position in the strategy's own book.

        risk = qty * |entry - stop| + estimated round-trip cost, the desk's
        formula. The cap is cfg["limits"]["max_loss_per_trade"] (or
        cfg["max_loss_per_trade"]), a TEST VALUE the desk passes in. With no
        cap in cfg the check passes with a note and the order manager
        enforces its own cap. It refuses; it never resizes.
        """
        if stop_price is None:
            return {"id": "NO_STOP", "passed": False, "detail": "entry has no stop price"}
        lims = self.cfg.get("limits")
        lim = lims.get("max_loss_per_trade") if isinstance(lims, dict) else None
        if lim is None:
            lim = self.cfg.get("max_loss_per_trade")
        risk = qty * abs(float(entry_price) - float(stop_price)) + float(est.get("usd") or 0.0)
        if lim is None:
            return {"id": "MAX_LOSS_WOULD_BREACH", "passed": True,
                    "detail": "risk $%.2f; no max_loss_per_trade in cfg, so the order manager enforces its cap" % risk}
        lim = float(lim)
        return {"id": "MAX_LOSS_WOULD_BREACH", "passed": risk <= lim,
                "detail": "qty %d x |%.4f - %.4f| + cost $%.2f = $%.2f vs cap $%.2f (TEST VALUE)"
                          % (qty, float(entry_price), float(stop_price), float(est.get("usd") or 0.0), risk, lim)}

    def _decide_cash(self, bar):
        return self._mk(
            bar, "pass", 0, "CASH_ALWAYS_PASSES",
            "Cash baseline: it never trades, so its result is exactly $0 before and after costs.",
            "Holding cash cannot lose money to costs, gaps or bad fills; it is the bar every strategy must beat after costs.",
            "Cash earns nothing here and misses any real move.",
            B.est_cost(0, None, self.costs, note="cash places no orders"),
            "Always passes. A $0 day is a valid result.",
            B.line(None, "none: cash has no trigger"), B.line(None, "none"), B.line(None, "none"), B.line(None, "none"),
            [{"id": "CASH_BASELINE", "passed": False, "detail": "cash never enters by rule"}])

    # ------------------------------------------------------------------- gold
    def _decide_gold(self, bar):
        g = self.gp
        sig, broke, sig_code = self._update_pivots(bar)
        close = float(bar["close"])
        phase = self._phase(bar)
        book = self.book
        q = book.qty
        bq = B.base_qty(close, self.cfg)
        tgt, stp = float(g["basket_target_usd"]), float(g["basket_stop_usd"])
        pnl = basket_pnl(book, close, self.costs) if book.basket else 0.0
        legs = len(book.basket["legs"]) if book.basket else 0
        cap = 1 if self.kind == "fixed_risk_single" else int(g["leg_cap"])
        checks = []
        ph = self.ph[0] if self.ph else None
        pl = self.pl[0] if self.pl else None
        lv = "swing high %s / swing low %s" % ("%.4f" % ph if ph else "none yet", "%.4f" % pl if pl else "none yet")
        trig_wait = B.line(ph if ph is not None else pl,
                           "Next signal: a close above the unbroken %s, or below the swing low (%s)." % (
                               "swing high" if ph is not None else "swing low", lv))
        hold_ext = B.line(threshold_price(book, tgt, self.costs),
                          "Basket target: exit when basket P&L after costs reaches +$%.2f" % tgt)
        hold_inv = B.line(threshold_price(book, stp, self.costs),
                          "Position-level stop: exit when basket P&L after costs reaches -$%.2f" % abs(stp))
        none = B.line(None, "none")
        name = {"gold_basket": "Reddit gold basket (change-of-character)",
                "gold_alternating": "Gold basket, alternating-only variant",
                "fixed_risk_single": "Fixed-risk single entry",
                "bounded_fixed": "Bounded fixed-size basket"}[self.kind]
        basket_txt = ("basket of %d leg(s), net %+d at avg %.4f, basket P&L after est. exit cost $%.2f"
                      % (legs, q, book.avg or 0.0, pnl)) if book.basket else "flat"

        def exit_dec(code, text, cfor, cagainst):
            return self._mk(bar, "exit", abs(q), code, text, cfor, cagainst,
                            B.est_cost(abs(q), close, self.costs, sides=1, note="one side to close"),
                            "No pass: the frozen rule requires this exit.",
                            B.line(close, "Exit decided at this close (%s)" % basket_txt),
                            B.line(None, "none: this is an exit"),
                            B.line(close, "Desk fill: the next bar's close plus simulated costs (estimated from this close)"),
                            none, checks + [{"id": code, "passed": True, "detail": text}],
                            order_kind="exit", side=-_sign(q))

        if "exit" in self._pending_kinds() or (self.pending and q == 0 and phase != "open"):
            return self._mk(bar, "hold" if q else "pass", 0, "ORDER_WORKING",
                            "An earlier order has not filled yet; no new order until it does.",
                            "Avoids stacking duplicate orders.", "The working order may fill late or not at all.",
                            B.est_cost(0, None, self.costs), "Waits for the working order.",
                            trig_wait, none, hold_ext, hold_inv,
                            [{"id": "ORDER_WORKING", "passed": False, "detail": "%d order(s) working" % len(self.pending)}])
        if phase == "closed":
            if q:
                return exit_dec("OVERNIGHT_RESIDUAL", "Session has ended with a position; close it at the next bar's close plus simulated costs (gap risk).",
                                "The desk must not hold overnight.", "The next bar may gap against the position.")
            return self._mk(bar, "pass", 0, "OUTSIDE_SESSION", "The session's last bar has closed; no entries.",
                            "No fills are possible inside this session.", "None.",
                            B.est_cost(0, None, self.costs), "Entries resume after the next session opens.",
                            trig_wait, none, none, none,
                            [{"id": "OUTSIDE_SESSION", "passed": False, "detail": "phase=closed"}])
        checks.append({"id": "OUTSIDE_SESSION", "passed": True, "detail": "phase=%s" % phase})
        if phase == "flatten":
            if q:
                return exit_dec("SESSION_FLAT", "Next bar is the session's last; flatten so the session ends flat.",
                                "Desk sessions must finish flat.", "Exiting may give up a move that continues.")
            return self._mk(bar, "pass", 0, "NEAR_CLOSE", "Too close to the session end to enter.",
                            "An entry now would have to be closed one bar later.", "None.",
                            B.est_cost(0, None, self.costs), "No entries in the session's last two bars.",
                            trig_wait, none, none, none,
                            checks + [{"id": "NEAR_CLOSE", "passed": False, "detail": "next bar is the session's last"}])
        checks.append({"id": "NEAR_CLOSE", "passed": True, "detail": "entries allowed"})
        if book.basket and q:
            if pnl >= tgt:
                return exit_dec("BASKET_TARGET", "Basket P&L after costs $%.2f reached the +$%.2f target." % (pnl, tgt),
                                "Locks the basket gain.", "The move may continue without us.")
            if pnl <= stp:
                return exit_dec("BASKET_STOP", "Basket P&L after costs $%.2f hit the -$%.2f position-level stop." % (pnl, abs(stp)),
                                "Caps the basket loss at the rule's stop (plus gap/slippage).",
                                "Price may reverse right after the stop.")
        if sig == 0:
            code = "NO_SIGNAL" if sig_code != "BOTH_BROKEN_SAME_BAR" else "BOTH_BROKEN_SAME_BAR"
            return self._mk(bar, "hold" if q else "pass", 0, code,
                            ("No change-of-character break at this close. " if code == "NO_SIGNAL" else
                             "Both swing levels broke on one bar: ambiguous, no signal. ") + basket_txt + ".",
                            "No signal means no reason to trade; cash costs nothing.",
                            "A move can start without a confirmed break.",
                            B.est_cost(0, None, self.costs), "Passes until a close breaks a confirmed swing level.",
                            trig_wait, none, hold_ext if q else none, hold_inv if q else none,
                            checks + [{"id": "NO_SIGNAL", "passed": False, "detail": sig_code}])
        checks.append({"id": "NO_SIGNAL", "passed": True, "detail": sig_code})
        dirn = "long" if sig > 0 else "short"
        lvl = broke["up"] if sig > 0 else broke["down"]
        trig = B.line(lvl[0], "Close %.4f broke the swing %s %.4f confirmed at %s" % (
            close, "high" if sig > 0 else "low", lvl[0], lvl[1]))
        if self.kind == "fixed_risk_single" and q:
            return self._mk(bar, "hold", 0, "SINGLE_ALREADY_IN", "Single-entry rule: already in one position; ignore new breaks.",
                            "Keeps risk to one base leg.", "Ignores a possibly better signal.",
                            B.est_cost(0, None, self.costs), "Holds until target, stop or session flat.",
                            trig, none, hold_ext, hold_inv,
                            checks + [{"id": "LEG_CAP", "passed": False, "detail": "single entry already open"}])
        if legs >= cap:
            return self._mk(bar, "hold" if q else "pass", 0, "LEG_CAP", "Leg cap %d reached; no more adds this basket." % cap,
                            "Bounds the basket's exposure.", "Ignores the new break.",
                            B.est_cost(0, None, self.costs), "Holds until target, stop or session flat.",
                            trig, none, hold_ext, hold_inv,
                            checks + [{"id": "LEG_CAP", "passed": False, "detail": "%d of %d legs" % (legs, cap)}])
        if self.kind == "gold_alternating" and book.basket and book.basket["legs"] and book.basket["legs"][-1] == sig:
            return self._mk(bar, "hold" if q else "pass", 0, "SAME_DIRECTION_SKIPPED",
                            "Alternating variant adds only on a reversal; this break repeats the last leg's direction.",
                            "Follows the alternating reading of the post.", "Skips a confirming break.",
                            B.est_cost(0, None, self.costs), "Waits for an opposite break.",
                            trig, none, hold_ext, hold_inv,
                            checks + [{"id": "ALTERNATING_ONLY", "passed": False, "detail": "same direction as last leg"}])
        checks.append({"id": "LEG_CAP", "passed": True, "detail": "%d of %d legs" % (legs, cap)})
        mult = (2 ** legs) if self.escalate else 1
        lq = bq * mult
        if lq <= 0:
            return self._mk(bar, "hold" if q else "pass", 0, "ZERO_SIZE",
                            "TEST order notional buys less than one unit at this price.",
                            "Refuses fractional sizing (Matthew-only).", "Misses the signal.",
                            B.est_cost(0, None, self.costs), "Passes while one unit costs more than the TEST notional.",
                            trig, none, none, none, checks + [{"id": "ZERO_SIZE", "passed": False, "detail": "qty 0"}])
        est = B.est_cost(lq, close, self.costs, sides=2, note="round trip for this leg")
        if est["usd"] >= abs(stp):
            return self._mk(bar, "hold" if q else "pass", 0, "COST_EXCEEDS_EDGE",
                            "Round-trip cost $%.2f for this leg is at least the $%.2f basket stop: the leg would start at its stop."
                            % (est["usd"], abs(stp)),
                            "Avoids a trade that is stopped out by costs alone.", "Misses the signal.",
                            est, "Passes while the leg's round-trip cost is at least the basket stop.",
                            trig, none, hold_ext if q else none, hold_inv if q else none,
                            checks + [{"id": "COST_EXCEEDS_EDGE", "passed": False,
                                       "detail": "round trip $%.2f >= stop $%.2f" % (est["usd"], abs(stp))}])
        checks.append({"id": "COST_EXCEEDS_EDGE", "passed": True,
                       "detail": "round trip $%.2f < stop $%.2f" % (est["usd"], abs(stp))})
        # Hypothetical book after this leg fills at this close, for the lines.
        hb = copy.deepcopy(book)
        if hb.basket is None:
            hb.basket = {"cash0": hb.cash, "legs": [], "start_ts": bar["ts_close"]}
        apply_fill(hb, sig, lq, close, self.costs)
        ext = B.line(threshold_price(hb, tgt, self.costs),
                     "Basket target +$%.2f after costs (estimate if the leg fills at this close)" % tgt)
        inv = B.line(threshold_price(hb, stp, self.costs),
                     "Position-level stop -$%.2f after costs (estimate if the leg fills at this close)" % abs(stp))
        ent = B.line(close, "Leg %d of %d (%s, %d unit(s)%s) fills at the next bar's close plus simulated costs; this close is the estimate"
                     % (legs + 1, cap, dirn, lq, ", x%d research escalation" % mult if mult > 1 else ""))
        cfor = ("Close broke a confirmed swing level (change of character); the frozen rule %s on it." %
                ("adds a leg" if legs else "opens a basket"))
        cagainst = ("Secondhand Reddit idea; Codex's 2023 gold spot replay lost money across all variants; "
                    "round trip $%.2f eats into a $%.2f target." % (est["usd"], tgt))
        pcond = ("Would pass if no break, leg cap reached, session near close, round-trip cost >= basket stop, "
                 "or qty x |entry - stop| + cost above the desk's max_loss_per_trade.")
        if q == 0 or _sign(q) == sig or lq > abs(q):
            mlc = self._max_loss_check(lq, ent["price"], inv["price"], est)
            if not mlc["passed"]:
                return self._mk(bar, "hold" if q else "pass", 0, mlc["id"],
                                "Entry refused: %s. Size is TEST VALUES and is never cut to fit." % mlc["detail"],
                                "Keeps one trade's worst planned loss inside the desk's cap.", "Misses the signal.",
                                est, "Passes while this leg's planned loss to its stop is above the cap.",
                                trig, none, hold_ext if q else none, hold_inv if q else none, checks + [mlc])
            checks.append(mlc)
        if q == 0 or _sign(q) == sig:
            return self._mk(bar, "enter_long" if sig > 0 else "enter_short", lq, "CHOCH_" + ("LONG" if sig > 0 else "SHORT"),
                            "Change-of-character break %s; %s." % (dirn, basket_txt), cfor, cagainst, est, pcond,
                            trig, ent, ext, inv, checks, order_kind="entry", side=sig, leg=True,
                            extra={"basket": {"legs_before": legs, "leg_qty": lq, "escalation_mult": mult}})
        if lq <= abs(q):
            return self._mk(bar, "exit", lq, "BASKET_REVERSE_LEG",
                            "Opposite break: the reverse leg nets against the basket, reducing the position by %d; %s."
                            % (lq, basket_txt), cfor, cagainst, est, pcond, trig, ent, ext, inv, checks,
                            order_kind="exit", side=sig, leg=True,
                            extra={"basket": {"legs_before": legs, "leg_qty": lq, "escalation_mult": mult}})
        return self._mk(bar, "enter_long" if sig > 0 else "enter_short", lq, "BASKET_REVERSE_FLIP",
                        "Research-only: the escalated reverse leg (%d) exceeds the net position (%d) and flips it." % (lq, q),
                        cfor, cagainst, est, pcond, trig, ent, ext, inv, checks, order_kind="entry", side=sig, leg=True,
                        extra={"basket": {"legs_before": legs, "leg_qty": lq, "escalation_mult": mult}})

    # -------------------------------------------------------------------- ema
    def _decide_ema(self, bar):
        m = emax()
        close = float(bar["close"])
        self.ind = m.step_indicators(self.ind, close, self.ep)
        s = m.signals(self.ind, self.ep)
        phase = self._phase(bar)
        q = self.book.qty
        none = B.line(None, "none")
        f, sl = self.ind.get("fast"), self.ind.get("slow")
        state = "fast EMA %.4f vs slow EMA %.4f" % (f or 0.0, sl or 0.0)
        stop_px = self.book.entry_open * (1 - self.ep["stop_pct"] / 100.0) if self.book.entry_open else None
        hold_ext = B.line(None, "Exit at the next bar's close plus simulated costs after the fast EMA crosses below the slow EMA")
        hold_inv = B.line(stop_px, "Stop: a close at or below %.1f%% under the entry open" % self.ep["stop_pct"])
        trig_wait = B.line(None, "Next signal: fast EMA(%d) crosses above slow EMA(%d); now %s" % (
            self.ep["fast_len"], self.ep["slow_len"], state))
        checks = []

        def exit_dec(code, text, cfor, cagainst):
            return self._mk(bar, "exit", abs(q), code, text, cfor, cagainst,
                            B.est_cost(abs(q), close, self.costs, sides=1, note="one side to close"),
                            "No pass: the frozen rule requires this exit.",
                            B.line(close, text), none,
                            B.line(close, "Desk fill: the next bar's close plus simulated costs (estimated from this close)"), none,
                            checks + [{"id": code, "passed": True, "detail": text}],
                            order_kind="exit", side=-_sign(q))

        if "exit" in self._pending_kinds() or (self.pending and q == 0):
            return self._mk(bar, "hold" if q else "pass", 0, "ORDER_WORKING",
                            "An earlier order has not filled yet.", "Avoids duplicate orders.", "It may fill late.",
                            B.est_cost(0, None, self.costs), "Waits for the working order.",
                            trig_wait, none, hold_ext, hold_inv,
                            [{"id": "ORDER_WORKING", "passed": False, "detail": "%d working" % len(self.pending)}])
        if phase == "closed":
            if q:
                return exit_dec("OVERNIGHT_RESIDUAL", "Session ended with a position; close at the next bar's close plus simulated costs.",
                                "The desk must not hold overnight.", "The open may gap.")
            return self._mk(bar, "pass", 0, "OUTSIDE_SESSION", "Session's last bar has closed; no entries.",
                            "No fills possible this session.", "None.", B.est_cost(0, None, self.costs),
                            "Entries resume next session.", trig_wait, none, none, none,
                            [{"id": "OUTSIDE_SESSION", "passed": False, "detail": "phase=closed"}])
        checks.append({"id": "OUTSIDE_SESSION", "passed": True, "detail": "phase=%s" % phase})
        if phase == "flatten":
            if q:
                return exit_dec("SESSION_FLAT", "Next bar is the session's last; flatten so the session ends flat.",
                                "Desk sessions must finish flat (EMAX as frozen holds overnight; that runs in research only).",
                                "Cuts a trend trade short.")
            return self._mk(bar, "pass", 0, "NEAR_CLOSE", "Too close to the session end to enter.",
                            "An entry would be closed one bar later.", "None.", B.est_cost(0, None, self.costs),
                            "No entries in the session's last two bars.", trig_wait, none, none, none,
                            checks + [{"id": "NEAR_CLOSE", "passed": False, "detail": "next bar is the session's last"}])
        checks.append({"id": "NEAR_CLOSE", "passed": True, "detail": "entries allowed"})
        if q:
            if stop_px is not None and close <= stop_px:
                return exit_dec("STOP", "Close %.4f is at or below the stop %.4f." % (close, stop_px),
                                "Caps the loss per the frozen EMAX rule.", "Price may recover.")
            if s["cross_down"]:
                return exit_dec("CROSS_DOWN", "Fast EMA crossed below slow EMA (%s)." % state,
                                "Trend signal reversed.", "Crossovers lag and whipsaw.")
            return self._mk(bar, "hold", 0, "HOLD_IN_TREND", "Holding long; no stop or cross-down (%s)." % state,
                            "Trend still up.", "Open risk to the stop.", B.est_cost(0, None, self.costs),
                            "Holds until stop, cross-down or session flat.", trig_wait, none, hold_ext, hold_inv,
                            checks + [{"id": "NO_SIGNAL", "passed": False, "detail": "holding"}])
        if not s["ready"]:
            return self._mk(bar, "pass", 0, "WARMUP", "Warm-up: %d of %d bars." % (self.ind["n"], self.ep["warmup_bars"]),
                            "Averages are not settled yet.", "None.", B.est_cost(0, None, self.costs),
                            "Passes until %d bars have closed." % self.ep["warmup_bars"], trig_wait, none, none, none,
                            checks + [{"id": "WARMUP", "passed": False, "detail": "n=%d" % self.ind["n"]}])
        checks.append({"id": "WARMUP", "passed": True, "detail": "n=%d" % self.ind["n"]})
        if not s["cross_up"]:
            return self._mk(bar, "pass", 0, "NO_SIGNAL", "No cross-up (%s)." % state,
                            "No signal, no trade.", "A move may start without a cross.", B.est_cost(0, None, self.costs),
                            "Passes until the fast EMA crosses above the slow EMA.", trig_wait, none, none, none,
                            checks + [{"id": "NO_SIGNAL", "passed": False, "detail": "no cross-up"}])
        checks.append({"id": "NO_SIGNAL", "passed": True, "detail": "cross-up"})
        bq = B.base_qty(close, self.cfg)
        if bq <= 0:
            return self._mk(bar, "pass", 0, "ZERO_SIZE", "TEST notional buys less than one unit.",
                            "No fractional sizing.", "Misses the signal.", B.est_cost(0, None, self.costs),
                            "Passes while one unit costs more than the TEST notional.", trig_wait, none, none, none,
                            checks + [{"id": "ZERO_SIZE", "passed": False, "detail": "qty 0"}])
        est = B.est_cost(bq, close, self.costs, sides=2, note="round trip")
        stop_est = close * (1 - self.ep["stop_pct"] / 100.0)
        mlc = self._max_loss_check(bq, close, stop_est, est)
        if not mlc["passed"]:
            return self._mk(bar, "pass", 0, mlc["id"],
                            "Cross-up entry refused: %s. Size is TEST VALUES and is never cut to fit." % mlc["detail"],
                            "Keeps one trade's worst planned loss inside the desk's cap.", "Misses the signal.",
                            est, "Passes while the planned loss to the %.1f%% stop is above the cap." % self.ep["stop_pct"],
                            B.line(close, "Cross-up confirmed at this close (%s)" % state), none, none, none,
                            checks + [mlc])
        checks.append(mlc)
        return self._mk(bar, "enter_long", bq, "CROSS_UP", "Fast EMA crossed above slow EMA (%s)." % state,
                        "Frozen EMAX trend entry (EMAX-1.0.0); the existing desk rule.",
                        "EMAX's own holdout was already used on 2026-11-14 with no evidence of an edge; crossovers whipsaw.",
                        est, "Would pass with no cross-up, during warm-up or near the session end.",
                        B.line(close, "Cross-up confirmed at this close (%s)" % state),
                        B.line(close, "Long %d at the next bar's close plus simulated costs; this close is the estimate" % bq),
                        hold_ext, B.line(stop_est, "Stop %.1f%% under the entry open (estimated from this close)" % self.ep["stop_pct"]),
                        checks, order_kind="entry", side=1, leg=False)


def run(kind, bars, cfg=None):
    """Replay all bars; returns the Replayer (records kept if cfg says so)."""
    r = Replayer(kind, cfg)
    for b in bars:
        r.step(b)
    return r
