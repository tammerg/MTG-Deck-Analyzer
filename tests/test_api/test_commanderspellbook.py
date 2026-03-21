"""Tests for the CommanderSpellbook API client.

All HTTP calls are mocked -- no real API requests are made in tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mtg_deck_maker.api.commanderspellbook import (
    CommanderSpellbookError,
    fetch_combos,
    fetch_combos_for_cards,
    load_fallback_combos,
)
from mtg_deck_maker.models.combo import Combo


# -- Sample API response fixtures --

SAMPLE_VARIANT = {
    "id": "abc-123",
    "uses": [
        {"card": {"name": "Exquisite Blood"}},
        {"card": {"name": "Sanguine Bond"}},
    ],
    "produces": [
        {"feature": {"name": "Infinite damage"}},
        {"feature": {"name": "Infinite lifegain"}},
    ],
    "identity": "B",
    "otherPrerequisites": "Both permanents on the battlefield",
    "description": "Whenever you gain life Sanguine Bond deals damage.",
}

SAMPLE_VARIANT_B = {
    "id": "def-456",
    "uses": [
        {"card": {"name": "Dramatic Reversal"}},
        {"card": {"name": "Isochron Scepter"}},
    ],
    "produces": [
        {"feature": {"name": "Infinite mana"}},
    ],
    "identity": "U",
    "otherPrerequisites": "Mana-producing nonland permanents",
    "description": "Imprint Dramatic Reversal on Isochron Scepter.",
}


def _make_api_response(
    results: list[dict], next_url: str | None = None
) -> dict:
    """Build a paginated API response dict."""
    return {
        "count": len(results),
        "next": next_url,
        "previous": None,
        "results": results,
    }


# === fetch_combos tests ===


class TestFetchCombos:
    @pytest.mark.asyncio
    async def test_fetch_combos_parses_response(self) -> None:
        """fetch_combos should parse API results into Combo objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_response(
            [SAMPLE_VARIANT, SAMPLE_VARIANT_B]
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.commanderspellbook.httpx.AsyncClient",
            return_value=mock_client,
        ):
            combos = await fetch_combos(limit=10)

        assert len(combos) == 2
        assert combos[0].combo_id == "abc-123"
        assert combos[0].card_names == ["Exquisite Blood", "Sanguine Bond"]
        assert "Infinite damage" in combos[0].result
        assert combos[0].color_identity == ["B"]
        assert combos[1].combo_id == "def-456"
        assert combos[1].card_names == [
            "Dramatic Reversal",
            "Isochron Scepter",
        ]

    @pytest.mark.asyncio
    async def test_fetch_combos_handles_error(self) -> None:
        """fetch_combos should raise CommanderSpellbookError on HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception(
            "Server Error"
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.commanderspellbook.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(CommanderSpellbookError):
                await fetch_combos(limit=10)

    @pytest.mark.asyncio
    async def test_fetch_combos_paginates(self) -> None:
        """fetch_combos should follow pagination links."""
        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = _make_api_response(
            [SAMPLE_VARIANT],
            next_url="https://backend.commanderspellbook.com/variants/?page=2",
        )
        page1_response.raise_for_status = MagicMock()

        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = _make_api_response(
            [SAMPLE_VARIANT_B]
        )
        page2_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[page1_response, page2_response]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.commanderspellbook.httpx.AsyncClient",
            return_value=mock_client,
        ):
            combos = await fetch_combos()

        assert len(combos) == 2
        assert mock_client.get.call_count == 2


# === fetch_combos_for_cards tests ===


class TestFetchCombosForCards:
    @pytest.mark.asyncio
    async def test_fetch_combos_for_cards_filters(self) -> None:
        """fetch_combos_for_cards should return only combos containing
        the specified cards."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_response(
            [SAMPLE_VARIANT]
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.commanderspellbook.httpx.AsyncClient",
            return_value=mock_client,
        ):
            combos = await fetch_combos_for_cards(["Exquisite Blood"])

        assert len(combos) == 1
        assert "Exquisite Blood" in combos[0].card_names

    @pytest.mark.asyncio
    async def test_fetch_combos_for_cards_empty(self) -> None:
        """fetch_combos_for_cards with no matching cards should return []."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_api_response([])
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "mtg_deck_maker.api.commanderspellbook.httpx.AsyncClient",
            return_value=mock_client,
        ):
            combos = await fetch_combos_for_cards(["Nonexistent Card"])

        assert combos == []


# === Fallback loading tests ===


class TestLoadFallbackCombos:
    def test_load_fallback_combos(self) -> None:
        """load_fallback_combos should return Combo objects from the JSON file."""
        combos = load_fallback_combos()
        assert len(combos) > 0
        assert all(isinstance(c, Combo) for c in combos)

    def test_fallback_combos_have_required_fields(self) -> None:
        """Each fallback combo should have a combo_id and card_names."""
        combos = load_fallback_combos()
        for combo in combos:
            assert combo.combo_id != ""
            assert len(combo.card_names) >= 2
            assert combo.result != ""
