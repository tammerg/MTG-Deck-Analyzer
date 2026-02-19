"""Async Scryfall API client for card search and data retrieval."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mtg_deck_maker.api.rate_limiter import RateLimiter
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing

logger = logging.getLogger(__name__)

BASE_URL = "https://api.scryfall.com"
USER_AGENT = "mtg-deck-maker/0.1.0"
SCRYFALL_RATE = 10.0  # Scryfall allows ~10 req/sec


class ScryfallError(Exception):
    """Base exception for Scryfall API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ScryfallNotFoundError(ScryfallError):
    """Raised when a card is not found (404)."""


class ScryfallRateLimitError(ScryfallError):
    """Raised when rate limited by Scryfall (429)."""


class ScryfallServerError(ScryfallError):
    """Raised on Scryfall server errors (5xx)."""


def parse_scryfall_card(data: dict[str, Any]) -> tuple[Card, Printing]:
    """Parse a Scryfall card JSON object into Card and Printing models.

    Args:
        data: A single Scryfall card object from the API.

    Returns:
        A tuple of (Card, Printing) parsed from the data.
    """
    legalities = data.get("legalities", {})

    card = Card(
        oracle_id=data.get("oracle_id", ""),
        name=data.get("name", ""),
        type_line=data.get("type_line", ""),
        oracle_text=data.get("oracle_text", ""),
        mana_cost=data.get("mana_cost", ""),
        cmc=float(data.get("cmc", 0.0)),
        colors=data.get("colors", []),
        color_identity=data.get("color_identity", []),
        keywords=data.get("keywords", []),
        edhrec_rank=data.get("edhrec_rank"),
        legal_commander=legalities.get("commander") == "legal",
        legal_brawl=legalities.get("brawl") == "legal",
        updated_at=data.get("updated_at", ""),
    )

    finishes_raw = data.get("finishes", [])
    printing = Printing(
        scryfall_id=data.get("id", ""),
        card_id=0,  # Will be set when card is inserted into DB
        set_code=data.get("set", ""),
        collector_number=data.get("collector_number", ""),
        lang=data.get("lang", "en"),
        rarity=data.get("rarity", ""),
        finishes=finishes_raw if isinstance(finishes_raw, list) else [],
        tcgplayer_id=data.get("tcgplayer_id"),
        cardmarket_id=data.get("cardmarket_id"),
        released_at=data.get("released_at", ""),
        is_promo=data.get("promo", False),
        is_reprint=data.get("reprint", False),
    )

    return card, printing


def _parse_scryfall_prices(data: dict[str, Any]) -> dict[str, float | None]:
    """Extract normalized price dict from Scryfall card data.

    Returns a dict with keys like 'usd', 'usd_foil', 'eur', 'eur_foil'.
    Values are floats or None if not available.
    """
    prices_raw = data.get("prices", {})
    result: dict[str, float | None] = {}
    for key in ("usd", "usd_foil", "usd_etched", "eur", "eur_foil"):
        val = prices_raw.get(key)
        if val is not None:
            try:
                result[key] = float(val)
            except (ValueError, TypeError):
                result[key] = None
        else:
            result[key] = None
    return result


class ScryfallClient:
    """Async client for the Scryfall API.

    Handles rate limiting, error handling, pagination, and parsing
    Scryfall JSON responses into Card and Printing models.

    Args:
        client: An httpx.AsyncClient instance. If not provided, one will
            be created internally.
        rate_limiter: A RateLimiter instance. If not provided, a default
            one configured for Scryfall's limits will be created.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        self._rate_limiter = rate_limiter or RateLimiter(
            rate=SCRYFALL_RATE, burst=10
        )

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> ScryfallClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a rate-limited HTTP request to Scryfall.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path relative to base URL.
            params: Query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ScryfallNotFoundError: On 404 responses.
            ScryfallRateLimitError: On 429 responses.
            ScryfallServerError: On 5xx responses.
            ScryfallError: On other non-success responses.
        """
        async with self._rate_limiter:
            url = path if path.startswith("http") else f"{BASE_URL}{path}"
            response = await self._client.request(
                method, url, params=params
            )

        if response.status_code == 404:
            body = response.json()
            detail = body.get("details", "Card not found")
            raise ScryfallNotFoundError(detail, status_code=404)

        if response.status_code == 429:
            raise ScryfallRateLimitError(
                "Rate limited by Scryfall", status_code=429
            )

        if response.status_code >= 500:
            raise ScryfallServerError(
                f"Scryfall server error: {response.status_code}",
                status_code=response.status_code,
            )

        if response.status_code >= 400:
            body = response.json()
            detail = body.get("details", f"HTTP {response.status_code}")
            raise ScryfallError(detail, status_code=response.status_code)

        return response.json()

    async def search_cards(
        self,
        query: str,
        page: int = 1,
        unique: str = "cards",
        order: str = "name",
    ) -> dict[str, Any]:
        """Search for cards using Scryfall's full-text search.

        Args:
            query: Scryfall search query string.
            page: Page number for pagination (1-indexed).
            unique: Uniqueness strategy ('cards', 'art', 'prints').
            order: Sort order ('name', 'released', 'edhrec', etc.).

        Returns:
            Raw Scryfall list response with 'data', 'has_more',
            'total_cards', and optionally 'next_page' keys.
        """
        params = {
            "q": query,
            "page": str(page),
            "unique": unique,
            "order": order,
        }
        return await self._request("GET", "/cards/search", params=params)

    async def search_cards_all(
        self,
        query: str,
        unique: str = "cards",
        order: str = "name",
    ) -> list[dict[str, Any]]:
        """Search for cards and automatically paginate through all results.

        Args:
            query: Scryfall search query string.
            unique: Uniqueness strategy.
            order: Sort order.

        Returns:
            List of all card data dicts across all pages.
        """
        all_cards: list[dict[str, Any]] = []
        page = 1

        while True:
            result = await self.search_cards(
                query, page=page, unique=unique, order=order
            )
            all_cards.extend(result.get("data", []))

            if not result.get("has_more", False):
                break

            page += 1

        return all_cards

    async def get_card_by_name(
        self,
        name: str,
        exact: bool = True,
    ) -> dict[str, Any]:
        """Look up a card by name.

        Args:
            name: Card name to search for.
            exact: If True, use exact name match. If False, use fuzzy match.

        Returns:
            Scryfall card object dict.

        Raises:
            ScryfallNotFoundError: If no card matches the name.
        """
        param_key = "exact" if exact else "fuzzy"
        params = {param_key: name}
        return await self._request("GET", "/cards/named", params=params)

    async def get_card_by_id(
        self,
        scryfall_id: str,
    ) -> dict[str, Any]:
        """Look up a card by its Scryfall UUID.

        Args:
            scryfall_id: The Scryfall UUID of the card.

        Returns:
            Scryfall card object dict.

        Raises:
            ScryfallNotFoundError: If no card matches the ID.
        """
        return await self._request("GET", f"/cards/{scryfall_id}")

    async def get_bulk_data(self) -> list[dict[str, Any]]:
        """Get the list of available bulk data downloads.

        Returns:
            List of bulk data descriptor dicts from Scryfall.
        """
        result = await self._request("GET", "/bulk-data")
        return result.get("data", [])

    async def autocomplete(
        self,
        query: str,
        include_extras: bool = False,
    ) -> list[str]:
        """Get card name autocompletions.

        Args:
            query: Partial card name to autocomplete.
            include_extras: Include extra/funny cards in results.

        Returns:
            List of card name suggestions.
        """
        params: dict[str, str] = {"q": query}
        if include_extras:
            params["include_extras"] = "true"
        result = await self._request(
            "GET", "/cards/autocomplete", params=params
        )
        return result.get("data", [])

    async def get_card_prices(
        self,
        scryfall_id: str,
    ) -> dict[str, float | None]:
        """Get cached Scryfall prices for a card by its Scryfall ID.

        Args:
            scryfall_id: The Scryfall UUID of the card.

        Returns:
            Dict of price keys to float values (or None if unavailable).
        """
        data = await self.get_card_by_id(scryfall_id)
        return _parse_scryfall_prices(data)
