"""Tests for card search, get, printings, price, and commander search endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestCardSearch:
    def test_search_returns_results(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=Sol")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)
        assert any(c["name"] == "Sol Ring" for c in data["results"])

    def test_search_empty_query_returns_all(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["total"] >= 1

    def test_search_no_results(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=zzznomatch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_search_with_color_filter(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=&color=U")
        assert resp.status_code == 200
        data = resp.json()
        # Counterspell has color_identity U, Sol Ring is colorless (subset of any)
        for card in data["results"]:
            assert set(card["color_identity"]).issubset({"U"})

    def test_search_with_type_filter(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=&type=Instant")
        assert resp.status_code == 200
        data = resp.json()
        assert all("Instant" in c["type_line"] for c in data["results"])

    def test_search_limit_applied(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 1

    def test_search_card_has_image_url(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=Sol Ring")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        # Image URL should be populated from printing
        assert data["results"][0]["image_url"] is not None
        assert "scryfall.io" in data["results"][0]["image_url"]

    def test_search_with_offset(self, client: TestClient) -> None:
        # Get all results first
        all_resp = client.get("/api/cards/search?q=&limit=100")
        all_data = all_resp.json()
        total = all_data["total"]
        all_results = all_data["results"]

        if total < 2:
            return  # Not enough data to test offset

        # Get results with offset=1
        offset_resp = client.get("/api/cards/search?q=&limit=100&offset=1")
        offset_data = offset_resp.json()

        # Total should be the same regardless of offset
        assert offset_data["total"] == total
        # Results should be shifted by 1
        assert len(offset_data["results"]) == len(all_results) - 1
        assert offset_data["results"][0]["id"] == all_results[1]["id"]

    def test_search_offset_beyond_results(self, client: TestClient) -> None:
        resp = client.get("/api/cards/search?q=&offset=9999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        # Total should still reflect the full count
        assert data["total"] >= 0

    def test_search_total_reflects_filtered_count(self, client: TestClient) -> None:
        # Search for a specific card
        resp = client.get("/api/cards/search?q=Sol Ring&limit=1")
        data = resp.json()
        # Total should be >= 1 (the full filtered count, not the page size)
        assert data["total"] >= 1
        assert len(data["results"]) == 1


class TestGetCard:
    def test_get_existing_card(self, client: TestClient) -> None:
        # First find the id via search
        search_resp = client.get("/api/cards/search?q=Sol Ring")
        card_id = search_resp.json()["results"][0]["id"]

        resp = client.get(f"/api/cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Sol Ring"

    def test_get_nonexistent_card_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/cards/99999")
        assert resp.status_code == 404

    def test_get_card_has_image_url(self, client: TestClient) -> None:
        search_resp = client.get("/api/cards/search?q=Sol Ring")
        card_id = search_resp.json()["results"][0]["id"]

        resp = client.get(f"/api/cards/{card_id}")
        data = resp.json()
        assert data["image_url"] is not None
        assert "scryfall.io" in data["image_url"]


class TestCardPrintings:
    def test_get_printings_for_card(self, client: TestClient) -> None:
        search_resp = client.get("/api/cards/search?q=Sol Ring")
        card_id = search_resp.json()["results"][0]["id"]

        resp = client.get(f"/api/cards/{card_id}/printings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert all("scryfall_id" in p for p in data)
        assert all("image_url" in p for p in data)

    def test_get_printings_for_missing_card(self, client: TestClient) -> None:
        resp = client.get("/api/cards/99999/printings")
        assert resp.status_code == 404


class TestCardPrice:
    def test_get_price_for_card(self, client: TestClient) -> None:
        search_resp = client.get("/api/cards/search?q=Sol Ring")
        card_id = search_resp.json()["results"][0]["id"]

        resp = client.get(f"/api/cards/{card_id}/price")
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 2.0
        assert data["currency"] == "USD"
        assert data["finish"] == "nonfoil"

    def test_get_price_for_missing_card(self, client: TestClient) -> None:
        resp = client.get("/api/cards/99999/price")
        assert resp.status_code == 404


class TestCommanderSearch:
    def test_commander_search_returns_only_legal(self, client: TestClient) -> None:
        resp = client.get("/api/commanders/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["legal_commander"] for c in data)

    def test_commander_search_with_query(self, client: TestClient) -> None:
        resp = client.get("/api/commanders/search?q=Atraxa")
        assert resp.status_code == 200
        data = resp.json()
        assert any(c["name"] == "Atraxa, Praetors' Voice" for c in data)
        assert all(c["legal_commander"] for c in data)


class TestPopularCommanders:
    def test_returns_commanders_from_edhrec(self, client: TestClient) -> None:
        mock_pairs = [
            ("Atraxa, Praetors' Voice", 5000),
            ("Sol Ring", 3000),  # not a commander — but exists in seeded db
        ]
        with patch(
            "mtg_deck_maker.api.web.routers.cards.fetch_popular_commanders",
            new_callable=AsyncMock,
            return_value=mock_pairs,
        ):
            resp = client.get("/api/commanders/popular?limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert "commanders" in data
        assert len(data["commanders"]) == 2
        assert data["commanders"][0]["card"]["name"] == "Atraxa, Praetors' Voice"
        assert data["commanders"][0]["num_decks"] == 5000
        assert data["commanders"][0]["card"]["image_url"] is not None

    def test_skips_unmatched_names(self, client: TestClient) -> None:
        mock_pairs = [
            ("Nonexistent Commander", 9000),
            ("Atraxa, Praetors' Voice", 5000),
        ]
        with patch(
            "mtg_deck_maker.api.web.routers.cards.fetch_popular_commanders",
            new_callable=AsyncMock,
            return_value=mock_pairs,
        ):
            resp = client.get("/api/commanders/popular")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["commanders"]) == 1
        assert data["commanders"][0]["card"]["name"] == "Atraxa, Praetors' Voice"

    def test_empty_edhrec_response(self, client: TestClient) -> None:
        with patch(
            "mtg_deck_maker.api.web.routers.cards.fetch_popular_commanders",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get("/api/commanders/popular")

        assert resp.status_code == 200
        data = resp.json()
        assert data["commanders"] == []
