#!/usr/bin/env python3
"""
Tests for MEM-3: mcp_server.py (FTS5 backend)
Tests tool logic directly (no subprocess needed).
Run: python3 memory-system/tests/test_mcp_server.py
"""

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path

# Add parent dirs to path so we can import mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server import (
    tool_load_memories,
    tool_search_memory,
    handle_request,
    _project_slug,
)
from memory_store import MemoryStore


def _make_store_with_memories(memories_data):
    """Create an in-memory MemoryStore pre-populated with test data."""
    store = MemoryStore(":memory:")
    for m in memories_data:
        store.create_memory(
            content=m.get("content", "test content"),
            tags=m.get("tags", ["general"]),
            confidence=m.get("confidence", "HIGH"),
            source=m.get("source", "explicit"),
            context=m.get("context", ""),
            project=m.get("project", "testproject"),
            memory_id=m.get("id", None),
        )
    return store


class TestProjectSlug(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_project_slug("/Users/matt/Projects/ClaudeCodeAdvancements"), "claudecodeadvancements")

    def test_spaces_become_hyphens(self):
        self.assertEqual(_project_slug("/Users/matt/My Project"), "my-project")

    def test_underscores_become_hyphens(self):
        self.assertEqual(_project_slug("/Users/matt/my_project"), "my-project")

    def test_already_lowercase(self):
        self.assertEqual(_project_slug("/home/user/myapp"), "myapp")


class TestToolLoadMemories(unittest.TestCase):
    def _run(self, memories_data, include_medium=False):
        store = _make_store_with_memories(memories_data)
        return tool_load_memories(
            {"cwd": "/tmp/testproject", "include_medium": include_medium},
            store=store
        )

    def test_returns_only_high_by_default(self):
        mems = [
            {"id": "m1", "confidence": "HIGH", "content": "high mem"},
            {"id": "m2", "confidence": "MEDIUM", "content": "medium mem"},
            {"id": "m3", "confidence": "LOW", "content": "low mem"},
        ]
        result = self._run(mems)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m1")

    def test_include_medium_returns_high_and_medium(self):
        mems = [
            {"id": "m1", "confidence": "HIGH", "content": "high mem"},
            {"id": "m2", "confidence": "MEDIUM", "content": "medium mem"},
            {"id": "m3", "confidence": "LOW", "content": "low mem"},
        ]
        result = self._run(mems, include_medium=True)
        self.assertEqual(result["count"], 2)
        ids = {m["id"] for m in result["memories"]}
        self.assertIn("m1", ids)
        self.assertIn("m2", ids)
        self.assertNotIn("m3", ids)

    def test_empty_store_returns_zero(self):
        result = self._run([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["memories"], [])

    def test_high_sorted_before_medium(self):
        mems = [
            {"id": "m_medium", "confidence": "MEDIUM", "content": "medium mem"},
            {"id": "m_high", "confidence": "HIGH", "content": "high mem"},
        ]
        result = self._run(mems, include_medium=True)
        self.assertEqual(result["memories"][0]["id"], "m_high")

    def test_project_slug_in_result(self):
        result = self._run([])
        self.assertEqual(result["project"], "testproject")

    def test_filters_by_project(self):
        """Only returns memories for the requested project."""
        store = MemoryStore(":memory:")
        store.create_memory(content="project A mem", project="testproject", memory_id="m_a")
        store.create_memory(content="project B mem", project="otherproject", memory_id="m_b")
        result = tool_load_memories(
            {"cwd": "/tmp/testproject", "include_medium": True},
            store=store
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m_a")


class TestToolSearchMemory(unittest.TestCase):
    def _run(self, memories_data, query):
        store = _make_store_with_memories(memories_data)
        return tool_search_memory(
            {"query": query, "cwd": "/tmp/testproject"},
            store=store
        )

    def test_finds_content_match(self):
        mems = [{"id": "m1", "content": "Use stdlib for all file operations"}]
        result = self._run(mems, "stdlib")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m1")

    def test_finds_tag_match(self):
        mems = [{"id": "m1", "content": "some content", "tags": ["hooks", "architecture"]}]
        result = self._run(mems, "hooks")
        self.assertEqual(result["count"], 1)

    def test_case_insensitive(self):
        mems = [{"id": "m1", "content": "Use STDLIB for operations"}]
        result = self._run(mems, "stdlib")
        self.assertEqual(result["count"], 1)

    def test_no_match_returns_empty(self):
        mems = [{"id": "m1", "content": "nothing relevant here"}]
        result = self._run(mems, "xyzzy")
        self.assertEqual(result["count"], 0)

    def test_empty_query_returns_empty(self):
        mems = [{"id": "m1", "content": "test content"}]
        result = self._run(mems, "")
        self.assertEqual(result["count"], 0)

    def test_returns_max_10(self):
        mems = [{"id": f"m{i}", "content": "hooks pattern"} for i in range(15)]
        result = self._run(mems, "hooks")
        self.assertLessEqual(result["count"], 10)
        self.assertLessEqual(len(result["memories"]), 10)

    def test_query_echoed_in_result(self):
        result = self._run([], "myquery")
        self.assertEqual(result["query"], "myquery")

    def test_relevance_ranked(self):
        """FTS5 BM25 should rank a more specific match higher."""
        mems = [
            {"id": "m_general", "content": "hooks are a general concept in programming languages"},
            {"id": "m_specific", "content": "hooks hooks hooks are the core delivery mechanism"},
        ]
        result = self._run(mems, "hooks")
        # m_specific has more hits of "hooks" so should rank higher
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["memories"][0]["id"], "m_specific")

    def test_fts5_operators(self):
        """FTS5 AND/OR/NOT operators should work."""
        mems = [
            {"id": "m1", "content": "hooks and architecture patterns"},
            {"id": "m2", "content": "hooks for credential safety"},
            {"id": "m3", "content": "architecture patterns only"},
        ]
        result = self._run(mems, '"hooks" AND "architecture"')
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m1")

    def test_project_filtering(self):
        """Search should respect project filter from cwd."""
        store = MemoryStore(":memory:")
        store.create_memory(content="hooks in project A", project="testproject", memory_id="m_a")
        store.create_memory(content="hooks in project B", project="other", memory_id="m_b")
        result = tool_search_memory(
            {"query": "hooks", "cwd": "/tmp/testproject"},
            store=store
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m_a")


class TestHandleRequest(unittest.TestCase):
    def _make_store(self, memories_data=None):
        return _make_store_with_memories(memories_data or [])

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = handle_request(req)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "claude-memory")
        self.assertEqual(resp["result"]["serverInfo"]["version"], "2.0.0")
        self.assertIn("protocolVersion", resp["result"])

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        resp = handle_request(req)
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("load_memories", tool_names)
        self.assertIn("search_memory", tool_names)

    def test_tools_call_unknown_tool(self):
        req = {
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}}
        }
        resp = handle_request(req)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_unknown_method_returns_error(self):
        req = {"jsonrpc": "2.0", "id": 4, "method": "bad/method", "params": {}}
        resp = handle_request(req)
        self.assertIn("error", resp)

    def test_notification_returns_none(self):
        req = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        resp = handle_request(req)
        self.assertIsNone(resp)

    def test_ping_returns_ok(self):
        req = {"jsonrpc": "2.0", "id": 5, "method": "ping", "params": {}}
        resp = handle_request(req)
        self.assertEqual(resp["result"], {})

    def test_tools_call_load_memories(self):
        store = _make_store_with_memories([
            {"id": "m1", "content": "test memory", "confidence": "HIGH"}
        ])
        req = {
            "jsonrpc": "2.0", "id": 6,
            "method": "tools/call",
            "params": {"name": "load_memories", "arguments": {"cwd": "/tmp/testproject"}}
        }
        resp = handle_request(req, store=store)
        self.assertFalse(resp["result"]["isError"])
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(content["count"], 1)

    def test_tools_call_search_memory(self):
        store = _make_store_with_memories([
            {"id": "m1", "content": "hooks are important"}
        ])
        req = {
            "jsonrpc": "2.0", "id": 7,
            "method": "tools/call",
            "params": {"name": "search_memory", "arguments": {"query": "hooks", "cwd": "/tmp/testproject"}}
        }
        resp = handle_request(req, store=store)
        self.assertFalse(resp["result"]["isError"])
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(content["count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
