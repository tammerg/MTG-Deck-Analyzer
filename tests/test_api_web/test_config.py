"""Tests for the config get and update endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestGetConfig:
    def test_get_config_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        assert resp.status_code == 200

    def test_get_config_has_all_sections(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        data = resp.json()
        assert "constraints" in data
        assert "pricing" in data
        assert "general" in data
        assert "llm" in data

    def test_get_config_constraints_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        constraints = resp.json()["constraints"]
        assert constraints["avoid_reserved_list"] is True
        assert constraints["allow_fast_mana"] is False
        assert constraints["max_price_per_card"] == 20.0

    def test_get_config_pricing_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        pricing = resp.json()["pricing"]
        assert pricing["preferred_source"] == "tcgplayer"
        assert pricing["preferred_currency"] == "USD"

    def test_get_config_llm_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        llm = resp.json()["llm"]
        assert llm["provider"] == "auto"
        assert llm["max_tokens"] == 2048


class TestUpdateConfig:
    def test_update_config_returns_200(self, client: TestClient) -> None:
        resp = client.put(
            "/api/config",
            json={"constraints": {"max_price_per_card": 30.0}},
        )
        assert resp.status_code == 200

    def test_update_constraints_field(self, client: TestClient) -> None:
        resp = client.put(
            "/api/config",
            json={"constraints": {"max_price_per_card": 50.0}},
        )
        data = resp.json()
        assert data["constraints"]["max_price_per_card"] == 50.0

    def test_update_llm_field(self, client: TestClient) -> None:
        resp = client.put(
            "/api/config",
            json={"llm": {"provider": "openai", "temperature": 0.5}},
        )
        data = resp.json()
        assert data["llm"]["provider"] == "openai"
        assert data["llm"]["temperature"] == 0.5

    def test_update_partial_leaves_others_unchanged(self, client: TestClient) -> None:
        resp = client.put(
            "/api/config",
            json={"pricing": {"preferred_source": "cardmarket"}},
        )
        data = resp.json()
        assert data["pricing"]["preferred_source"] == "cardmarket"
        # Other fields remain at defaults
        assert data["constraints"]["avoid_reserved_list"] is True

    def test_update_empty_body(self, client: TestClient) -> None:
        resp = client.put("/api/config", json={})
        assert resp.status_code == 200
