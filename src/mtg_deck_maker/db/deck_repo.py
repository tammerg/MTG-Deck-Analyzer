"""Deck repository for CRUD operations on the decks and deck_cards tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.deck import Deck, DeckCard


@dataclass
class DeckSummary:
    """Lightweight deck summary returned by list_decks_summary().

    Contains only metadata and aggregated statistics; no per-card data.
    """

    id: int
    name: str
    format: str
    budget_target: float
    created_at: str
    total_cards: int
    total_price: float
    commander_names: list[str] = field(default_factory=list)


class DeckRepository:
    """Data access layer for the decks and deck_cards tables."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_deck(self, deck: Deck) -> int:
        """Persist a deck and all its cards to the database.

        Inserts a row into the decks table and then inserts each
        DeckCard into deck_cards. Sets deck.id on the provided Deck
        object before returning.

        Args:
            deck: Deck instance to persist. Must have cards populated.

        Returns:
            The database ID of the newly created deck.
        """
        created_at = deck.created_at or datetime.now(timezone.utc).isoformat()

        cursor = self._db.execute(
            """
            INSERT INTO decks (name, format, budget_target, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (deck.name, deck.format, deck.budget_target, created_at),
        )
        deck_id = cursor.lastrowid

        card_rows = [
            (
                deck_id,
                dc.card_id,
                dc.quantity,
                dc.category,
                int(dc.is_commander),
                int(dc.is_companion),
            )
            for dc in deck.cards
        ]
        self._db.executemany(
            """
            INSERT INTO deck_cards
                (deck_id, card_id, quantity, category, is_commander, is_companion)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            card_rows,
        )

        self._db.commit()
        return deck_id  # type: ignore[return-value]

    def get_deck(self, deck_id: int) -> Deck | None:
        """Retrieve a deck by its primary key, including all cards.

        Args:
            deck_id: The database primary key for the deck.

        Returns:
            Deck instance with cards populated, or None if not found.
        """
        cursor = self._db.execute(
            "SELECT * FROM decks WHERE id = ?", (deck_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        deck = Deck(
            id=row["id"],
            name=row["name"],
            format=row["format"],
            budget_target=row["budget_target"],
            created_at=row["created_at"],
        )

        cursor = self._db.execute(
            """
            SELECT dc.card_id, dc.quantity, dc.category,
                   dc.is_commander, dc.is_companion,
                   c.name as card_name, c.cmc, c.colors,
                   c.mana_cost, c.type_line, c.oracle_text
            FROM deck_cards dc
            JOIN cards c ON dc.card_id = c.id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_commander DESC, dc.category, c.name
            """,
            (deck_id,),
        )

        for dc_row in cursor.fetchall():
            colors_raw = dc_row["colors"] or ""
            colors = [c for c in colors_raw.split(",") if c]
            deck.cards.append(
                DeckCard(
                    card_id=dc_row["card_id"],
                    quantity=dc_row["quantity"],
                    category=dc_row["category"] or "",
                    is_commander=bool(dc_row["is_commander"]),
                    is_companion=bool(dc_row["is_companion"]),
                    card_name=dc_row["card_name"],
                    cmc=float(dc_row["cmc"] or 0.0),
                    colors=colors,
                )
            )

        return deck

    def list_decks(self) -> list[Deck]:
        """Return all decks (without cards loaded for efficiency).

        Cards are not populated here; use get_deck() to retrieve a
        specific deck with its full card list.

        Returns:
            List of Deck instances (cards list will be empty).
        """
        cursor = self._db.execute(
            "SELECT * FROM decks ORDER BY created_at DESC"
        )
        decks: list[Deck] = []
        for row in cursor.fetchall():
            decks.append(
                Deck(
                    id=row["id"],
                    name=row["name"],
                    format=row["format"],
                    budget_target=row["budget_target"],
                    created_at=row["created_at"],
                )
            )
        return decks

    def list_decks_summary(self) -> list[DeckSummary]:
        """Return summary rows for all decks using a single aggregated query.

        Joins deck_cards with cards (for names/is_commander flag), printings,
        and prices to compute total_cards and total_price per deck, and
        assembles pipe-separated commander names in one SQL pass.

        Returns:
            List of DeckSummary dataclasses ordered by created_at DESC.
            Each summary contains aggregated totals and commander_names;
            no per-card data is loaded.
        """
        # A single query aggregates totals across all decks.
        # total_price uses a correlated sub-select to get the cheapest price
        # per card (matching _deck_to_response semantics) without additional
        # round-trips. Commander names use '|||' as separator to avoid
        # splitting on the commas that appear in many MTG card names.
        cursor = self._db.execute(
            """
            SELECT
                d.id,
                d.name,
                d.format,
                COALESCE(d.budget_target, 0.0)  AS budget_target,
                d.created_at,
                COALESCE(SUM(dc.quantity), 0)   AS total_cards,
                COALESCE(
                    SUM(
                        dc.quantity * COALESCE(
                            (
                                SELECT MIN(p.price)
                                FROM prices p
                                JOIN printings pr ON p.printing_id = pr.id
                                WHERE pr.card_id = dc.card_id
                                  AND p.currency = 'USD'
                                  AND p.finish   = 'nonfoil'
                                  AND p.price IS NOT NULL
                            ),
                            0.0
                        )
                    ),
                    0.0
                ) AS total_price,
                GROUP_CONCAT(
                    CASE WHEN dc.is_commander = 1 THEN c.name ELSE NULL END,
                    '|||'
                ) AS commander_names_raw
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            LEFT JOIN cards c       ON c.id = dc.card_id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """
        )
        summaries: list[DeckSummary] = []
        for row in cursor.fetchall():
            raw = row["commander_names_raw"] or ""
            commander_names = [n for n in raw.split("|||") if n]
            summaries.append(
                DeckSummary(
                    id=row["id"],
                    name=row["name"],
                    format=row["format"],
                    budget_target=float(row["budget_target"]),
                    created_at=row["created_at"],
                    total_cards=int(row["total_cards"]),
                    total_price=round(float(row["total_price"]), 2),
                    commander_names=commander_names,
                )
            )
        return summaries

    def delete_deck(self, deck_id: int) -> bool:
        """Delete a deck and all its cards.

        Args:
            deck_id: The database primary key for the deck.

        Returns:
            True if the deck was deleted, False if it did not exist.
        """
        # Check existence first
        cursor = self._db.execute(
            "SELECT id FROM decks WHERE id = ?", (deck_id,)
        )
        if cursor.fetchone() is None:
            return False

        self._db.execute(
            "DELETE FROM deck_cards WHERE deck_id = ?", (deck_id,)
        )
        self._db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        self._db.commit()
        return True
