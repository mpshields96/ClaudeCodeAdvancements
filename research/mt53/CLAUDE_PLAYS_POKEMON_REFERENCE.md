# Claude Plays Pokemon — Complete Reference Document
# Source: r/ClaudePlaysPokemon subreddit sidebar + architecture diagram
# Captured: 2026-03-26, Session 201
# Status: VERBATIM — do not edit or summarize

---

## SIDEBAR TEXT (Verbatim from r/ClaudePlaysPokemon)

### How does Claude Play Pokemon?

**What is This?** This is an experiment where a large language model (LLM) named Claude plays through the classic Game Boy game Pokemon Red, entirely on its own. Unlike traditional game bots that follow predetermined rules, Claude can see what's happening, understand the game state, and make decisions, similar to how a human player would.

**Background** This project is a passion project made by a person who loves Claude and loves Pokemon. As Anthropic releases new models, we'll kick off new runs and see how they do -- one of these days Claude will be a Pokemon Master!

**Watch the Adventure Unfold** Throughout the stream, you'll see Claude encounter challenges, develop strategies, raise Pokemon, battle trainers, and make progress toward becoming a Pokemon Champion. You can watch its thought process in real-time, showing how an AI approaches problem-solving in an interactive environment.

Claude can be a little silly sometimes -- tune in and enjoy the show!

### How it works:

The system combines several components that enable Claude to play Pokemon:

**Game Interface:** A custom interface that allows Claude to control the game by pressing virtual buttons.

**Screenshot Analysis:** Claude looks at screenshots of the game and interprets what's happening on screen. Claude's ability to understand Game Boy screens isn't great -- you'll often see it misinterpret what it's seeing.

**Knowledge Base:** Claude maintains a dynamic set of notes about the game world, storing information about locations, Pokemon team status, and game mechanics.

**Navigation System:** A pathfinding tool helps Claude navigate efficiently by finding paths to a spot on the screen.

**Memory Reader:** Claude also gets a few tidbits of information from the memory of the game, like its current location and party. This helps prevent Claude from getting confused if it misinterprets the screen.

When Claude wants to act, it can:
- Press game buttons in sequence (A, B, Up, Down, Left, Right, Start, Select)
- Navigate to specific coordinates on the screen
- Update its knowledge base with new information it discovers

**Note:** We're using Danny-E 33 + FroggestSpirit's full color patch, which also helps Claude see the screen a bit better!

---

## ARCHITECTURE DIAGRAM (Verbatim transcription of visual guide)

### Title: "Claude Plays Pokemon, a Visual Guide"

### About the Knowledge Base

The knowledge base gives Claude access to long term memory. Its basically just a Python dictionary, and it is rendered like this:

```xml
<section id="pokemon">
I like pikachu because its cute and I like
how it electrocutes people
</section>
<section id="brock">
Brock stinks and I kicked his ass back
on step 3932
</section>
...
```

### The Tools

#### 1. update_knowledge_base
- **What:** Add to, edit, or delete content in knowledge base
- **How:** Claude specifies an operation + content
- **Tool Result:** Acknowledgement

#### 2. use_emulator
- **What:** Executes a series of button presses + optional pauses for time to pass
- **How:** Claude writes an array that looks like `['a', 'b', 'start', 'select']`
- **Tool Result:** Screenshot
- Also returns: State from RAM (parsed directly from the RAM of the game — "Claude Code is very good at this task")
- Also returns: Helpful reminders
- Note: The overlay (on screenshot) comes from reading the tiles on the screen and checking if they are walkable

#### 3. navigator
- **What:** Finds the path to selected coordinates on screen, and executes button presses to get there. Calls use_emulator for execution.
- **How:** Claude specifies coordinates in its current view, i.e. `(6, 21)`
- **Tool Result (If Failed to Find):** Return helpful error message
- **Tool Result (If Success):** Success message + Result from use_emulator

### The Prompt

Components fed into each call:
1. **Tool Definitions**
2. **System Prompt** — "System prompt is mostly just tips + tricks about tools + a few short reminders about things Claude is bad at (i.e. don't trust your vision, use your knowledge base more often than you think)"
3. **Knowledge Base**
4. **Blurb about how summaries work**

### Conversation History

Structured as alternating:
- Tool Use
- Tool Result
- Tool Use
- Tool Result
- ...

### The Core Loop

1. **Compose Prompt + Call Model**
2. **Resolve Tools**
3. **Check for Summarization**
4. **Save State**
(loops back to step 1)

### Summarization / Managing Long Context

> "Rollouts are way too long for the 200k context window, so we need some way to manage context. I've found progressive summarization to work well"

Process:
1. Once conversation history > max_turns, we trigger a summarization event
2. This has Claude write a summary of their recent progress / what happened in the last max_turns
3. Then we clear the full conversation history and insert the summary as the first assistant message, and Claude resumes its journey
4. Finally, another LLM is called to inspect the first LLM's knowledge base and to provide feedback — this helps ensure the agent does more frequent maintenance of its knowledge base

---

## KEY ARCHITECTURAL PATTERNS (extracted for MT-53)

### Pattern 1: Tool-Mediated Game Control
- 3 tools only: update_knowledge_base, use_emulator, navigator
- Minimal tool surface — Claude decides what to do, tools execute
- use_emulator returns screenshot + RAM state + overlay (walkability tiles)

### Pattern 2: Knowledge Base as Long-Term Memory
- Python dictionary with XML-like sections
- Claude reads AND writes its own memory
- Persistent across summarization events
- Separate from conversation history

### Pattern 3: Progressive Summarization for Context Management
- 200K context window is insufficient for long game sessions
- max_turns threshold triggers summarization
- Claude self-summarizes recent progress
- History cleared, summary becomes first message
- Second LLM audits knowledge base after summarization (quality control)

### Pattern 4: RAM Reading as Ground Truth
- Memory reader provides objective game state (location, party)
- Compensates for Claude's poor screenshot interpretation
- "Claude's ability to understand Game Boy screens isn't great"
- RAM data prevents confusion from misinterpreted visuals

### Pattern 5: Walkability Overlay
- Tile data read from screen memory
- Overlay shows which tiles are walkable
- Augments screenshot with structural navigation data
- Helps navigator tool find valid paths

### Pattern 6: Zero-Harness Approach
- No predetermined rules or decision trees
- Claude sees game state and makes decisions like a human would
- System prompt = tips/tricks + reminders about weaknesses
- No reward function, no RL — pure LLM reasoning

---

## RELEVANCE TO MT-53

This is the canonical reference architecture for Claude playing Pokemon. Our MT-53 implementation
should BUILD on this proven framework. Key decisions validated by this project:
1. RAM reading is essential (not optional) — Claude's vision is unreliable for Game Boy screens
2. Knowledge base (persistent memory) is essential — game sessions outlast context windows
3. Progressive summarization solves the context problem — proven at 200K window
4. Minimal tool surface (3 tools) is sufficient — don't over-engineer
5. Navigator with pathfinding is a separate tool from raw button presses — good separation
6. Second LLM for knowledge base auditing — novel and valuable pattern
7. Full color patch helps Claude's vision — visual preprocessing matters
