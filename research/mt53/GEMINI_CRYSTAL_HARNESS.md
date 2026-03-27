# Gemini Plays Pokemon Crystal — Complete Harness Analysis
# Source: github.com/waylaidwanderer/gemini-plays-pokemon-public (default branch)
# Session: S201, 2026-03-26
# Status: VERBATIM captures of agents, tools, and notepad (Gem's Brain)

---

## 1. HARNESS OVERVIEW

### "Almost Vision-Only" Design
From the subreddit FAQ (u/reasonosaur):
- **Prompt Changes:** Instructions shifted from strict orders to advice. Removed specific game mechanic tips.
- **Minimized RAM Extraction:** Stopped providing map names, sizes, tile definitions. AI only receives:
  - Money, Pokedex, Party, PC, Inventory, Coordinates (essential status info only)
- **Anonymized Memory:** Mental Map uses generic IDs instead of names. AI sees `<Object id=3>` not `<NPC name=Jasmine>`. Must look at screenshot to identify.
- **Gap Filling (still provided):**
  1. NPC Movement reports between turns (using anonymized IDs)
  2. Text Logs — history of on-screen text (in case dialogue was skipped)

### Result
Gemini with this harness was **never able to get the 8th gym badge** in Crystal.
Accidentally KO'd Suicune while trying to blackout after running out of balls.

---

## 2. CUSTOM AGENTS (4 specialized sub-agents)

### 2A. Reality Check Agent
- Validates assumptions against actual game state
- Prevents hallucinations and logical inconsistencies
- Recognizes stunned NPCs remain visible (don't disappear)
- **MANDATORY before any significant navigation**

### 2B. Puzzle Solver Agent
- Scientific methodology: systematic hypothesis testing
- Key constraints:
  - Exhaust simple single-action tests before complex sequences
  - Avoid functionally equivalent failed attempts
  - Perform collision checks on suggested movements
  - 10-14 critical rules governing behavior

### 2C. Navigation Strategist
- High-level quest progression advice
- ABSOLUTE FIRST PRIORITY: only recognize puzzle elements explicitly in data
- Nothing can be inferred or hallucinated

### 2D. Party Strategist Agent
- Recommends optimal 3-Pokemon teams
- Analyzes type coverage and synergy
- Based on available roster and strategic objectives

---

## 3. CUSTOM TOOLS (6 tools)

### 3A. find_reachable_unseen_tiles
- BFS from player position
- Finds nearest unseen tile reachable through passable terrain
- Returns coordinates of adjacent SEEN tile to pathfind to
- Impassable types: WALL, VOID, WATER, unseen, PC, TV, COUNTER, BOOKSHELF, WINDOW, TOWN_MAP, POKEDEX, RADIO, PILLAR, MART_SHELF, INCENSE_BURNER, DOOR, STAIRCASE, PIT, CAVE, LEDGE_HOP_DOWN/LEFT/RIGHT

### 3B. plan_path_with_warnings
- A* pathfinding with NPC warning system
- Handles WATER (passable if player is on water), ledge one-way tiles, FLOOR_UP_WALL
- Returns JSON path + warnings for nearby moving NPCs
- Suggests stun_npc for NPCs near the route
- Distinguishes static objects (FRUIT_TREE, GYM_GUIDE, FISHER, etc.) from moving NPCs

### 3C. menu_navigator (vertical)
- Calculates Up/Down presses for vertical menus
- Handles text normalization for matching
- Outputs button press sequence ending with A

### 3D. horizontal_menu_navigator
- Same as above but Left/Right for horizontal menus

### 3E. select_move_tool
- Battle move selection by slot number (1-4)
- Calculates cursor movement from current position
- Used with autopress_buttons=true

### 3F. Built-in Tools (from harness framework)
- notepad_edit, run_code, define_agent, delete_agent
- define_map_marker, delete_map_marker
- stun_npc (freeze/unfreeze NPC movement)
- define_tool, delete_tool
- select_battle_option

---

## 4. GEM'S BRAIN (Notepad) — Complete Knowledge Base

### 4A. Critical Directives (Failure Prevention)
1. **TRUST THE TOOLS:** If pathfinding says "No path found," trust it. Don't waste turns trying to fix correct output.
2. **INVENTORY CHECK:** Always check inventory before searching for key items (COIN CASE incident).
3. **REALITY CHECK:** Use reality_check_agent BEFORE significant navigation.
4. **SIMPLICITY FIRST:** Test simplest assumptions first (Battle Tower exit was just walking on carpet).
5. **IMMEDIATE MAINTENANCE:** Fix things NOW — there is no "later" for an LLM.
6. **PATH EXECUTION:** plan_path_with_warnings only PLANS. Must set buttons_to_press=["path"] to MOVE.
7. **COORDINATE SYSTEM:** 0-indexed coordinates.
8. **MAP VERIFICATION:** Check actual map ID from game state before pathfinding.

### 4B. Critical Bugs Discovered
- **BATTLE TOWER GLITCH:** Accepting challenge + saving = guaranteed data corruption. Press B to cancel.
- **DIG GLITCH:** DIG in Olivine Lighthouse dead-end = game-breaking. Works fine in Dark Cave (location-specific).
- **HM USAGE:** Path command doesn't auto-use SURF. Must manually select from Pokemon menu.

### 4C. Common LLM Failure Modes (LEARNED FROM 100+ TURNS)
1. Position hallucinations
2. Hallucinated interactable objects (wall decorations are NOT switches)
3. Unproductive loops (repeating failed actions)
4. Deferring maintenance to "later"
5. Not marking dead ends immediately
6. Trusting internal state over game state
7. Long-distance paths unreliable (NPCs appear off-screen)
8. Menu dialogue loops (B not A to escape)
9. Location hallucination after warps
10. Not unstunning NPCs after finishing area

### 4D. Tile Mechanics Reference
**Impassable:** BOOKSHELF, BUOY, COUNTER, CUT_TREE, HEADBUTT_TREE, MART_SHELF, PC, PILLAR, RADIO, ROCK, TV, VOID, WALL, WHIRLPOOL, WINDOW, WATERFALL, INCENSE_BURNER, TOWN_MAP
**Traversable:** FLOOR, GRASS, TALL_GRASS
**Warps:** DOOR, LADDER (two-way), STAIRCASE (two-way), PIT (one-way), WARP_CARPET_LEFT/RIGHT/DOWN (two-way, directional)
**Conditional:** LEDGE_HOP_DOWN/LEFT/RIGHT (one-way), FLOOR_UP_WALL (can't move up), WATER (needs SURF)

### 4E. Game Mechanics Confirmed
- HM-cleared obstacles respawn on re-entry
- HM moves can't be forgotten
- Some NPCs need multiple A presses
- Phone list can fill up
- Trade evolutions: MACHOKE, KADABRA, HAUNTER, GRAVELER
- Defeated trainers remain as physical barriers
- STRENGTH pushes boulders (needs empty space opposite side)
- Ladders activated by walking onto them, not A/Up

---

## 5. CRITICAL LESSONS FOR MT-53 (Extracted from Gemini's Failures)

### What Gemini Failed At (and we must handle better)
1. **Walking in circles** burning tokens — need stuck detection
2. **Hallucinating game state** — RAM reading prevents this
3. **Not checking inventory** — systematic pre-action checks
4. **Deferring maintenance** — force immediate updates
5. **Long paths failing** — plan shorter segments
6. **Type confusion** — provide Crystal-specific type chart
7. **Never got 8th badge** — Crystal is HARD for LLMs
8. **50+ turns on wrong hypothesis** — need hypothesis timeout/abandonment

### What Gemini Did Well (and we should adopt)
1. Reality check agent concept (validate before acting)
2. Scientific puzzle solving (hypothesis -> test -> record)
3. Tile mechanics documentation (systematic)
4. Dead end marking system
5. NPC stunning for path safety
6. BFS exploration of unseen tiles
7. Party optimization for specific goals

### Our Advantages Over Gemini's Approach
1. **Opus 4.6** — stronger reasoning than Gemini 3.1 Pro
2. **Full RAM reading** — not "almost vision-only," we use ground truth
3. **Crystal memory reader already built** (37 tests)
4. **Better navigation** (A* pathfinding, 36 tests)
5. **No need for anonymized IDs** — we read actual data
6. **No NPC movement reports needed** — we read sprite positions from RAM
