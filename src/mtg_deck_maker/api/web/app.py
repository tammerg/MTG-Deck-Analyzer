"""FastAPI application factory for the MTG Deck Maker web API."""

from __future__ import annotations

from fastapi import FastAPI

from mtg_deck_maker.api.web.middleware import register_middleware
from mtg_deck_maker.api.web.routers import (
    cards,
    config,
    decks,
    health,
    research,
    sync,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Registers all routers under the /api prefix and attaches
    CORS and global error handling middleware.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="MTG Deck Maker API",
        description=(
            "REST API for building, analyzing, and managing "
            "Magic: The Gathering Commander decks."
        ),
        version="1.0.0",
    )

    register_middleware(app)

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(cards.router, prefix=api_prefix)
    app.include_router(decks.router, prefix=api_prefix)
    app.include_router(research.router, prefix=api_prefix)
    app.include_router(sync.router, prefix=api_prefix)
    app.include_router(config.router, prefix=api_prefix)

    return app
