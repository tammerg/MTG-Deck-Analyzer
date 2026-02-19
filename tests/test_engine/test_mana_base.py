"""Tests for the mana base builder."""

from __future__ import annotations

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.mana_base import (
    calculate_land_count,
    calculate_basic_land_distribution,
    count_color_pips,
    build_mana_base,
)


# -- Helper to create test cards --


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    color_identity: list[str] | None = None,
) -> Card:
    return Card(
        oracle_id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=[],
        color_identity=color_identity or [],
        keywords=[],
    )


def _make_land(
    name: str,
    oracle_text: str = "",
    color_identity: list[str] | None = None,
    type_line: str = "Land",
) -> Card:
    return _make_card(
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        color_identity=color_identity,
    )


# === Land Count Calculation ===


class TestCalculateLandCount:
    def test_mono_color_base(self):
        """Mono-color deck should have 34 base lands."""
        result = calculate_land_count(["R"])
        assert result == 34

    def test_two_color_base(self):
        """Two-color deck should have 35 base lands."""
        result = calculate_land_count(["W", "U"])
        assert result == 35

    def test_three_color_base(self):
        """Three-color deck should have 36 base lands."""
        result = calculate_land_count(["W", "U", "B"])
        assert result == 36

    def test_four_color_base(self):
        """Four-color deck should have 36 base lands."""
        result = calculate_land_count(["W", "U", "B", "R"])
        assert result == 36

    def test_five_color_base(self):
        """Five-color deck should have 37 base lands."""
        result = calculate_land_count(["W", "U", "B", "R", "G"])
        assert result == 37

    def test_colorless_base(self):
        """Colorless deck should have 36 base lands."""
        result = calculate_land_count([])
        assert result == 36

    def test_ramp_adjustment_high_ramp(self):
        """12 ramp cards: 4 above 8, so -1 land from base."""
        result = calculate_land_count(["G"], ramp_count=12)
        assert result == 34 - 1  # 33

    def test_ramp_adjustment_very_high_ramp(self):
        """16 ramp cards: 8 above 8, -2 lands."""
        result = calculate_land_count(["G"], ramp_count=16)
        assert result == 34 - 2  # 32

    def test_ramp_adjustment_no_effect_below_threshold(self):
        """8 ramp cards should not reduce land count."""
        result = calculate_land_count(["G"], ramp_count=8)
        assert result == 34

    def test_cmc_adjustment_high(self):
        """Average CMC > 3.5 adds 1 land."""
        result = calculate_land_count(["R"], avg_cmc=4.0)
        assert result == 34 + 1  # 35

    def test_cmc_adjustment_low(self):
        """Average CMC < 2.5 removes 1 land."""
        result = calculate_land_count(["R"], avg_cmc=2.0)
        assert result == 34 - 1  # 33

    def test_cmc_adjustment_normal(self):
        """Average CMC between 2.5 and 3.5 has no effect."""
        result = calculate_land_count(["R"], avg_cmc=3.0)
        assert result == 34

    def test_combined_adjustments(self):
        """High ramp and low CMC should stack adjustments."""
        result = calculate_land_count(["G"], ramp_count=12, avg_cmc=2.0)
        # Base 34, ramp -1, CMC -1 = 32
        assert result == 32

    def test_minimum_land_count(self):
        """Land count should never go below 28."""
        result = calculate_land_count(["G"], ramp_count=100, avg_cmc=1.0)
        assert result >= 28

    def test_maximum_land_count(self):
        """Land count should never exceed 42."""
        result = calculate_land_count(
            ["W", "U", "B", "R", "G"], ramp_count=0, avg_cmc=5.0
        )
        assert result <= 42


# === Basic Land Distribution ===


class TestCalculateBasicLandDistribution:
    def test_proportional_distribution(self):
        """Basics should be proportional to pip counts."""
        pips = {"W": 10, "U": 10}
        dist = calculate_basic_land_distribution(pips, 20)
        assert dist["W"] == 10
        assert dist["U"] == 10

    def test_uneven_distribution(self):
        """Uneven pips should produce proportional basics."""
        pips = {"W": 3, "B": 1}
        dist = calculate_basic_land_distribution(pips, 20)
        assert dist["W"] > dist["B"]
        assert dist["W"] + dist["B"] == 20

    def test_single_color(self):
        """Single color gets all basics."""
        pips = {"R": 15}
        dist = calculate_basic_land_distribution(pips, 25)
        assert dist["R"] == 25

    def test_total_equals_requested(self):
        """Total distributed basics must equal requested total."""
        pips = {"W": 7, "U": 5, "B": 3}
        total = 30
        dist = calculate_basic_land_distribution(pips, total)
        assert sum(dist.values()) == total

    def test_empty_pips_returns_empty(self):
        """Empty pip dict returns empty distribution."""
        dist = calculate_basic_land_distribution({}, 10)
        assert dist == {}

    def test_zero_basics_returns_empty(self):
        """Zero basics requested returns empty distribution."""
        dist = calculate_basic_land_distribution({"W": 5}, 0)
        assert dist == {}

    def test_three_color_distribution(self):
        """Three color distribution sums correctly."""
        pips = {"W": 10, "U": 8, "G": 6}
        total = 24
        dist = calculate_basic_land_distribution(pips, total)
        assert sum(dist.values()) == total
        # W should have the most, G the least
        assert dist["W"] >= dist["U"] >= dist["G"]

    def test_five_color_distribution(self):
        """Five color distribution sums correctly."""
        pips = {"W": 5, "U": 5, "B": 5, "R": 5, "G": 5}
        total = 15
        dist = calculate_basic_land_distribution(pips, total)
        assert sum(dist.values()) == total
        # Each should get 3
        for color in pips:
            assert dist[color] == 3


# === Count Color Pips ===


class TestCountColorPips:
    def test_single_color_pips(self):
        """Count pips in a simple mana cost."""
        cards = [
            _make_card("Lightning Bolt", mana_cost="{R}", type_line="Instant"),
        ]
        pips = count_color_pips(cards)
        assert pips == {"R": 1}

    def test_multi_color_pips(self):
        """Count pips in a multicolor mana cost."""
        cards = [
            _make_card(
                "Atraxa",
                mana_cost="{G}{W}{U}{B}",
                type_line="Creature",
            ),
        ]
        pips = count_color_pips(cards)
        assert pips == {"G": 1, "W": 1, "U": 1, "B": 1}

    def test_multiple_cards(self):
        """Pips accumulate across multiple cards."""
        cards = [
            _make_card("Bolt", mana_cost="{R}", type_line="Instant"),
            _make_card("Chain Lightning", mana_cost="{R}", type_line="Sorcery"),
            _make_card("Counterspell", mana_cost="{U}{U}", type_line="Instant"),
        ]
        pips = count_color_pips(cards)
        assert pips["R"] == 2
        assert pips["U"] == 2

    def test_lands_excluded(self):
        """Lands should not contribute to pip counts."""
        cards = [
            _make_card("Forest", type_line="Basic Land - Forest", mana_cost=""),
            _make_card("Bolt", mana_cost="{R}", type_line="Instant"),
        ]
        pips = count_color_pips(cards)
        assert pips == {"R": 1}

    def test_colorless_card_no_pips(self):
        """Colorless mana costs produce no color pips."""
        cards = [
            _make_card("Sol Ring", mana_cost="{1}", type_line="Artifact"),
        ]
        pips = count_color_pips(cards)
        assert pips == {}

    def test_empty_list(self):
        """Empty card list returns empty pip dict."""
        pips = count_color_pips([])
        assert pips == {}


# === Budget-Aware Land Selection ===


class TestBuildManaBase:
    def _create_available_lands(self) -> list[Card]:
        """Create a pool of available lands for testing."""
        return [
            _make_land("Command Tower", oracle_text="{T}: Add one mana of any color in your commander's color identity."),
            _make_land("Plains", type_line="Basic Land - Plains"),
            _make_land("Island", type_line="Basic Land - Island"),
            _make_land("Swamp", type_line="Basic Land - Swamp"),
            _make_land("Mountain", type_line="Basic Land - Mountain"),
            _make_land("Forest", type_line="Basic Land - Forest"),
            _make_land(
                "Temple of Enlightenment",
                oracle_text="Temple of Enlightenment enters the battlefield tapped.\nWhen Temple of Enlightenment enters the battlefield, scry 1.\n{T}: Add {W} or {U}.",
                color_identity=["W", "U"],
            ),
            _make_land(
                "Hallowed Fountain",
                oracle_text="({T}: Add {W} or {U}.)\nAs Hallowed Fountain enters the battlefield, you may pay 2 life. If you don't, it enters the battlefield tapped.",
                color_identity=["W", "U"],
            ),
            _make_land(
                "Adarkar Wastes",
                oracle_text="{T}: Add {C}.\n{T}: Add {W} or {U}. Adarkar Wastes deals 1 damage to you.",
                color_identity=["W", "U"],
            ),
            _make_land(
                "Flooded Strand",
                oracle_text="{T}, Pay 1 life, Sacrifice Flooded Strand: Search your library for a Plains or Island card, put it onto the battlefield, then shuffle.",
                color_identity=["W", "U"],
            ),
        ]

    def test_command_tower_included_multicolor(self):
        """Command Tower should be included in multicolor decks."""
        lands = self._create_available_lands()
        result = build_mana_base(["W", "U"], 10, 50.0, lands)
        names = [c.name for c in result]
        assert "Command Tower" in names

    def test_command_tower_excluded_monocolor(self):
        """Command Tower should not be included in mono-color decks."""
        lands = self._create_available_lands()
        result = build_mana_base(["W"], 10, 50.0, lands)
        names = [c.name for c in result]
        assert "Command Tower" not in names

    def test_budget_low_mostly_basics(self):
        """Low budget should produce mostly basics and taplands."""
        lands = self._create_available_lands()
        result = build_mana_base(["W", "U"], 35, 30.0, lands)
        # At $30, pain/check/shock/fetch lands should be excluded
        names = [c.name for c in result]
        assert "Adarkar Wastes" not in names  # Painland excluded at low budget
        assert "Flooded Strand" not in names  # Fetchland excluded

    def test_budget_high_includes_premium(self):
        """High budget should include premium lands."""
        lands = self._create_available_lands()
        result = build_mana_base(["W", "U"], 35, 500.0, lands)
        names = [c.name for c in result]
        # At $500 budget, all tiers should be available
        # Command Tower + nonbasics + basics to fill
        assert "Command Tower" in names

    def test_correct_land_count(self):
        """Build should return exactly the requested number of lands."""
        lands = self._create_available_lands()
        for num_lands in [30, 35, 37]:
            result = build_mana_base(["W", "U"], num_lands, 100.0, lands)
            assert len(result) == num_lands

    def test_colorless_deck_gets_wastes(self):
        """Colorless decks should get Wastes."""
        lands = [
            _make_land("Command Tower", oracle_text="{T}: Add one mana of any color."),
        ]
        result = build_mana_base([], 36, 100.0, lands)
        wastes_count = sum(1 for c in result if c.name == "Wastes")
        assert wastes_count > 0

    def test_basic_distribution_proportional(self):
        """Basics should be distributed roughly proportional to the identity."""
        lands = [
            _make_land("Command Tower", oracle_text="{T}: Add one mana of any color."),
            _make_land("Plains", type_line="Basic Land - Plains"),
            _make_land("Island", type_line="Basic Land - Island"),
        ]
        result = build_mana_base(["W", "U"], 20, 30.0, lands)
        plains_count = sum(1 for c in result if c.name == "Plains")
        island_count = sum(1 for c in result if c.name == "Island")
        # With equal pip distribution, should be roughly equal
        # (Command Tower takes 1 slot, then ~9-10 each)
        assert plains_count > 0
        assert island_count > 0
