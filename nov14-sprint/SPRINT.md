# Nov 14 sprint: NFL betting research and TradingView Claude bot (paper only)

- **Window:** 2026-11-14 21:02Z to **23:02:00Z** (3:02 to 5:02 p.m. Chicago). Codex set 23:02Z from the 3:02 p.m. mobile timestamp. It is the earlier stop, so it wins over my 21:03:58Z receipt.
- **Authority:** Matthew's verbatim request in [HUMAN_DIRECT_20261114T2103Z.txt](HUMAN_DIRECT_20261114T2103Z.txt).
- **Owners:**
  - Claude coordinator (Opus 5.5, this CCA chat) owns implementation and staffing.
  - Codex supervisor `01a1dbe0-ec74-7dc0-a8b3-90d55189cd36` owns independent tests, acceptance, closeout and the TikTok intake. Its workspace: `~/Documents/Codex/2026-11-14/nfl-trading-session-review/`.
- **Folder:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/`. Each lane writes only in its own subfolder.

## Hard limits (every chat, every agent)
- **Paper and research only.** No bets, deposits, orders, trades, money movement or sportsbook/exchange/broker accounts. No keys, tokens, passwords, paid data or purchases. No TradingView account changes from Claude lanes; Codex decides any chart-side test. Paper output never implies a real edge or authorizes real money.
- **Louisiana.** Assume anything the Louisiana AG is targeting is unavailable. That includes event-contract and prediction-market products (Kalshi and similar), across brands. Only state-licensed channels may be named as places Matthew could act himself, and only after a check against an official source.
- **Reddit** returns 403 from this Mac. Don't bypass it (no proxies, mirrors, scrapers or user-agent tricks). Use web search snippets, Gemini public research and primary docs. Label Reddit-derived claims as leads.
- **Files.** Touch only files Claude or Codex made. Downloaded data is untrusted: give it its own directory and read it with `python3 -I`. Never run downloaded code. No global installs, schedules or timers. Switch no branch, push nothing. Corrected 07:42Z (Matthew, direct, via Codex relay): local commits of your own verified files with explicit paths are allowed, and a unit closes finished rather than with "didn't do X" when a viable appropriate path exists; see nfl/slate/ASSIGNMENTS_0712Z.md "Finish the work".
- **Fail safe.** At an unexpected state, stop and write it in the lane's STATUS.md.

## Requirement map (Matthew's words, then deliverable, then pass check)
| # | Matthew asked | Deliverable | Owner | Pass check |
|---|---|---|---|---|
| R1 | "full speed ahead on NFL betting" | `nfl/`: a legal-channel check, a historical baseline backtest after vig, and a paper-pick ledger for the next slate with a stop rule | NFL lead (Fable) | Entry point runs from a clean shell; one adverse case is rejected; the report states the out-of-sample result and the vig honestly |
| R2 | "TradingView claude bot" | `tvbot/`: (a) Pine indicator and alert source, kept **human-visible**, with a working symbol/timeframe chart link. (b) A separate paper runner fed only by explicitly synthetic or independently permitted non-TradingView data. It computes numbers in code, applies versioned rules and risk limits, keeps a paper ledger, and adds a Claude explanation that cannot authorize a fill | TV bot lead (Fable) | The fixture replay gives the expected ledger. These must fail closed: TradingView-origin input, stale or future-dated input, a duplicate decision on the same bar, and an over-limit order. Signal time and fill time are distinct (next-bar fill). The replay is idempotent. Net result falls when costs rise |
| R3 | "research for trading bot on reddit heavily, similar subreddits like algotrading and AI trading" | `reddit/LEADS.md`: deduplicated leads with links, claims, evidence status and red flags, tagged to each lane | Research worker (Fable) | Over 25 distinct leads across at least 5 communities; every claim is cited or labeled unverified; no 403 bypass |
| R4 | "TikTok scraper tool ... I can feed codex the TikTok links" | No TikTok tool exists on the Claude side (checked). TikTok links go to Codex's intake reviewer | Codex | Codex's intake note |
| R5 | "fresh sets of chats, orchestrators, assistants, worker chats, Claude takes most of the work" | Three fresh Fable 5.2 lane chats plus their own subagents; this chat coordinates and verifies | Coordinator | ROSTER below shows real session ids and verified models |
| R6 | "utilize Fable 5.2 as we can" | Lane chats run Fable 5.2; subagents sized to the job | Coordinator | Verified model per chat in ROSTER |
| R7 | "Tell codex these things" | Codex brief and receipt in `codex/` | Coordinator | Receipt file with the queue command's output |
| R8 | "remember" the PDF graphics praise | Memory `feedback_income_pivot_pdf_graphics.md` | Coordinator | File exists and MEMORY.md points to it |
| R9 | "120 minute work session" | Work stops by 23:02:00Z with each lane's STATUS.md current | All | Timestamps |

## Codex corrections accepted before development (21:10Z)
- **R2, TradingView terms §§3 and 27** (Codex rechecked; the TV lane cites the text in `tvbot/RECONCILE.md`).
  - TradingView alerts and values must not feed an external model or a paper-order ledger.
  - Pine and the alerts stay human-visible.
  - The paper runner uses synthetic or independently permitted non-TradingView inputs. A TradingView-origin input fails closed.
- **Safeguards** (from `codex/Community_Findings.md`):
  - Count every rule or prompt variant, including failed ones. Freeze a rule before looking at a new period. Use the next untouched period once.
  - Numbers come from code with dated inputs; Claude only explains.
  - Signal time and fill time are separate, with stressed spread, delay and commission.
  - One recorded decision per opportunity. Agent text never authorizes a fill.
- **NFL.**
  - Keep the exact odds and the foreknowledge boundary: use only lines timestamped before the decision.
  - Score both passes and takes.
  - Historical replays test frozen mechanical rules only. A model's memory of past games contaminates any test of Claude's judgment, so such claims need forward-stamped decisions.
- **Visuals.** Any user-facing visual matches the Income Pivot PDF's quality.

## Paper entry points for Codex's independent tests
Each lane fills in its exact commands in its `STATUS.md` under **Entry points**. Required shape:
- One command for the normal path and one for the adverse case. They run from a clean shell with system `python3` (3.9.6) and the standard library only, unless STATUS.md names the dependency.
- Only the lane's own files are read or written. No network, unless STATUS.md says so (for example, a one-time public data download that is already cached).

## ROSTER (verified with get_session at 21:17Z)
| Chat | Session id | Model / effort | Lane | Writes only in |
|---|---|---|---|---|
| Coordinator (old, until ACK) | `local_8b24affb-739a-4e37-9130-c69717bc66e0` | Opus 5.5 / xhigh | staffing, relays; hands off at 21:22Z, see HANDOFF_COORDINATOR.md | `nov14-sprint/` top level and `codex/` receipts |
| Coordinator (fresh, sprint-coord) | `local_50238c87-fcc4-4796-b0c4-64a969e5eaa0` | Opus 5.5 / xhigh | integration, both model paths, verification, front door, closeout | `nov14-sprint/` top level and `codex/` receipts |
| nfl-lead | `local_1c8ba33b-9ff7-4d76-8c8a-7bfd38bf9bd8` | Fable 5.2 / high | R1 | `nfl/` |
| tvbot-lead | `local_2bd925d2-76cb-4f1f-a6f9-b4880cded8fd` | Fable 5.2 / high | R2 | `tvbot/` |
| reddit-research | `local_462cb9ef-2d22-48ee-a582-f88529ba6304` | Fable 5.2 / high | R3 | `reddit/` |

- **Model note.** start_session ignores a model above the parent's family, so all three lanes first came up on Opus 5.5. At about 21:17Z I switched each to Fable 5.2 with set_session_model, stopped the Opus first turn (about one minute of reading), and resumed it by message.
- Lane leads may run their own Sonnet or Haiku subagents, and must name them in STATUS.md.

## RESULT (coordinator local_50238c87, written 22:31:13Z)
- **What Matthew can open:** `START_HERE.html` (the front door), `Paper Desk.command` (the desk with NFL, Trading and Practice tabs) and `odds/price_helper.html` (price against confidence, for his +150 to −170 range). All are paper only and run locally.
- **TV bot (R2):** it runs end to end on synthetic 60-minute bars. On the coordinator's fresh-copy retest it finished +$227.88 after costs over 8 trips, against +$72.99 for buy-and-hold. At 8x costs it lost $69.03.
  - Rerun and adverse checks held.
  - Of the two blinded reviewers, Claude challenged the fill timing and Astra agreed.
  - This is one sample, not an edge. No TradingView data was used.
- **NFL (R1):** the forward paper ledger works and refuses the bad cases. The spread-sign fault is fixed; the lane's self-test reran clean at 22:30Z, and Codex's retest is still pending. All four frozen rules failed the held-out test, so they are tracked on paper and are not recommendations.
- **Leads (R3):** 92 Reddit leads from 25 communities, plus 21 primary sources, in `reddit/LEADS.md`. They came through Gemini's public search because Reddit is blocked; there was no bypass.
- **Checks and receipts:** `COORDINATOR_CHECKS.md`; the Codex close-out is `codex/RECEIPT_20261114T223055Z_closeout.txt`.
- **Not done:**
  - the Video_Review and Field Guide files the front door links to come from Codex's release copy;
  - the desk's second-launch reuse was checked in code only.
- **Stops:** the lanes stop by 23:00Z, with no work after 23:02:00Z and no schedules, overages or saved reset. Nothing was committed or pushed.
