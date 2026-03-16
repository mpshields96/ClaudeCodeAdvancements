#!/usr/bin/env python3
"""
SPEC-6: Skill Auto-Activation Hook (UserPromptSubmit)

Analyzes user prompts for intent signals and injects skill activation
reminders via additionalContext before Claude processes the prompt.

Uses skill_rules.json for configurable pattern matching:
  - Keyword matching (case-insensitive substring)
  - Intent regex patterns (positive match)
  - Exclude regex patterns (suppress if matched)
  - Priority ordering (highest priority rules fire first)
  - Max activations per prompt (default: 2)

Hook event: UserPromptSubmit
Output: JSON with hookSpecificOutput.additionalContext

Usage (hooks config in settings.local.json):
  "UserPromptSubmit": [{
    "type": "command",
    "command": "python3 /path/to/skill_activator.py"
  }]
"""

import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_RULES_PATH = Path(__file__).parent.parent / "skill_rules.json"


def load_rules(rules_path: Path | None = None) -> dict:
    """
    Load skill rules from JSON file.

    Returns the full rules dict with 'rules' list and 'settings' dict.
    Returns empty structure if file doesn't exist or is invalid.
    """
    if rules_path is None:
        rules_path = Path(
            os.environ.get("SKILL_RULES_PATH", str(DEFAULT_RULES_PATH))
        )

    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"rules": [], "settings": {}}

    if not isinstance(data, dict):
        return {"rules": [], "settings": {}}

    return data


def get_enabled_rules(rules_data: dict) -> list[dict]:
    """Return only enabled rules, sorted by priority (highest first)."""
    rules = rules_data.get("rules", [])
    enabled = [r for r in rules if r.get("enabled", True)]
    enabled.sort(key=lambda r: r.get("priority", 0), reverse=True)
    return enabled


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_keywords(prompt: str, keywords: list[str]) -> bool:
    """
    Check if any keyword appears in the prompt (case-insensitive).

    Returns True if at least one keyword matches.
    """
    prompt_lower = prompt.lower()
    for kw in keywords:
        if kw.lower() in prompt_lower:
            return True
    return False


def match_intent_patterns(prompt: str, patterns: list[str]) -> bool:
    """
    Check if any intent regex pattern matches the prompt.

    Returns True if at least one pattern matches.
    """
    for pattern in patterns:
        try:
            if re.search(pattern, prompt):
                return True
        except re.error:
            continue
    return False


def match_exclude_patterns(prompt: str, patterns: list[str]) -> bool:
    """
    Check if any exclude regex pattern matches the prompt.

    Returns True if prompt should be EXCLUDED (skip this rule).
    """
    for pattern in patterns:
        try:
            if re.search(pattern, prompt):
                return True
        except re.error:
            continue
    return False


def evaluate_rule(prompt: str, rule: dict) -> bool:
    """
    Evaluate a single rule against a prompt.

    A rule matches if:
      1. At least one keyword OR intent pattern matches, AND
      2. No exclude pattern matches

    Returns True if the rule should fire.
    """
    keywords = rule.get("keywords", [])
    intent_patterns = rule.get("intent_patterns", [])
    exclude_patterns = rule.get("exclude_patterns", [])

    # Must match at least one positive signal
    has_keyword = match_keywords(prompt, keywords) if keywords else False
    has_intent = match_intent_patterns(prompt, intent_patterns) if intent_patterns else False

    if not has_keyword and not has_intent:
        return False

    # Exclude patterns override positive matches
    if exclude_patterns and match_exclude_patterns(prompt, exclude_patterns):
        return False

    return True


def find_matching_rules(
    prompt: str,
    rules_data: dict,
    max_activations: int | None = None,
) -> list[dict]:
    """
    Find all rules that match the given prompt.

    Args:
        prompt: The user's prompt text.
        rules_data: Full rules dict from load_rules().
        max_activations: Override max activations per prompt.

    Returns a list of matched rule dicts (up to max_activations).
    """
    if not prompt or not prompt.strip():
        return []

    settings = rules_data.get("settings", {})
    if settings.get("disabled", False):
        return []

    if max_activations is None:
        max_activations = settings.get("max_activations_per_prompt", 2)

    enabled = get_enabled_rules(rules_data)
    matched = []

    for rule in enabled:
        if len(matched) >= max_activations:
            break
        if evaluate_rule(prompt, rule):
            matched.append(rule)

    return matched


# ---------------------------------------------------------------------------
# Hook output
# ---------------------------------------------------------------------------

def build_context_message(matched_rules: list[dict]) -> str:
    """
    Build the additionalContext string from matched rules.

    Returns empty string if no rules matched.
    """
    if not matched_rules:
        return ""

    parts = []
    for rule in matched_rules:
        msg = rule.get("message", "")
        skill = rule.get("skill", "")
        if msg:
            parts.append(f"[Skill suggestion: {skill}] {msg}")

    return "\n".join(parts)


def build_hook_output(context: str) -> dict:
    """
    Build the UserPromptSubmit hook output JSON.

    Returns empty dict (allow, no context) if context is empty.
    """
    if not context:
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Hook entry point. Reads JSON from stdin, writes JSON to stdout.
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Invalid input — allow prompt through, no context
        print("{}")
        sys.exit(0)

    prompt = hook_input.get("prompt", "")
    if not prompt:
        print("{}")
        sys.exit(0)

    rules_data = load_rules()
    matched = find_matching_rules(prompt, rules_data)

    if not matched:
        print("{}")
        sys.exit(0)

    context = build_context_message(matched)
    output = build_hook_output(context)

    # Log activations to stderr for debugging (visible in verbose mode)
    if rules_data.get("settings", {}).get("log_activations", False):
        rule_ids = [r.get("id", "?") for r in matched]
        print(f"[skill_activator] Matched: {', '.join(rule_ids)}", file=sys.stderr)

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
