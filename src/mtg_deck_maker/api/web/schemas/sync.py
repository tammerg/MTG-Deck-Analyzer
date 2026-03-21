"""Pydantic schemas for sync-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SyncRequest(BaseModel):
    """Request body for a database sync operation."""

    full: bool = False


class SyncResultResponse(BaseModel):
    """Response schema for a sync operation result."""

    cards_added: int
    cards_updated: int
    printings_added: int
    prices_added: int
    combos_synced: int
    duration_seconds: float
    errors: list[str]
    success: bool
    summary: str
