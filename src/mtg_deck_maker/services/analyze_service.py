"""Analyze service orchestrating deck import, categorization, and analysis.

Provides a high-level interface for analyzing a deck from a CSV file
through to a complete DeckAnalysis report.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mtg_deck_maker.advisor.analyzer import DeckAnalysis, analyze_deck
from mtg_deck_maker.engine.categories import bulk_categorize
from mtg_deck_maker.io.csv_import import ImportResult, import_deck_from_csv
from mtg_deck_maker.models.card import Card

if TYPE_CHECKING:
    from mtg_deck_maker.db.card_repo import CardRepository

logger = logging.getLogger(__name__)


class AnalyzeService:
    """Orchestrates the deck analysis pipeline.

    Flow: import CSV -> build Card list -> categorize -> analyze -> report.
    """

    def analyze_from_csv(
        self,
        filepath: str,
        *,
        card_repo: CardRepository | None = None,
    ) -> DeckAnalysis:
        """Analyze a deck from a CSV file.

        When *card_repo* is provided each card name is looked up in the
        database so the analysis uses real oracle text, CMC, colours, and
        keywords.  When no repository is available hollow Card objects are
        used, which may silently produce inaccurate category and curve
        results; a warning is emitted in that case.

        Args:
            filepath: Path to the CSV/text deck file.
            card_repo: Optional ``CardRepository`` for database card lookups.
                When ``None`` the service creates lightweight placeholder Card
                objects and logs a warning about reduced accuracy.

        Returns:
            DeckAnalysis with complete metrics and recommendations.

        Raises:
            ValueError: If the file cannot be parsed or contains errors.
        """
        import_result = import_deck_from_csv(filepath)

        if import_result.errors:
            raise ValueError(
                f"Import errors: {'; '.join(import_result.errors)}"
            )

        if not import_result.cards:
            raise ValueError("No cards found in the deck file.")

        if card_repo is None:
            logger.warning(
                "No database provided — analysis will use limited card data. "
                "Results may be inaccurate."
            )

        cards = self._build_card_list(import_result, card_repo=card_repo)
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        return analysis

    def analyze_from_cards(self, cards: list[Card]) -> DeckAnalysis:
        """Analyze a deck from an existing list of Card objects.

        Args:
            cards: List of Card objects to analyze.

        Returns:
            DeckAnalysis with complete metrics and recommendations.
        """
        if not cards:
            return DeckAnalysis()

        categories = bulk_categorize(cards)
        return analyze_deck(cards, categories)

    def _build_card_list(
        self,
        import_result: ImportResult,
        *,
        card_repo: CardRepository | None = None,
    ) -> list[Card]:
        """Convert ImportResult entries into Card objects.

        When *card_repo* is supplied each card name is resolved against the
        database.  Cards that are not found (or when no repository is given)
        fall back to a lightweight placeholder with empty oracle text and
        ``cmc=0.0``.

        Args:
            import_result: Parsed import data.
            card_repo: Optional repository for database card lookups.

        Returns:
            List of Card objects, one per card (quantity is expanded).
        """
        cards: list[Card] = []
        for idx, imported in enumerate(import_result.cards):
            resolved: Card | None = None
            if card_repo is not None:
                resolved = card_repo.get_card_by_name(imported.name)

            for _ in range(imported.quantity):
                if resolved is not None:
                    cards.append(resolved)
                else:
                    cards.append(Card(
                        oracle_id=f"imported-{idx}",
                        name=imported.name,
                        type_line="",
                        oracle_text="",
                        mana_cost="",
                        cmc=0.0,
                        colors=[],
                        color_identity=[],
                        keywords=[],
                    ))
        return cards
