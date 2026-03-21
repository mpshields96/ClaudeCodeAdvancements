#!/usr/bin/env python3
"""
pattern_registry.py — MT-28 Phase 2: Pattern Plugin Registry

Central registry for pattern detectors. Each detector is a class that
implements the PatternDetector interface and registers via @register_detector.

This replaces the monolithic detect_patterns() in reflect.py with a
pluggable architecture that supports:
- Domain-tagged detectors (general, trading, nuclear_scan, etc.)
- Detector isolation (one crash doesn't break others)
- Easy extension (add detectors without modifying reflect.py)
- Configurable min_sample per detector

Usage:
    from pattern_registry import register_detector, PatternDetector, run_all_detectors

    @register_detector(name="my_detector", domain="general")
    class MyDetector(PatternDetector):
        def detect(self, entries, strategy=None):
            # Return list of pattern dicts
            return [{"type": "my_pattern", "severity": "info",
                     "message": "Found something", "data": {}}]

    # Run all registered detectors
    patterns = run_all_detectors(entries=journal_entries)
"""

import sys
from abc import ABC, abstractmethod


# Global registry: {name: PatternDetector instance}
_registry = {}


class PatternDetector(ABC):
    """Base class for pattern detectors.

    Subclasses must implement detect(entries, strategy) -> List[dict].
    Each returned dict should have: type, severity, message, data.
    Optionally: suggestion (for auto-apply).
    """

    def __init__(self, name="unnamed", domain="general", description="",
                 min_sample=5):
        self.name = name
        self.domain = domain if isinstance(domain, list) else [domain]
        self.description = description
        self.min_sample = min_sample

    @abstractmethod
    def detect(self, entries, strategy=None):
        """Detect patterns in journal entries.

        Args:
            entries: List of journal entry dicts
            strategy: Optional strategy config dict

        Returns:
            List of pattern dicts, each with:
                type (str): Pattern identifier
                severity (str): "info" or "warning"
                message (str): Human-readable description
                data (dict): Structured data about the pattern
                suggestion (dict, optional): Suggested strategy changes
        """
        pass


def register_detector(name, domain, description="", min_sample=5):
    """Decorator to register a PatternDetector class.

    Args:
        name: Unique identifier for this detector
        domain: Domain tag(s) — str or list of str
        description: Human-readable description
        min_sample: Minimum entries needed before detector activates

    Returns:
        Decorator that registers the class and returns it unchanged.

    Raises:
        ValueError: If a detector with the same name is already registered.
    """
    def decorator(cls):
        if name in _registry:
            raise ValueError(
                f"Detector '{name}' already registered. "
                f"Use a unique name for each detector."
            )
        instance = cls(
            name=name,
            domain=domain,
            description=description,
            min_sample=min_sample,
        )
        _registry[name] = instance
        return cls
    return decorator


def get_all_detectors():
    """Return all registered detector instances."""
    return list(_registry.values())


def get_detectors(domain=None):
    """Return detectors filtered by domain.

    Args:
        domain: Domain string to filter by, or None for all.

    Returns:
        List of PatternDetector instances matching the domain.
    """
    if domain is None:
        return list(_registry.values())
    return [d for d in _registry.values() if domain in d.domain]


def list_detectors():
    """Return metadata about all registered detectors.

    Returns:
        List of dicts with name, domain, description, min_sample.
    """
    return [
        {
            "name": d.name,
            "domain": d.domain[0] if len(d.domain) == 1 else d.domain,
            "description": d.description,
            "min_sample": d.min_sample,
        }
        for d in _registry.values()
    ]


def run_all_detectors(entries, strategy=None, domain=None):
    """Run all registered detectors (optionally filtered by domain).

    Each detector runs in isolation — exceptions are caught and logged
    to stderr, but don't prevent other detectors from running.

    Args:
        entries: List of journal entry dicts
        strategy: Optional strategy config dict
        domain: Optional domain filter

    Returns:
        Combined list of pattern dicts from all detectors.
    """
    detectors = get_detectors(domain=domain)
    all_patterns = []

    for detector in detectors:
        try:
            patterns = detector.detect(entries, strategy=strategy)
            if patterns:
                all_patterns.extend(patterns)
        except Exception as e:
            print(
                f"  [pattern_registry] Detector '{detector.name}' failed: {e}",
                file=sys.stderr,
            )

    return all_patterns
