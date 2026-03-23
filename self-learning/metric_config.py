#!/usr/bin/env python3
"""metric_config.py — Centralized metric configuration for self-learning.

Loads default metrics from metric_defaults.json, with optional user overrides
from ~/.cca-metrics.json. Eliminates hardcoded magic numbers across the
self-learning module.

Usage:
    from metric_config import get_metric

    # Get a single metric with section.key notation
    threshold = get_metric("strategy_health.min_sample_size")  # -> 20

    # Get with explicit default (if key missing from both files)
    val = get_metric("strategy_health.new_key", default=42)

    # Get entire section
    section = get_section("strategy_health")  # -> dict

User overrides:
    Create ~/.cca-metrics.json with any subset of keys to override defaults.
    Only specified keys are overridden — everything else keeps defaults.
"""

import json
from pathlib import Path
from typing import Any, Optional

_DEFAULTS_FILE = Path(__file__).parent / "metric_defaults.json"
_USER_CONFIG_FILE = Path.home() / ".cca-metrics.json"

# Module-level cache (cleared by reload())
_cache: Optional[dict] = None


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively. Override wins on conflicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_config() -> dict:
    """Load defaults + user overrides. Cached after first call."""
    global _cache
    if _cache is not None:
        return _cache

    # Load defaults (must exist)
    if not _DEFAULTS_FILE.exists():
        raise FileNotFoundError(f"Metric defaults not found: {_DEFAULTS_FILE}")
    with open(_DEFAULTS_FILE) as f:
        config = json.load(f)

    # Remove _meta section (not a metric section)
    config.pop("_meta", None)

    # Merge user overrides if present
    if _USER_CONFIG_FILE.exists():
        try:
            with open(_USER_CONFIG_FILE) as f:
                user = json.load(f)
            user.pop("_meta", None)
            config = _deep_merge(config, user)
        except (json.JSONDecodeError, OSError):
            pass  # Invalid user config — use defaults only

    _cache = config
    return config


def get_metric(key: str, default: Any = None) -> Any:
    """Get a metric value using section.key notation.

    Args:
        key: Dot-separated path, e.g. "strategy_health.min_sample_size"
        default: Fallback if key not found in config or defaults

    Returns:
        The metric value, or default if not found.
    """
    config = _load_config()
    parts = key.split(".", 1)
    if len(parts) != 2:
        return default
    section, metric_key = parts
    return config.get(section, {}).get(metric_key, default)


def get_section(section: str) -> dict:
    """Get all metrics for a section.

    Args:
        section: Section name, e.g. "strategy_health"

    Returns:
        Dict of metric_key -> value. Empty dict if section not found.
    """
    config = _load_config()
    return dict(config.get(section, {}))


def reload() -> dict:
    """Force reload config from disk. Returns the new config."""
    global _cache
    _cache = None
    return _load_config()


def all_sections() -> list[str]:
    """List all metric sections."""
    config = _load_config()
    return list(config.keys())


def dump() -> dict:
    """Return the full merged config (for debugging/inspection)."""
    return dict(_load_config())
