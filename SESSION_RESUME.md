Run /cca-init. Last session was S105 on 2026-03-22.
S105 was a desktop coordinator session. 4 commits. 151 suites (150 pass, 1 pre-existing failure in test_website_generator_extended.py CSS bug).

COMPLETED S105:
- MT-28 Phase 1: principle_registry.py (73 tests) + wired into reflect.py. Laplace-smoothed scoring, domain dedup, pruning.
- MT-26 research: extracted clean markdown from raw JSONL (S104 high-context error). 6 verified papers in MT26_FINANCIAL_INTEL_RESEARCH.md.
- 3-chat system: launch_kalshi.sh + LAUNCH_3CHAT.md. All 3 chats launched (desktop + cli1 worker + Kalshi research).
- CCA_TO_POLYBOT.md: MT-26 papers + MT-0 task brief pointer + Matthew's VERBATIM late-night safety directive (permanent).
- Priority picker: MT-0 touched S105, MT-28 Phase 1 complete, session 105.
- Comms decision: bridge file (CCA_TO_POLYBOT.md) stays for cross-project. Don't port hivemind to Kalshi chats.

STANDING DIRECTIVES (S105, permanent):
- 3-chat system with Kalshi is THE priority for next few chats
- Late night bot safety: no regular-size bets, small experiments first, know how to turn off. PERMANENT.
- Use Kalshi RESEARCH chat (not main) — research has more context
- Keep comms simple: bridge file cross-project, cca_comm.py internal only

NEXT PRIORITIES:
1. Check if Kalshi research chat started MT-0 code work (trading_journal.py, research_tracker.py)
2. MT-28 Phase 2: pattern plugin registry (refactor reflect.py detectors). Multi-session.
3. MT-26 Phase 1: build financial intelligence tools from research doc
4. Fix test_website_generator_extended.py + test_dashboard_generator_extended.py CSS bug (worker task)
5. Paper digest spam fix status — check git log for debounce commit

PRE-EXISTING FAILURE: test_website_generator_extended.py (2 tests) — CSS class in global stylesheet matches when section is absent. Same pattern as dashboard_generator bug. Not from S105 changes.

Tests: 150/151 passing (1 pre-existing). Git: 4 commits (9b31961, 32cc7a0, bd6daee, f56a132).
