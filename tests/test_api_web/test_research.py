"""Tests for the research endpoint with mocked LLM provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestResearch:
    def test_research_with_mocked_provider(self, client: TestClient) -> None:
        """Research endpoint returns structured result when LLM is available."""
        mock_result = MagicMock()
        mock_result.commander_name = "Atraxa, Praetors' Voice"
        mock_result.strategy_overview = "Proliferate everything."
        mock_result.key_cards = ["Doubling Season", "Contagion Engine"]
        mock_result.budget_staples = ["Sol Ring", "Arcane Signet"]
        mock_result.combos = ["Infinite Proliferate Combo"]
        mock_result.win_conditions = ["Poison Counters"]
        mock_result.cards_to_avoid = ["Bad Card"]
        mock_result.parse_success = True

        with (
            patch(
                "mtg_deck_maker.advisor.llm_provider.get_provider"
            ) as mock_get_provider,
            patch(
                "mtg_deck_maker.services.research_service.ResearchService"
            ) as MockService,
            patch(
                "mtg_deck_maker.api.web.routers.research.get_provider"
            ) as router_get_provider,
            patch(
                "mtg_deck_maker.api.web.routers.research.ResearchService"
            ) as RouterMockService,
        ):
            mock_llm = MagicMock()
            router_get_provider.return_value = mock_llm
            RouterMockService.return_value.research_commander.return_value = mock_result

            resp = client.post(
                "/api/research",
                json={"commander": "Atraxa, Praetors' Voice", "provider": "auto"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["commander_name"] == "Atraxa, Praetors' Voice"
        assert data["strategy_overview"] == "Proliferate everything."
        assert "Doubling Season" in data["key_cards"]
        assert data["parse_success"] is True

    def test_research_no_provider_returns_503(self, client: TestClient) -> None:
        """Research endpoint returns 503 when no LLM provider is available."""
        with patch(
            "mtg_deck_maker.api.web.routers.research.get_provider"
        ) as mock_get_provider:
            mock_get_provider.return_value = None

            resp = client.post(
                "/api/research",
                json={"commander": "Atraxa, Praetors' Voice"},
            )

        assert resp.status_code == 503

    def test_research_with_budget(self, client: TestClient) -> None:
        """Research endpoint passes budget to the research service."""
        mock_result = MagicMock()
        mock_result.commander_name = "Atraxa, Praetors' Voice"
        mock_result.strategy_overview = "Budget strategy."
        mock_result.key_cards = []
        mock_result.budget_staples = ["Sol Ring"]
        mock_result.combos = []
        mock_result.win_conditions = []
        mock_result.cards_to_avoid = []
        mock_result.parse_success = True

        with (
            patch(
                "mtg_deck_maker.api.web.routers.research.get_provider"
            ) as mock_get_provider,
            patch(
                "mtg_deck_maker.api.web.routers.research.ResearchService"
            ) as MockService,
        ):
            mock_llm = MagicMock()
            mock_get_provider.return_value = mock_llm
            MockService.return_value.research_commander.return_value = mock_result

            resp = client.post(
                "/api/research",
                json={
                    "commander": "Atraxa, Praetors' Voice",
                    "budget": 75.0,
                },
            )

        assert resp.status_code == 200
        # Verify budget was passed
        call_kwargs = MockService.return_value.research_commander.call_args
        assert call_kwargs.kwargs.get("budget") == 75.0
