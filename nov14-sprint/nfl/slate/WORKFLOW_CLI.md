# NFL Sunday workflow: command contract for the launcher

Claude coordinator local_<session>, 2026-11-15 07:22Z. **Workflow owner: nfl-lead** (Claude, local_<session>), who writes `nfl/slate/workflow.py` and `nfl/slate/tests/test_workflow.py`. Engine files stay Codex 7d2e's; this tool only reads them.

The hard stop is 08:59:53Z. Paper only. No network, no `odds_feed`, no `sunday_quotes` refresh. The tool uses stdlib only, runs under Python 3.9 with `-I`, and doesn't use `X | Y` types.

## 1. What runs now (verified 07:20Z on a scratch ledger)

`nfl/paper_ledger.py` (nfl-lead's, existing) already records a ticket and a closing price. A probe into a scratch `--ledger-dir` accepted three takes:

- KC ML −166 at DraftKings;
- a prop: Warren receiving yards over 22.5, −115 at BetMGM;
- +180 at FanDuel, recorded with `price_in_band=false`.

```
python3 -I nov14-sprint/nfl/paper_ledger.py add --game-id 2026_10_KC_ATL --rule MANUAL-SUN-TICKET \
  --action take --market moneyline --side away --price -166 --quote-ts 2026-11-15T06:55:04Z \
  --source draftkings --stake 1 --reason "accepted terms as shown on the ticket"
python3 -I nov14-sprint/nfl/paper_ledger.py add --game-id 2026_10_PIT_CIN --rule MANUAL-SUN-TICKET \
  --action take --market prop --side over --line 22.5 --selection "Jaylen Warren receiving yards" \
  --price -115 --quote-ts <UTC> --source betmgm --reason "..."
python3 -I nov14-sprint/nfl/paper_ledger.py close --pick-id <id> --price <American> --source <book> --quote-ts <UTC> [--line X] [--not-a-close]
python3 -I nov14-sprint/nfl/paper_ledger.py settle --results-file <scores> --results-ts <UTC>
python3 -I nov14-sprint/nfl/paper_ledger.py settle-manual --pick-id <id> --outcome win|loss|push --result-source <src>
python3 -I nov14-sprint/nfl/paper_ledger.py status
```

These are the ledger's limits, and `workflow.py` must fix them:

- **The band is wrong for Sunday.** The ledger uses −170 to +150 and only flags a price outside it. Sunday's band is −200 to +200 inclusive. A pick outside it is still recorded, with `price_in_band=false`.
- **Some markets are missing.** It has no first-half markets and no team totals. Its markets are spread, total, moneyline and prop only.
- **It has one `--price`.** It can't keep the offered and accepted prices apart, and it doesn't link to the engine call id.
- **Quote time is self-reported.** It is refused as STALE_LINE when older than 12 hours.

## 2. SUPERSEDED at 07:25Z: `experiment/journal.py` is the single ledger

A Codex relay at about 07:24Z set this. nfl-lead's existing `nfl/slate/experiment/journal.py` (1,758 lines), with its `data/` folder, is the **only production ledger**. Codex <codex-thread> wires it into `Open Sunday NFL.command`. There is no `workflow_log/` and no second system. A `workflow.py`, if one exists at all, only calls this journal.

The table below is kept as a list of the behaviours the journal must have.

What runs now, probed on a scratch `--data` at 07:23Z:

```
journal.py [--data DIR] import-capture PATH
journal.py [--data DIR] import-calls PATH [--late]
journal.py [--data DIR] add --event --market --side --price --book [--subject --point --quote-utc --note]
journal.py [--data DIR] list [words] [--calls --window early|late|night --band --all --limit N]
journal.py [--data DIR] show ID
journal.py [--data DIR] hypothesis --text [--event ...] [--id ...] [--by] [--late]
journal.py [--data DIR] decide ID take|pass|alternative --reason [--alt --hypothesis --price --book --by --revise --late]
journal.py [--data DIR] ticket ID --book --price --stake [--unit --point --placed-utc --note]
journal.py [--data DIR] final EVENT --home --away [--h1-home --h1-away] --source
journal.py [--data DIR] player-result EVENT --player --market --value --source
journal.py [--data DIR] void ID --reason --source
journal.py [--data DIR] import-finals PATH | import-close PATH | report [--out] | grade | verify | status | form
```

Exit codes: 0 is ok. 1 is "Refused: …", and also a verify failure. 2 means import-calls refused a call, or an argparse error.

Gaps sent to nfl-lead at 07:25Z, each to be fixed with a test:

- A ticket has no offered-versus-accepted split.
- `--placed-utc` is optional.
- Duplicate tickets are accepted.
- An out-of-band ticket is not flagged.
- There are no per-control grade streams, so the matched-role control from `Matched_Role_Control.json` has none.
- Late human entries are not flagged visibly in grade.
- Quote age is not shown against the clock.
- Blinded comparator rows are missing.

### Original planned contract, now only a behaviour list

Run it as `python3 -I nov14-sprint/nfl/slate/workflow.py <command> [--json]`.

- Exit 0 means ok. Exit 2 means refused, with `REFUSED CODE: detail` on stderr.
- Logs are append-only JSONL in `nov14-sprint/nfl/slate/workflow_log/`. Each row carries `utc`, `sha256` of the row, and `prev_sha256`.

The call id is `calls[].id` in `results/sunday_20261115_selections.json`, which has the form `event:period:market:subject:side:line`.

| Command | Arguments | Rule |
|---|---|---|
| `view` | `[--selections results/sunday_20261115_selections.json] [--candidates results/sunday_20261115_candidates.json]` | Read-only pregame view per window: calls and passes, book, price, `minimum_price`, quote UTC and age, kickoff in CT, condition, health label. It refuses to show a call without a quote time. |
| `hypothesis add` | `--id --rule --falsifier --control --events <event ids>` | Refused once any listed event has kicked off. Pre-register the top-2 ML lead before 14:30Z. |
| `hypothesis list` | | |
| `pool` | `--candidates PATH` | Snapshots every candidate and pass with its pass reason and the file's sha256. |
| `challenge` | `--call-id --view agree\|disagree\|pass --reason [--revises ROW_ID]` | Matthew's own view, append-only, before kickoff. It never edits a call. A revision is a new row pointing at the old one. |
| `ticket` | `--call-id --book --offered-price --accepted-price --stake --placed-utc [--line X]` | **A ticket is never a call.** It is refused if `--placed-utc` is at or after kickoff. It flags, but does not refuse, an accepted price worse than `minimum_price`. Band −200 to +200 is checked on the accepted price. Stake is in paper units only. |
| `observe` | `--call-id --book --price [--line X] --quote-utc [--close]` | Line movement and CLV, for information only. It labels the earliest observation `earliest_observed`, never `opener`, unless the source says opener. |
| `comparator add` | `--handle --market --side [--line X] --price --book --posted-utc --observed-utc --source-ref` | See section 3. It is refused if `--posted-utc` is at or after kickoff, or if the price is missing. |
| `grade` | `--results PATH` | Grades calls, controls, tickets and comparators **separately**, reusing `rules.py` `grade` and `american_profit`. The control is the market favourite in the same window and price bucket. It reports Wilson 95% intervals and makes no profit claim. |
| `status` | | Counts per stream plus Wilson intervals. |

## 3. Comparator rule (relay at about 07:18Z, research figures via relay and not read by Claude)

The research reported in the relay:

- Rodeero_ went 26–12–1 on 39 priced NFL full-game sides and totals over 8 played Sundays, for +12.44 flat units. One Sunday was explicitly a no-play.
- mijese went 20–21–2, unpriced.
- The 60 gradable priced singles in nine sampled POTD threads lost 11.19 units. All six with retrospective votes of 25 or more lost.

The rules that follow from it:

- **No vote count or handle becomes a model weight.** Comparators never feed selection, ranking or the probability.
- **Register Rodeero_ only as a blinded prospective comparator.** That happens only if a public pregame call, with price and post time, is actually observed and frozen with `comparator add` before kickoff. "Blinded" means comparator rows are not shown in `view` and not used by anyone choosing Sunday's calls; they show up only in `grade` and `status`.
- **A Sunday with no observed call is recorded as missing**, never as a loss, a pass or a fabricated control row. An explicit public "no play" is recorded as `no_play` only when it was observed before kickoff.
- The handle was picked after its record was seen, so its past record is selection-biased. Only prospective rows count.
- Reddit returns 403 from this Mac. Claude doesn't bypass that, so Claude can't make the observation itself.

## Due

nfl-lead: `view`, `ticket` and `challenge` with tests by **07:55Z**. `hypothesis`, `observe`, `comparator` and `grade` follow by **08:25Z**. Each command reports pass or fail to the coordinator; nothing counts as accepted until its test passes.
