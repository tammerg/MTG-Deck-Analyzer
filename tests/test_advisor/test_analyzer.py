"""Tests for the deck analyzer module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.advisor.analyzer import (
    DeckAnalysis,
    analyze_deck,
    _identify_weak_categories,
    _identify_strong_categories,
    _generate_recommendations,
    _compute_color_distribution,
)
from mtg_deck_maker.engine.categories import Category, bulk_categorize
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


def _make_ramp_card(name: str, card_id: int) -> Card:
    return _make_card(
        name,
        type_line="Sorcery",
        oracle_text="Search your library for a basic land card.",
        mana_cost="{1}{G}",
        cmc=2.0,
        colors=["G"],
        card_id=card_id,
    )


def _make_draw_card(name: str, card_id: int) -> Card:
    return _make_card(
        name,
        type_line="Instant",
        oracle_text="Draw two cards.",
        mana_cost="{1}{U}",
        cmc=2.0,
        colors=["U"],
        card_id=card_id,
    )


def _make_removal_card(name: str, card_id: int) -> Card:
    return _make_card(
        name,
        type_line="Instant",
        oracle_text="Destroy target creature.",
        mana_cost="{1}{B}",
        cmc=2.0,
        colors=["B"],
        card_id=card_id,
    )


def _make_board_wipe_card(name: str, card_id: int) -> Card:
    return _make_card(
        name,
        type_line="Sorcery",
        oracle_text="Destroy all creatures.",
        mana_cost="{2}{W}{W}",
        cmc=4.0,
        colors=["W"],
        card_id=card_id,
    )


def _make_land_card(name: str, card_id: int) -> Card:
    return _make_card(
        name,
        type_line="Basic Land",
        oracle_text="",
        mana_cost="",
        cmc=0.0,
        card_id=card_id,
    )


def _make_creature_card(name: str, card_id: int, cmc: float = 3.0) -> Card:
    return _make_card(
        name,
        type_line="Creature - Human",
        oracle_text="",
        mana_cost="{2}{W}",
        cmc=cmc,
        colors=["W"],
        card_id=card_id,
    )


# === DeckAnalysis Dataclass ===


class TestDeckAnalysisDataclass:
    def test_default_values(self):
        """DeckAnalysis should have sensible defaults."""
        analysis = DeckAnalysis()
        assert analysis.category_breakdown == {}
        assert analysis.mana_curve == {}
        assert analysis.color_distribution == {}
        assert analysis.avg_cmc == 0.0
        assert analysis.weak_categories == []
        assert analysis.strong_categories == []
        assert analysis.total_price == 0.0
        assert analysis.power_level == 1
        assert analysis.recommendations == []


# === Color Distribution ===


class TestColorDistribution:
    def test_single_color(self):
        """Cards with one color should be counted."""
        cards = [
            _make_card("A", colors=["W"]),
            _make_card("B", colors=["W"]),
            _make_card("C", colors=["U"]),
        ]
        dist = _compute_color_distribution(cards)
        assert dist["W"] == 2
        assert dist["U"] == 1

    def test_multicolor_card(self):
        """Multicolor cards should count for each color."""
        cards = [_make_card("A", colors=["W", "U"])]
        dist = _compute_color_distribution(cards)
        assert dist["W"] == 1
        assert dist["U"] == 1

    def test_colorless(self):
        """Colorless cards should be counted under 'Colorless'."""
        cards = [_make_card("A", colors=[])]
        dist = _compute_color_distribution(cards)
        assert dist["Colorless"] == 1

    def test_empty_deck(self):
        """Empty card list should return empty distribution."""
        assert _compute_color_distribution([]) == {}


# === Weak Category Detection ===


class TestWeakCategoryDetection:
    def test_all_below_minimum(self):
        """All categories below minimum should be flagged."""
        counts: dict[str, int] = {
            Category.RAMP.value: 3,
            Category.CARD_DRAW.value: 2,
            Category.REMOVAL.value: 1,
            Category.BOARD_WIPE.value: 0,
        }
        weak = _identify_weak_categories(counts)
        assert Category.RAMP.value in weak
        assert Category.CARD_DRAW.value in weak
        assert Category.REMOVAL.value in weak
        assert Category.BOARD_WIPE.value in weak

    def test_all_above_minimum(self):
        """No categories should be weak when all are above minimum."""
        counts: dict[str, int] = {
            Category.RAMP.value: 10,
            Category.CARD_DRAW.value: 10,
            Category.REMOVAL.value: 7,
            Category.BOARD_WIPE.value: 3,
        }
        weak = _identify_weak_categories(counts)
        assert weak == []

    def test_partial_weakness(self):
        """Only categories below minimum should be flagged."""
        counts: dict[str, int] = {
            Category.RAMP.value: 10,
            Category.CARD_DRAW.value: 3,
            Category.REMOVAL.value: 7,
            Category.BOARD_WIPE.value: 0,
        }
        weak = _identify_weak_categories(counts)
        assert Category.CARD_DRAW.value in weak
        assert Category.BOARD_WIPE.value in weak
        assert Category.RAMP.value not in weak
        assert Category.REMOVAL.value not in weak

    def test_missing_categories(self):
        """Missing categories should count as 0 and be flagged."""
        counts: dict[str, int] = {}
        weak = _identify_weak_categories(counts)
        assert len(weak) == 4  # All four tracked categories


# === Strong Category Detection ===


class TestStrongCategoryDetection:
    def test_strong_ramp(self):
        """Ramp at 150% of minimum should be flagged as strong."""
        counts = {Category.RAMP.value: 12}
        strong = _identify_strong_categories(counts)
        assert Category.RAMP.value in strong

    def test_not_strong_at_exact_minimum(self):
        """Category at exactly the minimum is not strong."""
        counts = {Category.RAMP.value: 8}
        strong = _identify_strong_categories(counts)
        assert Category.RAMP.value not in strong

    def test_empty_counts(self):
        """Empty counts should produce no strong categories."""
        assert _identify_strong_categories({}) == []


# === Recommendation Generation ===


class TestRecommendationGeneration:
    def test_ramp_recommendation(self):
        """Should recommend adding ramp when below minimum."""
        counts = {Category.RAMP.value: 3}
        weak = [Category.RAMP.value]
        recs = _generate_recommendations(counts, 3.0, {}, weak)
        assert any("ramp" in r.lower() for r in recs)

    def test_draw_recommendation(self):
        """Should recommend adding card draw when below minimum."""
        counts = {Category.CARD_DRAW.value: 2}
        weak = [Category.CARD_DRAW.value]
        recs = _generate_recommendations(counts, 3.0, {}, weak)
        assert any("card draw" in r.lower() for r in recs)

    def test_removal_recommendation(self):
        """Should recommend adding removal when below minimum."""
        counts = {Category.REMOVAL.value: 1}
        weak = [Category.REMOVAL.value]
        recs = _generate_recommendations(counts, 3.0, {}, weak)
        assert any("removal" in r.lower() for r in recs)

    def test_board_wipe_recommendation_zero(self):
        """Should recommend board wipes when deck has none."""
        counts = {Category.BOARD_WIPE.value: 0}
        weak = [Category.BOARD_WIPE.value]
        recs = _generate_recommendations(counts, 3.0, {}, weak)
        assert any("board wipe" in r.lower() for r in recs)

    def test_high_cmc_recommendation(self):
        """Should warn about high average CMC."""
        recs = _generate_recommendations({}, 4.5, {}, [])
        assert any("cmc" in r.lower() and "high" in r.lower() for r in recs)

    def test_low_cmc_recommendation(self):
        """Should warn about very low average CMC."""
        recs = _generate_recommendations({}, 1.5, {}, [])
        assert any("cmc" in r.lower() and "low" in r.lower() for r in recs)

    def test_no_recommendations_healthy_deck(self):
        """A healthy deck should generate no weakness recommendations."""
        counts = {
            Category.RAMP.value: 10,
            Category.CARD_DRAW.value: 10,
            Category.REMOVAL.value: 7,
            Category.BOARD_WIPE.value: 3,
        }
        recs = _generate_recommendations(counts, 3.0, {}, [])
        assert len(recs) == 0

    def test_top_heavy_mana_curve(self):
        """Should warn when > 20% of cards cost 6+ mana."""
        curve = {0: 2, 1: 3, 2: 5, 3: 5, 4: 3, 5: 2, 6: 8, 7: 7}
        recs = _generate_recommendations({}, 3.0, curve, [])
        assert any("6+ mana" in r for r in recs)


# === Full analyze_deck Integration ===


class TestAnalyzeDeck:
    def test_basic_analysis(self):
        """analyze_deck should return a valid DeckAnalysis."""
        cards = [
            _make_ramp_card(f"Ramp {i}", card_id=i) for i in range(5)
        ] + [
            _make_creature_card(f"Creature {i}", card_id=100 + i)
            for i in range(5)
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert isinstance(analysis, DeckAnalysis)
        assert analysis.avg_cmc > 0
        assert analysis.power_level >= 1
        assert analysis.power_level <= 10

    def test_weak_ramp_detected(self):
        """Deck with fewer than 8 ramp cards should flag ramp as weak."""
        cards = [
            _make_ramp_card(f"Ramp {i}", card_id=i) for i in range(3)
        ] + [
            _make_creature_card(f"Creature {i}", card_id=100 + i)
            for i in range(10)
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert Category.RAMP.value in analysis.weak_categories

    def test_no_board_wipes_detected(self):
        """Deck with no board wipes should flag board_wipe as weak."""
        cards = [
            _make_creature_card(f"Creature {i}", card_id=i)
            for i in range(20)
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert Category.BOARD_WIPE.value in analysis.weak_categories

    def test_category_breakdown_populated(self):
        """Category breakdown should contain entries for categorized cards."""
        cards = [
            _make_ramp_card("Ramp 1", card_id=1),
            _make_draw_card("Draw 1", card_id=2),
            _make_removal_card("Remove 1", card_id=3),
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert Category.RAMP.value in analysis.category_breakdown
        assert Category.CARD_DRAW.value in analysis.category_breakdown
        assert Category.REMOVAL.value in analysis.category_breakdown

    def test_mana_curve_populated(self):
        """Mana curve should have entries for non-land cards."""
        cards = [
            _make_creature_card(f"C{i}", card_id=i, cmc=float(i))
            for i in range(1, 6)
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert sum(analysis.mana_curve.values()) > 0

    def test_empty_deck(self):
        """Empty deck should produce an analysis with defaults."""
        analysis = analyze_deck([], {})
        assert analysis.avg_cmc == 0.0
        assert analysis.category_breakdown == {}

    def test_recommendations_generated_for_weak_deck(self):
        """Weak deck should generate recommendations."""
        cards = [
            _make_creature_card(f"Creature {i}", card_id=i)
            for i in range(15)
        ]
        categories = bulk_categorize(cards)
        analysis = analyze_deck(cards, categories)

        assert len(analysis.recommendations) > 0
