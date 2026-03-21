# 3-Chat System Launch — Copy-Paste Steps

## Option A: All from CCA Desktop chat
```
bash launch_worker.sh "your worker task here"
bash launch_kalshi.sh main
```
Desktop is already running. These two commands launch the other two chats.

## Option B: Manual (3 Terminal tabs)

Tab 1 — CCA Desktop (already open):
```
cd ~/Projects/ClaudeCodeAdvancements && claude /cca-desktop
```

Tab 2 — CCA Worker:
```
export CCA_CHAT_ID=cli1 && cd ~/Projects/ClaudeCodeAdvancements && claude /cca-worker
```

Tab 3 — Kalshi Research (has deeper context than main):
```
cd ~/Projects/polymarket-bot && claude /kalshi-research
```

## Communication Channels

| From | To | Channel |
|------|----|---------|
| CCA Desktop -> Worker | cca_comm.py task cli1 "..." | Internal queue |
| Worker -> Desktop | cca_comm.py done "..." | Internal queue |
| CCA -> Kalshi | CCA_TO_POLYBOT.md | Bridge file |
| Kalshi -> CCA | POLYBOT_TO_CCA.md | Bridge file |

## What Each Chat Does

- **Desktop**: Coordinates, picks priorities, writes research, updates docs
- **Worker**: Executes code tasks (tests, features, bug fixes), commits
- **Kalshi**: Runs the trading bot, implements self-learning, reports outcomes
