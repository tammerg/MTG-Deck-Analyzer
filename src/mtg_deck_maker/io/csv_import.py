"""CSV import for Commander decklists.

Supports auto-detection of multiple CSV/text formats:
- Standard (our export format): Quantity,Card Name,...
- Moxfield: "1 Sol Ring (C21) 199"
- Archidekt: "1x Sol Ring [C21]" or "1 Sol Ring"
- Simple text: one card name per line (quantity=1)

Uses only the Python stdlib csv module for parsing standard CSV.
Uses thefuzz for fuzzy card name matching.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class ImportedCard:
    """A single card parsed from an imported file."""

    quantity: int
    name: str
    category: str = ""
    set_code: str = ""
    is_commander: bool = False


@dataclass(slots=True)
class ImportResult:
    """Result of importing a deck from CSV/text."""

    cards: list[ImportedCard] = field(default_factory=list)
    format_detected: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Regex patterns for format detection
_MOXFIELD_PATTERN = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+\(([A-Za-z0-9]+)\)\s+(\S+)\s*$"
)

_ARCHIDEKT_X_PATTERN = re.compile(
    r"^\s*(\d+)\s*x\s+(.+?)(?:\s+\[([A-Za-z0-9]+)\])?\s*$",
    re.IGNORECASE,
)

_ARCHIDEKT_PLAIN_PATTERN = re.compile(
    r"^\s*(\d+)\s+(.+?)(?:\s+\[([A-Za-z0-9]+)\])?\s*$"
)

# Summary section markers to skip during import
_SUMMARY_MARKERS = frozenset({
    "DECK SUMMARY",
    "Total Cards:",
    "Total Price:",
    "Average CMC:",
    "Colors:",
    "Commander:",
    "Budget Target:",
    "Prices As Of:",
})


def _strip_bom(text: str) -> str:
    """Remove UTF-8 BOM marker if present."""
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _is_comment_or_blank(line: str) -> bool:
    """Check if a line is blank or a comment."""
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _is_summary_line(line: str) -> bool:
    """Check if a line belongs to the summary section."""
    stripped = line.strip().strip(",")
    if not stripped:
        return False
    for marker in _SUMMARY_MARKERS:
        if marker in stripped:
            return True
    return False


def _detect_format(lines: list[str]) -> str:
    """Auto-detect the import format from the first non-blank, non-comment lines.

    Args:
        lines: All lines from the file (BOM-stripped, but not filtered).

    Returns:
        One of: "standard", "moxfield", "archidekt", "simple"
    """
    content_lines = [
        ln for ln in lines
        if not _is_comment_or_blank(ln) and not _is_summary_line(ln)
    ]

    if not content_lines:
        return "unknown"

    first_line = content_lines[0].strip()

    # Check for standard CSV header
    first_lower = first_line.lower()
    if "quantity" in first_lower and "card name" in first_lower:
        return "standard"

    # Look at a few content lines (skip first if it looks like a header)
    sample_lines = content_lines[:10]

    moxfield_count = 0
    archidekt_x_count = 0
    archidekt_plain_count = 0
    simple_count = 0

    for ln in sample_lines:
        stripped = ln.strip()
        if _MOXFIELD_PATTERN.match(stripped):
            moxfield_count += 1
        elif _ARCHIDEKT_X_PATTERN.match(stripped):
            archidekt_x_count += 1
        elif _ARCHIDEKT_PLAIN_PATTERN.match(stripped):
            archidekt_plain_count += 1
        else:
            # Could be simple text (just a card name)
            simple_count += 1

    # Prefer more specific formats
    if moxfield_count > 0 and moxfield_count >= archidekt_plain_count:
        return "moxfield"
    if archidekt_x_count > 0:
        return "archidekt"
    if archidekt_plain_count > 0:
        return "archidekt"
    return "simple"


def _parse_standard(lines: list[str], result: ImportResult) -> None:
    """Parse our standard CSV export format.

    Expected columns: Quantity, Card Name, Category, ...
    """
    reader = csv.reader(io.StringIO("\n".join(lines)))
    header = None
    in_summary = False

    for row_num, row in enumerate(reader, start=1):
        if not row or all(cell.strip() == "" for cell in row):
            # Blank row may signal start of summary
            in_summary = True
            continue

        # Check for summary markers
        joined = ",".join(row)
        if _is_summary_line(joined):
            in_summary = True
            continue

        if in_summary:
            continue

        # First non-empty row is the header
        if header is None:
            header = [col.strip().lower() for col in row]
            continue

        # Map columns
        def _col(name: str) -> str:
            try:
                idx = header.index(name)
                return row[idx].strip() if idx < len(row) else ""
            except ValueError:
                return ""

        qty_str = _col("quantity")
        name = _col("card name")
        category = _col("category")
        notes = _col("notes")

        if not name:
            continue

        try:
            quantity = int(qty_str) if qty_str else 1
        except ValueError:
            result.warnings.append(
                f"Row {row_num}: invalid quantity '{qty_str}', defaulting to 1"
            )
            quantity = 1

        is_commander = (
            category.lower() == "commander"
            or notes.lower() == "commander"
        )

        result.cards.append(ImportedCard(
            quantity=quantity,
            name=name,
            category=category,
            is_commander=is_commander,
        ))


def _parse_moxfield(lines: list[str], result: ImportResult) -> None:
    """Parse Moxfield export format: '1 Sol Ring (C21) 199'."""
    current_section = ""

    for line_num, line in enumerate(lines, start=1):
        if _is_comment_or_blank(line):
            continue
        if _is_summary_line(line):
            continue

        stripped = line.strip()

        # Moxfield section headers (e.g., "Commander", "Deck", "Sideboard")
        # These are lines that don't match the card pattern and contain no digits
        match = _MOXFIELD_PATTERN.match(stripped)
        if match:
            quantity = int(match.group(1))
            name = match.group(2).strip()
            set_code = match.group(3)

            is_commander = current_section.lower() == "commander"

            result.cards.append(ImportedCard(
                quantity=quantity,
                name=name,
                category=current_section,
                set_code=set_code,
                is_commander=is_commander,
            ))
        else:
            # Could be a section header like "Commander" or "Deck"
            if stripped and not stripped[0].isdigit():
                current_section = stripped
            else:
                result.warnings.append(
                    f"Line {line_num}: could not parse '{stripped}'"
                )


def _parse_archidekt(lines: list[str], result: ImportResult) -> None:
    """Parse Archidekt export format: '1x Sol Ring [C21]' or '1 Sol Ring'."""
    current_section = ""

    for line_num, line in enumerate(lines, start=1):
        if _is_comment_or_blank(line):
            continue
        if _is_summary_line(line):
            continue

        stripped = line.strip()

        # Try "1x Card Name [SET]" first
        match = _ARCHIDEKT_X_PATTERN.match(stripped)
        if match:
            quantity = int(match.group(1))
            name = match.group(2).strip()
            set_code = match.group(3) or ""

            is_commander = current_section.lower() == "commander"

            result.cards.append(ImportedCard(
                quantity=quantity,
                name=name,
                category=current_section,
                set_code=set_code,
                is_commander=is_commander,
            ))
            continue

        # Try "1 Card Name [SET]" (no 'x')
        match = _ARCHIDEKT_PLAIN_PATTERN.match(stripped)
        if match:
            quantity = int(match.group(1))
            name = match.group(2).strip()
            set_code = match.group(3) or ""

            is_commander = current_section.lower() == "commander"

            result.cards.append(ImportedCard(
                quantity=quantity,
                name=name,
                category=current_section,
                set_code=set_code,
                is_commander=is_commander,
            ))
            continue

        # Could be a section header
        if stripped and not stripped[0].isdigit():
            current_section = stripped
        else:
            result.warnings.append(
                f"Line {line_num}: could not parse '{stripped}'"
            )


def _parse_simple(lines: list[str], result: ImportResult) -> None:
    """Parse simple text format: one card name per line, quantity=1."""
    for line_num, line in enumerate(lines, start=1):
        if _is_comment_or_blank(line):
            continue
        if _is_summary_line(line):
            continue

        name = line.strip()
        if name:
            result.cards.append(ImportedCard(
                quantity=1,
                name=name,
            ))


def import_deck_from_csv(filepath: str) -> ImportResult:
    """Import a deck from a CSV or text file.

    Automatically detects the format and parses accordingly. Handles:
    - UTF-8 BOM markers
    - Blank lines and comment lines (starting with #)
    - Summary sections (skipped during import)
    - Different line endings (handled by Python's universal newline mode)

    Args:
        filepath: Path to the CSV/text file to import.

    Returns:
        ImportResult with parsed cards, detected format, warnings, and errors.
    """
    result = ImportResult()

    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            raw_content = f.read()
    except FileNotFoundError:
        result.errors.append(f"File not found: {filepath}")
        return result
    except OSError as exc:
        result.errors.append(f"Error reading file: {exc}")
        return result

    raw_content = _strip_bom(raw_content)
    lines = raw_content.splitlines()

    if not lines or all(_is_comment_or_blank(ln) for ln in lines):
        result.warnings.append("File is empty or contains only comments.")
        result.format_detected = "unknown"
        return result

    detected_format = _detect_format(lines)
    result.format_detected = detected_format

    parsers = {
        "standard": _parse_standard,
        "moxfield": _parse_moxfield,
        "archidekt": _parse_archidekt,
        "simple": _parse_simple,
    }

    parser = parsers.get(detected_format, _parse_simple)
    parser(lines, result)

    if not result.cards:
        result.warnings.append("No cards found in the file.")

    return result


def import_deck_from_string(content: str) -> ImportResult:
    """Import a deck from a CSV/text string.

    Convenience wrapper around import_deck_from_csv that accepts a string
    instead of a file path. Same auto-detection and parsing logic.

    Args:
        content: The CSV/text content as a string.

    Returns:
        ImportResult with parsed cards, detected format, warnings, and errors.
    """
    result = ImportResult()

    content = _strip_bom(content)
    lines = content.splitlines()

    if not lines or all(_is_comment_or_blank(ln) for ln in lines):
        result.warnings.append("Content is empty or contains only comments.")
        result.format_detected = "unknown"
        return result

    detected_format = _detect_format(lines)
    result.format_detected = detected_format

    parsers = {
        "standard": _parse_standard,
        "moxfield": _parse_moxfield,
        "archidekt": _parse_archidekt,
        "simple": _parse_simple,
    }

    parser = parsers.get(detected_format, _parse_simple)
    parser(lines, result)

    if not result.cards:
        result.warnings.append("No cards found in the content.")

    return result


def fuzzy_match_card_name(
    name: str,
    known_names: list[str],
    threshold: int = 80,
) -> str | None:
    """Find the best fuzzy match for a card name from a list of known names.

    Uses thefuzz library for string similarity matching.

    Args:
        name: The card name to match (potentially misspelled).
        known_names: List of known correct card names.
        threshold: Minimum score (0-100) to accept a match. Default 80.

    Returns:
        The best matching card name if score >= threshold, otherwise None.
    """
    if not name or not known_names:
        return None

    from thefuzz import fuzz, process

    result = process.extractOne(name, known_names, scorer=fuzz.ratio)
    if result is None:
        return None

    best_match, score = result[0], result[1]
    if score >= threshold:
        return best_match
    return None
