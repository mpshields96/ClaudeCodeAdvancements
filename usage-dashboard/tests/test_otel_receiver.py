"""Tests for USAGE-2: OTel OTLP HTTP/JSON Receiver."""

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from otel_receiver import (
    parse_otlp_metrics,
    parse_otlp_logs,
    append_metrics,
    load_metrics,
    summarize_metrics,
    format_summary,
    get_daily_file,
    get_storage_dir,
    start_server,
    _extract_attributes,
    _extract_data_points,
    _parse_data_point,
    _extract_log_body,
    OTLPHandler,
    DEFAULT_PORT,
)


# ---------------------------------------------------------------------------
# Test fixtures — realistic OTLP payloads matching Claude Code's format
# ---------------------------------------------------------------------------

def make_otlp_metrics_payload(
    metric_name="claude_code.token.usage",
    value=1500,
    unit="tokens",
    attributes=None,
    resource_attrs=None,
):
    """Build a realistic OTLP ExportMetricsServiceRequest."""
    if attributes is None:
        attributes = [
            {"key": "type", "value": {"stringValue": "input"}},
            {"key": "model", "value": {"stringValue": "claude-sonnet-4-6"}},
        ]
    if resource_attrs is None:
        resource_attrs = [
            {"key": "service.name", "value": {"stringValue": "claude-code"}},
            {"key": "session.id", "value": {"stringValue": "test-session-123"}},
        ]

    return {
        "resourceMetrics": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeMetrics": [
                    {
                        "scope": {"name": "com.anthropic.claude_code"},
                        "metrics": [
                            {
                                "name": metric_name,
                                "unit": unit,
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "asInt": value,
                                            "attributes": attributes,
                                            "timeUnixNano": "1710547200000000000",
                                            "startTimeUnixNano": "1710543600000000000",
                                        }
                                    ],
                                    "aggregationTemporality": 1,
                                    "isMonotonic": True,
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }


def make_otlp_logs_payload(
    event_name="user_prompt",
    body="test prompt",
    attributes=None,
):
    """Build a realistic OTLP ExportLogsServiceRequest."""
    if attributes is None:
        attributes = [
            {"key": "event.name", "value": {"stringValue": event_name}},
            {"key": "prompt_length", "value": {"intValue": len(body)}},
        ]

    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "claude-code"}},
                    ]
                },
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": "1710547200000000000",
                                "severityText": "INFO",
                                "severityNumber": 9,
                                "body": {"stringValue": body},
                                "attributes": attributes,
                            }
                        ]
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestExtractAttributes(unittest.TestCase):
    """Tests for _extract_attributes."""

    def test_string_value(self):
        attrs = [{"key": "model", "value": {"stringValue": "claude-sonnet-4-6"}}]
        self.assertEqual(_extract_attributes(attrs), {"model": "claude-sonnet-4-6"})

    def test_int_value(self):
        attrs = [{"key": "count", "value": {"intValue": 42}}]
        self.assertEqual(_extract_attributes(attrs), {"count": 42})

    def test_double_value(self):
        attrs = [{"key": "cost", "value": {"doubleValue": 0.015}}]
        self.assertEqual(_extract_attributes(attrs), {"cost": 0.015})

    def test_bool_value(self):
        attrs = [{"key": "success", "value": {"boolValue": True}}]
        self.assertEqual(_extract_attributes(attrs), {"success": True})

    def test_multiple_attributes(self):
        attrs = [
            {"key": "type", "value": {"stringValue": "input"}},
            {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
        ]
        result = _extract_attributes(attrs)
        self.assertEqual(result["type"], "input")
        self.assertEqual(result["model"], "claude-opus-4-6")

    def test_empty_list(self):
        self.assertEqual(_extract_attributes([]), {})

    def test_not_a_list(self):
        self.assertEqual(_extract_attributes("invalid"), {})

    def test_missing_key(self):
        attrs = [{"value": {"stringValue": "x"}}]
        self.assertEqual(_extract_attributes(attrs), {})

    def test_plain_value(self):
        attrs = [{"key": "simple", "value": "direct_string"}]
        self.assertEqual(_extract_attributes(attrs), {"simple": "direct_string"})


class TestParseDataPoint(unittest.TestCase):
    """Tests for _parse_data_point."""

    def test_as_int(self):
        dp = {"asInt": 1500, "attributes": [], "timeUnixNano": "123"}
        result = _parse_data_point(dp)
        self.assertEqual(result["value"], 1500)

    def test_as_double(self):
        dp = {"asDouble": 0.0234, "attributes": [], "timeUnixNano": "123"}
        result = _parse_data_point(dp)
        self.assertAlmostEqual(result["value"], 0.0234)

    def test_string_int_value(self):
        dp = {"asInt": "500", "attributes": [], "timeUnixNano": "123"}
        result = _parse_data_point(dp)
        self.assertEqual(result["value"], 500)

    def test_string_double_value(self):
        dp = {"asDouble": "1.5", "attributes": [], "timeUnixNano": "123"}
        result = _parse_data_point(dp)
        self.assertAlmostEqual(result["value"], 1.5)

    def test_missing_value(self):
        dp = {"attributes": [], "timeUnixNano": "123"}
        result = _parse_data_point(dp)
        self.assertEqual(result["value"], 0)

    def test_timestamp_preserved(self):
        dp = {"asInt": 1, "attributes": [], "timeUnixNano": "999", "startTimeUnixNano": "100"}
        result = _parse_data_point(dp)
        self.assertEqual(result["timestamp"], "999")
        self.assertEqual(result["start_time"], "100")


class TestExtractDataPoints(unittest.TestCase):
    """Tests for _extract_data_points."""

    def test_sum_metric(self):
        metric = {
            "sum": {
                "dataPoints": [
                    {"asInt": 100, "attributes": [], "timeUnixNano": "1"}
                ]
            }
        }
        points = _extract_data_points(metric)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value"], 100)

    def test_gauge_metric(self):
        metric = {
            "gauge": {
                "dataPoints": [
                    {"asDouble": 45.5, "attributes": [], "timeUnixNano": "1"}
                ]
            }
        }
        points = _extract_data_points(metric)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0]["value"], 45.5)

    def test_histogram_metric(self):
        metric = {
            "histogram": {
                "dataPoints": [
                    {"sum": 250.5, "count": 10, "attributes": [], "timeUnixNano": "1"}
                ]
            }
        }
        points = _extract_data_points(metric)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0]["value"], 250.5)
        self.assertEqual(points[0]["count"], 10)

    def test_empty_metric(self):
        self.assertEqual(_extract_data_points({}), [])

    def test_multiple_data_points(self):
        metric = {
            "sum": {
                "dataPoints": [
                    {"asInt": 100, "attributes": [], "timeUnixNano": "1"},
                    {"asInt": 200, "attributes": [], "timeUnixNano": "2"},
                ]
            }
        }
        points = _extract_data_points(metric)
        self.assertEqual(len(points), 2)


class TestParseOtlpMetrics(unittest.TestCase):
    """Tests for parse_otlp_metrics — full payload parsing."""

    def test_token_usage_metric(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.token.usage",
            value=1500,
            unit="tokens",
        )
        records = parse_otlp_metrics(payload)
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["metric"], "claude_code.token.usage")
        self.assertEqual(r["value"], 1500)
        self.assertEqual(r["unit"], "tokens")
        self.assertEqual(r["attributes"]["type"], "input")
        self.assertEqual(r["attributes"]["model"], "claude-sonnet-4-6")
        self.assertEqual(r["resource"]["service.name"], "claude-code")

    def test_cost_usage_metric(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.cost.usage",
            value=0.0234,
            unit="USD",
            attributes=[{"key": "model", "value": {"stringValue": "claude-opus-4-6"}}],
        )
        # Patch asInt to asDouble for cost
        payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["sum"]["dataPoints"][0] = {
            "asDouble": 0.0234,
            "attributes": [{"key": "model", "value": {"stringValue": "claude-opus-4-6"}}],
            "timeUnixNano": "1710547200000000000",
        }
        records = parse_otlp_metrics(payload)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0]["value"], 0.0234)

    def test_empty_payload(self):
        self.assertEqual(parse_otlp_metrics({}), [])

    def test_empty_resource_metrics(self):
        self.assertEqual(parse_otlp_metrics({"resourceMetrics": []}), [])

    def test_multiple_metrics_in_scope(self):
        payload = make_otlp_metrics_payload()
        # Add a second metric
        payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"].append({
            "name": "claude_code.cost.usage",
            "unit": "USD",
            "sum": {
                "dataPoints": [
                    {"asDouble": 0.01, "attributes": [], "timeUnixNano": "1"}
                ]
            },
        })
        records = parse_otlp_metrics(payload)
        self.assertEqual(len(records), 2)

    def test_session_count_metric(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.session.count",
            value=1,
            unit="count",
            attributes=[],
        )
        records = parse_otlp_metrics(payload)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["metric"], "claude_code.session.count")
        self.assertEqual(records[0]["value"], 1)

    def test_lines_of_code_metric(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.lines_of_code.count",
            value=150,
            unit="count",
            attributes=[{"key": "type", "value": {"stringValue": "added"}}],
        )
        records = parse_otlp_metrics(payload)
        self.assertEqual(records[0]["attributes"]["type"], "added")

    def test_active_time_metric(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.active_time.total",
            value=120,
            unit="s",
            attributes=[{"key": "type", "value": {"stringValue": "cli"}}],
        )
        records = parse_otlp_metrics(payload)
        self.assertEqual(records[0]["metric"], "claude_code.active_time.total")
        self.assertEqual(records[0]["attributes"]["type"], "cli")

    def test_scope_name_captured(self):
        payload = make_otlp_metrics_payload()
        records = parse_otlp_metrics(payload)
        self.assertEqual(records[0]["scope"], "com.anthropic.claude_code")


class TestParseOtlpLogs(unittest.TestCase):
    """Tests for parse_otlp_logs."""

    def test_user_prompt_event(self):
        payload = make_otlp_logs_payload(event_name="user_prompt", body="build a function")
        records = parse_otlp_logs(payload)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["body"], "build a function")
        self.assertEqual(records[0]["attributes"]["event.name"], "user_prompt")

    def test_empty_payload(self):
        self.assertEqual(parse_otlp_logs({}), [])

    def test_tool_result_event(self):
        payload = make_otlp_logs_payload(
            event_name="tool_result",
            body="",
            attributes=[
                {"key": "event.name", "value": {"stringValue": "tool_result"}},
                {"key": "tool_name", "value": {"stringValue": "Read"}},
                {"key": "success", "value": {"stringValue": "true"}},
                {"key": "duration_ms", "value": {"intValue": 45}},
            ],
        )
        records = parse_otlp_logs(payload)
        self.assertEqual(records[0]["attributes"]["tool_name"], "Read")
        self.assertEqual(records[0]["attributes"]["duration_ms"], 45)

    def test_extract_log_body_string(self):
        self.assertEqual(_extract_log_body({"stringValue": "hello"}), "hello")

    def test_extract_log_body_dict(self):
        result = _extract_log_body({"kvlistValue": {"values": []}})
        self.assertIn("kvlistValue", result)

    def test_extract_log_body_plain(self):
        self.assertEqual(_extract_log_body("plain"), "plain")


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStorage(unittest.TestCase):
    """Tests for JSONL storage functions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_append_metrics(self):
        records = [{"metric": "test", "value": 1}]
        written = append_metrics(records, self.storage)
        self.assertEqual(written, 1)

        # Verify file exists and is valid JSONL
        files = list(self.storage.glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        with open(files[0]) as f:
            data = json.loads(f.readline())
        self.assertEqual(data["metric"], "test")
        self.assertIn("_received_at", data)

    def test_append_empty_list(self):
        self.assertEqual(append_metrics([], self.storage), 0)

    def test_append_multiple_records(self):
        records = [{"metric": f"m{i}", "value": i} for i in range(5)]
        written = append_metrics(records, self.storage)
        self.assertEqual(written, 5)

    def test_get_daily_file(self):
        dt = datetime(2026, 3, 16, tzinfo=timezone.utc)
        path = get_daily_file(self.storage, dt)
        self.assertEqual(path.name, "2026-03-16.jsonl")

    def test_load_metrics_empty_dir(self):
        records = load_metrics(storage_dir=self.storage, hours=24)
        self.assertEqual(records, [])

    def test_load_metrics_roundtrip(self):
        records = [
            {"metric": "claude_code.token.usage", "value": 1500},
            {"metric": "claude_code.cost.usage", "value": 0.02},
        ]
        append_metrics(records, self.storage)
        loaded = load_metrics(storage_dir=self.storage, hours=24)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["metric"], "claude_code.token.usage")

    def test_load_metrics_filter_by_name(self):
        records = [
            {"metric": "claude_code.token.usage", "value": 1500},
            {"metric": "claude_code.cost.usage", "value": 0.02},
        ]
        append_metrics(records, self.storage)
        loaded = load_metrics(
            storage_dir=self.storage, hours=24, metric_filter="claude_code.cost.usage"
        )
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["metric"], "claude_code.cost.usage")

    def test_load_metrics_nonexistent_dir(self):
        fake = Path(self.tmpdir) / "nonexistent"
        records = load_metrics(storage_dir=fake, hours=24)
        self.assertEqual(records, [])

    def test_get_storage_dir_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_OTEL_STORAGE_DIR", None)
            d = get_storage_dir()
            self.assertTrue(d.name == ".claude-otel-metrics")

    def test_get_storage_dir_custom(self):
        custom = Path(self.tmpdir) / "custom"
        with patch.dict(os.environ, {"CLAUDE_OTEL_STORAGE_DIR": str(custom)}):
            d = get_storage_dir()
            self.assertEqual(d, custom)
            self.assertTrue(d.exists())


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):
    """Tests for summarize_metrics and format_summary."""

    def test_empty_records(self):
        s = summarize_metrics([])
        self.assertEqual(s["record_count"], 0)
        self.assertEqual(s["metrics"], {})

    def test_single_metric(self):
        records = [{"metric": "claude_code.session.count", "value": 1, "attributes": {}, "unit": "count"}]
        s = summarize_metrics(records)
        self.assertEqual(s["record_count"], 1)
        self.assertIn("claude_code.session.count", s["metrics"])
        self.assertEqual(s["metrics"]["claude_code.session.count"]["total"], 1.0)

    def test_grouped_by_type(self):
        records = [
            {"metric": "claude_code.token.usage", "value": 1000, "attributes": {"type": "input"}, "unit": "tokens"},
            {"metric": "claude_code.token.usage", "value": 500, "attributes": {"type": "output"}, "unit": "tokens"},
        ]
        s = summarize_metrics(records)
        m = s["metrics"]["claude_code.token.usage"]
        self.assertEqual(m["total"], 1500.0)
        self.assertEqual(m["by_type"]["input"]["total"], 1000.0)
        self.assertEqual(m["by_type"]["output"]["total"], 500.0)

    def test_grouped_by_model(self):
        records = [
            {"metric": "claude_code.cost.usage", "value": 0.01, "attributes": {"model": "claude-sonnet-4-6"}, "unit": "USD"},
            {"metric": "claude_code.cost.usage", "value": 0.05, "attributes": {"model": "claude-opus-4-6"}, "unit": "USD"},
        ]
        s = summarize_metrics(records)
        m = s["metrics"]["claude_code.cost.usage"]
        self.assertAlmostEqual(m["total"], 0.06)
        self.assertAlmostEqual(m["by_model"]["claude-opus-4-6"]["total"], 0.05)

    def test_format_summary_output(self):
        records = [
            {"metric": "claude_code.token.usage", "value": 1000, "attributes": {"type": "input"}, "unit": "tokens"},
        ]
        s = summarize_metrics(records)
        output = format_summary(s)
        self.assertIn("OTel Metrics Summary", output)
        self.assertIn("claude_code.token.usage", output)
        self.assertIn("input", output)

    def test_format_summary_empty(self):
        s = summarize_metrics([])
        output = format_summary(s)
        self.assertIn("Total records: 0", output)


# ---------------------------------------------------------------------------
# HTTP Server tests
# ---------------------------------------------------------------------------

class TestHTTPServer(unittest.TestCase):
    """Tests for the OTLP HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.storage = Path(cls.tmpdir)
        cls.port = 14318  # Use a non-standard port for testing
        cls.server = start_server(cls.port, cls.storage)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)  # Let server start

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _request(self, method, path, body=None):
        """Make an HTTP request to the test server."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if body is not None:
            conn.request(method, path, json.dumps(body).encode(), headers)
        else:
            conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        return resp.status, data

    def test_health_endpoint(self):
        status, data = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_root_endpoint(self):
        status, data = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_post_metrics(self):
        payload = make_otlp_metrics_payload()
        status, data = self._request("POST", "/v1/metrics", payload)
        self.assertEqual(status, 200)

    def test_post_logs(self):
        payload = make_otlp_logs_payload()
        status, data = self._request("POST", "/v1/logs", payload)
        self.assertEqual(status, 200)

    def test_post_unknown_path(self):
        status, data = self._request("POST", "/v1/unknown", {})
        self.assertEqual(status, 404)

    def test_post_invalid_json(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/v1/metrics", b"not json", {"Content-Type": "application/json", "Content-Length": "8"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 400)
        conn.close()

    def test_post_empty_body(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/v1/metrics", b"", {"Content-Type": "application/json", "Content-Length": "0"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()

    def test_get_unknown_path(self):
        status, data = self._request("GET", "/unknown")
        self.assertEqual(status, 404)

    def test_metrics_stored_after_post(self):
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.test.counter",
            value=42,
        )
        self._request("POST", "/v1/metrics", payload)

        # Verify stored
        records = load_metrics(storage_dir=self.storage, hours=1, metric_filter="claude_code.test.counter")
        found = [r for r in records if r["metric"] == "claude_code.test.counter"]
        self.assertTrue(len(found) >= 1)
        self.assertEqual(found[-1]["value"], 42)

    def test_multiple_cc_metrics_in_one_request(self):
        """Simulate a real CC metrics export with multiple metrics."""
        payload = {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "claude-code"}},
                            {"key": "session.id", "value": {"stringValue": "sess-abc"}},
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {"name": "com.anthropic.claude_code"},
                            "metrics": [
                                {
                                    "name": "claude_code.token.usage",
                                    "unit": "tokens",
                                    "sum": {
                                        "dataPoints": [
                                            {
                                                "asInt": 5000,
                                                "attributes": [
                                                    {"key": "type", "value": {"stringValue": "input"}},
                                                    {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                                ],
                                                "timeUnixNano": "1710547200000000000",
                                            },
                                            {
                                                "asInt": 800,
                                                "attributes": [
                                                    {"key": "type", "value": {"stringValue": "output"}},
                                                    {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                                ],
                                                "timeUnixNano": "1710547200000000000",
                                            },
                                        ],
                                    },
                                },
                                {
                                    "name": "claude_code.cost.usage",
                                    "unit": "USD",
                                    "sum": {
                                        "dataPoints": [
                                            {
                                                "asDouble": 0.135,
                                                "attributes": [
                                                    {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
                                                ],
                                                "timeUnixNano": "1710547200000000000",
                                            }
                                        ],
                                    },
                                },
                                {
                                    "name": "claude_code.active_time.total",
                                    "unit": "s",
                                    "sum": {
                                        "dataPoints": [
                                            {
                                                "asInt": 45,
                                                "attributes": [
                                                    {"key": "type", "value": {"stringValue": "cli"}},
                                                ],
                                                "timeUnixNano": "1710547200000000000",
                                            },
                                            {
                                                "asInt": 3,
                                                "attributes": [
                                                    {"key": "type", "value": {"stringValue": "user"}},
                                                ],
                                                "timeUnixNano": "1710547200000000000",
                                            },
                                        ],
                                    },
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        status, _ = self._request("POST", "/v1/metrics", payload)
        self.assertEqual(status, 200)

        # Verify all 4 data points were stored
        records = load_metrics(storage_dir=self.storage, hours=1)
        token_records = [r for r in records if r["metric"] == "claude_code.token.usage"]
        cost_records = [r for r in records if r["metric"] == "claude_code.cost.usage"]
        time_records = [r for r in records if r["metric"] == "claude_code.active_time.total"]
        self.assertTrue(len(token_records) >= 2)
        self.assertTrue(len(cost_records) >= 1)
        self.assertTrue(len(time_records) >= 2)


# ---------------------------------------------------------------------------
# Integration: full pipeline test
# ---------------------------------------------------------------------------

class TestFullPipeline(unittest.TestCase):
    """End-to-end: parse → store → load → summarize."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_cycle(self):
        # 1. Parse a realistic payload
        payload = make_otlp_metrics_payload(
            metric_name="claude_code.token.usage",
            value=2000,
            attributes=[
                {"key": "type", "value": {"stringValue": "output"}},
                {"key": "model", "value": {"stringValue": "claude-opus-4-6"}},
            ],
        )
        records = parse_otlp_metrics(payload)
        self.assertEqual(len(records), 1)

        # 2. Store
        written = append_metrics(records, self.storage)
        self.assertEqual(written, 1)

        # 3. Load
        loaded = load_metrics(storage_dir=self.storage, hours=24)
        self.assertEqual(len(loaded), 1)

        # 4. Summarize
        summary = summarize_metrics(loaded)
        self.assertEqual(summary["record_count"], 1)
        m = summary["metrics"]["claude_code.token.usage"]
        self.assertEqual(m["total"], 2000.0)
        self.assertEqual(m["by_type"]["output"]["total"], 2000.0)
        self.assertEqual(m["by_model"]["claude-opus-4-6"]["total"], 2000.0)

    def test_multi_session_aggregation(self):
        """Simulate metrics from two different sessions."""
        for session_id, value in [("sess-1", 1000), ("sess-2", 3000)]:
            payload = make_otlp_metrics_payload(
                metric_name="claude_code.token.usage",
                value=value,
                resource_attrs=[
                    {"key": "service.name", "value": {"stringValue": "claude-code"}},
                    {"key": "session.id", "value": {"stringValue": session_id}},
                ],
            )
            records = parse_otlp_metrics(payload)
            append_metrics(records, self.storage)

        loaded = load_metrics(storage_dir=self.storage, hours=24)
        summary = summarize_metrics(loaded)
        m = summary["metrics"]["claude_code.token.usage"]
        self.assertEqual(m["total"], 4000.0)
        self.assertEqual(m["count"], 2)


if __name__ == "__main__":
    unittest.main()
