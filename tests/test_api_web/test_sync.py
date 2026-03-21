"""Tests for the sync endpoint with mocked sync service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestSync:
    def test_sync_returns_streaming_response(self, client: TestClient) -> None:
        """Sync endpoint streams SSE events and returns a result."""
        mock_result = MagicMock()
        mock_result.cards_added = 100
        mock_result.cards_updated = 5
        mock_result.printings_added = 200
        mock_result.prices_added = 300
        mock_result.combos_synced = 50
        mock_result.duration_seconds = 1.5
        mock_result.errors = []
        mock_result.success = True
        mock_result.summary.return_value = "Cards added: 100\nDuration: 1.5s"

        with patch(
            "mtg_deck_maker.api.web.routers.sync.SyncService"
        ) as MockSyncService:
            MockSyncService.return_value.sync.return_value = mock_result

            resp = client.post(
                "/api/sync",
                json={"full": False},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE events from response body
        raw = resp.text
        events = []
        for line in raw.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) >= 1
        result_event = next(
            (e for e in events if e.get("type") == "result"), None
        )
        assert result_event is not None
        assert result_event["cards_added"] == 100
        assert result_event["success"] is True

    def test_sync_full_flag_passed_to_service(self, client: TestClient) -> None:
        """Sync endpoint passes the full flag to SyncService."""
        mock_result = MagicMock()
        mock_result.cards_added = 0
        mock_result.cards_updated = 0
        mock_result.printings_added = 0
        mock_result.prices_added = 0
        mock_result.combos_synced = 0
        mock_result.duration_seconds = 0.1
        mock_result.errors = []
        mock_result.success = True
        mock_result.summary.return_value = "Cards added: 0"

        with patch(
            "mtg_deck_maker.api.web.routers.sync.SyncService"
        ) as MockSyncService:
            MockSyncService.return_value.sync.return_value = mock_result

            client.post("/api/sync", json={"full": True})

            call_kwargs = MockSyncService.return_value.sync.call_args
            assert call_kwargs.kwargs.get("full") is True

    def test_sync_error_yields_error_event(self, client: TestClient) -> None:
        """Sync endpoint yields an error event when sync fails."""
        with patch(
            "mtg_deck_maker.api.web.routers.sync.SyncService"
        ) as MockSyncService:
            MockSyncService.return_value.sync.side_effect = RuntimeError("boom")

            resp = client.post("/api/sync", json={"full": False})

        assert resp.status_code == 200
        raw = resp.text
        events = []
        for line in raw.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        error_event = next((e for e in events if e.get("type") == "error"), None)
        assert error_event is not None
        assert "boom" in error_event["detail"]
