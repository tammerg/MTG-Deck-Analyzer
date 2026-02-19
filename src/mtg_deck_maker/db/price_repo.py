"""Price repository for CRUD operations on the prices table."""

from __future__ import annotations

from datetime import datetime, timezone

from mtg_deck_maker.db.database import Database


class PriceRepository:
    """Data access layer for the prices table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_price(
        self,
        printing_id: int,
        source: str,
        price: float,
        currency: str = "USD",
        finish: str = "nonfoil",
        retrieved_at: str | None = None,
    ) -> int:
        """Insert a price record.

        Args:
            printing_id: The printing's database ID.
            source: Price source (scryfall, tcgplayer, cardmarket, justtcg).
            price: The price value.
            currency: Currency code (default USD).
            finish: Card finish (nonfoil, foil, etched).
            retrieved_at: ISO timestamp. Defaults to now.

        Returns:
            The database ID of the inserted price record.
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(timezone.utc).isoformat()

        cursor = self._db.execute(
            """
            INSERT INTO prices (
                printing_id, source, currency, price, finish, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (printing_id, source, currency, price, finish, retrieved_at),
        )
        self._db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_latest_price(
        self,
        printing_id: int,
        source: str,
        currency: str = "USD",
        finish: str = "nonfoil",
    ) -> float | None:
        """Get the most recent price for a specific printing/source/finish.

        Args:
            printing_id: The printing's database ID.
            source: Price source to filter by.
            currency: Currency to filter by.
            finish: Finish to filter by.

        Returns:
            The price value, or None if no price exists.
        """
        cursor = self._db.execute(
            """
            SELECT price FROM prices
            WHERE printing_id = ? AND source = ?
              AND currency = ? AND finish = ?
            ORDER BY retrieved_at DESC
            LIMIT 1
            """,
            (printing_id, source, currency, finish),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return float(row["price"]) if row["price"] is not None else None

    def get_cheapest_price(
        self,
        card_id: int,
        currency: str = "USD",
        finish: str = "nonfoil",
    ) -> float | None:
        """Get the cheapest current price for a card across all printings.

        Joins prices with printings to find the lowest price for any
        printing of the given card.

        Args:
            card_id: The card's database ID.
            currency: Currency to filter by.
            finish: Finish to filter by.

        Returns:
            The cheapest price value, or None if no price exists.
        """
        cursor = self._db.execute(
            """
            SELECT MIN(p.price) as min_price
            FROM prices p
            JOIN printings pr ON p.printing_id = pr.id
            WHERE pr.card_id = ?
              AND p.currency = ?
              AND p.finish = ?
              AND p.price IS NOT NULL
            """,
            (card_id, currency, finish),
        )
        row = cursor.fetchone()
        if row is None or row["min_price"] is None:
            return None
        return float(row["min_price"])

    def bulk_insert_prices(
        self,
        prices: list[dict],
    ) -> int:
        """Insert multiple price records in a single transaction.

        Each dict in the list should contain:
        - printing_id: int
        - source: str
        - price: float
        - currency: str (optional, defaults to USD)
        - finish: str (optional, defaults to nonfoil)
        - retrieved_at: str (optional, defaults to now)

        Args:
            prices: List of price record dicts.

        Returns:
            Number of records inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for p in prices:
            rows.append((
                p["printing_id"],
                p["source"],
                p.get("currency", "USD"),
                p["price"],
                p.get("finish", "nonfoil"),
                p.get("retrieved_at", now),
            ))

        cursor = self._db.executemany(
            """
            INSERT INTO prices (
                printing_id, source, currency, price, finish, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._db.commit()
        return cursor.rowcount

    def get_prices_newer_than(
        self, timestamp: str
    ) -> list[dict]:
        """Get all price records newer than the given timestamp.

        Args:
            timestamp: ISO format timestamp to filter by.

        Returns:
            List of price record dicts with all fields.
        """
        cursor = self._db.execute(
            """
            SELECT p.id, p.printing_id, p.source, p.currency,
                   p.price, p.finish, p.retrieved_at
            FROM prices p
            WHERE p.retrieved_at > ?
            ORDER BY p.retrieved_at DESC
            """,
            (timestamp,),
        )
        return [
            {
                "id": row["id"],
                "printing_id": row["printing_id"],
                "source": row["source"],
                "currency": row["currency"],
                "price": row["price"],
                "finish": row["finish"],
                "retrieved_at": row["retrieved_at"],
            }
            for row in cursor.fetchall()
        ]
