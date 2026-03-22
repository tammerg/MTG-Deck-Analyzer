"""Tests for the sync endpoint with mocked sync service."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE data lines from a raw response body."""
    events = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


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

        events = _parse_sse_events(resp.text)

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
        events = _parse_sse_events(resp.text)

        error_event = next((e for e in events if e.get("type") == "error"), None)
        assert error_event is not None
        assert "boom" in error_event["detail"]

    def test_sync_streams_progress_events(self, client: TestClient) -> None:
        """Progress events are streamed via the queue bridge, not buffered."""
        mock_result = MagicMock()
        mock_result.cards_added = 10
        mock_result.cards_updated = 0
        mock_result.printings_added = 20
        mock_result.prices_added = 30
        mock_result.combos_synced = 0
        mock_result.duration_seconds = 0.5
        mock_result.errors = []
        mock_result.success = True
        mock_result.summary.return_value = "Cards added: 10"

        def fake_sync(full: bool = False, progress_callback=None) -> MagicMock:
            """Simulate a sync that emits progress events."""
            if progress_callback:
                progress_callback("Downloading", 0, 100)
                progress_callback("Downloading", 50, 100)
                progress_callback("Processing cards", 0, 10)
                progress_callback("Processing cards", 10, 10)
            return mock_result

        with patch(
            "mtg_deck_maker.api.web.routers.sync.SyncService"
        ) as MockSyncService:
            MockSyncService.return_value.sync.side_effect = fake_sync

            resp = client.post("/api/sync", json={"full": True})

        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        # Should have 4 progress events + 1 result event
        progress_events = [e for e in events if e.get("type") == "progress"]
        result_events = [e for e in events if e.get("type") == "result"]

        assert len(progress_events) == 4
        assert len(result_events) == 1

        # Verify progress event structure
        assert progress_events[0]["stage"] == "Downloading"
        assert progress_events[0]["current"] == 0
        assert progress_events[0]["total"] == 100

        assert progress_events[2]["stage"] == "Processing cards"

        # Verify result event
        assert result_events[0]["cards_added"] == 10
        assert result_events[0]["success"] is True

    def test_sync_progress_events_arrive_before_result(
        self, client: TestClient
    ) -> None:
        """Progress events appear in the stream before the final result."""
        mock_result = MagicMock()
        mock_result.cards_added = 1
        mock_result.cards_updated = 0
        mock_result.printings_added = 1
        mock_result.prices_added = 1
        mock_result.combos_synced = 0
        mock_result.duration_seconds = 0.1
        mock_result.errors = []
        mock_result.success = True
        mock_result.summary.return_value = "Cards added: 1"

        def fake_sync(full: bool = False, progress_callback=None) -> MagicMock:
            """Emit a progress event, then pause briefly to simulate work."""
            if progress_callback:
                progress_callback("Working", 1, 2)
            # Small delay to ensure the queue is drained between events
            time.sleep(0.01)
            if progress_callback:
                progress_callback("Working", 2, 2)
            return mock_result

        with patch(
            "mtg_deck_maker.api.web.routers.sync.SyncService"
        ) as MockSyncService:
            MockSyncService.return_value.sync.side_effect = fake_sync

            resp = client.post("/api/sync", json={"full": False})

        events = _parse_sse_events(resp.text)
        types = [e.get("type") for e in events]

        # Progress events must come before the result
        assert types == ["progress", "progress", "result"]
