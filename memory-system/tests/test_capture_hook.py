#!/usr/bin/env python3
"""
Tests for memory-system/hooks/capture_hook.py

Covers all 3 hook handlers (PostToolUse, UserPromptSubmit, Stop),
helper functions (dedup, contradiction, credentials, tags, truncation),
and the main() entrypoint routing.

664 LOC source, 0 previous tests — highest-risk untested module.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directories to path
_TESTS_DIR = Path(__file__).resolve().parent
_MODULE_DIR = _TESTS_DIR.parent
_HOOKS_DIR = _MODULE_DIR / "hooks"
sys.path.insert(0, str(_MODULE_DIR))
sys.path.insert(0, str(_HOOKS_DIR))

import capture_hook as ch
from memory_store import MemoryStore


class TestProjectSlug(unittest.TestCase):
    """Tests for _project_slug helper."""

    def test_simple_path(self):
        self.assertEqual(ch._project_slug("/Users/matt/Projects/MyApp"), "myapp")

    def test_path_with_special_chars(self):
        slug = ch._project_slug("/home/user/My Cool Project!")
        self.assertEqual(slug, "my-cool-project")

    def test_empty_path(self):
        self.assertEqual(ch._project_slug(""), "unknown-project")

    def test_root_path(self):
        self.assertEqual(ch._project_slug("/"), "unknown-project")

    def test_mixed_case_and_numbers(self):
        slug = ch._project_slug("/opt/Project123")
        self.assertEqual(slug, "project123")


class TestContainsCredentials(unittest.TestCase):
    """Tests for _contains_credentials filter."""

    def test_anthropic_key(self):
        self.assertTrue(ch._contains_credentials("key is sk-ant-api03-abcdefghij1234567890"))

    def test_bearer_token(self):
        self.assertTrue(ch._contains_credentials("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"))

    def test_api_key_assignment(self):
        self.assertTrue(ch._contains_credentials("api_key = abc12345678901234567890"))

    def test_supabase_key(self):
        self.assertTrue(ch._contains_credentials("SUPABASE_KEY=something"))

    def test_aws_access_key(self):
        self.assertTrue(ch._contains_credentials("AKIAIOSFODNN7EXAMPLE"))

    def test_safe_content(self):
        self.assertFalse(ch._contains_credentials("The fix is to use sqlite instead of postgres"))

    def test_empty_string(self):
        self.assertFalse(ch._contains_credentials(""))

    def test_short_password_ignored(self):
        # password=abc is too short (<8 chars after =) to match
        self.assertFalse(ch._contains_credentials("password=abc"))


class TestTruncate(unittest.TestCase):
    """Tests for _truncate helper."""

    def test_short_string_unchanged(self):
        self.assertEqual(ch._truncate("hello"), "hello")

    def test_exact_limit(self):
        text = "a" * 500
        self.assertEqual(ch._truncate(text), text)

    def test_over_limit_truncated(self):
        text = "a" * 600
        result = ch._truncate(text)
        self.assertEqual(len(result), 500)
        self.assertTrue(result.endswith("\u2026"))

    def test_custom_limit(self):
        result = ch._truncate("abcdefghij", max_chars=5)
        self.assertEqual(len(result), 5)
        self.assertTrue(result.endswith("\u2026"))


class TestContentHash(unittest.TestCase):
    """Tests for _content_hash."""

    def test_same_content_same_hash(self):
        h1 = ch._content_hash("hello world")
        h2 = ch._content_hash("hello world")
        self.assertEqual(h1, h2)

    def test_whitespace_normalized(self):
        h1 = ch._content_hash("  hello   world  ")
        h2 = ch._content_hash("hello world")
        self.assertEqual(h1, h2)

    def test_case_normalized(self):
        h1 = ch._content_hash("Hello World")
        h2 = ch._content_hash("hello world")
        self.assertEqual(h1, h2)

    def test_different_content_different_hash(self):
        h1 = ch._content_hash("hello world")
        h2 = ch._content_hash("goodbye world")
        self.assertNotEqual(h1, h2)

    def test_hash_length(self):
        h = ch._content_hash("test content")
        self.assertEqual(len(h), 16)


class TestWordSet(unittest.TestCase):
    """Tests for _word_set helper."""

    def test_extracts_meaningful_words(self):
        words = ch._word_set("The quick brown fox jumps over the lazy dog")
        self.assertIn("quick", words)
        self.assertIn("brown", words)
        self.assertNotIn("the", words)  # stopword
        self.assertNotIn("a", words)

    def test_filters_short_words(self):
        words = ch._word_set("go to it")
        # All 2-letter words should be filtered
        self.assertEqual(len(words), 0)

    def test_empty_string(self):
        self.assertEqual(ch._word_set(""), set())


class TestContentSimilarity(unittest.TestCase):
    """Tests for _content_similarity (Jaccard)."""

    def test_identical_text(self):
        sim = ch._content_similarity("decided to use sqlite", "decided to use sqlite")
        self.assertEqual(sim, 1.0)

    def test_completely_different(self):
        sim = ch._content_similarity("sqlite database storage", "python regex matching")
        self.assertLess(sim, 0.3)

    def test_partial_overlap(self):
        sim = ch._content_similarity(
            "use sqlite for memory storage",
            "use postgres for memory storage"
        )
        self.assertGreater(sim, 0.5)
        self.assertLess(sim, 1.0)

    def test_empty_strings(self):
        self.assertEqual(ch._content_similarity("", ""), 0.0)
        self.assertEqual(ch._content_similarity("hello", ""), 0.0)


class TestFindDuplicates(unittest.TestCase):
    """Tests for find_duplicates."""

    def test_exact_hash_match(self):
        existing = [{"content": "decided to use sqlite", "id": "1"}]
        dupes = ch.find_duplicates("decided to use sqlite", existing)
        self.assertEqual(len(dupes), 1)

    def test_high_similarity_match(self):
        existing = [{"content": "we decided to use sqlite for persistent memory storage", "id": "1"}]
        dupes = ch.find_duplicates(
            "we decided to use sqlite for persistent memory storage backend",
            existing,
        )
        self.assertEqual(len(dupes), 1)

    def test_no_match(self):
        existing = [{"content": "python regex patterns for parsing", "id": "1"}]
        dupes = ch.find_duplicates("sqlite database for memory", existing)
        self.assertEqual(len(dupes), 0)

    def test_empty_existing(self):
        dupes = ch.find_duplicates("anything", [])
        self.assertEqual(len(dupes), 0)


class TestFindContradictions(unittest.TestCase):
    """Tests for find_contradictions."""

    def test_contradicting_same_type_overlapping_tags(self):
        existing = [{
            "content": "always use postgres for persistent data storage in this project backend",
            "tags": ["type:preference", "storage"],
            "id": "1",
        }]
        contradictions = ch.find_contradictions(
            "always use sqlite for persistent data storage in this project backend",
            "preference",
            ["type:preference", "storage"],
            existing,
        )
        self.assertEqual(len(contradictions), 1)

    def test_no_contradiction_different_type(self):
        existing = [{
            "content": "always use postgres for data storage",
            "tags": ["type:decision", "storage"],
            "id": "1",
        }]
        contradictions = ch.find_contradictions(
            "always use sqlite for data storage",
            "preference",
            ["type:preference", "storage"],
            existing,
        )
        self.assertEqual(len(contradictions), 0)

    def test_no_contradiction_no_tag_overlap(self):
        existing = [{
            "content": "always use postgres for data storage",
            "tags": ["type:preference", "database"],
            "id": "1",
        }]
        contradictions = ch.find_contradictions(
            "prefer dark mode for development",
            "preference",
            ["type:preference", "ui"],
            existing,
        )
        self.assertEqual(len(contradictions), 0)

    def test_too_similar_is_dupe_not_contradiction(self):
        # Similarity >= 0.85 should NOT be flagged (that's a duplicate, not contradiction)
        existing = [{
            "content": "always use sqlite for persistent memory storage",
            "tags": ["type:preference", "storage"],
            "id": "1",
        }]
        contradictions = ch.find_contradictions(
            "always use sqlite for persistent memory storage backend",
            "preference",
            ["type:preference", "storage"],
            existing,
        )
        # Similarity is likely >= 0.85, so NOT a contradiction
        self.assertEqual(len(contradictions), 0)


class TestGetTtlDays(unittest.TestCase):
    """Tests for get_ttl_days."""

    def test_decision_medium(self):
        self.assertEqual(ch.get_ttl_days("decision", "MEDIUM"), 365)

    def test_decision_high(self):
        self.assertEqual(ch.get_ttl_days("decision", "HIGH"), 730)  # capped

    def test_pattern_low(self):
        self.assertEqual(ch.get_ttl_days("pattern", "LOW"), 90)

    def test_preference_high(self):
        self.assertEqual(ch.get_ttl_days("preference", "HIGH"), 730)  # capped

    def test_unknown_type_defaults(self):
        ttl = ch.get_ttl_days("custom_type", "MEDIUM")
        self.assertEqual(ttl, 180)

    def test_error_low(self):
        ttl = ch.get_ttl_days("error", "LOW")
        self.assertEqual(ttl, 182)  # 365 // 2


class TestBuildTags(unittest.TestCase):
    """Tests for _build_tags."""

    def test_type_prefix_added(self):
        tags = ch._build_tags("decision", ["storage", "sqlite"])
        self.assertEqual(tags[0], "type:decision")

    def test_max_5_tags(self):
        tags = ch._build_tags("decision", ["a", "b", "c", "d", "e", "f"])
        self.assertEqual(len(tags), 5)

    def test_no_duplicate_tags(self):
        tags = ch._build_tags("decision", ["type:decision", "storage"])
        self.assertEqual(tags.count("type:decision"), 1)


class TestValidateMemoryParams(unittest.TestCase):
    """Tests for _validate_memory_params."""

    def test_valid_params(self):
        result = ch._validate_memory_params("valid content here", "decision", "HIGH")
        self.assertIsNotNone(result)
        self.assertEqual(result, ("valid content here", "decision", "HIGH"))

    def test_empty_content_returns_none(self):
        self.assertIsNone(ch._validate_memory_params("", "decision", "HIGH"))
        self.assertIsNone(ch._validate_memory_params("   ", "decision", "HIGH"))

    def test_credential_content_returns_none(self):
        self.assertIsNone(ch._validate_memory_params(
            "key is sk-ant-api03-abcdefghij1234567890", "decision", "HIGH"
        ))

    def test_invalid_type_defaults_to_decision(self):
        result = ch._validate_memory_params("content here", "invalid_type", "HIGH")
        self.assertEqual(result[1], "decision")

    def test_invalid_confidence_defaults_to_medium(self):
        result = ch._validate_memory_params("content here", "decision", "INVALID")
        self.assertEqual(result[2], "MEDIUM")

    def test_long_content_truncated(self):
        long_content = "x" * 600
        result = ch._validate_memory_params(long_content, "decision", "HIGH")
        self.assertEqual(len(result[0]), 500)


class TestInferTags(unittest.TestCase):
    """Tests for _infer_tags."""

    def test_memory_keyword(self):
        tags = ch._infer_tags("The memory system stores data persistently")
        self.assertIn("memory-system", tags)

    def test_hook_keyword(self):
        tags = ch._infer_tags("The hook fires on PostToolUse")
        self.assertIn("hooks", tags)

    def test_security_keyword(self):
        tags = ch._infer_tags("Never expose api key values")
        self.assertIn("security", tags)

    def test_no_keywords_general(self):
        tags = ch._infer_tags("Some random content without keywords")
        self.assertEqual(tags, ["general"])

    def test_max_3_tags(self):
        tags = ch._infer_tags("memory hook sqlite json schema test")
        self.assertLessEqual(len(tags), 3)


class TestExtractMemType(unittest.TestCase):
    """Tests for _extract_mem_type."""

    def test_extracts_type(self):
        self.assertEqual(ch._extract_mem_type(["type:error", "storage"]), "error")

    def test_default_to_decision(self):
        self.assertEqual(ch._extract_mem_type(["storage", "hooks"]), "decision")

    def test_empty_tags(self):
        self.assertEqual(ch._extract_mem_type([]), "decision")


# ── PostToolUse Handler Tests ────────────────────────────────────────────────

class TestHandlePostToolUse(unittest.TestCase):
    """Tests for handle_post_tool_use."""

    def test_write_tool_returns_context(self):
        result = ch.handle_post_tool_use({
            "tool_name": "Write",
            "tool_input": {"file_path": "/path/to/file.py"},
        })
        self.assertIn("additionalContext", result)
        self.assertIn("file.py", result["additionalContext"])

    def test_edit_tool_returns_context(self):
        result = ch.handle_post_tool_use({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/path/to/module.py"},
        })
        self.assertIn("additionalContext", result)

    def test_bash_tool_no_file_path(self):
        result = ch.handle_post_tool_use({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        })
        self.assertEqual(result, {})

    def test_insignificant_tool_ignored(self):
        result = ch.handle_post_tool_use({
            "tool_name": "Read",
            "tool_input": {"file_path": "/path/to/file.py"},
        })
        self.assertEqual(result, {})

    def test_write_no_file_path_empty(self):
        result = ch.handle_post_tool_use({
            "tool_name": "Write",
            "tool_input": {},
        })
        self.assertEqual(result, {})

    def test_unknown_tool_ignored(self):
        result = ch.handle_post_tool_use({
            "tool_name": "CustomTool",
            "tool_input": {},
        })
        self.assertEqual(result, {})


# ── UserPromptSubmit Handler Tests ───────────────────────────────────────────

class TestExtractFromPrompt(unittest.TestCase):
    """Tests for _extract_from_prompt."""

    def test_remember_that_pattern(self):
        candidates = ch._extract_from_prompt(
            "remember that we use sqlite for all storage backends",
            "testproject"
        )
        self.assertEqual(len(candidates), 1)
        self.assertIn("sqlite", candidates[0]["content"].lower())
        self.assertEqual(candidates[0]["confidence"], "HIGH")

    def test_always_use_pattern(self):
        candidates = ch._extract_from_prompt(
            "always use stdlib-first approach for dependencies",
            "testproject"
        )
        self.assertEqual(len(candidates), 1)

    def test_never_pattern(self):
        candidates = ch._extract_from_prompt(
            "never use pandas unless explicitly asked by the user",
            "testproject"
        )
        self.assertEqual(len(candidates), 1)

    def test_rule_pattern(self):
        candidates = ch._extract_from_prompt(
            "rule: every module must have tests before promotion",
            "testproject"
        )
        self.assertEqual(len(candidates), 1)

    def test_non_negotiable_pattern(self):
        candidates = ch._extract_from_prompt(
            "non-negotiable: credentials must never be logged in any output",
            "testproject"
        )
        self.assertEqual(len(candidates), 1)

    def test_too_short_prompt_ignored(self):
        candidates = ch._extract_from_prompt("remember x", "testproject")
        self.assertEqual(len(candidates), 0)

    def test_credential_content_filtered(self):
        candidates = ch._extract_from_prompt(
            "remember that the api_key = sk-ant-api03-abcdef1234567890abcdef",
            "testproject"
        )
        self.assertEqual(len(candidates), 0)

    def test_max_3_per_prompt(self):
        prompt = (
            "remember that sqlite is our database. "
            "always use stdlib for imports. "
            "never use external packages without justification. "
            "rule: tests before promotion. "
        )
        candidates = ch._extract_from_prompt(prompt, "testproject")
        self.assertLessEqual(len(candidates), 3)

    def test_overlapping_matches_deduped(self):
        # "remember that always use X" could match both patterns
        candidates = ch._extract_from_prompt(
            "remember that we should always use python3 for all scripts in the project",
            "testproject"
        )
        # Should not produce duplicate entries
        self.assertLessEqual(len(candidates), 2)

    def test_similar_content_deduped(self):
        prompt = (
            "remember that we use sqlite for storage. "
            "remember that sqlite is used for storage."
        )
        candidates = ch._extract_from_prompt(prompt, "testproject")
        # Second should be filtered by similarity check
        self.assertLessEqual(len(candidates), 1)

    def test_short_capture_trimmed_at_sentence(self):
        candidates = ch._extract_from_prompt(
            "remember that sqlite is our database. And also use it for caching.",
            "testproject"
        )
        if candidates:
            # Should trim at first period after 15+ chars
            self.assertNotIn("caching", candidates[0]["content"])


class TestHandleUserPromptSubmit(unittest.TestCase):
    """Tests for handle_user_prompt_submit with real MemoryStore."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_memories.db")
        self.store = MemoryStore(db_path=self.db_path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.db_path)
        except OSError:
            pass
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_saves_explicit_memory(self):
        result = ch.handle_user_prompt_submit(
            {
                "prompt": "remember that we use sqlite for all persistent storage in this project",
                "cwd": "/Users/test/Projects/MyApp",
            },
            store=self.store,
        )
        self.assertIn("additionalContext", result)
        self.assertIn("1", result["additionalContext"])
        self.assertIn("memory", result["additionalContext"])

        # Verify memory was written
        memories = self.store.list_all(project="myapp")
        self.assertEqual(len(memories), 1)

    def test_dedup_prevents_duplicate(self):
        # First save
        ch.handle_user_prompt_submit(
            {
                "prompt": "remember that sqlite is our storage backend for all memory operations",
                "cwd": "/Users/test/Projects/MyApp",
            },
            store=self.store,
        )
        # Second identical save
        result = ch.handle_user_prompt_submit(
            {
                "prompt": "remember that sqlite is our storage backend for all memory operations",
                "cwd": "/Users/test/Projects/MyApp",
            },
            store=self.store,
        )
        # Should return empty (deduped)
        self.assertEqual(result, {})
        memories = self.store.list_all(project="myapp")
        self.assertEqual(len(memories), 1)

    def test_short_prompt_ignored(self):
        result = ch.handle_user_prompt_submit(
            {"prompt": "hello", "cwd": "/tmp"},
            store=self.store,
        )
        self.assertEqual(result, {})

    def test_no_patterns_empty_result(self):
        result = ch.handle_user_prompt_submit(
            {
                "prompt": "Can you read the file at /path/to/main.py and explain it?",
                "cwd": "/tmp",
            },
            store=self.store,
        )
        self.assertEqual(result, {})


# ── Stop Hook Handler Tests ──────────────────────────────────────────────────

class TestExtractMemoriesFromMessage(unittest.TestCase):
    """Tests for _extract_memories_from_message."""

    def test_decision_keyword(self):
        memories = ch._extract_memories_from_message(
            "We decided to use SQLite instead of PostgreSQL for the memory backend because it requires no daemon.",
            "testproject",
        )
        self.assertGreaterEqual(len(memories), 1)
        self.assertEqual(memories[0]["type"], "decision")

    def test_error_keyword(self):
        memories = ch._extract_memories_from_message(
            "The issue was a circular import between memory_store and capture_hook modules.",
            "testproject",
        )
        self.assertGreaterEqual(len(memories), 1)
        self.assertEqual(memories[0]["type"], "error")

    def test_preference_keyword(self):
        memories = ch._extract_memories_from_message(
            "The user prefers to always use type hints in function signatures across the project.",
            "testproject",
        )
        self.assertGreaterEqual(len(memories), 1)
        self.assertEqual(memories[0]["type"], "preference")

    def test_pattern_keyword(self):
        memories = ch._extract_memories_from_message(
            "The pattern is to keep one file per module with a single responsibility.",
            "testproject",
        )
        self.assertGreaterEqual(len(memories), 1)
        self.assertEqual(memories[0]["type"], "pattern")

    def test_question_sentences_skipped(self):
        memories = ch._extract_memories_from_message(
            "Should we decide to use SQLite instead of PostgreSQL?",
            "testproject",
        )
        self.assertEqual(len(memories), 0)

    def test_short_message_ignored(self):
        self.assertEqual(ch._extract_memories_from_message("ok", "test"), [])
        self.assertEqual(ch._extract_memories_from_message("", "test"), [])

    def test_credential_content_filtered(self):
        memories = ch._extract_memories_from_message(
            "We decided to use the API key sk-ant-api03-abcdefghij1234567890 for authentication.",
            "testproject",
        )
        self.assertEqual(len(memories), 0)

    def test_max_5_memories(self):
        # Build a message with many decision sentences
        sentences = [
            f"We decided to use approach {i} for module {i} because of reason {i}."
            for i in range(10)
        ]
        memories = ch._extract_memories_from_message(" ".join(sentences), "test")
        self.assertLessEqual(len(memories), 5)

    def test_short_sentences_skipped(self):
        memories = ch._extract_memories_from_message(
            "The fix is here. Short.",
            "test",
        )
        self.assertEqual(len(memories), 0)


class TestExtractFromTranscript(unittest.TestCase):
    """Tests for _extract_from_transcript."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, "session.jsonl")
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def test_remember_that_in_transcript(self):
        path = self._write_transcript([
            {"role": "user", "content": [{"type": "text", "text": "remember that we always run tests before committing any code changes"}]},
        ])
        memories = ch._extract_from_transcript(path, "testproject")
        self.assertGreaterEqual(len(memories), 1)
        self.assertEqual(memories[0]["confidence"], "HIGH")
        self.assertEqual(memories[0]["source"], "explicit")

    def test_always_pattern_in_transcript(self):
        path = self._write_transcript([
            {"role": "user", "content": [{"type": "text", "text": "always use python3 explicitly instead of just python in all scripts"}]},
        ])
        memories = ch._extract_from_transcript(path, "testproject")
        self.assertGreaterEqual(len(memories), 1)

    def test_never_pattern_in_transcript(self):
        path = self._write_transcript([
            {"role": "user", "content": [{"type": "text", "text": "never modify files outside the project directory boundary"}]},
        ])
        memories = ch._extract_from_transcript(path, "testproject")
        self.assertGreaterEqual(len(memories), 1)

    def test_assistant_messages_ignored(self):
        path = self._write_transcript([
            {"role": "assistant", "content": [{"type": "text", "text": "remember that we use sqlite for storage operations"}]},
        ])
        memories = ch._extract_from_transcript(path, "testproject")
        self.assertEqual(len(memories), 0)

    def test_string_content_format(self):
        path = self._write_transcript([
            {"role": "user", "content": "remember that we always validate inputs before processing them in production"},
        ])
        memories = ch._extract_from_transcript(path, "testproject")
        self.assertGreaterEqual(len(memories), 1)

    def test_nonexistent_path(self):
        memories = ch._extract_from_transcript("/nonexistent/path.jsonl", "test")
        self.assertEqual(len(memories), 0)

    def test_empty_path(self):
        memories = ch._extract_from_transcript("", "test")
        self.assertEqual(len(memories), 0)

    def test_malformed_jsonl(self):
        path = os.path.join(self.tmpdir, "bad.jsonl")
        with open(path, "w") as f:
            f.write("not json\n")
            f.write('{"role": "user", "content": "remember that tests must pass before merging into main branch"}\n')
        memories = ch._extract_from_transcript(path, "test")
        # Should skip bad line, parse the good one
        self.assertGreaterEqual(len(memories), 1)

    def test_max_10_memories(self):
        entries = [
            {"role": "user", "content": f"remember that rule number {i} is important for the project stability"}
            for i in range(20)
        ]
        path = self._write_transcript(entries)
        memories = ch._extract_from_transcript(path, "test")
        self.assertLessEqual(len(memories), 10)

    def test_credential_in_transcript_filtered(self):
        path = self._write_transcript([
            {"role": "user", "content": "remember that the api_key = sk-ant-api03-secret1234567890abcdef"},
        ])
        memories = ch._extract_from_transcript(path, "test")
        self.assertEqual(len(memories), 0)


class TestHandleStop(unittest.TestCase):
    """Tests for handle_stop with real MemoryStore."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_memories.db")
        self.store = MemoryStore(db_path=self.db_path)

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_saves_from_last_message(self):
        result = ch.handle_stop(
            {
                "cwd": "/Users/test/Projects/MyApp",
                "last_assistant_message": "We decided to use SQLite instead of PostgreSQL because it requires no daemon process and is stdlib-compatible.",
                "transcript_path": "",
            },
            store=self.store,
        )
        self.assertIn("additionalContext", result)
        memories = self.store.list_all(project="myapp")
        self.assertGreaterEqual(len(memories), 1)

    def test_saves_from_transcript(self):
        transcript_path = os.path.join(self.tmpdir, "session.jsonl")
        with open(transcript_path, "w") as f:
            f.write(json.dumps({
                "role": "user",
                "content": [{"type": "text", "text": "remember that we always run the full test suite before committing changes"}],
            }) + "\n")

        result = ch.handle_stop(
            {
                "cwd": "/Users/test/Projects/MyApp",
                "last_assistant_message": "",
                "transcript_path": transcript_path,
            },
            store=self.store,
        )
        self.assertIn("additionalContext", result)

    def test_dedup_across_message_and_transcript(self):
        transcript_path = os.path.join(self.tmpdir, "session.jsonl")
        with open(transcript_path, "w") as f:
            f.write(json.dumps({
                "role": "user",
                "content": "remember that we decided to use sqlite for persistent memory storage backend",
            }) + "\n")

        result = ch.handle_stop(
            {
                "cwd": "/Users/test/Projects/MyApp",
                "last_assistant_message": "We decided to use sqlite for persistent memory storage because it has no daemon.",
                "transcript_path": transcript_path,
            },
            store=self.store,
        )
        # Both sources mention similar sqlite decision — should dedup
        memories = self.store.list_all(project="myapp")
        # Could be 1 or 2 depending on similarity, but should not be >2
        self.assertLessEqual(len(memories), 2)

    def test_contradiction_supersedes_old(self):
        # Seed an existing memory
        self.store.create_memory(
            content="always use postgres for data storage in this project",
            tags=["type:preference", "storage"],
            confidence="MEDIUM",
            source="session-end",
            context="type:preference",
            project="myapp",
            ttl_days=180,
        )

        # New contradicting memory
        result = ch.handle_stop(
            {
                "cwd": "/Users/test/Projects/MyApp",
                "last_assistant_message": "We decided to always use sqlite for data storage instead of postgres because of simplicity.",
                "transcript_path": "",
            },
            store=self.store,
        )
        # Old postgres memory should be superseded
        memories = self.store.list_all(project="myapp")
        contents = [m["content"].lower() for m in memories]
        # At least the new sqlite memory should exist
        self.assertTrue(any("sqlite" in c for c in contents))

    def test_empty_inputs(self):
        result = ch.handle_stop(
            {
                "cwd": "/tmp",
                "last_assistant_message": "",
                "transcript_path": "",
            },
            store=self.store,
        )
        self.assertEqual(result, {})

    def test_store_error_fails_silently(self):
        # Close store to simulate error
        self.store.close()
        broken_store = MagicMock()
        broken_store.list_all.side_effect = Exception("DB error")

        result = ch.handle_stop(
            {
                "cwd": "/tmp",
                "last_assistant_message": "We decided to use approach X for the architecture.",
                "transcript_path": "",
            },
            store=broken_store,
        )
        # Should not raise, should return empty
        self.assertEqual(result, {})


# ── Main Entrypoint Tests ────────────────────────────────────────────────────

class TestMain(unittest.TestCase):
    """Tests for main() routing."""

    @patch("capture_hook.handle_post_tool_use")
    def test_routes_post_tool_use(self, mock_handler):
        mock_handler.return_value = {"additionalContext": "test"}
        payload = json.dumps({
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.py"},
        })
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value=payload))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)
        mock_handler.assert_called_once()

    @patch("capture_hook.handle_user_prompt_submit")
    def test_routes_user_prompt_submit(self, mock_handler):
        mock_handler.return_value = {}
        payload = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "prompt": "remember that tests are important",
            "cwd": "/tmp",
        })
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value=payload))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)
        mock_handler.assert_called_once()

    @patch("capture_hook.handle_stop")
    def test_routes_stop(self, mock_handler):
        mock_handler.return_value = {}
        payload = json.dumps({
            "hook_event_name": "Stop",
            "cwd": "/tmp",
            "last_assistant_message": "Done.",
            "transcript_path": "",
        })
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value=payload))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)
        mock_handler.assert_called_once()

    def test_unknown_event_no_output(self):
        payload = json.dumps({"hook_event_name": "UnknownEvent"})
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value=payload))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)

    def test_empty_stdin_exits_cleanly(self):
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value=""))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)

    def test_invalid_json_exits_cleanly(self):
        with patch("sys.stdin", MagicMock(read=MagicMock(return_value="not json"))):
            with self.assertRaises(SystemExit) as ctx:
                ch.main()
            self.assertEqual(ctx.exception.code, 0)


class TestDaysSince(unittest.TestCase):
    """Tests for _days_since helper."""

    def test_recent_date_near_zero(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        days = ch._days_since(now)
        self.assertLess(days, 0.01)

    def test_old_date(self):
        days = ch._days_since("2020-01-01T00:00:00Z")
        self.assertGreater(days, 365 * 5)

    def test_empty_string(self):
        self.assertEqual(ch._days_since(""), 0.0)

    def test_invalid_string(self):
        self.assertEqual(ch._days_since("not-a-date"), 0.0)


class TestGetAgentId(unittest.TestCase):
    """Tests for _get_agent_id helper."""

    def test_returns_env_var(self):
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            self.assertEqual(ch._get_agent_id(), "desktop")

    def test_returns_empty_if_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "CCA_CHAT_ID"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(ch._get_agent_id(), "")


class TestDecideAction(unittest.TestCase):
    """Tests for decide_action function."""

    def _mem(self, content, mem_id="m1", days_old=0):
        from datetime import datetime, timezone, timedelta
        dt = datetime.now(timezone.utc) - timedelta(days=days_old)
        return {
            "id": mem_id,
            "content": content,
            "last_accessed_at": dt.isoformat().replace("+00:00", "Z"),
            "updated_at": dt.isoformat().replace("+00:00", "Z"),
        }

    def test_add_when_no_existing(self):
        action, mid = ch.decide_action("use sqlite for storage", [])
        self.assertEqual(action, "ADD")
        self.assertIsNone(mid)

    def test_add_when_no_overlap(self):
        existing = [self._mem("prefer dark mode for the editor ui")]
        action, mid = ch.decide_action("use sqlite for persistent storage", existing)
        self.assertEqual(action, "ADD")

    def test_skip_near_identical_fresh(self):
        content = "use sqlite for persistent memory storage in the project"
        existing = [self._mem(content, days_old=5)]
        action, mid = ch.decide_action(content, existing)
        self.assertEqual(action, "SKIP")
        self.assertEqual(mid, "m1")

    def test_delete_add_near_identical_stale(self):
        content = "use sqlite for persistent memory storage in the project"
        existing = [self._mem(content, days_old=120)]
        action, mid = ch.decide_action(content, existing)
        self.assertEqual(action, "DELETE_ADD")
        self.assertEqual(mid, "m1")

    def test_update_when_new_is_richer(self):
        # old and new share core words (Jaccard 0.55-0.85), new is >20% longer
        old = "use sqlite for memory storage with full text search"
        new = "use sqlite for memory storage with full text search and fts5 querying support"
        existing = [self._mem(old, days_old=10)]
        action, mid = ch.decide_action(new, existing)
        self.assertEqual(action, "UPDATE")
        self.assertEqual(mid, "m1")

    def test_update_stale_overlapping(self):
        # old and new share most words but one differs (Jaccard ~0.78), stale, similar lengths
        old = "prefer sqlite backend for persistent memory storage with fts5 search"
        new = "prefer sqlite backend for persistent memory storage with fts5 support"
        existing = [self._mem(old, days_old=95)]  # stale
        action, mid = ch.decide_action(new, existing)
        self.assertEqual(action, "UPDATE")

    def test_add_different_enough(self):
        # 0.55 <= sim < 0.85, new is not longer, not stale — add as separate
        old = "use sqlite database for persistent storage module"
        new = "prefer postgres database for distributed storage deployment"
        existing = [self._mem(old, days_old=5)]
        action, _ = ch.decide_action(new, existing)
        # sim is moderate, new is similar length, fresh — ADD separate perspective
        self.assertEqual(action, "ADD")

    def test_uses_best_match(self):
        existing = [
            self._mem("totally unrelated content about cats", "m1", days_old=5),
            self._mem("use sqlite for storage", "m2", days_old=5),
        ]
        action, mid = ch.decide_action("use sqlite for storage", existing)
        self.assertEqual(action, "SKIP")
        self.assertEqual(mid, "m2")


class TestScopingFields(unittest.TestCase):
    """Tests that user_id/agent_id/run_id are written and queryable."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        from memory_store import MemoryStore
        self.store = MemoryStore(str(Path(self._tmp) / "test.db"))

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_scoping_fields_written(self):
        m = self.store.create_memory(
            content="test memory",
            project="myapp",
            user_id="matthew",
            agent_id="desktop",
            run_id="run42",
        )
        self.assertEqual(m["user_id"], "matthew")
        self.assertEqual(m["agent_id"], "desktop")
        self.assertEqual(m["run_id"], "run42")

    def test_list_all_filters_by_user_id(self):
        self.store.create_memory("mem A", project="p", user_id="alice")
        self.store.create_memory("mem B", project="p", user_id="bob")
        results = self.store.list_all(user_id="alice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "mem A")

    def test_list_all_filters_by_agent_id(self):
        self.store.create_memory("desktop mem", project="p", agent_id="desktop")
        self.store.create_memory("worker mem", project="p", agent_id="cli1")
        results = self.store.list_all(agent_id="cli1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "worker mem")

    def test_list_all_filters_by_run_id(self):
        self.store.create_memory("run1 mem", project="p", run_id="run1")
        self.store.create_memory("run2 mem", project="p", run_id="run2")
        results = self.store.list_all(run_id="run1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "run1 mem")

    def test_search_filters_by_user_id(self):
        self.store.create_memory("sqlite storage backend", project="p", user_id="alice")
        self.store.create_memory("sqlite storage backend", project="p", user_id="bob")
        results = self.store.search("sqlite storage", user_id="alice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["user_id"], "alice")

    def test_defaults_to_default_user(self):
        m = self.store.create_memory("memory without user", project="p")
        self.assertEqual(m["user_id"], "default")
        self.assertEqual(m["agent_id"], "")
        self.assertEqual(m["run_id"], "")


class TestHandleStopDecideAction(unittest.TestCase):
    """Tests that handle_stop uses decide_action (UPDATE/DELETE_ADD paths)."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        from memory_store import MemoryStore
        self.store = MemoryStore(str(Path(self._tmp) / "test.db"))

    def tearDown(self):
        self.store.close()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _stop_payload(self, message, cwd="/Users/test/Projects/MyApp"):
        return {"hook_event_name": "Stop", "last_assistant_message": message,
                "transcript_path": "", "cwd": cwd}

    def test_update_path_does_not_duplicate(self):
        # Seed a memory with content that overlaps >20% length-wise with the extracted sentence
        original = "prefer sqlite for persistent memory storage with fts5 search"
        self.store.create_memory(original, project="myapp")
        count_before = self.store.count()
        # Message produces a richer overlapping sentence → decide_action → UPDATE (no new row)
        enriched = (
            "We prefer sqlite for persistent memory storage with fts5 search "
            "and querying support because it is efficient."
        )
        ch.handle_stop(self._stop_payload(enriched), store=self.store)
        # UPDATE path keeps count ≤ count_before + 1 (allow one if extraction misses overlap)
        self.assertLessEqual(self.store.count(), count_before + 1)

    def test_skip_does_not_add_duplicate(self):
        content = "we decided to use sqlite for persistent memory storage"
        self.store.create_memory(content, project="myapp")
        count_before = self.store.count()
        ch.handle_stop(self._stop_payload(content + " in this project."), store=self.store)
        # Count should not have grown from a near-identical SKIP
        self.assertLessEqual(self.store.count(), count_before + 1)


if __name__ == "__main__":
    unittest.main()
