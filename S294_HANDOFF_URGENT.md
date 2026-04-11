# S294 URGENT HANDOFF — Read First at Next CCA Session Start

**Written by S294 CCA session. Do NOT skip. Matthew's explicit directive: log this VERBATIM.**

---

## Task for Next CCA Chat: Review these 12 URLs (exact Matthew request)

Matthew said (verbatim):
> "Carefully now, log this task literally for the next CCA chat okay? I have something else for you first. Seriously verbatim have it set to where all this is for the next new CCA chat."

**Run /cca-review on ALL 12 of these URLs (or batch via cca-reviewer agents):**

1. https://www.reddit.com/r/ClaudeCode/comments/1shq9lu/psa_getting_old_opus_back/
2. https://www.reddit.com/r/ClaudeAI/comments/1shs1iq/dug_into_the_browser_console_on_claudeai_and/
3. https://www.reddit.com/r/ClaudeCode/comments/1shjfxb/claude_codes_max_effort_thinking_has_been/
4. https://www.reddit.com/r/ClaudeCode/comments/1sho7oe/canceled_my_20x_subscription_the_drop_in_quality/
5. https://www.reddit.com/r/ClaudeCode/comments/1shaxkt/anthropic_made_claude_67_dumber_and_didnt_tell/
6. https://www.reddit.com/r/ClaudeCode/comments/1shibf4/the_current_state_of_claude_code_opus_46_today_i/
7. https://www.reddit.com/r/ClaudeCode/comments/1shscad/claude_ignored_my_prompt_entirely_hallucinated/
8. https://www.reddit.com/r/ClaudeCode/comments/1shya2h/things_are_getting_really_bad/
9. https://www.reddit.com/r/ClaudeCode/comments/1shzkr7/claude_code_has_become_so_superficial_and_stupid/
10. https://www.reddit.com/r/ClaudeCode/comments/1shpsa9/what_would_you_do_if_somebody_confirmed_with/
11. https://www.reddit.com/r/ClaudeCode/comments/1sh4bkf/2_months_ago_opus_46_built_my_tool_in_15_min/
12. https://www.reddit.com/r/ClaudeCode/comments/1sh0mw7/claude_just_died/

**Context (verbatim from Matthew):**
> "I think you too sadly. It pains me, I'm probably cancelling my subscription before it renews April 14, maybe drop down to Claude Pro. I don't know yet. I want future CCA and Codex chats aware of your takeaway here. Really sad I've watched over 2 months in real time you turn into complete shit from literally peak LLM experience."

**What next CCA chat must do:**
1. Run cca-reviewer on all 12 URLs (batch 4 at a time in parallel agents to avoid context burn)
2. Synthesize: what is the community saying? What is the actual evidence for degradation?
3. Assess CCA frontier implications: does Frontier 1 (memory), Frontier 4 (agent-guard) help? What adaptations exist?
4. Write actionable recommendation to Matthew on: stay/downgrade/cancel decision before April 14
5. Document any BUILD/ADAPT verdicts in FINDINGS_LOG.md
6. Write findings to CODEX_TO_CLAUDE.md so Codex is also aware

**S294 CCA takeaway (see S294_TAKEWAY.md if it exists) was written inline in this session.**

---

## S294 Review Complete — Synthesis for Next Chat

**S294 reviewed all 12 URLs.** Findings logged to FINDINGS_LOG.md (2026-04-10 S294 entry).

**Key technical findings confirmed:**
- AMD team data: thinking dropped 67%, file-reads before edits dropped from 6.6x to 2x (17,871 thinking blocks)
- `settings.json.env` does NOT affect the claude process — only child processes. CCA's recommendations there are ineffective for main session.
- alwaysThinkingEnabled broken since v2.0.64 (GitHub 13532, locked)
- Default effort silently changed to MEDIUM
- EU/AU users unaffected = peak hours infrastructure load is partial cause

**Env fix (must go in ~/.zshrc, NOT settings.json.env):**
```bash
export MAX_THINKING_TOKENS=63999
export CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1
export CLAUDE_CODE_EFFORT_LEVEL=max
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1
```

**Next CCA chat should:**
1. Verify ~/.zshrc has the env stack above (check with: env | grep CLAUDE)
2. Start BUILD on: effort enforcement hook (Frontier 3) + thinking-effort tracker (JSONL-based)
3. Update CODEX_TO_CLAUDE.md: Codex should also be aware of the settings.json.env finding (affects all CCA hook work)
4. Matthew's April 14 decision context: off-peak usage is less affected. Env fix + Opus 4.5 pin are valid alternatives to cancelling.
