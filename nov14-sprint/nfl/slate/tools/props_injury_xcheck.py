#!/usr/bin/env python3
"""Cross-check the players in the prop feed against the NFL.com week-10 injury page capture. Read-only, no network, stdlib only, Python 3.9 safe.

Usage: props_injury_xcheck.py <review.json> <nfl_injuries_reg10.html> <out.md>
Run as: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_injury_xcheck.py ...

The page lists the players on a team's week-10 injury report. Some rows carry only a practice status and no game status. A player absent from the page is
therefore "not on the report", not "confirmed healthy".
Each NFL.com row reads: Player, Position, Injuries, Practice Status, Game Status. The parser finds each prop player's name in the visible text and reads the
text that follows up to the next player link. It prints the raw text it found so the reader can check it. Nothing is inferred from team or position.
"""
import json, sys, re, html, unicodedata, collections

SHORT = {"player_pass_yds": "pass yds", "player_rush_yds": "rush yds", "player_reception_yds": "rec yds"}
GAME_STATUS = ("Out", "Doubtful", "Questionable", "Injured Reserve", "Suspended", "Physically Unable to Perform")


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def rows_from_page(t):
    """Split the page into player rows. Each row starts at an <a ... href="/players/slug/"> link; take the visible text up to the next such link."""
    parts = re.split(r'(?=<a [^>]*href="/players/[^"]+/")', t)
    out = []
    for p in parts[1:]:
        txt = re.sub(r"<[^>]+>", " ", p)
        txt = re.sub(r"\s+", " ", html.unescape(txt)).strip()
        txt = txt.split(" Player Position Injuries Practice Status Game Status")[0]  # a team's table header can follow its last row
        # a team name can follow the last row of its table; cut after the last status phrase
        txt = re.sub(r"^(.*(?:Questionable|Doubtful|\bOut\b|Injured Reserve|Participation in Practice|Participate In Practice)).*$", r"\1", txt)
        out.append(txt)
    return out


def main(rev_p, html_p, out_p):
    rv = json.load(open(rev_p))
    t = open(html_p, encoding="utf-8", errors="replace").read()
    rows = rows_from_page(t)
    # visible text per row, keyed by normalized leading name; the link's own text repeats the name, so use the text after "Visit ... profile page" if present
    page = {}
    for r in rows:
        r2 = re.sub(r"^.*?profile page\s*", "", r, count=1) if "profile page" in r[:200] else r
        m = None
        for st in GAME_STATUS:
            if re.search(r"\b" + re.escape(st) + r"\b", r2[:200]):
                m = st
                break
        page.setdefault(norm(" ".join(r2.split()[:3])), []).append((r2[:140], m))
    names = collections.OrderedDict()
    for x in rv["review"]:
        names.setdefault(x["player"], []).append(x)

    found = []
    for nm, xs in names.items():
        n = norm(nm)
        hit = None
        for k, v in page.items():
            if k.startswith(n) or n.startswith(k.split(" ")[0] + " " + (k.split(" ")[1] if len(k.split(" ")) > 1 else "")) and n.split(" ")[-1] == k.split(" ")[-1]:
                hit = v[0]
                break
        # fallback: look for the normalized name in any row text
        if hit is None:
            for r in rows:
                if n in norm(r[:160]):
                    hit = (re.sub(r"^.*?profile page\s*", "", r, count=1)[:140], None)
                    break
        found.append((nm, xs, hit))

    espn_flag = {nm: (xs[0]["identity"].get("injuries") or []) for nm, xs, _ in found}
    out = []
    out.append("### K. Injury cross-check: ESPN roster status (06:58:49Z) against the NFL.com week-10 injury page (07:14:50Z)\n")
    out.append("The NFL.com page lists players on the week-10 injury report. A row with a practice status and no game status carries no game designation. A player absent from the page is not on the report, which is not the same as confirmed healthy. Final inactives come about 90 minutes before each kickoff and are not in either source.\n")
    both, only_espn, only_nfl = [], [], []
    for nm, xs, hit in found:
        e = espn_flag[nm]
        if e and hit:
            both.append((nm, xs, e, hit))
        elif e and not hit:
            only_espn.append((nm, xs, e))
        elif hit and not e:
            only_nfl.append((nm, xs, hit))
    out.append("Prop players with an ESPN flag: %d; also on the NFL.com page: %d; on ESPN only: %d. On the NFL.com page without an ESPN flag: %d.\n" % (len(both) + len(only_espn), len(both), len(only_espn), len(only_nfl)))
    out.append("**On both sources**\n")
    out.append("| Player | Props in the feed | ESPN status | NFL.com row as parsed |")
    out.append("|---|---|---|---|")
    for nm, xs, e, hit in both:
        out.append("| %s | %s | %s (%s) | %s |" % (nm, ", ".join(sorted(SHORT[x["market"]] for x in xs)), e[0]["status"], e[0]["date"], hit[0]))
    out.append("")
    out.append("**On ESPN only (NFL.com shows no designation at 07:14:50Z; the two sources disagree and I cannot tell which is newer)**\n")
    for nm, xs, e in only_espn:
        out.append("- %s (%s): ESPN %s as of %s" % (nm, ", ".join(sorted(SHORT[x["market"]] for x in xs)), e[0]["status"], e[0]["date"]))
    out.append("")
    out.append("**On the NFL.com page with no ESPN flag**\n")
    out.append("| Player | Props in the feed | NFL.com row as parsed |")
    out.append("|---|---|---|")
    for nm, xs, hit in only_nfl:
        out.append("| %s | %s | %s |" % (nm, ", ".join(sorted(SHORT[x["market"]] for x in xs)), hit[0]))
    out.append("")
    open(out_p, "w").write("\n".join(out) + "\n")
    print("both", len(both), "espn_only", len(only_espn), "nfl_only", len(only_nfl), "page rows", len(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
