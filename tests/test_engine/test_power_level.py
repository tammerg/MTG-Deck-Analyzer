"""Tests for the power level estimator."""

from __future__ import annotations

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.categories import Category, categorize_card, bulk_categorize
from mtg_deck_maker.engine.power_level import (
    estimate_power_level,
    analyze_deck_composition,
    FAST_MANA_CARDS,
)


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


def _build_simple_deck(
    ramp_count: int = 8,
    draw_count: int = 8,
    removal_count: int = 5,
    counter_count: int = 0,
    tutor_count: int = 0,
    fast_mana_names: list[str] | None = None,
    land_count: int = 36,
    avg_cmc: float = 3.0,
) -> tuple[list[Card], dict[int, list[tuple[str, float]]]]:
    """Build a simplified deck for power level testing.

    Returns (cards, categories) suitable for analyze_deck_composition.
    """
    cards: list[Card] = []
    card_id = 1

    # Lands
    for i in range(land_count):
        cards.append(
            _make_card(
                f"Land {i}",
                type_line="Basic Land",
                oracle_text="",
                card_id=card_id,
            )
        )
        card_id += 1

    # Ramp
    for i in range(ramp_count):
        cards.append(
            _make_card(
                f"Ramp Card {i}",
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                mana_cost="{2}",
                cmc=2.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Card draw
    for i in range(draw_count):
        cards.append(
            _make_card(
                f"Draw Card {i}",
                type_line="Instant",
                oracle_text="Draw two cards.",
                mana_cost="{2}{U}",
                cmc=3.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Removal
    for i in range(removal_count):
        cards.append(
            _make_card(
                f"Removal Card {i}",
                type_line="Instant",
                oracle_text="Destroy target creature.",
                mana_cost="{1}{B}",
                cmc=2.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Counterspells
    for i in range(counter_count):
        cards.append(
            _make_card(
                f"Counter Card {i}",
                type_line="Instant",
                oracle_text="Counter target spell.",
                mana_cost="{U}{U}",
                cmc=2.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Tutors
    for i in range(tutor_count):
        cards.append(
            _make_card(
                f"Tutor Card {i}",
                type_line="Sorcery",
                oracle_text="Search your library for a card, put that card into your hand, then shuffle.",
                mana_cost="{1}{B}",
                cmc=2.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Fast mana
    fast_mana_names = fast_mana_names or []
    for name in fast_mana_names:
        cards.append(
            _make_card(
                name,
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                mana_cost="{0}",
                cmc=0.0,
                card_id=card_id,
            )
        )
        card_id += 1

    # Fill remaining with generic creatures at the target avg_cmc
    current_non_land = len(cards) - land_count
    remaining = 100 - len(cards)
    for i in range(remaining):
        cards.append(
            _make_card(
                f"Creature {i}",
                type_line="Creature - Human",
                oracle_text="",
                mana_cost=f"{{{int(avg_cmc)}}}",
                cmc=avg_cmc,
                card_id=card_id,
            )
        )
        card_id += 1

    # Categorize all cards
    categories = bulk_categorize(cards)
    return cards, categories


# === Deck Composition Analysis ===


class TestAnalyzeDeckComposition:
    def test_category_counts(self):
        """Category counts should reflect the cards in the deck."""
        cards, categories = _build_simple_deck(
            ramp_count=10, draw_count=8, removal_count=5
        )
        analysis = analyze_deck_composition(cards, categories)
        cat_counts = analysis["category_counts"]

        assert cat_counts.get(Category.RAMP.value, 0) >= 10
        assert cat_counts.get(Category.CARD_DRAW.value, 0) >= 8
        assert cat_counts.get(Category.REMOVAL.value, 0) >= 5

    def test_average_cmc(self):
        """Average CMC should be computed for non-land cards."""
        cards, categories = _build_simple_deck(avg_cmc=3.0)
        analysis = analyze_deck_composition(cards, categories)
        # The average should be somewhere reasonable
        assert 1.0 < analysis["average_cmc"] < 5.0

    def test_mana_curve_histogram(self):
        """Mana curve should be a dict with CMC buckets 0-7."""
        cards, categories = _build_simple_deck()
        analysis = analyze_deck_composition(cards, categories)
        curve = analysis["mana_curve"]
        assert 0 in curve
        assert 7 in curve
        # Sum of curve should equal non-land cards
        land_count = analysis["category_counts"].get(Category.LAND.value, 0)
        non_land = analysis["total_cards"] - land_count
        assert sum(curve.values()) == non_land

    def test_color_pip_distribution(self):
        """Color pip distribution should count pips from mana costs."""
        cards = [
            _make_card(
                "Bolt",
                type_line="Instant",
                oracle_text="Deal 3 damage.",
                mana_cost="{R}",
                cmc=1.0,
                card_id=1,
            ),
            _make_card(
                "Counterspell",
                type_line="Instant",
                oracle_text="Counter target spell.",
                mana_cost="{U}{U}",
                cmc=2.0,
                card_id=2,
            ),
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck_composition(cards, categories)
        pips = analysis["color_pip_distribution"]
        assert pips.get("R", 0) == 1
        assert pips.get("U", 0) == 2

    def test_interaction_ratio(self):
        """Interaction ratio should reflect removal + counterspells vs total."""
        cards, categories = _build_simple_deck(
            removal_count=6, counter_count=4, land_count=36
        )
        analysis = analyze_deck_composition(cards, categories)
        # 10 interaction cards out of 64 non-land cards
        assert analysis["interaction_ratio"] > 0.0

    def test_ramp_ratio(self):
        """Ramp ratio should reflect ramp cards vs non-land total."""
        cards, categories = _build_simple_deck(ramp_count=10)
        analysis = analyze_deck_composition(cards, categories)
        assert analysis["ramp_ratio"] > 0.0

    def test_fast_mana_count(self):
        """Fast mana cards should be counted."""
        cards, categories = _build_simple_deck(
            fast_mana_names=["Sol Ring", "Mana Crypt"]
        )
        analysis = analyze_deck_composition(cards, categories)
        assert analysis["fast_mana_count"] == 2

    def test_tutor_count(self):
        """Tutor cards should be counted."""
        cards, categories = _build_simple_deck(tutor_count=3)
        analysis = analyze_deck_composition(cards, categories)
        assert analysis["tutor_count"] == 3

    def test_total_cards(self):
        """Total cards should match input."""
        cards, categories = _build_simple_deck()
        analysis = analyze_deck_composition(cards, categories)
        assert analysis["total_cards"] == len(cards)


# === Power Level Estimation ===


class TestEstimatePowerLevel:
    def test_power_level_range(self):
        """Power level should be between 1 and 10."""
        cards, categories = _build_simple_deck()
        analysis = analyze_deck_composition(cards, categories)
        level = estimate_power_level(analysis)
        assert 1 <= level <= 10

    def test_low_power_casual_deck(self):
        """A casual deck with high CMC, no tutors, no fast mana should be low power."""
        cards, categories = _build_simple_deck(
            ramp_count=4,
            draw_count=4,
            removal_count=2,
            counter_count=0,
            tutor_count=0,
            fast_mana_names=[],
            avg_cmc=4.0,
        )
        analysis = analyze_deck_composition(cards, categories)
        analysis["total_price"] = 30.0
        level = estimate_power_level(analysis)
        assert level <= 3

    def test_high_power_optimized_deck(self):
        """An optimized deck with tutors, fast mana, low CMC should be high power."""
        cards, categories = _build_simple_deck(
            ramp_count=12,
            draw_count=10,
            removal_count=7,
            counter_count=5,
            tutor_count=5,
            fast_mana_names=["Sol Ring", "Mana Crypt", "Mana Vault", "Chrome Mox"],
            avg_cmc=2.0,
        )
        analysis = analyze_deck_composition(cards, categories)
        analysis["total_price"] = 800.0
        level = estimate_power_level(analysis)
        assert level >= 8

    def test_mid_power_deck(self):
        """A moderate deck should fall in the middle range."""
        cards, categories = _build_simple_deck(
            ramp_count=8,
            draw_count=8,
            removal_count=5,
            counter_count=2,
            tutor_count=1,
            fast_mana_names=["Sol Ring"],
            avg_cmc=3.0,
        )
        analysis = analyze_deck_composition(cards, categories)
        analysis["total_price"] = 150.0
        level = estimate_power_level(analysis)
        assert 3 <= level <= 7

    def test_price_affects_power(self):
        """Higher price should increase power level (all else equal)."""
        cards, categories = _build_simple_deck(
            ramp_count=8,
            draw_count=8,
            removal_count=5,
        )
        analysis_cheap = analyze_deck_composition(cards, categories)
        analysis_cheap["total_price"] = 30.0

        analysis_expensive = analyze_deck_composition(cards, categories)
        analysis_expensive["total_price"] = 1200.0

        level_cheap = estimate_power_level(analysis_cheap)
        level_expensive = estimate_power_level(analysis_expensive)
        assert level_expensive >= level_cheap

    def test_empty_analysis_returns_minimum(self):
        """An empty analysis dict should return power level 1."""
        level = estimate_power_level({})
        assert level == 1

    def test_cedh_deck(self):
        """A cEDH-style deck should approach power 8-10."""
        cards, categories = _build_simple_deck(
            ramp_count=14,
            draw_count=12,
            removal_count=8,
            counter_count=8,
            tutor_count=6,
            fast_mana_names=[
                "Sol Ring", "Mana Crypt", "Mana Vault",
                "Chrome Mox", "Mox Diamond",
            ],
            avg_cmc=1.8,
            land_count=30,
        )
        analysis = analyze_deck_composition(cards, categories)
        analysis["total_price"] = 2000.0
        level = estimate_power_level(analysis)
        assert level >= 7


# === Fast Mana Cards Constant ===


class TestFastManaCards:
    @pytest.mark.parametrize("name", ["Sol Ring", "Mana Crypt", "Mana Vault"])
    def test_known_fast_mana_present(self, name):
        assert name in FAST_MANA_CARDS

    def test_fast_mana_nonempty_set(self):
        assert isinstance(FAST_MANA_CARDS, (set, frozenset))
        assert len(FAST_MANA_CARDS) >= 5
