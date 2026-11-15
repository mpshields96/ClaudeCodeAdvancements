# replacements/ interface (frozen keys, v1)

The dated assessment uses source files that accompany each game. Claude built the producer and gathered the public sources. Codex completed the two real inputs and independently checked the released output. The default 2026-11-15 spec screens Kansas City and Green Bay across the saved twelve-game slate. Other teams without supplied records remain unassessed.

## Files and exact paths (all under `nov14-sprint/nfl/slate/replacements/`)

| File | What |
|---|---|
| `replacement_report_20261115.json` | versioned report, `schema_version` = `replacement_report/1`. Engine and PDF read this. |
| `next_man_up.py` | stdlib, Python 3.9 safe. `screen_slate(spec) -> report` (any slate, any teams), `screen_team_block(team)`, `replacement_context(report, team=None, player=None, event_id=None) -> dict`. CLI: `python3 -I next_man_up.py <spec.json> <report.json>`. |
| `cases/*.spec.json` | inputs for one slate: the feed paths, the dated availability records, the saved pages. KC and GB are the first two. |
| `KC_SNAPSHOT_20261115.md` | human read of the KC case |
| `tests/` | `python3 -I -m unittest discover -s tests` from this folder |

## Report top level keys

`schema_version`, `report_id`, `built_utc`, `as_of_utc` (latest source time used; nothing later is read), `paper_only` (true), `inputs` (path, sha256, captured_utc per file), `rules` (thresholds and the no-double-count text), `by_event`, `unscreened_events`, `unknowns`.

## `by_event`

`by_event[event_id]` has `event` (`event_id`, `away_team`, `home_team`, `commence_utc`) and `teams`; `teams[team_name]` has:

| Key | Meaning |
|---|---|
| `screen_status` | `screened` (a dated absence record exists), `unknown_absence` (no dated availability record supplied for this team: no conclusion), `unknown_next_man` (absence known, nobody identified as next man) |
| `team_context` | `{label, built_from, rush_att_pg, rush_ypc, opp_allowed_ypc, points_pg, ex_starter_rush: {att, yds, ypc}}`, season baselines only. These do not describe the replacement's efficiency. |
| `priced_environment` | `{label, spread, total, implied_points, captured_utc, book_range}` the posted post-news scoring environment. It is **not** evidence of a preserved offence. |
| `marginal_effect_of_absence` | `{vs_pre_news: "unknown" or number, needs: "pre-news spread/total/lines"}` stays `unknown` unless a pre-news counterfactual is supplied |
| `absences` | list of `{player, status, label, source: {url, published_utc, modified_utc, retrieved_utc}}` |
| `starter` | `{player, history_2026, ...}` the absent starter's own 2026 usage and efficiency |
| `candidates` | list of next men, keys below |
| `replacement_context` | the engine object (below) |

## candidate keys

`player`, `position`, `availability` (`status`, `label`, `source`), `role_evidence` (each `{id, kind: "hard"|"interpretation", text, source, label}`), `history_2026` (`appearances`, `carries`, `yards`, `ypc`, `carries_pg`, `max_carries`, `receptions`, `rec_yards`, `sample_note`, `source`), `market` (`label` K or U, `stats` with `rush_yds`, `rush_attempts`, `rec_yds`; each has `books[]` of `{book, line, over, under, no_vig_over, hold, last_update_utc, same_line_both_sides}`, `line_min`, `line_max`, `line_median`, `captured_utc`, `threshold_note`), `components` (`workload`, `efficiency`, `team_expectation`, `receiving`, each `{label: weaker|preserved|stronger|unknown, confidence, basis, value_label: K|E|U}`), `vs_starter` (weaker, preserved, stronger, mixed or unknown), `priced_status` (`priced_in`, `partly_priced`, `possibly_unpriced`, `no_market`, `unknown`), `evidence`, `counterevidence`, `freshness`, `unknowns`.

A market line is a threshold. Each exact line and its available two-sided prices determine its no-vig probability. It is **not** a mean forecast. Hard evidence (dated availability, usage, posted prices) and interpretation (offensive fit, opponent front or coverage, plausible lead or trail and passing downs, a reporter's read of a depth chart) are separate lists and never merged into one number.

## `replacement_context` (the object for `call.replacement_context`; the engine owns normalization)

```
{
  "schema_version": "replacement_context/1",
  "event_id": "...", "team": "...", "built_utc": "...", "as_of_utc": "...",
  "absent": [{"player": "...", "status": "out", "source_published_utc": "..."}],
  "next_men": [{"player": "...", "vs_starter": "...", "priced_status": "...", "has_market": true, "role_claim_kind": "hard|interpretation|none"}],
  "vs_starter": "weaker|preserved|stronger|mixed|unknown",
  "priced_status": "priced_in|partly_priced|possibly_unpriced|no_market|unknown",
  "flag": "qualify|info|unscreened",
  "qualifier": "one sentence the PDF may print",
  "confidence": "low|medium|high",
  "win_probability_adjustment": null,
  "auto_upgrade": false,
  "reorders_issued_calls": false,
  "no_double_count": "posted prices already contain the availability news; nothing here adjusts a price or a win probability",
  "report": "replacements/replacement_report_20261115.json"
}
```

`flag`: `qualify` means print the qualifier next to any call on a listed player or on that team's rushing, receiving or game-total markets; `info` means screened with no qualifier needed; `unscreened` means no availability record was supplied for the team (unknown, not "no absence"). `win_probability_adjustment` is always null and `auto_upgrade` and `reorders_issued_calls` are always false: the screen never changes a call, an order, or a probability.

## Labels

Every value carries **K** (known/sourced, with source and retrieval time), **E** (estimated, computed from K values with the arithmetic named), or **U** (unknown/missing, never filled from memory). Times are UTC.

## Reproduce the November 15 source report

From this folder, run the following command with the dated evidence files available. Use a scratch output when reproducing a previously issued report. The build timestamp records the actual new review time.

```sh
/usr/bin/python3 -IB next_man_up.py cases/sunday_20261115.spec.json /tmp/replacement_report_rebuilt.json
```

Each team's input identifies its own offensive group and opponent. For another slate, supply its captured game list, exact event odds, dated starter availability, eligible replacements, observed role evidence and same-season logs. A listed backup with a later ruled-out designation is excluded from the active role. Questionable personnel remain conditional. A missing replacement produces a hold for that matchup on the weekly provisional shortlist. When no dated personnel inputs exist, the game shows unknown coverage. The producer reads supplied evidence offline. It does not collect breaking news.

The `priced_in` family of labels describes how a posted player threshold compares with his own recorded usage under a stated role change. It does not measure market accuracy. Even across comparable dated team prices, a change is an observation and can reflect other news. The review makes no quantitative adjustment to the team's win probability.
