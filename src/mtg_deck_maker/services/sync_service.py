"""Sync service placeholder for future Scryfall data synchronization.

This service will handle syncing the local card database with data
from Scryfall and other external sources. Currently a stub.
"""

from __future__ import annotations


class SyncService:
    """Placeholder service for card database synchronization.

    Will be implemented in a future phase to support:
    - Bulk data download from Scryfall
    - Incremental card updates
    - Price data synchronization
    """

    def sync(self, full: bool = False) -> str:
        """Run a sync operation.

        Args:
            full: If True, perform a full sync including bulk data.
                If False, perform an incremental update.

        Returns:
            Status message describing the sync result.
        """
        if full:
            return (
                "Full sync is not yet implemented. "
                "This will download bulk data from Scryfall in a future update."
            )
        return (
            "Incremental sync is not yet implemented. "
            "This will update card data from Scryfall in a future update."
        )
