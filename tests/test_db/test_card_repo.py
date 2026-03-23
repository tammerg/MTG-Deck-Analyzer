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

    def test_insert_card_persists_and_returns_id(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_id = card_repo.insert_card(sample_card)
        assert card_id is not None
        assert card_id > 0
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

    def test_get_card_by_name_oracle_id_and_id(
        self, card_repo: CardRepository, sample_card: Card
    ) -> None:
        card_id = card_repo.insert_card(sample_card)
        # By name
        by_name = card_repo.get_card_by_name("Sol Ring")
        assert by_name is not None
        assert by_name.name == "Sol Ring"
        assert by_name.id is not None
        # By oracle_id
        by_oracle = card_repo.get_card_by_oracle_id(sample_card.oracle_id)
        assert by_oracle is not None
        assert by_oracle.name == "Sol Ring"
        # By id
        by_id = card_repo.get_card_by_id(card_id)
        assert by_id is not None
        assert by_id.name == "Sol Ring"

    def test_get_card_by_name_not_found(
        self, card_repo: CardRepository
    ) -> None:
        assert card_repo.get_card_by_name("Nonexistent Card") is None

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


class TestSearchCardsFiltered:
    """Test search_cards with SQL-level type/color filtering and pagination."""

    def test_type_filter_returns_only_matching_type(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # sample_cards_for_db has 3 Instants; artifact and land should be excluded
        results = card_repo.search_cards("", type_filter="Instant")
        names = [c.name for c in results]
        assert "Counterspell" in names
        assert "Swords to Plowshares" in names
        assert "Lightning Bolt" in names
        assert "Sol Ring" not in names
        assert "Command Tower" not in names

    def test_type_filter_case_insensitive(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("", type_filter="instant")
        assert len(results) == 3

    def test_color_filter_excludes_outside_colors(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # color_filter="U" — only colorless and U cards should appear
        results = card_repo.search_cards("", color_filter="U")
        names = [c.name for c in results]
        assert "Counterspell" in names        # color_identity=["U"]
        assert "Sol Ring" in names            # colorless is subset of any color
        assert "Command Tower" in names       # colorless
        assert "Swords to Plowshares" not in names   # W
        assert "Lightning Bolt" not in names          # R

    def test_color_filter_multicolor(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("", color_filter="WU")
        names = [c.name for c in results]
        assert "Swords to Plowshares" in names   # W subset of WU
        assert "Counterspell" in names            # U subset of WU
        assert "Sol Ring" in names               # colorless subset of anything
        assert "Lightning Bolt" not in names     # R not in WU

    def test_limit_restricts_result_count(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("", limit=2)
        assert len(results) == 2

    def test_offset_skips_leading_results(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        all_results = card_repo.search_cards("", limit=100)
        paged = card_repo.search_cards("", offset=1, limit=100)
        assert len(paged) == len(all_results) - 1
        assert paged[0].name == all_results[1].name

    def test_offset_beyond_results_returns_empty(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.search_cards("", offset=9999, limit=50)
        assert results == []

    def test_combined_name_type_color_filter(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        # "spell" matches "Counterspell"; type=Instant; color=U
        results = card_repo.search_cards(
            "spell", type_filter="Instant", color_filter="U"
        )
        assert len(results) == 1
        assert results[0].name == "Counterspell"

    def test_count_reflects_full_filtered_total(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        total = card_repo.count_search_cards("", type_filter="Instant")
        assert total == 3

    def test_count_with_name_filter(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        total = card_repo.count_search_cards("Co")
        assert total == 2

    def test_count_no_match(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        total = card_repo.count_search_cards("Nonexistent")
        assert total == 0


class TestCommanderLegalCards:
    """Test filtering for commander-legal cards."""

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

    def test_five_color_returns_all(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        """Five-color identity should return all commander-legal cards."""
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity(["W", "U", "B", "R", "G"])
        assert len(results) == 5

    def test_colorless_identity_returns_colorless_cards(
        self, card_repo: CardRepository, sample_cards_for_db: list[Card]
    ) -> None:
        card_repo.bulk_insert_cards(sample_cards_for_db)
        results = card_repo.get_cards_by_color_identity([])
        names = [c.name for c in results]
        assert "Sol Ring" in names
        assert "Command Tower" in names
        assert "Swords to Plowshares" not in names

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
