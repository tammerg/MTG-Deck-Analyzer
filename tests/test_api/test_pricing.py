"""Tests for pricing API clients and PricingService fallback logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mtg_deck_maker.api.pricing import (
    JustTCGClient,
    PricingAuthError,
    PricingError,
    PricingNotFoundError,
    PricingRateLimitError,
    PricingService,
    TCGAPIsClient,
    _normalize_price_dict,
    _safe_float,
)
from mtg_deck_maker.api.rate_limiter import RateLimiter

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "pricing"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture file by name."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    return response


def _make_tcgapis_client(
    mock_responses: list[httpx.Response] | None = None,
    api_key: str = "test-key",
) -> tuple[TCGAPIsClient, AsyncMock]:
    """Create a TCGAPIsClient with mocked HTTP."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    if mock_responses:
        mock_http.request.side_effect = mock_responses
    limiter = RateLimiter(rate=1000.0, burst=100)
    client = TCGAPIsClient(
        api_key=api_key, client=mock_http, rate_limiter=limiter
    )
    return client, mock_http.request


def _make_justtcg_client(
    mock_responses: list[httpx.Response] | None = None,
    api_key: str = "test-key",
) -> tuple[JustTCGClient, AsyncMock]:
    """Create a JustTCGClient with mocked HTTP."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    if mock_responses:
        mock_http.request.side_effect = mock_responses
    limiter = RateLimiter(rate=1000.0, burst=100)
    client = JustTCGClient(
        api_key=api_key, client=mock_http, rate_limiter=limiter
    )
    return client, mock_http.request


class TestNormalizePriceDict:
    """Test the _normalize_price_dict helper."""

    def test_all_values_provided(self) -> None:
        result = _normalize_price_dict(
            usd=1.50, usd_foil=3.00, eur=1.20, eur_foil=2.50, source="tcgplayer"
        )
        assert result["usd"] == 1.50
        assert result["usd_foil"] == 3.00
        assert result["eur"] == 1.20
        assert result["eur_foil"] == 2.50
        assert result["source"] == "tcgplayer"

    def test_default_values(self) -> None:
        result = _normalize_price_dict()
        assert result["usd"] is None
        assert result["usd_foil"] is None
        assert result["eur"] is None
        assert result["eur_foil"] is None
        assert result["source"] == "unknown"


class TestSafeFloat:
    """Test the _safe_float helper."""

    def test_valid_float(self) -> None:
        assert _safe_float("1.50") == 1.50

    def test_valid_int(self) -> None:
        assert _safe_float(5) == 5.0

    def test_none_returns_none(self) -> None:
        assert _safe_float(None) is None

    def test_invalid_string_returns_none(self) -> None:
        assert _safe_float("not-a-number") is None

    def test_empty_string_returns_none(self) -> None:
        assert _safe_float("") is None


class TestTCGAPIsClientGetCardPrice:
    """Test TCGAPIsClient.get_card_price method."""

    @pytest.mark.asyncio
    async def test_get_card_price_success(self) -> None:
        fixture = _load_fixture("tcgapis_sol_ring.json")
        response = _mock_response(200, fixture)
        client, _ = _make_tcgapis_client([response])

        result = await client.get_card_price("Sol Ring")

        assert result["usd"] == 1.49
        assert result["source"] == "tcgplayer"

    @pytest.mark.asyncio
    async def test_get_card_price_not_found(self) -> None:
        fixture = _load_fixture("tcgapis_not_found.json")
        response = _mock_response(200, fixture)
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingNotFoundError):
            await client.get_card_price("Nonexistent Card")

    @pytest.mark.asyncio
    async def test_get_card_price_no_api_key(self) -> None:
        client, _ = _make_tcgapis_client(api_key="")

        with pytest.raises(PricingAuthError, match="not configured"):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_auth_error(self) -> None:
        response = _mock_response(401, {"error": "unauthorized"})
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingAuthError, match="Invalid or expired"):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_rate_limited(self) -> None:
        response = _mock_response(429, {})
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingRateLimitError):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_server_error(self) -> None:
        response = _mock_response(500, {})
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingError):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_403_auth_error(self) -> None:
        response = _mock_response(403, {"error": "forbidden"})
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingAuthError):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_404(self) -> None:
        response = _mock_response(404, {"error": "not found"})
        client, _ = _make_tcgapis_client([response])

        with pytest.raises(PricingNotFoundError):
            await client.get_card_price("Sol Ring")


class TestTCGAPIsClientGetCardPricesBatch:
    """Test TCGAPIsClient.get_card_prices_batch method."""

    @pytest.mark.asyncio
    async def test_batch_success(self) -> None:
        fixture1 = _load_fixture("tcgapis_sol_ring.json")
        fixture2 = _load_fixture("tcgapis_not_found.json")
        response1 = _mock_response(200, fixture1)
        response2 = _mock_response(200, fixture2)
        client, _ = _make_tcgapis_client([response1, response2])

        result = await client.get_card_prices_batch(
            ["Sol Ring", "Nonexistent Card"]
        )

        assert "Sol Ring" in result
        assert "Nonexistent Card" not in result
        assert result["Sol Ring"]["usd"] == 1.49

    @pytest.mark.asyncio
    async def test_batch_empty_list(self) -> None:
        client, _ = _make_tcgapis_client()

        result = await client.get_card_prices_batch([])

        assert result == {}


class TestTCGAPIsClientContextManager:
    """Test TCGAPIsClient as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        limiter = RateLimiter(rate=1000.0, burst=100)
        async with TCGAPIsClient(
            api_key="test", client=mock_http, rate_limiter=limiter
        ) as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        limiter = RateLimiter(rate=1000.0, burst=100)
        client = TCGAPIsClient(
            api_key="test", client=mock_http, rate_limiter=limiter
        )
        await client.close()
        mock_http.aclose.assert_not_called()


class TestJustTCGClientGetCardPrice:
    """Test JustTCGClient.get_card_price method."""

    @pytest.mark.asyncio
    async def test_get_card_price_success(self) -> None:
        fixture = _load_fixture("justtcg_sol_ring.json")
        response = _mock_response(200, fixture)
        client, _ = _make_justtcg_client([response])

        result = await client.get_card_price("Sol Ring")

        assert result["usd"] == 1.55
        assert result["source"] == "justtcg"

    @pytest.mark.asyncio
    async def test_get_card_price_no_api_key(self) -> None:
        client, _ = _make_justtcg_client(api_key="")

        with pytest.raises(PricingAuthError, match="not configured"):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_auth_error(self) -> None:
        response = _mock_response(401, {"error": "unauthorized"})
        client, _ = _make_justtcg_client([response])

        with pytest.raises(PricingAuthError):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_rate_limited(self) -> None:
        response = _mock_response(429, {})
        client, _ = _make_justtcg_client([response])

        with pytest.raises(PricingRateLimitError):
            await client.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_get_card_price_not_found(self) -> None:
        response = _mock_response(404, {})
        client, _ = _make_justtcg_client([response])

        with pytest.raises(PricingNotFoundError):
            await client.get_card_price("Nonexistent")

    @pytest.mark.asyncio
    async def test_get_card_price_server_error(self) -> None:
        response = _mock_response(500, {})
        client, _ = _make_justtcg_client([response])

        with pytest.raises(PricingError):
            await client.get_card_price("Sol Ring")


class TestJustTCGClientSearchCard:
    """Test JustTCGClient.search_card method."""

    @pytest.mark.asyncio
    async def test_search_card_success(self) -> None:
        fixture = _load_fixture("justtcg_search_sol.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_justtcg_client([response])

        result = await client.search_card("Sol")

        assert len(result) == 2
        assert result[0]["name"] == "Sol Ring"
        assert result[1]["name"] == "Sol Talisman"

    @pytest.mark.asyncio
    async def test_search_card_no_api_key(self) -> None:
        client, _ = _make_justtcg_client(api_key="")

        with pytest.raises(PricingAuthError):
            await client.search_card("Sol")


class TestJustTCGClientContextManager:
    """Test JustTCGClient as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        limiter = RateLimiter(rate=1000.0, burst=100)
        async with JustTCGClient(
            api_key="test", client=mock_http, rate_limiter=limiter
        ) as client:
            assert client is not None


class TestPricingServiceFallback:
    """Test PricingService fallback chain: TCGAPIs -> JustTCG -> Scryfall."""

    @pytest.mark.asyncio
    async def test_tcgapis_success_no_fallback(self) -> None:
        """When TCGAPIs succeeds, JustTCG and Scryfall are not called."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            return_value=_normalize_price_dict(usd=1.49, source="tcgplayer")
        )
        tcgapis.close = AsyncMock()

        justtcg = AsyncMock(spec=JustTCGClient)
        justtcg.close = AsyncMock()

        service = PricingService(
            tcgapis_client=tcgapis, justtcg_client=justtcg
        )

        result = await service.get_card_price("Sol Ring")

        assert result["usd"] == 1.49
        assert result["source"] == "tcgplayer"
        tcgapis.get_card_price.assert_called_once_with("Sol Ring")
        justtcg.get_card_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_justtcg_on_tcgapis_failure(self) -> None:
        """When TCGAPIs fails, falls back to JustTCG."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            side_effect=PricingError("TCGAPIs down")
        )
        tcgapis.close = AsyncMock()

        justtcg = AsyncMock(spec=JustTCGClient)
        justtcg.get_card_price = AsyncMock(
            return_value=_normalize_price_dict(usd=1.55, source="justtcg")
        )
        justtcg.close = AsyncMock()

        service = PricingService(
            tcgapis_client=tcgapis, justtcg_client=justtcg
        )

        result = await service.get_card_price("Sol Ring")

        assert result["usd"] == 1.55
        assert result["source"] == "justtcg"

    @pytest.mark.asyncio
    async def test_fallback_to_scryfall_when_both_fail(self) -> None:
        """When TCGAPIs and JustTCG fail, falls back to Scryfall."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            side_effect=PricingError("TCGAPIs down")
        )
        tcgapis.close = AsyncMock()

        justtcg = AsyncMock(spec=JustTCGClient)
        justtcg.get_card_price = AsyncMock(
            side_effect=PricingError("JustTCG down")
        )
        justtcg.close = AsyncMock()

        scryfall = AsyncMock()
        scryfall.get_card_prices = AsyncMock(
            return_value={"usd": 1.50, "usd_foil": None, "eur": 1.20, "eur_foil": None}
        )

        service = PricingService(
            tcgapis_client=tcgapis,
            justtcg_client=justtcg,
            scryfall_client=scryfall,
        )

        result = await service.get_card_price(
            "Sol Ring", scryfall_id="f1d1e196"
        )

        assert result["usd"] == 1.50
        assert result["source"] == "scryfall"

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises_error(self) -> None:
        """When all sources fail, raises PricingError."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            side_effect=PricingError("TCGAPIs down")
        )
        tcgapis.close = AsyncMock()

        justtcg = AsyncMock(spec=JustTCGClient)
        justtcg.get_card_price = AsyncMock(
            side_effect=PricingError("JustTCG down")
        )
        justtcg.close = AsyncMock()

        scryfall = AsyncMock()
        scryfall.get_card_prices = AsyncMock(
            side_effect=Exception("Scryfall down")
        )

        service = PricingService(
            tcgapis_client=tcgapis,
            justtcg_client=justtcg,
            scryfall_client=scryfall,
        )

        with pytest.raises(PricingError, match="All pricing sources failed"):
            await service.get_card_price("Sol Ring", scryfall_id="f1d1e196")

    @pytest.mark.asyncio
    async def test_no_clients_configured_raises_error(self) -> None:
        """When no clients are configured, raises PricingError."""
        service = PricingService()

        with pytest.raises(PricingError, match="All pricing sources failed"):
            await service.get_card_price("Sol Ring")

    @pytest.mark.asyncio
    async def test_scryfall_fallback_skipped_without_scryfall_id(self) -> None:
        """Scryfall fallback requires a scryfall_id to be provided."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            side_effect=PricingError("TCGAPIs down")
        )
        tcgapis.close = AsyncMock()

        scryfall = AsyncMock()
        scryfall.get_card_prices = AsyncMock(
            return_value={"usd": 1.50}
        )

        service = PricingService(
            tcgapis_client=tcgapis,
            scryfall_client=scryfall,
        )

        # Without scryfall_id, Scryfall fallback should be skipped
        with pytest.raises(PricingError, match="All pricing sources failed"):
            await service.get_card_price("Sol Ring")

        scryfall.get_card_prices.assert_not_called()


class TestPricingServiceBatch:
    """Test PricingService.get_card_prices_batch method."""

    @pytest.mark.asyncio
    async def test_batch_success(self) -> None:
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            return_value=_normalize_price_dict(usd=1.49, source="tcgplayer")
        )
        tcgapis.close = AsyncMock()

        service = PricingService(tcgapis_client=tcgapis)

        cards = [
            {"name": "Sol Ring"},
            {"name": "Command Tower"},
        ]
        result = await service.get_card_prices_batch(cards)

        assert len(result) == 2
        assert "Sol Ring" in result
        assert "Command Tower" in result

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self) -> None:
        """Cards that fail are omitted from the result."""
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.get_card_price = AsyncMock(
            side_effect=[
                _normalize_price_dict(usd=1.49, source="tcgplayer"),
                PricingError("Not found"),
            ]
        )
        tcgapis.close = AsyncMock()

        service = PricingService(tcgapis_client=tcgapis)

        cards = [
            {"name": "Sol Ring"},
            {"name": "Nonexistent Card"},
        ]
        result = await service.get_card_prices_batch(cards)

        assert len(result) == 1
        assert "Sol Ring" in result
        assert "Nonexistent Card" not in result

    @pytest.mark.asyncio
    async def test_batch_empty_list(self) -> None:
        service = PricingService()

        result = await service.get_card_prices_batch([])

        assert result == {}


class TestPricingServiceContextManager:
    """Test PricingService as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_clients(self) -> None:
        tcgapis = AsyncMock(spec=TCGAPIsClient)
        tcgapis.close = AsyncMock()
        justtcg = AsyncMock(spec=JustTCGClient)
        justtcg.close = AsyncMock()

        async with PricingService(
            tcgapis_client=tcgapis, justtcg_client=justtcg
        ):
            pass

        tcgapis.close.assert_called_once()
        justtcg.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_none_clients(self) -> None:
        """No error when closing with None clients."""
        async with PricingService():
            pass
