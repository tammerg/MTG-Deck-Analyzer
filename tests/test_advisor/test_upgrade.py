"""Tests for the upgrade recommender module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.advisor.upgrade import (
    UpgradeRecommendation,
    recommend_upgrades,
    _compute_upgrade_score,
)
from mtg_deck_maker.engine.categories import bulk_categorize
from mtg_deck_maker.models.card import Card


# -- Helper to create test cards --


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    keywords: list[str] | None = None,
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
        keywords=keywords or [],
        id=card_id,
    )


def _make_commander() -> Card:
    return _make_card(
        "Test Commander",
        type_line="Legendary Creature - Human Wizard",
        oracle_text="Whenever you cast an instant or sorcery spell, draw a card.",
        mana_cost="{1}{U}{R}",
        cmc=3.0,
        colors=["U", "R"],
        color_identity=["U", "R"],
        card_id=999,
    )


# === Upgrade Score Computation ===


class TestUpgradeScore:
    def test_positive_synergy_improvement(self):
        """Higher new synergy should produce positive score."""
        score = _compute_upgrade_score(
            old_synergy=0.3,
            new_synergy=0.8,
            old_cmc=4.0,
            new_cmc=2.0,
            new_price=1.0,
        )
        assert score > 0

    def test_negative_synergy_produces_negative_score(self):
        """Lower new synergy should produce negative score."""
        score = _compute_upgrade_score(
            old_synergy=0.8,
            new_synergy=0.3,
            old_cmc=2.0,
            new_cmc=4.0,
            new_price=1.0,
        )
        assert score < 0

    def test_expensive_card_lower_score(self):
        """Same synergy improvement but higher price should give lower score."""
        cheap_score = _compute_upgrade_score(
            old_synergy=0.3, new_synergy=0.8,
            old_cmc=3.0, new_cmc=2.0, new_price=1.0,
        )
        expensive_score = _compute_upgrade_score(
            old_synergy=0.3, new_synergy=0.8,
            old_cmc=3.0, new_cmc=2.0, new_price=10.0,
        )
        assert cheap_score > expensive_score

    def test_zero_price_handled(self):
        """Score should not error on zero price."""
        score = _compute_upgrade_score(
            old_synergy=0.3, new_synergy=0.8,
            old_cmc=3.0, new_cmc=2.0, new_price=0.0,
        )
        # Price floor is 0.01
        assert score > 0

    def test_equal_synergy_zero_score(self):
        """Equal synergy should produce zero score (no improvement)."""
        score = _compute_upgrade_score(
            old_synergy=0.5, new_synergy=0.5,
            old_cmc=3.0, new_cmc=3.0, new_price=1.0,
        )
        assert score == 0.0


# === Recommend Upgrades ===


class TestRecommendUpgrades:
    def test_empty_deck(self):
        """Empty deck should produce no recommendations."""
        recs = recommend_upgrades(
            deck_cards=[],
            budget=50.0,
            card_pool=[_make_card("Pool Card")],
            categories={},
            prices={},
        )
        assert recs == []

    def test_empty_pool(self):
        """Empty card pool should produce no recommendations."""
        deck = [_make_card("Deck Card", card_id=1)]
        recs = recommend_upgrades(
            deck_cards=deck,
            budget=50.0,
            card_pool=[],
            categories=bulk_categorize(deck),
            prices={},
        )
        assert recs == []

    def test_basic_recommendation(self):
        """Should produce recommendations when pool has better options."""
        commander = _make_commander()

        # Weak deck card: creature with no synergy text
        deck_card = _make_card(
            "Weak Creature",
            type_line="Creature - Human",
            oracle_text="",
            mana_cost="{3}{R}",
            cmc=4.0,
            colors=["R"],
            color_identity=["R"],
            card_id=1,
        )

        # Strong pool card: synergistic with commander
        pool_card = _make_card(
            "Better Card",
            type_line="Instant",
            oracle_text="Draw two cards. This spell costs {1} less for each instant or sorcery in your graveyard.",
            mana_cost="{1}{U}",
            cmc=2.0,
            colors=["U"],
            color_identity=["U"],
            card_id=2,
        )

        deck_cards = [deck_card]
        categories = bulk_categorize(deck_cards)
        prices = {"Weak Creature": 0.50, "Better Card": 1.00}

        recs = recommend_upgrades(
            deck_cards=deck_cards,
            budget=50.0,
            card_pool=[pool_card],
            categories=categories,
            prices=prices,
            commander=commander,
        )

        assert len(recs) > 0
        assert all(isinstance(r, UpgradeRecommendation) for r in recs)

    def test_budget_filtering(self):
        """Recommendations should respect budget constraints."""
        deck_card = _make_card(
            "Budget Card",
            type_line="Creature - Human",
            oracle_text="",
            cmc=3.0,
            card_id=1,
        )
        expensive_card = _make_card(
            "Expensive Upgrade",
            type_line="Instant",
            oracle_text="Draw three cards.",
            cmc=2.0,
            card_id=2,
        )

        deck_cards = [deck_card]
        categories = bulk_categorize(deck_cards)
        prices = {"Budget Card": 1.0, "Expensive Upgrade": 100.0}

        recs = recommend_upgrades(
            deck_cards=deck_cards,
            budget=5.0,  # Very low budget
            card_pool=[expensive_card],
            categories=categories,
            prices=prices,
        )

        # With a $5 budget and the card costing $100, the $99 delta exceeds budget
        assert len(recs) == 0

    def test_focus_mode(self):
        """Focus mode should only recommend cards in the focus category."""
        commander = _make_commander()

        deck_card = _make_card(
            "Generic Card",
            type_line="Creature - Human",
            oracle_text="",
            cmc=3.0,
            card_id=1,
        )

        draw_card = _make_card(
            "Draw Spell",
            type_line="Instant",
            oracle_text="Draw two cards.",
            mana_cost="{1}{U}",
            cmc=2.0,
            colors=["U"],
            color_identity=["U"],
        )
        removal_card = _make_card(
            "Kill Spell",
            type_line="Instant",
            oracle_text="Destroy target creature.",
            mana_cost="{1}{B}",
            cmc=2.0,
            colors=["B"],
            color_identity=["B"],
        )

        categories = bulk_categorize([deck_card])
        prices = {"Generic Card": 1.0, "Draw Spell": 2.0, "Kill Spell": 2.0}

        recs = recommend_upgrades(
            deck_cards=[deck_card],
            budget=50.0,
            card_pool=[draw_card, removal_card],
            categories=categories,
            prices=prices,
            commander=commander,
            focus="card_draw",
        )

        # Only draw cards should be recommended
        for rec in recs:
            assert rec.card_in.name == "Draw Spell"

    def test_sorted_by_score_descending(self):
        """Recommendations should be sorted by upgrade_score descending."""
        commander = _make_commander()

        deck_cards = [
            _make_card(f"Deck Card {i}", type_line="Creature", cmc=4.0, card_id=i)
            for i in range(3)
        ]

        pool_cards = [
            _make_card(
                f"Pool Card {i}",
                type_line="Instant",
                oracle_text="Draw a card.",
                cmc=float(i + 1),
            )
            for i in range(3)
        ]

        categories = bulk_categorize(deck_cards)
        prices = {c.name: 1.0 for c in deck_cards + pool_cards}

        recs = recommend_upgrades(
            deck_cards=deck_cards,
            budget=100.0,
            card_pool=pool_cards,
            categories=categories,
            prices=prices,
            commander=commander,
        )

        if len(recs) > 1:
            scores = [r.upgrade_score for r in recs]
            assert scores == sorted(scores, reverse=True)

    def test_no_self_swaps(self):
        """Cards already in the deck should not be in the pool."""
        card = _make_card("Same Card", card_id=1)
        categories = bulk_categorize([card])

        recs = recommend_upgrades(
            deck_cards=[card],
            budget=50.0,
            card_pool=[card],  # Same card in pool
            categories=categories,
            prices={"Same Card": 1.0},
        )

        assert len(recs) == 0

    def test_recommendation_has_reason(self):
        """Each recommendation should have a non-empty reason."""
        commander = _make_commander()
        deck_card = _make_card(
            "Old Card", type_line="Creature", cmc=4.0, card_id=1,
        )
        pool_card = _make_card(
            "New Card",
            type_line="Instant",
            oracle_text="Draw two cards.",
            cmc=2.0,
        )

        categories = bulk_categorize([deck_card])
        prices = {"Old Card": 1.0, "New Card": 1.0}

        recs = recommend_upgrades(
            deck_cards=[deck_card],
            budget=50.0,
            card_pool=[pool_card],
            categories=categories,
            prices=prices,
            commander=commander,
        )

        for rec in recs:
            assert rec.reason != ""
