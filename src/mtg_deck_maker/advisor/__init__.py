"""Deck advisor: analysis, upgrade recommendations, and LLM integration."""

from mtg_deck_maker.advisor.analyzer import DeckAnalysis, analyze_deck
from mtg_deck_maker.advisor.anthropic_provider import AnthropicProvider
from mtg_deck_maker.advisor.llm_advisor import get_deck_advice
from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider
from mtg_deck_maker.advisor.openai_provider import OpenAIProvider
from mtg_deck_maker.advisor.retry import RetryError, with_retries
from mtg_deck_maker.advisor.upgrade import (
    UpgradeRecommendation,
    recommend_upgrades,
)

__all__ = [
    "AnthropicProvider",
    "DeckAnalysis",
    "LLMProvider",
    "OpenAIProvider",
    "RetryError",
    "UpgradeRecommendation",
    "analyze_deck",
    "get_deck_advice",
    "get_provider",
    "recommend_upgrades",
    "with_retries",
]
