"""Tests for the LLM synergy cache repository (SQLite-backed data access)."""

from __future__ import annotations

import pytest

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.llm_synergy_repo import LLMSynergyRepo


@pytest.fixture
def repo(db: Database) -> LLMSynergyRepo:
    """Create an LLMSynergyRepo with the test database."""
    r = LLMSynergyRepo(db)
    r.create_tables()
    return r


@pytest.fixture
def sample_scores() -> dict[tuple[str, str], float]:
    """Return sample synergy scores (canonically ordered card pairs)."""
    return {
        ("Doubling Season", "Hardened Scales"): 0.85,
        ("Doubling Season", "Sol Ring"): 0.30,
        ("Hardened Scales", "Sol Ring"): 0.25,
    }


COMMANDER = "Atraxa, Praetors' Voice"
MODEL = "claude-sonnet-4-20250514"
ALT_MODEL = "gpt-4o"


class TestCreateTables:
    """Test table creation."""

    def test_create_tables_succeeds(self, db: Database) -> None:
        """create_tables should create the llm_synergy_cache table."""
        r = LLMSynergyRepo(db)
        r.create_tables()
        cursor = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='llm_synergy_cache'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "llm_synergy_cache"

    def test_create_tables_idempotent(self, db: Database) -> None:
        """Calling create_tables twice should not raise."""
        r = LLMSynergyRepo(db)
        r.create_tables()
        r.create_tables()  # Should not raise


class TestUpsertScores:
    """Test inserting and updating synergy scores."""

    def test_upsert_inserts_new_scores(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """upsert_scores should insert new rows."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        assert repo.count_pairs(COMMANDER, MODEL) == 3

    def test_upsert_updates_existing_scores(
        self,
        repo: LLMSynergyRepo,
    ) -> None:
        """upsert_scores should replace scores for existing keys."""
        initial = {("Doubling Season", "Hardened Scales"): 0.85}
        repo.upsert_scores(COMMANDER, initial, MODEL)

        updated = {("Doubling Season", "Hardened Scales"): 0.95}
        repo.upsert_scores(COMMANDER, updated, MODEL)

        # Should still be 1 row, not 2
        assert repo.count_pairs(COMMANDER, MODEL) == 1

        matrix = repo.get_cached_matrix(
            COMMANDER,
            ["Doubling Season", "Hardened Scales"],
            MODEL,
        )
        assert matrix[("Doubling Season", "Hardened Scales")] == pytest.approx(0.95)

    def test_upsert_empty_scores_is_noop(self, repo: LLMSynergyRepo) -> None:
        """upsert_scores with empty dict should not error."""
        repo.upsert_scores(COMMANDER, {}, MODEL)
        assert repo.count_pairs(COMMANDER, MODEL) == 0


class TestGetCachedMatrix:
    """Test retrieving cached synergy matrices."""

    def test_returns_empty_dict_when_no_data(
        self, repo: LLMSynergyRepo
    ) -> None:
        """get_cached_matrix should return empty dict when table is empty."""
        result = repo.get_cached_matrix(
            COMMANDER, ["Doubling Season", "Sol Ring"], MODEL
        )
        assert result == {}

    def test_returns_empty_dict_with_empty_card_names(
        self, repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """get_cached_matrix should return empty dict for empty card list."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        result = repo.get_cached_matrix(COMMANDER, [], MODEL)
        assert result == {}

    def test_returns_matching_scores(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """get_cached_matrix should return all matching pairs."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        result = repo.get_cached_matrix(
            COMMANDER,
            ["Doubling Season", "Hardened Scales", "Sol Ring"],
            MODEL,
        )
        assert len(result) == 3
        assert result[("Doubling Season", "Hardened Scales")] == pytest.approx(0.85)
        assert result[("Doubling Season", "Sol Ring")] == pytest.approx(0.30)
        assert result[("Hardened Scales", "Sol Ring")] == pytest.approx(0.25)

    def test_filters_by_card_names(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """get_cached_matrix should only return pairs where both cards match."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        # Only request two of the three cards
        result = repo.get_cached_matrix(
            COMMANDER,
            ["Doubling Season", "Hardened Scales"],
            MODEL,
        )
        assert len(result) == 1
        assert ("Doubling Season", "Hardened Scales") in result
        # Pairs involving Sol Ring should be excluded
        assert ("Doubling Season", "Sol Ring") not in result
        assert ("Hardened Scales", "Sol Ring") not in result

    def test_filters_by_model(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """get_cached_matrix should only return scores for the given model."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)

        result = repo.get_cached_matrix(
            COMMANDER,
            ["Doubling Season", "Hardened Scales", "Sol Ring"],
            ALT_MODEL,
        )
        assert result == {}


class TestHasData:
    """Test checking for cached commander data."""

    def test_returns_false_when_empty(self, repo: LLMSynergyRepo) -> None:
        """has_data should return False when no data exists."""
        assert repo.has_data(COMMANDER, MODEL) is False

    def test_returns_true_after_insert(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """has_data should return True after inserting scores."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        assert repo.has_data(COMMANDER, MODEL) is True

    def test_filters_by_model(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """has_data should be False for a model with no data."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        assert repo.has_data(COMMANDER, ALT_MODEL) is False


class TestCountPairs:
    """Test counting cached synergy pairs."""

    def test_returns_correct_count(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """count_pairs should return the number of cached pairs."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        assert repo.count_pairs(COMMANDER, MODEL) == 3


class TestDeleteCommander:
    """Test deleting cached data for a commander."""

    def test_removes_all_data(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """delete_commander should remove all rows for that commander."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        repo.delete_commander(COMMANDER)
        assert repo.has_data(COMMANDER, MODEL) is False
        assert repo.count_pairs(COMMANDER, MODEL) == 0

    def test_returns_correct_rowcount(
        self,
        repo: LLMSynergyRepo,
        sample_scores: dict[tuple[str, str], float],
    ) -> None:
        """delete_commander should return the number of deleted rows."""
        repo.upsert_scores(COMMANDER, sample_scores, MODEL)
        deleted = repo.delete_commander(COMMANDER)
        assert deleted == 3
