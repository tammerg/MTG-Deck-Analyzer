"""Card repository for CRUD operations on the cards table."""

from __future__ import annotations

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.card import Card


class CardRepository:
    """Data access layer for the cards table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_card(self, card: Card) -> int:
        """Insert a card into the database.

        Args:
            card: Card instance to insert.

        Returns:
            The database ID of the inserted card.
        """
        row = card.to_db_row()
        cursor = self._db.execute(
            """
            INSERT INTO cards (
                oracle_id, name, type_line, oracle_text, mana_cost,
                cmc, colors, color_identity, keywords, edhrec_rank,
                legal_commander, legal_brawl, updated_at
            ) VALUES (
                :oracle_id, :name, :type_line, :oracle_text, :mana_cost,
                :cmc, :colors, :color_identity, :keywords, :edhrec_rank,
                :legal_commander, :legal_brawl, :updated_at
            )
            """,
            row,
        )
        self._db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_card_by_name(self, name: str) -> Card | None:
        """Look up a card by exact name.

        Args:
            name: Exact card name to search for.

        Returns:
            Card instance or None if not found.
        """
        cursor = self._db.execute(
            "SELECT * FROM cards WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Card.from_db_row(dict(row))

    def get_card_by_oracle_id(self, oracle_id: str) -> Card | None:
        """Look up a card by oracle ID.

        Args:
            oracle_id: The oracle ID to search for.

        Returns:
            Card instance or None if not found.
        """
        cursor = self._db.execute(
            "SELECT * FROM cards WHERE oracle_id = ?", (oracle_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Card.from_db_row(dict(row))

    def get_card_by_id(self, card_id: int) -> Card | None:
        """Look up a card by its database ID.

        Args:
            card_id: The database primary key.

        Returns:
            Card instance or None if not found.
        """
        cursor = self._db.execute(
            "SELECT * FROM cards WHERE id = ?", (card_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Card.from_db_row(dict(row))

    def search_cards(self, query: str) -> list[Card]:
        """Search cards by name using LIKE matching.

        Args:
            query: Search string (will be wrapped in % wildcards).

        Returns:
            List of matching Card instances.
        """
        cursor = self._db.execute(
            "SELECT * FROM cards WHERE name LIKE ? ORDER BY name",
            (f"%{query}%",),
        )
        return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_commander_legal_cards(self) -> list[Card]:
        """Return all cards that are legal in Commander format.

        Returns:
            List of Commander-legal Card instances.
        """
        cursor = self._db.execute(
            "SELECT * FROM cards WHERE legal_commander = 1 ORDER BY name"
        )
        return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_cards_by_color_identity(self, colors: list[str]) -> list[Card]:
        """Return cards whose color identity is a subset of the given colors.

        For a card to be within identity, every color in its color_identity
        must be present in the provided colors list.

        Args:
            colors: List of color characters (e.g., ["W", "U", "B"]).

        Returns:
            List of Card instances within the color identity.
        """
        # For empty color identity (colorless), return cards with empty identity
        if not colors:
            cursor = self._db.execute(
                "SELECT * FROM cards WHERE color_identity = '' "
                "OR color_identity IS NULL ORDER BY name"
            )
            return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

        # Fetch all cards and filter in Python since SQLite doesn't natively
        # support set-subset operations on comma-separated values
        cursor = self._db.execute("SELECT * FROM cards ORDER BY name")
        result = []
        color_set = set(colors)
        for row in cursor.fetchall():
            row_dict = dict(row)
            card_identity_str = row_dict.get("color_identity", "")
            if not card_identity_str:
                # Colorless cards are always within any identity
                result.append(Card.from_db_row(row_dict))
            else:
                card_colors = {
                    c for c in card_identity_str.split(",") if c
                }
                if card_colors.issubset(color_set):
                    result.append(Card.from_db_row(row_dict))
        return result

    def bulk_insert_cards(self, cards: list[Card]) -> int:
        """Insert multiple cards in a single transaction.

        Uses INSERT OR IGNORE to skip duplicates (by oracle_id).

        Args:
            cards: List of Card instances to insert.

        Returns:
            Number of cards actually inserted.
        """
        rows = [card.to_db_row() for card in cards]
        cursor = self._db.executemany(
            """
            INSERT OR IGNORE INTO cards (
                oracle_id, name, type_line, oracle_text, mana_cost,
                cmc, colors, color_identity, keywords, edhrec_rank,
                legal_commander, legal_brawl, updated_at
            ) VALUES (
                :oracle_id, :name, :type_line, :oracle_text, :mana_cost,
                :cmc, :colors, :color_identity, :keywords, :edhrec_rank,
                :legal_commander, :legal_brawl, :updated_at
            )
            """,
            rows,
        )
        self._db.commit()
        return cursor.rowcount
