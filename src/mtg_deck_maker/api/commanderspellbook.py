"""CommanderSpellbook API client for fetching verified card combos.

Fetches combo data from the CommanderSpellbook API and provides a fallback
mechanism using a bundled static JSON file when the API is unavailable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from mtg_deck_maker.models.combo import Combo

logger = logging.getLogger(__name__)

BASE_URL = "https://backend.commanderspellbook.com"
VARIANTS_ENDPOINT = f"{BASE_URL}/variants/"
FALLBACK_PATH = Path(__file__).parent.parent.parent.parent / "data" / "combos.json"
REQUEST_TIMEOUT = 30.0


class CommanderSpellbookError(Exception):
    """Raised when a CommanderSpellbook API request fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _parse_variant(data: dict[str, Any]) -> Combo:
    """Parse a single variant/combo from the API response into a Combo model.

    Args:
        data: A single variant dict from the API.

    Returns:
        A Combo instance.
    """
    card_names = [
        use["card"]["name"]
        for use in data.get("uses", [])
        if "card" in use and "name" in use["card"]
    ]

    produces = data.get("produces", [])
    result_parts = [
        prod["feature"]["name"]
        for prod in produces
        if "feature" in prod and "name" in prod["feature"]
    ]
    result = ", ".join(result_parts) if result_parts else ""

    identity_str = data.get("identity", "")
    color_identity = list(identity_str) if identity_str else []

    return Combo(
        combo_id=str(data.get("id", "")),
        card_names=card_names,
        result=result,
        color_identity=color_identity,
        prerequisite=data.get("otherPrerequisites", ""),
        description=data.get("description", ""),
    )


async def fetch_combos(limit: int | None = None) -> list[Combo]:
    """Fetch combos from the CommanderSpellbook API.

    Handles pagination automatically. If a limit is specified, stops after
    collecting that many combos.

    Args:
        limit: Maximum number of combos to fetch. None for all.

    Returns:
        List of Combo instances.

    Raises:
        CommanderSpellbookError: On API errors.
    """
    combos: list[Combo] = []
    params: dict[str, str] = {"format": "json"}
    if limit is not None:
        params["limit"] = str(limit)

    url: str | None = VARIANTS_ENDPOINT

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT),
        follow_redirects=True,
    ) as client:
        while url is not None:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except Exception as exc:
                raise CommanderSpellbookError(
                    f"Failed to fetch combos: {exc}"
                ) from exc

            data = response.json()
            results = data.get("results", [])

            for variant in results:
                combos.append(_parse_variant(variant))

            if limit is not None and len(combos) >= limit:
                combos = combos[:limit]
                break

            url = data.get("next")
            # After the first request, params are embedded in the next URL
            params = {}

    return combos


async def fetch_combos_for_cards(card_names: list[str]) -> list[Combo]:
    """Fetch combos that include any of the specified cards.

    Uses the CommanderSpellbook search API to filter by card names.

    Args:
        card_names: List of card names to search for.

    Returns:
        List of Combo instances containing the specified cards.

    Raises:
        CommanderSpellbookError: On API errors.
    """
    if not card_names:
        return []

    # The API supports card filtering via query parameter
    search_query = " ".join(f'card="{name}"' for name in card_names)
    params: dict[str, str] = {
        "format": "json",
        "q": search_query,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT),
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(VARIANTS_ENDPOINT, params=params)
            response.raise_for_status()
        except Exception as exc:
            raise CommanderSpellbookError(
                f"Failed to fetch combos for cards: {exc}"
            ) from exc

        data = response.json()
        results = data.get("results", [])

    return [_parse_variant(variant) for variant in results]


def load_fallback_combos() -> list[Combo]:
    """Load combos from the bundled static JSON fallback file.

    Returns:
        List of Combo instances from the fallback data.
    """
    if not FALLBACK_PATH.is_file():
        logger.warning(
            "Fallback combos file not found at %s", FALLBACK_PATH
        )
        return []

    with open(FALLBACK_PATH) as f:
        raw_combos = json.load(f)

    combos: list[Combo] = []
    for entry in raw_combos:
        combos.append(
            Combo(
                combo_id=entry["combo_id"],
                card_names=entry["card_names"],
                result=entry["result"],
                color_identity=entry.get("color_identity", []),
                prerequisite=entry.get("prerequisite", ""),
                description=entry.get("description", ""),
            )
        )

    return combos
