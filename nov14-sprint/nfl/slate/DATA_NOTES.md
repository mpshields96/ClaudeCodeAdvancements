# Slate data notes (nfl-slate-data) - FINAL v2 for the Sun Nov 15 2026 slate

Built 2026-11-15 07:34:55Z by the nfl-slate-data worker. Paper and advisory only. Nothing here is a model output. The only estimated value is the inactives time.

**Deliverable:** `nfl/slate/slate_20261115.json` (12 games, 24 teams, 79 cited sources, 0 builder warnings, 0 validation problems). SHA-256 `c90a28feeb23e96ddecabb20e0da634db27646676e62d1dd500e4463c1716593`, 1,278,224 bytes. The file is large because every value carries its own `source_url` and `retrieved_utc`.

**What changed since the first delivery (07:22Z, sha `8de8f4ae...84ae`, now superseded):**
- Weather is now in the file (new per-game `weather` block). My first version said weather was "not captured". That was wrong: the ESPN summaries I had already pulled carry it for 11 of 12 games. Corrected.
- The six quarterbacks that were `unknown` are now `known`, each verified against the club's own announcement page that I captured myself (new `qb.club_announcement` block). The source conflicts stay recorded in `conflict_reasons`.
- ESPN carries no league ranks, so I derived them: new `league_ranks` per team, over all 32 teams (I captured the 8 non-slate teams' statistics for this). Label `derived`.
- Per-game `caveats` list for the quarterbacks (health words on the club pages, ESPN depth chart still showing a different QB).
- The injury rows are unchanged: 204 rows, known 177, unknown 27.
- Everything else in the file is byte-for-byte the same values (checked by diffing the two builds apart from the new or updated fields).

**Rebuild command** (one self-contained stdlib file, Python 3.9-safe, run isolated; inputs are the newest capture folders below):

    S=nov14-sprint/nfl/slate
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I $S/tools/build_slate.py \
      --out $S/slate_20261115.json \
      --espn-summary-dir $S/inputs/espn-summary.20261115T071450Z \
      --espn-stats-dir $S/inputs/espn-team-statistics.20261115T065633Z \
      --espn-stats-extra-dir $S/inputs/espn-team-statistics-nonslate.20261115T073159Z \
      --club-qb-dir $S/inputs/club-qb-announcements.20261115T072922Z \
      --espn-depth-dir $S/inputs/espn-depthcharts.20261115T065829Z \
      --nfl-injuries-dir $S/inputs/nfl-com-injuries-reg10.20261115T071450Z \
      --odds-shared ~/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json \
      --health nov14-sprint/codex/NFL_SUNDAY_HEALTH.json \
      --lines nov14-sprint/nfl/real/inputs/nfl-public-lines.20261114T225342Z.json \
      --games-csv nov14-sprint/nfl/data/raw/games.csv

The builder verifies each capture's sha256 against the disk, skips non-200 bodies, and exits 1 if validation fails (12 games, 24 teams, required fields, four last-four games each, cross-book block present). The two new flags are optional; without them the file builds as in the first delivery.

## Labels used in the file
- **known**: read straight from a cited source.
- **derived**: arithmetic on known values, with the formula named (per-game stats = ESPN total / games played; yards per play = totalYards / totalOffensivePlays; SU/ATS/O/U and points from nflverse rows; league ranks from the per-game values).
- **unknown**: a source is missing or sources disagree. Never filled in.
- **estimated**: used for exactly one thing, the inactives time (kickoff minus 90 minutes). No data value is estimated.

## Sources and as-of times (UTC)
| Item | Source | As-of |
|---|---|---|
| Per-book prices (moneyline, spread, total) for 5 LA books, with each quote's `last_update`, plus best price across books | Codex shared capture `.../paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json` (read with `python3 -I`; no Odds API call, no key) | 2026-11-15T06:55:06Z |
| DraftKings display lines (`odds.ml/spread/total`, kept for compatibility) | `nfl/real/inputs/nfl-public-lines.20261114T225342Z.json`, DraftKings via ESPN display; not a confirmed Louisiana quote | 2026-11-14T22:53:42Z |
| Team health strings (Out, Doubtful, Questionable) | `nov14-sprint/codex/NFL_SUNDAY_HEALTH.json` (Codex, relaying the NFL.com week 10 report) | 2026-11-15T06:38:46Z |
| Official injury table with practice participation | NFL.com `https://www.nfl.com/injuries/league/2026/reg10`, parsed from server-rendered HTML. The page has no timestamp, so retrieval time is the only as-of | 2026-11-15T07:14:50Z |
| ESPN injuries (per-row `date`), standings, leaders, **weather** | ESPN public site API `summary?event=<id>`, 12 events | 2026-11-15T07:14:57Z |
| Team offense and defense (stats and allowed) | ESPN public site API team statistics, 24 slate teams | 2026-11-15T06:56:47Z |
| Team statistics for the 8 other teams (ranks only: CHI, DEN, NYG, PHI, LAC, TB, WSH, BAL) | Same ESPN endpoint | 2026-11-15T07:31:59Z |
| Depth chart (QB room, first-string flag per injured player) | ESPN public site API depth charts, 24 teams | 2026-11-15T06:58:44Z |
| Starting-QB confirmation for ARI, CLE, LV, MIA, MIN, SEA | The six club news pages, captured by this lane (URLs in the file and below) | 2026-11-15T07:29:22Z |
| Records, ATS, O/U, points, last 4, rest days, home/away splits, QB per game, H2H since 2016, roof | nflverse `nov14-sprint/nfl/data/raw/games.csv`, games before Nov 15 only, sha256 `44f6ba50a76303869229be8fdad82d124e77f24f50c90c319fbc245dd34120a0` | 2026-11-14T21:16:58Z |

Matching: the shared capture is matched to ESPN events by full team name plus commence time. nflverse LA is ESPN LAR in the file. NE at DET carries `neutral: true` (Munich) and is excluded from home/away splits.

## What was checked
- **Independent recompute** (a second script, different code path, over `games.csv`), run on the first build: SU, ATS, O/U, points for and against per game, and games played match the slate for all 24 teams, with 0 mismatches. Head-to-head counts since 2016 match for all 12 games. SU also matches the ESPN standings for all 24 teams (`record_crosscheck_ok`). Those values did not change in v2 (diffed).
- ESPN points per game and points allowed per game equal the nflverse figures for all 24 teams.
- **Cross-book prices**: every moneyline, spread line and total line for every book matches the raw shared capture (360 raw outcomes scanned, 0 mismatches).
- **Injuries**: all 156 NFL.com Out, Doubtful and Questionable rows on the 24 slate teams appear in the slate. 204 injury rows in all: Out 78, Questionable 78, No designation 30 (full or limited practice, no game designation), Injured Reserve 14, Doubtful 4. The raw page also lists Commanders, Giants, Chargers and Ravens rows; those teams are not on Sunday's slate, so their rows are left out.
- **v2 build check**: 12 games, 24 teams, 0 warnings, 0 problems. League ranks cover 32 teams for every metric (rank 1 = best, ties share a rank). Re-counted the injury labels from the final file. Diffed v2 against the first delivery: nothing changed except the new and updated fields.

## Injury rows by evidence label (the `evidence` field on each of the 204 rows)
Counted from the v2 file at 07:35Z.
- **known: 177.** The sources agree on the game status, or only one source lists the player. Doubtful 4, Injured Reserve 14, No designation 30, Out 55, Questionable 74.
- **estimated: 0.** No injury status is estimated. The only estimated value in the file is the inactives time.
- **unknown: 27.** Codex health, NFL.com and ESPN disagree on game status. Out 23, Questionable 4. These rows keep every source's status in `status_by_source`, and the `status` field shows the highest-priority source (Codex health first, then NFL.com, then ESPN). Treat them as open until the inactives. By game: CAR@NO 4, MIA@IND 4, SF@DAL 4, HOU@CLE 3, JAX@TEN 3, PIT@CIN 3, KC@ATL 2, NE@DET 1, BUF@NYJ 1, MIN@GB 1, LAR@ARI 1, SEA@LV 0.
- Every row carries `source_url`, `report_utc` and `source_ids` (0 rows lack any of them).
- QB labels, a separate field on each team: **known 24 teams, unknown 0** (was 18 and 6 in the first delivery).

## Quarterbacks: all 24 teams known
For 18 teams the sources agree. For the six that disagreed, the club's own page names the starter. I checked each page by full name plus a sentence that names the player with "start" (no page text is copied into the file; it stores counts, booleans and keywords). The conflicts stay in each team's `qb.conflict_reasons`, and the game's `caveats` list says what to confirm at the inactives.
- **CLE** Deshaun Watson: https://www.clevelandbrowns.com/news/deshaun-watson-set-to-start-week-10-against-the-texans . The page sentences naming him contain "concussion".
- **MIA** Kyle McCord: https://www.miamidolphins.com/news/top-quotes-dolphins-travel-to-indianapolis-with-a-new-quarterback-new-captain
- **MIN** Kirk Cousins: https://www.vikings.com/news/kirk-cousins-starting-packers-week-10-game-2026 . Health word "injur" appears near his name (Kyler Murray is Out; recorded as a room note).
- **ARI** Carson Beck: https://www.azcardinals.com/news/for-starters-carson-beck-ready-to-play-first-game-against-rams
- **LV** Fernando Mendoza: https://www.raiders.com/news/fernando-mendoza-named-raiders-starting-quarterback
- **SEA** Drew Lock: https://www.seahawks.com/news/drew-lock-confident-and-optimistic-heading-into-sunday-s-game-other-seahawks-updates . Lock was limited in practice (oblique and elbow words appear) and is starting for Sam Darnold, who is Out in all three injury sources. ESPN's depth chart still lists Darnold first. This is the one to watch at the inactives.

## Weather (new, ESPN summary `gameInfo.weather`)
11 of 12 games carry a `weather` block labeled `known` with temperature, high, low, gust, precipitation, a condition code and the AccuWeather link. Caveats, all stated in the file:
- ESPN gives no units and no forecast hour. I read the values as degrees F, mph and percent chance (an assumption, flagged in `unit_assumption`). The condition code has no text in the feed, so I give no description.
- Roof: nflverse supplies a roof value for 8 games. It is **blank for KC@ATL, MIA@IND, LAR@ARI and SF@DAL**, and ESPN does not fill it, so weather may or may not apply there. Each block has a `roof_note`: weather applies only if the roof is open.
- NE at DET (Munich) has no weather object in ESPN, so its block is `unknown`. nflverse labels the venue "dome"; I could not verify that independently.
- By game (temp, gust, precipitation): BUF@NYJ 50/27/3, CAR@NO 61/24/0 (dome), HOU@CLE 46/21/60, JAX@TEN 53/7/0, KC@ATL 54/5/0, MIA@IND 46/10/0, MIN@GB 41/5/0, LAR@ARI 76/6/0, SEA@LV 66/7/0 (dome), SF@DAL 48/18/47, PIT@CIN 39/5/0.

## League ranks (new, label `derived`)
`teams.<side>.league_ranks` ranks each slate team among all 32 using per-game values. Offense: points, yards, yards per play, pass yards, rush yards and third-down percent (higher is better), giveaways (lower is better). Defense: points, yards, yards per play, pass yards and rush yards allowed and third-down percent allowed (lower is better), takeaways and sacks (higher is better). Each entry has `rank`, `of` (32), `value` and `direction`. Per-game values make a bye or Thursday game comparable.

## What is still missing (also in each game's `missing` array; 65 entries, 12 distinct kinds)
- **Final inactives.** Released about 90 minutes before kickoff, so after my 08:59:53Z hard stop. Every Questionable and Doubtful status is open. See "Rerun at the inactives" below.
- NFL.com injury report publication time (the page has no timestamp).
- Practice participation for players absent from the NFL.com table (ESPN carries none).
- Weather forecast hour and units (not stated by ESPN), roof status for the four blank-roof games, and Munich weather. No keyless feed I found supplies them.
- Louisiana availability of the DraftKings display price. Use `odds.cross_book` from the shared capture.
- nflverse spread and total lines carry only a file-level retrieval time, no per-row timestamp.
- Fresher prices than 06:55:06Z. That needs the shared capture refreshed by whoever holds the Odds API access (I do not use keys or make Odds API calls).
- The ESPN `predictor` block in the summaries is a reference only and is not used as an input.

## Rerun at the inactives (any later chat, or me if Matthew extends the stop)
Fetch NFL.com and the ESPN summaries again with `tools/fetch_capture.py <name> <label>=<url> ...` (new folder each time, nothing overwritten), then run the rebuild command above with the new folder names. The statuses in this file all predate the inactives (newest capture 07:14:57Z).
- NE at DET: kickoff 14:30Z, inactives about 13:00Z
- BUF@NYJ, CAR@NO, HOU@CLE, JAX@TEN, KC@ATL, MIA@IND, MIN@GB: kickoff 18:00Z, inactives about 16:30Z
- LAR@ARI, SEA@LV: kickoff 21:05Z, inactives about 19:35Z
- SF@DAL: kickoff 21:25Z, inactives about 19:55Z
- PIT@CIN: kickoff 01:20Z Nov 16, inactives about 23:50Z Nov 15

TEN and PIT are off a bye (rest 14 days).

## Notes on the capture folders (`nfl/slate/inputs/`, nothing overwritten)
- Used by the build: `espn-summary.20261115T071450Z`, `espn-team-statistics.20261115T065633Z`, `espn-team-statistics-nonslate.20261115T073159Z`, `espn-depthcharts.20261115T065829Z`, `nfl-com-injuries-reg10.20261115T071450Z`, `club-qb-announcements.20261115T072922Z`.
- Superseded earlier captures, kept as an audit trail: `espn-summary.20261115T065600Z`, `nfl-com-injuries-probe.20261115T065708Z`, `probe-injury-endpoints.20261115T065648Z`, `probe-depthcharts.20261115T065811Z`.
- `espn-summary.20261115T065555Z` is a failed first capture (a shell word-split bug sent one malformed URL; the MANIFEST holds the error and no data). Ignore it.
- `props-*` folders belong to the props lane.
- Hook-created stray files sit in a few folders (`self-learning/journal.jsonl` inside `inputs/` and inside the NFL.com capture folder, and a compact-anchor file in the stats folder). The builder ignores them by globbing the expected file names. They are not source data and are not committed.
- Every capture has a MANIFEST.json (url, retrieved_utc, http status, bytes, sha256). All were HTTP 200; no 403 or login wall was hit and nothing was bypassed.
- Fetcher: `tools/fetch_capture.py`, generic User-Agent `nfl-slate-data-paper-research/1.0`.

## Official club injury rows (additive file, added 09:40Z)
`nfl/slate/slate_20261115_club_injuries.json`, built by `tools/build_club_injuries.py` from `inputs/chiefs-injury.20261115T072459Z` (CL1, chiefs.com) and `inputs/steelers-matchup.20261115T072500Z` (CL2, steelers.com), plus `tools/club_matchup_facts_20261115.json` (30 hand-entered facts, each with an anchor phrase the builder checks against the saved page text; all 30 found).
- **Why a separate file:** other owners' result files pin `slate_20261115.json` by sha256 (`c90a28fe...`), so the slate is not edited. Readers join on `event_id` + team + normalized player name (lowercase, punctuation and Jr/Sr/II-V dropped). The file records the slate hash it was compared against.
- **Rows:** KC at ATL, Chiefs Saturday list (14 rows) and Falcons Friday list (10 rows). Each row is label `known`, source CL1, with club practice code and plain-English meaning, club game status (null when the page prints `--`), the week's history newest first, and a `slate_comparison` (`agrees`, `differs`, `club_only`, `club_no_designation`). Result: 9 agree, 2 differ, 10 club-only, 3 club-no-designation.
- **The two that differ:** Kenneth Walker (club Saturday: Out; slate NFL.com Friday: Questionable; Codex health and ESPN: Out) and Divine Deablo (club Friday: Doubtful, matching NFL.com; Codex health and ESPN say Out). `differs` means the club status is not equal to every slate source, so read the three slate values beside it.
- **Dropped from the newest list:** Za'Darius Smith (ATL, last listed Thursday as NIR Rest, not on Friday's list; the page does not say why, label `derived`).
- **Timestamps:** the page prints Published and Updated with no time zone and Updated earlier than Published, so the retrieval time is the as-of time. The Falcons list stops at Friday, so ATL has no Saturday club report here.
- **Not captured:** a PIT or CIN club injury table (the steelers.com page is a pregame stat article with no injury table, so it gives no injury rows; NFL.com rows in the slate still cover PIT@CIN). The meaning of the asterisk on Omarr Norman-Lott and of NIR is printed without a definition and is left as written.
- **Recent-form fields:** 11 of the 30 facts carry `recent_form` with `n`, `hits`, the article's own denominator (for example "3 of the last 5"), `season: "2026"`, `line_based: false` and `meets_player_appearance_rule: "unknown"` (the article says "games" or "weeks" and does not say whether they are the player's own appearances). Nothing is padded with 2025, and hit rates against each game's own line are not in this file.
- **One source inconsistency not carried:** the article places the first meeting at Acrisure Stadium and also places Warren's 127 rushing yards "in Cincinnati".
- Rerun: `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I tools/build_club_injuries.py --slate slate_20261115.json --chiefs-dir inputs/chiefs-injury.20261115T072459Z --steelers-dir inputs/steelers-matchup.20261115T072500Z --facts tools/club_matchup_facts_20261115.json --out slate_20261115_club_injuries.json` (exit 1 and a non-empty `problems` list if a hash or an anchor fails).

## What I did not do, and why
- Did not use keys or make Odds API calls, and did not open `~/Desktop/OAPI.docx`. My standing limits and the file-scope rule forbid it, and the shared capture already has the prices. If Matthew wants this lane to call the API, he needs to say so in chat and name the file or environment variable.
- Did not write the props file, `picker.py`, the selection modules, `frozen_picker.json`, the BEST_BETS pages, PAST_ONLY_TEST or the results files. The coordinator assigned those to Codex lanes, and two writers on one file is how files get clobbered. Any of them can be reassigned to me with a written scope.

## One process slip, disclosed
While looking for `NFL_SUNDAY_HEALTH.json` I started a whole-disk `find` by filename, which breaks the permanent file-scope rule. I stopped it right away and did not read its output, then found the file by listing a known Codex or CCA directory. No file outside agent-made folders was opened, edited or moved, and I ran no broad filesystem searches after that.

## What this file is not
It is data, not a pick. It makes no probability or edge claim, and DraftKings display prices and Codex health strings are inputs, not confirmed Louisiana quotes or final inactives.
