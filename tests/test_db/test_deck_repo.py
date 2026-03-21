"""Tests for the DeckRepository data access layer."""

from __future__ import annotations

import pytest

from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.deck_repo import DeckRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck, DeckCard


@pytest.fixture
def deck_db():
    """In-memory database with a seeded card."""
    db = Database(":memory:")
    db.connect()

    card_repo = CardRepository(db)
    card = Card(
        oracle_id="test-oracle-id",
        name="Test Commander",
        type_line="Legendary Creature",
        oracle_text="Test",
        mana_cost="{3}",
        cmc=3.0,
        colors=[],
        color_identity=[],
        keywords=[],
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )
    card_id = card_repo.insert_card(card)

    yield db, card_id
    db.close()


def _make_deck(card_id: int) -> Deck:
    """Create a minimal test Deck."""
    deck = Deck(
        name="Test Deck",
        format="commander",
        budget_target=100.0,
        created_at="2026-01-01T00:00:00+00:00",
    )
    deck.cards = [
        DeckCard(
            card_id=card_id,
            quantity=1,
            category="commander",
            is_commander=True,
            card_name="Test Commander",
            cmc=3.0,
            colors=[],
        )
    ]
    return deck


class TestCreateDeck:
    def test_create_returns_int_id(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))
        assert isinstance(deck_id, int)
        assert deck_id > 0

    def test_create_persists_deck_row(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))

        cursor = db.execute("SELECT * FROM decks WHERE id = ?", (deck_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Test Deck"

    def test_create_persists_deck_cards(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))

        cursor = db.execute(
            "SELECT * FROM deck_cards WHERE deck_id = ?", (deck_id,)
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["card_id"] == card_id
        assert rows[0]["is_commander"] == 1


class TestGetDeck:
    def test_get_existing_deck(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))

        deck = repo.get_deck(deck_id)
        assert deck is not None
        assert deck.name == "Test Deck"
        assert len(deck.cards) == 1

    def test_get_deck_cards_loaded(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))

        deck = repo.get_deck(deck_id)
        assert deck is not None
        dc = deck.cards[0]
        assert dc.card_id == card_id
        assert dc.is_commander is True
        assert dc.card_name == "Test Commander"

    def test_get_nonexistent_deck_returns_none(self, deck_db) -> None:
        db, _ = deck_db
        repo = DeckRepository(db)
        assert repo.get_deck(99999) is None


class TestListDecks:
    def test_list_empty_returns_empty_list(self, deck_db) -> None:
        db, _ = deck_db
        repo = DeckRepository(db)
        assert repo.list_decks() == []

    def test_list_returns_all_decks(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)

        repo.create_deck(_make_deck(card_id))
        deck2 = _make_deck(card_id)
        deck2.name = "Second Deck"
        repo.create_deck(deck2)

        decks = repo.list_decks()
        assert len(decks) == 2


class TestDeleteDeck:
    def test_delete_existing_deck(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))

        result = repo.delete_deck(deck_id)
        assert result is True
        assert repo.get_deck(deck_id) is None

    def test_delete_removes_deck_cards(self, deck_db) -> None:
        db, card_id = deck_db
        repo = DeckRepository(db)
        deck_id = repo.create_deck(_make_deck(card_id))
        repo.delete_deck(deck_id)

        cursor = db.execute(
            "SELECT COUNT(*) as cnt FROM deck_cards WHERE deck_id = ?",
            (deck_id,),
        )
        assert cursor.fetchone()["cnt"] == 0

    def test_delete_nonexistent_returns_false(self, deck_db) -> None:
        db, _ = deck_db
        repo = DeckRepository(db)
        assert repo.delete_deck(99999) is False
