"""Tests for deck build, list, get, delete, export, and analyze endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _build_minimal_deck(client: TestClient) -> dict:
    """Helper to build and return a minimal test deck."""
    # We need a large enough card pool to build a Commander deck.
    # Since the seeded DB only has 3 cards, we mock BuildService.
    fake_deck_data = {
        "commander": "Atraxa, Praetors' Voice",
        "budget": 100.0,
        "seed": 42,
    }
    with patch(
        "mtg_deck_maker.api.web.routers.decks.BuildService"
    ) as MockBuildService:
        from mtg_deck_maker.models.deck import Deck, DeckCard

        # Build a minimal Deck with commander + one card
        search_resp = client.get("/api/cards/search?q=Atraxa")
        cmd_id = search_resp.json()["results"][0]["id"]
        sol_resp = client.get("/api/cards/search?q=Sol Ring")
        sol_id = sol_resp.json()["results"][0]["id"]

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
            ),
            DeckCard(
                card_id=sol_id,
                quantity=1,
                category="ramp",
                is_commander=False,
                card_name="Sol Ring",
                cmc=1.0,
                colors=[],
                price=2.00,
            ),
        ]

        mock_result = MagicMock()
        mock_result.deck = fake_deck
        MockBuildService.return_value.build_from_db.return_value = mock_result

        resp = client.post("/api/decks/build", json=fake_deck_data)
    return resp


class TestBuildDeck:
    def test_build_returns_201(self, client: TestClient) -> None:
        resp = _build_minimal_deck(client)
        assert resp.status_code == 201

    def test_build_returns_deck_response(self, client: TestClient) -> None:
        resp = _build_minimal_deck(client)
        data = resp.json()
        assert "id" in data
        assert data["name"] == "Atraxa, Praetors' Voice Commander"
        assert data["format"] == "commander"

    def test_build_unknown_commander_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={"commander": "Nonexistent Card", "budget": 100.0},
        )
        assert resp.status_code == 404

    def test_build_deck_has_cards(self, client: TestClient) -> None:
        resp = _build_minimal_deck(client)
        data = resp.json()
        assert len(data["cards"]) >= 1

    def test_build_deck_has_commanders_list(self, client: TestClient) -> None:
        resp = _build_minimal_deck(client)
        data = resp.json()
        assert len(data["commanders"]) >= 1
        assert all(c["is_commander"] for c in data["commanders"])


class TestListDecks:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/decks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_after_build(self, client: TestClient) -> None:
        _build_minimal_deck(client)
        resp = client.get("/api/decks")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestGetDeck:
    def test_get_existing_deck(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.get(f"/api/decks/{deck_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == deck_id

    def test_get_nonexistent_deck_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/decks/99999")
        assert resp.status_code == 404


class TestDeleteDeck:
    def test_delete_existing_deck(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        delete_resp = client.delete(f"/api/decks/{deck_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = client.get(f"/api/decks/{deck_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_deck_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/decks/99999")
        assert resp.status_code == 404


class TestExportDeck:
    def test_export_csv(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.post(f"/api/decks/{deck_id}/export", json={"format": "csv"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "csv"
        assert "content" in data

    def test_export_moxfield(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.post(
            f"/api/decks/{deck_id}/export", json={"format": "moxfield"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "moxfield"

    def test_export_archidekt(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.post(
            f"/api/decks/{deck_id}/export", json={"format": "archidekt"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "archidekt"

    def test_export_nonexistent_deck_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/decks/99999/export", json={"format": "csv"})
        assert resp.status_code == 404


class TestAnalyzeDeck:
    def test_analyze_deck(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.post(f"/api/decks/{deck_id}/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert "category_breakdown" in data
        assert "avg_cmc" in data
        assert "power_level" in data
        assert "recommendations" in data

    def test_analyze_nonexistent_deck_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/decks/99999/analyze")
        assert resp.status_code == 404
