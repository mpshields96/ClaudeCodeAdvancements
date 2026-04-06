# NEXT CHAT HANDOFF

## Start Here
Run /cca-init. Last session S265 on 2026-04-06.

COMPLETED (Chat 36 — S265):
  36A. Wire collision_reader_crystal into main.py (MT-53)
       - main.py now imports build_intro_navigator_with_collision from collision_reader_crystal.py
       - Replaces build_crystal_intro_navigator (all-FLOOR approximation) with real wall/door/grass grids
       - Accurate tile dimensions from pret/pokecrystal .blk files (1F=12x8, NewBark=20x18, Elm=12x8)
       - 27 tests pass (test_collision_reader_crystal.py). Commit 78bb57c.

  36B. Blast radius import graph for agent-guard (AG)
       - agent-guard/blast_radius.py: ast-based forward/reverse dep graph
         - build_import_graph(root): scans .py files, extracts imports via ast
         - build_reverse_deps(forward): inverts graph
         - blast_radius(file, reverse_deps): len of reverse_deps[file]
         - is_high_risk: blast_radius > 5 (HIGH_RISK_THRESHOLD)
         - high_risk_files(): sorted desc list of (file, radius) pairs
         - Excludes venv/site-packages/__pycache__/node_modules from scan
         - CLI: --dir, --file, --threshold, --json flags
       - agent-guard/tests/test_blast_radius.py: 24 tests
         - known import graph → correct values
         - high_risk fires at 6 (not at 5 — strictly >threshold)
         - zero-dep = 0
         - diamond dependency, relative imports
       - agent-guard/ownership.py integration:
         - blast_radius column added to conflict risk table
         - "High Blast Radius Files (>5 importers)" section in manifest
         - Graceful fallback if blast_radius import fails
       - 24 tests pass. Commit 6036b01.

Tests: 363/374 suites passing (12677 tests). 11 pre-existing failures (pytest/module missing).
Git: clean after S265 wrap commit.

NEXT (Chat 37 — TODAYS_TASKS.md §CHAT 37):
  37A. BMAD Party-Mode Read (research only, ~15 min)
       - Fetch: https://raw.githubusercontent.com/bmadcode/bmad-method/main/src/core-skills/bmad-party-mode/SKILL.md
       - Capture key patterns in agent-guard/hivemind_notes.md (scratch pad)
       - READ ONLY — do not build anything. Prereq for MT-21 hivemind work.

  37B. Memory System Semantic Deduplication (Frontier 1)
       - Fix append-only memory rot: memories should update/delete when stale
       - Source: Finding #15 (mem0 architecture). Extract patterns only — no mem0 dependency.
       - Steps:
         1. Update memory-system/schema.md: add user_id, agent_id, run_id scoping fields
         2. In memory-system/capture_hook.py (write path): before inserting, find semantically
            similar existing memories (string similarity / keyword overlap — no embeddings v1)
         3. LLM prompt: "ADD new / UPDATE existing [id] / DELETE stale [id]?"
         4. Execute decision: ADD inserts, UPDATE modifies, DELETE removes
         5. Three-tier scoping: filter by user_id + optional agent_id/run_id
       - Commit after 37B tests green.

  37C. FAISS Local Vector Backend (stretch only)
       - Replace keyword-overlap with faiss-cpu cosine similarity
       - Graceful fallback if FAISS unavailable
       - Only if time permits after 37B

SCOPE NOTE: Chat 37 touches Frontier 1 (memory-system/) + possibly agent-guard/
  If > 4 subsystems: run gsd:plan-phase first (20 min). Otherwise gsd:quick.

ALSO DEFERRED (pick up when Chat 37 has slack):
  - Auto-generate PROJECT_INDEX.md from AST (codesight pattern) — blast_radius is now working, this is unblocked
  - MT-21 hivemind with BMAD patterns — after Chat 37 BMAD read
