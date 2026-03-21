"""FastAPI dependency injection providers."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from mtg_deck_maker.config import AppConfig, load_config
from mtg_deck_maker.db.database import Database


def get_config() -> AppConfig:
    """Return the loaded application configuration.

    Returns:
        AppConfig loaded from TOML, environment, and defaults.
    """
    return load_config()


def get_db() -> Generator[Database, None, None]:
    """Yield an open Database connection using the configured data directory.

    Closes the connection when the request finishes.

    Yields:
        An open Database instance.
    """
    config = load_config()
    db_path = Path(config.general.data_dir) / "mtg_deck_maker.db"
    db = Database(db_path)
    db.connect()
    try:
        yield db
    finally:
        db.close()
