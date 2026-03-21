#!/usr/bin/env python3
"""
session_id.py — MT-20 Gap 3: Canonical session ID normalization.

Canonical format: "S{number}" string (e.g., "S99", "S100").

All CCA modules should use this format for cross-module correlation.
This module provides normalize(), validate(), and extract_number()
to convert between the 3 formats found across the codebase:
  - Integer: 99
  - Prefixed string: "S99", "s99", "S99a"
  - Bare string: "99"

Usage:
    from session_id import normalize, validate, extract_number

    sid = normalize(99)        # -> "S99"
    sid = normalize("S99a")    # -> "S99"
    sid = normalize("99")      # -> "S99"

    valid = validate("S99")    # -> True
    valid = validate("99")     # -> False

    num = extract_number("S99")  # -> 99
"""

import re


class SessionIdError(ValueError):
    """Raised when a session ID cannot be normalized."""
    pass


_PATTERN = re.compile(r"^[Ss]?([0-9]+)[a-zA-Z]?$")


def normalize(value) -> str:
    """Normalize any session ID format to canonical 'S{number}'.

    Accepts: int (99), str ("S99", "s99", "99", "S99a")
    Returns: "S99"
    Raises: SessionIdError for invalid input
    """
    if value is None:
        raise SessionIdError("Session ID cannot be None")

    if isinstance(value, float):
        value = int(value)

    if isinstance(value, int):
        value = int(value)  # normalize bool subclass to plain int
        if value < 0:
            raise SessionIdError(f"Session number cannot be negative: {value}")
        return f"S{value}"

    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise SessionIdError("Session ID cannot be empty")

        m = _PATTERN.match(value)
        if not m:
            raise SessionIdError(f"Cannot parse session ID: {value!r}")

        return f"S{int(m.group(1))}"

    raise SessionIdError(f"Unsupported session ID type: {type(value).__name__}")


def validate(value) -> bool:
    """Check if a value is in canonical session ID format.

    Returns True only for "S{number}" strings (e.g., "S99").
    Returns False for ints, bare numbers, lowercase, suffixed, etc.
    """
    if not isinstance(value, str):
        return False
    return bool(re.match(r"^S\d+$", value))


def extract_number(value) -> int:
    """Extract the integer session number from any format.

    Accepts: int (99), str ("S99", "s99", "99", "S99a")
    Returns: 99
    Raises: SessionIdError for invalid input
    """
    if value is None:
        raise SessionIdError("Session ID cannot be None")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        value = value.strip()
        m = _PATTERN.match(value)
        if not m:
            raise SessionIdError(f"Cannot extract number from: {value!r}")
        return int(m.group(1))

    raise SessionIdError(f"Unsupported session ID type: {type(value).__name__}")
