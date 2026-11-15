"""Read-only check: the Sunday PDF brief against the reissued watchlist.

It extracts the PDF's text with the standard library only (ASCII85 and Flate
streams, literal Tj and TJ strings) and compares it with
results/sunday_20261115_watchlist.json.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B <this file>
Writes nothing. Imports no engine, view or PDF-builder module. No network.
"""
import base64
import hashlib
import json
import os
import re
import zlib
from datetime import datetime, timedelta, timezone

S = "/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate"
PDF = S + "/pdf_export/Sunday_NFL_Brief.pdf"
WL = S + "/results/sunday_20261115_watchlist.json"
WL_ISSUED = S + "/results/sunday_20261115_watchlist.issued_2026-11-15T073826Z.json"
EVID = S + "/pdf_export/evidence/2026-11-15.json"
results = []


def check(name, ok, detail=""):
    results.append(ok)
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
                if body.endswith(b"~>"):
                    body = body[:-2]
                if body.startswith(b"<~"):
                    body = body[2:]
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


text = pdf_text(PDF)
wl = json.load(open(WL))
issued = json.load(open(WL_ISSUED))

print("0. Files")
print("    PDF", mtime(PDF), sha(PDF)[:16], "| watchlist", mtime(WL), sha(WL)[:16], "| PDF evidence", mtime(EVID), sha(EVID)[:16])
check("PDF text extracted with the standard library", len(text) > 1000, "%d chars" % len(text))

print("1. Reissued watchlist against the 07:38:26Z issue")
added = sorted(set(wl) - set(issued))
changed = [k for k in issued if k in wl and issued[k] != wl[k]]
# 07:45Z reissue added appearance_evidence; the 09:36:16Z reissue added supplement and annotated ranked rows.
check("top level: only appearance_evidence and supplement added, only ranked changed, nothing removed",
      set(added) <= {"appearance_evidence", "supplement"} and set(changed) <= {"ranked"} and not set(issued) - set(wl),
      (added, changed))
ri = {r["rank"]: r for r in issued["ranked"]}
rw = {r["rank"]: r for r in wl["ranked"]}
same = ("id", "label", "event_id", "market", "subject", "side", "point", "price", "sportsbook", "status", "kickoff", "volatility")
diff = {k: [f for f in same if ri[k].get(f) != rw[k].get(f)] for k in ri}
check("ranks 1-5 unchanged in order, label, line, side, price, book, status, kickoff and volatility",
      sorted(ri) == sorted(rw) and not any(diff.values()), diff)
ann = ("market_value_", "evidence_utc", "supplemental_", "last_start")
extra = {k: sorted(f for f in set(rw[k]) - set(ri[k]) if not f.startswith(ann)) for k in ri}
gone = {k: sorted(set(ri[k]) - set(rw[k])) for k in ri}
check("rows only gained market_value_*, evidence_utc, supplemental_* or last_start fields; none removed",
      not any(extra.values()) and not any(gone.values()), (extra, gone))
tags = {k: (ri[k]["risk_tag"], rw[k]["risk_tag"]) for k in ri if ri[k]["risk_tag"] != rw[k]["risk_tag"]}
other = {k: [f for f in ri[k] if f not in same + ("risk_tag",) and ri[k][f] != rw[k].get(f)] for k in ri}
check("only Warren's (1) and Bowers's (5) risk_tag changed; no other issued field changed",
      sorted(tags) == [1, 5] and not any(other.values()), (tags, {k: v for k, v in other.items() if v}))
ae = wl["appearance_evidence"]
check("appearance_evidence hash is the props input", ae["sha256"] == sha(S + "/props_20261115.json"), ae["sha256"][:16])

print("2. Top 5 table against the ranked rows")
check("ranked time shown as 1:38 am CT", "at %s CT" % chicago(wl["ranked_utc"]) in text, chicago(wl["ranked_utc"]))
obs = {chicago(r["observed_utc"]) for r in wl["ranked"]}
check("quote time shown as 12:55 am CT", all("Quotes at %s CT" % o in text for o in obs), sorted(obs))
top5 = text.find("Top 5 potential bets")
order = [text.find(r["label"].split(" · ")[-1], top5) for r in sorted(wl["ranked"], key=lambda r: r["rank"])]
# The column header is now "STATUS / RISK", so a row reads "-115 BetMGM Formal · high · PIT inactives / shared targets".
# Check tokens inside each row's own segment, as r8 does, not one exact string.
for i, r in enumerate(sorted(wl["ranked"], key=lambda r: r["rank"])):
    seg = text[order[i]: order[i + 1] if i + 1 < len(order) else order[i] + 260] if order[i] > top5 > 0 else ""
    status = "Formal" if r["status"] == "formal_call" else "Watch"
    price = "%+d" % r["price"]
    tokens = [price, r["sportsbook"], status, r["volatility"].lower(), r["risk_tag"], chicago(r["kickoff"])]
    missing = [t for t in tokens if t not in seg]
    check("rank %d %s at %s %s, kickoff %s" % (r["rank"], r["label"], price, r["sportsbook"], chicago(r["kickoff"])),
          not missing, "missing %s" % missing if missing else "")
check("rows appear in rank order 1 to 5", all(x > 0 for x in order) and order == sorted(order), order)
fc = wl["formal_call_counts"]
check("two formal calls (early 1, night 1) and none in the afternoon", fc == {"early": 1, "night": 1, "late": 0} and "Afternoon pass." in text, fc)

print("3. Warren text against the appearance evidence")
sel = json.load(open(S + "/results/sunday_20261115_selections.json"))
e = sorted([c for c in sel["calls"] if c.get("subject") == "Jaylen Warren"][0]["recent_appearances"]["entries"], key=lambda r: r["date"])
today5, today10 = sum(r["value"] > 22.5 for r in e[-5:]), sum(r["value"] > 22.5 for r in e)
own5, own10 = sum(r["value"] > r["prior_line"] for r in e[-5:]), sum(r["value"] > r["prior_line"] for r in e)
check("today's line: 4 of last 5 and 7 of 8", "%d of his last 5 games and %d of %d this season" % (today5, today10, len(e)) in text, (today5, today10, len(e)))
check("own posted lines: 6 of 8, labelled unverified", ("beat %d of %d actual prior lines" % (own10, len(e))) in text and "unverified" in text, (own10, len(e)))
check("zero receiving yards last game shown", e[-1]["value"] == 0 and "zero receiving yards last game" in text)

print("4. LOW notes (not counted)")
if ("%d of his last 5" % own5) not in text.split("prior lines")[0][-200:] and "3 of his last 5" not in text:
    note("own-line last five (%d of 5) is not shown; only the 8-game own-line count is." % own5)
for p in ("Freiermuth", "Harmon"):
    if p not in text:
        note("%s is not named in the PDF (the HTML front door names him)." % p)
if "143" not in text:
    note("the week 8 appearance (17 rushes for 143 yards) is not shown; the PDF says only zero receiving yards.")
if os.path.getmtime(EVID) > os.path.getmtime(PDF):
    ev = json.load(open(EVID))
    titles = [c.get("title") for c in ev.get("calls", [])]
    note("PDF evidence file changed at %s, after the PDF at %s. Its call titles %s; in the PDF: %s"
         % (mtime(EVID), mtime(PDF), titles, [t in text for t in titles]))

print("TOTAL", sum(results), "of", len(results), "checks pass")
