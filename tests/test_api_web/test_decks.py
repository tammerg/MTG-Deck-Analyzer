"""Tests for deck build, list, get, delete, export, and analyze endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import Response


def _build_minimal_deck(client: TestClient) -> Response:
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
    def test_build_returns_complete_deck(self, client: TestClient) -> None:
        resp = _build_minimal_deck(client)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "Atraxa, Praetors' Voice Commander"
        assert data["format"] == "commander"
        assert len(data["cards"]) >= 1
        assert len(data["commanders"]) >= 1
        assert all(c["is_commander"] for c in data["commanders"])

    def test_build_unknown_commander_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/decks/build",
            json={"commander": "Nonexistent Card", "budget": 100.0},
        )
        assert resp.status_code == 404


class TestListDecks:
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
    @pytest.mark.parametrize(
        "fmt",
        ["csv", "moxfield", "archidekt"],
    )
    def test_export_formats(self, client: TestClient, fmt: str) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        resp = client.post(f"/api/decks/{deck_id}/export", json={"format": fmt})
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == fmt
        assert "content" in data

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


class TestUpgradeDeck:
    def test_upgrade_returns_recommendations(self, client: TestClient) -> None:
        build_resp = _build_minimal_deck(client)
        deck_id = build_resp.json()["id"]

        with patch(
            "mtg_deck_maker.services.upgrade_service.UpgradeService"
        ) as MockUpgradeService:
            from mtg_deck_maker.advisor.upgrade import UpgradeRecommendation
            from mtg_deck_maker.models.card import Card

            card_out = Card(
                id=1, oracle_id="a", name="Bad Card", type_line="Creature",
                oracle_text="", mana_cost="{3}", cmc=3.0, colors=["R"],
                color_identity=["R"], keywords=[], edhrec_rank=5000,
                legal_commander=True, legal_brawl=False,
            )
            card_in = Card(
                id=2, oracle_id="b", name="Better Card", type_line="Creature",
                oracle_text="", mana_cost="{2}", cmc=2.0, colors=["R"],
                color_identity=["R"], keywords=[], edhrec_rank=100,
                legal_commander=True, legal_brawl=False,
            )
            fake_rec = UpgradeRecommendation(
                card_out=card_out,
                card_in=card_in,
                price_delta=2.50,
                reason="Better synergy",
                upgrade_score=1.85,
            )
            mock_analysis = MagicMock()
            MockUpgradeService.return_value.recommend_from_cards.return_value = (
                mock_analysis,
                [fake_rec],
            )

            resp = client.post(
                f"/api/decks/{deck_id}/upgrade",
                json={"budget": 50.0},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["deck_id"] == deck_id
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["card_out"] == "Bad Card"
        assert data["recommendations"][0]["card_in"] == "Better Card"
        assert data["recommendations"][0]["price_delta"] == 2.5
        assert data["total_cost"] == 2.5

    def test_upgrade_nonexistent_deck_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/decks/99999/upgrade", json={"budget": 50.0})
        assert resp.status_code == 404
