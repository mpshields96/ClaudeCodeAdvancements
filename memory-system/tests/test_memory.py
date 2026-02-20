#!/usr/bin/env python3
"""
Smoke tests for memory-system.
Run: python3 memory-system/tests/test_memory.py
All tests use in-memory or tmp paths — no writes to ~/.claude-memory.
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


class TestBuildMemory(unittest.TestCase):
    def test_valid_memory_created(self):
        mem = ch._build_memory(
            content="Use stdlib-first approach",
            mem_type="decision",
            project="testproject",
            tags=["architecture"],
            confidence="HIGH",
            source="explicit",
        )
        self.assertIsNotNone(mem)
        self.assertEqual(mem["type"], "decision")
        self.assertEqual(mem["confidence"], "HIGH")
        self.assertEqual(mem["project"], "testproject")
        self.assertIn("mem_", mem["id"])

    def test_empty_content_rejected(self):
        mem = ch._build_memory("", "decision", "proj", [], "HIGH", "explicit")
        self.assertIsNone(mem)

    def test_credential_content_rejected(self):
        mem = ch._build_memory(
            "sk-ant-api03-secretkey123456789",
            "error", "proj", [], "HIGH", "explicit"
        )
        self.assertIsNone(mem)

    def test_content_truncated_at_500(self):
        long = "x" * 600
        mem = ch._build_memory(long, "decision", "proj", [], "MEDIUM", "inferred")
        self.assertIsNotNone(mem)
        self.assertLessEqual(len(mem["content"]), 500)

    def test_invalid_type_falls_back(self):
        mem = ch._build_memory("Some content here", "invalid_type", "proj", [], "HIGH", "explicit")
        self.assertIsNotNone(mem)
        self.assertEqual(mem["type"], "decision")

    def test_tags_capped_at_5(self):
        mem = ch._build_memory(
            "Some content", "pattern", "proj",
            ["a", "b", "c", "d", "e", "f", "g"],
            "LOW", "inferred"
        )
        self.assertIsNotNone(mem)
        self.assertLessEqual(len(mem["tags"]), 5)


class TestExtractMemoriesFromMessage(unittest.TestCase):
    def test_decision_sentence_extracted(self):
        msg = "We decided to use SQLite instead of PostgreSQL because it requires no server setup."
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["type"], "decision")

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
        # Questions should not be captured as memories
        for mem in memories:
            self.assertFalse(mem["content"].endswith("?"))

    def test_credential_sentence_not_captured(self):
        msg = "We decided the API key is sk-ant-api03-abc123 and should never be logged."
        memories = ch._extract_memories_from_message(msg, "testproject")
        for mem in memories:
            self.assertFalse(ch._contains_credentials(mem["content"]))

    def test_cap_at_5_memories_per_message(self):
        # A message with many decision-keyword sentences
        sentences = [
            f"We decided to use approach {i} because it is better." for i in range(20)
        ]
        msg = " ".join(sentences)
        memories = ch._extract_memories_from_message(msg, "testproject")
        self.assertLessEqual(len(memories), 5)


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


class TestStoreLoadSave(unittest.TestCase):
    def test_new_store_created_when_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "newproject.json"
            store = ch._load_store(path)
            self.assertIn("memories", store)
            self.assertEqual(store["memories"], [])
            self.assertEqual(store["schema_version"], ch.SCHEMA_VERSION)

    def test_existing_store_loaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing.json"
            data = {
                "project": "existing",
                "schema_version": "1.0",
                "created_at": "2026-01-01T00:00:00Z",
                "last_updated": "2026-01-01T00:00:00Z",
                "memories": [{"id": "mem_test", "content": "test memory"}],
            }
            with open(path, "w") as f:
                json.dump(data, f)
            store = ch._load_store(path)
            self.assertEqual(len(store["memories"]), 1)
            self.assertEqual(store["memories"][0]["id"], "mem_test")

    def test_save_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            store = ch._load_store(path)
            store["memories"].append({"id": "mem_001", "content": "test"})
            ch._save_store(store, path)
            self.assertTrue(path.exists())
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(len(loaded["memories"]), 1)

    def test_corrupted_store_returns_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corrupted.json"
            path.write_text("{ invalid json !!!")
            store = ch._load_store(path)
            self.assertIn("memories", store)
            self.assertEqual(store["memories"], [])


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


class TestMakeId(unittest.TestCase):
    def test_id_has_mem_prefix(self):
        id_ = ch._make_id()
        self.assertTrue(id_.startswith("mem_"))

    def test_id_is_unique(self):
        ids = {ch._make_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


if __name__ == "__main__":
    # Run with verbose output for a clear pass/fail per test
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
