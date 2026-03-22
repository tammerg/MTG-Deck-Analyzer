"""Sync router - database sync with Scryfall via Server-Sent Events.

Uses a queue-based bridge to stream progress events from the sync
service (running in a background thread) to the async SSE generator
in real time, avoiding the buffering problem where all events would
only arrive after sync completion.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mtg_deck_maker.api.web.schemas.sync import SyncRequest
from mtg_deck_maker.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

# Sentinel object to signal the sync thread has finished.
_DONE = object()


def _sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE data event string."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/sync")
async def run_sync(req: SyncRequest) -> StreamingResponse:
    """Sync the local card database with Scryfall.

    Streams progress events via Server-Sent Events. The sync runs in a
    background thread while the async generator yields events as they
    arrive through a ``queue.Queue`` bridge.

    Args:
        req: SyncRequest with full flag controlling sync mode.

    Returns:
        StreamingResponse with text/event-stream content.
    """
    event_queue: queue.Queue[dict[str, Any] | object] = queue.Queue()

    def _run_sync_in_thread() -> None:
        """Execute the sync in a background thread and push events to the queue."""
        def progress_callback(stage: str, current: int, total: int) -> None:
            event_queue.put({
                "type": "progress",
                "stage": stage,
                "current": current,
                "total": total,
            })

        try:
            service = SyncService()
            result = service.sync(full=req.full, progress_callback=progress_callback)

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
            event_queue.put(result_data)

        except Exception as exc:
            logger.exception("Sync failed")
            event_queue.put({"type": "error", "detail": str(exc)})

        finally:
            event_queue.put(_DONE)

    async def event_stream():
        """Async generator that yields SSE events from the queue."""
        loop = asyncio.get_running_loop()

        # Start the sync in a background thread.
        sync_task = loop.run_in_executor(None, _run_sync_in_thread)

        try:
            while True:
                # Read from the thread-safe queue without blocking the event loop.
                item = await loop.run_in_executor(None, event_queue.get)
                if item is _DONE:
                    break
                yield _sse_event(item)
        finally:
            # Ensure the background thread finishes even if the client disconnects.
            await sync_task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
