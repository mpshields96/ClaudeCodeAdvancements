"""Decision lab recorder (desk/alpaca/CONTRACT.md section 7). SHADOW ONLY.

The lab never routes orders, never promotes a strategy and never changes size
or limits. The session calls `LabRecorder(state_dir).observe(bars, {active: d}, bar)`
after the active decision and before the broker step; this module then

  1. adds any new closed bar to the bar store   <state_dir>/lab_bars.jsonl
  2. scores earlier forecasts whose later bars now exist (lab/score.py)
  3. writes one forecast per strategy (challenger, EMA baseline, cash), all
     decided on the identical input bars, to       <state_dir>/lab_forecasts.jsonl

Every file is append-only JSON lines with a sha256 hash chain (`prev_hash`,
`row_hash`). A forecast stores the sha256 of its exact input bars and the size
of the bar store when it was written (`bars_known_count`), so a later score can
prove it used only bars that entered the store afterwards.
"""
import datetime
import hashlib
import json
import os

from strategies import base as B
from strategies import challenger as CH
from strategies.registry import STRATEGIES

FORMAT = "desk-lab/1"
BARS = "lab_bars.jsonl"
INPUTS = "lab_inputs.jsonl"
FORECASTS = "lab_forecasts.jsonl"
SCORES = "lab_scores.jsonl"
GENESIS = "GENESIS"
BASELINES = ("challenger", "ema", "cash")
# Baseline cfg, recorded on every row: the strategies' own TEST-notional sizing and
# desk default (ASSUMED) costs. The lab never reads or changes Matthew's limits.
LAB_CFG = {}
FORECAST_LABEL = "SHADOW FORECAST: decided on closed bars only; never routed, never sized, never promoted"
SCORE_LABEL = "HYPOTHETICAL shadow score; never realized P&L"


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha(obj):
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def bar_sha(bar):
    return sha(bar)


def input_sha(bars):
    return sha(list(bars))


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_rows(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def row_hash(row):
    return sha({k: v for k, v in row.items() if k != "row_hash"})


def append_chained(path, rows_cache, row):
    """Append `row` to `path` with prev_hash/row_hash; `rows_cache` is the file's rows."""
    row = dict(row)
    row["prev_hash"] = rows_cache[-1]["row_hash"] if rows_cache else GENESIS
    row["row_hash"] = row_hash(row)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canon(row) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    rows_cache.append(row)
    return row


def check_chain(rows, upto=None):
    """(ok, detail) for the hash chain of `rows` through index `upto` (all when None)."""
    prev = GENESIS
    last = len(rows) - 1 if upto is None else upto
    for i, r in enumerate(rows[:last + 1]):
        if r.get("prev_hash") != prev:
            return False, "row %d prev_hash does not match row %d" % (i, i - 1)
        if row_hash(r) != r.get("row_hash"):
            return False, "row %d content does not match its row_hash" % i
        prev = r["row_hash"]
    return True, "%d rows chained from GENESIS" % (last + 1)


def strategy_fns():
    return {"challenger": CH.decide, "ema": STRATEGIES["ema"], "cash": STRATEGIES["cash"]}


def run_decision(strategy, bars, cfg, now):
    c = dict(cfg or {})
    c["now"] = now
    return dict(strategy_fns()[strategy](list(bars), None, c))


def exposure_of(d):
    if d.get("exposure") in (1, -1, 0):
        return d["exposure"]
    a = d.get("action")
    if a == "enter_long":
        return 1
    if a == "enter_short":
        return -1
    n = d.get("net_qty_after")
    if isinstance(n, (int, float)) and not isinstance(n, bool) and a == "hold":
        return 1 if n > 0 else (-1 if n < 0 else 0)
    return 0


class Store(object):
    """All four lab files of one state_dir, read once."""

    def __init__(self, state_dir):
        self.dir = state_dir
        self.paths = {k: os.path.join(state_dir, f) for k, f in
                      (("bars", BARS), ("inputs", INPUTS), ("forecasts", FORECASTS), ("scores", SCORES))}
        self.rows = {k: read_rows(p) for k, p in self.paths.items()}
        self.bar_index = {r["bar_sha"]: i for i, r in enumerate(self.rows["bars"])}
        self.input_index = {r["input_sha256"]: r for r in self.rows["inputs"]}
        self.forecast_index = {r["forecast_id"]: r for r in self.rows["forecasts"]}
        self.scored = {r["forecast_id"]: r for r in self.rows["scores"]}

    def append(self, kind, row):
        return append_chained(self.paths[kind], self.rows[kind], row)

    def add_bar(self, bar):
        s = bar_sha(bar)
        if s not in self.bar_index:
            self.append("bars", {"format": FORMAT, "bar_sha": s, "bar": dict(bar), "ts_added": now_iso(),
                                 "synthetic": _synthetic(bar)})
            self.bar_index[s] = len(self.rows["bars"]) - 1
        return s

    def bars_by_sha(self, shas):
        out = []
        for s in shas:
            i = self.bar_index.get(s)
            out.append(None if i is None else self.rows["bars"][i]["bar"])
        return out


def _synthetic(bar):
    src = str(bar.get("source") or "")
    return "IEX" not in src.upper() or "MOCK" in src.upper() or "SYNTHETIC" in src.upper()


class LabRecorder(object):
    """Shadow recorder the session owns. observe() never raises into trading on purpose
    (the session catches anything), never mutates the decisions it is given, and
    returns the forecast rows it wrote."""

    def __init__(self, state_dir):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

    def observe(self, bars_so_far, active_decisions, bar):
        from . import score as S
        st = Store(self.state_dir)
        cut = B.parse_ts(bar["ts_close"])
        inputs = [dict(b) for b in B.knowable_bars(bars_so_far) if B.parse_ts(b["ts_close"]) <= cut]
        if not inputs or inputs[-1].get("ts_close") != bar.get("ts_close"):
            inputs.append(dict(bar))
        shas = [st.add_bar(b) for b in inputs]
        S.score_pending(self.state_dir, store=st)
        return self._record(st, inputs, shas, active_decisions or {})

    def _record(self, st, inputs, shas, active):
        isha = input_sha(inputs)
        if isha not in st.input_index:
            r = st.append("inputs", {"format": FORMAT, "input_sha256": isha, "bar_shas": shas, "n": len(shas),
                                     "synthetic": any(_synthetic(b) for b in inputs)})
            st.input_index[isha] = r
        last = inputs[-1]
        knowable = B.ts_knowable(last)
        group_id = "grp-%s" % isha[:16]
        act = [{"strategy": k, "decision_id": v.get("decision_id"), "action": v.get("action"),
                "qty": v.get("qty")} for k, v in sorted(active.items()) if isinstance(v, dict)]
        wrote = []
        for name in BASELINES:
            fid = "fc-%s-%s" % (name, isha[:16])
            if fid in st.forecast_index:
                continue
            cfg = dict(LAB_CFG)
            d = run_decision(name, inputs, cfg, knowable)
            row = {
                "format": FORMAT, "label": FORECAST_LABEL, "forecast_id": fid, "group_id": group_id,
                "strategy": name, "ts_recorded": now_iso(), "ts_recorded_source": "wall clock",
                "ts_knowable": knowable, "bar_ts_open": last.get("ts_open"), "bar_ts_close": last.get("ts_close"),
                "input_sha256": isha, "n_inputs": len(inputs), "bars_known_count": len(st.rows["bars"]),
                "synthetic_inputs": any(_synthetic(b) for b in inputs), "source": last.get("source"),
                "rule_id": d.get("rule_id"), "cfg": cfg, "now": knowable,
                "cfg_hash": d.get("cfg_hash") or B.cfg_hash(cfg), "frozen_at": d.get("frozen_at"),
                "action": d.get("action"), "qty": d.get("qty"), "exposure": exposure_of(d),
                "reason_code": d.get("reason_code"), "reason_text": d.get("reason_text"),
                "pass_condition": d.get("pass_condition"),
                "thresholds": {k: d.get(k) for k in ("trigger", "intended_entry", "intended_exit",
                                                     "invalidation", "refusal_checks", "indicators",
                                                     "cost_view", "params", "horizon_bars")
                               if d.get(k) is not None},
                "est_cost": d.get("est_cost"), "assumed_costs": B.cost_cfg(cfg),
                "decision_id": d.get("decision_id"), "decision_sha": sha(d),
                "active": act, "shadow": True, "never_routed": True,
            }
            wrote.append(st.append("forecasts", row))
            st.forecast_index[fid] = wrote[-1]
        return wrote

    def record(self, bar_window, decisions):
        """CONTRACT section 7 name: same as observe(bar_window, decisions, bar_window[-1])."""
        if not bar_window:
            return []
        return self.observe(bar_window, decisions, bar_window[-1])

    def view(self, limit=200):
        return view(self.state_dir, limit=limit)

    def verify(self, forecast_id):
        from . import verify as V
        return V.verify(self.state_dir, forecast_id)


Lab = LabRecorder  # the constructor name the session controller assumes: Lab(state_dir)


def _brief(f, s):
    out = {"forecast_id": f["forecast_id"], "action": f["action"], "qty": f["qty"],
           "exposure": f["exposure"], "reason_code": f["reason_code"], "reason_text": f["reason_text"],
           "scored": s is not None}
    if s is not None:
        for k in ("net_bps", "net_bps_2x", "gross_bps", "net_usd", "vs_ema_net_bps", "vs_cash_net_bps",
                  "hypothetical"):
            if k in s:
                out[k] = s[k]
    return out


def view(state_dir, limit=200):
    """Read-only summary for ui/lab.html: groups newest first, per-strategy totals."""
    st = Store(state_dir)
    groups, order = {}, []
    for f in st.rows["forecasts"]:
        g = groups.get(f["group_id"])
        if g is None:
            g = groups[f["group_id"]] = {"group_id": f["group_id"], "bar_ts_open": f["bar_ts_open"],
                                         "bar_ts_close": f["bar_ts_close"], "ts_knowable": f["ts_knowable"],
                                         "n_inputs": f["n_inputs"], "synthetic_inputs": f["synthetic_inputs"],
                                         "source": f.get("source"), "active": f.get("active"), "rows": {}}
            order.append(f["group_id"])
        g["rows"][f["strategy"]] = _brief(f, st.scored.get(f["forecast_id"]))
    totals = {}
    for name in BASELINES:
        sc = [s for s in st.rows["scores"] if s["strategy"] == name]
        nets = [s["net_bps"] for s in sc if s.get("net_bps") is not None]
        totals[name] = {"forecasts": sum(1 for f in st.rows["forecasts"] if f["strategy"] == name),
                        "scored": len(sc), "trades": sum(1 for s in sc if s.get("exposure")),
                        "sum_net_bps": round(sum(nets), 4),
                        "sum_net_bps_2x": round(sum(s.get("net_bps_2x") or 0.0 for s in sc), 4)}
    synthetic = any(f.get("synthetic_inputs") for f in st.rows["forecasts"])
    return {"ok": True, "label": SCORE_LABEL, "forecast_label": FORECAST_LABEL,
            "data_label": "MOCK / synthetic bars" if synthetic else "IEX-only bars (not consolidated)",
            "synthetic": synthetic,
            "frozen": {"strategy": "challenger", "rule_id": CH.RULE_ID, "frozen_at": CH.FROZEN_AT,
                       "cfg_hash": CH.CFG_HASH, "params": dict(CH.PARAMS), "cost_label": CH.COST_LABEL},
            "counts": {k: len(v) for k, v in st.rows.items()},
            "totals": totals,
            "groups": [groups[g] for g in reversed(order)][:limit]}
