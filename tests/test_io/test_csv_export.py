"""Tests for CSV export functionality."""

from __future__ import annotations

import csv
import io
import os
import tempfile

import pytest

from mtg_deck_maker.io.csv_export import export_deck_to_csv, CSV_COLUMNS
from mtg_deck_maker.io.csv_import import import_deck_from_csv
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck, DeckCard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(
    card_id: int,
    oracle_id: str,
    name: str,
    type_line: str = "Creature",
    mana_cost: str = "{1}",
    cmc: float = 1.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
) -> Card:
    return Card(
        id=card_id,
        oracle_id=oracle_id,
        name=name,
        type_line=type_line,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=color_identity or [],
        legal_commander=True,
    )


def _make_deck_card(
    card_id: int,
    name: str,
    category: str = "",
    cmc: float = 0.0,
    price: float = 0.0,
    is_commander: bool = False,
    is_companion: bool = False,
    quantity: int = 1,
    colors: list[str] | None = None,
) -> DeckCard:
    return DeckCard(
        card_id=card_id,
        quantity=quantity,
        category=category,
        is_commander=is_commander,
        is_companion=is_companion,
        card_name=name,
        cmc=cmc,
        colors=colors or [],
        price=price,
    )


def _parse_csv_string(csv_str: str) -> list[list[str]]:
    """Parse a CSV string into a list of rows."""
    reader = csv.reader(io.StringIO(csv_str))
    return list(reader)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_deck() -> Deck:
    """A minimal deck with a commander and two cards for basic export tests."""
    return Deck(
        name="Test Deck",
        cards=[
            _make_deck_card(
                card_id=1,
                name="Atraxa, Praetors' Voice",
                category="Commander",
                cmc=4.0,
                price=12.50,
                is_commander=True,
                colors=["W", "U", "B", "G"],
            ),
            _make_deck_card(
                card_id=2,
                name="Sol Ring",
                category="Ramp",
                cmc=1.0,
                price=3.00,
            ),
            _make_deck_card(
                card_id=3,
                name="Command Tower",
                category="Land",
                cmc=0.0,
                price=0.25,
            ),
        ],
        format="commander",
        budget_target=150.00,
    )


@pytest.fixture
def cards_dict() -> dict[int, Card]:
    """Card objects keyed by id for enriched export."""
    return {
        1: _make_card(
            card_id=1,
            oracle_id="atraxa-oracle",
            name="Atraxa, Praetors' Voice",
            type_line="Legendary Creature - Phyrexian Angel Horror",
            mana_cost="{G}{W}{U}{B}",
            cmc=4.0,
            colors=["W", "U", "B", "G"],
            color_identity=["W", "U", "B", "G"],
        ),
        2: _make_card(
            card_id=2,
            oracle_id="sol-ring-oracle",
            name="Sol Ring",
            type_line="Artifact",
            mana_cost="{1}",
            cmc=1.0,
        ),
        3: _make_card(
            card_id=3,
            oracle_id="command-tower-oracle",
            name="Command Tower",
            type_line="Land",
            mana_cost="",
            cmc=0.0,
        ),
    }


@pytest.fixture
def prices_dict() -> dict[int, float]:
    """Prices keyed by card id."""
    return {1: 12.50, 2: 3.00, 3: 0.25}


# ---------------------------------------------------------------------------
# Tests: Basic Export
# ---------------------------------------------------------------------------


class TestBasicExport:
    """Test basic CSV export with all columns populated."""

    def test_export_returns_string_when_no_filepath(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_header_row(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        rows = _parse_csv_string(result)
        assert rows[0] == CSV_COLUMNS

    def test_export_all_columns_populated(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        rows = _parse_csv_string(result)

        # Find the Sol Ring row (should be in Ramp category)
        sol_ring_row = None
        for row in rows[1:]:
            if len(row) >= 2 and row[1] == "Sol Ring":
                sol_ring_row = row
                break

        assert sol_ring_row is not None
        assert sol_ring_row[0] == "1"        # Quantity
        assert sol_ring_row[1] == "Sol Ring"  # Card Name
        assert sol_ring_row[2] == "Ramp"      # Category
        assert sol_ring_row[3] == "{1}"       # Mana Cost
        assert sol_ring_row[4] == "1"         # CMC
        assert sol_ring_row[5] == "Artifact"  # Type
        assert sol_ring_row[6] == "3.00"      # Price (USD)

    def test_export_commander_has_notes(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        rows = _parse_csv_string(result)

        atraxa_row = None
        for row in rows[1:]:
            if len(row) >= 2 and "Atraxa" in row[1]:
                atraxa_row = row
                break

        assert atraxa_row is not None
        assert atraxa_row[9] == "Commander"  # Notes column


# ---------------------------------------------------------------------------
# Tests: Missing Prices
# ---------------------------------------------------------------------------


class TestMissingPrices:
    """Test export when prices are missing."""

    def test_missing_price_shows_na(self, simple_deck, cards_dict):
        # No prices dict at all
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=None)
        rows = _parse_csv_string(result)

        # Command Tower has price 0.25 on the DeckCard, so it shows
        # Sol Ring has price 3.00 on the DeckCard
        # Atraxa has price 12.50 on the DeckCard
        # All should show their DeckCard price since no external prices dict
        for row in rows[1:]:
            if len(row) >= 7 and row[1] == "Sol Ring":
                assert row[6] == "3.00"

    def test_no_price_anywhere_shows_na(self):
        deck = Deck(
            name="No Prices",
            cards=[
                _make_deck_card(card_id=10, name="Mystery Card", category="Utility"),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)

        mystery_row = None
        for row in rows[1:]:
            if len(row) >= 2 and row[1] == "Mystery Card":
                mystery_row = row
                break

        assert mystery_row is not None
        assert mystery_row[6] == "N/A"

    def test_partial_prices_shows_mix(self, simple_deck, cards_dict):
        partial_prices = {2: 3.50}  # Only Sol Ring has a price
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=partial_prices)
        rows = _parse_csv_string(result)

        for row in rows[1:]:
            if len(row) >= 7 and row[1] == "Sol Ring":
                assert row[6] == "3.50"
            elif len(row) >= 7 and row[1] == "Command Tower":
                # Falls back to DeckCard.price = 0.25
                assert row[6] == "0.25"


# ---------------------------------------------------------------------------
# Tests: Summary Section
# ---------------------------------------------------------------------------


class TestSummarySection:
    """Test the summary section appended after card list."""

    def test_summary_contains_deck_summary_header(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "DECK SUMMARY" in result

    def test_summary_total_cards(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Total Cards:" in result
        assert ",3," in result  # 3 cards total

    def test_summary_total_price(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Total Price:" in result
        assert "$15.75" in result  # 12.50 + 3.00 + 0.25

    def test_summary_average_cmc(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Average CMC:" in result

    def test_summary_commander_name(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Atraxa, Praetors' Voice" in result

    def test_summary_budget_target(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Budget Target:" in result
        assert "$150.00" in result

    def test_summary_no_budget(self, cards_dict, prices_dict):
        deck = Deck(
            name="No Budget",
            cards=[
                _make_deck_card(card_id=2, name="Sol Ring", category="Ramp", cmc=1.0, price=3.00),
            ],
            budget_target=None,
        )
        result = export_deck_to_csv(deck, cards=cards_dict, prices=prices_dict)
        assert "None" in result

    def test_summary_prices_as_of(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert "Prices As Of:" in result


# ---------------------------------------------------------------------------
# Tests: Card Sorting
# ---------------------------------------------------------------------------


class TestCardSorting:
    """Test cards are sorted by category, then by name."""

    def test_sorted_by_category(self):
        deck = Deck(
            name="Sorting Test",
            cards=[
                _make_deck_card(card_id=1, name="Zenith", category="Utility", cmc=3.0, price=1.0),
                _make_deck_card(card_id=2, name="Alpha", category="Land", cmc=0.0, price=0.5),
                _make_deck_card(card_id=3, name="Beta", category="Ramp", cmc=2.0, price=2.0),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)

        # Filter card data rows (skip header and summary)
        card_rows = [
            r for r in rows[1:]
            if len(r) >= 3 and r[1] and r[1] not in ("DECK SUMMARY", "")
            and "Total Cards:" not in r[1]
            and "Total Price:" not in r[1]
            and "Average CMC:" not in r[1]
            and "Colors:" not in r[1]
            and "Commander:" not in r[1]
            and "Budget Target:" not in r[1]
            and "Prices As Of:" not in r[1]
        ]

        categories = [r[2] for r in card_rows]
        assert categories == ["Land", "Ramp", "Utility"]

    def test_sorted_by_name_within_category(self):
        deck = Deck(
            name="Name Sorting Test",
            cards=[
                _make_deck_card(card_id=1, name="Zenith Flare", category="Removal", cmc=4.0, price=0.5),
                _make_deck_card(card_id=2, name="Alpha Strike", category="Removal", cmc=3.0, price=1.0),
                _make_deck_card(card_id=3, name="Murder", category="Removal", cmc=3.0, price=0.25),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)

        card_rows = [
            r for r in rows[1:]
            if len(r) >= 2 and r[0].isdigit()
        ]

        names = [r[1] for r in card_rows]
        assert names == ["Alpha Strike", "Murder", "Zenith Flare"]


# ---------------------------------------------------------------------------
# Tests: Special Characters
# ---------------------------------------------------------------------------


class TestSpecialCharacters:
    """Test that special characters in card names are properly escaped."""

    def test_comma_in_card_name(self):
        deck = Deck(
            name="Special Chars",
            cards=[
                _make_deck_card(
                    card_id=1,
                    name="Atraxa, Praetors' Voice",
                    category="Commander",
                    cmc=4.0,
                    price=12.50,
                    is_commander=True,
                ),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)

        # The CSV reader should correctly parse the quoted name
        card_row = rows[1]
        assert card_row[1] == "Atraxa, Praetors' Voice"

    def test_apostrophe_in_card_name(self):
        deck = Deck(
            name="Apostrophe Test",
            cards=[
                _make_deck_card(card_id=1, name="Thassa's Oracle", category="Win Condition", cmc=2.0, price=5.0),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)
        card_row = rows[1]
        assert card_row[1] == "Thassa's Oracle"

    def test_double_quote_in_card_name(self):
        deck = Deck(
            name="Quote Test",
            cards=[
                _make_deck_card(card_id=1, name='Who / What / When / Where / Why', category="Utility", cmc=5.0, price=0.50),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)
        card_row = rows[1]
        assert card_row[1] == "Who / What / When / Where / Why"

    def test_actual_quotes_in_name(self):
        deck = Deck(
            name="Real Quote Test",
            cards=[
                _make_deck_card(
                    card_id=1,
                    name='"Ach! Hans, Run!"',
                    category="Utility",
                    cmc=6.0,
                    price=1.00,
                ),
            ],
        )
        result = export_deck_to_csv(deck)
        rows = _parse_csv_string(result)
        card_row = rows[1]
        assert card_row[1] == '"Ach! Hans, Run!"'


# ---------------------------------------------------------------------------
# Tests: Round-trip (Export then Import)
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Test that exporting then importing produces the same card list."""

    def test_roundtrip_preserves_card_names(self, simple_deck, cards_dict, prices_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            result = import_deck_from_csv(filepath)

            exported_names = sorted(
                cards_dict[dc.card_id].name for dc in simple_deck.cards
            )
            imported_names = sorted(card.name for card in result.cards)
            assert exported_names == imported_names
        finally:
            os.unlink(filepath)

    def test_roundtrip_preserves_quantities(self, simple_deck, cards_dict, prices_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            result = import_deck_from_csv(filepath)

            for imported_card in result.cards:
                assert imported_card.quantity == 1
        finally:
            os.unlink(filepath)

    def test_roundtrip_preserves_categories(self, simple_deck, cards_dict, prices_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            result = import_deck_from_csv(filepath)

            categories = {card.name: card.category for card in result.cards}
            assert categories["Sol Ring"] == "Ramp"
            assert categories["Command Tower"] == "Land"
        finally:
            os.unlink(filepath)

    def test_roundtrip_detects_commander(self, simple_deck, cards_dict, prices_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            result = import_deck_from_csv(filepath)

            commander_cards = [c for c in result.cards if c.is_commander]
            assert len(commander_cards) == 1
            assert commander_cards[0].name == "Atraxa, Praetors' Voice"
        finally:
            os.unlink(filepath)


# ---------------------------------------------------------------------------
# Tests: Export to String vs File
# ---------------------------------------------------------------------------


class TestExportTarget:
    """Test exporting to string vs file produces equivalent output."""

    def test_export_to_file_returns_none(self, simple_deck, cards_dict, prices_dict):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            result = export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            assert result is None
        finally:
            os.unlink(filepath)

    def test_export_to_string_returns_content(self, simple_deck, cards_dict, prices_dict):
        result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)
        assert result is not None
        assert isinstance(result, str)

    def test_file_and_string_match(self, simple_deck, cards_dict, prices_dict):
        string_result = export_deck_to_csv(simple_deck, cards=cards_dict, prices=prices_dict)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            filepath = f.name

        try:
            export_deck_to_csv(simple_deck, filepath=filepath, cards=cards_dict, prices=prices_dict)
            with open(filepath, "r", newline="", encoding="utf-8") as f:
                file_result = f.read()

            assert string_result == file_result
        finally:
            os.unlink(filepath)
