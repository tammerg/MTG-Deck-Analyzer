"""Tests for the LLM advisor module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.advisor.llm_advisor import (
    _build_context,
    get_deck_advice,
)
from mtg_deck_maker.advisor.llm_provider import LLMProvider


# === Context Building ===


class TestBuildContext:
    def test_basic_context(self):
        """Context should include key analysis metrics."""
        analysis = DeckAnalysis(
            avg_cmc=3.2,
            power_level=6,
            total_price=150.0,
            category_breakdown={"ramp": 10, "card_draw": 8},
            mana_curve={0: 2, 1: 5, 2: 10, 3: 8, 4: 5, 5: 3, 6: 1, 7: 1},
        )
        context = _build_context(analysis)
        assert "3.20" in context
        assert "6/10" in context
        assert "$150.00" in context
        assert "ramp" in context

    def test_weak_categories_in_context(self):
        """Context should include weak categories."""
        analysis = DeckAnalysis(
            weak_categories=["ramp", "card_draw"],
        )
        context = _build_context(analysis)
        assert "Weak Areas" in context
        assert "ramp" in context
        assert "card_draw" in context

    def test_strong_categories_in_context(self):
        """Context should include strong categories."""
        analysis = DeckAnalysis(
            strong_categories=["removal"],
        )
        context = _build_context(analysis)
        assert "Strong Areas" in context
        assert "removal" in context

    def test_recommendations_in_context(self):
        """Context should include existing recommendations."""
        analysis = DeckAnalysis(
            recommendations=["Add more ramp", "Lower your curve"],
        )
        context = _build_context(analysis)
        assert "Add more ramp" in context
        assert "Lower your curve" in context

    def test_empty_analysis(self):
        """Context should handle empty analysis gracefully."""
        analysis = DeckAnalysis()
        context = _build_context(analysis)
        assert "Deck Analysis Context" in context


# === get_deck_advice with provider ===


class _FakeProvider(LLMProvider):
    """Fake LLM provider for testing."""

    def __init__(self, response: str = "") -> None:
        self._response = response

    def chat(self, messages, *, max_tokens=1024, temperature=0.7, timeout_s=60.0) -> str:
        return self._response

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "Fake"


class TestGetDeckAdviceWithProvider:
    def test_provider_used(self):
        """Should use the provided LLMProvider."""
        provider = _FakeProvider(response="Add more ramp sources.")
        result = get_deck_advice(
            DeckAnalysis(), "What do I need?", provider=provider
        )
        assert result == "Add more ramp sources."

    def test_provider_empty_response(self):
        """Should handle empty provider response."""
        provider = _FakeProvider(response="")
        result = get_deck_advice(
            DeckAnalysis(), "Help", provider=provider
        )
        assert "no response" in result.lower()

    def test_provider_rate_limit(self):
        """Should handle rate limit from provider."""
        provider = MagicMock(spec=LLMProvider)
        provider.chat.side_effect = Exception("429 rate_limit")
        result = get_deck_advice(
            DeckAnalysis(), "Help", provider=provider
        )
        assert "rate limit" in result.lower()

    def test_provider_generic_error(self):
        """Should handle generic error from provider."""
        provider = MagicMock(spec=LLMProvider)
        provider.chat.side_effect = Exception("Connection refused")
        result = get_deck_advice(
            DeckAnalysis(), "Help", provider=provider
        )
        assert "Failed to get LLM advice" in result


# === get_deck_advice legacy path ===


class TestGetDeckAdviceNoProvider:
    """Tests for the fallback path when no LLM provider is available."""

    def test_no_provider_returns_fallback(self):
        """Should return fallback message when no provider is available."""
        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            return_value=None,
        ):
            result = get_deck_advice(DeckAnalysis(), "Help!", api_key=None)
        assert "ANTHROPIC_API_KEY" in result

    def test_explicit_api_key_ignored_without_provider(self):
        """api_key param is ignored; only the provider abstraction matters."""
        with patch(
            "mtg_deck_maker.advisor.llm_provider.get_provider",
            return_value=None,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Help", api_key="explicit-key"
            )
        assert "ANTHROPIC_API_KEY" in result
