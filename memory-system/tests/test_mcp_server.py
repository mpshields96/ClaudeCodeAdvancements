#!/usr/bin/env python3
"""
Tests for MEM-3: mcp_server.py
Tests tool logic directly (no subprocess needed).
Run: python3 memory-system/tests/test_mcp_server.py
"""

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent dirs to path so we can import mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server import (
    tool_load_memories,
    tool_search_memory,
    handle_request,
    _project_slug,
    _load_store,
)


def make_store(memories: list) -> dict:
    return {
        "project": "testproject",
        "schema_version": "1.0",
        "memories": memories
    }


def make_memory(id, type="decision", content="test content", confidence="HIGH",
                tags=None, last_used="2026-02-20T10:00:00Z"):
    return {
        "id": id,
        "type": type,
        "content": content,
        "project": "testproject",
        "tags": tags or ["general"],
        "created_at": "2026-02-20T09:00:00Z",
        "last_used": last_used,
        "confidence": confidence,
        "source": "explicit"
    }


class TestProjectSlug(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_project_slug("/Users/matt/Projects/ClaudeCodeAdvancements"), "claudecodeadvancements")

    def test_spaces_become_hyphens(self):
        self.assertEqual(_project_slug("/Users/matt/My Project"), "my-project")

    def test_underscores_become_hyphens(self):
        self.assertEqual(_project_slug("/Users/matt/my_project"), "my-project")

    def test_already_lowercase(self):
        self.assertEqual(_project_slug("/home/user/myapp"), "myapp")


class TestLoadStore(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                store = _load_store("nonexistent")
        self.assertEqual(store["memories"], [])

    def test_loads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text(json.dumps(make_store([make_memory("mem_001")])))
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                store = _load_store("testproject")
        self.assertEqual(len(store["memories"]), 1)

    def test_corrupt_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text("NOT VALID JSON {{{")
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                store = _load_store("testproject")
        self.assertEqual(store["memories"], [])


class TestToolLoadMemories(unittest.TestCase):
    def _run(self, memories, include_medium=False):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = str(Path(tmpdir) / "testproject")
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text(json.dumps(make_store(memories)))
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                return tool_load_memories({"cwd": cwd, "include_medium": include_medium})

    def test_returns_only_high_by_default(self):
        mems = [
            make_memory("m1", confidence="HIGH"),
            make_memory("m2", confidence="MEDIUM"),
            make_memory("m3", confidence="LOW"),
        ]
        result = self._run(mems)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m1")

    def test_include_medium_returns_high_and_medium(self):
        mems = [
            make_memory("m1", confidence="HIGH"),
            make_memory("m2", confidence="MEDIUM"),
            make_memory("m3", confidence="LOW"),
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
            make_memory("m_medium", confidence="MEDIUM", last_used="2026-02-20T12:00:00Z"),
            make_memory("m_high", confidence="HIGH", last_used="2026-02-20T08:00:00Z"),
        ]
        result = self._run(mems, include_medium=True)
        self.assertEqual(result["memories"][0]["id"], "m_high")

    def test_project_slug_in_result(self):
        result = self._run([])
        self.assertEqual(result["project"], "testproject")


class TestToolSearchMemory(unittest.TestCase):
    def _run(self, memories, query):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = str(Path(tmpdir) / "testproject")
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text(json.dumps(make_store(memories)))
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                return tool_search_memory({"query": query, "cwd": cwd})

    def test_finds_content_match(self):
        mems = [make_memory("m1", content="Use stdlib for all file operations")]
        result = self._run(mems, "stdlib")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memories"][0]["id"], "m1")

    def test_finds_tag_match(self):
        mems = [make_memory("m1", tags=["hooks", "architecture"])]
        result = self._run(mems, "hooks")
        self.assertEqual(result["count"], 1)

    def test_finds_type_match(self):
        mems = [make_memory("m1", type="error", content="completely unrelated")]
        result = self._run(mems, "error")
        self.assertEqual(result["count"], 1)

    def test_case_insensitive(self):
        mems = [make_memory("m1", content="Use STDLIB for operations")]
        result = self._run(mems, "stdlib")
        self.assertEqual(result["count"], 1)

    def test_no_match_returns_empty(self):
        mems = [make_memory("m1", content="nothing relevant here")]
        result = self._run(mems, "xyzzy")
        self.assertEqual(result["count"], 0)

    def test_empty_query_returns_empty(self):
        mems = [make_memory("m1")]
        result = self._run(mems, "")
        self.assertEqual(result["count"], 0)

    def test_returns_max_10(self):
        mems = [make_memory(f"m{i}", content="hooks pattern") for i in range(15)]
        result = self._run(mems, "hooks")
        self.assertLessEqual(result["count"], 10)
        self.assertLessEqual(len(result["memories"]), 10)

    def test_sorted_by_last_used_descending(self):
        mems = [
            make_memory("m_old", content="hooks", last_used="2026-02-18T10:00:00Z"),
            make_memory("m_new", content="hooks", last_used="2026-02-20T10:00:00Z"),
        ]
        result = self._run(mems, "hooks")
        self.assertEqual(result["memories"][0]["id"], "m_new")

    def test_query_echoed_in_result(self):
        result = self._run([], "myquery")
        self.assertEqual(result["query"], "myquery")


class TestHandleRequest(unittest.TestCase):
    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = handle_request(req)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "claude-memory")
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
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = str(Path(tmpdir) / "testproject")
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text(json.dumps(make_store([make_memory("m1")])))
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                req = {
                    "jsonrpc": "2.0", "id": 6,
                    "method": "tools/call",
                    "params": {"name": "load_memories", "arguments": {"cwd": cwd}}
                }
                resp = handle_request(req)
        self.assertFalse(resp["result"]["isError"])
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(content["count"], 1)

    def test_tools_call_search_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = str(Path(tmpdir) / "testproject")
            store_path = Path(tmpdir) / "testproject.json"
            store_path.write_text(json.dumps(make_store([
                make_memory("m1", content="hooks are important")
            ])))
            with patch("mcp_server._memory_dir", return_value=Path(tmpdir)):
                req = {
                    "jsonrpc": "2.0", "id": 7,
                    "method": "tools/call",
                    "params": {"name": "search_memory", "arguments": {"query": "hooks", "cwd": cwd}}
                }
                resp = handle_request(req)
        self.assertFalse(resp["result"]["isError"])
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(content["count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
