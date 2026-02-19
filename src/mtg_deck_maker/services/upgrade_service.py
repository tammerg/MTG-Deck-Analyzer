"""Upgrade service orchestrating deck analysis and upgrade recommendation.

Provides a high-level interface for generating upgrade recommendations
from a deck file through to a sorted list of UpgradeRecommendation objects.
"""

from __future__ import annotations

from mtg_deck_maker.advisor.analyzer import DeckAnalysis, analyze_deck
from mtg_deck_maker.advisor.upgrade import (
    UpgradeRecommendation,
    recommend_upgrades,
)
from mtg_deck_maker.engine.categories import bulk_categorize
from mtg_deck_maker.models.card import Card


class UpgradeService:
    """Orchestrates the deck upgrade recommendation pipeline.

    Flow: analyze deck -> identify weaknesses -> recommend upgrades -> report.
    """

    def recommend_from_cards(
        self,
        deck_cards: list[Card],
        card_pool: list[Card],
        prices: dict[str, float],
        budget: float = 50.0,
        commander: Card | None = None,
        focus: str | None = None,
    ) -> tuple[DeckAnalysis, list[UpgradeRecommendation]]:
        """Generate upgrade recommendations for a deck.

        Args:
            deck_cards: Current deck Card objects.
            card_pool: Available replacement Card objects.
            prices: Dict mapping card name to price in USD.
            budget: Total budget for upgrades in USD.
            commander: Optional commander card for synergy scoring.
            focus: Optional category to prioritize.

        Returns:
            Tuple of (DeckAnalysis, list of UpgradeRecommendation).
        """
        categories = bulk_categorize(deck_cards)
        analysis = analyze_deck(deck_cards, categories)

        recommendations = recommend_upgrades(
            deck_cards=deck_cards,
            budget=budget,
            card_pool=card_pool,
            categories=categories,
            prices=prices,
            commander=commander,
            focus=focus,
        )

        return analysis, recommendations
