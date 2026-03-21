"""Combo repository for CRUD operations on the combos and combo_cards tables."""

from __future__ import annotations

import json

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.combo import Combo


class ComboRepository:
    """Data access layer for combo storage and lookup.

    Manages two tables:
    - ``combos``: stores combo metadata (id, result, color identity, etc.)
    - ``combo_cards``: normalized table mapping combo_id to individual card names
      for fast lookup.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_tables(self) -> None:
        """Create the combos and combo_cards tables if they do not exist."""
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS combos (
                id INTEGER PRIMARY KEY,
                combo_id TEXT UNIQUE NOT NULL,
                card_names_json TEXT NOT NULL,
                result TEXT NOT NULL,
                color_identity_json TEXT NOT NULL,
                prerequisite TEXT DEFAULT '',
                description TEXT DEFAULT ''
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS combo_cards (
                id INTEGER PRIMARY KEY,
                combo_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                FOREIGN KEY (combo_id) REFERENCES combos(combo_id)
                    ON DELETE CASCADE
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_combo_cards_card_name "
            "ON combo_cards(card_name)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_combo_cards_combo_id "
            "ON combo_cards(combo_id)"
        )
        self._db.commit()

    def upsert_combo(self, combo: Combo) -> None:
        """Insert or replace a combo record and its card associations.

        Args:
            combo: Combo instance to insert or update.
        """
        card_names_json = json.dumps(combo.card_names)
        color_identity_json = json.dumps(combo.color_identity)

        self._db.execute(
            """
            INSERT OR REPLACE INTO combos (
                combo_id, card_names_json, result,
                color_identity_json, prerequisite, description
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                combo.combo_id,
                card_names_json,
                combo.result,
                color_identity_json,
                combo.prerequisite,
                combo.description,
            ),
        )

        # Rebuild the combo_cards entries for this combo
        self._db.execute(
            "DELETE FROM combo_cards WHERE combo_id = ?",
            (combo.combo_id,),
        )
        for card_name in combo.card_names:
            self._db.execute(
                "INSERT INTO combo_cards (combo_id, card_name) VALUES (?, ?)",
                (combo.combo_id, card_name),
            )

        self._db.commit()

    def get_combos_for_card(self, card_name: str) -> list[Combo]:
        """Find all combos that include the specified card.

        Args:
            card_name: Exact card name to search for.

        Returns:
            List of Combo instances containing that card.
        """
        cursor = self._db.execute(
            """
            SELECT c.combo_id, c.card_names_json, c.result,
                   c.color_identity_json, c.prerequisite, c.description
            FROM combos c
            INNER JOIN combo_cards cc ON c.combo_id = cc.combo_id
            WHERE cc.card_name = ?
            """,
            (card_name,),
        )
        return [self._row_to_combo(dict(row)) for row in cursor.fetchall()]

    def get_combos_for_cards(self, card_names: list[str]) -> list[Combo]:
        """Find all combos where ANY of the given card names appear.

        Results are deduplicated by combo_id.

        Args:
            card_names: List of card names to search for.

        Returns:
            List of unique Combo instances matching any card name.
        """
        if not card_names:
            return []

        placeholders = ",".join("?" for _ in card_names)
        cursor = self._db.execute(
            f"""
            SELECT DISTINCT c.combo_id, c.card_names_json, c.result,
                   c.color_identity_json, c.prerequisite, c.description
            FROM combos c
            INNER JOIN combo_cards cc ON c.combo_id = cc.combo_id
            WHERE cc.card_name IN ({placeholders})
            """,
            tuple(card_names),
        )
        return [self._row_to_combo(dict(row)) for row in cursor.fetchall()]

    def get_combo_partners(self, card_name: str) -> list[str]:
        """Return all card names that form combos with the given card.

        Does not include the given card itself in the results.

        Args:
            card_name: Card name to find partners for.

        Returns:
            List of unique partner card names.
        """
        cursor = self._db.execute(
            """
            SELECT DISTINCT cc2.card_name
            FROM combo_cards cc1
            INNER JOIN combo_cards cc2 ON cc1.combo_id = cc2.combo_id
            WHERE cc1.card_name = ? AND cc2.card_name != ?
            """,
            (card_name, card_name),
        )
        return [row["card_name"] for row in cursor.fetchall()]

    def count(self) -> int:
        """Return the total number of combos stored.

        Returns:
            Integer count of combo records.
        """
        cursor = self._db.execute("SELECT COUNT(*) as cnt FROM combos")
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    @staticmethod
    def _row_to_combo(row: dict) -> Combo:
        """Convert a database row dict to a Combo instance.

        Args:
            row: Dict with combo table column values.

        Returns:
            Combo instance.
        """
        return Combo(
            combo_id=row["combo_id"],
            card_names=json.loads(row["card_names_json"]),
            result=row["result"],
            color_identity=json.loads(row["color_identity_json"]),
            prerequisite=row.get("prerequisite", ""),
            description=row.get("description", ""),
        )
