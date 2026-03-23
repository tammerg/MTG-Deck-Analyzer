"""LLM synergy cache repository for persisting pairwise synergy scores."""

from __future__ import annotations

from datetime import datetime, timezone

from mtg_deck_maker.db.database import Database


class LLMSynergyRepo:
    """Data access layer for cached LLM-generated pairwise synergy scores.

    Stores synergy scores keyed by (commander_name, card_a, card_b) where
    card names are canonically ordered (alphabetical) to avoid duplicates.

    Attributes:
        _db: The Database instance for SQL execution.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_tables(self) -> None:
        """Create the llm_synergy_cache table if it does not exist."""
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_synergy_cache (
                id INTEGER PRIMARY KEY,
                commander_name TEXT NOT NULL,
                card_a TEXT NOT NULL,
                card_b TEXT NOT NULL,
                score REAL NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(commander_name, card_a, card_b, model)
            )
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llm_synergy_commander
            ON llm_synergy_cache(commander_name, model)
            """
        )
        self._db.commit()

    def get_cached_matrix(
        self,
        commander: str,
        card_names: list[str],
        model: str,
    ) -> dict[tuple[str, str], float]:
        """Retrieve cached synergy scores for a commander and set of cards.

        Only returns scores where both cards are in the provided card_names list.

        Args:
            commander: The commander name.
            card_names: List of card names to filter by.
            model: The LLM model name used to generate scores.

        Returns:
            Dict mapping (card_a, card_b) -> score for cached entries.
        """
        if not card_names:
            return {}

        # Query all scores for this commander+model
        cursor = self._db.execute(
            "SELECT card_a, card_b, score FROM llm_synergy_cache "
            "WHERE commander_name = ? AND model = ?",
            (commander, model),
        )

        name_set = set(card_names)
        result: dict[tuple[str, str], float] = {}
        for row in cursor.fetchall():
            a, b = row["card_a"], row["card_b"]
            if a in name_set and b in name_set:
                result[(a, b)] = float(row["score"])

        return result

    def upsert_scores(
        self,
        commander: str,
        scores: dict[tuple[str, str], float],
        model: str,
    ) -> None:
        """Insert or update synergy scores in the cache.

        Args:
            commander: The commander name.
            scores: Dict mapping (card_a, card_b) -> score.
                Keys must be canonically ordered (alphabetical).
            model: The LLM model name.
        """
        if not scores:
            return

        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (commander, card_a, card_b, score, model, now)
            for (card_a, card_b), score in scores.items()
        ]
        self._db.executemany(
            """
            INSERT OR REPLACE INTO llm_synergy_cache
            (commander_name, card_a, card_b, score, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._db.commit()

    def has_data(self, commander: str, model: str) -> bool:
        """Check if any synergy data is cached for a commander+model.

        Args:
            commander: The commander name.
            model: The LLM model name.

        Returns:
            True if data exists.
        """
        cursor = self._db.execute(
            "SELECT COUNT(*) as cnt FROM llm_synergy_cache "
            "WHERE commander_name = ? AND model = ?",
            (commander, model),
        )
        row = cursor.fetchone()
        return row is not None and int(row["cnt"]) > 0

    def count_pairs(self, commander: str, model: str) -> int:
        """Count cached synergy pairs for a commander+model.

        Args:
            commander: The commander name.
            model: The LLM model name.

        Returns:
            Number of cached pairs.
        """
        cursor = self._db.execute(
            "SELECT COUNT(*) as cnt FROM llm_synergy_cache "
            "WHERE commander_name = ? AND model = ?",
            (commander, model),
        )
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    def delete_commander(self, commander: str) -> int:
        """Delete all cached data for a commander.

        Args:
            commander: The commander name.

        Returns:
            Number of rows deleted.
        """
        cursor = self._db.execute(
            "DELETE FROM llm_synergy_cache WHERE commander_name = ?",
            (commander,),
        )
        self._db.commit()
        return cursor.rowcount
