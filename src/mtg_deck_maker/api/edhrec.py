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
        cardlists = data.get("cardlists", [])
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
