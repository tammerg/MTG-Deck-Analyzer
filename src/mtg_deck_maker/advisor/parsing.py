"""Shared parsing utilities for LLM response handling."""

from __future__ import annotations

import re

FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def extract_json_from_response(text: str) -> str:
    """Extract JSON content from a fenced code block, or return the text as-is.

    Args:
        text: Raw LLM response text, possibly containing a fenced code block.

    Returns:
        The content inside the first fenced block (stripped), or the original
        text stripped of leading/trailing whitespace if no fence is found.
    """
    match = FENCED_JSON_RE.search(text)
    return match.group(1).strip() if match else text.strip()
