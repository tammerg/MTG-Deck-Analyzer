"""Tests for the analyze service module."""

from __future__ import annotations

import os
import tempfile

import pytest

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.services.analyze_service import AnalyzeService


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    colors: list[str] | None = None,
    card_id: int | None = None,
) -> Card:
    return Card(
        oracle_id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=[],
        keywords=[],
        id=card_id,
    )


class TestAnalyzeService:
    def test_analyze_from_cards(self):
        """Should analyze a list of Card objects."""
        service = AnalyzeService()
        cards = [
            _make_card(
                "Sol Ring",
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                cmc=1.0,
                card_id=1,
            ),
            _make_card(
                "Lightning Bolt",
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                cmc=1.0,
                colors=["R"],
                card_id=2,
            ),
        ]

        analysis = service.analyze_from_cards(cards)
        assert isinstance(analysis, DeckAnalysis)
        assert analysis.avg_cmc > 0

    def test_analyze_from_cards_empty(self):
        """Should handle empty card list."""
        service = AnalyzeService()
        analysis = service.analyze_from_cards([])
        assert isinstance(analysis, DeckAnalysis)
        assert analysis.avg_cmc == 0.0

    def test_analyze_from_csv(self, tmp_path):
        """Should analyze a CSV file."""
        csv_content = (
            "Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes\n"
            "1,Sol Ring,ramp,{1},1,Artifact,3.00,,,\n"
            "1,Swords to Plowshares,removal,{W},1,Instant,2.00,,,\n"
        )
        csv_file = tmp_path / "test_deck.csv"
        csv_file.write_text(csv_content)

        service = AnalyzeService()
        analysis = service.analyze_from_csv(str(csv_file))
        assert isinstance(analysis, DeckAnalysis)

    def test_analyze_from_csv_file_not_found(self):
        """Should raise ValueError for missing file."""
        service = AnalyzeService()
        with pytest.raises(ValueError, match="Import errors"):
            service.analyze_from_csv("/nonexistent/path/to/file.csv")

    def test_analyze_from_csv_empty_file(self, tmp_path):
        """Should raise ValueError for empty file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        service = AnalyzeService()
        with pytest.raises(ValueError, match="No cards found"):
            service.analyze_from_csv(str(csv_file))
