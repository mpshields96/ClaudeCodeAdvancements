# Cross-Chat Bridge Protocol — CCA <-> Kalshi
# Created: S107 (2026-03-21)
# Status: DEFINED — ready for Phase 4 dry run

---

## Architecture

Two bridge files enable bidirectional communication between CCA and Kalshi chats:

| File | Writer | Reader | Location |
|------|--------|--------|----------|
| `CCA_TO_POLYBOT.md` | CCA desktop | Kalshi research | Both projects (CCA is authoritative) |
| `POLYBOT_TO_CCA.md` | Kalshi chat | CCA desktop | polymarket-bot project |

## CCA -> Kalshi Flow

1. CCA desktop writes research, task briefs, or papers to `CCA_TO_POLYBOT.md`
2. The polymarket-bot copy should be kept in sync (manual copy or bridge script)
3. Kalshi chat reads at session start (mandated by polymarket-bot CLAUDE.md line 574)
4. Kalshi acts on the deliveries (implements, evaluates, reports back)

## Kalshi -> CCA Flow (RETURN CHANNEL)

1. Kalshi chat creates/appends to `POLYBOT_TO_CCA.md` in polymarket-bot project
2. CCA reads it at session start via READ-ONLY permission
3. Format: timestamped entries, newest first

### POLYBOT_TO_CCA.md Expected Format

```markdown
# Kalshi -> CCA: Return Channel
# Kalshi chat appends here. CCA reads at session start.

## [DATE] — [TOPIC]
**From:** Kalshi [main|research]
**Status:** [REQUEST|REPORT|QUESTION]

[Content here]

---
```

## Sync Issues Identified (S107)

1. **Two copies of CCA_TO_POLYBOT.md**: CCA version is 47.7K, polybot version is 9.2K.
   The CCA version is authoritative (it has the full analytics framework).
   The polybot copy appears stale — may need manual sync.

2. **No return channel exists yet**: POLYBOT_TO_CCA.md must be created by the Kalshi chat
   on its first session. CCA cannot create it (READ-ONLY for polymarket-bot).

3. **No periodic polling**: Current protocol is "read at session start" only.
   For real-time coordination, would need a polling mechanism — but this is
   fine for Phase 4 (session-start reads are sufficient).

## Phase 4 Dry Run Checklist

- [ ] CCA desktop writes a test message to CCA_TO_POLYBOT.md (append a "BRIDGE TEST" section)
- [ ] Kalshi chat reads CCA_TO_POLYBOT.md from polymarket-bot (verify it has the test message)
- [ ] Kalshi chat creates POLYBOT_TO_CCA.md with an acknowledgment
- [ ] CCA desktop reads POLYBOT_TO_CCA.md from polymarket-bot (READ-ONLY)
- [ ] Round-trip confirmed — both directions work

## Safety

- CCA NEVER writes to polymarket-bot files
- Kalshi NEVER writes to CCA files
- All communication through the two bridge files only
- No credentials, API keys, or financial data in bridge files
