Run /cca-init. Last session was S291 on 2026-04-09.

leagues6-companion work only. CCA tests: 355/374 suites (12409 total — existing 3.9 union syntax failures, no new regressions).

WHAT WAS DONE (leagues6-companion S291):
- GitHub push: OSRSLeaguesTool repo live at https://github.com/mpshields96/OSRSLeaguesTool (commit 7c74488)
- leagues_query.py: personal research assistant — searches 84,652 Discord messages + OSRS wiki
  - Free-text: python3 leagues_query.py "magic region picks" → Discord + wiki results with links
  - python3 leagues_query.py --regions → region points table (Desert=1410, Asgarnia=1170, etc.)
  - python3 leagues_query.py --tasks magic → all magic tasks with points + wiki URLs
  - python3 leagues_query.py --wiki grimoire → relic lookup with wiki link
- data/wiki_data.json: full OSRS wiki data (relics T1-T8, all 75 tasks with points, region echo gear, magic tasks, point cap requirements, mechanic changes)
- Pact planner confirmed: https://tools.runescape.wiki/demonic-pacts/ (what Discord links to)
- League dates confirmed: April 15 – June 10, 2026. Echo item stats reveal April 10.
- Reddit scan: "Six Easy/Lazy builds for Demonic Pacts Leagues" post has 6 builds including 3 magic variants with tree links
- Magic build consensus: Ancients forced. Kandarin+Desert+Zeah/Kourend for magic. T6=Grimoire (core).

IMPORTANT — leagues_query.py NOT usable by regular Claude Chat:
- It's a local Python script reading files from /Users/matthewshields/Downloads/leagues6-discord/
- Regular Claude (web/iOS) cannot run local scripts or access local files
- Solution: Claude Projects — upload wiki_data.json + Discord highlights as documents → works on iOS
- This is NEXT SESSION's Bucket 2 task (after the 3 Discord downloads)

NEXT SESSION WORK (in order):

Bucket 1 — Download + analyze 3 Discord threads:
  Matthew has 3 threads to download (not yet in /Downloads/leagues6-discord/):
  1. Route planner thread (~31k messages) — contains blank planner link to steal
  2. Large general discussion thread (~36k messages)
  3. Third thread (Matthew to confirm)
  Steps:
    - Matthew downloads the .txt exports to /Users/matthewshields/Downloads/leagues6-discord/
    - Run: python3 discord_analyzer.py (refreshes community_meta.json with new files)
    - Run: python3 leagues_query.py to confirm new message count
    - Search route planner thread for blank Google Sheets/Drive planner URLs

Bucket 2 — Clone the blank planner + Claude Code Google Drive integration:
  - Find the blank planner URL from the route tool Discord thread (ID 1487101393511649360)
  - Clone/copy the Google Sheet structure
  - Build a script that lets Claude Code update the Google Drive plan autonomously given Matthew's guidance
  - Requires: Google Drive API credentials (OAuth or service account) — Matthew to provide or set up
  - Key capability: Claude reads current plan state, Matthew says "add X to region Y", Claude updates sheet

Bucket 3 — Claude Project setup for iOS access:
  - Generate a plain-text summary document from wiki_data.json + community_meta.json
  - Package as uploadable documents for claude.ai Project
  - Upload to a new Claude Project titled "Leagues 6 Planner"
  - Verify iOS Claude app can query it: "what magic tasks give most points in Desert?"
  - No code needed — pure document upload

leagues6-companion gate: venv/bin/python3 -m pytest tests/ -q → 262 passed, GATE: PASSED
leagues6-companion git: 7c74488 (leagues_query.py + wiki_data.json added), remote: OSRSLeaguesTool
