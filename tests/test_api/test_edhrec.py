"""Tests for the EDHREC API client (all HTTP calls mocked)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.api.edhrec import (
    _commander_name_to_slug,
    fetch_commander_data,
)
from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData


class TestCommanderNameToSlug:
    """Tests for the commander name to URL slug conversion."""

    def test_commander_name_to_slug(self) -> None:
        """Atraxa, Praetors' Voice should become atraxa-praetors-voice."""
        result = _commander_name_to_slug("Atraxa, Praetors' Voice")
        assert result == "atraxa-praetors-voice"

    def test_commander_name_to_slug_simple(self) -> None:
        """Simple single-word name should lowercase."""
        result = _commander_name_to_slug("Krenko")
        assert result == "krenko"

    def test_commander_name_to_slug_multi_word(self) -> None:
        """Multi-word names should use hyphens."""
        result = _commander_name_to_slug("Thrasios Triton Hero")
        assert result == "thrasios-triton-hero"

    def test_commander_name_to_slug_special_chars(self) -> None:
        """Special characters (commas, apostrophes) should be removed."""
        result = _commander_name_to_slug("Korvold, Fae-Cursed King")
        assert result == "korvold-fae-cursed-king"


class TestFetchCommanderData:
    """Tests for fetching and parsing EDHREC commander data."""

    def _mock_response(self, data: dict) -> MagicMock:
        """Create a mock urllib response with JSON data."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_fetch_commander_data_success(self) -> None:
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
        mock_resp = self._mock_response(mock_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_commander_data("Atraxa, Praetors' Voice")

        assert len(result) == 3
        # Check first card parsed correctly
        doubling = next(r for r in result if r.card_name == "Doubling Season")
        assert doubling.commander_name == "Atraxa, Praetors' Voice"
        assert doubling.inclusion_rate == 0.45
        assert doubling.num_decks == 9000
        assert doubling.potential_decks == 20000
        assert doubling.synergy_score == 0.12

        sol_ring = next(r for r in result if r.card_name == "Sol Ring")
        assert sol_ring.inclusion_rate == 0.95
        assert sol_ring.synergy_score == -0.02

    def test_fetch_commander_data_http_error(self) -> None:
        """HTTP errors should return an empty list (graceful degradation)."""
        with patch(
            "urllib.request.urlopen",
            side_effect=Exception("HTTP 404"),
        ):
            result = fetch_commander_data("Nonexistent Commander")

        assert result == []

    def test_fetch_commander_data_parse_error(self) -> None:
        """Malformed JSON should return an empty list."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not valid json{{"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_commander_data("Some Commander")

        assert result == []

    def test_fetch_commander_data_empty_cardlists(self) -> None:
        """Empty cardlists should return an empty list."""
        mock_data = {"cardlists": []}
        mock_resp = self._mock_response(mock_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_commander_data("Some Commander")

        assert result == []

    def test_fetch_commander_data_missing_cardlists_key(self) -> None:
        """Missing cardlists key should return an empty list."""
        mock_data = {"other_key": "value"}
        mock_resp = self._mock_response(mock_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_commander_data("Some Commander")

        assert result == []
