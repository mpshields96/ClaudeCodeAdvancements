"""Parse the saved Covers NFL player-props page (public, no login) into per-book OVER quotes.

Usage: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_parse_covers.py <covers_playerprops.body> <out.json>
Stdlib only. The page lists ~50 curated cards (Covers' own projection board). Each card has
one OVER quote per book (line + price). Under prices are not shown. Covers' own
"projection"/"EV" numbers are a third-party model output and are deliberately NOT extracted.
"""
import html
import json
import re
import sys

ROW_RE = re.compile(r'<tr class="game-projections-container"([^>]*)>')


def clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def parse_row(seg, attrs):
    market = re.search(r'data-market-name="([^"]*)"', attrs).group(1)
    game_m = re.search(r'<a href="(/sport/football/nfl/matchup/(\d+)/picks#props)"[^>]*class="projection-game-link[^>]*>\s*([^<]*?)\s*</a>', seg)
    player_m = re.search(r'<a href="(/sport/football/nfl/players/(\d+)/[^"]*)" class="player-link">\s*([^<]*?)\s*</a>\s*<span class="player-position">\s*\(([^)]*)\)', seg)
    avatar = re.search(r"alt='([^']*) logo'", seg)
    team_alt = re.search(r"alt='([^']*) image thumbnail'", seg)
    headline = re.search(r'<span class="prediction[^>]*>([^<]*)</span>', seg)
    quotes = []
    for col in re.findall(r'<div class="compare-odds-column.*?</a>\s*</div>\s*</div>', seg, flags=re.S):
        book = re.search(r'alt="([^"]*?) logo"', col)
        a = re.search(r'<a [^>]*class="book-odds[^>]*>(.*?)</a>', col, flags=re.S)
        if not (book and a):
            continue
        txt = clean(a.group(1))
        m = re.match(r"^([ou])\s*([0-9]+(?:\.[0-9]+)?)\s+([+-][0-9]+)$", txt)
        if m:
            quotes.append({"book": html.unescape(book.group(1)), "side": "over" if m.group(1) == "o" else "under",
                           "line": float(m.group(2)), "price": int(m.group(3))})
        else:
            quotes.append({"book": html.unescape(book.group(1)), "side": None, "line": None, "price": None, "raw": txt})
    return {
        "market_name": market,
        "matchup_href": game_m.group(1) if game_m else None,
        "covers_matchup_id": game_m.group(2) if game_m else None,
        "game_label": game_m.group(3) if game_m else None,
        "player_full_name": html.unescape(avatar.group(1)) if avatar else None,
        "player_label": clean(player_m.group(3)) if player_m else None,
        "position": player_m.group(4) if player_m else None,
        "covers_player_id": player_m.group(2) if player_m else None,
        "team_name": html.unescape(team_alt.group(1)) if team_alt else None,
        "covers_headline": clean(headline.group(1)) if headline else None,
        "quotes": quotes,
    }


def main():
    src, out = sys.argv[1], sys.argv[2]
    t = open(src, encoding="utf-8", errors="replace").read()
    ms = list(ROW_RE.finditer(t))
    cards = []
    for i, m in enumerate(ms):
        end = t.find("</tr>", m.end())
        if end < 0:
            end = len(t)
        cards.append(parse_row(t[m.end():end], m.group(1)))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=1)
    print("cards", len(cards))


if __name__ == "__main__":
    main()
