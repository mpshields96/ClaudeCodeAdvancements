"""Build Matthew's portable November 15 NFL desk from named release artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import stat
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
PREFIX = "Sunday NFL Desk/"
SLATE = "nfl/slate/"
LIVE_SOURCE = (Path.home() / "Documents/Codex/2026-11-14/paper-desk-final-closeout"
               / "outputs/NFL_Live")
PACKAGED = HERE / "release_data"
DEFAULT_LIVE = PACKAGED if PACKAGED.is_dir() else LIVE_SOURCE
DATE_STAMP = (2026, 11, 15, 0, 0, 0)

PROJECT_FILES = (
    "advisor/NFL_REVIEW.md", "nfl/BEST_BETS_SUN_NOV15.html",
    "codex/NFL_SUNDAY_HEALTH.json", "codex/real-intake/nfl-prop-reference.json",
    "nfl/real/inputs/nfl-public-lines.20261114T225342Z.json",
    "nfl/rules.py", "nfl/data/raw/games.csv", "nfl/data/raw/MANIFEST.json",
)
SLATE_FILES = (
    "Open Sunday NFL.command", "pack_sunday.py",
    "sunday_availability.py", "sunday_card.py", "sunday_desk.py", "sunday_extras.py", "sunday_intake.py",
    "sunday_markets.py", "sunday_notebook.py", "sunday_quotes.py",
    "sunday_scoreboard.py", "sunday_view.py", "sunday_week_ui.py",
    "experiment/journal.py", "experiment/postgame/postgame.py", "experiment/postgame/espn_fetch.py",
    "pdf_export/brief.py", "pdf_export/generate_brief", "pdf_export/Rebuild Sunday Brief.command",
    "pdf_export/requirements.txt", "pdf_export/evidence/2026-11-15.json",
    "picker.py", "selection_decisions.py", "selection_markets.py", "build_watchlist.py",
    "frozen_picker.json", "slate_20261115.json", "props_20261115.json",
    "tools/appearance_gamebook_rows_20261115.json", "tools/official_appearance_sources_20261115.json",
    "tools/official_player_logs_20261115.json",
    "replacements/next_man_up.py", "replacements/replacement_report_20261115.json",
    "replacements/KC_SNAPSHOT_20261115.md", "replacements/cases/kansas_city_team.json",
    "replacements/cases/green_bay_team.json", "replacements/cases/sunday_20261115.spec.json",
    "replacements/tests/test_availability.py",
    "results/past_only_test.json", "results/sunday_20261115_candidates.json",
    "results/sunday_20261115_review_evidence.json", "results/sunday_20261115_selections.json",
    "results/sunday_20261115_watchlist.json", "PAST_ONLY_TEST.md", "PROP_REVIEW.md",
    "results/sunday_20261115_watchlist.issued_2026-11-15T073826Z.json",
    "FOOTBALL_RED_TEAM.md",
    "weekly_inputs/2026-11-15/schedule.json", "weekly_inputs/2026-11-22/schedule.json",
    "weekly_inputs/2026-11-22/captures/2026-11-15T073418Z.json",
    "results/sunday_20261115_candidates.superseded_6885d506c57b84b6.json",
    "sunday_week_review.py", "sunday_week_release.py", "weekly_football.py", "weekly/weekly_api.py",
    "sunday_club_news.py",
    "issued_picker_20261115.py", "issued_selection_decisions_20261115.py", "selection_release.py",
    "weekly/README.md", "experiment/postgame/README.md",
    "experiment/SETTLEMENT_API.md",
)
LIVE_FILES = (
    "odds_feed.py", "compare_books.py", "verify_card.py",
    "sunday-odds.json", "Sunday_Card.json", "Final_Decisions.json", "Matchup_Review.md",
    "Price_Band_Benchmark.md", "Legacy_Home_Dogs.md", "Legacy_Home_Dogs_Freeze.json",
    "Match_Control_Rule.json", "Matched_Role_Control.json", "Sunday NFL Brief.pdf",
)
# Exact archived bytes. Recreate the replaceable "latest" pointer from a verified observation.
CAPTURE_DIGESTS = {
    "sunday-odds.json": "2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f",
    "Sunday_Card.json": "96d09884cab7d0444c8f95551def07f43a94ed9de22695a280947310d4106932",
    "Final_Decisions.json": "7b95f1289cf97df3a945cdb0375f32869241fc998c1f3a617b3c48f625090858",
}
# These published role inputs are the reproducible evidence for the KC and GB cases.
# Only their recorded files are read, and each is checked against the dated report.
ROLE_FILES = {
    "inputs/chiefs-injury.20261115T072459Z/source.html",
    "inputs/nfl-com-injuries-reg10.20261115T071450Z/nfl_injuries_reg10.html",
    "replacements/inputs/kc-atl-rush-attempts.20261115T075205Z.json",
    "replacements/inputs/sunday-odds.20261115T065506Z.json",
}
ROLE_FILES.update(f"inputs/espn-team-statistics.20261115T065633Z/team_{team}.json" for team in (1, 9, 12, 16))
ROLE_FILES.update("replacements/inputs/" + folder + "/source.html" for folder in (
    "chiefs-preview-five-things.20261115T075408Z", "nfl-log-chris-brooks.20261115T075918Z",
    "nfl-log-emmett-johnson.20261115T075408Z", "nfl-log-jaydn-ott.20261115T075120Z",
    "nfl-log-josh-jacobs.20261115T075918Z", "nfl-log-kaleb-johnson.20261115T081133Z",
    "nfl-log-kenneth-walker-iii.20261115T075120Z", "nfl-log-marshawn-lloyd.20261115T081133Z",
    "nfl-log-nate-carter.20261115T075919Z", "nfl-log-pierre-strong.20261115T075920Z",
    "nfl-news-walker-out.20261115T075408Z", "packers-brooks-activation.20261115T075408Z",
    "packers-depth.20261115T075408Z", "packers-inbox-nov13.20261115T075408Z",
))
AVAILABILITY = {
    "2026-11-15/availability/capture-20261115T081736812027Z-e631c718b29760b8a0fd1acfe9d059af5ee47dd75bea695c087bb4ee23d140e1.json":
        "61656d98e6e8a1d5e90c9663c1011bb7e92320ce3a8f3bb014a5d3c19d9c1e6f",
    "2026-11-22/availability/capture-20261115T081734865275Z-d432c71c265355309d290f220b45b162baae71b1bd27e84565c2c892deeb0e2f.json":
        "45486798b3cf70a07392259e08efdaf7afaf8e92a4908334eb4d025dfd2272a2",
}
OBSERVATIONS = {
    "kc-atl-20261115-rush-attempts.json": "611fc1b289eef3d1f5485f8151803c6378c21ae1f5fd8686512bbc7b312b7c46",
    "prices-20261115T070857592195Z.json": "7fedae05443dd316cee03ea36101bda6a997b70c2cbf887b245725c5db4869d3",
    "exact-observation-20261115T073000526529Z.json": "770ed0686da2c8ac585ab9fffcda8f96c846c012571a76316c262dcbf538a96a",
    "window-20261115T073000Z.json": "5ca9334283ce3bd290ac0cd94c0c3f49f9036d6a4d420cb7ea9bc55a78558eb4",
    "exact-observation-20261115T080000853499Z.json": "180cf4089245ae9e4db28dc349b67c8fae42e9967405c88bfc8594bad92d4a6b",
    "window-20261115T080000Z.json": "79f4f202e072cff99994df014c71c4753901cb899866a24f91970dfff92f7bfe",
    "exact-observation-20261115T085000656610Z.json": "c94815985a9ea4b14382b9e6d125ba298c2f84f4a1b7807201bafc5fa84e751c",
    "window-20261115T085000Z.json": "0d7bc0546936e8aec9898860fade0477d496f24f466dee5c0756a1965b2407f6",
    "exact-observation-20261115T093513987156Z.json": "aa3079f31d84ca01c489ce685d09ba8e9e4f75ff8ea3636748da875c7ec056c7",
    "final-release-20261115T093513Z.json": "0bdb63e586ae3e54cd94ebc1ccf10d722fb4370842f22f2fef17b24587109033",
}
LATEST_EXACT = "exact-observation-20261115T093513987156Z.json"
# Only read an authenticated original prefix. A later append in a working journal
# must never carry anyone's subsequent picks, tickets, results or notes into a new copy.
SEEDS = {
    "predictions.jsonl": (2160124, "471a5f1f6820e3220b90196ad2c15aa3ae3d8878b4573afb9b3c02d69d66d688"),
    "hypotheses.jsonl": (2058, "db311d3dcc2c39d88252de59b4f12fa5f71b3eecf774174e5afe9b5f262e94ec"),
    "controls.jsonl": (1605, "b4075980123ef7c5c9e5f2c99e366e368305522313e9c16fa41f21b5786916ee"),
    "research.jsonl": (1755, "a1848e6e5d70cdd92f8bf3ef46b205275d89b5836008a9ebe62916c0bceace57"),
}
LAUNCHER = """#!/bin/sh
set -eu
desk=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$desk/nfl/slate/Open Sunday NFL.command" "$@"
"""
SAVED_LAUNCHER = """#!/bin/sh
set -eu
desk=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$desk/Open Sunday NFL.command" --saved --date 2026-11-15 "$@"
"""
README = """Sunday NFL Desk  |  November 15, 2026

Extract the entire ZIP, keep the folder together and double-click Open Sunday NFL.command.
The desk runs in a local browser on this Mac. Close its Terminal window to stop it.
For the archived November 15 card with zero feed credits, double-click Open Saved November 15.command.
For a quick read, open the enclosed Sunday NFL Brief.pdf. It ranks five opportunities and
identifies the two issued conditional calls. Quoted prices carry observation times.

Using saved data
    ./\u0022Open Sunday NFL.command\u0022 --saved --date 2026-11-15
    ./\u0022Open Sunday NFL.command\u0022 --saved --date 2026-11-22
    ./\u0022Open Sunday NFL.command\u0022 --help
Run these commands from the extracted folder. The saved option uses the archived quotes.
The normal November 15 launch may request an exact-price refresh. Explicit refresh and
future-date intake use the configured sources and can consume odds-feed credits.
The included Nov 22 example uses its own saved schedule and main-market prices.

Notebook and postgame
The November 15 journal starts with 1,756 priced contracts, two calls, two preregistered
hypotheses, one matched role control, and one rejected research rule. These original,
hash-chained agent entries live in nfl/slate/experiment/data. Personal views,
accepted tickets and results begin empty.
The desk keeps new entries in the extracted folder. Keep a used folder separate from a
new extraction so its journal remains yours. The After the games view reads this journal.

PDF export
The desk exports the November 15 PDF using the dated evidence and observations inside
this folder. For an offline regeneration, double-click the Rebuild Sunday Brief.command
in nfl/slate/pdf_export. It writes Sunday_NFL_Brief.pdf next to the generator. This Mac
provides the PDF Python runtime. Another installation can point NFL_PDF_PYTHON to a Python
interpreter with the packages in pdf_export/requirements.txt.

Release files
nfl/slate/release_data contains the saved issuing card, decisions, odds, observations,
adapters and comparison evidence. The stored capture and issued terms retain their
original hashes. Historical provenance strings describe the author's source locations.
The extracted desk uses its own copies. Manifest.json lists payload digests and modes.
The player-log and gamebook indexes in nfl/slate/tools accompany the current-season
appearance samples. Warren's receiving log is available at
https://www.nfl.com/players/jaylen-warren/stats/logs/2026/

Rebuild this ZIP from a freshly extracted folder
    /usr/bin/python3 -IB nfl/slate/pack_sunday.py --output "../Sunday NFL Desk.zip"
The builder accepts only listed release artifacts and the verified starter journal bytes.
Local view, ticket and results history are omitted from subsequent release packages.
"""

def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(root, name, length=None):
    """Read a named regular file without following a symlink outside this source tree."""
    path = root / name
    if path.resolve() != path or not path.is_file():
        raise ValueError(f"Missing or indirect release input: {name}")
    with path.open("rb") as stream:
        return stream.read() if length is None else stream.read(length)


def checked_bytes(data, expected, label):
    if digest(data) != expected:
        raise ValueError(f"Unexpected contents in {label}")
    return data


def verify_releases(entries):
    """Check frozen evidence and exclude personal fill records from published research."""
    def artifact(name):
        return entries[SLATE + name][0]

    def record(name):
        return json.loads(artifact(name))

    selected = record("results/sunday_20261115_selections.json")
    candidate = record("results/sunday_20261115_candidates.json")
    ranked = record("results/sunday_20261115_watchlist.json")
    issued_file = "results/sunday_20261115_candidates.superseded_6885d506c57b84b6.json"
    issued = record(issued_file)["selections"]
    if any(stream.get("tickets") != [] for stream in [issued, selected, candidate["selections"]]):
        raise ValueError("The portable release accepts only ticket-free selection records")
    if candidate["selections"] != selected:
        raise ValueError("Selection and candidate files are from different builds")
    checked_bytes(artifact("replacements/replacement_report_20261115.json"),
                  candidate["inputs"]["replacement_evidence"]["sha256"], "dated replacement context")
    inputs = ranked["inputs"]
    checked_bytes(artifact(issued_file), inputs["candidate_record_sha256"], "issued ranking pool")
    original = (json.dumps(issued, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()
    checked_bytes(original, inputs["selection_record_sha256"], "issued ranking selections")
    checked_bytes(artifact("props_20261115.json"), ranked["appearance_evidence"]["sha256"], "prop sample")
    snapshot_hash = CAPTURE_DIGESTS["sunday-odds.json"]
    if ranked["capture_sha256"] != snapshot_hash or selected["capture_sha256"] != snapshot_hash:
        raise ValueError("Selection or ranking refers to a different price capture")
    rank_rows = ranked["ranked"]
    if ([r["rank"] for r in rank_rows] != [1, 2, 3, 4, 5] or
            [r["status"] for r in rank_rows].count("formal_call") != len(selected["calls"])):
        raise ValueError("Invalid five-row issued watchlist")
    return original


def release_payload(live, seed_dir):
    entries = {}
    def add(name, data, mode=0o644):
        if name in entries:
            raise ValueError(f"Duplicate release member: {name}")
        entries[name] = (data, mode)

    for name in PROJECT_FILES:
        add(name, checked_file(PROJECT, name))
    for name in SLATE_FILES:
        mode = 0o755 if name.endswith(".command") or name == "pdf_export/generate_brief" else 0o644
        add(SLATE + name, checked_file(HERE, name), mode)
    for club in ("chiefs-injury.20261115T072459Z", "steelers-matchup.20261115T072500Z"):
        for file in ("source.html", "source.json"):
            name = "inputs/" + club + "/" + file
            add(SLATE + name, checked_file(HERE, name), 0o444)

    role = json.loads(entries[SLATE + "replacements/replacement_report_20261115.json"][0])
    for receipt in role["inputs"]:
        name = posixpath.normpath(posixpath.join("replacements", receipt["file"]))
        if name not in ROLE_FILES:
            raise ValueError(f"Unlisted source in replacement report: {name}")
        if SLATE + name not in entries:
            add(SLATE + name, checked_file(HERE, name), 0o444)
        checked_bytes(entries[SLATE + name][0], receipt["sha256"], name)

    fixtures = SLATE + "release_data/"
    add(fixtures + "ranking_at_issue_selections.json", verify_releases(entries), 0o444)
    # A working journal can regenerate EVALUATION.md with personal results. The
    # portable publication pins the clean starter readout and keeps a frozen copy.
    if live == PACKAGED:
        evaluation = checked_file(live, "Starter_Evaluation.md")
    else:
        evaluation = checked_file(HERE, "experiment/EVALUATION.md")
    checked_bytes(evaluation, "ecbf6cf348ea394171abb2287554895997707d8775b09eafc2fa538d628b9bcd",
                  "clean release evaluation")
    add(fixtures + "Starter_Evaluation.md", evaluation, 0o444)
    add(SLATE + "experiment/EVALUATION.md", evaluation)
    checked_bytes(entries[SLATE + "weekly_inputs/2026-11-15/schedule.json"][0],
                  "fb6f4b2976bf20e491688b760bc4979781a34bc6f66b233f5f03d7b26fe09ca4",
                  "Nov 15 schedule reconstructed from archived ESPN summaries")
    sample = SLATE + "weekly_inputs/2026-11-22/"
    checked_bytes(entries[sample + "schedule.json"][0],
                  "26f830ca77c6fe38812ab1a63f12b380d7f2a3d4bed87075c65ac3018f108fb8", "Nov 22 schedule")
    snapshot = entries[sample + "captures/2026-11-15T073418Z.json"][0]
    add(sample + "odds.json", checked_bytes(snapshot,
        "a5d6b1057b4536b3d44be3b53c698489b6026067245587022d1e14a2c2ececb6", "Nov 22 prices"))
    for name, expected in AVAILABILITY.items():
        path = "weekly_inputs/" + name
        add(SLATE + path, checked_bytes(checked_file(HERE, path), expected, path), 0o444)
    for name in LIVE_FILES:
        # Desk exports may replace the writable PDF in release_data. Repacking an
        # extracted desk always uses its original top-level publication.
        if name == "Sunday NFL Brief.pdf":
            data = (checked_file(PROJECT, name) if live == PACKAGED else
                    checked_file(HERE, "pdf_export/Sunday_NFL_Brief.pdf"))
        else:
            data = checked_file(live, name)
        if name in CAPTURE_DIGESTS:
            checked_bytes(data, CAPTURE_DIGESTS[name], name)
        mode = 0o644 if name == "Sunday NFL Brief.pdf" else 0o444
        add(fixtures + name, data, mode)
    for name, expected in OBSERVATIONS.items():
        data = checked_file(live, "observations/" + name)
        add(fixtures + "observations/" + name, checked_bytes(data, expected, name), 0o444)
    last = entries[fixtures + "observations/" + LATEST_EXACT][0]
    fingerprint = json.loads(last)["fingerprint"]
    if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise ValueError("Invalid frozen quote fingerprint")
    add(fixtures + "observations/exact-" + fingerprint + ".json", last)
    for name, (length, expected) in SEEDS.items():
        seed = checked_file(seed_dir, name, length)
        add(SLATE + "experiment/data/" + name, checked_bytes(seed, expected, "starter " + name))

    # Finder front door and easy-to-find PDF. The PDF exporter writes its own regenerated copy.
    add("Open Sunday NFL.command", LAUNCHER.encode(), 0o755)
    add("Open Saved November 15.command", SAVED_LAUNCHER.encode(), 0o755)
    add("Sunday NFL Brief.pdf", entries[fixtures + "Sunday NFL Brief.pdf"][0])
    add("Read Me.txt", README.encode())
    manifest = {n: {"sha256": digest(data), "bytes": len(data), "mode": format(mode, "04o")}
                for n, (data, mode) in sorted(entries.items())}
    add("Manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    return entries


def write_archive(entries, output):
    if output.suffix.lower() != ".zip":
        raise ValueError("Output must end in .zip")
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".sunday-nfl-", suffix=".zip",
                                     delete=False) as file:
        temporary = Path(file.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, (data, mode) in sorted(entries.items()):
                info = zipfile.ZipInfo(PREFIX + name, DATE_STAMP)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise ValueError(f"ZIP integrity check failed at {bad_file}")
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-dir", type=Path, default=DEFAULT_LIVE,
                        help="directory containing the named release adapters and fixtures")
    parser.add_argument("--seed-dir", type=Path, default=HERE / "experiment/data",
                        help="directory containing the authenticated generated starter rows")
    default_output = PROJECT.parent if PACKAGED.is_dir() else LIVE_SOURCE
    parser.add_argument("--output", type=Path, default=default_output / "Sunday NFL Desk.zip")
    args = parser.parse_args()
    entries = release_payload(args.live_dir.resolve(), args.seed_dir.resolve())
    output = args.output.absolute()
    write_archive(entries, output)
    print(f"{output}\n{len(entries)} files  ·  {output.stat().st_size:,} bytes  ·  SHA-256 {digest(output.read_bytes())}")


if __name__ == "__main__":
    main()

