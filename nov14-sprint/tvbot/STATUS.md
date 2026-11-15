# TV bot lane: STATUS

Lane: TradingView bot (requirement R2, Matthew's words: "TradingView claude bot").
Owner: Claude, Fable 5.2, session `local_2bd925d2-76cb-4f1f-a6f9-b4880cded8fd`.
Written: 2026-11-14T22:29:07Z. Updated 2026-11-14T22:34:28Z for the coordinator's close-out (UTC times, what
changed since 22:12Z, what is not verified, the fresh reviewer's run). Last runs observed
2026-11-14 22:23Z to 22:33Z. Hard stop 23:02:00Z. Nothing is committed.
Updated 2026-11-15T05:25:36Z for Matthew's 04:41Z restart: the next section is new and is the current
state. Last runs observed 2026-11-15 05:19Z to 05:23Z. Still nothing committed.
Updated 2026-11-15T05:36:43Z for the advisor's four items (B4, A5, A1, D2): the next section is new and is
the newest state. Last runs observed 2026-11-15 05:31Z to 05:36Z. Still nothing committed.
Updated 2026-11-15T09:48Z for the 09:23Z window: the next section is new and is the newest state.
Last runs observed 2026-11-15 09:42Z to 09:43Z. The lane is committed locally in this window and is
not pushed: `git log --oneline -- nov14-sprint/tvbot` shows the commits, the first being `4945e65`. The "nothing committed" lines in
this file describe earlier times.
Added 2026-11-15T09:54Z: a pointer to the research lane's addendum, inside the 09:23Z section. No code changed.

## 09:23Z window, 2026-11-15: reconcile, three tidy-ups, local commit

This section is the newest state. Where any other section of this file disagrees with it, this
section wins.

A session alert at about 09:27Z opened a work window from 09:23:32Z to 11:23:32Z. Codex started the
alert and presents it as Matthew's instruction. It reached this chat as an agent relay. It asked
this lane to reconcile its paper-only deliverable with the parent, resume only work that was still
open, hand over and stay idle. A 09:40Z relay asked for a deliberate closeout toward about 10:40Z.
Limits are unchanged: paper only, no orders, accounts, keys, purchases, paid data, installs,
schedules or pushes.

### What the reconcile found

- The files matched the 05:36Z record. Between 05:37Z and 09:24Z the only changes were the
  coordinator's 06:40Z edits: `START_TONIGHT.md` section (b) and the last line of this file.
- Codex's source verdict (06:35Z, `nov14-sprint/codex/NOV15_SOURCE_VERDICT.md`): no source in the
  sprint evidence clears the full hourly SPY workflow. Twelve Data Basic is only a candidate for a
  private local evaluation. No signup is directed anywhere in this lane now.
- Codex's acceptance (`nov14-sprint/codex/NOV15_ACCEPTANCE.md`): "Accept the local paper demo and
  its refusal controls. Real hourly SPY operation is not accepted."
- The advisor's second pass (`nov14-sprint/advisor/PASS2_TRADING.md`): 18 PASS, 0 FAIL, 4 NOT YET.
  B2 and B5 need a cleared source and a real file. C4 was the phone copy of `START_TONIGHT.md`.
  B6 is scored in the NFL review and is not this lane's.
- Still open on this lane's side were the advisor's two tidy-ups and two points from Codex's B4
  review (`nov14-sprint/codex/NOV15_B4_CODEX.md`). All four are closed below.

### What changed in this window (each one written test-first)

1. **The cost table is on the result page.** `RESULT.html` has a table named "Same trades, every
   cost multiplied": net +270.30 at 0 times the cost settings, +227.88 at 1, +185.47 at 2,
   +100.63 at 4 and -69.03 at 8. The page says in words that at 8 times the costs the same trades
   end at a loss. The numbers are saved in `out/normal/summary.json` as `cost_sweep`, and
   `run.py sweep` prints the same five. The costs are settings. They were not measured from a
   market. Code: `bot/run.py` (`SWEEP_MULTS`, `cost_sweep`), `bot/page.py` (`cost_sweep_html`).
2. **A shorter file is refused.** Codex found that a file with fewer rows than the saved paper
   run, every row matching, was read without `--fresh`: zero new bars, the old 156 decisions kept,
   and a source report describing 141 bars. `paper` now stops before any bar is read with one
   line beginning `REAL FILE IS SHORTER THAN THE SAVED PAPER RUN`, exit 2, state unchanged.
   `paper --fresh` rebuilds from the file in hand. The same file run twice still needs no
   `--fresh`. Code: `bot/run.py` (`SHORTER_MESSAGE`, in `cmd_paper`).
3. **The page no longer pairs a refused file with the saved run.** The `paper` command converts a
   file before it can refuse it, so `real/last_source.json` can describe a file the saved run
   never read. The page now shows the source report the run itself saved, and says so in a red
   note when the newest converted file is a different one. Code: `bot/page.py` (`real_section`).
4. **`START_TONIGHT.md`** (09:43Z): a paragraph on the cost table and a refusal bullet for the
   shorter file. It still directs no signup and shows no key.

Tests added: 2 in `tests/test_real_feed.py`, and 3 for the page note plus the cost-table tests in
`tests/test_page.py`. Each new test was seen failing before its code change.

### Checks, observed 2026-11-15 09:42Z to 09:43Z, after the last code change

| Check | Result |
|---|---|
| Unit tests | 101 run, OK |
| `replay --fresh --expect` | exit 0. TEST ONLY. Expected ledger MATCH, 34 rows. Net +227.88 (before costs +270.30, spread and slippage -25.42, commission -17.00). Plan check 17 of 17. Result page rebuilt. |
| `adverse` | exit 0. 28 of 28 cases passed. |
| `sweep` | exit 0. +270.30, +227.88, +185.47, +100.63, -69.03. The 1-times figure equals the replay's net. |
| `paper --fresh --config config/smaller_size.json` | exit 2. `NO REAL SOURCE IS SET UP`. No bars read, no signal made. |
| `gate --show` | exit 0. Nothing recorded. |
| `check_review.py` | exit 0. PASS, 15 of 15 code checks. 49 numbers traced, 0 not traced. |
| `gate/` and `real/` | Neither exists. |
| `pine/emax_alerts.pine` | Unchanged, sha256 begins `a04cdd266f21096b`. |

The tests were run again at 09:47:27Z, after the document edits in this section: 101 run, OK.
A text check of `RESULT.html` at 09:48Z found all five tables, the new one included, inside the
page's side-scroll wrapper, and no outside links.

### After the checks

- Committed locally as `4945e65` at 09:49:02Z: 119 files, this lane's paths only. Not pushed. A
  small second commit holds the lines of this section, the handoff's last edits and the receipt
  below. `git log --oneline -- nov14-sprint/tvbot` lists both.
- The 09:43Z `START_TONIGHT.md` was sent to Matthew's device at about 09:49Z. That closes the
  advisor's C4.
- One review ask was queued to Codex at 09:49:47Z, for the two B4 points and a phone-width look
  at the page (`receipts/TO_CODEX_review_ask_20261115T094947Z.txt`). It is queued, not confirmed
  read. No reply had come when this was written.

### The research lane's addendum (read 09:51Z, this lane changed no code for it)

The reddit-research lane handed over its final files. Its addendum is in
`nov14-sprint/reddit/REAL_DATA_SOURCES.md` from line 227, written 05:35:29Z. It answers two
older lines in this file. Everything below is that lane's reading. This lane opened the
addendum and did not open the vendor's pages.

- **The key (D2, below).** The addendum says Twelve Data's documentation at
  `https://twelvedata.com/docs/introduction` lists a header method for the key and recommends
  it (addendum line 350 onward, read by that lane at 05:29Z). It also says the request was not
  run and no agent has a key (line 385), and that the docs do not say separately that the
  header works with a CSV reply. So the header form is documented and untested.
- **The terms quotes.** For Twelve Data, the addendum's quotes were read as the page's raw
  text, not through a summarising fetch (line 235). Its stated limit: it read the HTML as
  served, so text a page adds later by script would be missing (line 237). The older line in
  this file that says the research quotes came through a summarising fetch is replaced by this
  for Twelve Data only. The TradingView policy phrases in `RECONCILE.md` are a separate matter
  and still came through a summarising fetch.
- **No ruling changed.** The addendum says it makes no ruling. Codex's 06:35Z verdict stands:
  no source is cleared. `START_TONIGHT.md` still has no fetch command, no key and no signup
  step, and this lane did not add any. The header form matters only if a source is cleared
  later, and the fetch would be Matthew's step.

### Not verified

- The new cost table and the new red note were not looked at in a browser or at phone width.
  They reuse the page's existing table, scroll and note styles. The tests check the HTML text.
- No real file has been run. Every result is from made-up bars, and +227.88 on one synthetic
  sample is not evidence of an edge.
- No person has run `gate` or `paper` in Terminal. The gate is not approved, and approving it is
  Matthew's decision alone.

### Known limits still open

- A bar missing in the middle of a day inside one file is not detected.
- `paper --fresh` decides the whole file again from its first row. If a new file starts later
  than the old one, the earliest trades in the history can differ.
- The refusals for a shifted or a shorter file live in the `paper` command. The engine called
  directly, below the command, still accepts shifted rows.
- The durable bar-numbering repair is not built. Both reviewers accepted the refusal in its
  place. It matters only once a source is cleared.

### What is left, and whose it is

- **Matthew or a vendor:** a source that clears hourly SPY use (B2), then a first real file (B5).
- **Matthew:** the gate decision, typed in the Mac's Terminal. Steps are in `START_TONIGHT.md`.
- **The advisor (`nov14-sprint/advisor/ACCEPTANCE_RUBRIC.md`, its own file):** the draft short
  version for the phone is out of date. Its step 4 says to sign up for Twelve Data Basic and its
  step 5 shows `paper` without `--fresh`. `START_TONIGHT.md` is the current text.
- Nothing else is open in this lane.

## Advisor pass 1, 2026-11-15T05:27Z: four items closed

The advisor's rubric (`nov14-sprint/advisor/ACCEPTANCE_RUBRIC.md`) found one defect and three
gaps. The coordinator relayed them at 05:27Z with a 06:05Z deadline. This section was the newest
state at 05:36Z. The 09:23Z section above is newer and wins where the two differ. Where a later
section of this file disagrees with this one, this one wins.

### B4. A newly fetched file lost bars without a refusal (fixed at the `paper` command)

- The defect: `START_TONIGHT.md` said to fetch again on Monday and run `paper` again. The
  adapter numbers a file's rows from 1 every time (`bot/real_feed.py:241`), and the engine knows
  a bar by that number (`bot/engine.py:403-411`). When the vendor's 5000-row window slides, row 1
  of the new file is a different bar from row 1 of the old one. The engine then ignored every
  row whose number it had already stored, and the run still said the feed was accepted. The
  advisor's script shows it: 28 of 35 new bars read when the window slid by 7 rows, and 0 of 35
  when the new file had the same row count.
- The fix: `run.py paper` now compares the file with the saved run before it reads any bar
  (`refetch_conflicts`, `bot/run.py:1042`). If any row differs from the bar saved under the same
  number, it prints one line beginning `REAL FILE DOES NOT LINE UP WITH THE SAVED PAPER RUN`,
  exits 2 and leaves the saved run as it was. `paper --fresh` then rebuilds the paper run from
  the new file. A second check after the read refuses in the same way if a conflicting row is
  ever counted. `bot/engine.py` and `bot/real_feed.py` were not changed.
- `START_TONIGHT.md` now has `--fresh` in the `paper` command every time, and says why.
- Tests, in `tests/test_real_feed.py` (38 tests, was 35): the advisor's case 2 (window slid by
  7), case 3 (same row count) and case 1 (the file only grew, which still needs no `--fresh`).
  Each refusal test checks exit 2, exactly one line of output, no "accepted", every state file
  byte-identical, and then that `--fresh` reads every row of the new file.
- Red, then green: at 05:32:08Z the two refusal tests failed on a scratch copy holding the old
  `run.py` ("AssertionError: 0 != 2", 2 failures in 38). At 05:31:55Z and 05:35:27Z they passed
  on the live code.
- For pass 2: `advisor/repeat_run_check.py` calls the engine directly, below `run.py paper`. It
  still prints 28 and 0 after this fix, because the engine was not changed. The command Matthew
  types is covered by the three tests above.
- Not fixed, on purpose: the durable repair, which numbers each bar from its own open time. The
  engine treats a jump in that number as a data gap, so every night and weekend would become a
  gap until the engine also knows the session calendar. That is more than a safe edit tonight.
  Two limits follow. A bar missing from the middle of a day inside one file is still not
  detected. And a `--fresh` run on a file that starts later decides the history again from its
  new first row, so the earliest trades can differ from the previous run.
- Side effect of a refusal: the converted feed and its report inside `real/` are rewritten from
  the new file before the check runs. The saved paper run is not touched.

### A1. Why the expected ledger's hash changed

`fixtures/expected_normal_ledger.jsonl` went from sha256 `cc1b365708da1aba` to
`86ba83acc1ad29d8` when it was regenerated at 05:06:22Z, after the 05:03Z fill-plan fix in
`bot/engine.py`. Three fields changed, all on the 17 order rows:

- `min_fill_seq` is new. It holds the old meaning: the bar after the signal bar.
- `earliest_fill_open_expected` is new. It is the open time of the bar the plan names.
- `earliest_fill_seq` now means the first bar expected to open at or after the time the
  decision is ready. It is one higher than before on 14 of the 17 orders and the same on 3.

The 17 fill rows are byte-identical to the old file. No price, quantity, commission, cash, P&L
or time moved, and net is +227.88 before and after. The check, run at about 05:31Z: taking the
two new fields off the order rows and putting `min_fill_seq` back into `earliest_fill_seq` gives
a file whose sha256 starts `cc1b365708da1aba`, the old hash recorded in
`receipts/fresh_reviewer_20261114T223428Z.md:19`.

### A5. This file against the code

The advisor read the 22:35Z version of this file, where the gate and the result page were NOT
DONE. This file was rewritten at 05:25:36Z. One stale sentence was left in spec row 4 near the
end and is now marked superseded. State now: the gate is built and nobody has typed a decision.
The result page is built. The real-data door is built and no real file has been run. The
`MISSED_FILL` label the advisor asked about was never built and stays in "Not done".

### D2. The key

Superseded at 06:40Z. `START_TONIGHT.md` no longer has a fetch command, a key in a web address,
`TD_KEY` or a signup step. Codex's verdict is that no source is cleared. The paragraph below is
kept as the 05:36Z record only. The header-auth answer it waits for is in the research lane's
addendum: documented by the vendor, not run. See "The research lane's addendum" in the 09:23Z
section.

`START_TONIGHT.md` section (b) has a new step 6, `unset TD_KEY`, run once the fetched file is
checked. The request still carries the key in the URL (`apikey=${TD_KEY}`). The coordinator is
having Twelve Data's own documentation checked for header auth and said to leave the URL form
until that answer arrives.

### Not done from the optional list

- Done at 09:42Z, see the 09:23Z section above. The 05:36Z text was: The 8x-cost figure is not on `RESULT.html`. `run.py sweep` prints it: net -69.03 at 8 times
  costs and +100.63 at 4 times (05:35:29Z). A change to the page and its tests did not fit
  safely before 06:05Z.
- The durable bar-numbering repair, described under B4.

### Observed 2026-11-15 05:35Z to 05:36Z, all with `/usr/bin/python3 -I`

| UTC | Command | Result |
|---|---|---|
| 05:35:27Z | `-m unittest discover -s nov14-sprint/tvbot/tests -p "test_*.py"` | exit 0, "Ran 87 tests", OK |
| 05:35:28Z | `run.py replay --fresh --expect fixtures/expected_normal_ledger.jsonl` | exit 0, first line says TEST ONLY, "expected ledger MATCH 34 rows", sha256 `86ba83acc1ad29d8`, net +227.88, 17 orders, 17 fills, timing check yes, plan check 17 of 17, page rebuilt |
| 05:35:28Z | `run.py adverse` | exit 0, "RESULT: 28 of 28 cases passed" |
| 05:35:29Z | `run.py sweep` | exit 0, "net falls at every step as costs rise: yes" |
| 05:35:40Z | `bot/check_review.py` | exit 0, "RESULT: PASS. 15 of 15 code checks passed." |
| 05:35:41Z | `run.py paper --fresh --config config/smaller_size.json` (no source) | exit 2, "NO REAL SOURCE IS SET UP. No bars were read and no signal was made." |
| 05:35:41Z | `run.py paper` (no source) | exit 2, the same message |
| 05:35:41Z | `run.py gate --show --config config/smaller_size.json` | settings `7985e87d4578`, share 33.2 percent, "recorded now nothing" |

Also at 05:35:41Z: `gate/` and `real/` do not exist. The Pine file is unchanged (sha256 starts
`a04cdd266f21096b`). `git status` shows the whole `nov14-sprint/tvbot/` folder untracked, HEAD
`fe8b4d9`. Nothing is committed. The changed `START_TONIGHT.md` was sent to Matthew's device
from this chat at about 05:37Z.

### Not verified in this pass

- The refusal and the `--fresh` path ran only in tests, on made-up rows. No real re-fetched
  file exists, so the real vendor's window behaviour is taken from the advisor's reading.
- No person has run the changed guide, the `unset` step or `paper --fresh` in Terminal.
- `RESULT.html` was rebuilt by the 05:35:28Z replay and was not looked at again.
- Everything in "Not verified" in the restart section below still stands.

## Restart, 2026-11-15T04:41Z: the one-shot state

Matthew opened a new 120-minute session at 04:41:26Z, ending 06:41:26Z. Record:
`nov14-sprint/HUMAN_DIRECT_20261115T044126Z_RESTART_120MIN.txt`. His words: "I asked for a
one-shot best attempt at the trading bot, not multiple nights of work so this is it, I'll check
in via mobile and what's left to do tonight to start it". His earlier correction, relayed by
Codex: "I don't care about fake paper data. Use real teams and real events and in fact, let's
prepare to obtain real data."

The coordinator gave this lane five items. This section is the current state. Where a later
section of this file disagrees with it, this section wins.

**What is left tonight is Matthew's, and it is written for his phone in `START_TONIGHT.md`:**
look at `RESULT.html`, decide the gate, and, if he wants real bars, connect a source himself.
Both files were sent to his device from this chat at 05:26Z (the page as built at 05:23:06Z).

### The five items

| Item | State | Where |
|---|---|---|
| 1. Real-data adapter | Built for a local file. With no source set up it makes no signals and prints one message. TradingView-origin input is refused. No real file has been run through it. | `bot/real_feed.py`, `run.py paper`, `config/source_template_twelvedata.json`, `tests/test_real_feed.py` (35 tests) |
| 2. Fill-timing fault | Fixed, with regression tests. The plan now names bar 75, not 74. The second packet's inputs give 125, not 124. | `bot/engine.py`, `bot/run.py`, `tests/test_fill_plan.py` (7 tests), `packets/PKT-291c26718608.json` |
| 3. Risk and leak | Shown plainly on the gate and the page: one stop-out is 79.98, which is 80.0 percent of the 100 limit. A smaller size is ready: 33.19, 33.2 percent. The default size was not changed. The new packet bars file has no generator name, seed or period. | `bot/riskinfo.py`, `config/smaller_size.json`, `packets/test_only_bars_through_signal_bar.jsonl` |
| 4. Result page and gate | Built. The gate is not decided. Only Matthew can decide it. | `RESULT.html`, `bot/page.py`, `run.py gate` |
| 5. START_TONIGHT.md | Written. | `START_TONIGHT.md` |

### 1. Real-data adapter

- The bot reads `real/source.json` (schema `tvbot-real-source-1`). That file names one CSV on
  this Mac. Header `ts,open,high,low,close,volume`, UTC, oldest row first, closed bars only.
  `ts` is when the bar opened.
- The first column may also be named `datetime`, and times with no zone are read only when the
  source file says `"naive_ts_is_utc": true`. That allowance exists because the research
  worker's pick (Twelve Data) writes that shape. A template for it is in
  `config/source_template_twelvedata.json`. Matthew fills in three blanks himself. With them
  empty, the bot refuses the file and names the fields.
- The source file must carry an https terms URL, a quote from the terms, a human approver and a
  date. An assistant's name as approver is refused. A source named `synthetic` is refused.
- No source file: "NO REAL SOURCE IS SET UP. No bars were read and no signal was made.", exit 2.
  A source file without an approved gate: "PAPER GATE NOT APPROVED", exit 2, nothing is read.
- A chart-export header or any TradingView marker is refused as `tradingview_origin`
  (terms sections 3 and 27, `RECONCILE.md`).
- Synthetic bars are labelled TEST ONLY in the replay output, on the result page, in the new
  packet and in its bars file.
- Not built: a keyed or live connection. The brief said to support a local file now. The bot
  never calls a data service and never sees a key. Matthew fetches the file himself.
- `real/` does not exist. Making it is Matthew's step. `nov14-sprint/tvbot/.gitignore` keeps
  it out of git, because a vendor's terms may forbid sharing the bars.
- A saved file has no arrival times. Each bar is treated as arriving when it closes, and its
  close is its open plus the timeframe. For the short last bar of a session that is later than
  the real close, never earlier.
- The source pick and its terms notes are the research worker's:
  `nov14-sprint/reddit/REAL_DATA_SOURCES.md`. Nobody has signed up, made a key or sent a request.

### 2. Fill-timing fault

- The rule: a fill bar is the first bar after the signal bar that opens at or after
  `earliest_fill_ts`. The packet's `earliest_fill_seq` now names that bar and carries
  `earliest_fill_open_expected`.
- The engine always filled at the right bar. The fault was in the packet's forward plan, which
  named a lower bound. The plan and the fill now use one rule, and every replay checks one
  against the other: "the planned bar was the bar that filled for 17 of 17 orders".
- New packet `PKT-291c26718608`: bar 75, expected open 2026-06-15T18:30:00Z (decision ready
  17:30:07Z). The second packet's inputs (`PKT-a4e48b82b984`), rebuilt in memory: bar 125,
  expected open 2026-06-24T19:30:00Z (decision ready 18:30:07Z). Both match the fills in the
  replay.
- The old packet `PKT-7069f9b05f2a` and both of its reviews stay as history, unchanged.
  No model has reviewed the new packet.

### 3. Risk and leak

- Default settings (`fd1ec9cb6f5d`, order size 5000): one stopped trade costs 79.98, which is
  75.00 of price fall plus 4.98 of costs. That is 80.0 percent of the 100 daily-loss limit. The
  coordinator's figure was about 78.81. The figure shown is the one this lane's code computes.
- The worst closed trade in the test was -154.20, more than the whole daily limit. It sold
  about 3 percent below its entry, twice the stop distance. The gate prints that it is more
  than the whole daily limit, and the page shows the trade.
- Smaller size (`config/smaller_size.json`, order size 2000, settings `7985e87d4578`): one
  stopped trade costs 33.19, 33.2 percent of the limit. Three fit inside the limit. Worst closed
  trade in the test -62.25. Test net +81.10.
- The default was not changed. The expected ledger (34 rows) and the old packet and its reviews
  are tied to the default settings. Matthew picks the size at the gate, and an approval covers
  one rule id and one settings hash. `START_TONIGHT.md` suggests the smaller size.
- Leak: line 1 of `packets/test_only_bars_through_signal_bar.jsonl` now reads "a fixture script
  (name, seed and period withheld)". The old file `packets/bars_through_signal_bar.jsonl` is
  unchanged, because the old packet's saved reviews are checked against its hash. It still names
  the generator, the seed and the period, so do not give it to a new reviewer.

### 4. Result page and gate

- `RESULT.html` is rebuilt by every `replay`, `gate` and `paper` run. Paper `#fcfaf6`, Charter
  serif, cool-blue accents, after `odds/price_helper.html`. No scripts and no web links.
- It shows what the bot did (TEST ONLY), the line "+227.88 on one synthetic sample is not
  evidence of an edge.", the risk at both sizes, the gate state ("Not decided yet") and the
  real-data state ("No real data source is connected").
- `run.py gate` prints the rule, the settings and the risk, then takes exactly
  `APPROVE PAPER ONLY` or `PASS`, typed by a person in the Mac's Terminal app. From an assistant
  session, a script or a pipe it prints "NOT RECORDED" and exits 2. Observed in this session at
  05:23:14Z.
- An approval allows paper mode on real bars only, for one rule id and one settings hash. It is
  a gate on the mode as a whole. It does not ask before each paper trade. It never allows a
  real order, and no code here can place one.
- The decision is stored in `gate/paper_gate.json`. That file does not exist. No assistant may
  write it.

### Observed on 2026-11-15 (UTC), all with `/usr/bin/python3 -I`

| UTC | Command | Result |
|---|---|---|
| 05:19:42Z | `tests/test_real_feed.py` | 35 tests, OK |
| 05:19:52Z to 05:19:54Z | `run.py replay --expect fixtures/expected_normal_ledger.jsonl` | exit 0, "expected ledger MATCH 34 rows", sha256 `86ba83acc1ad29d8` |
| 05:19:52Z to 05:19:54Z | `run.py adverse` | exit 0, "RESULT: 28 of 28 cases passed" |
| 05:19:52Z to 05:19:54Z | `run.py sweep` | exit 0, "net falls at every step as costs rise: yes" |
| 05:19:52Z to 05:19:54Z | `-m unittest discover -s nov14-sprint/tvbot/tests -p "test_*.py"` | exit 0, "Ran 84 tests", OK |
| 05:20:04Z | `bot/check_review.py` (old packet) | exit 0, "RESULT: PASS. 15 of 15 code checks passed." |
| 05:20:04Z | `run.py gate --show` | settings `fd1ec9cb6f5d`, share 80.0 percent, "recorded now nothing" |
| 05:20:04Z | `run.py gate --show --config config/smaller_size.json` | settings `7985e87d4578`, share 33.2 percent |
| 05:20:04Z | `run.py paper` | exit 2, "NO REAL SOURCE IS SET UP. No bars were read and no signal was made." |
| 05:20:04Z | `run.py registry` | variants tried 1, frozen rule `EMAX-1.0.0-14251ac3` |
| 05:23:06Z | `run.py replay --fresh` (step 2 of `START_TONIGHT.md`, as written) | exit 0, first line says TEST ONLY, net +227.88 (before costs +270.30, spread and slippage -25.42, commission -17.00), 630 bars, 17 orders, 17 fills, 8 round trips (6 won, 2 lost), timing check yes, plan check 17 of 17, page rebuilt |
| 05:23:14Z | `run.py gate --config config/smaller_size.json` with no keyboard | exit 2, "NOT RECORDED" |

Also at 05:20Z and 05:23Z: `gate/` and `real/` do not exist. The Pine file is unchanged (sha256
starts `a04cdd266f21096b`). The old packet bars file is unchanged (sha256 starts
`571b15b1f507fed4`).

A made-up file in the picked vendor's shape (175 hourly rows, five weeks, prices invented) ran
through the template, the adapter and the engine at 05:19:15Z: 175 bars accepted, 2 entries,
1 exit, timing and plan checks clean. That tests the door. It is not market data.

### Not verified

- No real CSV has been run. Every check used made-up bars.
- Nobody has run the Twelve Data request. Its real hourly bars (session start, the short last
  bar of the day, half days) may not line up the way the adapter expects. If they do not, the
  bot refuses the file and says which line.
- Three terms points for Twelve Data are open and Codex has not ruled: whether Basic counts as a
  free trial for evaluation only, whether "internal use" covers one person, and how long data
  may be stored. The research worker's terms quotes came through a summarizing fetch, except
  the Alpha Vantage terms. (Replaced for Twelve Data at 09:54Z: the research lane's addendum
  quotes the pages' raw text. See "The research lane's addendum" in the 09:23Z section.)
- The result page was looked at once, as a Quick Look image of its top at desktop width (title,
  caveat box, tiles, first table). It was not opened in a browser and not seen at phone width.
  The lower sections (risk, gate, real data) were checked as text by 12 tests, not by eye.
- No person has run `gate` or `paper` in Terminal. The approve path was exercised only by tests
  that write a test approval inside a temporary folder.
- No model review exists for `PKT-291c26718608`.
- Nothing is scheduled and nothing runs by itself. Each run is a typed command.

### One incident to know about

During the page work a Sonnet helper ran `rm -rf /tmp/tmp* 2>/dev/null; true` as cleanup. The
AG-9 Bash Guard hook answered with a deny, but its reply failed the hook schema (no
`hookEventName`), so the app logged a hook error and the command ran. Errors were hidden, so it
is not known whether anything in `/tmp` matched and was deleted. In zsh a pattern with no match
stops the command before `rm` runs. I did not scan `/tmp` to find out, because those are not
this lane's files. The helper reports it changed no repo file other than its three. This is a
possible file-scope breach that I cannot check or undo. The rule for any later helper: no
`rm`, no writes outside `tvbot`, temporary files only through `tempfile` or the scratchpad.

### Follow-ups for the coordinator (not done in this lane)

1. A Codex ruling on the three Twelve Data terms points, before Matthew relies on that source.
2. A model review of `PKT-291c26718608`, if a fresh review is wanted.
3. The AG-9 guard hook's deny does not take effect, because its output fails the schema.
4. Someone opening `RESULT.html` at phone width.

### Tools and models used

Fable 5.2 for the design and the engine changes. One Sonnet helper for the page layout. The
checks run in under a second each, so they were run inline, not handed to a helper. Browser
tools were not used: the rule is Dia for browsing, and the page is a local file.

## What Matthew can use now

Two separate pieces, kept apart on purpose:

1. A TradingView Pine v6 indicator (`pine/emax_alerts.pine`) that draws one rule on a SPY 1-hour
   chart and raises alerts for him to read. It sends nothing anywhere.
2. An offline paper runner (`bot/`) that replays synthetic hourly bars through the same rule,
   records one decision per bar, fills paper orders at a later price with costs, and prints a
   ledger and a result. It uses no network, no account and no real prices.

Since the 04:41Z restart there are three more pieces: a result page (`RESULT.html`), Matthew's
paper-only gate (`run.py gate`) and a door for real bars from a file he downloads himself
(`run.py paper`). His steps are in `START_TONIGHT.md`.

Everything here is paper only. The only result so far comes from synthetic bars. It is a check
that the mechanics work. It is not evidence that the rule makes money.

## Entry points

Run from a clean shell at the CCA root (`/Users/matthewshields/Projects/ClaudeCodeAdvancements`).
Use `/usr/bin/python3` (3.9.6). Standard library only. No network.

2026-11-15: put `-I` after `/usr/bin/python3` in every command below. Each was rerun that way
between 05:19Z and 05:23Z. Two commands are new. `run.py gate` is Matthew's paper-only decision,
typed in Terminal (`gate --show` only prints). `run.py paper` reads real bars from the file he
set up, and refuses without a source and an approved gate. Add
`--config nov14-sprint/tvbot/config/smaller_size.json` to both for the smaller size. The unit
tests now number 87. `START_TONIGHT.md` has the same commands in the order Matthew runs them,
with `--fresh` on `paper`: after a new fetch, `paper` without it refuses and reads nothing.

Normal, fresh run (wipes this run's state folder, replays the bundled feed, compares the ledger
with the expected one). This is the command for a "Run" button:

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py replay --fresh --as-of 2026-11-14T00:00:00Z --expect
```

Rerun (same feed again without a reset; nothing new may be decided). This is the command for a
"Run again" button:

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py replay --as-of 2026-11-14T00:00:00Z --expect
```

Adverse run (28 cases: TradingView-origin, unknown origin, stale, future-dated, missing,
duplicate, agent text, over-limit, fill timing, second use of the untouched period):

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py adverse
```

Cost sweep (net result at 0, 1, 2, 4 and 8 times the costs):

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py sweep
```

Unit tests:

```bash
/usr/bin/python3 -m unittest discover -s nov14-sprint/tvbot/tests -p "test_*.py"
```

Plain-English reason for each decision (add `--decision <id>` for one, `--all` for every bar):

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py explain
```

Rule registry (variants tried, frozen rule, whether the untouched period was used):

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py registry
```

Review packet (rewrites the packet and the reply format; the packet id does not change):

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py packet
```

Check the saved Claude review against the packet in code:

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/check_review.py
```

Exit codes of `run.py`: 0 ok. 1 a check failed. 2 the feed, config or untouched period was
refused. 3 saved files disagree, so the run stopped. 4 busy, another run holds this state folder.
`check_review.py`: 0 pass. 1 a check failed or a number could not be traced. 2 a file is missing.

Do not run `run.py holdout`. The untouched period was used once and a second use is refused.

## What was observed

This section is from 2026-11-14. For 2026-11-15 see the restart section near the top.

All from the CCA root with `/usr/bin/python3`. Full outputs are in `out/qa_logs/final_*.txt`.

| Command | Exit | When observed (UTC, Nov 14) | Observed |
|---|---|---|---|
| normal fresh run | 0 | 22:23:47Z by this lane; 22:30:17Z by the fresh reviewer | 630 bars accepted, 0 rejected; 17 orders, 17 fills; net +227.88; 8 round trips; `expected ledger MATCH   34 rows` |
| rerun | 0 | 22:23:47Z and 22:27:11Z by this lane; twice at about 22:30Z by the fresh reviewer | 0 accepted, 630 rejected as `duplicate_bar`; "nothing new was decided"; ledger still matches |
| adverse | 0 | 22:23:48Z and 22:32:52Z by this lane; about 22:30Z by the fresh reviewer | `RESULT: 28 of 28 cases passed` |
| sweep | 0 | 22:23:48Z and 22:30:32Z | x0 +270.30, x1 +227.88, x2 +185.47, x4 +100.63, x8 -69.03; net falls at every step as costs rise: yes |
| unit tests | 0 | 22:23:48Z and 22:27:11Z | `Ran 30 tests ... OK` |
| registry | 0 | 22:23:48Z | variants tried 1; frozen `EMAX-1.0.0-14251ac3`; untouched period used 2026-11-14T22:17:06Z |
| holdout, second attempt | 2 | 22:23:48Z | `UNTOUCHED PERIOD REFUSED: ... it cannot be used again` |
| packet | 0 | 22:27:10Z | id `PKT-7069f9b05f2a`; frozen block equal to Codex's copy (checked in code) |
| check_review | 0 | 22:23:19Z and 22:27:11Z | `RESULT: PASS. 15 of 15 code checks passed.` 49 of 49 numbers and times traced |

The last code edit was at 22:27:10Z (`bot/run.py`, see "What changed since 22:12Z"). Runs timed
22:23Z are from before that edit. Runs timed 22:27Z or later are from after it.

Normal run, main lines as printed:

```
rule            EMAX-1.0.0-14251ac3 (rule variants tried so far: 1)
bars            630 accepted this run, 0 rejected
decisions       630 on file {"BLOCKED": 2, "ENTER_LONG": 9, "EXIT_LONG": 8, "HOLD": 201, "STAND_ASIDE": 410}
ledger          17 orders, 17 fills, 0 cancels, pending order: none
timing check    every fill used a bar that opened at or after its decision was ready: yes
start cash      10000.00
end equity      10227.88
net P&L         +227.88 (before costs +270.30, spread and slippage -25.42, commission -17.00)
round trips     8 (6 won, 2 lost); largest fall from a peak 469.58; open position 50
buy and hold    +72.99
note            synthetic bars; this is a mechanics check, not evidence of an edge
```

First trade, showing signal time apart from fill time: the buy signal came on bar 73, which
closed at 2026-06-15T17:30:00Z. The bar was delivered at 17:30:02Z and the decision was ready at
17:30:07Z. It filled at the open of bar 75 at 18:30:00Z: raw open 100.10, fill price 100.13 after
spread and slippage, commission 1.00.

Setups seen, refused and taken: 11 long setups were seen. 9 were taken (ENTER_LONG) and 2 were
refused by the risk check (BLOCKED): one at bar 129 because the daily loss limit had been reached,
one at bar 267 because the cooldown had not passed. Three of the 8 exits were forced: one by the
daily loss limit and two by the stop. The other five were the averages crossing back.

Cost sweep, as printed:

```
costs x0   net    +270.30
costs x1   net    +227.88   equals the replay's net: yes
costs x2   net    +185.47
costs x4   net    +100.63
costs x8   net     -69.03
net falls at every step as costs rise: yes
```

The untouched period (210 bars the rule had never seen) was run once, at 2026-11-14T22:17:06Z,
after the rule was frozen. Result: 1 round trip, net +76.98 against buy and hold -70.00. One trade
on made-up bars says nothing about the rule's worth. It shows the "use it once" lock works.

## What changed since 22:12Z

Times are UTC on 2026-11-14, taken from file stamps and saved receipts.

| When | What changed |
|---|---|
| 22:12:12Z | Matthew's "get everything restarted" line was passed to Codex through its queue command. Queued; the thread did not resume. Receipt: `receipts/TO_CODEX_restart_20261114T221212Z.txt`. |
| before 22:17Z | `bot/run.py`: the whole-transaction lock per state folder, the `BUSY:` line and exit 4 (Codex's concurrency repair). The exact minute was not recorded, because the file was edited again later. |
| 22:16:09Z | Packet `PKT-7069f9b05f2a` first published to `packets/`, with `CHALLENGE_SCHEMA.json`. |
| 22:16:33Z | The Claude review call started. Its reply carries the time 22:17:03Z. |
| 22:16:58Z | `tests/test_engine_adverse.py` last changed (30 tests). |
| 22:17:06Z | The rule was frozen in `bot/rule_registry.json` and the untouched period was used, once. |
| 22:18:13Z | The review reply was saved as received (`packets/reviews/...reply.txt`). |
| 22:23:19Z | New file `bot/check_review.py` (checks every number in the saved review in code) and its saved output. |
| 22:23:36Z | The recorded review wrapper (`packets/reviews/...recorded.json`). |
| 22:23:47Z | Every command was run once more. No code change. |
| 22:27:10Z | `bot/run.py`, `packet` command only: the packet's review status is now read from the saved review files, and one status line is printed. The `packet` command was rerun, so the packet file, the bars file and `CHALLENGE_SCHEMA.json` were rewritten. The packet id and frozen block are the same. Only `review_status` and `published_utc` differ. |
| 22:27:39Z | `RETEST_READY.md` written for Codex. |
| 22:29:07Z | This file written. |
| 22:30:17Z | The fresh reviewer's run rewrote `out/normal` (same 630 decisions, same ledger hash). |
| 2026-11-14T22:34:28Z | This update, and `receipts/fresh_reviewer_20261114T223428Z.md`. |

Not changed since 22:12Z: `bot/engine.py` and `bot/explain.py` (21:44:38Z), `bot/rules.py`
(21:31:32Z), `bot/provenance.py` (21:31:13Z), `fixtures/normal_bars.jsonl` (21:57:29Z),
`fixtures/expected_normal_ledger.jsonl` (22:00:02Z), `pine/emax_alerts.pine` (21:24:09Z) and
`pine/README.md` (21:57:02Z; lines 3 and 32 are the coordinator's).

The coordinator retested the code as it stood at 22:17Z on a fresh copy and saw the same numbers
(net +227.88, 8 round trips, rerun 630 `duplicate_bar`, adverse 28 of 28, sweep falling at every
step). The 22:23Z and 22:27Z changes are outside that retest.

## Not verified

This section is from 2026-11-14. For 2026-11-15 see the restart section near the top.

- No one outside this lane has run `bot/check_review.py` (22:23:19Z) or the 22:27:10Z edit to the
  `packet` command. This lane ran them, and its own subagent ran the replay and adverse commands.
- After the 22:27:10Z edit this lane did not rerun `registry`, `explain`, the refused `holdout`
  attempt or the concurrent-start tests. The edit touched none of that code.
- The fresh run after the edit was done by the fresh reviewer subagent, not by this lane. This lane
  checked the files it left (630 rows, 630 unique ids, ledger hash `cc1b365708da`).
- Codex has not reported a retest of the concurrency repair. The coordinator says it sent Codex
  the retest request at 22:33:16Z. The coordinator also reports its own check on a scratch copy:
  fresh with fresh and plain with fresh started together, all exit 0, net +227.88 each, 630 of
  630 unique decisions. It did not test the `BUSY` case. That is the coordinator's report,
  received about 22:35Z. This lane did not see those runs.
- A hard kill in the middle of a write was never tested.
- Whether a Pine alert fires on a live bar was never tested. This lane did not load the script
  into any TradingView account. Codex's check covered compile and draw of the file with SHA-256
  `a04cdd26...`.
- The desk's copy of the packet in `nov14-sprint/review/PKT-7069f9b05f2a/` is the coordinator's.
  It was made before the 22:27:10Z rewrite. This lane did not compare it with `packets/`.
- The Claude review's model id (`claude-sonnet-5-5`) is what the reply said about itself. The
  fresh reviewer's report states no model id. It was started on the Haiku setting.
- The 22:12Z message to Codex was queued and no reply was seen. Earlier messages to the
  coordinator were queued. The close-out message at 22:34Z was reported as delivered.
- The policy phrases in `RECONCILE.md` came through a summarising web fetch. Open the page before
  relying on any one phrase.
- The result is on scripted synthetic bars. Nothing here shows the rule works on real prices.

## The rule

`EMAX` 1.0.0, rule id `EMAX-1.0.0-14251ac3`. One instrument (`SYNTH-FUND-60M`, an ETF-like
synthetic fund on hourly bars, no futures). Long only.

- Two exponential averages of the close: fast 8 bars, slow 21 bars, each started from the first
  close. Nothing counts until 63 bars have been seen.
- Buy setup: the fast average crosses above the slow one on a closed bar while no position is open.
- Exit, in this order: a gap in the data, the daily loss limit, the stop (1.5 percent below the
  fill bar's raw open), the fast average crossing back below the slow one.
- Risk limits: at most 6,000 per position and 100 shares, daily loss limit 100, a 3-bar cooldown
  after an exit, one position per symbol. A config file can tighten these. It cannot loosen them.
- Costs: half-spread 1 basis point, slippage 2 basis points, commission 0.005 per share with a
  1.00 minimum.

## Fill timing (Codex's availability rule)

- Every bar must carry `delivered_ts`. I chose to refuse a bar without it (`missing_input`).
  I did not fall back to the bar's close time.
- A decision is ready at `delivered_ts` plus 5 seconds.
- It fills at the open of the first later bar that opens at or after that moment, plus costs. On
  a continuous hourly feed that is one full bar after the signal bar closes.
- An order still waiting when the feed ends stays pending. It is NOT labelled `MISSED_FILL`. The
  coordinator asked for that label. It is not done.
- A bar delivered more than 120 seconds late is rejected as stale. A bar dated after the `--as-of`
  clock is rejected as future-dated.

Codex's late-delivery file (`codex/late-signal-fixture.jsonl`): delivered 16:00:30Z, ready
16:00:35Z, filled at bar 66 open 2026-11-03T17:00:00Z. Codex confirmed this fix through the CLI.

## One decision per opportunity, and the lock

- Each bar gets one recorded decision with an id built from the symbol, bar and rule version. The
  decision is written before any fill. A repeated bar, a replayed feed or a restart keeps the first
  decision and adds nothing (adverse cases 16 to 19).
- Codex found that two runs started at once wrote 631 rows. Fixed: the CLI now holds one OS lock
  per state folder for the whole read, process and write, including `--fresh`. Lock files are in
  `locks/`, outside `out/`. A second start waits up to 30 seconds, then prints `BUSY:` and exits 4
  without reading or changing anything.
- Observed after the fix: three kinds of double start each gave 630 rows and 630 unique ids, and a
  later restart was clean. Details and retest commands for Codex are in `RETEST_READY.md`.
- The lock is taken by the CLI, not inside the engine. Code that imports the engine directly must
  call `run.hold_lock` itself.

## Review packet and the two model reviews

- Packet: `tvbot/packets/PKT-7069f9b05f2a.json`
- Bars the packet is allowed to show: `tvbot/packets/bars_through_signal_bar.jsonl` (73 bars)
- Reply format: `tvbot/CHALLENGE_SCHEMA.json`

The packet holds the first buy decision with every later bar, the fill and the result withheld.

Codex Astra review (Codex's record, not mine): `codex/packet-review/STATUS.txt`, raw reply in
`codex/packet-review/Astra_Review.json`. Per that status file, the gpt-6-astra call ran at 21:59Z
and its seven numeric, rule and time checks agreed. It also found the packet does not show the
cooldown status or the last exit, so the risk gate cannot be fully checked from the packet. I did
not read the raw reply.

Claude review (this lane):

- One real model call. A fresh-context subagent started through this app's Agent tool on the
  Claude subscription. It was not `claude -p` and it used no API key. This is the lane's one
  network use for a model. The runner, the tests and the checker never call a model.
- Model id as the reply reports it: `claude-sonnet-5-5`. The app returned no separate model id.
- Packet id `PKT-7069f9b05f2a`. Call started 2026-11-14T22:16:33Z. The reply's own time field is
  2026-11-14T22:17:03Z.
- Exact text: `packets/reviews/PKT-7069f9b05f2a.claude-sonnet-5-5.reply.txt`
- Record with the label "recorded": `packets/reviews/PKT-7069f9b05f2a.claude-sonnet-5-5.recorded.json`
- Verdict: "challenge". Rule followed: true. Authority line: "advisory only; cannot authorize a fill".
- Code check of every number: `packets/reviews/PKT-7069f9b05f2a.claude-sonnet-5-5.check.txt`,
  PASS, 15 of 15 checks, 49 of 49 numbers and times traced to the packet, the bars file or a value
  recomputed in code.

What the Claude review found, and it is right: the packet's forward plan says
`earliest_fill_seq` 74 and `earliest_fill_ts` 17:30:07Z, but its own fill rule points to bar 75
at 18:30:00Z, because bar 74 opens at 17:30:00Z, before the decision is ready. The engine did the
correct thing (it filled at bar 75). The packet's wording is the fault: the 74 is a lower bound on
the bar number and the time is the ready time, neither is the fill bar. I confirmed the mismatch
in code. I did not change the packet's frozen block, because both reviews were made against it.
Fix it in the next packet version.

Fixed on 2026-11-15 in a new packet, `PKT-291c26718608` (restart section, item 2). The old
packet and both reviews are unchanged.

Other points from that review: the cross was marginal (+0.018869 after -0.12742); no look-ahead
was found; the stop level, cost arithmetic and cooldown history cannot be checked from the packet.

Two small oddities, saved as received: the reply text carries `&gt;` and `&lt;` in place of the
comparison signs, and its own `live_or_recorded` field says "recorded" although it was a live call.

The packet's `review_status` line now reads "recorded" and names the saved review file. A replay
of the saved reply is always printed under the heading "RECORDED REPLY".

## Community_Findings safeguards

| Safeguard | Status | Where |
|---|---|---|
| Count every variant tried, freeze the rule, use the untouched period once | Done | `bot/rule_registry.json`, `registry`, `holdout` refused on second use (exit 2) |
| Numbers computed in code from dated inputs; Claude only explains | Done | `bot/rules.py`, `bot/explain.py`; `check_review.py` recomputes every review number |
| Signal time apart from the first later usable price, with stressed costs; higher costs lower the net | Done | fill timing above; `sweep` |
| Versioned rule, one recorded decision per opportunity, a re-sent decision makes no duplicate, agent text cannot authorize a fill | Done | adverse cases 16 to 21; the lock |

Reddit leads (`nov14-sprint/reddit/LEADS.md`, leads only, not facts) pointed the same way: signal
only on closed bars, count every variant, fill at the next bar with costs, one decision per
opportunity through one order path.

## Mapping to R2

| R2 pass check | Result |
|---|---|
| Pine indicator and alerts, human-visible, with a working chart link | Done. `pine/emax_alerts.pine`, `pine/README.md`. Codex compiled this exact file on a SPY 1-hour chart at 21:29Z (`codex/Pine_Native_Verification.md`). Chart: https://www.tradingview.com/chart/?symbol=AMEX%3ASPY&interval=60 |
| Runner fed only by synthetic or independently permitted data | Done. Only `synthetic` is permitted. A slot exists for another source and needs a terms URL, a quote, a named human approver and a date. None added. 2026-11-15: the slot is now a working door for a local CSV (restart section, item 1). Nothing has come through it yet. |
| Fixture replay gives the expected ledger | Done. 34 rows match. |
| TradingView-origin input fails closed | Done. Adverse cases 2 to 7. |
| Stale or future-dated input fails closed | Done. Adverse cases 11 to 15. |
| Duplicate decision on the same bar | Done. Adverse cases 16 to 19. |
| Over-limit order | Done. Adverse cases 22 and 23. |
| Signal time distinct from fill time | Done. Adverse cases 24 to 27 and the timing line in the normal run. |
| Net result falls as costs rise | Done. Sweep. |
| A Claude explanation that cannot authorize a fill | Done. Adverse cases 20 and 21. |
| Policy text quoted with its URL | Done. `RECONCILE.md`. The stricter reading is kept. |

## Mapping to Codex's first-build spec (`codex/Trading_Bot_First_Build.md`)

| Spec item | Result |
|---|---|
| 1. One dated observation with symbol, source, closed bar and a plain reason | Done in text: `explain` and `out/normal/decision_packet.md`. No live connection exists; the feed is a bundled synthetic replay. The TradingView chart is a link for Matthew to open, not an embed. |
| 2. A genuine Claude review and a separate Codex challenge on one packet, saved, arithmetic checked in code | Done. See the section above. |
| 3. Matthew sees the proposed action, the downside and an option to pass | BUILT 2026-11-15, NOT YET USED. `run.py gate` shows the rule, the settings and the downside (one stop-out against the daily limit, at both sizes) and takes `APPROVE PAPER ONLY` or `PASS` from Matthew in Terminal. It gates paper mode on real bars as a whole, once per rule and settings. It does not ask before each paper trade. The TEST ONLY replay does not need it. Nobody has typed a decision. |
| 4. A new reviewer launches the build and one result page | PARTLY DONE. At about 22:30Z a fresh-context Claude subagent, given only the Entry points section, ran the normal fresh run, two reruns and the adverse suite. Every command worked as written and its numbers matched this file. Its report is in `receipts/fresh_reviewer_20261114T223428Z.md`. It is this lane's own subagent, not a person or Codex. (Superseded: the 2026-11-14 wording here said the one result page was not done.) The one result page exists (`RESULT.html`, built 2026-11-15). No reviewer outside this lane has launched the build since the restart. |
| 5. Working entry point, commands for a second run, a short list of limits | Done. This file. |

## Not done

- (Built 2026-11-15.) Matthew's approve-or-pass gate exists. Nobody has typed a decision.
- (Built 2026-11-15.) The HTML result page exists. Still not built: served buttons or a
  `start.command`.
- A reviewer outside this lane has not launched the build after 22:17Z on 2026-11-14, or since
  the restart. The fresh reviewer was this lane's subagent.
- A live or keyed data connection. The real-data door reads a saved file only.
- A run on real bars. None has happened.
- The wording of adverse cases 11 and 12. Each reports a second rejection, `missing_input`, for
  the hole left by the refused bar. The case text names only the first reason. Both pass.
- The `MISSED_FILL` label for an order with no later bar.
- Cooldown status and last exit in the packet (Astra's finding).
- (Fixed 2026-11-15 in `PKT-291c26718608`.) The packet's forward-plan wording.
- Whether a Pine alert fires on a future bar. Codex's check covered compile and draw only.
- A test file for the `replay`, `adverse` and `sweep` commands themselves. There are 87 unit
  tests now. `tests/test_real_feed.py` runs the `paper` command and the gate check. The other
  commands were checked by running them.
- A hard kill in the middle of a write.

## Limits

- Synthetic data only. The normal feed was scripted so that each required event happens. The
  result shows the mechanics work and nothing more.
- No code can tell if someone typed TradingView numbers by hand into a file marked synthetic.
- In a replay, "stale" means the delivery lag written in the feed, and "future-dated" means later
  than the `--as-of` clock.
- Hourly open, high, low and close only. Stops are checked on a bar's close, not inside the bar.
- The expected ledger is a snapshot made by the same code. It catches a change. It does not prove
  the first run was right.
- The sweep's "extra wait" rows are different fills, so they are shown apart from the cost check.
- The review checker can match a small whole number to the wrong source by chance. It prints that
  caveat.
- The policy quotes in `RECONCILE.md` came through a summarising fetch, so treat them as close but
  not letter-perfect.

## Who wrote what, and other records

- Sonnet 5.5 subagents wrote the Pine files, the fixtures and the packet review. A Haiku 5.5
  subagent wrote the adverse test file. I wrote `bot/` and verified the rest by running it.
- One test expectation written by the Haiku subagent was wrong (it expected a stop where the daily
  loss limit fires first). I corrected the test and added a daily-loss test. The engine was right
  and was not changed for it.
- `pine/README.md` lines 3 and 32 were edited by the coordinator to record Codex's compile check.
  Claude did not load the script into Matthew's TradingView account and created no alert.
- Network use: none by the runner, tests or checker. One subagent model review. One research fetch
  of the TradingView policy pages. Messages to the coordinator session. One message to Codex.
- Matthew typed in this chat: "Get back to work, tell codex get everything restarted I just used a
  Fable reset". I passed that to Codex through its queue command at 22:12Z. The message was queued
  (`01a1dc1e-44f5-7620-8477-8e9398db67e9`) but the thread did not resume, so it is not confirmed
  read. Receipt: `receipts/TO_CODEX_restart_20261114T221212Z.txt`.
- A session-start note says a global pause is recorded. I judged it out of date: Matthew's direct
  Nov 14 sprint request and his line above both came after the Nov 7 pause.
- No commits, pushes, schedules or installs were made. Nothing was written outside `tvbot/`.
- No unexpected state is open.

- 06:40Z correction (coordinator, per Codex NOV15_SOURCE_VERDICT.md): Twelve Data Basic is not cleared for this workflow. START_TONIGHT section (b) no longer directs signup and no longer shows a key-in-URL fetch. No real SPY file has been run.
