#!/usr/bin/env python3
"""Paper Desk: one local page for the Nov 14 paper tools.

PAPER ONLY. It binds to 127.0.0.1 and runs the lanes' own command-line tools
with fixed argument lists. It places no bet or order, calls no model, and
reads no TradingView data. Standard library only (system python3 3.9).

    /usr/bin/python3 desk/desk_server.py --open             # Matthew's ledger
    /usr/bin/python3 desk/desk_server.py --ledger-dir DIR   # a test ledger
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # the nov14-sprint folder
LEDGER = os.path.join(ROOT, "nfl", "paper_ledger.py")
TV_ACTIONS = os.path.join(HERE, "tv_actions.json")
DESK_HTML = os.path.join(HERE, "desk.html")
PY = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable
TOKEN = secrets.token_hex(16)
MANUAL_RULE = "MANUAL-v1"                        # the id the NFL report documents
BASE_PORT = 8765

GAME_RE = re.compile(r"^\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}$")
NUM_RE = re.compile(r"^[+-]?\d{1,3}(\.\d{1,2})?$")
PRICE_RE = re.compile(r"^[+-]?\d{3,5}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SIDES = {"spread": ("home", "away"), "moneyline": ("home", "away"),
         "total": ("over", "under"), "prop": ("over", "under")}
STATIC = {".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8",
          ".txt": "text/plain; charset=utf-8", ".json": "application/json",
          ".jsonl": "text/plain; charset=utf-8", ".css": "text/css",
          ".pine": "text/plain; charset=utf-8", ".csv": "text/plain; charset=utf-8"}
OPTS = {"ledger_dir": None, "port": BASE_PORT}


def run(argv, cwd=ROOT, timeout=120):
    """Run one fixed command without a shell; return (exit code, output)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", ""), "LANG": "en_US.UTF-8"}
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + (("\n" + p.stderr) if p.stderr.strip() else "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "Stopped after %d seconds without finishing." % timeout
    except OSError as e:
        return 127, "Could not start: %s" % e


def ledger(*args):
    argv = [PY, LEDGER]                          # not -I: the ledger imports its own folder
    if OPTS["ledger_dir"]:
        argv += ["--ledger-dir", OPTS["ledger_dir"]]
    return run(argv + list(args))


def open_games(text):
    games = []
    for line in text.splitlines():
        parts = line.split()
        if parts and GAME_RE.match(parts[0]) and line.rstrip().endswith("open"):
            label = "%s  %s  kickoff %s" % (parts[2] if len(parts) > 2 else "", parts[0],
                                            parts[1].replace("T", " ") if len(parts) > 1 else "")
            games.append({"id": parts[0], "label": label.strip()})
    return games


def build_add(f):
    """Turn the form into `add` flags, or return an error string."""
    def s(k, n=300):
        v = str(f.get(k, "")).replace("\r", " ").replace("\n", " ").strip()
        return v[:n]
    game, action, market, side = s("game_id", 40), s("action", 8), s("market", 12), s("side", 8)
    line, price, qts, source = s("line", 12), s("price", 8), s("quote_ts", 25), s("source", 80)
    reason, selection, stake = s("reason"), s("selection", 80), s("stake", 6)
    if not GAME_RE.match(game):
        return "Pick a game from the slate."
    if action not in ("take", "pass"):
        return "Choose take or pass."
    if market not in SIDES or side not in SIDES[market]:
        return "Choose a market and a side that goes with it."
    if market != "moneyline" and not NUM_RE.match(line):
        return "Enter the line, for example -2.5, 47.5 or 54.5."
    if not PRICE_RE.match(price) or abs(int(price)) < 100:
        return "Enter the American price you were offered, for example -110 or +130."
    if not TS_RE.match(qts):
        return "Quote time must look like 2026-11-15T17:45:00Z."
    if not source:
        return "Say where you read the price (the sportsbook or site)."
    if not reason:
        return "Write one line on why you take or pass."
    if market == "prop" and not selection:
        return "For a prop, name the player and stat, for example 'Jane Doe receiving yards'."
    argv = ["add", "--game-id=" + game, "--rule=" + MANUAL_RULE, "--action=" + action,
            "--market=" + market, "--side=" + side, "--price=" + price,
            "--quote-ts=" + qts, "--source=" + source, "--reason=" + reason]
    if market != "moneyline":
        argv.append("--line=" + line)
    if market == "prop":
        argv.append("--selection=" + selection)
    if action == "take" and stake:
        if not NUM_RE.match(stake):
            return "Stake is a number of units, at most 1."
        argv.append("--stake=" + stake)
    return argv


def tv_actions():
    try:
        with open(TV_ACTIONS) as fh:
            acts = json.load(fh).get("actions", [])
    except (OSError, ValueError):
        return []
    return [a for a in acts if isinstance(a, dict) and a.get("name") and isinstance(a.get("argv"), list)]


REVIEW_DIR = os.path.join(ROOT, "review")
REPLAY_SUMMARY = os.path.join(ROOT, "tvbot", "out", "normal", "summary.json")
CHOICES = ("follow", "pass")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def decisions_file():
    base = OPTS["ledger_dir"] or os.path.join(HERE, "decisions")
    return os.path.join(base, "trading_decisions.jsonl")


def my_calls():
    out = {}
    try:
        with open(decisions_file(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    out.setdefault(r["packet_id"], r)
                except (ValueError, KeyError):
                    continue
    except OSError:
        pass
    return out


def trading():
    """The newest prepared packet, its stored reviews, the replay summary and my call."""
    mans = []
    for name in sorted(os.listdir(REVIEW_DIR)) if os.path.isdir(REVIEW_DIR) else []:
        m = _load(os.path.join(REVIEW_DIR, name, "inputs", "MANIFEST.json"))
        if m and m.get("packet_id") == name:
            mans.append(m)
    if not mans:
        return {"ready": False}
    man = max(mans, key=lambda m: m.get("prepared_utc", ""))
    pid = man["packet_id"]
    d = os.path.join(REVIEW_DIR, pid)
    pk = _load(os.path.join(d, "inputs", man["packet_file"])) or {}
    fz = pk.get("frozen", {})
    reviews = {}
    for r in ("claude", "astra"):
        m = _load(os.path.join(d, r + "_review.json"))
        if m:
            try:
                with open(os.path.join(d, m["answer_file"]), "rb") as fh:
                    same_answer = hashlib.sha256(fh.read()).hexdigest() == m.get("answer_sha256")
            except (OSError, KeyError):
                same_answer = False
            m["matches_inputs"] = m.get("packet_sha256") == man["packet_sha256"] and same_answer
        reviews[r] = m
    summ = _load(REPLAY_SUMMARY) or {}
    trips = summ.get("round_trips") or []
    return {"ready": True, "packet_id": pid, "prepared_utc": man.get("prepared_utc"),
            "packet_sha256": man["packet_sha256"], "symbol": fz.get("symbol"),
            "timeframe_minutes": fz.get("timeframe_minutes"), "rule": fz.get("rule", {}),
            "decision": fz.get("decision", {}), "order": fz.get("proposed_paper_order", {}),
            "portfolio": fz.get("portfolio_at_decision", {}), "plan": fz.get("forward_plan", {}),
            "close": fz.get("inputs_at_decision", {}).get("close"),
            "reviews": reviews, "my_call": my_calls().get(pid),
            "replay": {k: summ.get(k) for k in ("net_pnl", "fills", "round_trip_count", "wins", "losses",
                                                 "max_drawdown", "end_equity", "start_cash",
                                                 "open_position_qty", "data_note", "as_of")},
            "buy_and_hold": summ.get("buy_and_hold"),
            "first_trip": trips[0] if trips else None}


def record_call(body):
    t = trading()
    pid = str(body.get("packet_id", ""))
    choice = str(body.get("choice", ""))
    reason = str(body.get("reason", "")).replace("\r", " ").replace("\n", " ").strip()[:300]
    if not t.get("ready") or pid != t["packet_id"]:
        return 2, "NOT RECORDED: that is not the packet on the desk. Reload the page."
    if choice not in CHOICES:
        return 2, "NOT RECORDED: choose follow or pass."
    if not reason:
        return 2, "NOT RECORDED: write one line on why."
    if t["my_call"]:
        return 2, "NOT RECORDED: you already made a call on %s (%s at %s). It stays as it was." % (
            pid, t["my_call"]["choice"], t["my_call"]["decided_utc"])
    import datetime
    rec = {"packet_id": pid, "packet_sha256": t["packet_sha256"], "choice": choice, "reason": reason,
           "decided_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "reviews_on_screen": {r: (m or {}).get("verdict") for r, m in t["reviews"].items()},
           "paper_only": True}
    path = decisions_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return 0, "Recorded: %s on %s at %s, in %s. Paper only; no order exists." % (
        choice, pid, rec["decided_utc"], os.path.relpath(path, ROOT) if path.startswith(ROOT) else path)



# ---- Practice: one decision at a time, outcome held back until you make a call ----
TV_JOURNAL = os.path.join(ROOT, "tvbot", "out", "normal", "decisions.jsonl")
TV_BARS = os.path.join(ROOT, "tvbot", "fixtures", "normal_bars.jsonl")


def _jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def practice_file():
    return os.path.join(os.path.dirname(decisions_file()), "practice_decisions.jsonl")


def practice_items():
    """Every buy signal in the replay except the ones already shown with reviews."""
    reviewed = set()
    if os.path.isdir(REVIEW_DIR):
        for name in os.listdir(REVIEW_DIR):
            pk = _load(os.path.join(REVIEW_DIR, name, "inputs", name + ".json")) or {}
            seq = pk.get("frozen", {}).get("decision", {}).get("bar_seq")
            if isinstance(seq, int):
                reviewed.add(seq)
    return [r for r in _jsonl(TV_JOURNAL)
            if r.get("action") == "ENTER_LONG" and r.get("bar_seq") not in reviewed]


def practice_calls():
    out = {}
    for r in _jsonl(practice_file()):
        if isinstance(r, dict) and r.get("decision_id"):
            out.setdefault(r["decision_id"], r)
    return out


def practice_reveal(item, call):
    bars = {b["seq"]: b for b in _jsonl(TV_BARS) if b.get("type") == "bar" and isinstance(b.get("seq"), int)}
    summ = _load(REPLAY_SUMMARY) or {}
    s = item["bar_seq"]
    trip = next((t for t in summ.get("round_trips", []) if s < t.get("entry_fill_seq", 0) <= s + 3), None)
    last = max(bars) if bars else s
    end = trip["exit_fill_seq"] if trip else last
    pts = [[q, bars[q]["close"]] for q in range(max(1, s - 30), min(last, end + 6) + 1) if q in bars]
    mine = (trip["net_pnl"] if trip else None) if call["choice"] == "follow" else 0.0
    return {"call": call, "points": pts, "signal_seq": s, "trip": trip,
            "open_at_end": trip is None, "your_paper_result": mine}


def practice():
    items, calls = practice_items(), practice_calls()
    pending = [i for i in items if i["decision_id"] not in calls]
    done = sorted((calls[i["decision_id"]]["decided_utc"], n) for n, i in enumerate(items)
                  if i["decision_id"] in calls)
    q = None
    if pending:
        i, inp = pending[0], pending[0].get("inputs", {})
        q = {"decision_id": i["decision_id"], "number": items.index(i) + 1,
             "symbol": i.get("symbol"), "action": i["action"], "bar_seq": i["bar_seq"],
             "signal_ts": i["signal_ts"], "decision_ready_ts": i["decision_ready_ts"],
             "qty": i.get("order", {}).get("qty"), "close": inp.get("close"),
             "ema_fast": inp.get("ema_fast"), "ema_slow": inp.get("ema_slow"),
             "day_pnl": inp.get("day_pnl"), "position_qty": inp.get("position_qty"),
             "limit_daily_loss": inp.get("limit_daily_loss"), "explanation": i.get("explanation")}
    last = None
    if done:
        item = items[done[-1][1]]
        last = practice_reveal(item, calls[item["decision_id"]])
        last["number"] = done[-1][1] + 1
    return {"ready": bool(items), "total": len(items), "done": len(done), "question": q, "last": last,
            "stop_pct": (trading().get("rule", {}).get("params", {}) or {}).get("stop_pct")}


def record_practice(body):
    p = practice()
    did = str(body.get("decision_id", ""))
    choice = str(body.get("choice", ""))
    reason = str(body.get("reason", "")).replace("\r", " ").replace("\n", " ").strip()[:300]
    if not p["question"] or did != p["question"]["decision_id"]:
        return 2, "NOT RECORDED: that is not the practice decision on screen. Reload the page."
    if choice not in CHOICES:
        return 2, "NOT RECORDED: choose follow or pass."
    if not reason:
        return 2, "NOT RECORDED: write one line on why."
    import datetime
    rec = {"decision_id": did, "bar_seq": p["question"]["bar_seq"], "choice": choice, "reason": reason,
           "decided_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "shown_before_call": "decision-time facts only; chart and outcome held back",
           "paper_only": True}
    path = practice_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return 0, "Recorded: %s on practice decision %d at %s. Paper only; no order exists." % (
        choice, p["question"]["number"], rec["decided_utc"])


class Desk(BaseHTTPRequestHandler):
    server_version = "PaperDesk/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("desk %s\n" % (fmt % args))

    def _host_ok(self):
        port = OPTS["port"]
        return self.headers.get("Host", "") in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (
            json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "wrong host"})
        path = urlparse(self.path).path
        if path == "/api/ping":
            return self._send(200, {"desk": "paper", "root": os.path.realpath(ROOT),
                                    "ledger_dir": OPTS["ledger_dir"]})
        if path == "/api/trading":
            return self._send(200, trading())
        if path == "/api/practice":
            return self._send(200, practice())
        if path == "/api/slate":
            code, out = ledger("slate")
            return self._send(200, {"exit": code, "output": out, "games": open_games(out)})
        if path == "/api/status":
            code, out = ledger("status")
            return self._send(200, {"exit": code, "output": out})
        if path == "/api/tv":
            return self._send(200, {"actions": [{"name": a["name"], "label": a.get("label", a["name"]),
                                                 "note": a.get("note", "")} for a in tv_actions()]})
        if path in ("/", "/desk"):
            with open(DESK_HTML, encoding="utf-8") as fh:
                page = fh.read().replace("__DESK_TOKEN__", TOKEN)
            page = page.replace("__LEDGER_NOTE__", "Test ledger: %s" % OPTS["ledger_dir"]
                                if OPTS["ledger_dir"] else "Your paper ledger: nfl/ledger/")
            return self._send(200, page, "text/html; charset=utf-8")
        return self._static(path)

    def _static(self, path):
        rel = os.path.normpath(path.lstrip("/"))
        full = os.path.realpath(os.path.join(ROOT, rel))
        ext = os.path.splitext(full)[1].lower()
        if (not full.startswith(os.path.realpath(ROOT) + os.sep) or ext not in STATIC
                or not os.path.isfile(full)):
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        with open(full, "rb") as fh:
            return self._send(200, fh.read(), STATIC[ext])

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Desk-Token") != TOKEN:
            return self._send(403, {"error": "This page's session key does not match. Reload the desk."})
        try:
            n = min(int(self.headers.get("Content-Length", "0")), 20000)
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad request"})
        path = urlparse(self.path).path
        if path == "/api/log":
            argv = build_add(body)
            if isinstance(argv, str):
                return self._send(200, {"exit": 2, "output": "NOT SENT: " + argv})
            code, out = ledger(*argv)
            return self._send(200, {"exit": code, "output": out})
        if path == "/api/trading/decide":
            code, out = record_call(body)
            return self._send(200, {"exit": code, "output": out})
        if path == "/api/practice/decide":
            code, out = record_practice(body)
            return self._send(200, {"exit": code, "output": out})
        if path == "/api/settle":
            code, out = ledger("settle")
            return self._send(200, {"exit": code, "output": out})
        if path.startswith("/api/tv/"):
            name = path[len("/api/tv/"):]
            for a in tv_actions():
                if a["name"] == name:
                    argv = [PY if x == "{python}" else x for x in a["argv"]]
                    code, out = run(argv, cwd=os.path.join(ROOT, a.get("cwd", "tvbot")),
                                    timeout=int(a.get("timeout", 180)))
                    return self._send(200, {"exit": code, "output": out})
            return self._send(404, {"error": "no such TV action"})
        return self._send(404, {"error": "not found"})


def existing_desk(port):
    """True only if a desk on this port serves this same kit folder and the same ledger."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1) as r:
            p = json.loads(r.read().decode())
    except Exception:
        return False
    return (p.get("desk") == "paper" and p.get("root") == os.path.realpath(ROOT)
            and p.get("ledger_dir") == OPTS["ledger_dir"])


def main():
    ap = argparse.ArgumentParser(description="Paper Desk (paper only, local only)")
    ap.add_argument("--open", action="store_true", help="open the desk in the browser")
    ap.add_argument("--port", type=int, default=BASE_PORT)
    ap.add_argument("--ledger-dir", help="use a test ledger folder instead of nfl/ledger/")
    a = ap.parse_args()
    OPTS["ledger_dir"] = os.path.abspath(a.ledger_dir) if a.ledger_dir else None
    if a.open:
        for port in range(a.port, a.port + 10):
            if existing_desk(port):
                print("This Paper Desk is already running on port %d. Opening it." % port)
                webbrowser.open("http://127.0.0.1:%d/" % port)
                return
    srv = None
    for port in range(a.port, a.port + 10):
        try:
            srv = HTTPServer(("127.0.0.1", port), Desk)
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("No free local port between %d and %d." % (a.port, a.port + 9))
    OPTS["port"] = srv.server_address[1]
    url = "http://127.0.0.1:%d/" % OPTS["port"]
    print("PAPER ONLY. Paper Desk is running at %s" % url)
    print("Ledger: %s" % (OPTS["ledger_dir"] or os.path.join(ROOT, "nfl", "ledger")))
    print("Close this window, or press Control-C, to stop it.")
    sys.stdout.flush()
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
