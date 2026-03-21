#!/usr/bin/env python3
"""Tests for pattern_registry.py — MT-28 Phase 2: Pattern Plugin Registry."""

import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)
sys.path.insert(0, os.path.dirname(MODULE_DIR))


class TestPatternRegistry(unittest.TestCase):
    """Test the central pattern registry."""

    def setUp(self):
        # Import fresh each time to avoid cross-test state
        import pattern_registry
        pattern_registry._registry.clear()
        self.registry = pattern_registry

    def test_register_detector_decorator(self):
        """@register_detector adds detector to registry."""
        @self.registry.register_detector(
            name="test_detector",
            domain="general",
            description="A test detector",
        )
        class TestDetector(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        self.assertIn("test_detector", self.registry._registry)

    def test_register_duplicate_name_raises(self):
        """Registering two detectors with the same name raises ValueError."""
        @self.registry.register_detector(name="dup", domain="general")
        class Det1(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        with self.assertRaises(ValueError):
            @self.registry.register_detector(name="dup", domain="general")
            class Det2(self.registry.PatternDetector):
                def detect(self, entries, strategy=None):
                    return []

    def test_get_all_detectors(self):
        """get_all_detectors returns all registered detectors."""
        @self.registry.register_detector(name="d1", domain="general")
        class D1(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        @self.registry.register_detector(name="d2", domain="trading")
        class D2(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        all_detectors = self.registry.get_all_detectors()
        self.assertEqual(len(all_detectors), 2)

    def test_get_detectors_by_domain(self):
        """get_detectors filters by domain tag."""
        @self.registry.register_detector(name="gen1", domain="general")
        class Gen1(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        @self.registry.register_detector(name="trade1", domain="trading")
        class Trade1(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        @self.registry.register_detector(name="trade2", domain="trading")
        class Trade2(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        gen = self.registry.get_detectors(domain="general")
        trade = self.registry.get_detectors(domain="trading")
        self.assertEqual(len(gen), 1)
        self.assertEqual(len(trade), 2)

    def test_get_detectors_all_domain(self):
        """get_detectors with domain=None returns all."""
        @self.registry.register_detector(name="a", domain="general")
        class A(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        @self.registry.register_detector(name="b", domain="trading")
        class B(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        self.assertEqual(len(self.registry.get_detectors(domain=None)), 2)

    def test_detector_returns_patterns(self):
        """Detectors produce pattern dicts via run_all_detectors."""
        @self.registry.register_detector(name="always_finds", domain="general")
        class AlwaysFinds(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return [{"type": "test_pattern", "severity": "info",
                         "message": "Found something", "data": {}}]

        results = self.registry.run_all_detectors(entries=[{"event_type": "test"}])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "test_pattern")

    def test_detector_receives_entries_and_strategy(self):
        """Detectors receive the entries list and strategy dict."""
        received = {}

        @self.registry.register_detector(name="capture", domain="general")
        class Capture(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                received["entries"] = entries
                received["strategy"] = strategy
                return []

        test_entries = [{"event_type": "x"}]
        test_strategy = {"learning": {"auto_adjust_enabled": True}}
        self.registry.run_all_detectors(entries=test_entries, strategy=test_strategy)
        self.assertEqual(received["entries"], test_entries)
        self.assertEqual(received["strategy"], test_strategy)

    def test_run_all_with_domain_filter(self):
        """run_all_detectors respects domain filter."""
        @self.registry.register_detector(name="gen", domain="general")
        class Gen(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return [{"type": "gen_pattern", "severity": "info",
                         "message": "general", "data": {}}]

        @self.registry.register_detector(name="trade", domain="trading")
        class Trade(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return [{"type": "trade_pattern", "severity": "info",
                         "message": "trading", "data": {}}]

        gen_results = self.registry.run_all_detectors(
            entries=[], domain="general")
        self.assertEqual(len(gen_results), 1)
        self.assertEqual(gen_results[0]["type"], "gen_pattern")

    def test_detector_exception_isolated(self):
        """One detector throwing doesn't break others."""
        @self.registry.register_detector(name="good", domain="general")
        class Good(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return [{"type": "good", "severity": "info",
                         "message": "works", "data": {}}]

        @self.registry.register_detector(name="bad", domain="general")
        class Bad(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                raise RuntimeError("boom")

        results = self.registry.run_all_detectors(entries=[])
        # Good detector's result should still be present
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "good")

    def test_detector_min_sample(self):
        """PatternDetector base class provides min_sample default."""
        @self.registry.register_detector(name="sampled", domain="general",
                                          min_sample=10)
        class Sampled(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                if len(entries) < self.min_sample:
                    return []
                return [{"type": "enough_data", "severity": "info",
                         "message": "enough", "data": {}}]

        # Not enough entries
        r1 = self.registry.run_all_detectors(entries=[{} for _ in range(5)])
        self.assertEqual(len(r1), 0)

        # Enough entries
        r2 = self.registry.run_all_detectors(entries=[{} for _ in range(10)])
        self.assertEqual(len(r2), 1)

    def test_list_detectors(self):
        """list_detectors returns metadata about all registered detectors."""
        @self.registry.register_detector(
            name="d1", domain="general", description="Desc 1")
        class D1(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        info = self.registry.list_detectors()
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["name"], "d1")
        self.assertEqual(info[0]["domain"], "general")
        self.assertEqual(info[0]["description"], "Desc 1")

    def test_multi_domain_detector(self):
        """Detector with domains=['general', 'trading'] appears in both."""
        @self.registry.register_detector(
            name="multi", domain=["general", "trading"])
        class Multi(self.registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        gen = self.registry.get_detectors(domain="general")
        trade = self.registry.get_detectors(domain="trading")
        self.assertEqual(len(gen), 1)
        self.assertEqual(len(trade), 1)
        self.assertIs(gen[0], trade[0])


class TestPatternDetectorBase(unittest.TestCase):
    """Test the PatternDetector base class."""

    def test_base_class_not_instantiable_without_detect(self):
        """PatternDetector subclass must implement detect()."""
        import pattern_registry

        class Incomplete(pattern_registry.PatternDetector):
            pass

        with self.assertRaises(TypeError):
            Incomplete(name="inc", domain="general")

    def test_base_class_attributes(self):
        """PatternDetector stores name, domain, min_sample."""
        import pattern_registry

        class Complete(pattern_registry.PatternDetector):
            def detect(self, entries, strategy=None):
                return []

        d = Complete(name="test", domain="general", min_sample=5)
        self.assertEqual(d.name, "test")
        self.assertEqual(d.domain, ["general"])
        self.assertEqual(d.min_sample, 5)


if __name__ == "__main__":
    unittest.main()
