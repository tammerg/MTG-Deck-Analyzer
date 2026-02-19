"""Tests for the LLM advisor module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.advisor.llm_advisor import (
    _build_context,
    get_deck_advice,
)


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


# === get_deck_advice ===


class TestGetDeckAdvice:
    def test_no_api_key(self):
        """Should return fallback message when no API key is available."""
        with patch.dict("os.environ", {}, clear=True):
            result = get_deck_advice(DeckAnalysis(), "Help!", api_key=None)
        assert "ANTHROPIC_API_KEY" in result

    def test_env_api_key_used(self):
        """Should use ANTHROPIC_API_KEY from environment."""
        mock_content = MagicMock()
        mock_content.text = "Use more removal spells."

        mock_message = MagicMock()
        mock_message.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}),
            patch(
                "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
                mock_anthropic,
            ),
        ):
            result = get_deck_advice(
                DeckAnalysis(), "What removal should I add?"
            )

        assert result == "Use more removal spells."
        mock_anthropic.Anthropic.assert_called_once_with(api_key="env-key")

    def test_explicit_api_key(self):
        """Should use the explicitly provided API key."""
        mock_content = MagicMock()
        mock_content.text = "Good deck!"

        mock_message = MagicMock()
        mock_message.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch(
            "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
            mock_anthropic,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Rate my deck", api_key="explicit-key"
            )

        assert result == "Good deck!"
        mock_anthropic.Anthropic.assert_called_once_with(
            api_key="explicit-key"
        )

    def test_rate_limit_handling(self):
        """Should handle rate limit errors gracefully."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception(
            "Error code: 429 rate_limit_exceeded"
        )
        mock_anthropic.Anthropic.return_value = mock_client

        with patch(
            "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
            mock_anthropic,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Help", api_key="test-key"
            )

        assert "rate limit" in result.lower()

    def test_generic_error_handling(self):
        """Should handle generic API errors gracefully."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception(
            "Connection refused"
        )
        mock_anthropic.Anthropic.return_value = mock_client

        with patch(
            "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
            mock_anthropic,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Help", api_key="test-key"
            )

        assert "Failed to get LLM advice" in result
        assert "Connection refused" in result

    def test_empty_response_handling(self):
        """Should handle empty API response."""
        mock_anthropic = MagicMock()
        mock_message = MagicMock()
        mock_message.content = []

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client

        with patch(
            "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
            mock_anthropic,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Help", api_key="test-key"
            )

        assert "no response" in result.lower()

    def test_anthropic_not_installed(self):
        """Should handle missing anthropic package."""
        with patch(
            "mtg_deck_maker.advisor.llm_advisor._anthropic_module",
            None,
        ):
            result = get_deck_advice(
                DeckAnalysis(), "Help", api_key="test-key"
            )

        assert "anthropic" in result.lower()
