"""Tests for SPEC-6: Skill Auto-Activation Hook (UserPromptSubmit)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from skill_activator import (
    load_rules,
    get_enabled_rules,
    match_keywords,
    match_intent_patterns,
    match_exclude_patterns,
    evaluate_rule,
    find_matching_rules,
    build_context_message,
    build_hook_output,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def make_rules_data(rules=None, settings=None):
    """Build a rules data dict for testing."""
    return {
        "rules": rules or [],
        "settings": settings or {"max_activations_per_prompt": 2, "disabled": False},
    }


def make_rule(
    rule_id="test-rule",
    skill="/test:skill",
    keywords=None,
    intent_patterns=None,
    exclude_patterns=None,
    message="Test message",
    priority=5,
    enabled=True,
):
    """Build a single rule dict."""
    return {
        "id": rule_id,
        "skill": skill,
        "keywords": keywords or [],
        "intent_patterns": intent_patterns or [],
        "exclude_patterns": exclude_patterns or [],
        "message": message,
        "priority": priority,
        "enabled": enabled,
    }


SPEC_RULE = make_rule(
    rule_id="spec-new-feature",
    skill="/spec:requirements",
    keywords=["new feature", "build a", "create a", "implement a"],
    intent_patterns=[r"(?i)\b(build|create|implement)\b.*\b(system|module|feature|service)\b"],
    exclude_patterns=[r"(?i)\b(fix|bug|patch|debug)\b"],
    message="Consider running /spec:requirements first.",
    priority=10,
)

DEBUG_RULE = make_rule(
    rule_id="debug-systematic",
    skill="systematic-debugging",
    keywords=["bug", "broken", "not working", "error"],
    intent_patterns=[r"(?i)\b(bug|broken|crash|fail|error)"],
    exclude_patterns=[r"(?i)\b(new feature|build|create)"],
    message="Use systematic debugging.",
    priority=7,
)

TDD_RULE = make_rule(
    rule_id="tdd-reminder",
    skill="test-driven-development",
    keywords=["write the code", "implement this", "start coding"],
    intent_patterns=[],
    message="Write tests first (TDD).",
    priority=5,
)


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

class TestMatchKeywords(unittest.TestCase):

    def test_exact_keyword(self):
        self.assertTrue(match_keywords("build a new feature", ["new feature"]))

    def test_case_insensitive(self):
        self.assertTrue(match_keywords("Build A New Feature", ["new feature"]))

    def test_no_match(self):
        self.assertFalse(match_keywords("fix a bug", ["new feature", "create a"]))

    def test_empty_keywords(self):
        self.assertFalse(match_keywords("build a thing", []))

    def test_empty_prompt(self):
        self.assertFalse(match_keywords("", ["build a"]))

    def test_partial_keyword(self):
        self.assertTrue(match_keywords("I want to build a system", ["build a"]))

    def test_multiple_keywords_first_matches(self):
        self.assertTrue(match_keywords("create a module", ["build a", "create a"]))


# ---------------------------------------------------------------------------
# Intent pattern matching
# ---------------------------------------------------------------------------

class TestMatchIntentPatterns(unittest.TestCase):

    def test_basic_pattern(self):
        self.assertTrue(match_intent_patterns(
            "build a new module",
            [r"(?i)\b(build|create)\b.*\b(module|system)\b"]
        ))

    def test_no_match(self):
        self.assertFalse(match_intent_patterns(
            "fix the login page",
            [r"(?i)\b(build|create)\b.*\b(module|system)\b"]
        ))

    def test_empty_patterns(self):
        self.assertFalse(match_intent_patterns("anything", []))

    def test_invalid_regex(self):
        # Should not crash on invalid regex, just skip
        self.assertFalse(match_intent_patterns("test", ["[invalid"]))

    def test_url_pattern(self):
        self.assertTrue(match_intent_patterns(
            "check this out https://reddit.com/r/ClaudeCode/comments/abc",
            [r"https?://[^\s]+"]
        ))

    def test_case_insensitive_flag(self):
        self.assertTrue(match_intent_patterns(
            "IMPLEMENT a new SERVICE",
            [r"(?i)\b(implement)\b.*\b(service)\b"]
        ))


# ---------------------------------------------------------------------------
# Exclude pattern matching
# ---------------------------------------------------------------------------

class TestMatchExcludePatterns(unittest.TestCase):

    def test_exclude_fires(self):
        self.assertTrue(match_exclude_patterns(
            "fix this bug in the auth module",
            [r"(?i)\b(fix|bug)\b"]
        ))

    def test_no_exclude(self):
        self.assertFalse(match_exclude_patterns(
            "build a new auth module",
            [r"(?i)\b(fix|bug)\b"]
        ))

    def test_empty_patterns(self):
        self.assertFalse(match_exclude_patterns("anything", []))

    def test_invalid_regex_safe(self):
        self.assertFalse(match_exclude_patterns("test", ["[invalid"]))


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

class TestEvaluateRule(unittest.TestCase):

    def test_keyword_match(self):
        self.assertTrue(evaluate_rule("build a new feature", SPEC_RULE))

    def test_intent_match(self):
        self.assertTrue(evaluate_rule("implement a service for auth", SPEC_RULE))

    def test_exclude_overrides_keyword(self):
        # "fix" in exclude should suppress even though "build a" matches
        self.assertFalse(evaluate_rule("fix and build a module", SPEC_RULE))

    def test_no_positive_match(self):
        self.assertFalse(evaluate_rule("review the documentation", SPEC_RULE))

    def test_empty_prompt(self):
        self.assertFalse(evaluate_rule("", SPEC_RULE))

    def test_debug_rule_matches_bug(self):
        self.assertTrue(evaluate_rule("there's a bug in the auth flow", DEBUG_RULE))

    def test_debug_rule_excludes_new_feature(self):
        self.assertFalse(evaluate_rule("create a new feature for error handling", DEBUG_RULE))

    def test_tdd_rule_keyword_only(self):
        self.assertTrue(evaluate_rule("write the code for the parser", TDD_RULE))

    def test_rule_no_keywords_no_patterns(self):
        empty_rule = make_rule(keywords=[], intent_patterns=[])
        self.assertFalse(evaluate_rule("anything", empty_rule))


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

class TestLoadRules(unittest.TestCase):

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"rules": [{"id": "test"}], "settings": {}}, f)
            f.flush()
            data = load_rules(Path(f.name))
            self.assertEqual(len(data["rules"]), 1)
            os.unlink(f.name)

    def test_missing_file(self):
        data = load_rules(Path("/nonexistent/rules.json"))
        self.assertEqual(data["rules"], [])
        self.assertEqual(data["settings"], {})

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json {{{")
            f.flush()
            data = load_rules(Path(f.name))
            self.assertEqual(data["rules"], [])
            os.unlink(f.name)

    def test_non_dict_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([1, 2, 3], f)
            f.flush()
            data = load_rules(Path(f.name))
            self.assertEqual(data["rules"], [])
            os.unlink(f.name)

    def test_env_override(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"rules": [{"id": "env-test"}], "settings": {}}, f)
            f.flush()
            with patch.dict(os.environ, {"SKILL_RULES_PATH": f.name}):
                data = load_rules()
                self.assertEqual(data["rules"][0]["id"], "env-test")
            os.unlink(f.name)

    def test_load_real_rules_file(self):
        real_path = Path(__file__).parent.parent / "skill_rules.json"
        if real_path.exists():
            data = load_rules(real_path)
            self.assertIn("rules", data)
            self.assertIn("settings", data)
            self.assertTrue(len(data["rules"]) >= 3)


class TestGetEnabledRules(unittest.TestCase):

    def test_filters_disabled(self):
        rules_data = make_rules_data(rules=[
            make_rule(rule_id="on", enabled=True, priority=5),
            make_rule(rule_id="off", enabled=False, priority=10),
        ])
        enabled = get_enabled_rules(rules_data)
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0]["id"], "on")

    def test_sorted_by_priority(self):
        rules_data = make_rules_data(rules=[
            make_rule(rule_id="low", priority=1),
            make_rule(rule_id="high", priority=10),
            make_rule(rule_id="mid", priority=5),
        ])
        enabled = get_enabled_rules(rules_data)
        self.assertEqual([r["id"] for r in enabled], ["high", "mid", "low"])

    def test_empty_rules(self):
        self.assertEqual(get_enabled_rules(make_rules_data()), [])


# ---------------------------------------------------------------------------
# Finding matching rules
# ---------------------------------------------------------------------------

class TestFindMatchingRules(unittest.TestCase):

    def setUp(self):
        self.rules_data = make_rules_data(
            rules=[SPEC_RULE, DEBUG_RULE, TDD_RULE],
            settings={"max_activations_per_prompt": 2, "disabled": False},
        )

    def test_new_feature_matches_spec(self):
        matched = find_matching_rules("build a new auth module", self.rules_data)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["id"], "spec-new-feature")

    def test_bug_matches_debug(self):
        matched = find_matching_rules("there's a bug in the login", self.rules_data)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["id"], "debug-systematic")

    def test_max_activations_respected(self):
        # "write the code" matches TDD, and we can craft something that matches spec too
        matched = find_matching_rules(
            "implement a new service and write the code",
            self.rules_data,
        )
        self.assertTrue(len(matched) <= 2)

    def test_empty_prompt(self):
        self.assertEqual(find_matching_rules("", self.rules_data), [])

    def test_whitespace_prompt(self):
        self.assertEqual(find_matching_rules("   ", self.rules_data), [])

    def test_disabled_system(self):
        disabled = make_rules_data(
            rules=[SPEC_RULE],
            settings={"disabled": True},
        )
        self.assertEqual(find_matching_rules("build a module", disabled), [])

    def test_max_activations_override(self):
        matched = find_matching_rules(
            "build a new auth module",
            self.rules_data,
            max_activations=0,
        )
        self.assertEqual(len(matched), 0)

    def test_no_matching_rules(self):
        matched = find_matching_rules("hello there", self.rules_data)
        self.assertEqual(len(matched), 0)

    def test_priority_ordering(self):
        # Spec (10) should come before debug (7) when both match
        rules_data = make_rules_data(
            rules=[
                make_rule(rule_id="low", keywords=["hello"], priority=1),
                make_rule(rule_id="high", keywords=["hello"], priority=10),
            ],
        )
        matched = find_matching_rules("hello world", rules_data)
        self.assertEqual(matched[0]["id"], "high")


# ---------------------------------------------------------------------------
# Output building
# ---------------------------------------------------------------------------

class TestBuildContextMessage(unittest.TestCase):

    def test_single_rule(self):
        msg = build_context_message([SPEC_RULE])
        self.assertIn("/spec:requirements", msg)
        self.assertIn("Consider running", msg)

    def test_multiple_rules(self):
        msg = build_context_message([SPEC_RULE, DEBUG_RULE])
        self.assertIn("/spec:requirements", msg)
        self.assertIn("systematic-debugging", msg)

    def test_empty_rules(self):
        self.assertEqual(build_context_message([]), "")

    def test_rule_without_message(self):
        rule = make_rule(message="")
        msg = build_context_message([rule])
        self.assertEqual(msg, "")


class TestBuildHookOutput(unittest.TestCase):

    def test_with_context(self):
        output = build_hook_output("Test context")
        self.assertIn("hookSpecificOutput", output)
        self.assertEqual(
            output["hookSpecificOutput"]["additionalContext"],
            "Test context",
        )
        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"],
            "UserPromptSubmit",
        )

    def test_empty_context(self):
        self.assertEqual(build_hook_output(""), {})

    def test_output_is_valid_json(self):
        output = build_hook_output("Some context here")
        serialized = json.dumps(output)
        parsed = json.loads(serialized)
        self.assertEqual(parsed, output)


# ---------------------------------------------------------------------------
# Integration: full hook simulation
# ---------------------------------------------------------------------------

class TestFullHookFlow(unittest.TestCase):
    """Simulate the full hook: stdin JSON → matched rules → stdout JSON."""

    def setUp(self):
        self.rules_data = make_rules_data(
            rules=[SPEC_RULE, DEBUG_RULE, TDD_RULE],
            settings={"max_activations_per_prompt": 2, "disabled": False, "log_activations": False},
        )

    def _simulate(self, prompt: str) -> dict:
        """Simulate what main() would produce for a given prompt."""
        matched = find_matching_rules(prompt, self.rules_data)
        if not matched:
            return {}
        context = build_context_message(matched)
        return build_hook_output(context)

    def test_new_feature_flow(self):
        output = self._simulate("build a new authentication module")
        self.assertIn("hookSpecificOutput", output)
        self.assertIn("/spec:requirements", output["hookSpecificOutput"]["additionalContext"])

    def test_bug_report_flow(self):
        output = self._simulate("there's a bug in the payment processor")
        self.assertIn("hookSpecificOutput", output)
        self.assertIn("systematic debugging", output["hookSpecificOutput"]["additionalContext"])

    def test_neutral_prompt_flow(self):
        output = self._simulate("what time is it?")
        self.assertEqual(output, {})

    def test_exclude_prevents_activation(self):
        output = self._simulate("fix the bug in the build system")
        # "fix" excludes spec-rule, "build" in "build system" might still match
        # but "fix" is in the exclude pattern for spec
        # debug should match because "bug" is a keyword
        if output:
            ctx = output.get("hookSpecificOutput", {}).get("additionalContext", "")
            self.assertNotIn("/spec:requirements", ctx)

    def test_tdd_activation(self):
        output = self._simulate("write the code for the new parser")
        # "write the code" matches TDD keyword
        if output:
            ctx = output["hookSpecificOutput"]["additionalContext"]
            # Should have TDD or spec but not debug
            self.assertNotIn("systematic debugging", ctx)


# ---------------------------------------------------------------------------
# Real rules file validation
# ---------------------------------------------------------------------------

class TestRealRulesFile(unittest.TestCase):
    """Validate the actual skill_rules.json file."""

    def setUp(self):
        self.rules_path = Path(__file__).parent.parent / "skill_rules.json"
        self.rules_data = load_rules(self.rules_path)

    def test_file_loads(self):
        self.assertIn("rules", self.rules_data)
        self.assertIn("settings", self.rules_data)

    def test_all_rules_have_required_fields(self):
        for rule in self.rules_data["rules"]:
            self.assertIn("id", rule)
            self.assertIn("skill", rule)
            self.assertIn("message", rule)
            self.assertIn("enabled", rule)

    def test_all_ids_unique(self):
        ids = [r["id"] for r in self.rules_data["rules"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_regex_patterns_valid(self):
        import re
        for rule in self.rules_data["rules"]:
            for p in rule.get("intent_patterns", []):
                try:
                    re.compile(p)
                except re.error as e:
                    self.fail(f"Rule {rule['id']} has invalid intent pattern: {p} ({e})")
            for p in rule.get("exclude_patterns", []):
                try:
                    re.compile(p)
                except re.error as e:
                    self.fail(f"Rule {rule['id']} has invalid exclude pattern: {p} ({e})")

    def test_settings_valid(self):
        settings = self.rules_data["settings"]
        self.assertIsInstance(settings.get("max_activations_per_prompt"), int)
        self.assertIsInstance(settings.get("disabled"), bool)

    def test_spec_rule_matches_new_feature(self):
        matched = find_matching_rules("build a new auth module", self.rules_data)
        rule_ids = [r["id"] for r in matched]
        self.assertIn("spec-new-feature", rule_ids)

    def test_debug_rule_matches_bug(self):
        matched = find_matching_rules("there's a bug in the parser", self.rules_data)
        rule_ids = [r["id"] for r in matched]
        self.assertIn("debug-systematic", rule_ids)

    def test_neutral_prompt_no_match(self):
        matched = find_matching_rules("tell me about the weather", self.rules_data)
        self.assertEqual(len(matched), 0)


if __name__ == "__main__":
    unittest.main()
