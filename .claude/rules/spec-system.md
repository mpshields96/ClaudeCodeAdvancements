---
globs: spec-system/**
---

# Spec System Rules (Frontier 2)

- Non-negotiable sequence: requirements.md -> design.md -> tasks.md -> implement
- User must APPROVE each document before the next is generated
- No code during requirements or design phases
- Implementation runs ONE task at a time, commit after each
- Tasks must be atomic (~100-500 LOC), testable, committable

## Compaction-Resilient Format
Structure all task lists as numbered todo items — this format survives context compaction.
Claude Code preserves numbered todo lists through compression, so specs using this format
remain intact even in long sessions.

## Architecture Diagram Step
Before implementation, generate a mermaid architecture diagram in the design.md.
Mermaid renders natively in GitHub, VS Code, and Obsidian — zero dependencies.
This serves as a reviewable visual spec artifact.
