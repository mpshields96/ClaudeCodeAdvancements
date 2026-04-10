# Leagues Claude Project Packaging

Purpose: turn the local `OSRSLeaguesTool` knowledge base into Claude Project documents that work on claude.ai and the Claude iOS app without requiring local scripts.

This is the safe parallel lane while CCA owns the blank-planner / Google Drive slice.

## Goal

Create a small document set that lets Claude answer Leagues 6 planning questions from uploaded files alone:
- best regions for a combat style
- highest-value tasks by region/skill
- relic and pact recommendations
- community build consensus
- planner/routing notes once the blank planner work stabilizes

Do not upload raw 84k-message Discord exports if a distilled summary can answer the same questions faster and cheaper.

## Inputs

Primary local sources in `OSRSLeaguesTool`:
- `data/wiki_data.json`
- `data/community_meta.json`
- `leagues_query.py` output for targeted questions

Optional later source:
- blank planner notes or exported planner snapshot once Bucket 2 settles

## Output Document Set

Use a 4-document minimum pack, or a 5-document pack when planner/route notes deserve their own upload.

Current CCA local state indicates the Leagues iOS pack has already expanded to 5 docs, so Codex support should treat 5 as the preferred shape when that extra planner/advisor layer exists.

Ready-to-fill templates now exist in CCA:
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_01_OVERVIEW.md`
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_02_REGIONS_RELICS_TASKS.md`
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_03_COMMUNITY_META.md`
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_04_QUERY_EXAMPLES.md`
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_05_PLANNER_ROUTE_NOTES.md`

### 1. `01_OVERVIEW.md`

Keep this under ~3 pages.

Include:
- league dates
- what the document pack contains
- region point totals
- always-unlocked context
- top current consensus bullets
- known caveats: community data can drift after new exports or patches

### 2. `02_REGIONS_RELICS_TASKS.md`

This is the core structured reference.

Include:
- each region with point total and notable unlocks
- relic tiers with short descriptions
- top tasks per combat style or skill cluster
- echo or item notes that matter for planning

Prefer compact tables or repeated section headings over giant prose blocks.

### 3. `03_COMMUNITY_META.md`

This is the distilled Discord intelligence layer.

Include:
- strongest repeated region combinations
- strongest repeated combat-style archetypes
- repeated relic or pact recommendations
- disagreements or split opinions worth knowing
- "high confidence" vs "speculative" notes

Only carry forward conclusions that repeated across threads or had strong reactions.

### 4. `04_QUERY_EXAMPLES.md`

This is the operator prompt pack for mobile use.

Include copy-pasteable prompts such as:
- `What are the best Desert magic tasks by points?`
- `I want a lazy magic build. Recommend 3 regions and key relics.`
- `Compare Kandarin+Desert+Zeah vs Kandarin+Desert+Asgarnia for mage.`
- `Given this route idea, what am I missing for early points?`
- `Summarize the strongest community consensus for ranged right now.`

Also include one line telling Claude to cite which uploaded doc it used.

### 5. `05_PLANNER_ROUTE_NOTES.md` (optional in the minimal pack, preferred when planner outputs exist)

Use this when the project has a live advisor, route notes, or build-specific planning guidance that should not be mixed into the core fact/reference docs.

Include:
- current focus build or route
- planner/advisor outputs worth preserving
- tradeoffs between region paths
- warnings and opportunity costs
- open questions that Claude should keep explicit instead of smoothing over

## Build Rules

1. Distill, do not dump.
2. Preserve exact names for regions, relics, echo bosses, and major items.
3. Separate verified wiki facts from community consensus.
4. Prefer bullets and short tables over long narrative text.
5. Keep each uploaded file focused enough that Claude can retrieve the right one quickly.
6. Do not include credentials, Google Drive links with edit access, or private account data.

## Minimal Packaging Workflow

1. Refresh source data after new Discord exports:
   - run `discord_analyzer.py`
   - run targeted `leagues_query.py` lookups for topics that need distilled summaries
2. Draft the 4 or 5 documents above from current JSON plus query outputs.
   - start from the template files in this repo
3. Upload them to a Claude Project named `Leagues 6 Planner`.
4. Test on web or iOS with 5-10 concrete planning questions.
5. Tighten weak docs if Claude answers vaguely or mixes wiki facts with Discord speculation.
6. Run the validator before upload:
   - `python3 leagues_project_doc_validator.py validate <docs_dir> --require-planner`
7. If you need a fresh output pack directory first:
   - `python3 leagues_project_doc_pack.py init <docs_dir> --with-planner`
8. If you have structured context JSON and want rendered docs plus a manifest:
   - `python3 leagues_project_doc_pack.py materialize <docs_dir> <context.json> --with-planner`

## Validation Checklist

The Claude Project pass is good enough when Claude can answer all of these without local tool access:
- `What magic tasks give the most points in Desert?`
- `What regions are most recommended for mage and why?`
- `What relics or pact choices are core for magic according to community consensus?`
- `What are the main tradeoffs between two region trios?`
- `What does the community think is strongest for a lazy or dad-style route?`

Failure signs:
- Claude invents data not present in the documents
- Claude cannot distinguish wiki facts from community opinions
- Claude gives generic OSRS advice instead of Leagues-specific answers

## Manifest

The `materialize` command writes `leagues_project_pack.json` alongside the docs.

Use it to track:
- whether planner notes were included
- how many docs were generated
- which structured context file was used
- which source paths fed the pack

## Refresh Policy

Refresh the project docs when any of these happen:
- new major Discord thread exports land
- wiki data changes materially
- April 15 launch reveals invalidate pre-launch assumptions
- the blank planner introduces a new route structure worth capturing

## Non-Overlap Boundary

CCA current ownership:
- blank planner discovery
- planner cloning/adaptation
- Google Drive update capability

This packaging lane should only consume stable outputs from that work, not modify the planner implementation itself.
