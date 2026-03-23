"""Tests for enhanced EDHREC API functions (all HTTP calls mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mtg_deck_maker.api.edhrec import (
    fetch_commander_full_data,
    fetch_training_commanders,
)


def _make_mock_client(*, response_data=None, side_effect=None):
    """Build a mock httpx.AsyncClient with preset response or error."""
    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# Sample EDHREC commander page response with varying inclusion rates
_COMMANDER_DATA = {
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
                    "name": "Niche Card",
                    "num_decks": 100,
                    "potential_decks": 20000,
                    "inclusion": 0,  # 0% inclusion
                    "synergy": 0.01,
                },
            ],
        },
    ],
}

# Sample EDHREC training commanders response
_TRAINING_COMMANDERS_DATA = {
    "cardlists": [
        {
            "tag": "commanders",
            "cardviews": [
                {"name": "Atraxa, Praetors' Voice", "num_decks": 12000},
                {"name": "Korvold, Fae-Cursed King", "num_decks": 8000},
                {"name": "Obscure Commander", "num_decks": 200},
            ],
        },
    ],
}


class TestFetchCommanderFullData:
    """Tests for fetch_commander_full_data."""

    @pytest.mark.asyncio
    async def test_returns_filtered_results(self) -> None:
        """Should return cards meeting the min_inclusion threshold."""
        mock_client = _make_mock_client(response_data=_COMMANDER_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_full_data("Atraxa", min_inclusion=0.01)

        # Doubling Season (0.45) and Hardened Scales (0.40) pass; Niche Card (0.0) does not
        assert len(result) == 2
        names = {r.card_name for r in result}
        assert "Doubling Season" in names
        assert "Hardened Scales" in names

    @pytest.mark.asyncio
    async def test_high_threshold_returns_fewer(self) -> None:
        """Higher threshold should filter out more cards."""
        mock_client = _make_mock_client(response_data=_COMMANDER_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_full_data("Atraxa", min_inclusion=0.42)

        # Only Doubling Season (0.45) passes 0.42 threshold
        assert len(result) == 1
        assert result[0].card_name == "Doubling Season"

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self) -> None:
        """HTTP errors should propagate graceful empty list from fetch_commander_data."""
        mock_client = _make_mock_client(side_effect=Exception("HTTP 500"))
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_full_data("Bad Commander")

        assert result == []

    @pytest.mark.asyncio
    async def test_min_inclusion_zero_returns_all(self) -> None:
        """min_inclusion=0.0 should return all cards including 0% inclusion."""
        mock_client = _make_mock_client(response_data=_COMMANDER_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_commander_full_data("Atraxa", min_inclusion=0.0)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_default_min_inclusion_is_001(self) -> None:
        """Default min_inclusion should be 0.01, filtering out 0% cards."""
        mock_client = _make_mock_client(response_data=_COMMANDER_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Call without explicit min_inclusion to use default
            result = await fetch_commander_full_data("Atraxa")

        # Niche Card has 0% inclusion, should be filtered out by default 0.01
        names = {r.card_name for r in result}
        assert "Niche Card" not in names
        assert len(result) == 2


class TestFetchTrainingCommanders:
    """Tests for fetch_training_commanders."""

    @pytest.mark.asyncio
    async def test_returns_list_of_names(self) -> None:
        """Should return commander names from the response."""
        mock_client = _make_mock_client(response_data=_TRAINING_COMMANDERS_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_training_commanders(min_decks=100)

        assert isinstance(result, list)
        assert "Atraxa, Praetors' Voice" in result
        assert "Korvold, Fae-Cursed King" in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self) -> None:
        """HTTP errors should return empty list."""
        mock_client = _make_mock_client(side_effect=Exception("Connection refused"))
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_training_commanders()

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_by_min_decks(self) -> None:
        """Should exclude commanders below the min_decks threshold."""
        mock_client = _make_mock_client(response_data=_TRAINING_COMMANDERS_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_training_commanders(min_decks=500)

        assert "Atraxa, Praetors' Voice" in result
        assert "Korvold, Fae-Cursed King" in result
        assert "Obscure Commander" not in result

    @pytest.mark.asyncio
    async def test_handles_missing_data_gracefully(self) -> None:
        """Missing or malformed data should return empty list."""
        mock_client = _make_mock_client(response_data={"unexpected": "format"})
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_training_commanders()

        assert result == []

    @pytest.mark.asyncio
    async def test_default_min_decks_is_500(self) -> None:
        """Default min_decks should be 500, filtering out low-count commanders."""
        mock_client = _make_mock_client(response_data=_TRAINING_COMMANDERS_DATA)
        with patch(
            "mtg_deck_maker.api.edhrec.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Call without explicit min_decks to use default
            result = await fetch_training_commanders()

        # Obscure Commander has 200 decks, should be filtered by default 500
        assert "Obscure Commander" not in result
        assert len(result) == 2
