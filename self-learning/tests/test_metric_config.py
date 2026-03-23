#!/usr/bin/env python3
"""Tests for metric_config.py — centralized self-learning metric configuration."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import metric_config


class TestMetricConfigDefaults(unittest.TestCase):
    """Test loading defaults from metric_defaults.json."""

    def setUp(self):
        metric_config.reload()

    def test_get_metric_existing(self):
        val = metric_config.get_metric("strategy_health.min_sample_size")
        self.assertEqual(val, 20)

    def test_get_metric_missing_returns_default(self):
        val = metric_config.get_metric("strategy_health.nonexistent", default=42)
        self.assertEqual(val, 42)

    def test_get_metric_missing_section_returns_default(self):
        val = metric_config.get_metric("fake_section.fake_key", default=-1)
        self.assertEqual(val, -1)

    def test_get_metric_no_dot_returns_default(self):
        val = metric_config.get_metric("nodot", default=99)
        self.assertEqual(val, 99)

    def test_get_metric_none_default(self):
        val = metric_config.get_metric("fake.key")
        self.assertIsNone(val)

    def test_get_section_existing(self):
        section = metric_config.get_section("strategy_health")
        self.assertIsInstance(section, dict)
        self.assertIn("min_sample_size", section)
        self.assertIn("kill_pnl_threshold", section)

    def test_get_section_missing(self):
        section = metric_config.get_section("nonexistent")
        self.assertEqual(section, {})

    def test_all_sections(self):
        sections = metric_config.all_sections()
        self.assertIn("strategy_health", sections)
        self.assertIn("trade_reflector", sections)
        self.assertIn("overnight_detector", sections)
        self.assertIn("reflect", sections)
        self.assertIn("detectors", sections)
        self.assertIn("principle_registry", sections)

    def test_dump_returns_full_config(self):
        config = metric_config.dump()
        self.assertIsInstance(config, dict)
        self.assertNotIn("_meta", config)
        self.assertGreater(len(config), 5)

    def test_meta_stripped(self):
        """_meta section should not appear in loaded config."""
        config = metric_config.dump()
        self.assertNotIn("_meta", config)


class TestMetricConfigAllDefaults(unittest.TestCase):
    """Verify every metric in defaults JSON is accessible."""

    def setUp(self):
        metric_config.reload()
        defaults_path = Path(__file__).parent.parent / "metric_defaults.json"
        with open(defaults_path) as f:
            self.raw = json.load(f)
        self.raw.pop("_meta", None)

    def test_all_defaults_accessible(self):
        """Every key in metric_defaults.json should be retrievable."""
        for section, metrics in self.raw.items():
            if not isinstance(metrics, dict):
                continue
            for key, expected in metrics.items():
                val = metric_config.get_metric(f"{section}.{key}")
                self.assertEqual(val, expected,
                    f"{section}.{key}: got {val}, expected {expected}")

    def test_strategy_health_values(self):
        self.assertEqual(metric_config.get_metric("strategy_health.kill_pnl_threshold"), -30.0)
        self.assertEqual(metric_config.get_metric("strategy_health.pause_loss_streak"), 8)
        self.assertEqual(metric_config.get_metric("strategy_health.monitor_win_rate_drop"), 0.10)

    def test_trade_reflector_values(self):
        self.assertEqual(metric_config.get_metric("trade_reflector.p_value_threshold"), 0.10)
        self.assertEqual(metric_config.get_metric("trade_reflector.min_streak"), 15)

    def test_overnight_detector_values(self):
        self.assertEqual(metric_config.get_metric("overnight_detector.cusum_h_threshold"), 5.0)

    def test_principle_registry_values(self):
        self.assertEqual(metric_config.get_metric("principle_registry.prune_score"), 0.3)
        self.assertEqual(metric_config.get_metric("principle_registry.reinforce_score"), 0.7)

    def test_signal_pipeline_values(self):
        self.assertEqual(metric_config.get_metric("signal_pipeline.default_min_edge"), 0.03)


class TestMetricConfigUserOverrides(unittest.TestCase):
    """Test user override merging from ~/.cca-metrics.json."""

    def test_user_override_single_key(self):
        """User can override a single metric."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"strategy_health": {"min_sample_size": 50}}, f)
            tmp_path = f.name
        try:
            with patch.object(metric_config, '_USER_CONFIG_FILE', Path(tmp_path)):
                metric_config.reload()
                val = metric_config.get_metric("strategy_health.min_sample_size")
                self.assertEqual(val, 50)
                # Other keys in same section should keep defaults
                kill = metric_config.get_metric("strategy_health.kill_pnl_threshold")
                self.assertEqual(kill, -30.0)
        finally:
            os.unlink(tmp_path)
            metric_config.reload()

    def test_user_override_new_section(self):
        """User can add entirely new sections."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"custom_strategy": {"my_threshold": 0.42}}, f)
            tmp_path = f.name
        try:
            with patch.object(metric_config, '_USER_CONFIG_FILE', Path(tmp_path)):
                metric_config.reload()
                val = metric_config.get_metric("custom_strategy.my_threshold")
                self.assertEqual(val, 0.42)
        finally:
            os.unlink(tmp_path)
            metric_config.reload()

    def test_invalid_user_config_falls_back(self):
        """Invalid JSON in user config should fall back to defaults only."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("NOT VALID JSON {{{")
            tmp_path = f.name
        try:
            with patch.object(metric_config, '_USER_CONFIG_FILE', Path(tmp_path)):
                metric_config.reload()
                val = metric_config.get_metric("strategy_health.min_sample_size")
                self.assertEqual(val, 20)
        finally:
            os.unlink(tmp_path)
            metric_config.reload()

    def test_missing_user_config_uses_defaults(self):
        """No user config file = pure defaults."""
        with patch.object(metric_config, '_USER_CONFIG_FILE', Path("/nonexistent/path.json")):
            metric_config.reload()
            val = metric_config.get_metric("strategy_health.min_sample_size")
            self.assertEqual(val, 20)


class TestDeepMerge(unittest.TestCase):
    """Test the _deep_merge helper."""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = metric_config._deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_nested_merge(self):
        base = {"section": {"x": 1, "y": 2}}
        override = {"section": {"y": 99}}
        result = metric_config._deep_merge(base, override)
        self.assertEqual(result["section"]["x"], 1)
        self.assertEqual(result["section"]["y"], 99)

    def test_base_not_modified(self):
        base = {"a": 1}
        override = {"a": 2}
        metric_config._deep_merge(base, override)
        self.assertEqual(base["a"], 1)

    def test_empty_override(self):
        base = {"a": 1}
        result = metric_config._deep_merge(base, {})
        self.assertEqual(result, {"a": 1})


class TestCaching(unittest.TestCase):
    """Test config caching behavior."""

    def test_reload_clears_cache(self):
        """reload() should clear and re-read config."""
        config1 = metric_config.dump()
        metric_config.reload()
        config2 = metric_config.dump()
        self.assertEqual(config1, config2)

    def test_get_section_returns_copy(self):
        """get_section should return a copy, not a reference."""
        section = metric_config.get_section("strategy_health")
        section["min_sample_size"] = 99999
        fresh = metric_config.get_section("strategy_health")
        self.assertNotEqual(fresh["min_sample_size"], 99999)


if __name__ == "__main__":
    unittest.main()
