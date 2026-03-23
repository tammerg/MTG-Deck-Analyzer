"""FastAPI dependency injection providers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Generator

from fastapi import Depends

from mtg_deck_maker.config import AppConfig, load_config
from mtg_deck_maker.db.database import Database


@lru_cache(maxsize=1)
def _cached_config() -> AppConfig:
    """Return a cached AppConfig, loaded once for the process lifetime.

    Returns:
        AppConfig loaded from TOML, environment, and defaults.
    """
    return load_config()


def get_config() -> AppConfig:
    """Return the loaded application configuration.

    Returns:
        AppConfig loaded from TOML, environment, and defaults.
    """
    return _cached_config()


def get_db(
    config: AppConfig = Depends(get_config),
) -> Generator[Database, None, None]:
    """Yield an open Database connection using the configured data directory.

    Closes the connection when the request finishes.

    Args:
        config: AppConfig injected from get_config (never calls load_config again).

    Yields:
        An open Database instance.
    """
    db_path = Path(config.general.data_dir) / "mtg_deck_maker.db"
    db = Database(db_path)
    db.connect()
    try:
        yield db
    finally:
        db.close()
