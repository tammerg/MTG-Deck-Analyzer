"""Tests for CSV import functionality."""

from __future__ import annotations

import os
import tempfile

import pytest

from mtg_deck_maker.io.csv_import import (
    ImportedCard,
    ImportResult,
    fuzzy_match_card_name,
    import_deck_from_csv,
    import_deck_from_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_temp_file(content: str, encoding: str = "utf-8") -> str:
    """Write content to a temporary file and return its path."""
    fd, filepath = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding=encoding) as f:
        f.write(content)
    return filepath


# ---------------------------------------------------------------------------
# Tests: Standard CSV Format
# ---------------------------------------------------------------------------


class TestStandardFormat:
    """Test importing our standard CSV export format."""

    def test_basic_standard_import(self):
        content = (
            "Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes\n"
            '1,"Atraxa, Praetors\' Voice",Commander,"{G}{W}{U}{B}",4,'
            "Legendary Creature,12.50,Phyrexia All Will Be One,ONE,Commander\n"
            "1,Sol Ring,Ramp,{1},1,Artifact,3.00,Commander 2021,C21,\n"
            "1,Command Tower,Land,,0,Land,0.25,Commander 2021,C21,\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "standard"
            assert len(result.cards) == 3
            assert result.errors == []

            names = [c.name for c in result.cards]
            assert "Atraxa, Praetors' Voice" in names
            assert "Sol Ring" in names
            assert "Command Tower" in names
        finally:
            os.unlink(filepath)

    def test_standard_import_quantities(self):
        content = (
            "Quantity,Card Name,Category\n"
            "2,Island,Land\n"
            "1,Sol Ring,Ramp\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            qty_map = {c.name: c.quantity for c in result.cards}
            assert qty_map["Island"] == 2
            assert qty_map["Sol Ring"] == 1
        finally:
            os.unlink(filepath)

    def test_standard_import_categories(self):
        content = (
            "Quantity,Card Name,Category\n"
            "1,Sol Ring,Ramp\n"
            "1,Swords to Plowshares,Removal\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            cat_map = {c.name: c.category for c in result.cards}
            assert cat_map["Sol Ring"] == "Ramp"
            assert cat_map["Swords to Plowshares"] == "Removal"
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Moxfield Format
# ---------------------------------------------------------------------------


class TestMoxfieldFormat:
    """Test importing Moxfield export format."""

    def test_basic_moxfield(self):
        content = "1 Sol Ring (C21) 263\n1 Command Tower (C21) 284\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "moxfield"
            assert len(result.cards) == 2

            names = [c.name for c in result.cards]
            assert "Sol Ring" in names
            assert "Command Tower" in names
        finally:
            os.unlink(filepath)

    def test_moxfield_set_code_parsed(self):
        content = "1 Sol Ring (C21) 263\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.cards[0].set_code == "C21"
        finally:
            os.unlink(filepath)

    def test_moxfield_quantity(self):
        content = "3 Island (UST) 213\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.cards[0].quantity == 3
        finally:
            os.unlink(filepath)

    def test_moxfield_with_sections(self):
        content = (
            "Commander\n"
            "1 Atraxa, Praetors' Voice (ONE) 1\n"
            "\n"
            "Deck\n"
            "1 Sol Ring (C21) 263\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            # Commander section card should be detected
            commander_cards = [c for c in result.cards if c.is_commander]
            assert len(commander_cards) == 1
            assert "Atraxa" in commander_cards[0].name
        finally:
            os.unlink(filepath)

    def test_moxfield_card_with_comma_in_name(self):
        content = "1 Atraxa, Praetors' Voice (ONE) 1\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 1
            assert result.cards[0].name == "Atraxa, Praetors' Voice"
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Archidekt Format
# ---------------------------------------------------------------------------


class TestArchidektFormat:
    """Test importing Archidekt export format."""

    def test_archidekt_with_x(self):
        content = "1x Sol Ring [C21]\n1x Command Tower [C21]\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "archidekt"
            assert len(result.cards) == 2

            names = [c.name for c in result.cards]
            assert "Sol Ring" in names
            assert "Command Tower" in names
        finally:
            os.unlink(filepath)

    def test_archidekt_set_code(self):
        content = "1x Sol Ring [C21]\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.cards[0].set_code == "C21"
        finally:
            os.unlink(filepath)

    def test_archidekt_without_set_code(self):
        content = "1x Sol Ring\n1x Command Tower\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 2
            assert result.cards[0].set_code == ""
        finally:
            os.unlink(filepath)

    def test_archidekt_plain_number(self):
        content = "1 Sol Ring [C21]\n1 Command Tower [C21]\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "archidekt"
            assert len(result.cards) == 2
        finally:
            os.unlink(filepath)

    def test_archidekt_quantity(self):
        content = "3x Island [UST]\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.cards[0].quantity == 3
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Simple Text Format
# ---------------------------------------------------------------------------


class TestSimpleTextFormat:
    """Test importing simple text format (one card per line)."""

    def test_basic_simple_import(self):
        content = "Sol Ring\nCommand Tower\nSwords to Plowshares\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "simple"
            assert len(result.cards) == 3
        finally:
            os.unlink(filepath)

    def test_simple_all_quantity_one(self):
        content = "Sol Ring\nCommand Tower\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            for card in result.cards:
                assert card.quantity == 1
        finally:
            os.unlink(filepath)

    def test_simple_card_names(self):
        content = "Sol Ring\nCommand Tower\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            names = [c.name for c in result.cards]
            assert names == ["Sol Ring", "Command Tower"]
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Auto-Format Detection
# ---------------------------------------------------------------------------


class TestFormatDetection:
    """Test automatic format detection."""

    def test_detect_standard(self):
        content = (
            "Quantity,Card Name,Category\n"
            "1,Sol Ring,Ramp\n"
        )
        result = import_deck_from_string(content)
        assert result.format_detected == "standard"

    def test_detect_moxfield(self):
        content = "1 Sol Ring (C21) 263\n1 Command Tower (C21) 284\n"
        result = import_deck_from_string(content)
        assert result.format_detected == "moxfield"

    def test_detect_archidekt_x(self):
        content = "1x Sol Ring [C21]\n1x Command Tower [C21]\n"
        result = import_deck_from_string(content)
        assert result.format_detected == "archidekt"

    def test_detect_archidekt_plain(self):
        content = "1 Sol Ring [C21]\n1 Command Tower [C21]\n"
        result = import_deck_from_string(content)
        assert result.format_detected == "archidekt"

    def test_detect_simple(self):
        content = "Sol Ring\nCommand Tower\n"
        result = import_deck_from_string(content)
        assert result.format_detected == "simple"


# ---------------------------------------------------------------------------
# Tests: Blank Lines, Comments, BOM
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test handling of blank lines, comments, and BOM markers."""

    def test_blank_lines_skipped(self):
        content = "Sol Ring\n\n\nCommand Tower\n\n"
        result = import_deck_from_string(content)
        assert len(result.cards) == 2

    def test_comment_lines_skipped(self):
        content = "# This is a comment\nSol Ring\n# Another comment\nCommand Tower\n"
        result = import_deck_from_string(content)
        assert len(result.cards) == 2
        names = [c.name for c in result.cards]
        assert "Sol Ring" in names
        assert "Command Tower" in names

    def test_bom_marker_handled(self):
        content = "\ufeffQuantity,Card Name,Category\n1,Sol Ring,Ramp\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert result.format_detected == "standard"
            assert len(result.cards) == 1
            assert result.cards[0].name == "Sol Ring"
        finally:
            os.unlink(filepath)

    def test_empty_file(self):
        content = ""
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 0
            assert len(result.warnings) > 0
        finally:
            os.unlink(filepath)

    def test_only_comments(self):
        content = "# comment 1\n# comment 2\n"
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 0
            assert len(result.warnings) > 0
        finally:
            os.unlink(filepath)

    def test_file_not_found(self):
        result = import_deck_from_csv("/nonexistent/path/deck.csv")
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower() or "error" in result.errors[0].lower()


# ---------------------------------------------------------------------------
# Tests: Fuzzy Matching
# ---------------------------------------------------------------------------


class TestFuzzyMatching:
    """Test fuzzy card name matching."""

    def test_exact_match(self):
        known = ["Sol Ring", "Command Tower", "Swords to Plowshares"]
        result = fuzzy_match_card_name("Sol Ring", known)
        assert result == "Sol Ring"

    def test_close_misspelling(self):
        known = ["Sol Ring", "Command Tower", "Swords to Plowshares"]
        result = fuzzy_match_card_name("Sol Rign", known)
        assert result == "Sol Ring"

    def test_no_match_below_threshold(self):
        known = ["Sol Ring", "Command Tower"]
        result = fuzzy_match_card_name("Completely Different Card", known, threshold=80)
        assert result is None

    def test_empty_name(self):
        known = ["Sol Ring"]
        result = fuzzy_match_card_name("", known)
        assert result is None

    def test_empty_known_names(self):
        result = fuzzy_match_card_name("Sol Ring", [])
        assert result is None

    def test_case_variation(self):
        known = ["Sol Ring", "Command Tower"]
        result = fuzzy_match_card_name("sol ring", known)
        assert result == "Sol Ring"

    def test_partial_name_match(self):
        known = ["Swords to Plowshares", "Sol Ring"]
        result = fuzzy_match_card_name("Swords to Plowshare", known)
        assert result == "Swords to Plowshares"

    def test_custom_threshold(self):
        known = ["Sol Ring"]
        # Very low threshold should match even poor matches
        result = fuzzy_match_card_name("Sol", known, threshold=40)
        assert result == "Sol Ring"

    def test_high_threshold_rejects_partial(self):
        known = ["Sol Ring"]
        result = fuzzy_match_card_name("Sol", known, threshold=95)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Error Handling for Malformed CSV
# ---------------------------------------------------------------------------


class TestMalformedInput:
    """Test error handling for malformed CSV input."""

    def test_invalid_quantity_warns(self):
        content = (
            "Quantity,Card Name,Category\n"
            "abc,Sol Ring,Ramp\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.warnings) > 0
            assert result.cards[0].quantity == 1  # defaults to 1
        finally:
            os.unlink(filepath)

    def test_missing_card_name_skipped(self):
        content = (
            "Quantity,Card Name,Category\n"
            "1,,Ramp\n"
            "1,Sol Ring,Ramp\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 1
            assert result.cards[0].name == "Sol Ring"
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Summary Section Handling
# ---------------------------------------------------------------------------


class TestSummarySkipping:
    """Test that import correctly skips the summary section."""

    def test_import_skips_summary(self):
        content = (
            "Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes\n"
            '1,"Atraxa, Praetors\' Voice",Commander,"{G}{W}{U}{B}",4,'
            "Legendary Creature,12.50,Phyrexia All Will Be One,ONE,Commander\n"
            "1,Sol Ring,Ramp,{1},1,Artifact,3.00,Commander 2021,C21,\n"
            ",,,,,,,,\n"
            ",DECK SUMMARY,,,,,,,\n"
            ",Total Cards:,2,,,,,,\n"
            ",Total Price:,$15.50,,,,,,\n"
            ",Average CMC:,2.5,,,,,,\n"
            ',Colors:,"W,U,B,G",,,,,,\n'
            ',Commander:,"Atraxa, Praetors\' Voice",,,,,,\n'
            ",Budget Target:,$150.00,,,,,,\n"
            ",Prices As Of:,2026-02-18,,,,,,\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            assert len(result.cards) == 2
            names = [c.name for c in result.cards]
            assert "DECK SUMMARY" not in names
            assert "Total Cards:" not in names
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Commander Detection
# ---------------------------------------------------------------------------


class TestCommanderDetection:
    """Test detection of commander cards from various indicators."""

    def test_commander_from_category(self):
        content = (
            "Quantity,Card Name,Category\n"
            '1,"Atraxa, Praetors\' Voice",Commander\n'
            "1,Sol Ring,Ramp\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            commanders = [c for c in result.cards if c.is_commander]
            assert len(commanders) == 1
            assert "Atraxa" in commanders[0].name
        finally:
            os.unlink(filepath)

    def test_commander_from_notes(self):
        content = (
            "Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes\n"
            '1,"Atraxa, Praetors\' Voice",Special,"{G}{W}{U}{B}",4,'
            "Legendary Creature,12.50,ONE,ONE,Commander\n"
            "1,Sol Ring,Ramp,{1},1,Artifact,3.00,C21,C21,\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            commanders = [c for c in result.cards if c.is_commander]
            assert len(commanders) == 1
            assert "Atraxa" in commanders[0].name
        finally:
            os.unlink(filepath)

    def test_commander_from_moxfield_section(self):
        content = (
            "Commander\n"
            "1 Atraxa, Praetors' Voice (ONE) 1\n"
            "\n"
            "Deck\n"
            "1 Sol Ring (C21) 263\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            commanders = [c for c in result.cards if c.is_commander]
            assert len(commanders) == 1
        finally:
            os.unlink(filepath)

    def test_non_commander_not_flagged(self):
        content = (
            "Quantity,Card Name,Category\n"
            "1,Sol Ring,Ramp\n"
            "1,Command Tower,Land\n"
        )
        filepath = _write_temp_file(content)
        try:
            result = import_deck_from_csv(filepath)
            commanders = [c for c in result.cards if c.is_commander]
            assert len(commanders) == 0
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: import_deck_from_string
# ---------------------------------------------------------------------------


class TestImportFromString:
    """Test the string-based import convenience function."""

    def test_import_string_standard(self):
        content = (
            "Quantity,Card Name,Category\n"
            "1,Sol Ring,Ramp\n"
        )
        result = import_deck_from_string(content)
        assert result.format_detected == "standard"
        assert len(result.cards) == 1

    def test_import_string_moxfield(self):
        content = "1 Sol Ring (C21) 263\n"
        result = import_deck_from_string(content)
        assert result.format_detected == "moxfield"
        assert len(result.cards) == 1

    def test_import_string_empty(self):
        result = import_deck_from_string("")
        assert len(result.cards) == 0
        assert len(result.warnings) > 0
