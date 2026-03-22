"""Tests for the EDHREC repository (SQLite-backed data access)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.edhrec_repo import EdhrecRepository
from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData


@pytest.fixture
def edhrec_repo(db: Database) -> EdhrecRepository:
    """Create an EdhrecRepository with the test database."""
    repo = EdhrecRepository(db)
    repo.create_tables()
    return repo


@pytest.fixture
def sample_edhrec_data() -> list[EdhrecCommanderData]:
    """Return sample EDHREC data for Atraxa."""
    return [
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Doubling Season",
            inclusion_rate=0.45,
            num_decks=9000,
            potential_decks=20000,
            synergy_score=0.12,
        ),
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Hardened Scales",
            inclusion_rate=0.40,
            num_decks=8000,
            potential_decks=20000,
            synergy_score=0.15,
        ),
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Sol Ring",
            inclusion_rate=0.95,
            num_decks=19000,
            potential_decks=20000,
            synergy_score=-0.02,
        ),
    ]


class TestCreateTables:
    """Test table creation."""

    def test_create_tables(self, db: Database) -> None:
        """create_tables should create the edhrec_commander_cards table."""
        repo = EdhrecRepository(db)
        repo.create_tables()
        cursor = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='edhrec_commander_cards'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "edhrec_commander_cards"


class TestUpsertData:
    """Test upserting EDHREC data."""

    def test_upsert_data(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
    ) -> None:
        """Upsert should insert new records and update existing ones."""
        edhrec_repo.upsert_data(sample_edhrec_data)

        top = edhrec_repo.get_top_cards("Atraxa, Praetors' Voice", limit=10)
        assert len(top) == 3

        # Update one record
        updated = [
            EdhrecCommanderData(
                commander_name="Atraxa, Praetors' Voice",
                card_name="Doubling Season",
                inclusion_rate=0.50,
                num_decks=10000,
                potential_decks=20000,
                synergy_score=0.14,
            ),
        ]
        edhrec_repo.upsert_data(updated)

        rate = edhrec_repo.get_card_inclusion(
            "Atraxa, Praetors' Voice", "Doubling Season"
        )
        assert rate == 0.50

        top = edhrec_repo.get_top_cards("Atraxa, Praetors' Voice", limit=10)
        assert len(top) == 3


class TestGetCardInclusion:
    """Test getting per-card inclusion rate."""

    @pytest.mark.parametrize(
        "card_name, expected",
        [
            ("Sol Ring", 0.95),
            ("Nonexistent Card", None),
        ],
        ids=["found", "missing"],
    )
    def test_get_card_inclusion(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
        card_name: str,
        expected,
    ) -> None:
        edhrec_repo.upsert_data(sample_edhrec_data)
        rate = edhrec_repo.get_card_inclusion(
            "Atraxa, Praetors' Voice", card_name
        )
        assert rate == expected


class TestGetTopCards:
    """Test getting top cards by inclusion rate."""

    @pytest.mark.parametrize(
        "commander, limit, expected_len, first_card",
        [
            ("Atraxa, Praetors' Voice", 2, 2, "Sol Ring"),
            ("Unknown Commander", 10, 0, None),
        ],
        ids=["top_cards", "empty_unknown"],
    )
    def test_get_top_cards(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
        commander: str,
        limit: int,
        expected_len: int,
        first_card,
    ) -> None:
        edhrec_repo.upsert_data(sample_edhrec_data)
        top = edhrec_repo.get_top_cards(commander, limit=limit)
        assert len(top) == expected_len
        if first_card:
            assert top[0].card_name == first_card


class TestHasData:
    """Test checking for cached commander data."""

    def test_has_data_true(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
    ) -> None:
        """Should return True when data exists for a commander."""
        edhrec_repo.upsert_data(sample_edhrec_data)
        assert edhrec_repo.has_data("Atraxa, Praetors' Voice") is True


class TestCountCommanders:
    """Test counting distinct commanders with data."""

    def test_count_commanders(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
    ) -> None:
        """Should count distinct commanders."""
        edhrec_repo.upsert_data(sample_edhrec_data)

        extra = [
            EdhrecCommanderData(
                commander_name="Krenko, Mob Boss",
                card_name="Goblin Chieftain",
                inclusion_rate=0.80,
                num_decks=5000,
                potential_decks=6000,
                synergy_score=0.30,
            ),
        ]
        edhrec_repo.upsert_data(extra)

        assert edhrec_repo.count_commanders() == 2


class TestIsStale:
    """Test staleness check for cached data."""

    def test_is_stale(
        self,
        edhrec_repo: EdhrecRepository,
        sample_edhrec_data: list[EdhrecCommanderData],
    ) -> None:
        """Data older than max_age_days should be considered stale."""
        edhrec_repo.upsert_data(sample_edhrec_data)

        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).isoformat()
        edhrec_repo._db.execute(
            "UPDATE edhrec_commander_cards SET fetched_at = ? "
            "WHERE commander_name = ?",
            (old_ts, "Atraxa, Praetors' Voice"),
        )
        edhrec_repo._db.commit()

        assert edhrec_repo.is_stale("Atraxa, Praetors' Voice", max_age_days=30) is True

    def test_is_stale_no_data(self, edhrec_repo: EdhrecRepository) -> None:
        """No data should be considered stale."""
        assert edhrec_repo.is_stale("Unknown Commander", max_age_days=30) is True
