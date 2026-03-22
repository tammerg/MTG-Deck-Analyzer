"""Tests for the config get and update endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestGetConfig:
    def test_get_config_with_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        # All sections present
        assert "constraints" in data
        assert "pricing" in data
        assert "general" in data
        assert "llm" in data
        # Representative defaults
        assert data["constraints"]["avoid_reserved_list"] is True
        assert data["constraints"]["max_price_per_card"] == 20.0
        assert data["pricing"]["preferred_source"] == "tcgplayer"
        assert data["llm"]["provider"] == "auto"
        assert data["llm"]["max_tokens"] == 2048


class TestUpdateConfig:
    @pytest.mark.parametrize(
        "payload, check_path, expected",
        [
            (
                {"constraints": {"max_price_per_card": 50.0}},
                ("constraints", "max_price_per_card"),
                50.0,
            ),
            (
                {"llm": {"provider": "openai", "temperature": 0.5}},
                ("llm", "provider"),
                "openai",
            ),
            (
                {"pricing": {"preferred_source": "cardmarket"}},
                ("pricing", "preferred_source"),
                "cardmarket",
            ),
        ],
        ids=["update_constraints", "update_llm", "update_pricing"],
    )
    def test_update_config_field(self, client: TestClient, payload, check_path, expected) -> None:
        resp = client.put("/api/config", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        section, field = check_path
        assert data[section][field] == expected

    def test_update_partial_leaves_others_unchanged(self, client: TestClient) -> None:
        resp = client.put(
            "/api/config",
            json={"pricing": {"preferred_source": "cardmarket"}},
        )
        data = resp.json()
        assert data["pricing"]["preferred_source"] == "cardmarket"
        assert data["constraints"]["avoid_reserved_list"] is True

    def test_update_empty_body(self, client: TestClient) -> None:
        resp = client.put("/api/config", json={})
        assert resp.status_code == 200
