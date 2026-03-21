"""Printing repository for CRUD operations on the printings table."""

from __future__ import annotations

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.printing import Printing


class PrintingRepository:
    """Data access layer for the printings table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_printing(self, printing: Printing) -> int:
        """Insert a printing into the database.

        Args:
            printing: Printing instance to insert.

        Returns:
            The database ID of the inserted printing.
        """
        row = printing.to_db_row()
        cursor = self._db.execute(
            """
            INSERT INTO printings (
                scryfall_id, card_id, set_code, collector_number, lang,
                rarity, finishes, tcgplayer_id, cardmarket_id,
                released_at, is_promo, is_reprint
            ) VALUES (
                :scryfall_id, :card_id, :set_code, :collector_number, :lang,
                :rarity, :finishes, :tcgplayer_id, :cardmarket_id,
                :released_at, :is_promo, :is_reprint
            )
            """,
            row,
        )
        self._db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_printing_by_scryfall_id(self, scryfall_id: str) -> Printing | None:
        """Look up a printing by its Scryfall ID.

        Args:
            scryfall_id: The Scryfall UUID to search for.

        Returns:
            Printing instance or None if not found.
        """
        cursor = self._db.execute(
            "SELECT * FROM printings WHERE scryfall_id = ?", (scryfall_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Printing.from_db_row(dict(row))

    def get_printings_for_card(self, card_id: int) -> list[Printing]:
        """Return all printings for a given card.

        Args:
            card_id: The card's database ID.

        Returns:
            List of Printing instances for this card.
        """
        cursor = self._db.execute(
            "SELECT * FROM printings WHERE card_id = ? ORDER BY released_at DESC",
            (card_id,),
        )
        return [Printing.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_primary_printing(self, card_id: int) -> Printing | None:
        """Get the best printing for image display.

        Prefers English, non-promo printings ordered by most recent release.

        Args:
            card_id: The card's database ID.

        Returns:
            The preferred Printing instance, or None if no printings exist.
        """
        cursor = self._db.execute(
            """
            SELECT * FROM printings
            WHERE card_id = ?
            ORDER BY
                CASE WHEN lang = 'en' THEN 0 ELSE 1 END ASC,
                CASE WHEN is_promo = 0 THEN 0 ELSE 1 END ASC,
                released_at DESC,
                id ASC
            LIMIT 1
            """,
            (card_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Printing.from_db_row(dict(row))

    def bulk_insert_printings(self, printings: list[Printing]) -> int:
        """Insert multiple printings in a single transaction.

        Uses INSERT OR IGNORE to skip duplicates (by scryfall_id).

        Args:
            printings: List of Printing instances to insert.

        Returns:
            Number of printings actually inserted.
        """
        rows = [p.to_db_row() for p in printings]
        cursor = self._db.executemany(
            """
            INSERT OR IGNORE INTO printings (
                scryfall_id, card_id, set_code, collector_number, lang,
                rarity, finishes, tcgplayer_id, cardmarket_id,
                released_at, is_promo, is_reprint
            ) VALUES (
                :scryfall_id, :card_id, :set_code, :collector_number, :lang,
                :rarity, :finishes, :tcgplayer_id, :cardmarket_id,
                :released_at, :is_promo, :is_reprint
            )
            """,
            rows,
        )
        self._db.commit()
        return cursor.rowcount
