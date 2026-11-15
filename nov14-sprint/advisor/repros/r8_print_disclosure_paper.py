"""Read-only acceptance recheck for the 09:23:32-11:23:32Z window on Nov 15.

Covers four open items against the current product:
  1. M5: every call's evidence is labelled known, estimated or unknown, and the
     calls are still bound to the 07:08:57Z issue.
  2. Print edition: the front-door PDF (and the builder's copy) against the
     watchlist rows and the latest saved price observation, by token.
  3. Same-game disclosure: whether any two selections share a game, and where
     the product would print the shared-game line.
  4. Paper versus real cash: saved quotes are labelled as quotes, no ticket is
     implied, and the journal keeps Matthew's accepted terms apart.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B <this file>
Writes nothing. Imports no engine, view, journal or PDF-builder module. No network.
"""
import base64
import hashlib
import json
import os
import re
import zlib
from datetime import datetime, timedelta, timezone

S = "/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate"
LIVE = "/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live"
FRONT = "/Users/matthewshields/Documents/Codex/2026-11-15/nfl-weekly-release-integration/outputs/Sunday NFL Brief.pdf"
BUILDER = S + "/pdf_export/Sunday_NFL_Brief.pdf"
SEL = S + "/results/sunday_20261115_selections.json"
WL = S + "/results/sunday_20261115_watchlist.json"
CAPTURE = "2a50d6951366342f"
ISSUED = "2026-11-15T07:08:57"
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print("   ", "PASS" if ok else "FAIL", name, detail)


def note(text):
    print("    NOTE", text)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def mtime(path):
    return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%H:%M:%SZ")


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n in "nrtbf":
                out.append({"n": "\n", "r": "", "t": " ", "b": "", "f": ""}[n]); i += 2
            elif n.isdigit():
                m = re.match(r"[0-7]{1,3}", s[i + 1:])
                out.append(chr(int(m.group(0), 8))); i += 1 + len(m.group(0))
            else:
                out.append(n); i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def pdf_text(path):
    raw = open(path, "rb").read()
    chunks = []
    for m in re.finditer(rb"<<(.*?)>>\s*stream\r?\n(.*?)endstream", raw, re.S):
        head, body = m.group(1), m.group(2)
        try:
            if b"ASCII85Decode" in head:
                body = body.strip()
                body = body[:-2] if body.endswith(b"~>") else body
                body = body[2:] if body.startswith(b"<~") else body
                body = base64.a85decode(body)
            if b"FlateDecode" in head:
                body = zlib.decompress(body)
        except Exception:
            continue
        txt = body.decode("latin-1")
        for t in re.finditer(r"\((?:\\.|[^\\)])*\)\s*Tj|\[(?:[^\]]*)\]\s*TJ", txt):
            parts = re.findall(r"\(((?:\\.|[^\\)])*)\)", t.group(0))
            chunks.append("".join(unescape(p) for p in parts))
    return " ".join(" ".join(chunks).split())


def chicago(utc):
    # November 15, 2026 is standard time in Chicago (UTC-6).
    t = datetime.strptime(utc[:19], "%Y-%m-%dT%H:%M:%S") - timedelta(hours=6)
    h = t.hour % 12 or 12
    return "%d:%02d %s" % (h, t.minute, "am" if t.hour < 12 else "pm")


def dec(p):
    return 1 + (p / 100.0 if p > 0 else 100.0 / -p)


sel = json.load(open(SEL))
wl = json.load(open(WL))
calls = sel["calls"]

print("0. Files")
for p in (FRONT, BUILDER, SEL, WL):
    print("   ", mtime(p), sha(p)[:16], p.replace(S, "slate").replace(LIVE, "NFL_Live"))
# At 09:34Z the front door was a link; from 09:41Z it is a copy. Either way it must be the NFL_Live brief.
check("front door PDF is the NFL_Live brief and the builder copy (same bytes)",
      sha(FRONT) == sha(LIVE + "/Sunday NFL Brief.pdf") == sha(BUILDER),
      "link" if os.path.islink(FRONT) else "copy")

print("1. M5: evidence labels and binding to the 07:08:57Z issue")
check("selections still bound to capture %s and decided %sZ" % (CAPTURE, ISSUED),
      sel["capture_sha256"].startswith(CAPTURE) and sel["decided_utc"].startswith(ISSUED), sel["run_utc"])
check("two calls, no tickets", len(calls) == 2 and not sel.get("tickets"), (len(calls), sel.get("ticket_status")))
for c in calls:
    ev = c.get("evidence") or []
    labels = [(e.get("kind"), e.get("label")) for e in ev]
    allowed = all(l in ("known", "estimated", "unknown") for _, l in labels)
    kinds = dict(labels)
    hl = c.get("health") or {}
    ok = (allowed and kinds.get("price") == "known" and kinds.get("football_judgment") == "estimated"
          and {"known", "estimated", "unknown"} <= {l for _, l in labels}
          and hl.get("report_status") == "known" and hl.get("final_participation") == "unknown"
          and hl.get("official_inactives_verified") is False)
    check("%s: every item labelled; price known, judgment estimated, participation unknown" % c["label"], ok, labels)

print("2. Print edition (front door), token check per row")
front = pdf_text(FRONT)
builder = pdf_text(BUILDER)
check("PDF text extracted", len(front) > 1000, "%d chars" % len(front))
top = front.find("Top 5 potential bets")
rows = sorted(wl["ranked"], key=lambda r: r["rank"])
starts = []
for r in rows:
    tail = r["label"].split(" · ")[-1]
    starts.append(front.find(tail, top))
check("rows appear in rank order 1 to 5", top > 0 and all(x > top for x in starts) and starts == sorted(starts), starts)
for i, r in enumerate(rows):
    seg = front[starts[i]: starts[i + 1] if i + 1 < len(starts) else starts[i] + 260]
    status = "Formal" if r["status"] == "formal_call" else "Watch"
    tokens = ["%+d" % r["price"], r["sportsbook"], status, r["volatility"].lower(), r["risk_tag"], chicago(r["kickoff"])]
    missing = [t for t in tokens if t not in seg]
    check("rank %d %s" % (r["rank"], r["label"]), not missing, "missing %s" % missing if missing else " ".join(tokens))
note("r7's exact-string row check failed only because the column header became 'STATUS / RISK' and the"
     " word 'risk' left each row (for example 'Formal · high · PIT inactives / shared targets'). Layout change, not content.")
obs_path = sorted((f for f in os.listdir(LIVE + "/observations") if f.startswith(("window-", "final-release-"))),
                  key=lambda f: json.load(open(LIVE + "/observations/" + f))["checked_utc"])[-1]
obs = json.load(open(LIVE + "/observations/" + obs_path))
print("    latest saved observation:", obs_path, "source", obs["source"], "credits used", obs["credits_used"])
for c in calls:
    q = [x for x in obs["quotes"] if x["sportsbook"] == c["sportsbook"] and x["selection"].startswith(c["label"])]
    q = q[0] if q else None
    if not q:
        check("%s: latest saved quote found" % c["label"], False)
        continue
    p = q["price"]
    expect = ["%+d · %s %s CT" % (p, q["sportsbook"], chicago(q["utc"])), "Limit: %+d or better" % c["minimum_price"],
              "$%.2f net per $10" % ((dec(p) - 1) * 10), "Break-even: %.1f%%" % (100 / dec(p))]
    missing = [t for t in expect if t not in front]
    check("%s: TL;DR shows the latest saved quote, its time, limit and break-even" % c["label"], not missing,
          "missing %s" % missing if missing else expect)
    check("%s: latest saved quote still meets the issued limit" % c["label"], dec(p) >= dec(c["minimum_price"]),
          "%+d vs limit %+d" % (p, c["minimum_price"]))
w = [c for c in calls if c.get("subject") == "Jaylen Warren"][0]
e = sorted(w["recent_appearances"]["entries"], key=lambda r: r["date"])
t5, t10 = sum(x["value"] > 22.5 for x in e[-5:]), sum(x["value"] > 22.5 for x in e)
o10 = sum(x["value"] > x["prior_line"] for x in e)
check("Warren counts with n: today's line %d of 5 and %d of %d; own lines %d of %d unverified" % (t5, t10, len(e), o10, len(e)),
      ("cleared 22.5 in %d of his last 5 games and %d of %d this season (fewer than 10 played)" % (t5, t10, len(e))) in front
      and ("beat %d of %d actual prior lines. Their books and quote times are unverified" % (o10, len(e))) in front)
if builder != front:
    extra = [s for s in ("Confirm Jaydn Ott (questionable) at inactives",) if s in front and s not in builder]
    note("builder copy %s differs from the front door %s; front-door-only text: %s. The front door is the product."
         % (mtime(BUILDER), mtime(FRONT), extra))
for p in ("Freiermuth", "Harmon"):
    if p not in front:
        note("%s is not named in the PDF (the HTML page names him; LOW, unchanged)." % p)

print("3. Same-game disclosure")
games = {}
for c in calls:
    games.setdefault(c["event_id"], []).append(c["label"])
shared = {k: v for k, v in games.items() if len(v) > 1}
wl_games = {}
for r in rows:
    wl_games.setdefault(r.get("event_id") or r.get("game") or r["label"], []).append(r["rank"])
print("    selections: %d calls in %d games; watchlist: %d rows, keyed by %s" % (len(calls), len(games), len(rows),
      "event_id" if rows[0].get("event_id") else "game"))
check("no same-game pair among today's calls, so no shared-game line is owed", not shared, shared or "")
check("no call carries shared_game_risk or same_game_contract_ids", not any(c.get("shared_game_risk") or c.get("same_game_contract_ids") for c in calls))
check("PDF prints no false shared-game line", "Shared game risk" not in front)
check("watchlist rows are in distinct games", all(len(v) == 1 for v in wl_games.values()), sorted(wl_games.values()))
src = {n: open(S + "/" + n).read() for n in ("pdf_export/brief.py", "selection_release.py", "sunday_view.py", "sunday_week_release.py")}
# The '/' page words it "Same-game selections share game risk"; the 09:34Z version of this check
# searched only "Shared game" and wrongly reported the page as missing the line.
paths = {n: bool(re.search(r"Shared[ -]game|Same-game|shared_game_risk", t)) for n, t in src.items()}
print("    render paths with a shared-game line:", paths)
check("every render path (PDF, release report, '/' page, week pages) has a shared-game line", all(paths.values()), paths)
check("the '/' page prints it when two calls share an event_id",
      'if len({c["event_id"] for c in card["calls"]})<len(card["calls"]):' in src["sunday_view.py"]
      and "Same-game selections share game risk" in src["sunday_view.py"])
# Final policy (09:35Z): same-game allowed with the disclosure; no opposing same-subject formal picks at any threshold.
subj = {}
for c in calls:
    subj.setdefault((c["event_id"], c["market"], c.get("subject") or ""), set()).add(c.get("side"))
check("no opposing formal picks on one event, market and subject (any threshold)",
      all(len(v) == 1 for v in subj.values()), sorted((k[1], k[2], sorted(v)) for k, v in subj.items()))

print("4. Paper versus real cash")
for t in ("BEST SAVED QUOTE", "No ticket recorded", "Conditional selections", "Log your read and any ticket",
          "Louisiana availability is unverified", "Saved observations only. No verified opener, close or closing-line value"):
    check("PDF says: %s" % t, t in front)
view = src["sunday_view.py"]
check("page footer keeps selection, observed odds and accepted ticket apart",
      "A conditional selection, observed odds, and an accepted ticket are three different records" in view
      and "Matthew submits any wager himself" in view)
j = open(S + "/experiment/journal.py").read()
need = ["offered_price", "Enter the actual ticket placement time", "issued_minimum_price", "meets_issued_minimum",
        "Your tickets (only what you reported)"]
missing = [t for t in need if t not in j]
check("journal stores accepted price, offered price, stake, placement time and the issued-minimum comparison",
      not missing, "journal.py %s; missing %s" % (mtime(S + "/experiment/journal.py"), missing))
check("journal report marks a ticket below the issued minimum, or at a different line",
      '" [below the issued minimum]" if t["meets_issued_minimum"] is False' in j
      and "[different line from the bot's" in j and "graded at `price`, never at it" in j)

print("5. Static front door page (outputs/Sunday NFL.html), read as text only")
import html as _html
PAGE = os.path.dirname(FRONT) + "/Sunday NFL.html"
raw = open(PAGE, encoding="utf-8").read()
raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
page = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
print("   ", mtime(PAGE), sha(PAGE)[:16], "%d chars" % len(page))
oc = chicago(obs["checked_utc"]).replace("am", "AM").replace("pm", "PM")
check("page shows the latest saved observation time", "Sun %s CT (%s)" % (oc, obs["checked_utc"]) in page, oc)
cells = []
for c in calls:
    q = [x for x in obs["quotes"] if x["sportsbook"] == c["sportsbook"] and x["selection"].startswith(c["label"])][0]
    upd = chicago(q["book_updated_utc"]).replace("am", "AM").replace("pm", "PM")
    p = ("%+d" % q["price"]).replace("-", "−")
    m = ("%+d" % c["minimum_price"]).replace("-", "−")
    cells.append("%s %s · %s" % (c["sportsbook"], p, q["status"]))
    want = ["%s %s · book update Sun %s CT" % (q["sportsbook"], p, upd), "Minimum acceptable %s or better" % m]
    missing = [t for t in want if t not in page]
    check("%s: page price, book update time and minimum" % c["label"], not missing,
          "missing %s" % missing if missing else want[0])
# Each price-history row holds both calls side by side, in card order.
row = "Sun %s CT %s" % (oc, " ".join(cells))
check("page price-history row for the latest observation", row in page, row)
for t in ("Saved quote · recheck before use", "No ticket is created by a price check",
          "A conditional selection, observed odds, and an accepted ticket are three different records",
          "Matthew submits any wager himself", "Only rows marked formal call are on the issued card"):
    check("page says: %s" % t, t in page)
check("page prints no false same-game line", "Same-game selections share game risk" not in page and "Shared game" not in page)
if obs.get("credits_used") and "This check used 0 free credits" in page:
    note("page says 'This check used 0 free credits' beside the %s observation, which itself used %s credits"
         " (the 0 is the offline reread). LOW wording." % (obs["checked_utc"], obs["credits_used"]))

print("TOTAL", sum(results), "of", len(results), "checks pass")
