"""Weekly desk report from a session state dir (SIMULATED, mock fills).

    /usr/bin/python3 -I desk/report.py --state-dir D [--week YYYY-Www]

Writes D/reports/report_<week>.html and, when headless Chrome renders it,
D/reports/report_<week>.pdf (max 3 pages; the page count is checked).

Input: D/review.json (weeks, default_week, by_week{...}), D/ledger.jsonl,
D/decisions.jsonl, and D/session.json when present. Offline and stdlib only.
Every number is simulated. Sizes and limits are TEST VALUES, never
Matthew's. Chrome runs with a throwaway --user-data-dir in a temp dir, never a
real profile. The look reuses the approved print-edition CSS (The Income Pivot).
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

MAX_PAGES = 3
MAX_TRADE_ROWS = 12
MAX_REFUSED_ROWS = 6
CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Dia.app/Contents/MacOS/Dia",
)
LOCAL_TZ = "America/Chicago"

# Palette from print-edition/build_charts.py
INK, INK2, MUTED, FAINT, RULE = "#1b222b", "#49515b", "#636a72", "#9a9fa5", "#e5e3dd"
COOL, COOL_L, WARM, WARM_L = "#0e5e8a", "#8fb5cd", "#c56c21", "#e9bd96"
SANS = "'Avenir Next', Avenir, Seravek, 'Gill Sans', sans-serif"


def e(x):
    return html.escape("" if x is None else str(x), quote=True)


def money(v, sign=True):
    if v is None:
        return "n/a"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return e(v)
    s = "%s$%s" % ("-" if v < 0 else ("+" if sign and v > 0 else ""), format(abs(v), ",.2f"))
    return s.replace("-", "−")


def px(v):
    try:
        return format(float(v), ",.4f")
    except (TypeError, ValueError):
        return "n/a"


def count(x):
    if isinstance(x, (list, tuple, dict)):
        return len(x)
    if isinstance(x, bool) or x is None:
        return 0
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def read_jsonl(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    rows.append({"_bad_line": True})
    except OSError:
        pass
    return rows


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(LOCAL_TZ)
    except Exception:  # tz data missing: fall back to UTC, labeled below
        return timezone.utc


TZ = _tz()


def iso_week(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.strptime(ts.replace("Z", "+00:00")[:25], "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    y, w, _ = dt.astimezone(TZ).isocalendar()
    return "%d-W%02d" % (y, w)


def short_ts(ts):
    if not ts:
        return ""
    return str(ts).replace("T", " ").replace("Z", "Z")[:17] + ("Z" if str(ts).endswith("Z") else "")


def metric(comp, name, default=None):
    for row in comp or []:
        if str(row.get("metric", "")).startswith(name):
            return row.get("value")
    return default


def audit(rows, check):
    for row in rows or []:
        if row.get("check", "").startswith(check):
            return row
    return {}


def pick_week(review, week):
    weeks = list(review.get("weeks") or sorted((review.get("by_week") or {}).keys()))
    if week:
        if week not in (review.get("by_week") or {}) and week != review.get("week"):
            raise SystemExit("week %s not in review.json (have: %s)" % (week, ", ".join(weeks) or "none"))
        return week, weeks
    w = review.get("default_week") or (weeks[-1] if weeks else review.get("week"))
    return w, weeks


def week_view(review, week):
    bw = (review.get("by_week") or {}).get(week)
    if bw is None and review.get("week") == week:
        bw = review
    return bw or {}


# ---------- chart (inline SVG, stdlib) ----------

def weekly_chart(review, weeks, sel):
    vals = []
    for w in weeks:
        v = metric((review.get("by_week") or {}).get(w, {}).get("comparison"), "after-cost")
        vals.append((w, float(v) if isinstance(v, (int, float)) else 0.0))
    if not vals:
        return ""
    W, H, L, R, T, B = 476, 132, 34, 6, 14, 26
    lo = min(0.0, min(v for _, v in vals))
    hi = max(0.0, max(v for _, v in vals))
    if hi - lo < 1e-9:
        hi, lo = 1.0, -1.0
    span = hi - lo
    def y(v):
        return T + (hi - v) / span * (H - T - B)
    n = len(vals)
    bw = (W - L - R) / float(n)
    p = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" role="img" '
         'aria-label="After-cost mock P&amp;L by week">' % (W, H)]
    for v in sorted(set([lo, 0.0, hi])):
        yy = y(v)
        p.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="%s"/>'
                 % (L, yy, W - R, yy, INK if v == 0 else RULE, 0.8 if v == 0 else 0.6))
        p.append('<text x="%d" y="%.1f" font-family="%s" font-size="8" fill="%s" text-anchor="end">%s</text>'
                 % (L - 4, yy + 3, SANS, MUTED, e(money(v, sign=False) if v >= 0 else money(v))))
    for i, (w, v) in enumerate(vals):
        x = L + i * bw + bw * 0.18
        top, bot = (y(v), y(0)) if v >= 0 else (y(0), y(v))
        hh = max(bot - top, 0.8 if v != 0 else 0)
        col = (WARM if v < 0 else COOL) if w == sel else (WARM_L if v < 0 else COOL_L)
        if hh:
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1.5" fill="%s"/>'
                     % (x, top, bw * 0.64, hh, col))
        if w == sel or i in (0, n - 1):
            p.append('<text x="%.1f" y="%d" font-family="%s" font-size="7.5" fill="%s" text-anchor="middle"%s>%s</text>'
                     % (x + bw * 0.32, H - 12, SANS, INK if w == sel else MUTED,
                        ' font-weight="700"' if w == sel else "", e(w)))
    p.append('<text x="%d" y="%d" font-family="%s" font-size="7.5" fill="%s">%s</text>'
             % (L, H - 2, SANS, FAINT, "Weeks with no closed mock round trip show $0. Selected week in full colour."))
    p.append("</svg>")
    return "".join(p)


# ---------- page ----------

CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                        "nov14-proposal-exchange", "print-edition", "The_Income_Pivot.html")


def approved_css():
    """The approved print-edition <style> block, with our own footer label."""
    try:
        with open(os.path.normpath(CSS_PATH), "r", encoding="utf-8") as fh:
            m = re.search(r"<style>(.*?)</style>", fh.read(), re.S)
        css = m.group(1) if m else ""
    except OSError:
        css = ""
    css = css.replace('"The Income Pivot · private"', '"SIMULATED desk report · mock fills · TEST VALUES"')
    return css + EXTRA_CSS


EXTRA_CSS = """
:root{ --paper:#fcfaf6; --ink:#1b222b; --ink2:#49515b; --muted:#636a72; --rule:#e5e3dd;
  --cool:#0e5e8a; --cool-soft:#e6eff4; --warm:#c56c21; --warm-soft:#f7ebdf;
  --serif: Charter, "Iowan Old Style", Georgia, serif; --sans: "Avenir Next", Avenir, Seravek, "Gill Sans", sans-serif; }
body{ margin:0 auto; max-width:186mm; }
@media screen{ body{ padding:10mm 12mm; } }
@page{ size:letter; margin:13mm 15mm 15mm 15mm; }
body{ font-size:9pt; line-height:1.38; }
h1{ font-size:25pt; margin-bottom:2mm; } h2{ font-size:13.5pt; margin-bottom:1.6mm; }
.deck{ font-size:10.4pt; margin-bottom:3mm; }
section{ margin-top:3.6mm; padding-top:2.4mm; }
.answer{ padding:2.4mm 3.4mm 0.6mm; margin-bottom:3.4mm; } .answer ul.tight li{ font-size:8.8pt; margin-bottom:0.8mm; }
.tiles{ margin-bottom:3mm; } table{ margin:1.4mm 0 2.4mm; font-size:7.6pt; } td{ padding:1.2mm 1.4mm; }
.callout{ padding:2.2mm 3mm 0.4mm; margin:2mm 0 2mm; }
.labels{ display:flex; flex-wrap:wrap; gap:1.4mm; margin:0 0 4mm; }
.labels span{ font:700 6.4pt/1 var(--sans); letter-spacing:.11em; text-transform:uppercase; border:0.6pt solid var(--warm);
  color:#9a4d12; border-radius:1mm; padding:1.1mm 1.6mm; background:var(--warm-soft); }
.tiles.four{ grid-template-columns:1fr 1fr 1fr 1fr; }
.tiles.four .tile .num{ font-size:15pt; }
td.r, th.r{ text-align:right; white-space:nowrap; }
td.neg{ color:#9a4d12 } td.pos{ color:var(--cool) }
table.tight td{ padding:1.1mm 1.4mm } table.tight{ font-size:7.4pt }
.chart svg{ display:block; width:100%; height:auto; }
ul.tight li{ font-size:9pt }
"""


def labels_bar(review, bw, sizing):
    out = ["SIMULATED", "mock fills", "synthetic bars", "TEST VALUES", "no real orders"]
    if (sizing or {}).get("mode") == "fixed":
        out.append("HYPOTHETICAL %s-share demo preset" % e(sizing.get("fixed_qty")))
    return '<div class="labels">%s</div>' % "".join("<span>%s</span>" % e(x) if "<" not in x else "<span>%s</span>" % x
                                                      for x in out)


def trades_table(trips):
    if not trips:
        return '<p class="small">No closed mock round trip this week.</p>'
    rows = []
    for t in trips[:MAX_TRADE_ROWS]:
        fills = t.get("fills") or []
        ent = fills[0] if fills else {}
        ext = fills[-1] if len(fills) > 1 else {}
        net = t.get("net_pnl")
        cls = "neg" if (net or 0) < 0 else "pos"
        rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td class='r'>%s</td><td class='r'>%s</td><td class='r'>%s</td>"
            "<td class='r'>%s</td><td class='r'>%s</td><td class='r %s'><b>%s</b></td></tr>"
            % (e(short_ts(t.get("entry_ts"))), e(short_ts(t.get("exit_ts"))),
               e("%s / %s" % (t.get("side", ""), t.get("exit_kind", ""))),
               e(ent.get("qty", "")), px(ent.get("price")), px(ext.get("price")),
               money(t.get("fees"), sign=False), money(t.get("gross_pnl")), cls, money(net)))
    more = ""
    if len(trips) > MAX_TRADE_ROWS:
        more = '<p class="note">%d more round trips this week are in review.json and ledger.jsonl.</p>' % (
            len(trips) - MAX_TRADE_ROWS)
    return ("<table class='tight'><tr><th>Entry (UTC)</th><th>Exit (UTC)</th><th>Side / exit</th><th class='r'>Qty</th>"
            "<th class='r'>Entry px</th><th class='r'>Exit px</th><th class='r'>Fees</th><th class='r'>Gross</th>"
            "<th class='r'>After cost</th></tr>%s</table>%s" % ("".join(rows), more))


def line_text(v):
    if isinstance(v, dict):
        if v.get("price") is not None:
            return "%s (%s)" % (v.get("text") or "", px(v.get("price")))
        return v.get("text") or ""
    return "" if v is None else str(v)


def best_pass_block(bp, pass_rule):
    if not bp or not bp.get("decision"):
        return '<p class="small">No pass decision this week.</p>'
    d = bp["decision"]
    failed = [c for c in d.get("refusal_checks") or [] if not c.get("passed")]
    rows = [
        ("Decision", "%s at %s (bar %s)" % (d.get("decision_id"), short_ts(d.get("ts_knowable") or d.get("bar_ts_close")),
                                            d.get("bar_seq"))),
        ("Reason", "%s: %s" % (d.get("reason_code"), d.get("reason_text"))),
        ("Case for", d.get("case_for")),
        ("Case against", d.get("case_against")),
        ("Would trade if", d.get("pass_condition")),
        ("Failed refusal checks", "%s%s" % (bp.get("failed_refusal_checks", len(failed)),
                                           (": " + ", ".join("%s (%s)" % (c.get("id"), c.get("detail")) for c in failed))
                                           if failed else "")),
    ]
    body = "".join("<tr><td class='opt'>%s</td><td>%s</td></tr>" % (e(k), e(v)) for k, v in rows if v not in (None, ""))
    hyp = bp.get("hypothetical_after_reveal") or {}
    hyp_html = ""
    if hyp:
        bits = ", ".join("%s %s" % (k.replace("_", " "), px(v) if isinstance(v, float) else e(v))
                         for k, v in sorted(hyp.items()) if k not in ("label", "counted_in_pnl"))
        hyp_html = ('<div class="callout"><div class="label">%s, not counted in P&amp;L</div>'
                    '<p class="small">What happened after this pass (known only afterwards): %s.</p></div>'
                    % (e(hyp.get("label", "HYPOTHETICAL")), bits))
    return ("<p class='note'>%s</p><table>%s</table>%s" % (e(pass_rule), body, hyp_html))


def comparison_table(bw, allw):
    cw = bw.get("comparison") or []
    ca = (allw or {}).get("comparison") or []
    names = [r.get("metric") for r in cw] or [r.get("metric") for r in ca]
    rows = []
    for nm in names:
        a = metric(cw, nm)
        b = metric(ca, nm) if ca else None
        money_row = any(k in str(nm) for k in ("P&L", "fees", "cash"))
        fa = money(a) if money_row else e(a)
        fb = (money(b) if money_row else e(b)) if ca else "n/a"
        rows.append("<tr><td>%s</td><td class='r'>%s</td><td class='r'>%s</td></tr>" % (e(nm), fa, fb))
    return ("<table class='tight'><tr><th>Metric (simulated)</th><th class='r'>This week</th>"
            "<th class='r'>All weeks</th></tr>%s</table>" % "".join(rows))


def audit_table(bw, ledger_week, dec_week):
    oa = bw.get("operating_audit") or []
    fi = audit(oa, "fills vs intents")
    rj = audit(oa, "rejections by reason").get("counts") or {}
    rf = audit(oa, "refused decisions")
    al = audit(oa, "alarms").get("alarms") or []
    an = audit(oa, "anomalies").get("rows") or []
    xr = audit(oa, "entries refused at the execution price")
    xrows = xr.get("rows") or []
    xtxt = "%s" % xr.get("count", 0) if xr else "n/a (not in review.json)"
    if xrows:
        xtxt += ": " + "; ".join("%s %s %s at simulated %s = %s over cap %s" % (
            short_ts(r.get("bar_ts_close")), r.get("side", ""), r.get("qty", ""), px(r.get("exec_price")),
            money(r.get("notional"), sign=False), money(r.get("per_trade_cap"), sign=False)) for r in xrows[:3])
    rows = [
        ("Order intents / filled / rejected", "%s / %s / %s" % (fi.get("intents", "n/a"), fi.get("filled", "n/a"),
                                                                fi.get("rejected", "n/a"))),
        ("Rejections by reason", ", ".join("%s %s" % (k, v) for k, v in sorted(rj.items())) or "none"),
        ("Refused by risk check (never sent, never filled)", rf.get("count", 0)),
        ("Entries refused at the execution price (exec_refusals; nothing filled)", xtxt),
        ("Alarms (whole run)", "; ".join(("%s: %s" % (a.get("code") or a.get("kind") or "alarm",
                                                       a.get("detail") or a.get("text") or ""))
                                         if isinstance(a, dict) else str(a) for a in al[:5]) or "none"),
        ("Anomalies", "; ".join(str(a) for a in an[:4]) or "none"),
        ("Ledger rows this week (by status)", ", ".join("%s %s" % (k, v) for k, v in sorted(ledger_week.items())) or "none"),
        ("Decisions this week (by action)", ", ".join("%s %s" % (k, v) for k, v in sorted(dec_week.items())) or "none"),
    ]
    return "<table class='tight'>%s</table>" % "".join(
        "<tr><td class='opt'>%s</td><td>%s</td></tr>" % (e(k), e(v)) for k, v in rows)


def refused_table(refused):
    if not refused:
        return ""
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(short_ts(r.get("bar_ts_close"))), e(r.get("action")), e(r.get("why")), e(r.get("detail")))
        for r in refused[:MAX_REFUSED_ROWS])
    more = ""
    if len(refused) > MAX_REFUSED_ROWS:
        more = '<p class="note">%d more are in review.json.</p>' % (len(refused) - MAX_REFUSED_ROWS)
    return ("<h3>Refused by risk check: not sent, not filled</h3><table class='tight'><tr><th>Bar close</th>"
            "<th>Wanted</th><th>Why</th><th>Detail</th></tr>%s</table>%s" % (rows, more))


def cost_model(session, bw):
    fc = (session or {}).get("fill_costs") or {}
    parts = []
    if fc:
        parts.append("commission $%s a share, minimum $%s an order; half-spread %s bps; slippage %s bps (%s)" % (
            fc.get("commission_per_share"), fc.get("commission_min"), fc.get("half_spread_bps"),
            fc.get("slippage_bps"), fc.get("kind", "model")))
    bp = ((bw.get("best_pass") or {}).get("decision") or {}).get("est_cost") or {}
    if bp.get("basis") and bp.get("basis") != "no order":
        parts.append("strategy estimate basis: %s" % bp["basis"])
    return "; ".join(parts) or "fees as recorded on each mock fill in ledger.jsonl"


def build_html(state_dir, week=None):
    review = read_json(os.path.join(state_dir, "review.json"))
    if not isinstance(review, dict):
        raise SystemExit("no readable review.json in %s (run the session review first)" % state_dir)
    session = read_json(os.path.join(state_dir, "session.json"), {}) or {}
    week, weeks = pick_week(review, week)
    bw = week_view(review, week)
    allw = review.get("all_weeks_summary") or {}
    sizing = bw.get("sizing") or review.get("sizing") or session.get("sizing") or {}
    limits = session.get("limits") or {}

    ledger = read_jsonl(os.path.join(state_dir, "ledger.jsonl"))
    ledger_week = {}
    for row in ledger:
        if iso_week(row.get("signal_ts") or row.get("ts")) == week:
            k = "%s %s" % (row.get("kind", "?"), row.get("status", "?"))
            ledger_week[k] = ledger_week.get(k, 0) + 1
    decs = bw.get("decisions") if isinstance(bw.get("decisions"), list) else None
    if decs is None:
        decs = [d for d in read_jsonl(os.path.join(state_dir, "decisions.jsonl"))
                if iso_week(d.get("bar_ts_close") or d.get("ts_knowable")) == week]
    dec_week = {}
    for d in decs:
        a = d.get("action", "?")
        dec_week[a] = dec_week.get(a, 0) + 1

    comp = bw.get("comparison") or []
    net = metric(comp, "after-cost")
    gross = metric(comp, "gross")
    fees = metric(comp, "fees")
    trips = bw.get("round_trips") or []
    n_dec = metric(comp, "decisions", count(bw.get("decisions")) or len(decs))
    n_pass = metric(comp, "passes", count(bw.get("passes")) or dec_week.get("pass", 0))
    fi = audit(bw.get("operating_audit"), "fills vs intents")
    alarms = audit(bw.get("operating_audit"), "alarms").get("alarms") or []
    bt, wt = bw.get("best_trade"), bw.get("worst_trade")
    bp = bw.get("best_pass") or {}
    bpd = bp.get("decision") or {}

    tldr = [
        "After-cost mock P&amp;L this week: <b>%s</b> (gross %s, fees %s). Cash baseline: <b>$0.00</b>." % (
            money(net), money(gross), money(fees, sign=False)),
        "%d closed mock round trip%s from %s decisions, %s of them passes." % (
            len(trips), "" if len(trips) == 1 else "s", e(n_dec), e(n_pass)),
    ]
    if bt and len(trips) > 1:
        tldr.append("Best trip %s, worst %s." % (money(bt.get("net_pnl")), money((wt or {}).get("net_pnl"))))
    if bw.get("no_trade_filled"):
        tldr.append("No trade filled this week. %s" % e(bw.get("no_trade_note") or ""))
    if bpd:
        tldr.append("Pre-ranked best pass: %s (%s), chosen from facts known at the time." % (
            e(bpd.get("reason_code")), e(short_ts(bpd.get("ts_knowable")))))
    tldr.append("Operations: %s intents, %s filled, %s rejected; %d alarm%s in the run." % (
        e(fi.get("intents", "n/a")), e(fi.get("filled", "n/a")), e(fi.get("rejected", "n/a")),
        len(alarms), "" if len(alarms) == 1 else "s"))
    all_net = metric(allw.get("comparison"), "after-cost")
    if all_net is not None:
        tldr.append("All %d weeks: %s after costs over %s round trips, against $0 for cash." % (
            len(weeks), money(all_net), e(metric(allw.get("comparison"), "round trips", count(allw.get("round_trips"))))))

    tiles = "".join('<div class="tile"><div class="num %s">%s</div><div class="cap">%s</div></div>' % (c, v, cap) for v, c, cap in (
        (money(net), "warm" if (net or 0) < 0 else "cool", "after-cost mock P&amp;L, this week"),
        (money(gross), "", "gross, before costs"),
        (money(fees, sign=False), "", "fees on mock fills"),
        (str(len(trips)), "", "closed round trips"),
    ))

    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    tz_note = LOCAL_TZ if TZ is not timezone.utc else "UTC (time-zone data unavailable)"
    lim_txt = ", ".join("%s %s" % (k.replace("_", " "), v) for k, v in sorted(limits.items())
                        if isinstance(v, (int, float)) and not isinstance(v, bool))

    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Desk report %s</title><style>%s</style></head><body>" % (e(week), approved_css()),
        "<section class='first'>",
        "<div class='kicker'>Paper desk &middot; %s &middot; %s</div>" % (e(week), e(review.get("strategy") or bw.get("strategy"))),
        "<h1>Weekly desk report</h1>",
        "<p class='deck'>%s. %s.</p>" % (e(bw.get("label") or review.get("label") or "SIMULATED REPLAY REVIEW"),
                                         e(bw.get("scope") or week)),
        labels_bar(review, bw, sizing),
        "<div class='answer'><div class='label'>TL;DR</div><ul class='tight'>%s</ul></div>" % "".join(
            "<li>%s</li>" % x for x in tldr),
        "<div class='tiles four'>%s</div>" % tiles,
        "<figure class='chart'>%s<figcaption><b>After-cost mock P&amp;L by week.</b> SIMULATED replay on synthetic "
        "bars with mock fills; not a market result.</figcaption></figure>" % weekly_chart(review, weeks, week),
        "</section>",
        "<section><div class='kicker'>The week's mock trades</div><h2>Round trips, after costs</h2>",
        trades_table(trips),
        "<p class='note'>Sessions: %s. Times are UTC; weeks follow local sessions (%s).</p>" % (
            e(", ".join(bw.get("sessions") or []) or "none"), e(tz_note)),
        refused_table(bw.get("refused_decisions") or []),
        "</section>",
        "<section><div class='kicker'>Pre-ranked best pass</div><h2>The pass with the strongest recorded reasons</h2>",
        best_pass_block(bp, bw.get("pass_rule") or review.get("pass_rule")),
        "</section>",
        "<section><div class='kicker'>Comparison</div><h2>Against doing nothing</h2>",
        comparison_table(bw, allw),
        "</section>",
        "<section><div class='kicker'>Operating audit</div><h2>What the desk did</h2>",
        audit_table(bw, ledger_week, dec_week),
        "</section>",
        "<section><div class='kicker'>Labels and method</div>",
        "<ul class='tight small'>",
        "<li><b>Cost model (simulated):</b> %s.</li>" % e(cost_model(session, bw)),
        "<li><b>Sizing:</b> %s. %s</li>" % (e(sizing.get("label") or "TEST VALUES sizing"), e(sizing.get("note") or "")),
        "<li><b>Limits:</b> %s%s.</li>" % (e(limits.get("label") or "TEST VALUES"), (" (" + e(lim_txt) + ")") if lim_txt else ""),
        "<li><b>Data:</b> %s. Fills are mock fills from the offline fake broker; no account, network or real order.</li>"
        % e(session.get("data_label") or "SYNTHETIC FIXTURE BARS"),
        "<li><b>Not a recommendation.</b> Every number here is SIMULATED and says nothing about a real market.</li>",
        "</ul><p class='note'>Built %s from review.json, ledger.jsonl and decisions.jsonl by desk/report.py.</p>" % e(gen),
        "</section></body></html>",
    ]
    return week, "".join(parts)


def page_count(pdf_path):
    with open(pdf_path, "rb") as fh:
        data = fh.read()
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def render_pdf(html_path, pdf_path, timeout=90):
    if os.path.exists(pdf_path):
        os.remove(pdf_path)                                   # never leave a stale PDF behind
    exe = next((c for c in CHROME if os.path.exists(c)), None)
    if not exe:
        return None, "no headless Chrome/Dia found"
    prof = tempfile.mkdtemp(prefix="desk-report-chrome-")   # throwaway profile, never a real one
    try:
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               "--no-default-browser-check", "--disable-extensions", "--disable-sync",
               "--user-data-dir=" + prof, "--print-to-pdf=" + pdf_path, "file://" + html_path]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, "render failed: %s" % exc
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            return None, "render produced no PDF"
        return page_count(pdf_path), None
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def build_report(state_dir, week=None, render=True):
    """Write reports/report_<week>.html (+ .pdf). Returns the PDF path, else the HTML path."""
    build_report.last_pages = None
    state_dir = os.path.abspath(state_dir)
    week, page = build_html(state_dir, week)
    out = os.path.join(state_dir, "reports")
    os.makedirs(out, exist_ok=True)
    base = os.path.join(out, "report_%s" % re.sub(r"[^0-9A-Za-z_-]", "_", week or "all"))
    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    if not render:
        return html_path
    pdf_path = base + ".pdf"
    pages, err = render_pdf(html_path, pdf_path)
    if pages is None:
        sys.stderr.write("report: no PDF written (%s). HTML-only report at %s; open it in a browser and "
                         "print to PDF (US Letter) if a PDF is needed.\n" % (err, html_path))
        return html_path
    if pages > MAX_PAGES:
        sys.stderr.write("report: WARNING %d pages > %d max (%s)\n" % (pages, MAX_PAGES, pdf_path))
    build_report.last_pages = pages
    return pdf_path


build_report.last_pages = None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Weekly SIMULATED desk report (mock fills, TEST VALUES).")
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--week", default=None, help="ISO week YYYY-Www (default: latest week)")
    ap.add_argument("--html-only", action="store_true")
    a = ap.parse_args(argv)
    if a.week and not re.match(r"^\d{4}-W\d{2}$", a.week):
        ap.error("--week must look like 2026-W40")
    path = build_report(a.state_dir, a.week, render=not a.html_only)
    pages = build_report.last_pages
    print("%s%s" % (path, "" if pages is None else "  (%d page%s)" % (pages, "" if pages == 1 else "s")))
    return 0 if (pages is None or pages <= MAX_PAGES) else 2


if __name__ == "__main__":
    sys.exit(main())
