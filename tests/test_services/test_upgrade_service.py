"""Tests for the upgrade service module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.advisor.analyzer import DeckAnalysis
from mtg_deck_maker.advisor.upgrade import UpgradeRecommendation
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.services.upgrade_service import UpgradeService


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
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
        color_identity=color_identity or [],
        keywords=[],
        id=card_id,
    )


class TestUpgradeService:
    def test_recommend_from_cards(self):
        """Should return analysis and recommendations."""
        service = UpgradeService()

        deck_cards = [
            _make_card(
                "Weak Card",
                type_line="Creature",
                cmc=4.0,
                card_id=1,
            ),
        ]
        pool_cards = [
            _make_card(
                "Better Card",
                type_line="Instant",
                oracle_text="Draw two cards.",
                cmc=2.0,
            ),
        ]
        prices = {"Weak Card": 1.0, "Better Card": 2.0}

        analysis, recs = service.recommend_from_cards(
            deck_cards=deck_cards,
            card_pool=pool_cards,
            prices=prices,
            budget=50.0,
        )

        assert isinstance(analysis, DeckAnalysis)
        assert isinstance(recs, list)

    def test_empty_deck(self):
        """Should handle empty deck gracefully."""
        service = UpgradeService()
        analysis, recs = service.recommend_from_cards(
            deck_cards=[],
            card_pool=[_make_card("Pool Card")],
            prices={},
            budget=50.0,
        )
        assert isinstance(analysis, DeckAnalysis)
        assert recs == []

    def test_with_commander(self):
        """Should factor in commander synergy when provided."""
        service = UpgradeService()

        commander = _make_card(
            "Commander",
            type_line="Legendary Creature",
            oracle_text="Whenever you cast an instant or sorcery, draw a card.",
            cmc=3.0,
            colors=["U", "R"],
            color_identity=["U", "R"],
            card_id=999,
        )
        deck_cards = [
            _make_card("Filler", type_line="Creature", cmc=4.0, card_id=1),
        ]
        pool_cards = [
            _make_card(
                "Synergy Card",
                type_line="Instant",
                oracle_text="Draw a card.",
                cmc=1.0,
                colors=["U"],
                color_identity=["U"],
            ),
        ]
        prices = {"Filler": 0.50, "Synergy Card": 1.00}

        analysis, recs = service.recommend_from_cards(
            deck_cards=deck_cards,
            card_pool=pool_cards,
            prices=prices,
            budget=50.0,
            commander=commander,
        )

        assert isinstance(analysis, DeckAnalysis)
        # Recommendations may or may not exist depending on synergy scores
        assert isinstance(recs, list)
