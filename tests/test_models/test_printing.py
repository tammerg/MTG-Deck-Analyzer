"""Tests for the Printing data model."""

from __future__ import annotations

from mtg_deck_maker.models.printing import Printing


class TestPrintingCreation:
    """Test Printing dataclass creation and field access."""

    def test_create_printing_with_all_fields(self) -> None:
        printing = Printing(
            scryfall_id="abc-123",
            card_id=1,
            set_code="C21",
            collector_number="263",
            lang="en",
            rarity="uncommon",
            finishes=["nonfoil", "foil"],
            tcgplayer_id=12345,
            cardmarket_id=67890,
            released_at="2021-04-16",
            is_promo=False,
            is_reprint=True,
        )
        assert printing.scryfall_id == "abc-123"
        assert printing.card_id == 1
        assert printing.set_code == "C21"
        assert printing.collector_number == "263"
        assert printing.lang == "en"
        assert printing.rarity == "uncommon"
        assert printing.finishes == ["nonfoil", "foil"]
        assert printing.tcgplayer_id == 12345
        assert printing.cardmarket_id == 67890
        assert printing.released_at == "2021-04-16"
        assert printing.is_promo is False
        assert printing.is_reprint is True
        assert printing.id is None

    def test_create_printing_with_defaults(self) -> None:
        printing = Printing(
            scryfall_id="def-456",
            card_id=2,
            set_code="ONE",
            collector_number="1",
        )
        assert printing.lang == "en"
        assert printing.rarity == ""
        assert printing.finishes == []
        assert printing.tcgplayer_id is None
        assert printing.cardmarket_id is None
        assert printing.released_at == ""
        assert printing.is_promo is False
        assert printing.is_reprint is False


class TestPrintingProperties:
    """Test Printing computed properties."""

    def test_finishes_str_single(self) -> None:
        printing = Printing(
            scryfall_id="a",
            card_id=1,
            set_code="X",
            collector_number="1",
            finishes=["nonfoil"],
        )
        assert printing.finishes_str == "nonfoil"

    def test_finishes_str_multiple(self) -> None:
        printing = Printing(
            scryfall_id="b",
            card_id=1,
            set_code="X",
            collector_number="2",
            finishes=["nonfoil", "foil", "etched"],
        )
        assert printing.finishes_str == "nonfoil,foil,etched"

    def test_finishes_str_empty(self) -> None:
        printing = Printing(
            scryfall_id="c",
            card_id=1,
            set_code="X",
            collector_number="3",
        )
        assert printing.finishes_str == ""


class TestPrintingSerialization:
    """Test Printing to/from database row conversion."""

    def test_to_db_row(self) -> None:
        printing = Printing(
            scryfall_id="abc-123",
            card_id=1,
            set_code="C21",
            collector_number="263",
            rarity="uncommon",
            finishes=["nonfoil", "foil"],
            tcgplayer_id=12345,
            is_reprint=True,
        )
        row = printing.to_db_row()
        assert row["scryfall_id"] == "abc-123"
        assert row["card_id"] == 1
        assert row["set_code"] == "C21"
        assert row["finishes"] == "nonfoil,foil"
        assert row["is_promo"] == 0
        assert row["is_reprint"] == 1

    def test_from_db_row(self) -> None:
        row = {
            "id": 10,
            "scryfall_id": "xyz-789",
            "card_id": 5,
            "set_code": "ONE",
            "collector_number": "42",
            "lang": "en",
            "rarity": "rare",
            "finishes": "nonfoil,foil",
            "tcgplayer_id": 99999,
            "cardmarket_id": 88888,
            "released_at": "2023-02-03",
            "is_promo": 0,
            "is_reprint": 1,
        }
        printing = Printing.from_db_row(row)
        assert printing.id == 10
        assert printing.scryfall_id == "xyz-789"
        assert printing.card_id == 5
        assert printing.finishes == ["nonfoil", "foil"]
        assert printing.is_promo is False
        assert printing.is_reprint is True

    def test_from_db_row_empty_finishes(self) -> None:
        row = {
            "id": 1,
            "scryfall_id": "empty-test",
            "card_id": 1,
            "set_code": "TST",
            "collector_number": "1",
            "lang": "en",
            "rarity": "common",
            "finishes": "",
            "tcgplayer_id": None,
            "cardmarket_id": None,
            "released_at": "",
            "is_promo": 0,
            "is_reprint": 0,
        }
        printing = Printing.from_db_row(row)
        assert printing.finishes == []

    def test_roundtrip_serialization(self) -> None:
        original = Printing(
            scryfall_id="round-trip",
            card_id=1,
            set_code="RT",
            collector_number="1",
            rarity="mythic",
            finishes=["nonfoil", "foil", "etched"],
            tcgplayer_id=111,
            cardmarket_id=222,
            released_at="2025-06-15",
            is_promo=True,
            is_reprint=False,
        )
        row = original.to_db_row()
        row["id"] = 99
        restored = Printing.from_db_row(row)
        assert restored.scryfall_id == original.scryfall_id
        assert restored.finishes == original.finishes
        assert restored.is_promo == original.is_promo
        assert restored.is_reprint == original.is_reprint
