#!/usr/bin/env python3
"""Static result page for the paper-only trading-rule test runner.

Reads saved files only (summary, ledger, gate decision, source report) and
writes one HTML file. No network, no accounts, no orders, no JavaScript.
Standard library only, Python 3.9.

    /usr/bin/python3 -I nov14-sprint/tvbot/bot/page.py [--test-state DIR]
        [--paper-state DIR] [--gate FILE] [--source-report FILE]
        [--out FILE] [--now YYYY-MM-DDTHH:MM:SSZ]
"""
import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
TVBOT_DIR = os.path.dirname(BOT_DIR)
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

import riskinfo  # noqa: E402
import rules  # noqa: E402

TITLE = "TV paper bot: what it did"
TEST_LABEL = "TEST ONLY: synthetic"
REAL_LABEL = "REAL BARS, PAPER ONLY"
SOURCE_SCHEMA = "tvbot-real-source-report-1"
GATE_COMMAND = "/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py gate"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

ACTION_ORDER = ["ENTER_LONG", "EXIT_LONG", "HOLD", "STAND_ASIDE", "BLOCKED"]
ACTION_GLOSS = {
    "ENTER_LONG": "Decided to buy.",
    "EXIT_LONG": "Decided to sell.",
    "HOLD": "Kept the position, or waited on an order.",
    "STAND_ASIDE": "No trade.",
    "BLOCKED": "A buy the risk limits refused.",
}
REASON_GLOSS = {
    "stop": "a bar closed at or below the stop level",
    "cross_down": "the fast average crossed back below the slow one",
    "daily_loss_limit": "the daily loss limit was hit",
}

CSS = """
:root{
  --paper:#fcfaf6; --ink:#1b222b; --ink2:#49515b; --muted:#636a72; --rule:#e5e3dd;
  --cool:#0e5e8a; --cool-soft:#e6eff4; --warm:#c56c21; --warm-soft:#f7ebdf; --good:#1d6b3a;
  --serif: Charter, "Iowan Old Style", Georgia, serif;
  --sans: "Avenir Next", Avenir, Seravek, "Gill Sans", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
*{ box-sizing:border-box }
html,body{ background:var(--paper); }
body{ margin:0; color:var(--ink); font:17px/1.5 var(--serif); font-variant-numeric:lining-nums tabular-nums; overflow-wrap:break-word; }
main{ max-width:760px; margin:0 auto; padding:40px 16px 64px; }
section{ margin-top:30px; padding-top:20px; border-top:1px solid var(--rule); }
section.first{ margin-top:0; padding-top:0; border-top:0 }
.kicker{ font:600 12px/1.2 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:var(--cool); margin:0 0 12px; }
h1{ font:700 42px/1.04 var(--serif); letter-spacing:-.015em; margin:0 0 12px; }
h2{ font:700 25px/1.15 var(--serif); margin:0 0 10px; }
h3{ font:700 19px/1.2 var(--serif); margin:18px 0 8px; }
p{ margin:0 0 10px; }
.deck{ font:400 19px/1.4 var(--serif); color:var(--ink2); margin:0 0 14px; }
.note{ font:400 13px/1.45 var(--sans); color:var(--muted); }
code{ font:500 13px/1.4 var(--mono); background:var(--cool-soft); padding:1px 5px; border-radius:4px; overflow-wrap:anywhere; }
pre{ font:500 13.5px/1.45 var(--mono); background:var(--cool-soft); border-left:4px solid var(--cool); border-radius:0 8px 8px 0; padding:12px 16px; margin:0 0 12px; overflow-x:auto; max-width:100%; }
.good{ color:var(--good) } .bad{ color:var(--warm) } .cool{ color:var(--cool) }
.caveat{ border-left:6px solid var(--warm); background:var(--warm-soft); border-radius:0 8px 8px 0; padding:16px 18px 8px; margin:18px 0 0; }
.caveat .label{ font:700 11.5px/1 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:#9a4d12; margin-bottom:10px; }
.caveat .big{ font:700 22px/1.25 var(--serif); margin:0 0 10px; }
.verdict{ border-left:4px solid var(--cool); background:var(--cool-soft); padding:12px 16px; border-radius:0 8px 8px 0; margin:0 0 12px; }
.verdict.bad{ border-color:var(--warm); background:var(--warm-soft); color:var(--ink) }
.verdict.ok{ border-color:var(--good); background:#e8f2ea; color:var(--ink) }
.pill{ display:inline-block; font:700 14px/1.2 var(--sans); padding:5px 10px; border-radius:999px; background:var(--cool-soft); color:var(--cool); margin:0 0 10px; }
.pill.ok{ background:#e8f2ea; color:var(--good) } .pill.warn{ background:var(--warm-soft); color:#9a4d12 }
.badge{ display:inline-block; font:700 11.5px/1 var(--sans); letter-spacing:.12em; text-transform:uppercase; padding:5px 9px; border-radius:4px; margin:0 8px 8px 0; }
.badge.test{ background:var(--warm-soft); color:#9a4d12; border:1px solid #e3c4a3 }
.badge.real{ background:var(--cool-soft); color:var(--cool); border:1px solid #a9c6d8 }
.tiles{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:6px 0 14px; }
.tile{ border-top:2.5px solid var(--ink); padding:9px 0 0; }
.tile .num{ font:700 28px/1 var(--serif); }
.tile .cap{ font:400 12.5px/1.4 var(--sans); color:var(--ink2); margin-top:6px; }
.scroll{ overflow-x:auto; max-width:100%; margin:8px 0 12px; }
table{ width:100%; border-collapse:collapse; font:400 14px/1.4 var(--sans); margin:0; }
caption{ text-align:left; font:700 11px/1.3 var(--sans); letter-spacing:.1em; text-transform:uppercase; color:var(--muted); padding:0 0 6px; }
th{ text-align:right; font:700 11px/1.2 var(--sans); letter-spacing:.1em; text-transform:uppercase; color:var(--muted); padding:6px 7px; border-bottom:1.5px solid var(--ink); vertical-align:bottom; }
th:first-child,td:first-child{ text-align:left }
td{ padding:6px 7px; border-bottom:1px solid var(--rule); text-align:right; vertical-align:top; }
th.l,td.l{ text-align:left }
td.l{ overflow-wrap:anywhere }
td .gloss{ display:block; font:400 12.5px/1.4 var(--sans); color:var(--muted); margin-top:2px; }
tr.strong td{ font-weight:700; background:var(--cool-soft) }
table.wide{ min-width:480px }
.meter-row{ display:flex; align-items:center; gap:12px; margin:4px 0 12px; }
.meter{ flex:1 1 auto; height:14px; background:#ebe8e0; border-radius:7px; overflow:hidden; min-width:120px; }
.meter-fill{ height:100%; background:var(--warm); }
.meter-num{ font:700 16px/1.2 var(--sans); white-space:nowrap; }
ul{ margin:0 0 10px; padding-left:20px } li{ margin:0 0 5px }
@media (max-width:640px){
  main{ padding-top:28px }
  h1{ font-size:34px }
  .tiles{ grid-template-columns:1fr 1fr }
  table{ font-size:13px }
  .caveat .big{ font-size:20px }
}
"""


# ---------------------------------------------------------------- helpers

def esc(v):
    """Escape any value that came from a file or the command line."""
    if v is None:
        return "n/a"
    return html.escape(str(v), quote=True)


def num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def money(v):
    """Signed money to 2 decimals, for gains and losses."""
    f = num(v)
    if f is None:
        return "n/a"
    f = round(f, 2) + 0.0
    return "{:+,.2f}".format(f)


def plain_money(v):
    f = num(v)
    if f is None:
        return "n/a"
    return "{:,.2f}".format(f)


def whole(v):
    f = num(v)
    if f is None:
        return "n/a"
    return "{:,d}".format(int(round(f)))


def tone(v):
    f = num(v)
    if f is None or round(f, 2) == 0:
        return ""
    return "good" if f > 0 else "bad"


def load_json(path):
    """A JSON object from a file, or None if missing, unreadable or not an object."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def first_ledger_rule_id(state_dir):
    path = os.path.join(state_dir, "ledger.jsonl")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            line = fh.readline(1 << 20)
        row = json.loads(line)
    except (OSError, ValueError, UnicodeError):
        return None
    if isinstance(row, dict) and row.get("rule_id"):
        return row["rule_id"]
    return None


def run_identity(summary, state_dir):
    """(rule_id, config_hash) of a saved run."""
    rid = first_ledger_rule_id(state_dir) or summary.get("rule_id")
    return rid, summary.get("config_hash")


def section(kicker, title, body, first=False):
    return ('<section%s>\n<div class="kicker">%s</div>\n<h2>%s</h2>\n%s\n</section>\n'
            % (' class="first"' if first else "", esc(kicker), title, body))


def scroll(table_html):
    return '<div class="scroll">%s</div>' % table_html


def tile(number, caption, cls=""):
    return ('<div class="tile"><div class="num %s">%s</div><div class="cap">%s</div></div>'
            % (cls, number, caption))


# ------------------------------------------------------------------ cost sweep

SWEEP_CAPTION = "Same trades, every cost multiplied"


def sweep_rows(sweep):
    """The saved cost sweep as [(multiplier, net)], or [] if any part of it is not a number."""
    if not isinstance(sweep, list) or not sweep:
        return []
    rows = []
    for item in sweep:
        if not isinstance(item, dict):
            return []
        mult, net = num(item.get("mult")), num(item.get("net"))
        if mult is None or net is None or mult < 0:
            return []
        rows.append((mult, net))
    return rows


def times(mult):
    return "%d" % mult if mult == int(mult) else "%g" % mult


def cost_sweep_html(sweep, label):
    """What the same trades would have made if every cost were 2, 4 or 8 times the settings."""
    rows = sweep_rows(sweep)
    if not rows:
        return ""

    def name(mult):
        if mult == 0:
            return "No costs at all"
        if mult == 1:
            return "Costs as in the settings (the net result above)"
        return "Costs %s times the settings" % times(mult)

    body = "".join('<tr%s><td class="l">%s</td><td class="%s">%s</td></tr>'
                   % (' class="strong"' if mult == 1 else "", esc(name(mult)), tone(net), money(net))
                   for mult, net in rows)
    top_mult, top_net = max(rows)
    if round(top_net, 2) < 0:
        verdict = ("At %s times the costs in the settings, the same trades end at a loss of %s."
                   % (times(top_mult), plain_money(abs(top_net))))
    else:
        verdict = ("The same trades are still a gain at %s times the costs in the settings (%s)."
                   % (times(top_mult), money(top_net)))
    return (scroll('<table><caption>%s (%s)</caption><thead><tr><th class="l">If costs were</th>'
                   '<th>Net result</th></tr></thead><tbody>%s</tbody></table>'
                   % (SWEEP_CAPTION, label, body))
            + '\n<p class="note">%s The costs are set in the settings, not measured from a market. '
              'Real costs can be higher than the settings.</p>' % esc(verdict))


# ------------------------------------------------------- result block (3 and 6)

def result_block(summary, rule_id, label, kind):
    """The saved-run result, used for the test run and for a real-bar paper run.

    label is "TEST ONLY: synthetic" or "REAL BARS, PAPER ONLY"; kind is "test" or "real".
    """
    s = summary
    L = esc(label)
    out = []
    out.append('<p><span class="badge %s">%s</span> <span class="note">symbol %s, feed file %s</span></p>'
               % (kind, L, esc(s.get("symbol")), esc(s.get("feed"))))

    net = num(s.get("net_pnl"))
    gross = num(s.get("gross_pnl_at_raw_opens"))
    comm = num(s.get("commission_cost"))
    spread = None
    if net is not None and gross is not None and comm is not None:
        spread = net - gross + comm
    dd = num(s.get("max_drawdown"))
    bh = s.get("buy_and_hold") if isinstance(s.get("buy_and_hold"), dict) else {}
    bh_net = bh.get("net_pnl")

    out.append('<div class="tiles">%s%s%s</div>' % (
        tile(money(net), "net result after all costs (%s)" % L, tone(net)),
        tile(money(bh_net), "buy-and-hold comparison (%s)" % L, tone(bh_net)),
        tile(money(-abs(dd)) if dd is not None else "n/a",
             "largest drop from a peak (%s)" % L, "bad" if dd else "")))

    def row(label_, gloss, value, cls="", strong=False):
        return ('<tr%s><td>%s<span class="gloss">%s</span></td><td class="%s">%s</td></tr>'
                % (' class="strong"' if strong else "", label_, gloss, cls, value))

    rows = []
    rows.append(row("Bars read", "A bar is one block of price history: open, high, low and close.",
                    whole(s.get("bars_accepted"))))
    rows.append(row("Decisions", "The bot picks one action for each bar. The next table breaks them down.",
                    whole(s.get("decisions"))))
    rows.append(row("Orders", "Orders the bot would have sent. Paper only.", whole(s.get("orders"))))
    rows.append(row("Fills", "Orders that would have been filled.", whole(s.get("fills"))))
    rows.append(row("Round trips", "One round trip is one buy followed by one sell.",
                    whole(s.get("round_trip_count"))))
    rows.append(row("Result before costs",
                    "Gain or loss with every trade at the raw open price, before any cost.",
                    money(gross), tone(gross)))
    rows.append(row("Spread and slippage cost",
                    "Spread is the gap between the buy and sell price. Slippage is a slightly worse "
                    "price than expected. Both come from the settings; they are not measured.",
                    money(spread), tone(spread)))
    rows.append(row("Commission", "Broker fees, charged per order.",
                    money(-comm) if comm is not None else "n/a", "bad" if comm else ""))
    rows.append(row("Net result", "The result before costs, minus all costs.",
                    money(net), tone(net), strong=True))
    rows.append(row("Largest drop from a peak",
                    "The biggest fall in account value from its highest point so far.",
                    money(-abs(dd)) if dd is not None else "n/a", "bad" if dd else ""))
    rows.append(row("Buy-and-hold comparison", esc(bh.get("note")) if bh.get("note") else
                    "Buy once at the start and never sell.", money(bh_net), tone(bh_net)))
    qty = num(s.get("open_position_qty"))
    if qty and qty > 0:
        open_gloss = ("Shares still held at the end, not yet sold. Their gain or loss so far is "
                      "already inside the net result.")
        open_val = "%s shares" % whole(qty)
    else:
        open_gloss = "Shares still held at the end, not yet sold."
        open_val = "None"
    rows.append(row("Position still open", open_gloss, open_val))
    out.append(scroll('<table><caption>Counts and money, in dollars (%s)</caption><tbody>%s</tbody></table>'
                      % (L, "".join(rows))))

    # decisions by action
    by = s.get("decisions_by_action") if isinstance(s.get("decisions_by_action"), dict) else {}
    keys = [k for k in ACTION_ORDER if k in by] + sorted(k for k in by if k not in ACTION_ORDER)
    if keys:
        body = "".join('<tr><td class="l">%s</td><td>%s</td><td class="l">%s</td></tr>'
                       % (esc(k), whole(by[k]), esc(ACTION_GLOSS.get(k, "")))
                       for k in keys)
        out.append(scroll('<table><caption>Decisions by action (%s)</caption><thead><tr><th class="l">Action</th>'
                          '<th>Count</th><th class="l">What it means</th></tr></thead><tbody>%s</tbody></table>'
                          % (L, body)))

    # round trips
    trips = s.get("round_trips") if isinstance(s.get("round_trips"), list) else []
    trips = [t for t in trips if isinstance(t, dict)]
    if trips:
        body = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>'
                       % (esc(t.get("entry_fill_ts")), esc(t.get("exit_fill_ts")), esc(t.get("exit_reason")),
                          tone(t.get("net_pnl")), money(t.get("net_pnl")))
                       for t in trips)
        out.append(scroll('<table class="wide"><caption>Round trips (%s)</caption><thead><tr>'
                          '<th>Entry time (UTC)</th><th>Exit time (UTC)</th><th>Exit reason</th>'
                          '<th>Net result</th></tr></thead><tbody>%s</tbody></table>' % (L, body)))
        reasons = []
        for t in trips:
            r = t.get("exit_reason")
            if r in REASON_GLOSS and r not in reasons:
                reasons.append(r)
        if reasons:
            out.append('<p class="note">Exit reasons: %s.</p>'
                       % "; ".join("%s = %s" % (esc(r), esc(REASON_GLOSS[r])) for r in reasons))
        closed = sum(t["net_pnl"] for t in trips if num(t.get("net_pnl")) is not None)
        line = "The closed trades above add up to %s." % money(closed)
        if net is not None and qty and qty > 0 and abs(net - closed) >= 0.005:
            line += (" The rest of the net result, %s, comes from the position still open at the end."
                     % money(net - closed))
        out.append('<p class="note">%s</p>' % esc(line))
    else:
        out.append('<p>No trade was closed in this run (%s).</p>' % L)

    out.append(cost_sweep_html(s.get("cost_sweep"), L))

    if s.get("fill_assumption"):
        out.append('<p><strong>Fill rule.</strong> %s</p>' % esc(s.get("fill_assumption")))
    out.append('<p class="note">Rule id: <code>%s</code> Config hash: <code>%s</code></p>'
               % (esc(rule_id), esc(s.get("config_hash"))))
    if s.get("data_note"):
        out.append('<p class="note">Data note: %s</p>' % esc(s.get("data_note")))
    return "\n".join(out)


# ------------------------------------------------------------------ sections

def header_html(now_utc):
    return ('<section class="first">\n'
            '<div class="kicker">Paper only · test runner · no orders</div>\n'
            '<h1>%s</h1>\n'
            '<p class="deck">Paper only. Nothing on this page can place an order.</p>\n'
            '<p class="note">Generated (UTC): %s. All money is paper money, in dollars. '
            '+ is a gain and - is a loss.</p>\n'
            % (esc(TITLE), esc(now_utc)))


def caveat_html(summary):
    if summary is None:
        return ('<div class="caveat"><div class="label">Read this first</div>'
                '<p class="big">No test run has been saved yet.</p>'
                '<p>This page looked for the saved test summary and did not find one, so there is no '
                'result to show. Any test run uses bars made by a script, not taken from any market, '
                'so it can never be evidence of an edge.</p></div>\n</section>\n')
    net = num(summary.get("net_pnl"))
    first = ("%s on one synthetic sample is not evidence of an edge." % money(net)
             if net is not None else "A result on one synthetic sample is not evidence of an edge.")
    return ('<div class="caveat"><div class="label">Read this first</div>'
            '<p class="big">%s</p>'
            '<p>The bars were made by a script for testing the machinery. They were not taken from any market.</p>'
            '<p>A real result needs real bars from a source whose terms allow it, and many more than one sample.</p>'
            '</div>\n</section>\n' % esc(first))


def test_section(summary, test_state):
    title = "What the bot did (%s sample)" % esc(TEST_LABEL)
    if summary is None:
        body = ('<p>No test run has been saved yet (%s). Nothing is shown here until one is.</p>'
                % esc(TEST_LABEL))
        return section("Saved test run", title, body)
    rid, _ = run_identity(summary, test_state)
    return section("Saved test run", title, result_block(summary, rid, TEST_LABEL, "test"))


SMALLER_SIZE = os.path.join(TVBOT_DIR, "config", "smaller_size.json")
SMALLER_OPTION = "--config nov14-sprint/tvbot/config/smaller_size.json"


def smaller_size_block(cfg, alt_summary):
    """The ready-made smaller order size, when its settings file is there and is smaller."""
    over = load_json(SMALLER_SIZE)
    size = num(over.get("order_notional")) if isinstance(over, dict) else None
    now_size = num(cfg.get("order_notional"))
    if size is None or now_size is None or size >= now_size:
        return ""
    alt_cfg = dict(cfg)
    alt_cfg["order_notional"] = size
    try:
        est = riskinfo.stop_out_estimate(alt_cfg, rules.validate_params(None))
    except Exception:
        return ""
    stops = est.get("stops_before_daily_limit")
    out = ["<h3>A smaller order size is ready</h3>",
           "<p>At an order size of %s, one stopped trade is estimated at <strong>%s</strong>, which is "
           "<strong>%.1f%%</strong> of the daily loss limit.%s</p>"
           % (plain_money(size), money(-abs(num(est.get("one_stop_estimate")) or 0.0)),
              num(est.get("stop_share_of_daily_limit_pct")) or 0.0,
              (" The limit then has room for about %d full stopped trades." % stops)
              if isinstance(stops, int) and stops > 1 else ""),
           "<p>To use it, add this to the end of both the gate command and the paper command:</p>",
           "<pre>%s</pre>" % esc(SMALLER_OPTION)]
    if (isinstance(alt_summary, dict) and isinstance(alt_summary.get("config"), dict)
            and num(alt_summary["config"].get("order_notional")) == size
            and num(alt_summary.get("net_pnl")) is not None):
        worst = riskinfo.worst_round_trip(alt_summary)
        w = num(worst.get("net_pnl")) if worst else None
        out.append("<p>The saved test at that size (%s) ended %s%s. A smaller size shrinks gains and "
                   "losses alike, and it is still one synthetic sample: not evidence of an edge.</p>"
                   % (esc(TEST_LABEL), money(num(alt_summary.get("net_pnl"))),
                      (", with a worst closed trade of %s" % money(w)) if w is not None else ""))
    return "\n".join(out)


def risk_section(summary, alt_summary=None):
    title = "Risk on one trade"
    if summary is None or not isinstance(summary.get("config"), dict):
        return section("Risk", title, "<p>No saved test run, so the risk numbers cannot be worked out yet.</p>")
    cfg = summary["config"]
    try:
        est = riskinfo.stop_out_estimate(cfg, rules.validate_params(None))
    except Exception:
        return section("Risk", title,
                       "<p>The saved settings could not be read, so the risk numbers cannot be worked out.</p>")
    limit = num(est.get("max_daily_loss"))
    one = num(est.get("one_stop_estimate"))
    share = num(est.get("stop_share_of_daily_limit_pct"))
    fill = 0.0 if share is None else min(100.0, max(0.0, share))
    rows = [
        ("Order size", "dollars of stock bought in one trade", plain_money(est.get("order_notional")), ""),
        ("Stop level", "the trade is sold after a bar closes this far under the entry price",
         "%s%%" % esc(est.get("stop_pct")), ""),
        ("Estimate for one stopped trade",
         "price loss %s plus costs %s, both sides"
         % (money(-abs(num(est.get("price_loss_at_stop")) or 0.0)),
            money(-abs(num(est.get("costs_both_sides")) or 0.0))),
         money(-abs(one)) if one is not None else "n/a", "bad"),
        ("Daily loss limit", "the most the bot may lose in one day before it must stop",
         plain_money(limit), ""),
    ]
    trs = "".join('<tr><td>%s<span class="gloss">%s</span></td><td class="%s">%s</td></tr>'
                  % (esc(a), esc(b), c, d) for a, b, d, c in rows)
    body = [scroll('<table><caption>One stopped trade, estimated from the test settings</caption>'
                   '<tbody>%s</tbody></table>' % trs)]
    body.append('<p><strong>Share of the daily limit used by one stopped trade</strong></p>')
    body.append('<div class="meter-row"><div class="meter"><div class="meter-fill" style="width:%.1f%%"></div></div>'
                '<div class="meter-num">%s</div></div>'
                % (fill, "n/a" if share is None else "%.1f%%" % share))
    if share is not None and share >= 100:
        body.append("<p>On these settings one stopped trade is estimated to use all of a day's loss limit.</p>")
    elif share is not None and share >= 50:
        body.append("<p>On these settings one stopped trade is estimated to use most of a day's loss limit.</p>")
    else:
        body.append("<p>On these settings one stopped trade is estimated to use part of a day's loss limit.</p>")
    stops = est.get("stops_before_daily_limit")
    if isinstance(stops, int) and not isinstance(stops, bool):
        if stops <= 0:
            body.append("<p>The limit has room for less than one full stopped trade.</p>")
        else:
            body.append("<p>The limit has room for about %d full stopped trade%s before it is used up.</p>"
                        % (stops, "" if stops == 1 else "s"))
    body.append("<p>In plain terms: one losing trade can use most or all of a day's loss limit.</p>")
    body.append('<p class="note">%s</p>' % esc(est.get("note")))

    worst = riskinfo.worst_round_trip(summary)
    body.append("<h3>The worst closed trade in the test (%s)</h3>" % esc(TEST_LABEL))
    if worst is None:
        body.append("<p>No trade was closed in the test run, so there is no worst trade to show.</p>")
    else:
        w = num(worst.get("net_pnl"))
        reason = worst.get("exit_reason")
        if w is None or w >= 0:
            body.append("<p>No closed trade lost money in the test run. The smallest result was %s.</p>"
                        % money(w))
        else:
            verdict = ""
            if limit is not None:
                if abs(w) > limit:
                    verdict = ("This loss was larger than the daily loss limit of %s." % plain_money(limit))
                else:
                    verdict = ("This loss was not larger than the daily loss limit of %s."
                               % plain_money(limit))
            body.append('<div class="verdict%s"><p><strong class="bad">%s</strong> on a trade that exited by '
                        '<code>%s</code>. %s</p></div>'
                        % (" bad" if limit is not None and abs(w) > limit else "",
                           money(w), esc(reason), esc(verdict)))
    body.append(smaller_size_block(cfg, alt_summary))
    return section("Risk", title, "\n".join(b for b in body if b))


def gate_section(gate_path, run_rid, run_hash, have_run, alt=None):
    gate = load_json(gate_path)
    valid = gate is not None and gate.get("schema") == riskinfo.GATE_SCHEMA
    decision = gate.get("decision") if valid else None
    body = []
    details = ""
    if valid and decision == "approve_paper_only":
        same = (have_run and run_rid and run_hash
                and gate.get("rule_id") == run_rid and gate.get("config_hash") == run_hash)
        alt_same = bool(alt and alt[0] and alt[1] and gate.get("rule_id") == alt[0]
                        and gate.get("config_hash") == alt[1])
        if same:
            body.append('<div class="pill ok">Approved for paper mode only</div>')
            body.append("<p>You made this decision in Terminal. It covers paper mode only, for the rule "
                        "and settings below.</p>")
        elif alt_same:
            body.append('<div class="pill ok">Approved for paper mode only</div>')
            body.append("<p>You made this decision in Terminal. It covers paper mode only, at the smaller "
                        "order size (%s), for the rule and settings below. Run the paper command with "
                        "the same <code>%s</code> option.</p>" % (plain_money(alt[2]), esc(SMALLER_OPTION)))
        else:
            body.append('<div class="pill warn">Not in force</div>')
            if have_run:
                body.append("<p>An approval file exists, but it is for a different rule or settings than "
                            "the saved test run, so it does not apply. Decide again below.</p>")
            else:
                body.append("<p>An approval file exists, but there is no saved test run to compare it "
                            "with, so it does not apply. Decide again below.</p>")
        details = True
    elif valid and decision == riskinfo.PASS_TEXT.lower():
        body.append('<div class="pill">Passed</div>')
        body.append("<p>You decided to pass. Nothing is cleared to run.</p>")
        details = True
    else:
        body.append('<div class="pill">Not decided yet</div>')
        body.append("<p>No valid decision has been recorded. Nothing is cleared to run.</p>")
    if details:
        rows = [("Decided (UTC)", gate.get("decided_utc")), ("What you typed", gate.get("typed")),
                ("Rule id", gate.get("rule_id")), ("Config hash", gate.get("config_hash"))]
        body.append(scroll("<table><caption>The recorded decision</caption><tbody>%s</tbody></table>"
                           % "".join('<tr><td>%s</td><td class="l">%s</td></tr>' % (esc(a), esc(b))
                                     for a, b in rows)))
    body.append('<p class="note">%s</p>' % esc(riskinfo.SCOPE))
    body.append("<h3>How to decide</h3>")
    body.append("<p>In Terminal, from the project folder, run:</p>")
    body.append("<pre>%s</pre>" % esc(GATE_COMMAND))
    body.append("<p>Then type %s or %s. Only a person typing in Terminal can decide; no chat message "
                "or file can.</p>" % (esc(riskinfo.APPROVE_TEXT), esc(riskinfo.PASS_TEXT)))
    body.append("<p>An approval is tied to one rule and one set of settings. To approve the smaller "
                "order size instead, add <code>%s</code> to the end of the command.</p>"
                % esc(SMALLER_OPTION))
    body.append("<p>Approval covers paper mode only and never a real order.</p>")
    return section("Gate", "Your gate: approve or pass", "\n".join(body))


def real_section(source_path, paper_state):
    body = []
    report = load_json(source_path)
    paper_summary = load_json(os.path.join(paper_state, "summary.json"))
    no_source = ("No real data source is connected. The bot reads real bars only from a CSV file Matthew "
                 "supplies, with columns ts, open, high, low, close, volume in UTC, from a source whose "
                 "terms allow it. Until then it makes no signals on real data. Steps are in START_TONIGHT.md.")
    if report is None or report.get("schema") != SOURCE_SCHEMA:
        if report is not None:
            body.append("<p>A source report file exists, but it is not in the expected format "
                        "(%s), so it is ignored.</p>" % esc(SOURCE_SCHEMA))
        body.append("<p>%s</p>" % esc(no_source))
        if paper_summary is not None:
            body.append("<p>A paper-state summary file exists, but no valid source report vouches for its "
                        "bars, so it is not shown here.</p>")
        return section("Real bars", "Real data", "\n".join(body))
    # The paper command converts a file before it can refuse it (a re-fetch that does not line
    # up, or a shorter file). The newest source report can then describe a file the saved run
    # never read. The run keeps its own copy of the report, so that copy is the one shown.
    used = paper_summary.get("source_report") if isinstance(paper_summary, dict) else None
    if (isinstance(used, dict) and used.get("schema") == SOURCE_SCHEMA and used.get("csv_sha256")
            and used.get("csv_sha256") != report.get("csv_sha256")):
        body.append('<div class="verdict bad"><p>The file converted most recently (%s rows, converted %s) '
                    'is not the file the saved paper run was made from. The paper command refused that '
                    'file or did not finish, so the table and the result below describe the earlier '
                    'file. To rebuild the paper run from the newer file, run the paper command with '
                    '<code>--fresh</code>.</p></div>'
                    % (esc(report.get("rows")), esc(report.get("converted_utc"))))
        report = used
    fields = [("Source name", "source_name"), ("Terms page", "terms_url"), ("Signed off by", "approved_by"),
              ("Signed off (UTC)", "approved_utc"), ("Symbol", "symbol"),
              ("Bar length (minutes)", "timeframe_minutes"), ("Rows", "rows"),
              ("First bar opens (UTC)", "first_ts_open"), ("Last bar closes (UTC)", "last_ts_close"),
              ("CSV SHA-256", "csv_sha256"), ("How bars are assumed to arrive", "delivery_assumption"),
              ("Converted (UTC)", "converted_utc")]
    trs = "".join('<tr><td>%s</td><td class="l">%s</td></tr>' % (esc(a), esc(report.get(k)))
                  for a, k in fields)
    body.append(scroll("<table><caption>Source report (%s)</caption><tbody>%s</tbody></table>"
                       % (esc(REAL_LABEL), trs)))
    if paper_summary is None:
        body.append("<p>No paper run on this file has been saved yet (%s).</p>" % esc(REAL_LABEL))
    else:
        rid, _ = run_identity(paper_summary, paper_state)
        body.append("<h3>What the bot did on the real bars (%s)</h3>" % esc(REAL_LABEL))
        body.append(result_block(paper_summary, rid, REAL_LABEL, "real"))
        body.append("<p><strong>One run on one file is still not evidence of an edge.</strong></p>")
    return section("Real bars", "Real data", "\n".join(body))


def footer_html(test_state, paper_state, gate_path, source_path):
    def rel(p):
        try:
            return os.path.relpath(p, TVBOT_DIR)
        except ValueError:
            return p
    files = [
        os.path.join(test_state, "summary.json"),
        os.path.join(test_state, "ledger.jsonl"),
        os.path.join(paper_state, "summary.json"),
        os.path.join(paper_state, "ledger.jsonl"),
        gate_path,
        source_path,
        os.path.join(BOT_DIR, "riskinfo.py"),
        os.path.join(BOT_DIR, "rules.py"),
    ]
    items = "".join("<li><code>%s</code> <span class=\"note\">%s</span></li>"
                    % (esc(rel(p)), "found" if os.path.isfile(p) else "not found") for p in files)
    return ('<section>\n<div class="kicker">Sources</div>\n<h2>Files this page was built from</h2>\n'
            '<p class="note">Paths are relative to the tvbot folder.</p>\n<ul>%s</ul>\n'
            '<p>No TradingView data is used anywhere in this runner.</p>\n</section>\n' % items)


def build_html(test_state, paper_state, gate_path, source_report_path, now_utc, alt_state=None):
    summary = load_json(os.path.join(test_state, "summary.json"))
    run_rid, run_hash = (run_identity(summary, test_state) if summary is not None else (None, None))
    # The saved test at the smaller order size, if there is one (TEST ONLY: synthetic).
    alt_summary = load_json(os.path.join(alt_state, "summary.json")) if alt_state else None
    alt = None
    if isinstance(alt_summary, dict) and isinstance(alt_summary.get("config"), dict):
        alt = run_identity(alt_summary, alt_state) + (alt_summary["config"].get("order_notional"),)
    parts = [
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n" % (esc(TITLE), CSS),
        header_html(now_utc),
        caveat_html(summary),
    ]
    parts += [
        test_section(summary, test_state),
        risk_section(summary, alt_summary),
        gate_section(gate_path, run_rid, run_hash, summary is not None, alt),
        real_section(source_report_path, paper_state),
        footer_html(test_state, paper_state, gate_path, source_report_path),
        "</main>\n</body>\n</html>\n",
    ]
    return "".join(p for p in parts if p)


# ------------------------------------------------------------------------ CLI

def _utc_arg(text):
    try:
        datetime.strptime(text, TIME_FORMAT)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DDTHH:MM:SSZ, got %r" % (text,))
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the paper-only result page. No network, no orders.")
    ap.add_argument("--test-state", default=os.path.join(TVBOT_DIR, "out", "normal"))
    ap.add_argument("--paper-state", default=os.path.join(TVBOT_DIR, "out", "paper"))
    ap.add_argument("--alt-state", default=os.path.join(TVBOT_DIR, "out", "small_size"),
                    help="saved test run at the smaller order size")
    ap.add_argument("--gate", default=os.path.join(TVBOT_DIR, "gate", "paper_gate.json"))
    ap.add_argument("--source-report", default=os.path.join(TVBOT_DIR, "real", "last_source.json"))
    ap.add_argument("--out", default=os.path.join(TVBOT_DIR, "RESULT.html"))
    ap.add_argument("--now", type=_utc_arg, default=None)
    args = ap.parse_args(argv)
    now = args.now or datetime.now(timezone.utc).strftime(TIME_FORMAT)
    page = build_html(args.test_state, args.paper_state, args.gate, args.source_report, now,
                      alt_state=args.alt_state)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(page)
    os.replace(tmp, args.out)
    print(os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
