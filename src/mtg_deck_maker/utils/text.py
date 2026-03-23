"""Shared text-processing utilities for oracle text parsing."""

from __future__ import annotations

import re

__all__ = ["REMINDER_TEXT_RE"]

# Matches parenthesised reminder text in MTG oracle text, e.g.
# "(This creature can only be blocked by creatures with flying.)"
REMINDER_TEXT_RE = re.compile(r"\([^)]*\)")
