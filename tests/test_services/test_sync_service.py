"""Tests for the sync service module."""

from __future__ import annotations

from mtg_deck_maker.services.sync_service import SyncService


class TestSyncService:
    def test_incremental_sync_returns_message(self):
        """Incremental sync should return a not-yet-implemented message."""
        service = SyncService()
        result = service.sync(full=False)
        assert isinstance(result, str)
        assert "not yet implemented" in result.lower()

    def test_full_sync_returns_message(self):
        """Full sync should return a not-yet-implemented message."""
        service = SyncService()
        result = service.sync(full=True)
        assert isinstance(result, str)
        assert "not yet implemented" in result.lower()

    def test_sync_default_is_incremental(self):
        """Default sync should be incremental."""
        service = SyncService()
        result = service.sync()
        assert "incremental" in result.lower()
