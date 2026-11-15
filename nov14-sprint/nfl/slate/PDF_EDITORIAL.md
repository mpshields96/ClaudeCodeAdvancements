# Editorial pass on the Sunday NFL brief

Written by Claude coordinator local_50238c87 at about 07:25Z on 2026-11-15. It goes to the generator owner, Codex 01a1de0b, which is the only PDF writer. Claude does not write `pdf_export/`.

What I checked:

- `pdf_export/evidence/2026-11-15.json`, the card with sha `96d09884…`;
- `results/sunday_20261115_selections.json`;
- the 06:55:06Z capture;
- `nfl/data/raw/games.csv`;
- Warren's nfl.com game log, retrieved 07:09Z;
- `experiment/journal.py`, run against a scratch copy.

Nothing here is a bet recommendation.

**Corrected at about 07:30Z**, after Matthew's clarification, relayed by Codex: "when I mentioned last 5 games or last 10 games I was referring to player props mainly and consecutive games like this season."

- Last 5 and last 10 mean the player's consecutive games in the current season.
- When he has played fewer than 10, show how many there are.
- Never pad with last season.
- Team last-5 and last-10 are optional, not required.

The earlier version of this file suggested a team last-10 that crossed into 2025. That suggestion is withdrawn.

## Must fix before print

1. **The KC model number disagrees between files.**
   - The brief says "The scoring model puts Kansas City at 56.3% to win."
   - `selections.json` has `model_estimate` 0.6024.
   - Print one number and name its source field. Both are below the 62.4% break-even at −166, so the sentence that it "falls short of the price" holds either way.
2. **The KC market probability has two values.**
   - The brief and the journal say 60.9%, described as a five-book midpoint.
   - `selections.json` `market_probability` says 61.16%. Its risk text says 60.9%.
   - Use one method across the card, the selections file and the journal, and label it.
3. **The Warren market note leaves out the main fact.** BetMGM's 22.5 is the lowest line of the five books. The others had 23.5 at DraftKings, 25.5 at FanDuel and theScore Bet, and 27.5 at BetRivers.
   - BetMGM priced both sides at −115, so the 50.0% no-vig figure is real for that one book.
   - It ignores that the other books put Warren's middle 1 to 5 yards higher. The "−6.5% per unit" value probably understates the over at 22.5.
   - Print the value as "unknown, line shop only", not as a number and not as an edge.
4. **"Cincinnati allows 135.3 yards after the catch per game" needs its source on the card.** The source is now captured: steelers.com "Matt's Stats: Week 10 at Bengals", retrieved 07:25:00Z, saved in `inputs/steelers-matchup.20261115T072500Z/`. Cite it as a season-to-date figure "per steelers.com". The page doesn't give a game count, so don't invent one. The same page has the "since Dowdle returned" role figures: 65% of snaps, 46% of routes, 10% of targets. It doesn't say how many games that covers, so label those figures "games since Dowdle's return, count not given".
5. **The injury lines need a source and a time.** The source is now captured: the chiefs.com Week 10 injury report, Saturday entries, retrieved 07:24:59Z, saved in `inputs/chiefs-injury.20261115T072459Z/`. It lists:
   - Kenneth Walker, groin, did not practise, **Out**;
   - Jaylon Moore, ankle, did not practise, **Out**.

   - Patrick Mahomes is also on that report, listed knee and right elbow. He practised fully every day and has no game status. Don't call him "injury-free". Write "listed (knee, right elbow), full practice, no game status".

   Print it as "Walker and Moore out, per chiefs.com Saturday report, retrieved 07:25Z". Statuses can still change, and final inactives come about 90 minutes before kickoff:
   - 16:30Z for the 18:00Z KC game;
   - 23:50Z for the 01:20Z Steelers game.
   - The "keep the pick only if…" conditions are good. Each one must be checkable against the inactives list.

## Correct as written (checked against the data)

| Claim | Check | Note for print |
|---|---|---|
| KC 6 of 8 this season, 3 of last 5 | games.csv, 2026 games | Optional team context; add "(2026, n=8)". |
| ATL 3 of 9, 1 of last 5 | games.csv | Optional team context; add "(n=9)". |
| "Neither has played 10" | true within 2026 | Keep this wording. A team last-10 is not required. Do not pad it with 2025 games. |
| KC allows 17.9 per game, ATL 24.8 | games.csv: KC 25.2 for and 17.9 against (n=8), ATL 20.9 and 24.8 (n=9) | add the n |
| KC won the last meeting 22–17 in 2024 | true, 2024-09-22 | Label it "different rosters, not evidence". It is the only meeting since 2024, and there have been 7 since 2012. |
| Warren over 22.5: 4 of his last 5 and 7 of 8 available | nfl.com log, last 5 newest first: 0, 36, 28, 87, 33 | **This is the main last-5/last-10 figure for the brief.** These are his consecutive 2026 games, measured against today's 22.5 line. He has 8 games, not 10, so print "7 of 8 (2026, all games available)". The 0 came in his latest game, after the role change. |
| "6 of 8 over the actual prior lines" | separate measure | Keep it apart from the 7 of 8 above. It uses each game's own posted line, and the book and time are unverified. Label it that way or cut it. |
| Warren 3 for 49 against CIN, Week 3 | 2026-09-27 | one game, n=1 |
| Counterpoint: since Dowdle returned, Warren is 1 of 3 against his own lines | from nfl-picker's `FOOTBALL_RED_TEAM.md`, 07:31Z: 28 vs 28.5, 36 vs 25.5, 0 vs 22.5. Prior lines are from statsniper via `candidates.json`; books and times are unverified. | Put it in "what could undo it". The weeks 6–8 span is inferred from the logs, so label it "inferred". n=3. |

## Standard for every future brief

- **Last 5 and last 10.** These mean the player's consecutive games in the current season, measured against today's line. A player prop always shows them.
  - With fewer than 10 games, show what exists, for example "7 of 8".
  - Never pad with last season.
  - Keep a hit rate against each game's own historical line as a separate figure.
  - Team last-5 and last-10 are optional.
- **Denominators.** Every rate carries its n and its season span. A split after a role change gets its own n. Don't mix a full-season rate with the current role without saying so.
- **Head-to-head.** Show it only with its year and the label "different rosters" when it's older than the current season. It never supports a pick on its own.
- **Neutral site.** NE at DET in Munich is not a home game for either team. Home/away splits do not apply.
- **Game script** is stated as a condition tied to the posted spread and total at the quote time, for example "if Atlanta leads early…". It is never a forecast.
- **"AI edge"** means what the model adds beyond the price. Here the past-only test gave the market full weight, and the model sits below break-even on KC. Say plainly: "The model does not beat this price." No edge is shown on either call.
- **Bet value** is defined once: estimated value per unit at the quoted price, against the margin-free market chance. It is marked "information only". Show it as negative when it's negative, and "unknown" when only one line exists.
- **Quote time.** Show it on every price, captured 06:55Z here, with "re-check price and inactives about 90 minutes before kickoff". A quote is not a ticket.
- **Local availability.** `local_availability_verified` is false on both calls, so print "Louisiana availability not verified".
- **The pass belongs on the card.** The late-window pass and its reason are already there.
- **Length.** One page.
- **One source.** Every number in the brief should come from one generated source: the journal, or `selections.json`, not both. Items 1 and 2 above happened because they don't.

## Top-5 watchlist (added about 07:38Z)

Matthew's direct addition, relayed by Codex: "a list of Top 5 bets that most accurately meet our edge and criteria even if we don't formally say yes. Doesn't need writeups for these, just to know viable and more volatile picks".

- **Source.** The only source is `results/sunday_20261115_watchlist.json`, written by Codex 7d2e. The PDF reads it and builds no second ranking. The file didn't exist at 07:37Z.
- **Formal calls are unchanged.** The two formal calls stay as they are. Each row says plainly whether it is a "formal call" or "watchlist only, not a recommendation, no ticket".
- **One line per row.** Each row is a single line with:
  - rank;
  - exact contract: player's full name and team, market, period, side and line;
  - book, price and quote time;
  - kickoff in CT and window;
  - volatility;
  - risk tag.
- **No write-ups.** A row gets at most one short fit note.
- **Ranking method.** Print the method in one line. The ranking is not an edge claim.
- **Value.** Any value number is "information only". It is shown negative when it is negative, and as "unknown" when only one book prices it.
- **Same checks as the calls:**
  - band −200 to +200;
  - quote before kickoff;
  - full-name match, so Jaylen Warren and Tyler Warren stay apart;
  - first half kept apart from full game;
  - home and away team totals kept apart;
  - neutral site handled correctly.
- **Reviewer.** nfl-props reviews each row in `redteam/WATCHLIST_REVIEW.md`.

## Matched-role control (release owner's file, read-only)

The frozen control in `Matched_Role_Control.json` is Jonathan Taylor over 21.5 receiving yards, BetMGM −115, MIA at IND, 18:00Z. It matches Warren on:

- market;
- price;
- book.

It doesn't match Warren on:

- **The line.** 21.5 is the common Taylor line: BetMGM, FanDuel and BetRivers all had 21.5, against 23.5 at DraftKings and theScore Bet. Warren's 22.5 is below every other book. The control therefore holds the price fixed but not the line advantage.
- **The window.** Taylor is early (12:00 CT), Warren is night.

With n=1 on each side, Sunday's result cannot tell the two apart. Grade it as its own stream and make no claim from it.

## Journal check (scratch copy only, 07:23Z)

`experiment/journal.py` imports only the standard library, with no network code. The capture import gave 1,756 exact bets with 0 dropped. Importing the calls twice was idempotent: 2 new rows, then 0 new rows.

These gaps came up and were sent to nfl-lead at 07:25Z to fix with tests:

- An identical ticket was saved twice.
- A ticket at −250 was saved with no refusal or visible band flag.
- A ticket without `--placed-utc` was saved.
- There is only one `--price`, with no offered-versus-accepted split.

The real `experiment/data/` was not written by Claude.

## Final build review (09:39:54Z front door, re-read 09:45Z)

The 09:41:01Z front-door copy matches `NFL_Live` and `pdf_export` byte for byte (`cmp`).

- **Size:** 11,230 bytes, one page, sha256 prefix `0d89417e`.
- **Superseded build:** the 09:38:54Z one (`9bc9832f`).

**The page matches the final refresh** (09:35:13Z, 2 credits, run by Codex 01a1de30):

- **KC moneyline:** −166 · DraftKings 3:35 am CT, limit −166, $6.02 net per $10, break-even 62.4%.
- **Warren over 22.5:** −115 · BetMGM 3:35 am CT, limit −115, $8.70, break-even 53.5%.

**What was corrected since 07:38Z:**

- **KC model figure:** 60.2%, which matches the selections.
- **Bowers row:** now "QB change / recheck inactives". The page says Mendoza replaces Cousins, and "First-start" is gone.
- **Warren row:** now "PIT inactives / shared targets". It names Freiermuth (illness) and Harmon (foot).

**Still true:**

- "Louisiana availability is unverified", "No ticket recorded" and the closing-line disclaimer are all on the page.
- Watchlist rows 3 to 5 carry their earlier saved quotes.
- Matthew re-checks the price and inactives about 90 minutes before each kickoff.

No editorial change is owed. Red-team detail is in `nov14-sprint/nfl/RED_TEAM.md`.
