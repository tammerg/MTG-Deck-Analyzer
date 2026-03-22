"""Tests for the health check endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """Health endpoint returns status ok, db_exists, and card_count."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db_exists"] is True
    # seeded_db contains 3 cards (Atraxa, Sol Ring, Counterspell)
    assert data["card_count"] == 3
