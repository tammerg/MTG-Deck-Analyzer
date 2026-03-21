"""Tests for the CardRepository CRUD operations."""

from __future__ import annotations

import pytest

from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.card import Card


@pytest.fixture
def card_repo(db: Database) -> CardRepository:
    """Create a CardRepository with the test database."""
    return CardRepository(db)


class TestInsertCard:
    """Test card insertion."""

    def test_insert_card_returns_id(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_id = card_repo.insert_card(sample_card)
        assert card_id is not None
        assert card_id > 0

    def test_insert_card_persists(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_repo.insert_card(sample_card)
        found = card_repo.get_card_by_name("Sol Ring")
        assert found is not None
        assert found.name == "Sol Ring"
        assert found.oracle_id == sample_card.oracle_id

    def test_insert_duplicate_oracle_id_raises(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_repo.insert_card(sample_card)
        with pytest.raises(Exception):
            card_repo.insert_card(sample_card)


class TestGetCard:
    """Test card retrieval methods."""

    def test_get_card_by_name_found(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_repo.insert_card(sample_card)
        found = card_repo.get_card_by_name("Sol Ring")
        assert found is not None
        assert found.name == "Sol Ring"
        assert found.id is not None

    def test_get_card_by_name_not_found(
        self, card_repo: CardRepository
    ) -> None:
        found = card_repo.get_card_by_name("Nonexistent Card")
        assert found is None

    def test_get_card_by_oracle_id(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_repo.insert_card(sample_card)
        found = card_repo.get_card_by_oracle_id(sample_card.oracle_id)
        assert found is not None
        assert found.name == "Sol Ring"

    def test_get_card_by_oracle_id_not_found(
        self, card_repo: CardRepository
    ) -> None:
        found = card_repo.get_card_by_oracle_id("nonexistent-id")
        assert found is None

    def test_get_card_by_id(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_id = card_repo.insert_card(sample_card)
        found = card_repo.get_card_by_id(card_id)
        assert found is not None
        assert found.name == "Sol Ring"

    def test_get_card_preserves_all_fields(
        self, card_repo: CardRepository, sample_commander_card: Card
    ) -> None:
        card_repo.insert_card(sample_commander_card)
        found = card_repo.get_card_by_name("Atraxa, Praetors' Voice")
        assert found is not None
        assert found.colors == ["W", "U", "B", "G"]
        assert found.color_identity == ["W", "U", "B", "G"]
        assert found.keywords == [
            "Flying",
            "Vigilance",
            "Deathtouch",
            "Lifelink",
        ]
        assert found.cmc == 4.0
        assert found.legal_commander is True
        assert found.legal_brawl is True
        assert found.edhrec_rank == 5


class TestSearchCards:
    """Test card search functionality."""

    def test_search_by_partial_name(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("Ring")
        assert len(results) == 1
        assert results[0].name == "Sol Ring"

    def test_search_case_insensitive_like(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # SQLite LIKE is case-insensitive for ASCII
        results = card_repo.search_cards("sol")
        assert len(results) == 1

    def test_search_no_results(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("Nonexistent")
        assert results == []

    def test_search_multiple_results(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # Both "Command Tower" and "Counterspell" start with "Co"
        results = card_repo.search_cards("Co")
        assert len(results) == 2


class TestCommanderLegalCards:
    """Test filtering for commander-legal cards."""

    def test_get_commander_legal_cards(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        legal = card_repo.get_commander_legal_cards()
        assert len(legal) == 5  # All sample cards are commander-legal

    def test_excludes_non_legal_cards(
        self, card_repo: CardRepository
    ) -> None:
        legal_card = Card(
            oracle_id="legal",
            name="Legal Card",
            legal_commander=True,
        )
        illegal_card = Card(
            oracle_id="illegal",
            name="Illegal Card",
            legal_commander=False,
        )
        card_repo.insert_card(legal_card)
        card_repo.insert_card(illegal_card)

        legal = card_repo.get_commander_legal_cards()
        assert len(legal) == 1
        assert legal[0].name == "Legal Card"


class TestColorIdentityFilter:
    """Test filtering cards by color identity."""

    def test_colorless_identity_returns_colorless_cards(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity([])
        # Sol Ring and Command Tower are colorless
        names = [c.name for c in results]
        assert "Sol Ring" in names
        assert "Command Tower" in names
        assert "Swords to Plowshares" not in names

    def test_mono_white_includes_colorless(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity(["W"])
        names = [c.name for c in results]
        assert "Sol Ring" in names  # Colorless
        assert "Swords to Plowshares" in names  # White
        assert "Counterspell" not in names  # Blue

    def test_full_wubrg_includes_all(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity(
            ["W", "U", "B", "R", "G"]
        )
        assert len(results) == 5  # All cards fit in WUBRG


    def test_color_identity_excludes_outside_colors(
        self, card_repo: CardRepository
    ) -> None:
        """Cards with colors outside the identity should be excluded."""
        card_repo.insert_card(Card(
            oracle_id="wu-card",
            name="WU Card",
            type_line="Creature",
            color_identity=["W", "U"],
            legal_commander=True,
        ))
        card_repo.insert_card(Card(
            oracle_id="r-card",
            name="Red Card",
            type_line="Creature",
            color_identity=["R"],
            legal_commander=True,
        ))
        results = card_repo.get_cards_by_color_identity(["W", "U"])
        names = [c.name for c in results]
        assert "WU Card" in names
        assert "Red Card" not in names

    def test_five_color_returns_all(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        """Five-color identity should return all commander-legal cards."""
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity(["W", "U", "B", "R", "G"])
        assert len(results) == 5

    def test_colorless_cards_always_included(
        self, card_repo: CardRepository
    ) -> None:
        """Colorless cards should be returned for any non-empty identity."""
        card_repo.insert_card(Card(
            oracle_id="colorless-rock",
            name="Mana Rock",
            type_line="Artifact",
            color_identity=[],
            legal_commander=True,
        ))
        card_repo.insert_card(Card(
            oracle_id="green-creature",
            name="Green Elf",
            type_line="Creature",
            color_identity=["G"],
            legal_commander=True,
        ))
        # Ask for mono-red: should include colorless but not green
        results = card_repo.get_cards_by_color_identity(["R"])
        names = [c.name for c in results]
        assert "Mana Rock" in names
        assert "Green Elf" not in names


class TestBulkInsert:
    """Test bulk card insertion."""

    def test_bulk_insert_count(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        count = card_repo.bulk_insert_cards(sample_cards_for_db)
        assert count == 5

    def test_bulk_insert_ignores_duplicates(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # Second insert should skip all duplicates
        count = card_repo.bulk_insert_cards(sample_cards_for_db)
        assert count == 0

    def test_bulk_insert_cards_retrievable(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        for card in sample_cards_for_db:
            found = card_repo.get_card_by_oracle_id(card.oracle_id)
            assert found is not None
            assert found.name == card.name
