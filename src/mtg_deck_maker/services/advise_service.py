"""Advise service wrapping the LLM advisor for deck consultation.

Provides a high-level interface for getting AI-powered deck advice
combining deck analysis context with user questions.
"""

from __future__ import annotations

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.advisor.llm_advisor import get_deck_advice
from mtg_deck_maker.advisor.llm_provider import LLMProvider


class AdviseService:
    """Wraps the LLM advisor with service-level orchestration."""

    def __init__(
        self,
        api_key: str | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        """Initialize the advise service.

        Args:
            api_key: Optional API key (deprecated, kept for compat).
            provider: Optional LLMProvider instance. If None, the advisor
                will auto-detect an available provider.
        """
        self._api_key = api_key
        self._provider = provider

    def get_advice(
        self,
        deck_analysis: DeckAnalysis,
        question: str,
    ) -> str:
        """Get AI-powered advice for a deck.

        Args:
            deck_analysis: Analyzed deck data.
            question: The user's question or problem description.

        Returns:
            Text response with deck advice.
        """
        return get_deck_advice(
            deck_analysis=deck_analysis,
            question=question,
            api_key=self._api_key,
            provider=self._provider,
        )
