# Leagues Claude Project Phase 2 Plan

Purpose: define the next product step for the Leagues Claude Project folder so future CCA and Codex chats stop treating it as a one-off doc export.

## Review Verdict

The current 5-doc upload pack is good enough for static Leagues Q&A, but it is not yet the full product Matthew described.

What it already does well:
- turns repo knowledge into a Claude/iOS-friendly format
- separates some reference material from community opinion
- gives Matthew a mobile-first way to query his current build

What it does not yet do:
- serve as a reliable optimizer for arbitrary goals, builds, regions, relics, or task routes
- expose claim provenance tightly enough for high-trust answers
- refresh itself from official updates plus new community signal without manual re-curation
- cover non-magic paths with the same depth as the current magic-first docs

## New User Directive

The planner must support multiple valid builds on demand.

Implications:
- magic can remain the likely meta combat style
- region trios, relic paths, route order, and optimization targets must stay flexible inputs
- the Claude Project folder must not collapse into one hard-coded Matthew build
- `05_PERSONAL_ROUTE_NOTES.md` should be treated as one current route example, not the universal answer

## Live Signal Check

Checked on Saturday, April 11, 2026:
- Official OSRS site currently shows `Get Ready For Leagues VI: Demonic Pacts - April 15th` dated Wednesday, April 9, 2026 as the latest official Leagues news item.
- `r/2007scape` currently shows fresh discussion around a Demonic Pacts starting guide by Laef, with comments pointing to more task details arriving in the next few days and the full task list near launch.

Implication: the current doc pack is already slightly stale if it still treats April 8 as the newest source boundary.

## Current Gaps

1. Evidence layers are still mixed.
The docs claim some sections are wiki/official facts, but they also include subjective scores and synthesis without a clear provenance tag.

2. Query coverage exceeds document coverage.
`04_QUERY_EXAMPLES.md` asks Claude to answer task-optimization questions that the uploaded docs do not fully support with explicit task tables or point-ranked outputs.

3. The pack is too magic-centered.
It reflects Matthew's current best build well, but it does not yet act like a universal Leagues planning brain for melee, ranged, dad-mode, points-maxing, or alternate route goals.

4. Strategy synthesis is under-modeled.
The current pack has facts, consensus, and one route. It does not yet have a dedicated strategy layer that explains why a recommendation wins versus nearby alternatives.

5. Freshness is manual.
There is no durable CCA-side rule that says the Claude Project folder must be regenerated after official news, `r/2007scape` movement, Discord exports, or launch-day task reveals.

## Product Target

Treat `leagues_query.py` as the source engine for a generated Claude Project folder with three explicit knowledge layers:

1. `facts`
- official/Jagex/wiki-confirmed data
- region unlocks, relic effects, pact rules, echo rewards, tasks, thresholds

2. `meta`
- Discord, Reddit, guide, and community consensus
- repeated archetypes, disputes, confidence ratings, launch-week discoveries

3. `advisor`
- synthesized recommendations built from `facts + meta`
- optimal routes, tradeoffs, region trios, relic paths, task pushes, and build-specific plans

The Claude Project folder should be a generated product on top of those layers, not the primary source of truth.
It should be able to emit more than one build for the same combat style when the user changes regions, relics, AFK tolerance, raid intent, or point-rush goals.

## Recommended Folder Shape

Keep the upload pack at 5 docs, but strengthen what each doc represents:

1. `01_OVERVIEW.md`
- snapshot, freshness date, source windows, confidence rules

2. `02_FACTS_REFERENCE.md`
- official facts only
- no subjective scoring unless labeled as inference

3. `03_COMMUNITY_META.md`
- consensus, disagreements, Reddit/Discord guide synthesis, confidence levels

4. `04_STRATEGY_PLAYBOOKS.md`
- the missing advisor layer
- route templates by goal: magic, melee, ranged, AFK, points rush, dad route, raid-first, casual-first

5. `05_PERSONAL_ROUTE_NOTES.md`
- Matthew's current plan, explicit preferences, and opportunity costs

If the current filenames are kept for compatibility, the content should still move toward these roles.

## Strategy Layer Requirements

The next meaningful leap is not more prose. It is structured strategy generation.

Each strategy/playbook should answer:
- target goal
- supported variants
- required regions
- recommended relic path
- key pact priorities
- high-value early tasks
- major unlock breakpoints
- opportunity costs
- who the build is bad for

Minimum first-pass playbooks:
- magic meta
- magic alternatives by region trio
- melee 2H/blindbag
- ranged crossbow
- ranged thrown/knives-out
- AFK dad route
- points-first unlock rush

Minimum variant support inside the advisor layer:
- same combat style, different 3-region sets
- same regions, different relic philosophies
- same core build, different goals: AFK, points, raid-first, casual-first

## Refresh Rules

Regenerate the Claude Project folder when any of these happen:
- official Leagues news/blog/FAQ update
- notable `r/2007scape` Leagues guide or discovery thread
- new Discord export materially changes consensus
- launch reveals task list details or invalidates pre-launch assumptions
- Matthew changes his build goals or region preferences

The daily scan rule should explicitly include:
- official OSRS news
- `r/2007scape`
- high-signal guide/community sources already in the dataset

## Validation Standard

The Claude Project folder is only "done" when Claude can answer all of these from uploads alone:
- best region trio for a stated goal and why
- best relic path for a stated playstyle and why
- what tradeoffs change if one region is swapped
- what is official fact versus community consensus versus synthesis
- what Matthew should do next for his current route

Failure signs:
- Claude answers generic OSRS advice
- Claude cannot show where a claim came from
- Claude overcommits on disputed community claims
- Claude cannot compare alternate builds cleanly

## Next Actions

1. Keep the current 5-doc pack as `v1` and use it now.
2. Move the next workstream to `v2 = facts + meta + advisor`.
3. Add a dedicated strategy/playbook generation pass sourced from `leagues_query.py`.
4. Tighten freshness/provenance labeling in every generated doc.
5. Re-run the upload pack after the next official task reveal and the next `r/2007scape` scan.
