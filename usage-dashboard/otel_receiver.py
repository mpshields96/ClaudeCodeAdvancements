"""
USAGE-2: Lightweight OTLP HTTP/JSON Receiver

Receives OpenTelemetry metrics from Claude Code via HTTP/JSON protocol.
Stores metrics locally in ~/.claude-otel-metrics/ as JSONL files (one per day).
No external dependencies — stdlib only.

Setup:
  1. Run: python3 otel_receiver.py start [--port 4318]
  2. Set env vars before launching Claude Code:
       export CLAUDE_CODE_ENABLE_TELEMETRY=1
       export OTEL_METRICS_EXPORTER=otlp
       export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
       export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

Usage:
  python3 otel_receiver.py start [--port PORT]    # Start receiver
  python3 otel_receiver.py status                  # Check if running
  python3 otel_receiver.py query [--hours N]       # Query stored metrics
  python3 otel_receiver.py summary [--hours N]     # Summarize recent metrics
"""

import argparse
import http.server
import json
import os
import signal
import socket
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

DEFAULT_STORAGE_DIR = Path.home() / ".claude-otel-metrics"
DEFAULT_PORT = 4318
PID_FILE = Path.home() / ".claude-otel-receiver.pid"


def get_storage_dir() -> Path:
    """Return the storage directory, creating it if needed."""
    path = Path(os.environ.get("CLAUDE_OTEL_STORAGE_DIR", str(DEFAULT_STORAGE_DIR)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_daily_file(storage_dir: Path, dt: datetime | None = None) -> Path:
    """Return the JSONL file path for a given date."""
    if dt is None:
        dt = datetime.now(tz=timezone.utc)
    return storage_dir / f"{dt.strftime('%Y-%m-%d')}.jsonl"


def append_metrics(records: list[dict], storage_dir: Path | None = None) -> int:
    """
    Append metric records to the daily JSONL file.

    Returns the number of records written.
    """
    if not records:
        return 0
    if storage_dir is None:
        storage_dir = get_storage_dir()

    now = datetime.now(tz=timezone.utc)
    daily_file = get_daily_file(storage_dir, now)

    written = 0
    with open(daily_file, "a", encoding="utf-8") as f:
        for record in records:
            record["_received_at"] = now.isoformat()
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
            written += 1

    return written


# ---------------------------------------------------------------------------
# OTLP JSON parsing
# ---------------------------------------------------------------------------

def parse_otlp_metrics(payload: dict) -> list[dict]:
    """
    Parse an OTLP ExportMetricsServiceRequest JSON payload.

    Extracts individual data points from the nested OTLP structure and
    flattens them into simple records for storage.

    Returns a list of flat metric dicts.
    """
    records = []

    resource_metrics = payload.get("resourceMetrics", [])
    for rm in resource_metrics:
        # Extract resource attributes
        resource_attrs = _extract_attributes(
            rm.get("resource", {}).get("attributes", [])
        )

        scope_metrics = rm.get("scopeMetrics", [])
        for sm in scope_metrics:
            scope_name = sm.get("scope", {}).get("name", "")

            metrics = sm.get("metrics", [])
            for metric in metrics:
                metric_name = metric.get("name", "")
                metric_unit = metric.get("unit", "")
                metric_desc = metric.get("description", "")

                # Handle different metric types
                data_points = _extract_data_points(metric)
                for dp in data_points:
                    record = {
                        "metric": metric_name,
                        "unit": metric_unit,
                        "value": dp.get("value"),
                        "attributes": dp.get("attributes", {}),
                        "resource": resource_attrs,
                        "scope": scope_name,
                        "timestamp": dp.get("timestamp"),
                        "start_time": dp.get("start_time"),
                    }
                    records.append(record)

    return records


def _extract_data_points(metric: dict) -> list[dict]:
    """Extract data points from any metric type (sum, gauge, histogram)."""
    points = []

    # Sum metric (most CC metrics are sums)
    if "sum" in metric:
        for dp in metric["sum"].get("dataPoints", []):
            points.append(_parse_data_point(dp))

    # Gauge metric
    elif "gauge" in metric:
        for dp in metric["gauge"].get("dataPoints", []):
            points.append(_parse_data_point(dp))

    # Histogram metric
    elif "histogram" in metric:
        for dp in metric["histogram"].get("dataPoints", []):
            point = {
                "value": dp.get("sum", 0),
                "count": dp.get("count", 0),
                "attributes": _extract_attributes(dp.get("attributes", [])),
                "timestamp": dp.get("timeUnixNano"),
                "start_time": dp.get("startTimeUnixNano"),
            }
            points.append(point)

    return points


def _parse_data_point(dp: dict) -> dict:
    """Parse a single numeric data point."""
    # Value can be asInt or asDouble
    value = dp.get("asDouble", dp.get("asInt", 0))
    if isinstance(value, str):
        try:
            value = float(value) if "." in value else int(value)
        except (ValueError, TypeError):
            value = 0

    return {
        "value": value,
        "attributes": _extract_attributes(dp.get("attributes", [])),
        "timestamp": dp.get("timeUnixNano"),
        "start_time": dp.get("startTimeUnixNano"),
    }


def _extract_attributes(attrs: list) -> dict:
    """Convert OTLP attribute list to a flat dict."""
    result = {}
    if not isinstance(attrs, list):
        return result

    for attr in attrs:
        key = attr.get("key", "")
        value_obj = attr.get("value", {})
        if isinstance(value_obj, dict):
            # OTLP uses typed values: stringValue, intValue, doubleValue, boolValue
            value = (
                value_obj.get("stringValue")
                or value_obj.get("intValue")
                or value_obj.get("doubleValue")
                or value_obj.get("boolValue")
            )
        else:
            value = value_obj
        if key:
            result[key] = value

    return result


# ---------------------------------------------------------------------------
# OTLP Events/Logs parsing
# ---------------------------------------------------------------------------

def parse_otlp_logs(payload: dict) -> list[dict]:
    """
    Parse an OTLP ExportLogsServiceRequest JSON payload.

    Extracts log/event records and flattens them for storage.
    Returns a list of flat event dicts.
    """
    records = []

    resource_logs = payload.get("resourceLogs", [])
    for rl in resource_logs:
        resource_attrs = _extract_attributes(
            rl.get("resource", {}).get("attributes", [])
        )

        scope_logs = rl.get("scopeLogs", [])
        for sl in scope_logs:
            log_records = sl.get("logRecords", [])
            for lr in log_records:
                record = {
                    "event": lr.get("severityText", ""),
                    "body": _extract_log_body(lr.get("body", {})),
                    "attributes": _extract_attributes(lr.get("attributes", [])),
                    "resource": resource_attrs,
                    "timestamp": lr.get("timeUnixNano"),
                    "severity": lr.get("severityNumber", 0),
                }
                records.append(record)

    return records


def _extract_log_body(body: dict) -> str:
    """Extract log body value."""
    if isinstance(body, dict):
        return body.get("stringValue", str(body))
    return str(body)


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class OTLPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OTLP JSON requests."""

    storage_dir: Path = DEFAULT_STORAGE_DIR
    metrics_received: int = 0
    events_received: int = 0
    _lock = threading.Lock()

    def do_POST(self):
        """Handle POST requests for OTLP metrics and logs."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_response(200, {})
            return

        if content_length > 10 * 1024 * 1024:  # 10MB limit
            self._send_response(413, {"error": "Payload too large"})
            return

        try:
            body = self.rfile.read(content_length)
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_response(400, {"error": "Invalid JSON"})
            return

        path = self.path.rstrip("/")

        if path == "/v1/metrics":
            records = parse_otlp_metrics(payload)
            written = append_metrics(records, self.storage_dir)
            with self._lock:
                OTLPHandler.metrics_received += written
            self._send_response(200, {})

        elif path == "/v1/logs":
            records = parse_otlp_logs(payload)
            written = append_metrics(records, self.storage_dir)
            with self._lock:
                OTLPHandler.events_received += written
            self._send_response(200, {})

        else:
            self._send_response(404, {"error": f"Unknown path: {path}"})

    def do_GET(self):
        """Handle GET requests for status check."""
        path = self.path.rstrip("/")
        if path in ("/health", "/", ""):
            with self._lock:
                status = {
                    "status": "ok",
                    "metrics_received": OTLPHandler.metrics_received,
                    "events_received": OTLPHandler.events_received,
                    "storage_dir": str(self.storage_dir),
                }
            self._send_response(200, status)
        else:
            self._send_response(404, {"error": "Not found"})

    def _send_response(self, code: int, body: dict):
        """Send a JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default request logging to stderr."""
        pass


def start_server(port: int = DEFAULT_PORT, storage_dir: Path | None = None) -> http.server.HTTPServer:
    """Start the OTLP receiver server."""
    if storage_dir is None:
        storage_dir = get_storage_dir()

    OTLPHandler.storage_dir = storage_dir
    OTLPHandler.metrics_received = 0
    OTLPHandler.events_received = 0

    server = http.server.HTTPServer(("127.0.0.1", port), OTLPHandler)
    return server


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def load_metrics(
    storage_dir: Path | None = None,
    hours: int = 24,
    metric_filter: str | None = None,
) -> list[dict]:
    """
    Load metrics from JSONL storage files.

    Args:
        storage_dir: Storage directory (default: ~/.claude-otel-metrics)
        hours: How many hours back to look (default: 24)
        metric_filter: Only return metrics matching this name (optional)

    Returns a list of metric record dicts.
    """
    if storage_dir is None:
        storage_dir = get_storage_dir()

    if not storage_dir.exists():
        return []

    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(hours=hours)
    records = []

    # Check files for the relevant date range
    date_cursor = cutoff.date()
    end_date = now.date()
    while date_cursor <= end_date:
        daily_file = storage_dir / f"{date_cursor.isoformat()}.jsonl"
        if daily_file.exists():
            try:
                with open(daily_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Filter by metric name if specified
                        if metric_filter and record.get("metric") != metric_filter:
                            continue

                        records.append(record)
            except OSError:
                pass

        date_cursor += timedelta(days=1)

    return records


def summarize_metrics(records: list[dict]) -> dict:
    """
    Summarize a list of metric records into an aggregate report.

    Returns a dict with per-metric summaries.
    """
    summary = {
        "record_count": len(records),
        "metrics": {},
    }

    for record in records:
        name = record.get("metric", "unknown")
        value = record.get("value", 0)
        attrs = record.get("attributes", {})

        if name not in summary["metrics"]:
            summary["metrics"][name] = {
                "count": 0,
                "total": 0.0,
                "by_type": {},
                "by_model": {},
                "unit": record.get("unit", ""),
            }

        m = summary["metrics"][name]
        m["count"] += 1

        if isinstance(value, (int, float)):
            m["total"] += value

        # Group by type attribute (for token.usage, active_time, LOC)
        type_val = attrs.get("type", "")
        if type_val:
            if type_val not in m["by_type"]:
                m["by_type"][type_val] = {"count": 0, "total": 0.0}
            m["by_type"][type_val]["count"] += 1
            if isinstance(value, (int, float)):
                m["by_type"][type_val]["total"] += value

        # Group by model attribute (for token.usage, cost.usage)
        model_val = attrs.get("model", "")
        if model_val:
            if model_val not in m["by_model"]:
                m["by_model"][model_val] = {"count": 0, "total": 0.0}
            m["by_model"][model_val]["count"] += 1
            if isinstance(value, (int, float)):
                m["by_model"][model_val]["total"] += value

    return summary


def format_summary(summary: dict) -> str:
    """Format a metrics summary for CLI display."""
    lines = []
    lines.append("")
    lines.append("OTel Metrics Summary")
    lines.append("=" * 60)
    lines.append(f"  Total records: {summary['record_count']}")
    lines.append("")

    for name, m in sorted(summary["metrics"].items()):
        unit = m["unit"] or ""
        unit_str = f" ({unit})" if unit else ""
        lines.append(f"  {name}{unit_str}")
        lines.append(f"    Data points: {m['count']}  |  Total: {m['total']:.4f}")

        if m["by_type"]:
            for t, td in sorted(m["by_type"].items()):
                lines.append(f"      {t}: {td['total']:.4f} ({td['count']} points)")

        if m["by_model"]:
            for model, md in sorted(m["by_model"].items()):
                lines.append(f"      [{model}]: {md['total']:.4f} ({md['count']} points)")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    """Start the OTLP receiver."""
    port = args.port
    storage_dir = get_storage_dir()

    # Check if port is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        print(f"Port {port} is already in use. Receiver may already be running.")
        print(f"Check: python3 {__file__} status")
        sys.exit(1)
    finally:
        sock.close()

    server = start_server(port, storage_dir)

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    # Handle shutdown
    def shutdown(signum, frame):
        print("\nShutting down...")
        server.shutdown()
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"OTLP receiver listening on http://127.0.0.1:{port}")
    print(f"Storage: {storage_dir}")
    print(f"PID: {os.getpid()}")
    print("")
    print("Configure Claude Code with:")
    print(f"  export CLAUDE_CODE_ENABLE_TELEMETRY=1")
    print(f"  export OTEL_METRICS_EXPORTER=otlp")
    print(f"  export OTEL_LOGS_EXPORTER=otlp")
    print(f"  export OTEL_EXPORTER_OTLP_PROTOCOL=http/json")
    print(f"  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:{port}")
    print("")
    print("Press Ctrl+C to stop.")

    server.serve_forever()


def cmd_status(args: argparse.Namespace) -> None:
    """Check receiver status."""
    port = args.port
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            print(f"Receiver: RUNNING on port {port}")
            print(f"  Metrics received: {data.get('metrics_received', 0)}")
            print(f"  Events received: {data.get('events_received', 0)}")
            print(f"  Storage: {data.get('storage_dir', 'unknown')}")
    except Exception:
        print(f"Receiver: NOT RUNNING on port {port}")
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            print(f"  Stale PID file found: {pid}")


def cmd_query(args: argparse.Namespace) -> None:
    """Query stored metrics."""
    records = load_metrics(hours=args.hours, metric_filter=args.metric)
    if not records:
        print(f"No metrics found in the last {args.hours} hours.")
        return

    for record in records:
        print(json.dumps(record, indent=2))


def cmd_summary(args: argparse.Namespace) -> None:
    """Summarize stored metrics."""
    records = load_metrics(hours=args.hours)
    if not records:
        print(f"No metrics found in the last {args.hours} hours.")
        return

    summary = summarize_metrics(records)
    print(format_summary(summary))


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="otel_receiver",
        description="Lightweight OTLP HTTP/JSON receiver for Claude Code metrics",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start
    sp_start = subparsers.add_parser("start", help="Start the OTLP receiver")
    sp_start.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 4318)")
    sp_start.set_defaults(func=cmd_start)

    # status
    sp_status = subparsers.add_parser("status", help="Check receiver status")
    sp_status.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 4318)")
    sp_status.set_defaults(func=cmd_status)

    # query
    sp_query = subparsers.add_parser("query", help="Query stored metrics")
    sp_query.add_argument("--hours", type=int, default=24, help="Hours to look back (default: 24)")
    sp_query.add_argument("--metric", type=str, default=None, help="Filter by metric name")
    sp_query.set_defaults(func=cmd_query)

    # summary
    sp_summary = subparsers.add_parser("summary", help="Summarize recent metrics")
    sp_summary.add_argument("--hours", type=int, default=24, help="Hours to look back (default: 24)")
    sp_summary.set_defaults(func=cmd_summary)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
