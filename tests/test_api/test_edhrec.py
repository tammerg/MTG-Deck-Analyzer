"""Tests for the EDHREC API client (all HTTP calls mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mtg_deck_maker.api.edhrec import (
    _commander_name_to_slug,
    fetch_commander_data,
)

class TestCommanderNameToSlug:
    """Tests for the commander name to URL slug conversion."""

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("Atraxa, Praetors' Voice", "atraxa-praetors-voice"),
            ("Krenko", "krenko"),
            ("Thrasios Triton Hero", "thrasios-triton-hero"),
            ("Korvold, Fae-Cursed King", "korvold-fae-cursed-king"),
        ],
        ids=["punctuation", "simple", "multi_word", "special_chars"],
    )
    def test_commander_name_to_slug(self, name, expected) -> None:
        assert _commander_name_to_slug(name) == expected


class TestFetchCommanderData:
    """Tests for fetching and parsing EDHREC commander data."""

    @pytest.mark.asyncio
    async def test_fetch_commander_data_success(self) -> None:
        """Successful fetch should parse card data correctly."""
        mock_data = {
            "cardlists": [
                {
                    "tag": "highsynergycards",
                    "cardviews": [
                        {
                            "name": "Doubling Season",
                            "num_decks": 9000,
                            "potential_decks": 20000,
                            "inclusion": 45,
                            "synergy": 0.12,
                        },
                        {
                            "name": "Hardened Scales",
                            "num_decks": 8000,
                            "potential_decks": 20000,
                            "inclusion": 40,
                            "synergy": 0.15,
                        },
                    ],
                },
                {
                    "tag": "topcards",
                    "cardviews": [
                        {
                            "name": "Sol Ring",
                            "num_decks": 19000,
                            "potential_decks": 20000,
                            "inclusion": 95,
                            "synergy": -0.02,
                        },
                    ],
                },
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_data("Atraxa, Praetors' Voice")

        assert len(result) == 3
        doubling = next(r for r in result if r.card_name == "Doubling Season")
        assert doubling.commander_name == "Atraxa, Praetors' Voice"
        assert doubling.inclusion_rate == 0.45
        assert doubling.num_decks == 9000
        assert doubling.potential_decks == 20000
        assert doubling.synergy_score == 0.12

        sol_ring = next(r for r in result if r.card_name == "Sol Ring")
        assert sol_ring.inclusion_rate == 0.95
        assert sol_ring.synergy_score == -0.02

    @pytest.mark.asyncio
    async def test_fetch_commander_data_http_error(self) -> None:
        """HTTP errors should return an empty list (graceful degradation)."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP 404"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_data("Nonexistent Commander")

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_commander_data_parse_error(self) -> None:
        """Malformed JSON should return an empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_data("Some Commander")

        assert result == []
