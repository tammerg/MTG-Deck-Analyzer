"""Tests for the PrintingRepository CRUD operations."""

from __future__ import annotations

import pytest

from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing


@pytest.fixture
def repos(db: Database) -> tuple[CardRepository, PrintingRepository]:
    """Create card and printing repositories."""
    return CardRepository(db), PrintingRepository(db)


@pytest.fixture
def card_id(repos: tuple[CardRepository, PrintingRepository]) -> int:
    """Insert a card and return its ID for printing tests."""
    card_repo, _ = repos
    card = Card(
        oracle_id="print-test-oracle",
        name="Print Test Card",
        type_line="Artifact",
        mana_cost="{1}",
        cmc=1.0,
        legal_commander=True,
    )
    return card_repo.insert_card(card)


class TestInsertPrinting:
    """Test printing insertion."""

    def test_insert_printing_returns_id(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printing = Printing(
            scryfall_id="test-scryfall-001",
            card_id=card_id,
            set_code="TST",
            collector_number="1",
            rarity="rare",
            finishes=["nonfoil"],
        )
        pid = printing_repo.insert_printing(printing)
        assert pid is not None
        assert pid > 0

    def test_insert_printing_persists(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printing = Printing(
            scryfall_id="persist-test",
            card_id=card_id,
            set_code="PER",
            collector_number="42",
            rarity="mythic",
            finishes=["nonfoil", "foil"],
            tcgplayer_id=999,
        )
        printing_repo.insert_printing(printing)
        found = printing_repo.get_printing_by_scryfall_id("persist-test")
        assert found is not None
        assert found.set_code == "PER"
        assert found.rarity == "mythic"
        assert found.finishes == ["nonfoil", "foil"]
        assert found.tcgplayer_id == 999

    def test_insert_duplicate_scryfall_id_raises(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printing = Printing(
            scryfall_id="dup-test",
            card_id=card_id,
            set_code="DUP",
            collector_number="1",
        )
        printing_repo.insert_printing(printing)
        with pytest.raises(Exception):
            printing_repo.insert_printing(printing)


class TestGetPrinting:
    """Test printing retrieval methods."""

    def test_get_by_scryfall_id_found(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printing = Printing(
            scryfall_id="find-me",
            card_id=card_id,
            set_code="FND",
            collector_number="1",
            rarity="uncommon",
        )
        printing_repo.insert_printing(printing)
        found = printing_repo.get_printing_by_scryfall_id("find-me")
        assert found is not None
        assert found.scryfall_id == "find-me"

    def test_get_by_scryfall_id_not_found(
        self,
        repos: tuple[CardRepository, PrintingRepository],
    ) -> None:
        _, printing_repo = repos
        found = printing_repo.get_printing_by_scryfall_id("doesnt-exist")
        assert found is None

    def test_get_printings_for_card(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        # Insert multiple printings for same card
        for i, code in enumerate(["SET1", "SET2", "SET3"]):
            printing = Printing(
                scryfall_id=f"multi-{i}",
                card_id=card_id,
                set_code=code,
                collector_number="1",
                released_at=f"202{i}-01-01",
            )
            printing_repo.insert_printing(printing)

        printings = printing_repo.get_printings_for_card(card_id)
        assert len(printings) == 3

    def test_get_printings_for_card_empty(
        self,
        repos: tuple[CardRepository, PrintingRepository],
    ) -> None:
        _, printing_repo = repos
        printings = printing_repo.get_printings_for_card(99999)
        assert printings == []

    def test_printing_preserves_all_fields(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printing = Printing(
            scryfall_id="full-fields",
            card_id=card_id,
            set_code="FUL",
            collector_number="100",
            lang="en",
            rarity="rare",
            finishes=["nonfoil", "foil", "etched"],
            tcgplayer_id=11111,
            cardmarket_id=22222,
            released_at="2025-06-15",
            is_promo=True,
            is_reprint=True,
        )
        printing_repo.insert_printing(printing)
        found = printing_repo.get_printing_by_scryfall_id("full-fields")
        assert found is not None
        assert found.lang == "en"
        assert found.rarity == "rare"
        assert found.finishes == ["nonfoil", "foil", "etched"]
        assert found.tcgplayer_id == 11111
        assert found.cardmarket_id == 22222
        assert found.released_at == "2025-06-15"
        assert found.is_promo is True
        assert found.is_reprint is True


class TestGetPrimaryPrinting:
    """Tests for get_primary_printing (best printing for image display)."""

    def test_returns_none_when_no_printings(
        self,
        repos: tuple[CardRepository, PrintingRepository],
    ) -> None:
        _, printing_repo = repos
        result = printing_repo.get_primary_printing(99999)
        assert result is None

    def test_returns_english_nonpromo_printing(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos

        promo = Printing(
            scryfall_id="primary-promo",
            card_id=card_id,
            set_code="PRM",
            collector_number="1",
            lang="en",
            released_at="2024-01-01",
            is_promo=True,
            is_reprint=False,
        )
        nonpromo = Printing(
            scryfall_id="primary-nonpromo",
            card_id=card_id,
            set_code="STD",
            collector_number="1",
            lang="en",
            released_at="2023-01-01",
            is_promo=False,
            is_reprint=True,
        )
        printing_repo.insert_printing(promo)
        printing_repo.insert_printing(nonpromo)

        result = printing_repo.get_primary_printing(card_id)
        assert result is not None
        # Prefers non-promo over promo even if promo is newer
        assert result.scryfall_id == "primary-nonpromo"

    def test_prefers_english_over_non_english(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos

        non_en = Printing(
            scryfall_id="primary-de",
            card_id=card_id,
            set_code="STD",
            collector_number="1",
            lang="de",
            released_at="2024-01-01",
            is_promo=False,
            is_reprint=False,
        )
        en = Printing(
            scryfall_id="primary-en",
            card_id=card_id,
            set_code="STD",
            collector_number="2",
            lang="en",
            released_at="2022-01-01",
            is_promo=False,
            is_reprint=True,
        )
        printing_repo.insert_printing(non_en)
        printing_repo.insert_printing(en)

        result = printing_repo.get_primary_printing(card_id)
        assert result is not None
        assert result.lang == "en"


class TestBulkInsertPrintings:
    """Test bulk printing insertion."""

    def test_bulk_insert_count(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printings = [
            Printing(
                scryfall_id=f"bulk-{i}",
                card_id=card_id,
                set_code=f"B{i:02d}",
                collector_number="1",
            )
            for i in range(5)
        ]
        count = printing_repo.bulk_insert_printings(printings)
        assert count == 5

    def test_bulk_insert_ignores_duplicates(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printings = [
            Printing(
                scryfall_id=f"dup-bulk-{i}",
                card_id=card_id,
                set_code=f"D{i:02d}",
                collector_number="1",
            )
            for i in range(3)
        ]
        printing_repo.bulk_insert_printings(printings)
        count = printing_repo.bulk_insert_printings(printings)
        assert count == 0

    def test_bulk_insert_retrievable(
        self,
        repos: tuple[CardRepository, PrintingRepository],
        card_id: int,
    ) -> None:
        _, printing_repo = repos
        printings = [
            Printing(
                scryfall_id=f"retrieve-{i}",
                card_id=card_id,
                set_code=f"R{i:02d}",
                collector_number="1",
            )
            for i in range(3)
        ]
        printing_repo.bulk_insert_printings(printings)
        all_printings = printing_repo.get_printings_for_card(card_id)
        assert len(all_printings) == 3
