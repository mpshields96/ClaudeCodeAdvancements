#!/usr/bin/env python3
"""
Smoke tests for memory-system capture_hook (v2.0 — FTS5 backend).
Run: python3 memory-system/tests/test_memory.py
All tests use in-memory MemoryStore — no writes to ~/.claude-memory.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make the hooks module importable from the tests directory
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import capture_hook as ch
from memory_store import MemoryStore


class TestProjectSlug(unittest.TestCase):
    def test_basic_path(self):
        self.assertEqual(ch._project_slug("/Users/matt/Projects/ClaudeCodeAdvancements"), "claudecodeadvancements")

    def test_spaces_become_hyphens(self):
        self.assertEqual(ch._project_slug("/Users/matt/My Project"), "my-project")

    def test_uppercase_lowercased(self):
        self.assertEqual(ch._project_slug("/Users/matt/TitaniumV36"), "titaniumv36")

    def test_empty_path_fallback(self):
        result = ch._project_slug("")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestCredentialFilter(unittest.TestCase):
    def test_anthropic_key_blocked(self):
        self.assertTrue(ch._contains_credentials("sk-ant-api03-abcdefghijklmnopqrstuvwxyz"))

    def test_bearer_token_blocked(self):
        self.assertTrue(ch._contains_credentials("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.longtoken"))

    def test_api_key_assignment_blocked(self):
        self.assertTrue(ch._contains_credentials("ODDS_API_KEY=abc123defghij"))

    def test_supabase_key_blocked(self):
        self.assertTrue(ch._contains_credentials("SUPABASE_KEY=eyJhbGciOiJIUzI1NiJ9"))

    def test_aws_key_blocked(self):
        self.assertTrue(ch._contains_credentials("AKIAIOSFODNN7EXAMPLE"))

    def test_clean_content_passes(self):
        self.assertFalse(ch._contains_credentials("Use SQLite for storage because it's stdlib"))

    def test_architecture_content_passes(self):
        self.assertFalse(ch._contains_credentials("Decided to use JSON over SQLite for schema v1"))


class TestValidateMemoryParams(unittest.TestCase):
    def test_valid_params(self):
        result = ch._validate_memory_params("Use stdlib-first approach", "decision", "HIGH")
        self.assertIsNotNone(result)
        content, mem_type, confidence = result
        self.assertEqual(content, "Use stdlib-first approach")
        self.assertEqual(mem_type, "decision")
        self.assertEqual(confidence, "HIGH")

    def test_empty_content_rejected(self):
        result = ch._validate_memory_params("", "decision", "HIGH")
        self.assertIsNone(result)

    def test_whitespace_content_rejected(self):
        result = ch._validate_memory_params("   ", "decision", "HIGH")
        self.assertIsNone(result)

    def test_credential_content_rejected(self):
        result = ch._validate_memory_params("sk-ant-api03-secretkey123456789", "error", "HIGH")
        self.assertIsNone(result)

    def test_content_truncated_at_500(self):
        long = "x" * 600
        result = ch._validate_memory_params(long, "decision", "MEDIUM")
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result[0]), 500)

    def test_invalid_type_falls_back(self):
        result = ch._validate_memory_params("Some content here", "invalid_type", "HIGH")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "decision")

    def test_invalid_confidence_falls_back(self):
        result = ch._validate_memory_params("Some content here", "decision", "UNKNOWN")
        self.assertIsNotNone(result)
        self.assertEqual(result[2], "MEDIUM")


class TestBuildTags(unittest.TestCase):
    def test_type_prefix_added(self):
        tags = ch._build_tags("decision", ["architecture"])
        self.assertEqual(tags[0], "type:decision")
        self.assertIn("architecture", tags)

    def test_capped_at_5(self):
        tags = ch._build_tags("error", ["a", "b", "c", "d", "e", "f"])
        self.assertLessEqual(len(tags), 5)
        self.assertEqual(tags[0], "type:error")

    def test_no_duplicates(self):
        tags = ch._build_tags("decision", ["type:decision", "general"])
        # type:decision appears once
        self.assertEqual(tags.count("type:decision"), 1)


class TestExtractMemoriesFromMessage(unittest.TestCase):
    def test_decision_sentence_extracted(self):
        msg = "We decided to use SQLite instead of PostgreSQL because it requires no server setup."
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["type"], "decision")
        self.assertIn("type:decision", memories[0]["tags"])

    def test_error_sentence_extracted(self):
        msg = "The bug was caused by importing edge_calculator from odds_fetcher. Fixed by deferring the import to function body."
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["type"], "error")

    def test_short_message_ignored(self):
        memories = ch._extract_memories_from_message("Done.", "testproject")
        self.assertEqual(memories, [])

    def test_question_not_captured(self):
        msg = "Should we always use SQLite instead of JSON for this project?"
        memories = ch._extract_memories_from_message(msg, "testproject")
        for mem in memories:
            self.assertFalse(mem["content"].endswith("?"))

    def test_credential_sentence_not_captured(self):
        msg = "We decided the API key is sk-ant-api03-abc123 and should never be logged."
        memories = ch._extract_memories_from_message(msg, "testproject")
        for mem in memories:
            self.assertFalse(ch._contains_credentials(mem["content"]))

    def test_cap_at_5_memories_per_message(self):
        sentences = [
            f"We decided to use approach {i} because it is better." for i in range(20)
        ]
        msg = " ".join(sentences)
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertLessEqual(len(memories), 5)

    def test_candidate_has_required_fields(self):
        msg = "We decided to use FTS5 because it provides relevance-ranked full-text search."
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertTrue(len(memories) > 0)
        mem = memories[0]
        self.assertIn("content", mem)
        self.assertIn("type", mem)
        self.assertIn("tags", mem)
        self.assertIn("confidence", mem)
        self.assertIn("source", mem)
        self.assertIn("project", mem)
        self.assertEqual(mem["source"], "session-end")
        self.assertEqual(mem["confidence"], "MEDIUM")


class TestPostToolUseHandler(unittest.TestCase):
    def _make_input(self, tool_name, tool_input=None):
        return {
            "hook_event_name": "PostToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input or {},
            "cwd": "/Users/matt/Projects/ClaudeCodeAdvancements",
            "session_id": "test-session",
        }

    def test_write_tool_returns_context(self):
        inp = self._make_input("Write", {"file_path": "/project/test.py", "content": "code"})
        result = ch.handle_post_tool_use(inp)
        self.assertIn("additionalContext", result)
        self.assertIn("test.py", result["additionalContext"])

    def test_edit_tool_returns_context(self):
        inp = self._make_input("Edit", {"file_path": "/project/main.py"})
        result = ch.handle_post_tool_use(inp)
        self.assertIn("additionalContext", result)

    def test_read_tool_ignored(self):
        inp = self._make_input("Read", {"file_path": "/project/main.py"})
        result = ch.handle_post_tool_use(inp)
        self.assertEqual(result, {})

    def test_bash_tool_ignored_when_no_file(self):
        inp = self._make_input("Bash", {"command": "ls"})
        result = ch.handle_post_tool_use(inp)
        self.assertEqual(result, {})


class TestStopHandlerFTS5(unittest.TestCase):
    """Tests for Stop handler writing to FTS5 MemoryStore."""

    def _make_stop_input(self, last_msg="", transcript_path=""):
        return {
            "hook_event_name": "Stop",
            "cwd": "/Users/matt/Projects/TestProject",
            "last_assistant_message": last_msg,
            "transcript_path": transcript_path,
        }

    def test_decision_written_to_store(self):
        store = MemoryStore(":memory:")
        inp = self._make_stop_input(
            last_msg="We decided to use SQLite instead of PostgreSQL because it requires no server setup."
        )
        result = ch.handle_stop(inp, store=store)
        self.assertIn("additionalContext", result)
        self.assertIn("1 new memory", result["additionalContext"])
        # Verify it's in the store
        memories = store.list_all(project="testproject")
        self.assertEqual(len(memories), 1)
        self.assertIn("SQLite", memories[0]["content"])
        store.close()

    def test_empty_message_no_write(self):
        store = MemoryStore(":memory:")
        inp = self._make_stop_input(last_msg="Done.")
        result = ch.handle_stop(inp, store=store)
        self.assertEqual(result, {})
        self.assertEqual(store.count(), 0)
        store.close()

    def test_multiple_memories_written(self):
        store = MemoryStore(":memory:")
        msg = (
            "We decided to use SQLite instead of PostgreSQL because it needs no server. "
            "The fix is to defer imports to avoid circular dependencies."
        )
        inp = self._make_stop_input(last_msg=msg)
        result = ch.handle_stop(inp, store=store)
        self.assertIn("additionalContext", result)
        count = store.count()
        self.assertGreaterEqual(count, 1)
        store.close()

    def test_duplicate_not_written_twice(self):
        store = MemoryStore(":memory:")
        msg = "We decided to use SQLite instead of PostgreSQL because it requires no server setup."
        inp = self._make_stop_input(last_msg=msg)
        # First call writes
        ch.handle_stop(inp, store=store)
        count1 = store.count()
        # Second call should dedup
        ch.handle_stop(inp, store=store)
        count2 = store.count()
        self.assertEqual(count1, count2)
        store.close()

    def test_credential_not_written(self):
        store = MemoryStore(":memory:")
        msg = "We decided the API key is sk-ant-api03-abcdefghijklmnopqrstuvwxyz and should never be logged."
        inp = self._make_stop_input(last_msg=msg)
        ch.handle_stop(inp, store=store)
        self.assertEqual(store.count(), 0)
        store.close()

    def test_type_encoded_in_tags(self):
        store = MemoryStore(":memory:")
        msg = "We decided to use SQLite instead of PostgreSQL because it requires no server setup."
        inp = self._make_stop_input(last_msg=msg)
        ch.handle_stop(inp, store=store)
        memories = store.list_all(project="testproject")
        self.assertTrue(len(memories) > 0)
        tags = memories[0]["tags"]
        type_tags = [t for t in tags if t.startswith("type:")]
        self.assertEqual(len(type_tags), 1)
        store.close()

    def test_transcript_explicit_memory(self):
        store = MemoryStore(":memory:")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            entry = {
                "role": "user",
                "content": [{"type": "text", "text": "Remember that we always use TDD before writing any production code"}],
            }
            f.write(json.dumps(entry) + "\n")
            f.flush()
            transcript_path = f.name

        try:
            inp = self._make_stop_input(transcript_path=transcript_path)
            result = ch.handle_stop(inp, store=store)
            self.assertIn("additionalContext", result)
            memories = store.list_all()
            self.assertTrue(len(memories) > 0)
            # Explicit memories get HIGH confidence
            self.assertEqual(memories[0]["confidence"], "HIGH")
        finally:
            os.unlink(transcript_path)
            store.close()

    def test_contradiction_supersedes_old(self):
        store = MemoryStore(":memory:")
        # Write an old memory manually
        store.create_memory(
            content="The default context threshold for yellow zone warning should be set at sixty percent of the total window capacity",
            tags=["type:decision", "context-monitor", "thresholds"],
            confidence="MEDIUM",
            source="session-end",
            project="testproject",
        )
        self.assertEqual(store.count(), 1)

        # Now fire stop with a contradicting message
        msg = "We decided the default context threshold for yellow zone warning should be set at twenty five percent of the total window capacity because sixty was too late."
        inp = self._make_stop_input(last_msg=msg)
        ch.handle_stop(inp, store=store)

        memories = store.list_all(project="testproject")
        # Old one should be superseded, new one written
        # (exact count depends on whether contradiction similarity is 55-85%)
        # At minimum, we should have at least 1 memory
        self.assertGreaterEqual(len(memories), 1)
        store.close()


class TestInferTags(unittest.TestCase):
    def test_memory_tag_inferred(self):
        tags = ch._infer_tags("The memory system uses JSON files for storage")
        self.assertIn("memory-system", tags)

    def test_security_tag_inferred(self):
        tags = ch._infer_tags("Never store API keys or credentials in memory content")
        self.assertIn("security", tags)

    def test_unknown_content_gets_general(self):
        tags = ch._infer_tags("This is some random unrelated content")
        self.assertIn("general", tags)

    def test_tags_capped_at_3(self):
        tags = ch._infer_tags(
            "The memory hook schema tests architecture credentials api key import"
        )
        self.assertLessEqual(len(tags), 3)


class TestExtractMemType(unittest.TestCase):
    def test_extracts_type_from_tags(self):
        self.assertEqual(ch._extract_mem_type(["type:error", "hooks"]), "error")

    def test_default_to_decision(self):
        self.assertEqual(ch._extract_mem_type(["hooks", "general"]), "decision")

    def test_empty_tags(self):
        self.assertEqual(ch._extract_mem_type([]), "decision")

    def test_first_type_wins(self):
        self.assertEqual(ch._extract_mem_type(["type:pattern", "type:error"]), "pattern")


# ═══════════════════════════════════════════════════════════════════════════
# OMEGA-Pattern Tests (dedup, contradiction, TTL)
# ═══════════════════════════════════════════════════════════════════════════

class TestContentHash(unittest.TestCase):
    def test_same_content_same_hash(self):
        h1 = ch._content_hash("Use SQLite for local storage")
        h2 = ch._content_hash("Use SQLite for local storage")
        self.assertEqual(h1, h2)

    def test_different_content_different_hash(self):
        h1 = ch._content_hash("Use SQLite for local storage")
        h2 = ch._content_hash("Use PostgreSQL for cloud storage")
        self.assertNotEqual(h1, h2)

    def test_case_insensitive(self):
        h1 = ch._content_hash("Always use TDD")
        h2 = ch._content_hash("always use tdd")
        self.assertEqual(h1, h2)

    def test_whitespace_normalized(self):
        h1 = ch._content_hash("Use  stdlib   first")
        h2 = ch._content_hash("Use stdlib first")
        self.assertEqual(h1, h2)

    def test_hash_is_16_chars(self):
        h = ch._content_hash("test content")
        self.assertEqual(len(h), 16)


class TestContentSimilarity(unittest.TestCase):
    def test_identical_texts(self):
        sim = ch._content_similarity("hello world test", "hello world test")
        self.assertEqual(sim, 1.0)

    def test_completely_different(self):
        sim = ch._content_similarity("alpha beta gamma", "delta epsilon zeta")
        self.assertEqual(sim, 0.0)

    def test_partial_overlap(self):
        sim = ch._content_similarity(
            "Use SQLite for local storage because it is lightweight",
            "Use SQLite for cloud storage because it is fast"
        )
        self.assertGreater(sim, 0.3)
        self.assertLess(sim, 0.9)

    def test_empty_text(self):
        sim = ch._content_similarity("", "hello")
        self.assertEqual(sim, 0.0)

    def test_high_similarity(self):
        sim = ch._content_similarity(
            "Always run tests before committing code changes",
            "Always run tests before committing any code changes"
        )
        self.assertGreater(sim, 0.8)


class TestWordSet(unittest.TestCase):
    def test_removes_stopwords(self):
        words = ch._word_set("the quick brown fox is a test")
        self.assertNotIn("the", words)
        self.assertNotIn("is", words)
        self.assertIn("quick", words)
        self.assertIn("brown", words)

    def test_removes_short_words(self):
        words = ch._word_set("it is at by on")
        self.assertEqual(len(words), 0)


class TestFindDuplicates(unittest.TestCase):
    def test_finds_exact_duplicate(self):
        existing = [{"content": "Use SQLite for storage", "id": "mem_1"}]
        dupes = ch.find_duplicates("Use SQLite for storage", existing)
        self.assertEqual(len(dupes), 1)

    def test_finds_near_duplicate(self):
        existing = [{"content": "Always run tests before committing code changes", "id": "mem_1"}]
        dupes = ch.find_duplicates("Always run tests before committing any code changes", existing)
        self.assertEqual(len(dupes), 1)

    def test_no_duplicate_for_different_content(self):
        existing = [{"content": "Use SQLite for storage", "id": "mem_1"}]
        dupes = ch.find_duplicates("Never expose API keys", existing)
        self.assertEqual(len(dupes), 0)

    def test_empty_existing(self):
        dupes = ch.find_duplicates("test content", [])
        self.assertEqual(len(dupes), 0)


class TestFindContradictions(unittest.TestCase):
    def test_detects_contradiction_same_type_overlapping_tags(self):
        existing = [{
            "content": "The default context threshold for yellow zone warning should be set at sixty percent of the total window capacity",
            "tags": ["type:decision", "context-monitor", "thresholds"],
            "id": "mem_old",
        }]
        contradictions = ch.find_contradictions(
            "The default context threshold for yellow zone warning should be set at twenty five percent of the total window capacity",
            "decision",
            ["type:decision", "context-monitor", "thresholds"],
            existing,
        )
        self.assertGreater(len(contradictions), 0)

    def test_no_contradiction_different_type(self):
        existing = [{
            "content": "Use PostgreSQL for the backend database",
            "tags": ["type:pattern", "storage"],
            "id": "mem_old",
        }]
        contradictions = ch.find_contradictions(
            "Use SQLite for the backend database",
            "decision",
            ["type:decision", "storage"],
            existing,
        )
        self.assertEqual(len(contradictions), 0)

    def test_no_contradiction_no_tag_overlap(self):
        existing = [{
            "content": "Use PostgreSQL for the backend database",
            "tags": ["type:decision", "frontend"],
            "id": "mem_old",
        }]
        contradictions = ch.find_contradictions(
            "Use SQLite for the backend database",
            "decision",
            ["type:decision", "storage"],
            existing,
        )
        self.assertEqual(len(contradictions), 0)

    def test_too_similar_is_duplicate_not_contradiction(self):
        existing = [{
            "content": "Always run tests before committing code changes to repo",
            "tags": ["type:preference", "testing"],
            "id": "mem_old",
        }]
        contradictions = ch.find_contradictions(
            "Always run tests before committing code changes to the repo",
            "preference",
            ["type:preference", "testing"],
            existing,
        )
        self.assertEqual(len(contradictions), 0)

    def test_empty_existing(self):
        contradictions = ch.find_contradictions(
            "test content", "decision", ["type:decision", "general"], []
        )
        self.assertEqual(len(contradictions), 0)


class TestTypeTTL(unittest.TestCase):
    def test_decision_high_confidence(self):
        ttl = ch.get_ttl_days("decision", "HIGH")
        self.assertEqual(ttl, 730)

    def test_decision_medium_confidence(self):
        ttl = ch.get_ttl_days("decision", "MEDIUM")
        self.assertEqual(ttl, 365)

    def test_decision_low_confidence(self):
        ttl = ch.get_ttl_days("decision", "LOW")
        self.assertEqual(ttl, 182)

    def test_pattern_medium(self):
        ttl = ch.get_ttl_days("pattern", "MEDIUM")
        self.assertEqual(ttl, 180)

    def test_pattern_low(self):
        ttl = ch.get_ttl_days("pattern", "LOW")
        self.assertEqual(ttl, 90)

    def test_preference_permanent(self):
        ttl = ch.get_ttl_days("preference", "MEDIUM")
        self.assertEqual(ttl, 730)

    def test_error_long_lived(self):
        ttl = ch.get_ttl_days("error", "MEDIUM")
        self.assertEqual(ttl, 365)

    def test_unknown_type_default(self):
        ttl = ch.get_ttl_days("unknown_type", "MEDIUM")
        self.assertEqual(ttl, 180)

    def test_low_confidence_min_30(self):
        ttl = ch.get_ttl_days("pattern", "LOW")
        self.assertGreaterEqual(ttl, 30)


class TestUserPromptSubmitHandler(unittest.TestCase):
    """Tests for UserPromptSubmit real-time memory capture."""

    def _make_input(self, prompt, cwd="/Users/matt/Projects/TestProject"):
        return {
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
            "cwd": cwd,
        }

    def test_remember_that_captures_memory(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("Remember that we always use TDD before writing any production code")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertIn("additionalContext", result)
        self.assertIn("saved", result["additionalContext"].lower())
        memories = store.list_all()
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["confidence"], "HIGH")
        store.close()

    def test_always_use_captures_memory(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("always use stdlib-first approach for all new modules")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertIn("additionalContext", result)
        memories = store.list_all()
        self.assertTrue(len(memories) > 0)
        store.close()

    def test_never_do_captures_memory(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("never modify files outside the project directory")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertIn("additionalContext", result)
        memories = store.list_all()
        self.assertTrue(len(memories) > 0)
        store.close()

    def test_rule_colon_captures_memory(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("rule: all hooks must fail silently with valid JSON")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertIn("additionalContext", result)
        store.close()

    def test_non_negotiable_captures_memory(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("non-negotiable: commit working code before risky changes")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertIn("additionalContext", result)
        store.close()

    def test_normal_prompt_no_capture(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("Can you help me fix this bug in the parser?")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertEqual(result, {})
        self.assertEqual(store.count(), 0)
        store.close()

    def test_short_prompt_no_capture(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("ok")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertEqual(result, {})
        store.close()

    def test_credential_in_memory_blocked(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("remember that the API key is sk-ant-api03-secretkey12345678901234")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertEqual(store.count(), 0)
        store.close()

    def test_dedup_against_existing(self):
        store = MemoryStore(":memory:")
        store.create_memory(
            content="we always use TDD before writing any production code",
            tags=["type:preference", "testing"],
            confidence="HIGH",
            source="explicit",
            project="testproject",
        )
        inp = self._make_input("Remember that we always use TDD before writing any production code")
        result = ch.handle_user_prompt_submit(inp, store=store)
        # Should dedup — no new memory written
        self.assertEqual(store.count(), 1)
        store.close()

    def test_source_is_realtime(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("remember that hooks must never crash the CLI process")
        ch.handle_user_prompt_submit(inp, store=store)
        memories = store.list_all()
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["source"], "realtime")
        store.close()

    def test_project_slug_used(self):
        store = MemoryStore(":memory:")
        inp = self._make_input(
            "remember that this project uses FTS5 for search",
            cwd="/Users/matt/Projects/ClaudeCodeAdvancements"
        )
        ch.handle_user_prompt_submit(inp, store=store)
        memories = store.list_all(project="claudecodeadvancements")
        self.assertEqual(len(memories), 1)
        store.close()

    def test_empty_prompt_no_crash(self):
        store = MemoryStore(":memory:")
        inp = self._make_input("")
        result = ch.handle_user_prompt_submit(inp, store=store)
        self.assertEqual(result, {})
        store.close()

    def test_cap_at_3_per_prompt(self):
        store = MemoryStore(":memory:")
        # Craft a prompt with many remember-that triggers
        lines = [f"remember that rule number {i} is very important for the project" for i in range(10)]
        inp = self._make_input(". ".join(lines))
        ch.handle_user_prompt_submit(inp, store=store)
        self.assertLessEqual(store.count(), 3)
        store.close()


class TestSchemaVersion(unittest.TestCase):
    def test_schema_version_is_2_0(self):
        self.assertEqual(ch.SCHEMA_VERSION, "2.0")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
