"""Pricing API clients and fallback service for card price lookups.

Provides clients for TCGAPIs and JustTCG, plus a unified PricingService
that tries sources in priority order with automatic fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from mtg_deck_maker.api.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class PricingError(Exception):
    """Base exception for pricing API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PricingNotFoundError(PricingError):
    """Raised when a card price is not found (404)."""


class PricingRateLimitError(PricingError):
    """Raised when rate limited by a pricing API (429)."""


class PricingAuthError(PricingError):
    """Raised when API key is missing or invalid (401/403)."""


def _normalize_price_dict(
    usd: float | None = None,
    usd_foil: float | None = None,
    eur: float | None = None,
    eur_foil: float | None = None,
    source: str = "unknown",
) -> dict[str, Any]:
    """Create a normalized price dict with standard keys.

    Returns:
        Dict with 'usd', 'usd_foil', 'eur', 'eur_foil', and 'source' keys.
    """
    return {
        "usd": usd,
        "usd_foil": usd_foil,
        "eur": eur,
        "eur_foil": eur_foil,
        "source": source,
    }


class TCGAPIsClient:
    """Async client for the TCGAPIs pricing service.

    TCGAPIs provides real-time TCGPlayer pricing data with hourly updates.
    Free tier allows 100 calls/day.

    Args:
        api_key: TCGAPIs API key. Defaults to TCGAPIS_API_KEY env var.
        client: An httpx.AsyncClient instance. If not provided, one will
            be created internally.
        rate_limiter: A RateLimiter instance. Defaults to 2 req/sec.
    """

    BASE_URL = "https://api.tcgapis.com/v1"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("TCGAPIS_API_KEY", "")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
        )
        self._rate_limiter = rate_limiter or RateLimiter(rate=2.0, burst=2)

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> TCGAPIsClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make a rate-limited request to TCGAPIs.

        Raises:
            PricingAuthError: If the API key is missing or invalid.
            PricingNotFoundError: On 404 responses.
            PricingRateLimitError: On 429 responses.
            PricingError: On other non-success responses.
        """
        if not self._api_key:
            raise PricingAuthError(
                "TCGAPIS_API_KEY not configured", status_code=None
            )

        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with self._rate_limiter:
            response = await self._client.request(
                method,
                f"{self.BASE_URL}{path}",
                params=params,
                headers=headers,
            )

        if response.status_code in (401, 403):
            raise PricingAuthError(
                "Invalid or expired TCGAPIs API key",
                status_code=response.status_code,
            )

        if response.status_code == 404:
            raise PricingNotFoundError(
                "Card not found in TCGAPIs", status_code=404
            )

        if response.status_code == 429:
            raise PricingRateLimitError(
                "Rate limited by TCGAPIs", status_code=429
            )

        if response.status_code >= 400:
            raise PricingError(
                f"TCGAPIs error: HTTP {response.status_code}",
                status_code=response.status_code,
            )

        return response.json()

    async def get_card_price(
        self,
        card_name: str,
    ) -> dict[str, Any]:
        """Get pricing for a card by name.

        Args:
            card_name: The card name to look up.

        Returns:
            Normalized price dict with 'usd', 'usd_foil', etc.
        """
        data = await self._request(
            "GET", "/prices/search", params={"name": card_name}
        )

        # Extract pricing from response
        results = data.get("results", [])
        if not results:
            raise PricingNotFoundError(
                f"No pricing found for '{card_name}'", status_code=None
            )

        first = results[0]
        prices = first.get("prices", {})
        return _normalize_price_dict(
            usd=_safe_float(prices.get("usd")),
            usd_foil=_safe_float(prices.get("usd_foil")),
            eur=_safe_float(prices.get("eur")),
            eur_foil=_safe_float(prices.get("eur_foil")),
            source="tcgplayer",
        )

    async def get_card_prices_batch(
        self,
        card_names: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get pricing for multiple cards by name.

        Args:
            card_names: List of card names to look up.

        Returns:
            Dict mapping card names to normalized price dicts.
            Cards not found will be omitted from the result.
        """
        result: dict[str, dict[str, Any]] = {}
        for name in card_names:
            try:
                price = await self.get_card_price(name)
                result[name] = price
            except PricingError as exc:
                logger.debug(
                    "TCGAPIs price lookup failed for '%s': %s", name, exc
                )
        return result


class JustTCGClient:
    """Async client for the JustTCG pricing service.

    JustTCG provides supplementary/fallback pricing data.
    Free tier allows 1,000 calls/month.

    Args:
        api_key: JustTCG API key. Defaults to JUSTTCG_API_KEY env var.
        client: An httpx.AsyncClient instance. If not provided, one will
            be created internally.
        rate_limiter: A RateLimiter instance. Defaults to 1 req/sec.
    """

    BASE_URL = "https://api.justtcg.com/v1"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("JUSTTCG_API_KEY", "")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
        )
        self._rate_limiter = rate_limiter or RateLimiter(rate=1.0, burst=1)

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> JustTCGClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make a rate-limited request to JustTCG.

        Raises:
            PricingAuthError: If the API key is missing or invalid.
            PricingNotFoundError: On 404 responses.
            PricingRateLimitError: On 429 responses.
            PricingError: On other non-success responses.
        """
        if not self._api_key:
            raise PricingAuthError(
                "JUSTTCG_API_KEY not configured", status_code=None
            )

        headers = {"X-Api-Key": self._api_key}

        async with self._rate_limiter:
            response = await self._client.request(
                method,
                f"{self.BASE_URL}{path}",
                params=params,
                headers=headers,
            )

        if response.status_code in (401, 403):
            raise PricingAuthError(
                "Invalid or expired JustTCG API key",
                status_code=response.status_code,
            )

        if response.status_code == 404:
            raise PricingNotFoundError(
                "Card not found in JustTCG", status_code=404
            )

        if response.status_code == 429:
            raise PricingRateLimitError(
                "Rate limited by JustTCG", status_code=429
            )

        if response.status_code >= 400:
            raise PricingError(
                f"JustTCG error: HTTP {response.status_code}",
                status_code=response.status_code,
            )

        return response.json()

    async def get_card_price(
        self,
        card_name: str,
    ) -> dict[str, Any]:
        """Get pricing for a card by name.

        Args:
            card_name: The card name to look up.

        Returns:
            Normalized price dict with 'usd', 'usd_foil', etc.
        """
        data = await self._request(
            "GET", "/cards/price", params={"name": card_name}
        )

        prices = data.get("prices", {})
        return _normalize_price_dict(
            usd=_safe_float(prices.get("usd")),
            usd_foil=_safe_float(prices.get("usd_foil")),
            eur=_safe_float(prices.get("eur")),
            eur_foil=_safe_float(prices.get("eur_foil")),
            source="justtcg",
        )

    async def search_card(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """Search for cards by name.

        Args:
            query: Partial or full card name.

        Returns:
            List of matching card data dicts from JustTCG.
        """
        data = await self._request(
            "GET", "/cards/search", params={"q": query}
        )
        return data.get("results", [])


class PricingService:
    """Unified pricing service with fallback chain.

    Tries pricing sources in priority order:
    1. TCGAPIs (real-time TCGPlayer data)
    2. JustTCG (supplementary pricing)
    3. Scryfall cached prices (free, always available)

    Args:
        tcgapis_client: A TCGAPIsClient instance. If not provided, one
            will be created using environment variables.
        justtcg_client: A JustTCGClient instance. If not provided, one
            will be created using environment variables.
        scryfall_client: A ScryfallClient instance for fallback pricing.
            Can be None to skip Scryfall fallback.
    """

    def __init__(
        self,
        tcgapis_client: TCGAPIsClient | None = None,
        justtcg_client: JustTCGClient | None = None,
        scryfall_client: Any | None = None,
    ) -> None:
        self._tcgapis = tcgapis_client
        self._justtcg = justtcg_client
        self._scryfall = scryfall_client

    async def close(self) -> None:
        """Close all owned clients."""
        if self._tcgapis is not None:
            await self._tcgapis.close()
        if self._justtcg is not None:
            await self._justtcg.close()

    async def __aenter__(self) -> PricingService:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def get_card_price(
        self,
        card_name: str,
        scryfall_id: str | None = None,
    ) -> dict[str, Any]:
        """Get the best available price for a card using the fallback chain.

        Tries TCGAPIs first, then JustTCG, then Scryfall cached prices.

        Args:
            card_name: The card name to look up.
            scryfall_id: Optional Scryfall UUID for Scryfall price fallback.

        Returns:
            Normalized price dict with 'usd', 'usd_foil', 'eur',
            'eur_foil', and 'source' keys.

        Raises:
            PricingError: If all pricing sources fail.
        """
        errors: list[str] = []

        # Try TCGAPIs first
        if self._tcgapis is not None:
            try:
                return await self._tcgapis.get_card_price(card_name)
            except PricingError as exc:
                logger.debug("TCGAPIs failed for '%s': %s", card_name, exc)
                errors.append(f"TCGAPIs: {exc}")

        # Fallback to JustTCG
        if self._justtcg is not None:
            try:
                return await self._justtcg.get_card_price(card_name)
            except PricingError as exc:
                logger.debug("JustTCG failed for '%s': %s", card_name, exc)
                errors.append(f"JustTCG: {exc}")

        # Fallback to Scryfall cached prices
        if self._scryfall is not None and scryfall_id is not None:
            try:
                prices = await self._scryfall.get_card_prices(scryfall_id)
                return _normalize_price_dict(
                    usd=prices.get("usd"),
                    usd_foil=prices.get("usd_foil"),
                    eur=prices.get("eur"),
                    eur_foil=prices.get("eur_foil"),
                    source="scryfall",
                )
            except Exception as exc:
                logger.debug(
                    "Scryfall fallback failed for '%s': %s", card_name, exc
                )
                errors.append(f"Scryfall: {exc}")

        raise PricingError(
            f"All pricing sources failed for '{card_name}': "
            + "; ".join(errors)
        )

    async def get_card_prices_batch(
        self,
        cards: list[dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        """Get prices for multiple cards using the fallback chain.

        Args:
            cards: List of dicts with 'name' and optionally 'scryfall_id'.

        Returns:
            Dict mapping card names to normalized price dicts.
            Cards where all sources failed will be omitted.
        """
        result: dict[str, dict[str, Any]] = {}
        for card_info in cards:
            name = card_info["name"]
            scryfall_id = card_info.get("scryfall_id")
            try:
                price = await self.get_card_price(
                    name, scryfall_id=scryfall_id
                )
                result[name] = price
            except PricingError as exc:
                logger.warning(
                    "Failed to get price for '%s': %s", name, exc
                )
        return result


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
