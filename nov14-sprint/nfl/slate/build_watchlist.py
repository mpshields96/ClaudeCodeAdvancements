"""Build the dated Sunday watchlist from already reviewed football evidence and frozen quotes.

This editorial ordering is separate from the signed decision. It never modifies the
picker, the decision overlay, its controls, or a ticket. Offline; Python 3.9+.
"""
import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CAPTURE = "2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f"
DATE = "2026-11-15"
ISSUED = RESULTS / "sunday_20261115_watchlist.issued_2026-11-15T073826Z.json"
ISSUED_SHA = "155a4e84da6ff16c57135bafff7832658a44be6988246c02a19f20f0b72325b4"
SUPPLEMENT_UTC = "2026-11-15T09:35:09Z"
METHOD = (
    "Editorial ranking for the November 15 Chicago slate. Start with documented football cases "
    "from the release review and independent red team. Look for repeatable opportunity or team "
    "strength, assess what changed in personnel and opponent, then compare two-sided exact-line "
    "prices at the captured US books. Rank the combined football and price case. A price or "
    "historical hit rate alone cannot determine rank. One contract per game keeps shared game "
    "scripts from dominating this five-row list. Volatility is qualitative sensitivity to role, "
    "personnel or a small number of possessions; no statistical variance was estimated."
)
# Exact descriptors from the reviewed pool. Book, price, identifiers and status are
# always looked up from the frozen candidate and selection files.
RANKING = [
    (("PIT at CIN", "player_reception_yds", "Jaylen Warren", "Over", 22.5), "High", "Passing-down role",
     "Four of five and seven of eight current-season appearances cleared 22.5. Both football reviews keep the conditional case; the only exact-line quote needs 53.5%, and Dowdle shares passing work."),
    (("KC at ATL", "h2h", "", "Kansas City Chiefs", None), "Moderate", "Price / injured starters",
     "Kansas City's 6–2 record, scoring defense and five-book favorite status support the win call. The best −166 offer still needs more wins than the peer estimate; the independent reviewer would pass."),
    (("NE at DET", "team_totals_h1", "Detroit Lions", "Under", 13.5), "High", "Short half / injuries",
     "Detroit stayed below 13.5 in six of eight first halves, and New England allowed fewer than 14 in five of nine. The best exact under is −105. A short field or late personnel news can overturn the Munich case."),
    (("MIA at IND", "team_totals", "Indianapolis Colts", "Under", 20.5), "Moderate", "Short fields / run game",
     "Indianapolis stayed under in three of its last four and lost receiving personnel. BetMGM's −102 is near the other books' fair estimate, but Miami held just two of eight opponents below 20.5."),
    (("SEA at LV", "player_reception_yds", "Brock Bowers", "Over", 58.5), "High", "First-start quarterback",
     "Bowers cleared 58.5 in five of five and all seven current-season appearances. The seven occurred before rookie Fernando Mendoza's first start. Seattle had allowed 42.1 yards per game to entire tight-end groups."),
]
ALTERNATIVES = [
    ("Jordan Love over 254.5 passing yards", "Seven of nine at this line, but Minnesota allowed 186.9 passing yards per game to opposing quarterbacks."),
    ("Joe Burrow over 6.5 rushing yards", "Six of eight, but one scramble or kneel can decide this short line. Shares Warren's game."),
    ("Arizona first-half team points under 6.5", "A rookie quarterback and replacement center favor the under; only four of nine Arizona first halves and three of nine Rams opponents stayed below 6.5."),
    ("John Metchie III over 7.5 receiving yards", "Six reported overs occurred before Xavier Legette's return. His recent opportunity may change."),
    ("Minnesota first-half team points over 9.5", "The peer price gap was about 0.19 percentage points, with no comparable independent football case supporting priority."),
]


def read_record(path):
    payload = path.read_bytes()
    return json.loads(payload), sha256(payload).hexdigest()


def capture_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build(candidates, selections, now):
    if candidates["inputs"]["lines"]["sha256"] != CAPTURE or selections["capture_sha256"] != CAPTURE:
        raise ValueError("This editorial watchlist requires its original capture")
    if not candidates["frozen"]["verified"] or selections["stage"] != "reviewed" or not selections["pregame"]:
        raise ValueError("A verified pregame reviewed card is required")
    pool = {(c["game"], c["provider_market"], c["subject"], c["outcome"], c["line"]): c
            for c in candidates["slate"]["candidates"]}
    formal = {c["id"]:c for c in selections["calls"]}
    if [c["id"] for c in selections["calls"]] != candidates["slate"]["picks"]:
        raise ValueError("The candidate and reviewed call records disagree")
    game_by_id = {g["event_id"]:g for g in candidates["slate"]["games"]}
    ranked = []
    for index, (key, volatility, risk, fit) in enumerate(RANKING, 1):
        c = pool[key]
        book = c["source"]
        g = game_by_id[c["event_id"]]
        if not c["in_price_band"] or not 100 <= abs(c["price"]) <= 200 or book["opposite_price"] is None:
            raise ValueError("Ranked contract lacks a qualifying two-sided quote: "+c["id"])
        if capture_time(book["observed_utc"]) >= capture_time(c["kickoff_utc"]):
            raise ValueError("Quote does not predate kickoff")
        ranking_status = "formal_call" if c["id"] in formal else "watchlist_only"
        ranked.append({
            "rank":index, "id":c["id"], "event_id":c["event_id"], "market":c["provider_market"],
            "period":c["period"], "subject":c["subject"], "side":c["outcome"], "point":c["line"],
            "label":c["label"], "game":c["game"], "matchup":g["name"], "kickoff":c["kickoff_utc"],
            "kickoff_chicago":g["kickoff_local"], "valid_until_utc":c["kickoff_utc"], "window":c["window"],
            "book":book["book"], "sportsbook":book["title"], "price":c["price"],
            "observed_utc":book["observed_utc"], "provider_updated_utc":book["provider_updated_utc"],
            "status":ranking_status, "formal_call":c["id"] in formal, "volatility":volatility,
            "risk_tag":risk, "fit":fit, "break_even":c["break_even"], "market_probability":c["hit_likelihood"],
            "probability_basis":c["likelihood_basis"], "exact_line_books":c["book_count"],
            "other_two_sided_books":c["peer_count"], "source_url":book["source_url"], "ticket":None,
        })
    if len({c["event_id"] for c in ranked}) != 5 or {c["id"] for c in ranked if c["formal_call"]} != set(formal):
        raise ValueError("Comparative ranking lost an issued call or duplicated a game")
    duration = "Sunday, November 15, 2026 in America/Chicago. Each row expires at its own kickoff; the saved price requires a personal recheck."
    counts = Counter(c["window"] for c in selections["calls"])
    return {"schema_version":1, "slate_date":DATE, "ranked_utc":now.isoformat(timespec="seconds").replace("+00:00","Z"),
            "timezone":"America/Chicago", "duration":duration, "method":METHOD, "method_type":"editorial football and exact-price review",
            "capture_sha256":CAPTURE, "captured_utc":selections["capture_utc"], "capture_utc":selections["capture_utc"],
            "original_decision_utc":selections["decided_utc"], "original_freeze_utc":candidates["frozen"]["frozen_utc"],
            "formal_call_counts":{window:counts[window] for window in ("early","late","night")},
            "reviewed_alternatives":ALTERNATIVES, "ranked":ranked}


def add_supplement(record, candidates_sha, selections_sha):
    review, review_sha = read_record(RESULTS / "sunday_20261115_review_evidence.json")
    teams, teams_sha = read_record(HERE / "slate_20261115.json")
    warren, bowers = record["ranked"][0], record["ranked"][4]
    pit = review["by_call"][warren["id"]]
    lv = next(g for g in teams["games"] if g["odds_event_id"] == bowers["event_id"])["teams"]["home"]
    club = lv["qb"]["club_announcement"]
    if (review_sha != "6b99a7662178f58ece05fe029dd8a92725c16345ff15469acb84b9ba19477604"
            or review["capture_sha256"] != record["capture_sha256"]
            or teams_sha != pit["team_input"]["sha256"] or not club["verified"]):
        raise ValueError("Supplement needs the verified, saved November 15 evidence")

    record["supplement"] = {
        "published_utc": SUPPLEMENT_UTC, "issued_watchlist_sha256": ISSUED_SHA,
        "candidate_record_sha256": candidates_sha, "selection_record_sha256": selections_sha,
        "slate_sha256": teams_sha, "review_evidence_sha256": review_sha,
        "market_value_basis": "Market probability with the bookmaker margin removed minus the hit rate needed at the quoted price, in percentage points. Within 0.1 point of zero is labeled essentially even. This compares prices; it does not estimate a football edge or change the ranking."
    }
    for r in record["ranked"]:
        gap = 100 * (r["market_probability"] - r["break_even"])
        r["market_value_gap_pp"] = round(gap, 3)
        label = "Essentially even" if abs(gap) <= 0.1 else ("Favorable" if gap > 0 else "Unfavorable")
        r["market_value_label"] = label
        source = ("the offering book alone; no other exact-line quote" if not r["other_two_sided_books"]
                  else f'{r["other_two_sided_books"]} other books at this line')
        r["market_value_detail"] = (f'{label}: market estimate {r["market_probability"]:.2%} '
                                    f'({source}); quote needs {r["break_even"]:.2%}.')

    # Observation times and later editorial publication are separate from the original ranking.
    players = {person["position"]: person for person in pit["players"]}
    te, dt = players["TE"], players["DT"]
    warren.update(
        evidence_utc=review["verified_utc"],
        supplemental_fit=f'If TE {te["player"]} sits, short targets could shift. Warren shares that work with Rico Dowdle; extra targets for Warren are uncertain.',
        supplemental_risk=f'TE {te["player"]} ({te["cause"].lower()}) and DT {dt["player"]} ({dt["cause"].lower()}) were questionable. Harmon could affect game script, not Warren’s receiving role directly. Recheck final inactives and Warren’s passing-down role.',
        risk_tag="PIT inactives / shared targets",
        supplemental_sources=[{k: person[k] for k in ("player", "source_url", "reported_utc", "retrieved_utc")}
                              for person in (te, dt)])
    last = lv["qb_last_start"]
    bowers.update(
        evidence_utc=club["retrieved_utc"],
        supplemental_fit=f'The Raiders named {club["expected_starter"]} their starting quarterback. {last["name"]} started their last game on {last["gameday"]}.',
        supplemental_risk="Bowers’ seven-game sample predates the new starter. Mendoza’s target distribution is unknown; recheck the quarterback and Bowers on the final inactives.",
        risk_tag="QB change / recheck inactives",
        supplemental_sources=[{k: club[k] for k in ("source_url", "retrieved_utc", "sha256", "page_title")}],
        last_start=last)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates",type=Path,default=RESULTS/"sunday_20261115_candidates.json")
    parser.add_argument("--selections",type=Path,default=RESULTS/"sunday_20261115_selections.json")
    parser.add_argument("--output",type=Path,default=RESULTS/"sunday_20261115_watchlist.json")
    a=parser.parse_args()
    candidates,candidate_digest=read_record(a.candidates)
    selections,selection_digest=read_record(a.selections)
    if a.output.resolve() == ISSUED.resolve():
        raise ValueError("The issued watchlist is immutable")
    issued, issued_sha = read_record(ISSUED)
    if issued_sha != ISSUED_SHA:
        raise ValueError("Issued watchlist does not match its archived digest")
    # Replay all ranked fields against current inputs before attaching any later evidence.
    # Always start from the immutable copy so a clean build cannot redate the ranking.
    record=build(candidates,selections,capture_time(issued["ranked_utc"]))
    if any(issued.get(k) != v for k,v in record.items() if k != "reviewed_alternatives"):
        raise ValueError("Current inputs no longer reproduce the issued watchlist")
    if [list(pair) for pair in record["reviewed_alternatives"]] != issued["reviewed_alternatives"]:
        raise ValueError("Original reviewed alternatives changed")
    record=issued
    context = candidates["inputs"].get("player_context") or {}
    if context.get("sha256") == "7f202c76572738e0329e8c9721fbaacee06333008748a019d05880c380b50980":
        update = {"version":2, "sha256":context["sha256"], "built_utc":context["built_utc"],
                  "role":"Subsequent verification of consecutive 2026 player appearances. Original ranking retained."}
        record["appearance_evidence"] = update
    add_supplement(record, candidate_digest, selection_digest)
    if capture_time(SUPPLEMENT_UTC) >= min(capture_time(r["kickoff"]) for r in record["ranked"]):
        raise ValueError("A new pregame watchlist cannot be issued after the first ranked kickoff")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile("w",dir=a.output.parent,encoding="utf-8",delete=False) as f:
        json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write("\n")
        temp=Path(f.name)
    try:
        os.replace(temp,a.output)
    finally:
        temp.unlink(missing_ok=True)
    for r in record["ranked"]:
        print(r["rank"],r["label"],r["sportsbook"],r["price"],r["status"],r["volatility"])


if __name__=="__main__":
    main()
