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
        must be present in the provided colors list.  Uses SQL-level filtering
        to avoid loading the entire card table into Python.

        Args:
            colors: List of color characters (e.g., ["W", "U", "B"]).

        Returns:
            List of Card instances within the color identity.
        """
        if not colors:
            # Colorless commander: only colorless cards
            cursor = self._db.execute(
                "SELECT * FROM cards WHERE (color_identity = '' "
                "OR color_identity IS NULL) AND legal_commander = 1 "
                "ORDER BY name"
            )
            return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

        all_colors = {"W", "U", "B", "R", "G"}
        excluded = all_colors - set(colors)

        if not excluded:
            # 5-color: all commander-legal cards
            cursor = self._db.execute(
                "SELECT * FROM cards WHERE legal_commander = 1 ORDER BY name"
            )
            return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

        # Exclude cards containing any color NOT in the commander's identity.
        # color_identity is stored as comma-separated (e.g. "W,U,B").
        # For each excluded color, we ensure it doesn't appear in the string.
        conditions = []
        params: list[str] = []
        for color in excluded:
            conditions.append(
                "(color_identity NOT LIKE ? AND color_identity NOT LIKE ? "
                "AND color_identity NOT LIKE ? AND color_identity != ?)"
            )
            params.extend([f"%,{color},%", f"{color},%", f"%,{color}", color])

        where = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM cards WHERE legal_commander = 1 "
            f"AND ({where} OR color_identity = '' OR color_identity IS NULL) "
            f"ORDER BY name"
        )
        cursor = self._db.execute(sql, tuple(params))
        return [Card.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_cards_by_ids(self, card_ids: list[int]) -> dict[int, Card]:
        """Look up multiple cards by their database IDs in a single query.

        Uses chunked queries to stay within SQLite's variable limit.

        Args:
            card_ids: List of card database primary keys.

        Returns:
            Dict mapping card_id to Card instance. Missing IDs are omitted.
        """
        if not card_ids:
            return {}
        result: dict[int, Card] = {}
        chunk_size = 900  # SQLite variable limit safety margin
        for i in range(0, len(card_ids), chunk_size):
            chunk = card_ids[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor = self._db.execute(
                f"SELECT * FROM cards WHERE id IN ({placeholders})",
                tuple(chunk),
            )
            for row in cursor.fetchall():
                card = Card.from_db_row(dict(row))
                if card.id is not None:
                    result[card.id] = card
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
