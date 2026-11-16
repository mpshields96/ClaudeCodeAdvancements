"""Local desk server (worker B, ui/).

Stdlib `http.server` only. Binds to loopback only and never fetches anything
external. Every route reads the state directory the session runner writes
(see desk/CONTRACT.md "State directory files"); the three control routes
append `{ts, action, body}` to `control_requests.jsonl` and then call the
SessionController (CONTRACT v2) when one is attached.

Run standalone against a state dir:
    /usr/bin/python3 -I <abs>/desk/ui/server.py --state-dir <abs>/desk/ui/sample_state
"""

import argparse
import inspect
import json
import os
import re
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

UI_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(UI_DIR, "index.html")
LAB_PATH = os.path.join(UI_DIR, "lab.html")      # W2's standalone decision-lab page
SPY_STUDY_PATH = os.path.join(UI_DIR, "spy_study.html")   # Codex's historical SPY study (hindsight)
DESK_DIR = os.path.dirname(UI_DIR)


def _sizing():
    """alpaca.sizing, imported on first use. `python3 -I ui/server.py` does not put desk/ on
    sys.path, so add it here. The module reads only the state dir's limits files."""
    if DESK_DIR not in sys.path:
        sys.path.insert(0, DESK_DIR)
    from alpaca import sizing  # noqa: WPS433
    return sizing

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# Stated before any session result (CONTRACT v2). review.json's pass_rule wins
# when the session runner writes one; this text is the UI's fallback.
PASS_HYPOTHETICAL_BARS = 7
RULE_BEST_PASS = (
    "Best reasoned pass = among the pass decisions, the one with the most failed "
    "refusal checks (passed == false); ties go to the earliest ts_knowable. "
    "The later price path is shown only after Reveal, is labeled HYPOTHETICAL "
    "and is never added to P&L. An avoided loss is never counted as profit."
)

MARKER_ACTIONS = ("enter_long", "enter_short", "exit", "pass")
# route -> (request name, controller method). Kept as 2-tuples so desk/launch.py
# can add its own no-argument routes; arguments come from _plan_call().
CONTROL_ROUTES = {
    "/api/arm": ("arm", "arm"),
    "/api/advance": ("advance", "advance"),
    "/api/play": ("play", "play"),
    "/api/pause": ("pause", "pause"),
    "/api/resume": ("resume", "resume"),
    "/api/stop_close": ("stop_close", "stop_and_close"),
    "/api/clear_stop": ("clear_stop", "clear_stop"),
    "/api/schedule": ("schedule", "set_schedule"),
    "/api/close_session": ("close_session", "close_session"),
    # Alpaca paper adapter (alpaca/CONTRACT.md sections 5-6). Served only when the attached
    # controller has the method; otherwise 501 and nothing is queued for later.
    "/api/alpaca/enable": ("alpaca_enable", "alpaca_enable"),
    "/api/alpaca/disable": ("alpaca_disable", "alpaca_disable"),
    "/api/alpaca/reconcile": ("alpaca_reconcile", "reconcile_now"),
    # read-only live connection check (GET requests only on the controller side); no confirm, no args
    "/api/alpaca/connection_check": ("alpaca_connection_check", "connection_check"),
}
ALPACA_REQUESTS = ("alpaca_enable", "alpaca_disable", "alpaca_reconcile", "alpaca_connection_check")
CONFIRM_REQUIRED = ("stop_close", "clear_stop", "alpaca_enable")
CONFIRM_LABELS = {"stop_close": "Stop & Close", "clear_stop": "Clear Stop", "alpaca_enable": "Enable"}
# Setup panel worksheet (alpaca/sizing.py). Draft and approve write only this desk's
# limits_draft.json / limits_approved.json; effects is arithmetic and writes nothing.
LIMITS_ROUTES = ("/api/limits/draft", "/api/limits/effects", "/api/limits/approve")
EFFECT_KEYS = ("ref_price", "stop_distance", "fee_per_share", "slippage_per_share",
               "open_exposure", "realized_loss_today", "working_notional")
LAB_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,200}")
TV_SCRIPT_ORIGIN = "https://s3.tradingview.com"
TV_FRAME_ORIGINS = ("https://s.tradingview.com", "https://www.tradingview-widget.com",
                    "https://www.tradingview.com")
BODY_KEYS = ("n", "bars_per_sec", "enabled", "confirm", "note", "week", "reason")
WEEK_RE = re.compile(r"[0-9]{4}-W[0-9]{2}")
MAX_ADVANCE = 500
MAX_PLAY_RATE = 50.0


def _plan_call(request, method_name, body):
    """Return (method_name, kwargs, fallbacks) for a control request, or raise
    ValueError with a plain message. Fallbacks are (method_name, kwargs) pairs
    tried when the attached controller lacks the first method."""
    if request == "advance":
        try:
            n = int(body.get("n", 1))
        except (TypeError, ValueError):
            raise ValueError("n must be a whole number of bars")
        return method_name, {"n": max(1, min(n, MAX_ADVANCE))}, ()
    if request == "play":
        try:
            rate = float(body.get("bars_per_sec", 4.0))
        except (TypeError, ValueError):
            raise ValueError("bars_per_sec must be a number")
        if rate != rate or rate <= 0:  # NaN or 0 means stop playing (CONTRACT v2)
            return "stop_play", {}, (("pause_play", {}),)
        return method_name, {"bars_per_sec": min(rate, MAX_PLAY_RATE)}, ()
    if request in ("clear_stop", "alpaca_enable"):
        return method_name, {"confirm": True}, ()
    if request == "alpaca_disable":
        reason = body.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("give a short reason for disabling the adapter")
        return method_name, {"reason": reason.strip()[:200]}, ()
    if request == "weekly_report":
        week = body.get("week")
        if week is None or week == "":
            return method_name, {}, ()
        if not isinstance(week, str) or not WEEK_RE.fullmatch(week):
            raise ValueError("week must look like 2026-W40")
        return method_name, {"week": week}, ()
    if request == "schedule":
        enabled = body.get("enabled") is True
        return method_name, {"enabled": enabled}, (
            ("schedule_on" if enabled else "schedule_off", {}),)
    return method_name, {}, ()


def _clean_body(body):
    out = {}
    for key in BODY_KEYS:
        if key in body:
            val = body[key]
            if isinstance(val, (bool, int, float)) or val is None:
                out[key] = val
            else:
                out[key] = str(val)[:200]
    return out


def _call_flex(method, kwargs):
    """Call with the kwargs the method accepts. A no-argument advance() is
    called n times so the launcher's DeskControls and the SessionController
    behave the same."""
    try:
        params = inspect.signature(method).parameters
        var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
    except (TypeError, ValueError):
        params, var_kw = {}, False
    use = dict((k, v) for k, v in kwargs.items() if var_kw or k in params)
    dropped = [k for k in kwargs if k not in use]
    if dropped == ["n"]:
        out = None
        for _ in range(int(kwargs["n"])):
            out = method()
            if isinstance(out, dict) and out.get("ok") is False:
                break
        return out, ["n (called %d times)" % int(kwargs["n"])]
    return method(**use), dropped


# --------------------------------------------------------------------------
# State reading helpers
# --------------------------------------------------------------------------

def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_meta(path):
    meta = {"file": os.path.basename(path), "exists": os.path.exists(path),
            "server_utc": utc_now_iso()}
    if meta["exists"]:
        mtime = os.path.getmtime(path)
        meta["mtime_utc"] = datetime.fromtimestamp(mtime, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        meta["age_s"] = round(time.time() - mtime, 1)
    return meta


def read_json(path):
    """Return (obj_or_None, meta). Tolerates a missing or half-written file."""
    meta = _file_meta(path)
    if not meta["exists"]:
        return None, meta
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), meta
    except (ValueError, OSError) as exc:
        meta["error"] = "unreadable: %s" % exc.__class__.__name__
        return None, meta


def read_jsonl(path):
    """Return (rows, meta). Skips blank and unparseable lines (a writer may be
    mid-line) and reports how many were skipped."""
    meta = _file_meta(path)
    rows = []
    skipped = 0
    if meta["exists"]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        skipped += 1
                        continue
                    if isinstance(obj, dict):
                        rows.append(obj)
                    else:
                        skipped += 1
        except OSError as exc:
            meta["error"] = "unreadable: %s" % exc.__class__.__name__
    meta["skipped_lines"] = skipped
    return rows, meta


def _num(value):
    """A float or None. Strategy decision lines are {"price": float, "text": str}
    objects (strategies/base.py line()); the price is unwrapped first so those
    lines are never shown blank."""
    if isinstance(value, dict):
        value = value.get("price")
    try:
        if value is None or isinstance(value, bool):
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


LINE_FIELDS = ("trigger", "intended_entry", "intended_exit", "invalidation")


def decision_lines(decision):
    """{field: {"price": float|None, "text": str|None}} for the four decision
    lines, whichever shape the decision row used (plain number or object)."""
    out = {}
    for key in LINE_FIELDS:
        raw = decision.get(key) if isinstance(decision, dict) else None
        text = raw.get("text") if isinstance(raw, dict) else None
        out[key] = {"price": _num(raw), "text": None if text is None else str(text)}
    return out


def _cost_usd(est):
    """est_cost is {"usd": ...} from strategies/base.py est_cost(), or a number."""
    if isinstance(est, dict):
        est = est.get("usd")
    return _num(est)


def _with_lines(decision):
    out = dict(decision)
    out["lines"] = decision_lines(decision)
    out["est_cost_usd"] = _cost_usd(decision.get("est_cost"))
    return out


BARS_SOURCE_REPLAY = "desk replay bars (state_dir/bars.jsonl), never TradingView"
BARS_SOURCE_ALPACA = ("alpaca session bars (state_dir/alpaca_bars.jsonl; synthetic in mock mode, "
                      "Alpaca free IEX in paper mode), never TradingView")


def _bars_file(state_dir):
    """Replay sessions write bars.jsonl; the Alpaca session writes alpaca_bars.jsonl."""
    replay = os.path.join(state_dir, "bars.jsonl")
    alpaca = os.path.join(state_dir, "alpaca_bars.jsonl")
    sess, _ = read_json(os.path.join(state_dir, "session.json"))
    mode = str(sess.get("broker_mode") or "") if isinstance(sess, dict) else ""
    if mode.startswith("alpaca") or (not os.path.exists(replay) and os.path.exists(alpaca)):
        return alpaca, BARS_SOURCE_ALPACA
    return replay, BARS_SOURCE_REPLAY


def _bars(state_dir):
    path, source = _bars_file(state_dir)
    rows, meta = read_jsonl(path)
    meta["bars_source"] = source
    manifest = None
    bars = []
    for row in rows:
        if row.get("type") == "manifest":
            manifest = row
            continue
        bars.append(row)
    bars.sort(key=lambda b: (str(b.get("ts_close", "")), b.get("seq", 0)))
    return bars, manifest, meta


def _strip_outcome(decision):
    out = dict(decision)
    has = "outcome" in out and out.get("outcome") is not None
    out.pop("outcome", None)
    out["has_outcome"] = bool(has)
    return out


# --------------------------------------------------------------------------
# Review (server-side so it is testable; review.json keys win when present)
# --------------------------------------------------------------------------

def _filled_qty(row):
    total = 0.0
    for fill in row.get("fills") or []:
        q = _num(fill.get("qty"))
        if q is not None:
            total += abs(q)
    return total


def _failed_checks(decision):
    return sum(1 for c in decision.get("refusal_checks") or []
               if isinstance(c, dict) and c.get("passed") is False)


def _hypothetical_path(decision, bars):
    """Bars after a pass. Served only behind Reveal; never in P&L."""
    ts = str(decision.get("ts_knowable") or "")
    later = [b for b in bars if str(b.get("ts_close", "")) > ts][:PASS_HYPOTHETICAL_BARS]
    if not later:
        return {"label": "HYPOTHETICAL", "counted_in_pnl": False, "note": "no later bars yet"}
    highs = [_num(b.get("high")) for b in later if _num(b.get("high")) is not None]
    lows = [_num(b.get("low")) for b in later if _num(b.get("low")) is not None]
    return {"label": "HYPOTHETICAL", "counted_in_pnl": False,
            "next_open": _num(later[0].get("open")),
            "max_high_next_%d" % PASS_HYPOTHETICAL_BARS: max(highs) if highs else None,
            "min_low_next_%d" % PASS_HYPOTHETICAL_BARS: min(lows) if lows else None,
            "close_after_%d" % PASS_HYPOTHETICAL_BARS: _num(later[-1].get("close")),
            "bars": len(later)}


def _flat_pass(decision, failed=None, hypothetical=None):
    out = {}
    for key in ("decision_id", "ts_knowable", "symbol", "strategy", "reason_code", "reason_text",
                "pass_condition", "case_for", "case_against", "refusal_checks"):
        if key in decision:
            out[key] = decision[key]
    out["failed_refusal_checks"] = _failed_checks(decision) if failed is None else failed
    if hypothetical is not None:
        out["hypothetical_after_reveal"] = hypothetical
    out["hypothetical"] = True
    out["counted_in_pnl"] = False
    return out


def _best_pass_v2(decisions, bars):
    passes = [d for d in decisions if d.get("action") == "pass"]
    if not passes:
        return None, 0
    best = sorted(passes, key=lambda d: (-_failed_checks(d), str(d.get("ts_knowable") or "")))[0]
    return _flat_pass(best, hypothetical=_hypothetical_path(best, bars)), len(passes)


def _norm_trip(trip):
    """Coordinator round trip {entry_decision_id, net_pnl, fills...} -> card fields."""
    if not isinstance(trip, dict):
        return trip
    out = dict(trip)
    if out.get("pnl_net") is None and out.get("net_pnl") is not None:
        out["pnl_net"] = out["net_pnl"]
    out.setdefault("decision_id", out.get("entry_decision_id"))
    out.setdefault("signal_ts", out.get("entry_ts"))
    out.setdefault("trade_id", out.get("entry_decision_id"))
    fills = [f for f in out.get("fills") or [] if isinstance(f, dict)]
    if fills and out.get("avg_entry") is None:
        side = fills[0].get("side")
        ent = [f for f in fills if f.get("side") == side]
        ext = [f for f in fills if f.get("side") != side]

        def vwap(rows):
            q = sum(abs(_num(f.get("qty")) or 0) for f in rows)
            if not q:
                return None
            return round(sum(abs(_num(f.get("qty")) or 0) * (_num(f.get("price")) or 0) for f in rows) / q, 6)
        out["avg_entry"] = vwap(ent)
        out["avg_exit"] = vwap(ext)
        out.setdefault("qty", sum(abs(_num(f.get("qty")) or 0) for f in ent))
    return out


def _normalize_file_review(fr):
    """Map the session runner's review.json (CONTRACT v2 / desk/session.py) onto
    the keys the page renders. Values are kept; only the shape changes."""
    out = dict(fr)
    if fr.get("pass_rule") and not fr.get("best_pass_rule"):
        out["best_pass_rule"] = fr["pass_rule"]
    bp = fr.get("best_pass")
    if isinstance(bp, dict) and isinstance(bp.get("decision"), dict):
        out["best_pass"] = _flat_pass(bp["decision"], bp.get("failed_refusal_checks"),
                                      bp.get("hypothetical_after_reveal"))
    for key in ("best_trade", "worst_trade"):
        if key in fr:
            out[key] = _norm_trip(fr[key])
    if "no_trade_filled" in fr and "no_fills" not in fr:
        out["no_fills"] = bool(fr["no_trade_filled"])
    if fr.get("no_trade_note") and not fr.get("trade_note"):
        out["trade_note"] = fr["no_trade_note"]
    cmp_ = fr.get("comparison")
    if isinstance(cmp_, list):
        metrics = [m for m in cmp_ if isinstance(m, dict)]

        def metric(word):
            for m in metrics:  # an exact metric name wins ("round trips" vs "... of closed mock round trips")
                if str(m.get("metric", "")).lower().strip() in (word, word + "s"):
                    return m.get("value")
            for m in metrics:
                if word in str(m.get("metric", "")).lower():
                    return m.get("value")
            return None
        out["comparison"] = {
            "rows": [
                {"name": fr.get("strategy") or "session strategy", "trades": metric("round trip"),
                 "fees": metric("fees"), "net_after_cost": metric("after-cost"),
                 "source": "review.json (session runner)"},
                {"name": "cash", "trades": 0, "fees": 0.0, "net_after_cost": 0.0,
                 "source": "added by the UI: cash is $0.00 by definition (no position)"},
            ],
            "metrics": metrics,
            "spread_note": ("Replay on synthetic bars: no real spreads exist here. Costs are the "
                            "runner's modeled fees and fill rule."),
            "simulated": True,
        }
    oa = fr.get("operating_audit")
    if isinstance(oa, list):
        out["operating_audit"] = {"runner_checks": [c for c in oa if isinstance(c, dict)]}
    return out


def _runner_check_rows(rows):
    out = []
    for c in rows:
        name = str(c.get("check", "check"))
        rest = dict((k, v) for k, v in c.items() if k != "check")
        empty = all(v in (None, [], {}, 0) for v in rest.values())
        if name == "alarms":
            status = "ok" if empty else "attention"
        elif name == "anomalies":
            status = "ok" if empty else "attention"
        else:
            status = "info"
        detail = ", ".join("%s %s" % (k, json.dumps(v, sort_keys=True, default=str)) for k, v in rest.items())
        out.append({"name": name + " (runner)", "status": status,
                    "detail": detail[:400] + ("..." if len(detail) > 400 else "")})
    return out


REPORT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.(pdf|html)$")


def list_reports(state_dir):
    """Report files the strategies worker wrote to <state_dir>/reports/ (.pdf/.html only)."""
    d = os.path.join(state_dir, "reports")
    try:
        names = os.listdir(d)
    except OSError:
        return []
    return sorted(n for n in names if REPORT_NAME.match(n) and ".." not in n
                  and os.path.isfile(os.path.join(d, n)))


def report_path(state_dir, name):
    """Absolute path of a report inside <state_dir>/reports/, or None. Path-safe."""
    if not isinstance(name, str) or not REPORT_NAME.match(name) or ".." in name:
        return None
    base = os.path.realpath(os.path.join(state_dir, "reports"))
    full = os.path.realpath(os.path.join(base, name))
    if os.path.dirname(full) != base or not os.path.isfile(full):
        return None
    return full


def _all_round_trips(file_review):
    """Every round trip in review.json: the top level plus each week, de-duplicated."""
    seen, out = set(), []
    parts = [file_review] + list((file_review.get("by_week") or {}).values()) \
        if isinstance(file_review.get("by_week"), dict) else [file_review]
    for part in parts:
        for t in (part.get("round_trips") or []) if isinstance(part, dict) else []:
            if not isinstance(t, dict):
                continue
            key = (t.get("entry_decision_id"), t.get("entry_ts"), t.get("exit_ts"))
            if key not in seen:
                seen.add(key)
                out.append(t)
    return out


def outcome_from_round_trip(trip):
    """Flat, revealed-only outcome for a decision whose round trip closed (mock fills)."""
    fills = [f for f in trip.get("fills") or [] if isinstance(f, dict)]
    ent = [f for f in fills if f.get("kind") == "entry"] or fills[:1]
    ext = [f for f in fills if f.get("kind") == "exit"] or [f for f in fills if f not in ent]
    t = _norm_trip(trip)
    return {
        "status": "round trip closed (%s)" % (trip.get("exit_kind") or "exit"),
        "side": trip.get("side"),
        "entry_fill_ids": ", ".join(str(f.get("intent_id")) for f in ent) or "-",
        "entry_fill_ts": trip.get("entry_ts"),
        "avg_entry": t.get("avg_entry"),
        "exit_fill_ids": ", ".join(str(f.get("intent_id")) for f in ext) or "-",
        "exit_fill_ts": trip.get("exit_ts"),
        "avg_exit": t.get("avg_exit"),
        "qty": t.get("qty"),
        "gross_pnl": trip.get("gross_pnl"),
        "fees": trip.get("fees"),
        "net_pnl": trip.get("net_pnl"),
        "fills": "%d MOCK FILL(s)" % len(fills),
        "source": "review.json round_trips (session runner), joined on entry_decision_id",
        "simulated": True,
    }


def build_review(state_dir, reveal_pass=False, week=None):
    session, _ = read_json(os.path.join(state_dir, "session.json"))
    session = session or {}
    ledger, _ = read_jsonl(os.path.join(state_dir, "ledger.jsonl"))
    decisions, _ = read_jsonl(os.path.join(state_dir, "decisions.jsonl"))
    audit, _ = read_jsonl(os.path.join(state_dir, "audit.jsonl"))
    controls, _ = read_json(os.path.join(state_dir, "controls.json"))
    requests, _ = read_jsonl(os.path.join(state_dir, "control_requests.jsonl"))
    bars, _, _ = _bars(state_dir)
    file_review, file_meta = read_json(os.path.join(state_dir, "review.json"))
    if not isinstance(file_review, dict):
        file_review = {}
    # Weekly review (session.py): top level is the default week; by_week holds every week.
    weeks = [w for w in (file_review.get("weeks") or []) if isinstance(w, str)]
    by_week = file_review.get("by_week") if isinstance(file_review.get("by_week"), dict) else {}
    default_week = file_review.get("default_week") or (weeks[-1] if weeks else None)
    selected_week = week if (week and week in by_week) else default_week
    if week and week in by_week:
        file_review = dict(by_week[week])
    file_review = dict(file_review)
    file_review.pop("by_week", None)  # each week's hypothetical path stays hidden
    weekly = bool(by_week)
    file_review = _normalize_file_review(file_review)

    filled = [r for r in ledger if _filled_qty(r) > 0 and _num(r.get("pnl_net")) is not None]
    still_open = [r for r in ledger if _filled_qty(r) > 0 and _num(r.get("pnl_net")) is None]
    computed = {}
    if filled:
        best = max(filled, key=lambda r: _num(r.get("pnl_net")))
        worst = min(filled, key=lambda r: _num(r.get("pnl_net")))
        computed["best_trade"] = best
        computed["worst_trade"] = worst
        computed["no_fills"] = False
        if best is worst:
            computed["trade_note"] = "Only one trade filled, so the best and worst net trade are the same trade."
    else:
        computed["best_trade"] = None
        computed["worst_trade"] = None
        computed["no_fills"] = not still_open
        if still_open:
            computed["trade_note"] = ("%d trade(s) filled and still open. Best and worst net trade "
                                      "wait until a trade closes." % len(still_open))
        else:
            computed["trade_note"] = ("No trade filled in this session. There is no best or worst "
                                      "trade to show, and none has been invented.")

    best_pass, n_pass = _best_pass_v2(decisions, bars)
    computed["best_pass_rule"] = RULE_BEST_PASS
    computed["best_pass"] = best_pass
    computed["pass_candidates"] = n_pass

    net = sum(_num(r.get("pnl_net")) or 0.0 for r in filled)
    fees = sum(_num(r.get("fees")) or 0.0 for r in filled)
    computed["comparison"] = {
        "rows": [
            {"name": session.get("strategy") or "session strategy", "trades": len(filled),
             "fees": round(fees, 6), "net_after_cost": round(net, 6),
             "source": "ledger.jsonl, closed trades" + (
                 "; %d open trade(s) not counted (see P&L)" % len(still_open) if still_open else "")},
            {"name": "cash", "trades": 0, "fees": 0.0, "net_after_cost": 0.0,
             "source": "by definition (no position)"},
        ],
        "spread_note": ("Replay on synthetic bars: no real spreads exist here. Costs are the "
                        "runner's modeled fees and fill rule."),
        "simulated": True,
    }

    computed["operating_audit"] = _operating_audit(session, audit, controls, requests, ledger)
    computed["simulated"] = True

    review = {}
    source_of = {}
    for key, value in computed.items():
        # With a weekly review the runner's value is the week's value, even when empty:
        # a no-fill week must not borrow trades from the whole session's ledger.
        if key in file_review and (file_review[key] is not None or weekly):
            review[key] = file_review[key]
            source_of[key] = "review.json"
        else:
            review[key] = value
            source_of[key] = "ui-computed"
    for key, value in file_review.items():
        if key not in review:
            review[key] = value
            source_of[key] = "review.json"
    # A runner's audit list is shown first, then the UI's own checks.
    if isinstance(file_review.get("operating_audit"), dict) and "runner_checks" in file_review["operating_audit"]:
        oa = dict(computed["operating_audit"])
        oa["checks"] = _runner_check_rows(file_review["operating_audit"]["runner_checks"]) + list(oa.get("checks") or [])
        review["operating_audit"] = oa
        source_of["operating_audit"] = "review.json + ui-computed"
    # A runner's best trade replaces the UI's "still open" note.
    if source_of.get("best_trade") == "review.json" and review.get("best_trade"):
        review["no_fills"] = False
        same = review.get("worst_trade") and (review["best_trade"].get("decision_id") ==
                                              review["worst_trade"].get("decision_id"))
        review["trade_note"] = file_review.get("trade_note") or (
            "Only one round trip closed, so the best and worst net trade are the same trade." if same else None)
    knowable = {}
    for d in decisions:
        if d.get("decision_id") and d.get("ts_knowable"):
            knowable[str(d["decision_id"])] = d["ts_knowable"]
    for key in ("best_trade", "worst_trade"):
        t = review.get(key)
        if isinstance(t, dict) and str(t.get("decision_id")) in knowable:
            t = dict(t)
            t["first_fill_ts"] = t.get("entry_ts") or t.get("signal_ts")
            t["signal_ts"] = knowable[str(t["decision_id"])]  # when the decision was knowable
            review[key] = t
    if not file_review.get("best_pass_rule"):
        review["best_pass_rule"] = RULE_BEST_PASS
    bp = review.get("best_pass")
    if isinstance(bp, dict):
        bp = dict(bp)
        bp["hypothetical"] = True
        bp["counted_in_pnl"] = False
        if not reveal_pass:
            bp["hypothetical_hidden"] = "hypothetical_after_reveal" in bp
            bp.pop("hypothetical_after_reveal", None)
        review["best_pass"] = bp
    review["source_of"] = source_of
    review["weeks"] = weeks
    review["default_week"] = default_week
    review["week"] = selected_week
    reports = list_reports(state_dir)
    review["reports"] = reports
    stem = "report_%s" % re.sub(r"[^0-9A-Za-z_-]", "_", selected_week or "all")
    review["week_report"] = next((n for n in (stem + ".pdf", stem + ".html") if n in reports), None)
    review["_meta"] = file_meta
    return review


def _blob(entry):
    try:
        return json.dumps(entry, sort_keys=True).lower()
    except (TypeError, ValueError):
        return ""


def _operating_audit(session, audit, controls, requests, ledger):
    counts = {}
    for entry in audit:
        kind = str(entry.get("kind", "?"))
        counts[kind] = counts.get(kind, 0) + 1
    alarms = [e for e in audit if e.get("kind") == "alarm"]
    rejected = [e for e in audit if e.get("kind") == "rejected"]
    control_entries = [e for e in audit if e.get("kind") == "control"]
    controls = controls if isinstance(controls, dict) else {}
    sess_controls = session.get("controls") or {}

    def exercised(word):
        hits = [e for e in control_entries if word in _blob(e)]
        hits += [r for r in requests if word in _blob(r)]
        return hits

    pause_hits = exercised("pause")
    stop_hits = exercised("stop")
    limit_hits = [e for e in rejected if "limit" in _blob(e) or "exposure" in _blob(e)]
    checks = []
    checks.append({
        "name": "Pause (blocks entries, keeps protective exits)",
        "status": "EXERCISED" if pause_hits else "UNTESTED",
        "detail": ("%d pause event(s) recorded; paused=%s" % (len(pause_hits), sess_controls.get("paused",
                   controls.get("paused")))) if pause_hits else "Pause was not used in this session.",
    })
    flat = sess_controls.get("flat_confirmed", controls.get("flat_confirmed"))
    if stop_hits:
        status = "PASS" if flat else "FAIL"
        detail = "%d stop event(s); flat_confirmed=%s (broker positions)" % (len(stop_hits), flat)
    else:
        status, detail = "UNTESTED", "Stop & Close was not used in this session."
    checks.append({"name": "Stop & Close (flat only when broker confirms)", "status": status,
                   "detail": detail})
    checks.append({
        "name": "Risk limits (per trade, daily loss, gross incl. working)",
        "status": "EXERCISED" if limit_hits else "UNTESTED",
        "detail": ("%d order(s) refused by a limit" % len(limit_hits)) if limit_hits
        else "No order reached a limit, so this session did not exercise them.",
    })
    checks.append({
        "name": "Failure handling (alarms, reconcile)",
        "status": "ALARM" if alarms else "NO ALARMS",
        "detail": ("%d blocking alarm(s) raised" % len(alarms)) if alarms
        else "No alarm was raised. Fault injection is proven in orders/ tests, not here.",
    })
    broker = session.get("broker") or {}
    checks.append({
        "name": "Broker state",
        # v2 session.json has {name, external: false} and no "connected" field.
        "status": ("OFFLINE (in-process fake)" if broker.get("external") is False
                   else "CONNECTED" if broker.get("connected") else "NOT CONNECTED"),
        "detail": (lambda n: n if "simulated" in n.lower() else n + ", simulated")(
            str(broker.get("name") or "FakeBroker (offline)")),
    })
    pos = (session.get("exposure") or {}).get("position_qty")
    if pos not in (None, 0, 0.0):
        checks.append({"name": "Residual exposure", "status": "OPEN",
                       "detail": "Position %s is still open. Not flat." % pos})
    unsimulated = [r for r in ledger if r.get("simulated") is not True]
    if unsimulated:
        checks.append({"name": "Simulated labels", "status": "FAIL",
                       "detail": "%d ledger row(s) lack simulated=true" % len(unsimulated)})
    return {"counts_by_kind": counts, "alarms": alarms[-20:], "rejected": rejected[-20:],
            "control_events": (control_entries + requests)[-30:], "checks": checks,
            "simulated": True}


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------

class DeskHandler(BaseHTTPRequestHandler):
    server_version = "PaperDeskUI/1"
    sys_version = ""
    timeout = 10  # a client that stalls mid-request cannot pin a thread

    # quiet logs; the runner owns the console
    def log_message(self, fmt, *args):  # noqa: D401
        if getattr(self.server, "verbose", False):
            sys.stderr.write("[ui] " + (fmt % args) + "\n")

    # ---- helpers ----
    @property
    def state_dir(self):
        return self.server.state_dir

    def _host_ok(self):
        host = (self.headers.get("Host") or "").strip()
        if not host:
            return True
        if host.startswith("["):
            name = host[1:].split("]")[0]
        elif host.count(":") == 1:
            name = host.split(":")[0]
        else:
            name = host
        return name.lower() in LOOPBACK_HOSTS

    def _send_report(self, full):
        with open(full, "rb") as fh:
            data = fh.read()
        is_pdf = full.endswith(".pdf")
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf" if is_pdf else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", 'inline; filename="%s"' % os.path.basename(full))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if not is_pdf:  # a report page runs no script and loads nothing from outside
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                             "img-src data:; sandbox; frame-ancestors 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            data = json.dumps(body, sort_keys=False).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # The page talks only to this server (connect-src 'self'). The one outside
        # load allowed is TradingView's official embed widget, and only after the
        # operator turns on "Show TradingView chart" (off by default). Nothing is
        # read from or injected into that frame.
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline' " + TV_SCRIPT_ORIGIN + "; "
                         "style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; "
                         "frame-src " + " ".join(TV_FRAME_ORIGINS) + "; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---- GET ----
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"ok": False, "error": "loopback host only"})
        url = urlparse(self.path)
        route = url.path.rstrip("/") or "/"
        query = parse_qs(url.query)
        try:
            if route in ("/", "/index.html"):
                with open(INDEX_PATH, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if route == "/api/health":
                attached = self.server.controller is not None
                return self._send(200, {"ok": True, "server_utc": utc_now_iso(),
                                        "state_dir": self.state_dir,
                                        "controller_attached": attached,
                                        "manager_attached": attached,
                                        "routes": self.server.available_routes(),
                                        "limits_routes": list(LIMITS_ROUTES),
                                        "lab_api": self.server.has_method("lab_view"),
                                        "lab_page": os.path.isfile(LAB_PATH),
                                        "spy_study_page": os.path.isfile(SPY_STUDY_PATH),
                                        "broker_mode": self.server.broker_mode(),
                                        "simulated": self.server.simulated()})
            if route == "/api/session":
                obj, meta = read_json(os.path.join(self.state_dir, "session.json"))
                body = dict(obj) if isinstance(obj, dict) else {}
                controls, cmeta = read_json(os.path.join(self.state_dir, "controls.json"))
                meta["missing"] = obj is None
                body["_meta"] = meta
                body["_controls_file"] = controls if isinstance(controls, dict) else None
                body["_controller_attached"] = self.server.controller is not None
                body["_manager_attached"] = body["_controller_attached"]
                # The adapter's own on/off file (alpaca/state.py), so a restart shows the
                # persisted state even before the session writes its `adapter` field.
                # Live desks keep it in alpaca_live.json, paper desks in alpaca_paper.json.
                adapter_name = self.server.adapter_file_name()
                adapter, _ = read_json(os.path.join(self.state_dir, adapter_name))
                body["_adapter_file"] = adapter if isinstance(adapter, dict) else None
                body["_adapter_file_name"] = adapter_name
                body["_broker_mode"] = self.server.broker_mode()
                body["_simulated"] = self.server.simulated()
                return self._send(200, body)
            if route == "/api/limits":
                return self._send(200, _sizing().worksheet(self.state_dir))
            if route == "/api/lab":
                return self._send(*self.server.call_read("lab_view", {}))
            if route == "/api/lab/verify":
                lab_id = (query.get("id") or [""])[0]
                if not LAB_ID_RE.fullmatch(lab_id):
                    return self._send(400, {"ok": False, "error": "id must be 1-200 letters, digits, . _ : -"})
                return self._send(*self.server.call_read("lab_verify", {"id": lab_id}, positional=True))
            if route in ("/lab", "/lab.html"):
                if not os.path.isfile(LAB_PATH):
                    return self._send(404, "The decision lab page (ui/lab.html) is not in this build yet.",
                                      "text/plain; charset=utf-8")
                with open(LAB_PATH, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if route in ("/spy-study", "/spy-study.html"):
                if not os.path.isfile(SPY_STUDY_PATH):
                    return self._send(404, "The SPY November study page (ui/spy_study.html) is not in this build yet.",
                                      "text/plain; charset=utf-8")
                with open(SPY_STUDY_PATH, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if route == "/api/bars":
                bars, manifest, meta = _bars(self.state_dir)
                sess, _ = read_json(os.path.join(self.state_dir, "session.json"))
                clock = sess.get("replay_clock_utc") if isinstance(sess, dict) else None
                total = len(bars)
                if clock:  # CONTRACT v2: only bars the replay clock has reached
                    bars = [b for b in bars if str(b.get("ts_close", "")) <= str(clock)]
                meta["replay_clock_utc"] = clock
                meta["bars_in_file"] = total
                return self._send(200, {"items": bars, "count": len(bars), "manifest": manifest,
                                        "source": meta.get("bars_source") or BARS_SOURCE_REPLAY,
                                        "_meta": meta})
            if route == "/api/decisions":
                rows, meta = read_jsonl(os.path.join(self.state_dir, "decisions.jsonl"))
                reveal = (query.get("reveal") or [None])[0]
                if reveal:
                    match = [r for r in rows if str(r.get("decision_id")) == reveal]
                    if not match:
                        return self._send(404, {"ok": False, "error": "unknown decision_id"})
                    item = _with_lines(match[-1])
                    if item.get("outcome") is None:  # join the closed round trip (mock fills)
                        fr, _ = read_json(os.path.join(self.state_dir, "review.json"))
                        trips = [t for t in _all_round_trips(fr if isinstance(fr, dict) else {})
                                 if str(t.get("entry_decision_id")) == reveal
                                 or str(t.get("exit_decision_id")) == reveal]
                        if trips:
                            item["outcome"] = outcome_from_round_trip(trips[-1])
                    return self._send(200, {"item": item, "revealed": True, "_meta": meta})
                items = [_with_lines(_strip_outcome(r)) for r in rows]
                markers = sum(1 for r in rows if r.get("action") in MARKER_ACTIONS)
                return self._send(200, {"items": items, "count": len(items), "marker_count": markers,
                                        "outcomes_hidden": True, "_meta": meta})
            if route == "/api/ledger":
                rows, meta = read_jsonl(os.path.join(self.state_dir, "ledger.jsonl"))
                return self._send(200, {"items": rows, "count": len(rows), "_meta": meta})
            if route == "/api/audit":
                rows, meta = read_jsonl(os.path.join(self.state_dir, "audit.jsonl"))
                return self._send(200, {"items": rows, "count": len(rows), "_meta": meta})
            if route == "/api/review":
                reveal_pass = (query.get("reveal_pass") or [""])[0] in ("1", "true")
                week = (query.get("week") or [None])[0]
                return self._send(200, build_review(self.state_dir, reveal_pass=reveal_pass, week=week))
            if route == "/api/reports":
                return self._send(200, {"items": list_reports(self.state_dir), "simulated": True})
            if route.startswith("/reports/"):
                full = report_path(self.state_dir, route[len("/reports/"):])
                if full is None:
                    return self._send(404, {"ok": False, "error": "no such report"})
                return self._send_report(full)
            if route == "/api/control_requests":
                rows, meta = read_jsonl(os.path.join(self.state_dir, "control_requests.jsonl"))
                return self._send(200, {"items": rows, "count": len(rows), "_meta": meta})
        except Exception as exc:  # never crash the server on a bad state file
            return self._send(500, {"ok": False, "error": "%s: %s" % (exc.__class__.__name__, exc)})
        return self._send(404, {"ok": False, "error": "no such route"})

    def do_HEAD(self):
        return self.do_GET()

    # ---- POST ----
    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"ok": False, "error": "loopback host only"})
        url = urlparse(self.path)
        route = url.path.rstrip("/")
        if route not in CONTROL_ROUTES and route not in LIMITS_ROUTES:
            return self._send(404, {"ok": False, "error": "no such route"})
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in LOOPBACK_HOSTS:
            return self._send(403, {"ok": False, "error": "cross-origin control refused"})
        # Controls must be JSON: a cross-site page cannot send application/json
        # without a CORS preflight, which this server never answers.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return self._send(415, {"ok": False, "error": "send Content-Type: application/json"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"ok": False, "error": "bad Content-Length"})
        if length < 0 or length > 65536:
            return self._send(413, {"ok": False, "error": "body too large"})
        try:
            raw = self.rfile.read(length) if length else b""
        except (socket.timeout, OSError):
            return None  # client stalled; nothing recorded
        if len(raw) < length:
            return self._send(400, {"ok": False, "error": "incomplete body; nothing recorded"})
        body = {}
        if raw:
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                return self._send(400, {"ok": False, "error": "bad JSON"})
            if not isinstance(body, dict):
                body = {}
        if route in LIMITS_ROUTES:
            return self._send(*self.server.limits_post(route, body))
        request, method_name = CONTROL_ROUTES[route][:2]
        query = parse_qs(url.query)
        confirmed = body.get("confirm") is True or (query.get("confirm") or [""])[0] in ("1", "true")
        if request in ALPACA_REQUESTS and not self.server.has_method(method_name):
            # Not queued for later: a recorded "pending enable" would imply a background job.
            if request == "alpaca_connection_check":
                msg = ("the running desk has no live connection check (connection_check); "
                       "nothing was recorded and Arm stays blocked")
            else:
                msg = ("the Alpaca paper adapter is not running in this desk "
                       "(start it with --broker alpaca-paper); nothing was recorded")
            return self._send(501, {"ok": False, "request": request, "recorded": False, "error": msg})
        if request in CONFIRM_REQUIRED and not confirmed:
            label = CONFIRM_LABELS.get(request, request)
            return self._send(400, {"ok": False, "error": "%s needs confirm=true" % label,
                                    "request": request, "action": request})
        try:
            method_name, kwargs, fallbacks = _plan_call(request, method_name, body)
        except ValueError as exc:
            return self._send(400, {"ok": False, "error": str(exc), "request": request})
        return self._send(200, self.server.record_control(request, method_name, body,
                                                          kwargs=kwargs, fallbacks=fallbacks))

    def do_PUT(self):
        return self._send(405, {"ok": False, "error": "method not allowed"})

    do_DELETE = do_PUT
    do_PATCH = do_PUT


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, state_dir, controller=None, verbose=False, manager=None):
        self.state_dir = os.path.abspath(state_dir)
        # `manager=` is the v1 name (desk/launch.py passes it); `controller=` is v2.
        self.controller = controller if controller is not None else manager
        self.verbose = verbose
        self._control_lock = threading.Lock()
        ThreadingHTTPServer.__init__(self, addr, DeskHandler)

    @property
    def manager(self):
        return self.controller

    def _append(self, row):
        os.makedirs(self.state_dir, exist_ok=True)
        path = os.path.join(self.state_dir, "control_requests.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return path

    def _session(self):
        obj, _ = read_json(os.path.join(self.state_dir, "session.json"))
        return obj if isinstance(obj, dict) else None

    # -- capability checks (the coordinator's controller may not have every method yet) --

    def has_method(self, name):
        return self.controller is not None and callable(getattr(self.controller, name, None))

    def available_routes(self):
        """Control routes the page may offer. Alpaca routes appear only when the attached
        controller really has the method, so offline desks never show an Enable button."""
        out = []
        for route, spec in CONTROL_ROUTES.items():
            if spec[0] in ALPACA_REQUESTS and not self.has_method(spec[1]):
                continue
            out.append(route)
        return sorted(out)

    def broker_mode(self):
        sess = self._session() or {}
        mode = sess.get("broker_mode")
        return mode if isinstance(mode, str) and mode else "offline-fake"

    # Modes whose orders reach a real Alpaca host: paper (simulated money) and live (REAL MONEY).
    BROKER_MODES_NOT_SIMULATED = ("alpaca-paper", "alpaca-live")

    def simulated(self):
        """False when orders go to an Alpaca host (paper or live); True for mock, rehearsal and
        unknown modes. Paper is still not real money; live is."""
        return self.broker_mode() not in self.BROKER_MODES_NOT_SIMULATED

    def adapter_file_name(self):
        """The adapter's own on/off file for this mode: alpaca_live.json on a live desk,
        alpaca_paper.json otherwise. Only these two names are ever read."""
        sess = self._session() or {}
        adapter = sess.get("adapter") if isinstance(sess.get("adapter"), dict) else {}
        if (self.broker_mode() == "alpaca-live" or adapter.get("path_name") == "alpaca_live.json"
                or adapter.get("mode") == "live"):
            return "alpaca_live.json"
        return "alpaca_paper.json"

    def call_read(self, name, kwargs, positional=False):
        """Call a read-only controller view (lab_view, lab_verify). Returns (code, body)."""
        if not self.has_method(name):
            return 501, {"ok": False, "error": "the decision lab is not available in this desk build",
                         "method": name}
        fn = getattr(self.controller, name)
        try:
            with self._control_lock:
                out = fn(*kwargs.values()) if positional else fn(**kwargs)
        except Exception as exc:
            return 500, {"ok": False, "error": "%s: %s" % (exc.__class__.__name__, str(exc)[:300])}
        return 200, _jsonable(out)

    # -- operator limits worksheet (alpaca/sizing.py); values are Matthew's, never filled here --

    def limits_post(self, route, body):
        """POST /api/limits/{draft,effects,approve}. Returns (code, body).

        Draft and approve write only <state_dir>/limits_draft.json / limits_approved.json and
        append an audit row with the action and hash, never the values."""
        sizing = _sizing()
        action = route.rsplit("/", 1)[-1]
        try:
            with self._control_lock:
                if action == "draft":
                    values = body.get("values")
                    if not isinstance(values, dict):
                        raise sizing.LimitsError("send the draft as {\"values\": {...}}")
                    copied = body.get("copied_from")
                    row = sizing.save_draft(self.state_dir, values,
                                            copied_from=copied if isinstance(copied, str) else None)
                    self._append({"ts": utc_now_iso(), "action": "limits_draft", "source": "ui",
                                  "status": "saved", "complete": row.get("complete"),
                                  "copied_from": row.get("copied_from")})
                    return 200, {"ok": True, "action": "limits_draft", "draft": row,
                                 "worksheet": sizing.worksheet(self.state_dir)}
                if action == "effects":
                    values = body.get("values")
                    if not isinstance(values, dict):
                        values = (sizing.read_draft(self.state_dir) or {}).get("values") or {}
                    kw = {}
                    for key in EFFECT_KEYS:
                        if body.get(key) not in (None, ""):
                            kw[key] = body.get(key)
                    if "ref_price" not in kw or "stop_distance" not in kw:
                        raise sizing.LimitsError("give a reference price and a stop distance")
                    return 200, {"ok": True, "action": "limits_effects",
                                 "effects": sizing.effects(values, **kw)}
                confirm = body.get("confirm")
                reason = body.get("reason")
                drafted = body.get("draft_hash")
                prior = body.get("prior_approved_hash", sizing.UNSET)
                if prior is not sizing.UNSET and prior is not None and not isinstance(prior, str):
                    prior = "invalid"   # a non-text hash can never match; approve() refuses it
                snap = sizing.approve(self.state_dir,
                                      confirm if isinstance(confirm, str) else "",
                                      reason if isinstance(reason, str) else "",
                                      reviewed_draft_hash=drafted if isinstance(drafted, str) else "",
                                      prior_approved_hash=prior)
                self._append({"ts": utc_now_iso(), "action": "limits_approve", "source": "ui",
                              "status": "approved", "hash": snap.get("hash"),
                              "previous_hash": snap.get("previous_hash"),
                              "changed_fields": [d.get("field") for d in snap.get("diff") or []
                                                 if isinstance(d, dict)]})
                return 200, {"ok": True, "action": "limits_approve", "approved": snap,
                             "note": "A running session keeps the limits it loaded at start; the "
                                     "banner's limits source says which. Restart the desk to use these.",
                             "worksheet": sizing.worksheet(self.state_dir)}
        except sizing.LimitsError as exc:
            return 400, {"ok": False, "action": "limits_" + action, "error": str(exc)}
        except (TypeError, ValueError) as exc:
            return 400, {"ok": False, "action": "limits_" + action,
                         "error": "bad limits input (%s)" % exc.__class__.__name__}

    def record_control(self, request, method_name, body, kwargs=None, fallbacks=()):
        """Append {ts, action, body} durably first (fsync), then call the
        controller method if one is attached, then record the result under the
        same request_id. Returns {ok, session, ...} (CONTRACT v2)."""
        kwargs = kwargs or {}
        with self._control_lock:
            req_id = "ui-%s-%s" % (request, uuid.uuid4().hex[:10])
            attached = self.controller is not None
            simulated = self.simulated()
            row = {"ts": utc_now_iso(), "action": request, "body": _clean_body(body),
                   "request_id": req_id, "request": request, "method": method_name,
                   "source": "ui", "status": "requested", "controller_attached": attached,
                   "simulated": simulated, "broker_mode": self.broker_mode()}
            path = self._append(row)
            result = {"ok": True, "action": request, "request": request, "request_id": req_id,
                      "written_to": path, "controller_attached": attached,
                      "controller_called": False, "simulated": simulated}
            if attached:
                target, call_kwargs = None, kwargs
                for name, kw in ((method_name, kwargs),) + tuple(fallbacks):
                    cand = getattr(self.controller, name, None)
                    if callable(cand):
                        target, method_name, call_kwargs = cand, name, kw
                        break
                if target is None:
                    result["ok"] = False
                    result["error"] = "controller has no %s()" % method_name
                    status = "controller_missing_method"
                else:
                    try:
                        out, dropped = _call_flex(target, call_kwargs)
                        result["controller_called"] = True
                        result["method"] = method_name
                        result["controller_result"] = _jsonable(out)
                        if dropped:
                            result["arguments_not_accepted"] = dropped
                        if isinstance(out, dict) and out.get("ok") is False:
                            result["ok"] = False
                            result["error"] = str(out.get("reason") or out.get("error") or out.get("detail") or "refused")
                            status = "controller_refused"
                        else:
                            status = "controller_ok"
                    except Exception as exc:
                        result["ok"] = False
                        result["controller_called"] = True
                        result["error"] = "%s: %s" % (exc.__class__.__name__, exc)
                        status = "controller_error"
                self._append({"ts": utc_now_iso(), "action": request, "request_id": req_id,
                              "request": request, "method": method_name, "source": "ui",
                              "status": status, "ok": result["ok"],
                              "controller_result": result.get("controller_result"),
                              "error": result.get("error"), "simulated": simulated})
            else:
                result["note"] = ("No controller attached; the request is recorded in "
                                  "control_requests.jsonl for the session runner to apply.")
            # v1 names, kept for desk/launch.py and older pages.
            result["manager_attached"] = attached
            result["manager_called"] = result["controller_called"]
            result["session"] = self._session()
            return result


def _jsonable(obj):
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return repr(obj)


def make_server(state_dir, host="127.0.0.1", port=8765, controller=None, verbose=False, manager=None):
    if host not in LOOPBACK_HOSTS:
        raise ValueError("the desk UI serves loopback only (127.0.0.1), not %r" % host)
    return DeskServer((host, port), state_dir, controller=controller, verbose=verbose, manager=manager)


def serve(state_dir, host="127.0.0.1", port=8765, controller=None, manager=None):
    """Blocking. CONTRACT v2 entry point; `manager=` is accepted as the v1 alias."""
    httpd = make_server(state_dir, host, port, controller=controller, manager=manager)
    sys.stderr.write("[ui] paper desk on http://%s:%d/ (state %s) SIMULATED\n"
                     % (host, httpd.server_address[1], httpd.state_dir))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Paper desk UI server (offline, simulated)")
    ap.add_argument("--state-dir", default=os.path.join(UI_DIR, "sample_state"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    serve(os.path.abspath(args.state_dir), args.host, args.port)


if __name__ == "__main__":
    main()
