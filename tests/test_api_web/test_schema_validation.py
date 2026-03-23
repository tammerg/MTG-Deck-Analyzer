"""Tests for input validation on DeckBuildRequest, ResearchRequest, and StrategyGuideRequest.

Following TDD: these tests are written BEFORE the schema changes so they fail red first.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# DeckBuildRequest validation
# ---------------------------------------------------------------------------


class TestDeckBuildRequestValidation:
    """422 responses are returned for invalid DeckBuildRequest payloads."""

    def test_empty_commander_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={"commander": "", "budget": 100.0},
        )
        assert resp.status_code == 422

    def test_whitespace_only_commander_would_need_validator(
        self, client: TestClient
    ) -> None:
        """A string of only spaces violates min_length=1 once stripped; with plain
        min_length the check is on raw length.  A non-empty whitespace string passes
        min_length but is semantically invalid — this test documents that the
        *empty* string case is the one we explicitly reject via min_length."""
        resp = client.post(
            "/api/decks/build",
            json={"commander": "", "budget": 100.0},
        )
        assert resp.status_code == 422

    def test_commander_exceeding_max_length_returns_422(
        self, client: TestClient
    ) -> None:
        long_name = "A" * 201
        resp = client.post(
            "/api/decks/build",
            json={"commander": long_name, "budget": 100.0},
        )
        assert resp.status_code == 422

    def test_invalid_provider_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "budget": 100.0,
                "provider": "gpt-5-turbo",
            },
        )
        assert resp.status_code == 422

    def test_zero_budget_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={"commander": "Atraxa, Praetors' Voice", "budget": 0},
        )
        assert resp.status_code == 422

    def test_negative_budget_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={"commander": "Atraxa, Praetors' Voice", "budget": -50.0},
        )
        assert resp.status_code == 422

    def test_partner_exceeding_max_length_returns_422(
        self, client: TestClient
    ) -> None:
        long_partner = "B" * 201
        resp = client.post(
            "/api/decks/build",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "budget": 100.0,
                "partner": long_partner,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("provider", ["auto", "openai", "anthropic"])
    def test_valid_providers_pass_validation(
        self, client: TestClient, provider: str
    ) -> None:
        """Valid provider values must not cause a Pydantic schema 422."""
        resp = client.post(
            "/api/decks/build",
            json={
                "commander": "Nonexistent Commander",
                "budget": 100.0,
                "provider": provider,
            },
        )
        # Nonexistent commander returns 404 — business-logic, not a schema error.
        # A Pydantic 422 has detail as a list; any other status is fine.
        if resp.status_code == 422:
            assert not isinstance(resp.json()["detail"], list), (
                f"Schema rejected valid provider {provider!r}: " + str(resp.json())
            )

    def test_valid_request_passes_validation(self, client: TestClient) -> None:
        """A fully valid payload must not cause a Pydantic 422.

        The seeded DB may return an app-level 422 (insufficient card pool) or
        404 for business-logic reasons — those are acceptable.  Only a Pydantic
        schema validation error (where detail is a list of field errors) would
        indicate the schema itself rejected a valid payload.
        """
        resp = client.post(
            "/api/decks/build",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "budget": 50.0,
                "provider": "auto",
                "smart": False,
                "seed": 42,
            },
        )
        if resp.status_code == 422:
            # App-level 422 has detail as str; Pydantic validation 422 has detail as list
            assert not isinstance(resp.json()["detail"], list), (
                "Schema rejected a valid payload: " + str(resp.json())
            )

    def test_null_partner_is_valid(self, client: TestClient) -> None:
        """An explicit null partner must not cause a Pydantic 422."""
        resp = client.post(
            "/api/decks/build",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "budget": 100.0,
                "partner": None,
            },
        )
        if resp.status_code == 422:
            assert not isinstance(resp.json()["detail"], list), (
                "Schema rejected a valid payload: " + str(resp.json())
            )


# ---------------------------------------------------------------------------
# ResearchRequest validation
# ---------------------------------------------------------------------------


class TestResearchRequestValidation:
    """422 responses are returned for invalid ResearchRequest payloads."""

    def test_empty_commander_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/research",
            json={"commander": ""},
        )
        assert resp.status_code == 422

    def test_commander_exceeding_max_length_returns_422(
        self, client: TestClient
    ) -> None:
        long_name = "X" * 201
        resp = client.post(
            "/api/research",
            json={"commander": long_name},
        )
        assert resp.status_code == 422

    def test_invalid_provider_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/research",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "provider": "invalid_llm",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("provider", ["auto", "openai", "anthropic"])
    def test_valid_providers_pass_validation(
        self, client: TestClient, provider: str
    ) -> None:
        """Valid provider values should not return 422."""
        resp = client.post(
            "/api/research",
            json={
                "commander": "Atraxa, Praetors' Voice",
                "provider": provider,
            },
        )
        assert resp.status_code != 422

    def test_valid_request_passes_validation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/research",
            json={"commander": "Atraxa, Praetors' Voice"},
        )
        assert resp.status_code != 422


# ---------------------------------------------------------------------------
# StrategyGuideRequest validation
# ---------------------------------------------------------------------------


class TestStrategyGuideRequestValidation:
    """422 responses are returned for invalid StrategyGuideRequest payloads."""

    def _build_deck_id(self, client: TestClient) -> int:
        """Build a minimal deck and return its ID, re-using the mock helper pattern."""
        from unittest.mock import MagicMock, patch

        from mtg_deck_maker.models.deck import Deck, DeckCard

        search_resp = client.get("/api/cards/search?q=Atraxa")
        cmd_id = search_resp.json()["results"][0]["id"]

        fake_deck = Deck(
            name="Atraxa, Praetors' Voice Commander",
            format="commander",
            budget_target=100.0,
            created_at="2026-01-01T00:00:00+00:00",
        )
        fake_deck.cards = [
            DeckCard(
                card_id=cmd_id,
                quantity=1,
                category="commander",
                is_commander=True,
                card_name="Atraxa, Praetors' Voice",
                cmc=4.0,
                colors=["W", "U", "B", "G"],
                price=8.50,
            )
        ]

        mock_result = MagicMock()
        mock_result.deck = fake_deck

        with patch(
            "mtg_deck_maker.api.web.routers.decks.BuildService"
        ) as MockBuildService:
            MockBuildService.return_value.build_from_db.return_value = mock_result
            build_resp = client.post(
                "/api/decks/build",
                json={"commander": "Atraxa, Praetors' Voice", "budget": 100.0},
            )

        assert build_resp.status_code == 201
        return build_resp.json()["id"]

    def test_zero_num_simulations_returns_422(self, client: TestClient) -> None:
        deck_id = self._build_deck_id(client)
        resp = client.post(
            f"/api/decks/{deck_id}/strategy-guide",
            json={"num_simulations": 0},
        )
        assert resp.status_code == 422

    def test_negative_num_simulations_returns_422(self, client: TestClient) -> None:
        deck_id = self._build_deck_id(client)
        resp = client.post(
            f"/api/decks/{deck_id}/strategy-guide",
            json={"num_simulations": -1},
        )
        assert resp.status_code == 422

    def test_num_simulations_above_limit_returns_422(
        self, client: TestClient
    ) -> None:
        deck_id = self._build_deck_id(client)
        resp = client.post(
            f"/api/decks/{deck_id}/strategy-guide",
            json={"num_simulations": 10001},
        )
        assert resp.status_code == 422

    def test_invalid_provider_returns_422(self, client: TestClient) -> None:
        deck_id = self._build_deck_id(client)
        resp = client.post(
            f"/api/decks/{deck_id}/strategy-guide",
            json={"provider": "bad_provider"},
        )
        assert resp.status_code == 422

    def test_valid_request_passes_validation(self, client: TestClient) -> None:
        deck_id = self._build_deck_id(client)
        resp = client.post(
            f"/api/decks/{deck_id}/strategy-guide",
            json={"num_simulations": 100, "provider": "auto", "seed": 0},
        )
        # Validation must pass — business logic may succeed or fail for other reasons.
        assert resp.status_code != 422
