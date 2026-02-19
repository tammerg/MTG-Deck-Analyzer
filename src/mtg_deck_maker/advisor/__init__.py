"""Deck advisor: analysis, upgrade recommendations, and LLM integration."""

from mtg_deck_maker.advisor.analyzer import DeckAnalysis, analyze_deck
from mtg_deck_maker.advisor.upgrade import (
    UpgradeRecommendation,
    recommend_upgrades,
)
from mtg_deck_maker.advisor.llm_advisor import get_deck_advice

__all__ = [
    "DeckAnalysis",
    "analyze_deck",
    "UpgradeRecommendation",
    "recommend_upgrades",
    "get_deck_advice",
]
