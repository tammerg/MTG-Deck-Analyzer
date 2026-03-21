"""Sync router - database sync with Scryfall via Server-Sent Events."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mtg_deck_maker.api.web.schemas.sync import SyncRequest, SyncResultResponse
from mtg_deck_maker.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data event string."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/sync")
def run_sync(req: SyncRequest) -> StreamingResponse:
    """Sync the local card database with Scryfall.

    Streams progress events via Server-Sent Events. The final event
    contains the complete SyncResult.

    Args:
        req: SyncRequest with full flag controlling sync mode.

    Returns:
        StreamingResponse with text/event-stream content.
    """
    def event_stream():
        progress_events: list[dict] = []

        def progress_callback(stage: str, current: int, total: int) -> None:
            event = {"type": "progress", "stage": stage, "current": current, "total": total}
            progress_events.append(event)

        try:
            service = SyncService()
            result = service.sync(full=req.full, progress_callback=progress_callback)

            # Yield all buffered progress events
            for event in progress_events:
                yield _sse_event(event)

            # Yield the final result
            result_data = {
                "type": "result",
                "cards_added": result.cards_added,
                "cards_updated": result.cards_updated,
                "printings_added": result.printings_added,
                "prices_added": result.prices_added,
                "combos_synced": result.combos_synced,
                "duration_seconds": result.duration_seconds,
                "errors": result.errors,
                "success": result.success,
                "summary": result.summary(),
            }
            yield _sse_event(result_data)

        except Exception as exc:
            logger.exception("Sync failed")
            yield _sse_event({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
