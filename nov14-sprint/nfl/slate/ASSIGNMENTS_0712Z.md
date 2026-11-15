# NFL roster and file ownership, corrected 07:14Z Sunday Nov 15

**This replaces the 07:12Z draft of this file.** The draft made nfl-picker the engine writer after a handback. That is withdrawn.

**Source.** A Codex relay pasted into the Claude coordinator chat at about 07:13Z. It was posted by the prior supervisor <codex-thread> on behalf of the current technical supervisor <codex-thread>. It is an agent relay; Matthew may not have typed it. It narrows ownership and grants no new permission.

**The hard stop is 08:59:53 UTC.** Every limit in BRIEF.md still applies:

- paper only;
- no keys;
- never read ~/Desktop/OAPI.docx;
- no Odds API calls;
- no installs or pushes;
- touch only files that Claude or Codex made.

**Corrected at 07:41Z.** The old blanket "no commits" line is withdrawn. See "Finish the work" below.

## Finish the work (Matthew, direct, relayed by Codex at about 07:40Z)

> "And would you mind being the chat to tell Claude chats don't wrap up their work by saying "didn't do these things and not touching this" if there's a viable appropriate reason they can finish things so that we're not missing stuff then I want them to do that. Like one chat wasn't touching picker.py or committing like just go do those things you know? That goes across the board as a sentiment for all chats"

He then clarified: "The picker.py was just an example mind you."

This is a general rule about finishing work. It doesn't order anyone to edit a particular file or to commit.

- **Don't close a unit with "didn't do X" or "not touching Y"** when there is a viable, appropriate way to finish it. Finish the work, verify it, and close with what Matthew can use. Name something as not done only when a genuine blocker stops it.
- **Someone else's file.** One writer per file still holds while that writer is active. "Not my file" is not, on its own, a reason to stop.
  - Send the owner the exact change with a repro, through the coordinator for Codex owners. Then check that the change landed.
  - If the owner has finished, gone idle or can't be reached, and the change is in scope, ask the coordinator to hand ownership over. Once it does, make the change yourself.
- **Local commits are allowed** when a verified, completed unit makes one appropriate. Commit only your own files:
  - `git commit -m "<msg>" -- <explicit paths>`;
  - never `git add -A`, `git add .` or `commit -a`;
  - never commit another owner's files, or legacy dirty files such as `pokemon-agent/*.sav`, `self-learning/journal.jsonl`, `session_timings.jsonl` or `.claude/settings*`;
  - no stash, reset, rebase or branch switch;
  - if `.git/index.lock` exists, wait and retry once, and never delete it.
- **Genuine blockers:**
  - a hard limit below;
  - another writer actively mid-edit;
  - the 08:59:53Z hard stop;
  - data that can't be had from public keyless sources.
- **Still not authorized:**
  - pushes;
  - bets or tickets;
  - accounts or sign-ins;
  - keys or credentials;
  - paid data;
  - Odds API calls, `odds_feed`, `sunday_quotes` and `full_snapshot`.

## One writer per file

| Owner | Writes | Never writes |
|---|---|---|
| **Codex <codex-thread>**, the engine author | The sole writer, for this release, of `picker.py`, `selection_markets.py`, `selection_decisions.py`, the frozen selection, the results files and the result pages. It is staging privately until the coordinator ACKs. | |
| **Codex <codex-thread>**, the release owner | The final overlay `Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/Final_Decisions.json`, already supplied (07:09Z, 2,495 bytes) | engine files |
| **Codex <codex-thread>**, the technical supervisor | Technical integration and UI. Codex <codex-thread> has handed UI over. | |
| **Codex <codex-thread>**, the data worker | `props_20261115.json` | |
| **nfl-picker** (Claude, local_<session>) | `FOOTBALL_RED_TEAM.md` and the independent football and selection review. Its read-only repro tests go in `nfl/slate/redteam/`. | the engine files listed above, the overlay, inputs |
| **nfl-lead** (Claude, local_<session>) | The experiment and workflow, in its own files: hypothesis register, candidate-pool log, Matthew's challenge log, ticket log, and grading against controls | the engine files, the overlay |
| **nfl-slate-data** (Claude, local_<session>) | the team JSON `slate_20261115.json`, per INPUT_HANDOFF.md | props JSON, engine files |
| **nfl-props** (Claude, local_<session>) | `DISSENT_PREGAME.md` and `.json`, the pregame football and fantasy dissent | props JSON, engine files |
| **bot-advisor** (Claude, local_<session>) | `advisor/NFL_REVIEW.md`, a read-only review with repros | any code |
| **Claude coordinator** (local_<session>) | This roster, red-team acceptance and Claude worker coordination | engine files |

Nobody merges into, overwrites or reverts `picker.py` or the two selection modules except Codex 7d2e. A finding goes to the coordinator as a repro. The coordinator relays it to 7d2e and <codex-thread> and checks that the fix landed, so it isn't left as an open "not touching".

## Engine state seen at 07:13Z, observed only, not accepted

- `picker.py` is 42,499 bytes, sha prefix `bc6f909563c1fb52`. It was 61,222 bytes at sha `21334698…` at 06:51Z.
- `selection_markets.key_for` builds the id from event, period, market, subject, side and line, so the subject should carry the player. That should end the prop-ID collision the advisor reproduced on the old engine at lines 708 and 768.
- **No test covers it yet.** It is not accepted.
- A grep found no import of `odds_feed`, `urllib.request`, `http.client` or `socket` in the three engine files. `BASE_URL` is only a provenance string.

## Assignments and due times

### nfl-picker: due 07:45Z

Write `FOOTBALL_RED_TEAM.md` and the read-only repros in `nfl/slate/redteam/test_engine_ids.py`. That file is stdlib unittest and imports the engine modules without editing them. Repro each case, then report pass or fail:

- Two players on the same game, market, side and line get distinct ids.
- `totals` against `totals_h1` on the same line get distinct ids.
- Home against away `team_totals` get distinct ids.
- Never both sides of one proposition.
- Nothing outside −200 to +200.
- At most 2 per window, from different games.
- A quote after kickoff is refused.

It also covers the football review of each call: matchup, health and role.

### nfl-lead: first tests due 07:40Z

The workflow covers:

- the hypothesis register, refused after kickoff;
- the pool snapshot with passes and pass reasons;
- Matthew's append-only challenge log, which never edits a call;
- the ticket log, kept apart from calls, recording offered and accepted price;
- grading against the price-matched control and the closing price, with Wilson intervals and no profit claim.

### nfl-slate-data: due 07:45Z

The team JSON for all 12 games. Every injury row is labelled known, estimated or unknown, with its source and time.

### nfl-props: due 08:00Z

The dissent covers role, target or route change after an injury, QB change, weather and roof, pace, and matchup. Every claim carries a source and time, or the label unknown. It also gives 1 or 2 falsifiable hypotheses for nfl-lead to register before 14:30Z.

### Red-team acceptance, coordinator: due 08:40Z

It covers:

- **failure cases:** id collisions, both sides, stale quotes, out of band, a missing book, push lines, h1 against full-game, the neutral site, and a run after kickoff;
- **paper against real offered and accepted odds:** the 06:55Z capture price is not an offered or accepted price, each call carries a minimum price, and the ticket log keeps the real one;
- **pregame dissent.**

A failure is reported as a failure, never relabelled. Trading gets its red team separately, later.
