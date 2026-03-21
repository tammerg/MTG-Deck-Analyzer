"""EDHREC data repository for per-commander card inclusion caching."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData


class EdhrecRepository:
    """Data access layer for cached EDHREC per-commander card data.

    Stores card inclusion rates, synergy scores, and deck counts
    keyed by (commander_name, card_name). Data is timestamped to
    support staleness checks for re-fetching.

    Attributes:
        _db: The Database instance for SQL execution.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_tables(self) -> None:
        """Create the edhrec_commander_cards table if it does not exist."""
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS edhrec_commander_cards (
                id INTEGER PRIMARY KEY,
                commander_name TEXT NOT NULL,
                card_name TEXT NOT NULL,
                inclusion_rate REAL NOT NULL,
                num_decks INTEGER NOT NULL,
                potential_decks INTEGER NOT NULL,
                synergy_score REAL DEFAULT 0.0,
                fetched_at TEXT NOT NULL,
                UNIQUE(commander_name, card_name)
            )
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_edhrec_commander
            ON edhrec_commander_cards(commander_name)
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_edhrec_card
            ON edhrec_commander_cards(card_name)
            """
        )
        self._db.commit()

    def upsert_data(self, data: list[EdhrecCommanderData]) -> None:
        """Insert or update EDHREC data records.

        Uses INSERT OR REPLACE to upsert based on the
        (commander_name, card_name) unique constraint.

        Args:
            data: List of EdhrecCommanderData to store.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                d.commander_name,
                d.card_name,
                d.inclusion_rate,
                d.num_decks,
                d.potential_decks,
                d.synergy_score,
                now,
            )
            for d in data
        ]
        self._db.executemany(
            """
            INSERT OR REPLACE INTO edhrec_commander_cards (
                commander_name, card_name, inclusion_rate,
                num_decks, potential_decks, synergy_score, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._db.commit()

    def get_card_inclusion(
        self, commander_name: str, card_name: str
    ) -> float | None:
        """Get the inclusion rate for a specific card under a commander.

        Args:
            commander_name: The commander to look up.
            card_name: The card to look up.

        Returns:
            The inclusion rate (0.0 to 1.0), or None if not found.
        """
        cursor = self._db.execute(
            "SELECT inclusion_rate FROM edhrec_commander_cards "
            "WHERE commander_name = ? AND card_name = ?",
            (commander_name, card_name),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return float(row["inclusion_rate"])

    def get_top_cards(
        self, commander_name: str, limit: int = 100
    ) -> list[EdhrecCommanderData]:
        """Get the top cards by inclusion rate for a commander.

        Args:
            commander_name: The commander to look up.
            limit: Maximum number of cards to return.

        Returns:
            List of EdhrecCommanderData sorted by inclusion rate descending.
        """
        cursor = self._db.execute(
            "SELECT * FROM edhrec_commander_cards "
            "WHERE commander_name = ? "
            "ORDER BY inclusion_rate DESC LIMIT ?",
            (commander_name, limit),
        )
        results: list[EdhrecCommanderData] = []
        for row in cursor.fetchall():
            results.append(
                EdhrecCommanderData(
                    commander_name=row["commander_name"],
                    card_name=row["card_name"],
                    inclusion_rate=float(row["inclusion_rate"]),
                    num_decks=int(row["num_decks"]),
                    potential_decks=int(row["potential_decks"]),
                    synergy_score=float(row["synergy_score"]),
                )
            )
        return results

    def has_data(self, commander_name: str) -> bool:
        """Check if any EDHREC data is cached for a commander.

        Args:
            commander_name: The commander to check.

        Returns:
            True if data exists, False otherwise.
        """
        cursor = self._db.execute(
            "SELECT COUNT(*) as cnt FROM edhrec_commander_cards "
            "WHERE commander_name = ?",
            (commander_name,),
        )
        row = cursor.fetchone()
        return row is not None and int(row["cnt"]) > 0

    def count_commanders(self) -> int:
        """Count the number of distinct commanders with cached data.

        Returns:
            Number of distinct commanders.
        """
        cursor = self._db.execute(
            "SELECT COUNT(DISTINCT commander_name) as cnt "
            "FROM edhrec_commander_cards"
        )
        row = cursor.fetchone()
        if row is None:
            return 0
        return int(row["cnt"])

    def is_stale(
        self, commander_name: str, max_age_days: int = 30
    ) -> bool:
        """Check if cached data for a commander is older than max_age_days.

        Returns True if no data exists or if the oldest record is
        older than the specified threshold.

        Args:
            commander_name: The commander to check.
            max_age_days: Maximum age in days before data is stale.

        Returns:
            True if data is stale or missing, False if fresh.
        """
        cursor = self._db.execute(
            "SELECT MIN(fetched_at) as oldest FROM edhrec_commander_cards "
            "WHERE commander_name = ?",
            (commander_name,),
        )
        row = cursor.fetchone()
        if row is None or row["oldest"] is None:
            return True

        oldest_str = row["oldest"]
        try:
            oldest = datetime.fromisoformat(oldest_str)
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return True

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        return oldest < cutoff
