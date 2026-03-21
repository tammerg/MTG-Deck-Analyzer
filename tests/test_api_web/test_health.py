"""Tests for the health check endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """Health endpoint returns status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_health_returns_db_exists(client: TestClient) -> None:
    """Health endpoint reports db_exists true when DB is available."""
    resp = client.get("/api/health")
    data = resp.json()
    assert data["db_exists"] is True


def test_health_returns_card_count(client: TestClient) -> None:
    """Health endpoint returns the number of cards in the database."""
    resp = client.get("/api/health")
    data = resp.json()
    # seeded_db contains 3 cards (Atraxa, Sol Ring, Counterspell)
    assert data["card_count"] == 3
