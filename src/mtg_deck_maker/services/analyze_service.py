"""Analyze service orchestrating deck import, categorization, and analysis.

Provides a high-level interface for analyzing a deck from a CSV file
through to a complete DeckAnalysis report.
"""

from __future__ import annotations

from mtg_deck_maker.advisor.analyzer import DeckAnalysis, analyze_deck
from mtg_deck_maker.engine.categories import bulk_categorize
from mtg_deck_maker.io.csv_import import ImportResult, import_deck_from_csv
from mtg_deck_maker.models.card import Card


class AnalyzeService:
    """Orchestrates the deck analysis pipeline.

    Flow: import CSV -> build Card list -> categorize -> analyze -> report.
    """

    def analyze_from_csv(self, filepath: str) -> DeckAnalysis:
        """Analyze a deck from a CSV file.

        Args:
            filepath: Path to the CSV/text deck file.

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

        cards = self._build_card_list(import_result)
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

    def _build_card_list(self, import_result: ImportResult) -> list[Card]:
        """Convert ImportResult cards to Card objects.

        Since we do not have a database lookup here, we create lightweight
        Card objects from the imported data. In a full implementation,
        this would resolve card names against the database.

        Args:
            import_result: Parsed import data.

        Returns:
            List of Card objects.
        """
        cards: list[Card] = []
        for idx, imported in enumerate(import_result.cards):
            for _ in range(imported.quantity):
                card = Card(
                    oracle_id=f"imported-{idx}",
                    name=imported.name,
                    type_line="",
                    oracle_text="",
                    mana_cost="",
                    cmc=0.0,
                    colors=[],
                    color_identity=[],
                    keywords=[],
                )
                cards.append(card)
        return cards
