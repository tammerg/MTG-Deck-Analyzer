"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from mtg_deck_maker.api.web.dependencies import get_db
from mtg_deck_maker.db.database import Database

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Database = Depends(get_db)) -> dict:
    """Return API health status and basic database statistics.

    Returns:
        JSON object with status, db_exists, and card_count fields.
    """
    try:
        cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
        row = cursor.fetchone()
        card_count = int(row["cnt"]) if row else 0
        db_exists = True
    except Exception:
        card_count = 0
        db_exists = False

    return {
        "status": "ok",
        "db_exists": db_exists,
        "card_count": card_count,
    }
