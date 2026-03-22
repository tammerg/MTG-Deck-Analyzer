"""Tests for the advise service module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.services.advise_service import AdviseService


class TestAdviseService:
    def test_no_api_key_fallback(self):
        """Should return fallback message when no API key is set."""
        service = AdviseService(api_key=None)
        analysis = DeckAnalysis()

        with patch.dict("os.environ", {}, clear=True):
            result = service.get_advice(analysis, "How can I improve my deck?")

        assert "ANTHROPIC_API_KEY" in result

    def test_with_explicit_api_key_mocked(self):
        """Should call the LLM advisor with the provided API key."""
        service = AdviseService(api_key="test-key")
        analysis = DeckAnalysis(
            avg_cmc=3.0,
            power_level=5,
            category_breakdown={"ramp": 8, "card_draw": 6},
        )

        with patch(
            "mtg_deck_maker.services.advise_service.get_deck_advice",
            return_value="Add more card draw sources.",
        ) as mock_advice:
            result = service.get_advice(analysis, "I run out of cards too fast")

        assert result == "Add more card draw sources."
        mock_advice.assert_called_once_with(
            deck_analysis=analysis,
            question="I run out of cards too fast",
            api_key="test-key",
            provider=None,
        )
