"""EDHREC JSON API client for per-commander card inclusion data.

Fetches data from EDHREC's public JSON endpoints that power their website.
Falls back gracefully to empty results on any error (the system works
without EDHREC data -- it just performs better with it).
"""

from __future__ import annotations

import logging
import re

import httpx

from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData

logger = logging.getLogger(__name__)

EDHREC_BASE_URL = "https://json.edhrec.com/pages/commanders"
USER_AGENT = "mtg-deck-maker/0.1.0"
REQUEST_TIMEOUT = 15.0  # seconds


def _extract_cardlists(data: dict) -> list[dict]:
    """Extract cardlists from EDHREC JSON, handling both old and new formats.

    EDHREC restructured their API: cardlists moved from the top level
    to ``container.json_dict.cardlists``.  This helper checks both
    locations so existing and new responses both work.
    """
    # New format: container → json_dict → cardlists
    cardlists = (
        data.get("container", {}).get("json_dict", {}).get("cardlists", [])
    )
    if cardlists:
        return cardlists

    # Legacy format: top-level cardlists
    return data.get("cardlists", [])


def _commander_name_to_slug(name: str) -> str:
    """Convert a commander name to an EDHREC URL slug.

    Rules:
        - Lowercase the name
        - Remove commas, apostrophes, and periods
        - Replace spaces with hyphens

    Args:
        name: Commander name (e.g. "Atraxa, Praetors' Voice").

    Returns:
        URL slug (e.g. "atraxa-praetors-voice").
    """
    slug = name.lower()
    # Remove commas, apostrophes, and periods
    slug = re.sub(r"[,'.]+", "", slug)
    # Replace spaces and multiple hyphens with a single hyphen
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


async def fetch_commander_data(
    commander_name: str,
) -> list[EdhrecCommanderData]:
    """Fetch per-commander card inclusion data from EDHREC.

    Queries the EDHREC JSON endpoint for a specific commander and parses
    the response into EdhrecCommanderData objects.

    Args:
        commander_name: The commander name to look up.

    Returns:
        List of EdhrecCommanderData objects. Returns empty list on any
        failure (HTTP error, parse error, missing data).
    """
    slug = _commander_name_to_slug(commander_name)
    url = f"{EDHREC_BASE_URL}/{slug}.json"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning(
            "Failed to fetch EDHREC data for %r from %s",
            commander_name,
            url,
        )
        return []

    return _parse_response(commander_name, data)


async def fetch_commander_full_data(
    commander_name: str,
    min_inclusion: float = 0.01,
) -> list[EdhrecCommanderData]:
    """Fetch extended per-commander card data with lower inclusion threshold.

    Similar to fetch_commander_data but includes cards with lower inclusion
    rates (down to min_inclusion), useful for ML training data.

    Args:
        commander_name: The commander name to look up.
        min_inclusion: Minimum inclusion rate to include (default 1%).

    Returns:
        List of EdhrecCommanderData filtered to min_inclusion threshold.
    """
    all_data = await fetch_commander_data(commander_name)
    return [d for d in all_data if d.inclusion_rate >= min_inclusion]


async def fetch_training_commanders(
    min_decks: int = 500,
) -> list[str]:
    """Fetch a list of popular commanders suitable for ML training.

    Queries EDHREC for top commanders by deck count.

    Args:
        min_decks: Minimum number of decks to qualify.

    Returns:
        List of commander names. Returns empty list on failure.
    """
    url = "https://json.edhrec.com/pages/commanders/year.json"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning(
            "Failed to fetch training commanders from %s", url
        )
        return []

    return _parse_training_commanders(data, min_decks)


async def fetch_popular_commanders(
    limit: int = 20,
) -> list[tuple[str, int]]:
    """Fetch popular commanders sorted by deck count.

    Queries the same EDHREC endpoint as fetch_training_commanders but
    returns (name, deck_count) tuples for display purposes.

    Args:
        limit: Maximum number of commanders to return.

    Returns:
        List of (name, deck_count) tuples sorted by popularity.
        Returns empty list on failure.
    """
    url = "https://json.edhrec.com/pages/commanders/year.json"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning("Failed to fetch popular commanders from %s", url)
        return []

    return _parse_popular_commanders(data, limit)


def _parse_popular_commanders(
    data: dict, limit: int,
) -> list[tuple[str, int]]:
    """Parse the EDHREC commanders list into (name, deck_count) tuples.

    Args:
        data: Parsed JSON dict from EDHREC.
        limit: Maximum results to return.

    Returns:
        List of (name, deck_count) sorted descending by deck count.
    """
    try:
        cardlists = _extract_cardlists(data)
        if not cardlists:
            return []

        commanders: list[tuple[str, int]] = []

        for cardlist in cardlists:
            cardviews = cardlist.get("cardviews", [])
            if not isinstance(cardviews, list):
                continue

            for entry in cardviews:
                name = entry.get("name", "")
                num_decks = int(entry.get("num_decks", 0))
                if name and num_decks > 0:
                    commanders.append((name, num_decks))

        commanders.sort(key=lambda x: x[1], reverse=True)
        return commanders[:limit]
    except Exception:
        logger.warning("Failed to parse popular commanders response")
        return []


def _parse_training_commanders(data: dict, min_decks: int) -> list[str]:
    """Parse the EDHREC commanders list response.

    Args:
        data: Parsed JSON dict from EDHREC.
        min_decks: Minimum deck count threshold.

    Returns:
        List of commander names meeting the threshold.
    """
    try:
        cardlists = _extract_cardlists(data)
        if not cardlists:
            return []

        commanders: list[str] = []

        for cardlist in cardlists:
            cardviews = cardlist.get("cardviews", [])
            if not isinstance(cardviews, list):
                continue

            for entry in cardviews:
                name = entry.get("name", "")
                num_decks = int(entry.get("num_decks", 0))
                if name and num_decks >= min_decks:
                    commanders.append(name)

        return commanders
    except Exception:
        logger.warning("Failed to parse training commanders response")
        return []


def _parse_response(
    commander_name: str,
    data: dict,
) -> list[EdhrecCommanderData]:
    """Parse the EDHREC JSON response into data objects.

    Args:
        commander_name: The commander name for context.
        data: Parsed JSON dict from EDHREC.

    Returns:
        List of EdhrecCommanderData. Empty on parse errors.
    """
    try:
        cardlists = _extract_cardlists(data)
        if not cardlists:
            return []

        results: list[EdhrecCommanderData] = []
        seen_cards: set[str] = set()

        for cardlist in cardlists:
            cardviews = cardlist.get("cardviews", [])
            if not isinstance(cardviews, list):
                continue

            for card_entry in cardviews:
                card_name = card_entry.get("name", "")
                if not card_name or card_name in seen_cards:
                    continue
                seen_cards.add(card_name)

                # inclusion is a percentage integer (e.g. 45 means 45%)
                inclusion_pct = card_entry.get("inclusion", 0)
                inclusion_rate = float(inclusion_pct) / 100.0

                num_decks = int(card_entry.get("num_decks", 0))
                potential_decks = int(card_entry.get("potential_decks", 0))
                synergy_score = float(card_entry.get("synergy", 0.0))

                results.append(
                    EdhrecCommanderData(
                        commander_name=commander_name,
                        card_name=card_name,
                        inclusion_rate=inclusion_rate,
                        num_decks=num_decks,
                        potential_decks=potential_decks,
                        synergy_score=synergy_score,
                    )
                )

        return results
    except Exception:
        logger.warning(
            "Failed to parse EDHREC response for %r", commander_name
        )
        return []
