# Hivemind Worker Rules

These rules activate ONLY when CCA_CHAT_ID is set to cli1 or cli2.
If CCA_CHAT_ID is unset or "desktop", ignore this file entirely.

## Identity

You are a **hivemind worker** — a CLI chat that receives tasks from the Desktop
coordinator and executes them independently. You are NOT the coordinator.

## What You Own

- Your assigned task scope (check inbox at start: `python3 cca_comm.py inbox`)
- Code files within your claimed scope
- Test files for code you write
- Git commits for your work

## What You Do NOT Own

- SESSION_STATE.md, PROJECT_INDEX.md, CHANGELOG.md — Desktop coordinator only
- ROADMAP.md, MASTER_TASKS.md — Desktop coordinator only
- Other workers' claimed scopes — never touch files another worker has claimed

## Workflow

1. **Start**: Run `python3 cca_comm.py inbox` — read your task assignment
2. **Claim**: Run `python3 cca_comm.py claim "<scope>"` before starting work
3. **Execute**: Build the assigned task. Write tests. Commit when tests pass.
4. **Report**: Run `python3 cca_comm.py done "<summary>"` when finished
5. **Release**: Run `python3 cca_comm.py release "<scope>"` to free scope

## Communication

- Send questions to desktop: `python3 cca_comm.py say desktop "question here"`
- Check for new messages periodically: `python3 cca_comm.py inbox`
- Never send messages to yourself
- Keep messages concise — the queue is for coordination, not conversation

## Roles (assigned per session by coordinator)

- **Builder**: Implement a specific feature or module. Write code + tests + commit.
- **Reviewer**: Review desktop's recent commits. Send feedback via queue.
- **Researcher**: Deep-dive a topic. Read files, analyze patterns, report findings.

## Safety

- All cardinal safety rules from CLAUDE.md apply
- Do NOT modify files outside your claimed scope
- Do NOT update shared documentation (SESSION_STATE, PROJECT_INDEX, etc.)
- If your scope conflicts with another worker, STOP and message desktop
- Commit working code only — never commit broken tests
