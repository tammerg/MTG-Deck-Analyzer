"""Tests for the ComboRepository CRUD operations."""

from __future__ import annotations

import pytest

from mtg_deck_maker.db.combo_repo import ComboRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.combo import Combo


@pytest.fixture
def combo_repo(db: Database) -> ComboRepository:
    """Create a ComboRepository with the test database."""
    repo = ComboRepository(db)
    repo.create_tables()
    return repo


@pytest.fixture
def sample_combo() -> Combo:
    """Return a sample two-card combo for testing."""
    return Combo(
        combo_id="csb-100",
        card_names=["Exquisite Blood", "Sanguine Bond"],
        result="Infinite damage, infinite lifegain",
        color_identity=["B"],
        prerequisite="Both permanents on the battlefield",
        description="Whenever you gain life, Sanguine Bond deals damage.",
    )


@pytest.fixture
def sample_combo_b() -> Combo:
    """Return a second sample combo sharing a card with sample_combo."""
    return Combo(
        combo_id="csb-200",
        card_names=["Exquisite Blood", "Vito, Thorn of the Dusk Rose"],
        result="Infinite damage, infinite lifegain",
        color_identity=["B"],
        prerequisite="Both permanents on the battlefield",
        description="Vito triggers on lifegain, Exquisite Blood triggers on damage.",
    )


@pytest.fixture
def sample_combo_c() -> Combo:
    """Return a third combo with no shared cards."""
    return Combo(
        combo_id="csb-300",
        card_names=["Dramatic Reversal", "Isochron Scepter"],
        result="Infinite mana",
        color_identity=["U"],
        prerequisite="Isochron Scepter imprinted with Dramatic Reversal, "
        "nonland permanents that produce 3+ mana",
        description="Activate Scepter to cast Dramatic Reversal, "
        "untapping all nonland permanents including Scepter.",
    )


class TestCreateTables:
    """Test table creation."""

    def test_create_tables(self, db: Database) -> None:
        repo = ComboRepository(db)
        repo.create_tables()
        # Verify tables exist by querying them
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='combos'"
        )
        assert cursor.fetchone() is not None

    def test_create_tables_creates_combo_cards(self, db: Database) -> None:
        repo = ComboRepository(db)
        repo.create_tables()
        cursor = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='combo_cards'"
        )
        assert cursor.fetchone() is not None

    def test_create_tables_idempotent(self, db: Database) -> None:
        repo = ComboRepository(db)
        repo.create_tables()
        repo.create_tables()  # Should not raise


class TestUpsertCombo:
    """Test combo insertion and update."""

    def test_upsert_combo(
        self, combo_repo: ComboRepository, sample_combo: Combo
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        combos = combo_repo.get_combos_for_card("Exquisite Blood")
        assert len(combos) == 1
        assert combos[0].combo_id == "csb-100"

    def test_upsert_overwrites(
        self, combo_repo: ComboRepository, sample_combo: Combo
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        # Update the result text
        updated = Combo(
            combo_id="csb-100",
            card_names=["Exquisite Blood", "Sanguine Bond"],
            result="Updated result text",
            color_identity=["B"],
            prerequisite="Updated prerequisite",
            description="Updated description",
        )
        combo_repo.upsert_combo(updated)
        combos = combo_repo.get_combos_for_card("Exquisite Blood")
        assert len(combos) == 1
        assert combos[0].result == "Updated result text"
        assert combos[0].prerequisite == "Updated prerequisite"

    def test_upsert_creates_combo_cards(
        self, combo_repo: ComboRepository, sample_combo: Combo
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        # Both card names should be in combo_cards
        combos_a = combo_repo.get_combos_for_card("Exquisite Blood")
        combos_b = combo_repo.get_combos_for_card("Sanguine Bond")
        assert len(combos_a) == 1
        assert len(combos_b) == 1
        assert combos_a[0].combo_id == combos_b[0].combo_id


class TestGetCombosForCard:
    """Test retrieving combos by card name."""

    def test_get_combos_for_card(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
        sample_combo_b: Combo,
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        combo_repo.upsert_combo(sample_combo_b)
        # Exquisite Blood appears in both combos
        combos = combo_repo.get_combos_for_card("Exquisite Blood")
        assert len(combos) == 2
        combo_ids = {c.combo_id for c in combos}
        assert "csb-100" in combo_ids
        assert "csb-200" in combo_ids

    def test_get_combos_for_card_not_found(
        self, combo_repo: ComboRepository
    ) -> None:
        combos = combo_repo.get_combos_for_card("Nonexistent Card")
        assert combos == []

    def test_get_combos_for_card_case_sensitive(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        # Exact name match required
        combos = combo_repo.get_combos_for_card("exquisite blood")
        assert combos == []


class TestGetCombosForCards:
    """Test retrieving combos matching any of several card names."""

    def test_get_combos_for_cards_multiple(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
        sample_combo_b: Combo,
        sample_combo_c: Combo,
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        combo_repo.upsert_combo(sample_combo_b)
        combo_repo.upsert_combo(sample_combo_c)
        # Search for cards in combo a and c
        combos = combo_repo.get_combos_for_cards(
            ["Sanguine Bond", "Dramatic Reversal"]
        )
        assert len(combos) == 2
        combo_ids = {c.combo_id for c in combos}
        assert "csb-100" in combo_ids
        assert "csb-300" in combo_ids

    def test_get_combos_for_cards_empty_list(
        self, combo_repo: ComboRepository
    ) -> None:
        combos = combo_repo.get_combos_for_cards([])
        assert combos == []

    def test_get_combos_for_cards_deduplicates(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        # Both cards are in the same combo - should not duplicate
        combos = combo_repo.get_combos_for_cards(
            ["Exquisite Blood", "Sanguine Bond"]
        )
        assert len(combos) == 1


class TestGetComboPartners:
    """Test retrieving combo partner card names."""

    def test_get_combo_partners(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
        sample_combo_b: Combo,
    ) -> None:
        combo_repo.upsert_combo(sample_combo)
        combo_repo.upsert_combo(sample_combo_b)
        partners = combo_repo.get_combo_partners("Exquisite Blood")
        # Sanguine Bond and Vito are partners
        assert "Sanguine Bond" in partners
        assert "Vito, Thorn of the Dusk Rose" in partners
        # Should not include the card itself
        assert "Exquisite Blood" not in partners

    def test_get_combo_partners_no_combos(
        self, combo_repo: ComboRepository
    ) -> None:
        partners = combo_repo.get_combo_partners("Nonexistent Card")
        assert partners == []


class TestCount:
    """Test counting combos."""

    def test_count(
        self,
        combo_repo: ComboRepository,
        sample_combo: Combo,
        sample_combo_b: Combo,
        sample_combo_c: Combo,
    ) -> None:
        assert combo_repo.count() == 0
        combo_repo.upsert_combo(sample_combo)
        assert combo_repo.count() == 1
        combo_repo.upsert_combo(sample_combo_b)
        assert combo_repo.count() == 2
        combo_repo.upsert_combo(sample_combo_c)
        assert combo_repo.count() == 3
