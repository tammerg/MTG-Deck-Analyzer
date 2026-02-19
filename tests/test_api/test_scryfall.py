"""Tests for the Scryfall API client with mocked HTTP responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from mtg_deck_maker.api.rate_limiter import RateLimiter
from mtg_deck_maker.api.scryfall import (
    ScryfallClient,
    ScryfallError,
    ScryfallNotFoundError,
    ScryfallRateLimitError,
    ScryfallServerError,
    parse_scryfall_card,
    _parse_scryfall_prices,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "scryfall"


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


def _make_client(
    mock_responses: list[httpx.Response] | None = None,
) -> tuple[ScryfallClient, AsyncMock]:
    """Create a ScryfallClient with a mocked httpx.AsyncClient.

    Returns a tuple of (ScryfallClient, mock_request_method) so tests
    can configure and inspect the mock.
    """
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    if mock_responses:
        mock_http.request.side_effect = mock_responses
    # Use a fast rate limiter for tests
    limiter = RateLimiter(rate=1000.0, burst=100)
    client = ScryfallClient(client=mock_http, rate_limiter=limiter)
    return client, mock_http.request


class TestParseScyfallCard:
    """Test parse_scryfall_card helper function."""

    def test_parse_sol_ring(self) -> None:
        data = _load_fixture("card_sol_ring.json")
        card, printing = parse_scryfall_card(data)

        assert card.oracle_id == "9b4cf4ef-0ea4-43f4-b529-9c5de5c3b22c"
        assert card.name == "Sol Ring"
        assert card.type_line == "Artifact"
        assert card.oracle_text == "{T}: Add {C}{C}."
        assert card.mana_cost == "{1}"
        assert card.cmc == 1.0
        assert card.colors == []
        assert card.color_identity == []
        assert card.keywords == []
        assert card.edhrec_rank == 1
        assert card.legal_commander is True
        assert card.legal_brawl is False
        assert card.updated_at == "2026-01-15T00:00:00Z"

        assert printing.scryfall_id == "f1d1e196-1a14-4e18-9136-e34c71f55836"
        assert printing.card_id == 0  # Set to 0 before DB insert
        assert printing.set_code == "C21"
        assert printing.collector_number == "263"
        assert printing.lang == "en"
        assert printing.rarity == "uncommon"
        assert printing.finishes == ["nonfoil"]
        assert printing.tcgplayer_id == 123456
        assert printing.cardmarket_id == 654321
        assert printing.released_at == "2021-04-16"
        assert printing.is_promo is False
        assert printing.is_reprint is True

    def test_parse_multicolor_card(self) -> None:
        data = _load_fixture("card_atraxa.json")
        card, printing = parse_scryfall_card(data)

        assert card.name == "Atraxa, Praetors' Voice"
        assert card.colors == ["W", "U", "B", "G"]
        assert card.color_identity == ["W", "U", "B", "G"]
        assert card.keywords == ["Flying", "Vigilance", "Deathtouch", "Lifelink"]
        assert card.cmc == 4.0
        assert card.legal_commander is True
        assert printing.rarity == "mythic"
        assert printing.set_code == "C16"

    def test_parse_minimal_data(self) -> None:
        """Parsing a card with missing optional fields should use defaults."""
        data = {
            "id": "test-id",
            "oracle_id": "oracle-test",
            "name": "Test Card",
        }
        card, printing = parse_scryfall_card(data)

        assert card.oracle_id == "oracle-test"
        assert card.name == "Test Card"
        assert card.type_line == ""
        assert card.oracle_text == ""
        assert card.mana_cost == ""
        assert card.cmc == 0.0
        assert card.colors == []
        assert card.color_identity == []
        assert card.keywords == []
        assert card.edhrec_rank is None
        assert card.legal_commander is False
        assert card.legal_brawl is False

        assert printing.scryfall_id == "test-id"
        assert printing.set_code == ""
        assert printing.finishes == []
        assert printing.tcgplayer_id is None
        assert printing.cardmarket_id is None

    def test_parse_card_with_multiple_finishes(self) -> None:
        data = _load_fixture("search_paginated_page1.json")["data"][1]
        card, printing = parse_scryfall_card(data)

        assert card.name == "Artifact Beta"
        assert printing.finishes == ["nonfoil", "foil"]


class TestParseScyfallPrices:
    """Test _parse_scryfall_prices helper."""

    def test_parse_prices_from_sol_ring(self) -> None:
        data = _load_fixture("card_sol_ring.json")
        prices = _parse_scryfall_prices(data)

        assert prices["usd"] == 1.50
        assert prices["usd_foil"] is None
        assert prices["usd_etched"] is None
        assert prices["eur"] == 1.20
        assert prices["eur_foil"] is None

    def test_parse_prices_with_no_prices_key(self) -> None:
        prices = _parse_scryfall_prices({})

        assert prices["usd"] is None
        assert prices["usd_foil"] is None
        assert prices["eur"] is None

    def test_parse_prices_with_invalid_value(self) -> None:
        data = {"prices": {"usd": "not-a-number", "usd_foil": "5.00"}}
        prices = _parse_scryfall_prices(data)

        assert prices["usd"] is None
        assert prices["usd_foil"] == 5.00


class TestScryfallClientSearchCards:
    """Test ScryfallClient.search_cards method."""

    @pytest.mark.asyncio
    async def test_search_cards_success(self) -> None:
        fixture = _load_fixture("search_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        result = await client.search_cards("sol ring")

        assert result["total_cards"] == 1
        assert len(result["data"]) == 1
        assert result["data"][0]["name"] == "Sol Ring"
        assert result["has_more"] is False

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "cards/search" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_search_cards_passes_params(self) -> None:
        fixture = _load_fixture("search_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        await client.search_cards(
            "sol ring", page=2, unique="prints", order="released"
        )

        call_kwargs = mock_request.call_args[1]
        params = call_kwargs["params"]
        assert params["q"] == "sol ring"
        assert params["page"] == "2"
        assert params["unique"] == "prints"
        assert params["order"] == "released"

    @pytest.mark.asyncio
    async def test_search_cards_not_found(self) -> None:
        fixture = _load_fixture("card_not_found.json")
        response = _mock_response(404, fixture)
        client, _ = _make_client([response])

        with pytest.raises(ScryfallNotFoundError) as exc_info:
            await client.search_cards("xyznonexistent")

        assert exc_info.value.status_code == 404


class TestScryfallClientSearchCardsAll:
    """Test automatic pagination via search_cards_all."""

    @pytest.mark.asyncio
    async def test_search_cards_all_paginates(self) -> None:
        page1 = _load_fixture("search_paginated_page1.json")
        page2 = _load_fixture("search_paginated_page2.json")
        response1 = _mock_response(200, page1)
        response2 = _mock_response(200, page2)
        client, mock_request = _make_client([response1, response2])

        result = await client.search_cards_all("type:artifact")

        assert len(result) == 3
        assert result[0]["name"] == "Artifact Alpha"
        assert result[1]["name"] == "Artifact Beta"
        assert result[2]["name"] == "Artifact Gamma"
        assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_search_cards_all_single_page(self) -> None:
        fixture = _load_fixture("search_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        result = await client.search_cards_all("sol ring")

        assert len(result) == 1
        assert mock_request.call_count == 1


class TestScryfallClientGetCardByName:
    """Test ScryfallClient.get_card_by_name method."""

    @pytest.mark.asyncio
    async def test_get_card_by_name_exact(self) -> None:
        fixture = _load_fixture("card_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        result = await client.get_card_by_name("Sol Ring", exact=True)

        assert result["name"] == "Sol Ring"
        call_kwargs = mock_request.call_args[1]
        assert "exact" in call_kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_card_by_name_fuzzy(self) -> None:
        fixture = _load_fixture("card_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        result = await client.get_card_by_name("sol rin", exact=False)

        assert result["name"] == "Sol Ring"
        call_kwargs = mock_request.call_args[1]
        assert "fuzzy" in call_kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_card_by_name_not_found(self) -> None:
        fixture = _load_fixture("card_not_found.json")
        response = _mock_response(404, fixture)
        client, _ = _make_client([response])

        with pytest.raises(ScryfallNotFoundError):
            await client.get_card_by_name("Nonexistent Card")


class TestScryfallClientGetCardById:
    """Test ScryfallClient.get_card_by_id method."""

    @pytest.mark.asyncio
    async def test_get_card_by_id_success(self) -> None:
        fixture = _load_fixture("card_sol_ring.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        scryfall_id = "f1d1e196-1a14-4e18-9136-e34c71f55836"
        result = await client.get_card_by_id(scryfall_id)

        assert result["name"] == "Sol Ring"
        assert result["id"] == scryfall_id
        call_args = mock_request.call_args[0]
        assert scryfall_id in call_args[1]

    @pytest.mark.asyncio
    async def test_get_card_by_id_not_found(self) -> None:
        fixture = _load_fixture("card_not_found.json")
        response = _mock_response(404, fixture)
        client, _ = _make_client([response])

        with pytest.raises(ScryfallNotFoundError):
            await client.get_card_by_id("nonexistent-id")


class TestScryfallClientGetBulkData:
    """Test ScryfallClient.get_bulk_data method."""

    @pytest.mark.asyncio
    async def test_get_bulk_data_success(self) -> None:
        fixture = _load_fixture("bulk_data.json")
        response = _mock_response(200, fixture)
        client, _ = _make_client([response])

        result = await client.get_bulk_data()

        assert len(result) == 2
        assert result[0]["type"] == "oracle_cards"
        assert result[1]["type"] == "default_cards"


class TestScryfallClientAutocomplete:
    """Test ScryfallClient.autocomplete method."""

    @pytest.mark.asyncio
    async def test_autocomplete_success(self) -> None:
        fixture = _load_fixture("autocomplete_sol.json")
        response = _mock_response(200, fixture)
        client, _ = _make_client([response])

        result = await client.autocomplete("sol")

        assert len(result) == 5
        assert "Sol Ring" in result
        assert "Sol Talisman" in result

    @pytest.mark.asyncio
    async def test_autocomplete_with_extras(self) -> None:
        fixture = _load_fixture("autocomplete_sol.json")
        response = _mock_response(200, fixture)
        client, mock_request = _make_client([response])

        await client.autocomplete("sol", include_extras=True)

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["include_extras"] == "true"


class TestScryfallClientGetCardPrices:
    """Test ScryfallClient.get_card_prices method."""

    @pytest.mark.asyncio
    async def test_get_card_prices_success(self) -> None:
        fixture = _load_fixture("card_sol_ring.json")
        response = _mock_response(200, fixture)
        client, _ = _make_client([response])

        prices = await client.get_card_prices(
            "f1d1e196-1a14-4e18-9136-e34c71f55836"
        )

        assert prices["usd"] == 1.50
        assert prices["eur"] == 1.20
        assert prices["usd_foil"] is None


class TestScryfallClientErrorHandling:
    """Test error handling for various HTTP status codes."""

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self) -> None:
        response = _mock_response(
            404, {"details": "No card found", "object": "error"}
        )
        client, _ = _make_client([response])

        with pytest.raises(ScryfallNotFoundError) as exc_info:
            await client.get_card_by_name("nonexistent")

        assert exc_info.value.status_code == 404
        assert "No card found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        response = _mock_response(429, {})
        client, _ = _make_client([response])

        with pytest.raises(ScryfallRateLimitError) as exc_info:
            await client.get_card_by_name("Sol Ring")

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_500_raises_server_error(self) -> None:
        response = _mock_response(500, {})
        client, _ = _make_client([response])

        with pytest.raises(ScryfallServerError) as exc_info:
            await client.get_card_by_name("Sol Ring")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_502_raises_server_error(self) -> None:
        response = _mock_response(502, {})
        client, _ = _make_client([response])

        with pytest.raises(ScryfallServerError) as exc_info:
            await client.get_card_by_name("Sol Ring")

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_400_raises_generic_error(self) -> None:
        response = _mock_response(
            400, {"details": "Bad request", "object": "error"}
        )
        client, _ = _make_client([response])

        with pytest.raises(ScryfallError) as exc_info:
            await client.search_cards("")

        assert exc_info.value.status_code == 400
        assert "Bad request" in str(exc_info.value)


class TestScryfallClientContextManager:
    """Test ScryfallClient as an async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_and_closes_client(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        limiter = RateLimiter(rate=1000.0, burst=100)

        async with ScryfallClient(
            client=mock_http, rate_limiter=limiter
        ) as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self) -> None:
        """When client is provided externally, close() should not close it."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        limiter = RateLimiter(rate=1000.0, burst=100)
        client = ScryfallClient(client=mock_http, rate_limiter=limiter)

        await client.close()
        # Should NOT have called aclose since we provided the client
        mock_http.aclose.assert_not_called()
