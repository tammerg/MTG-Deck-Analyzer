"""Tests for the budget efficiency metric module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.metrics.budget_efficiency import budget_efficiency
from mtg_deck_maker.models.deck import Deck, DeckCard


def _make_card(
    name: str,
    price: float,
    *,
    category: str = "creature",
    is_commander: bool = False,
    is_companion: bool = False,
    quantity: int = 1,
) -> DeckCard:
    """Helper to build a DeckCard with sensible defaults."""
    return DeckCard(
        card_id=0,
        card_name=name,
        price=price,
        category=category,
        is_commander=is_commander,
        is_companion=is_companion,
        quantity=quantity,
    )


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def deck_within_budget() -> Deck:
    """A deck whose mainboard nonland cards cost less than the budget."""
    return Deck(
        name="Under Budget",
        budget_target=100.0,
        cards=[
            _make_card("Commander A", 5.0, is_commander=True),
            _make_card("Sol Ring", 3.0, category="ramp"),
            _make_card("Counterspell", 1.50, category="counter"),
            _make_card("Command Tower", 2.0, category="land"),
            _make_card("Swords to Plowshares", 4.0, category="removal"),
        ],
    )


@pytest.fixture
def deck_over_budget() -> Deck:
    """A deck whose mainboard nonland cards exceed the budget."""
    return Deck(
        name="Over Budget",
        budget_target=5.0,
        cards=[
            _make_card("Commander B", 10.0, is_commander=True),
            _make_card("Mana Crypt", 150.0, category="ramp"),
            _make_card("Force of Will", 80.0, category="counter"),
        ],
    )


@pytest.fixture
def deck_no_budget() -> Deck:
    """A deck with no budget target set."""
    return Deck(
        name="No Budget",
        budget_target=None,
        cards=[
            _make_card("Commander C", 2.0, is_commander=True),
            _make_card("Lightning Bolt", 0.25, category="removal"),
            _make_card("Brainstorm", 1.00, category="draw"),
        ],
    )


@pytest.fixture
def empty_deck() -> Deck:
    """A deck with no cards at all."""
    return Deck(name="Empty", budget_target=50.0)


@pytest.fixture
def deck_with_price_spread() -> Deck:
    """A deck with cards across all price brackets."""
    return Deck(
        name="Price Spread",
        budget_target=500.0,
        cards=[
            _make_card("Commander X", 5.0, is_commander=True),
            # bulk: < $0.50
            _make_card("Bulk Card A", 0.10, category="creature"),
            _make_card("Bulk Card B", 0.49, category="creature"),
            # budget: $0.50 - $2.00
            _make_card("Budget Card A", 0.50, category="creature"),
            _make_card("Budget Card B", 1.99, category="creature"),
            # mid: $2.00 - $10.00
            _make_card("Mid Card A", 2.00, category="creature"),
            _make_card("Mid Card B", 9.99, category="creature"),
            # premium: $10.00 - $30.00
            _make_card("Premium Card A", 10.00, category="creature"),
            _make_card("Premium Card B", 29.99, category="creature"),
            # chase: > $30.00
            _make_card("Chase Card A", 31.00, category="creature"),
            _make_card("Chase Card B", 100.00, category="creature"),
            # land should be excluded
            _make_card("Fancy Land", 50.0, category="land"),
        ],
    )


@pytest.fixture
def edhrec_data() -> dict[str, float]:
    """Sample EDHREC inclusion-rate data."""
    return {
        "Sol Ring": 0.90,
        "Counterspell": 0.60,
        "Swords to Plowshares": 0.75,
        "Lightning Bolt": 0.30,
        "Brainstorm": 0.55,
    }


# -- basic total_spent / budget_utilization -----------------------------------


class TestBudgetUtilization:
    def test_within_budget(self, deck_within_budget: Deck) -> None:
        result = budget_efficiency(deck_within_budget)
        # mainboard nonland: Sol Ring (3) + Counterspell (1.5) + StP (4) = 8.5
        assert result.total_spent == pytest.approx(8.5)
        assert result.budget_target == 100.0
        assert result.budget_utilization == pytest.approx(8.5 / 100.0)

    def test_over_budget(self, deck_over_budget: Deck) -> None:
        result = budget_efficiency(deck_over_budget)
        # mainboard nonland: Mana Crypt (150) + Force of Will (80) = 230
        assert result.total_spent == pytest.approx(230.0)
        assert result.budget_target == 5.0
        assert result.budget_utilization == pytest.approx(230.0 / 5.0)
        assert result.budget_utilization > 1.0

    def test_no_budget_target(self, deck_no_budget: Deck) -> None:
        result = budget_efficiency(deck_no_budget)
        assert result.budget_target is None
        assert result.budget_utilization is None

    def test_empty_deck(self, empty_deck: Deck) -> None:
        result = budget_efficiency(empty_deck)
        assert result.total_spent == 0.0
        assert result.avg_price_per_card == 0.0
        assert result.budget_utilization == pytest.approx(0.0)
        assert result.quality_per_dollar is None
        assert result.most_expensive == []
        assert all(v == 0 for v in result.price_distribution.values())


# -- avg_price_per_card -------------------------------------------------------


class TestAvgPrice:
    def test_average_price(self, deck_within_budget: Deck) -> None:
        result = budget_efficiency(deck_within_budget)
        # 3 mainboard nonland cards, total 8.5
        assert result.avg_price_per_card == pytest.approx(8.5 / 3.0)

    def test_excludes_commanders_and_lands(self, deck_within_budget: Deck) -> None:
        result = budget_efficiency(deck_within_budget)
        # Commander (5.0) and Command Tower (2.0) excluded
        assert result.total_spent == pytest.approx(8.5)

    def test_excludes_companions(self) -> None:
        deck = Deck(
            name="Companion Test",
            cards=[
                _make_card("Cmdr", 5.0, is_commander=True),
                _make_card("Companion", 8.0, is_companion=True),
                _make_card("Bear", 0.50, category="creature"),
            ],
        )
        result = budget_efficiency(deck)
        assert result.total_spent == pytest.approx(0.50)

    def test_respects_quantity(self) -> None:
        deck = Deck(
            name="Qty Test",
            cards=[
                _make_card("Bear", 2.0, category="creature", quantity=4),
            ],
        )
        result = budget_efficiency(deck)
        assert result.total_spent == pytest.approx(8.0)
        assert result.avg_price_per_card == pytest.approx(2.0)


# -- quality_per_dollar -------------------------------------------------------


class TestQualityPerDollar:
    def test_with_edhrec_data(
        self, deck_within_budget: Deck, edhrec_data: dict[str, float]
    ) -> None:
        result = budget_efficiency(deck_within_budget, edhrec_inclusion=edhrec_data)
        assert result.quality_per_dollar is not None
        # avg inclusion = (0.90 + 0.60 + 0.75) / 3 = 0.75
        # avg price = 8.5 / 3
        expected = 0.75 / (8.5 / 3.0)
        assert result.quality_per_dollar == pytest.approx(expected)

    def test_without_edhrec_data(self, deck_within_budget: Deck) -> None:
        result = budget_efficiency(deck_within_budget)
        assert result.quality_per_dollar is None

    def test_partial_edhrec_data(self, deck_within_budget: Deck) -> None:
        """Cards not in edhrec_inclusion default to 0.0 inclusion rate."""
        partial = {"Sol Ring": 0.90}
        result = budget_efficiency(deck_within_budget, edhrec_inclusion=partial)
        assert result.quality_per_dollar is not None
        # avg inclusion = (0.90 + 0.0 + 0.0) / 3 = 0.30
        expected = 0.30 / (8.5 / 3.0)
        assert result.quality_per_dollar == pytest.approx(expected)

    def test_empty_edhrec_dict(self, deck_within_budget: Deck) -> None:
        """An empty dict is still 'provided' so quality_per_dollar is computed."""
        result = budget_efficiency(deck_within_budget, edhrec_inclusion={})
        assert result.quality_per_dollar is not None
        assert result.quality_per_dollar == pytest.approx(0.0)


# -- price_distribution -------------------------------------------------------


class TestPriceDistribution:
    def test_all_brackets(self, deck_with_price_spread: Deck) -> None:
        result = budget_efficiency(deck_with_price_spread)
        dist = result.price_distribution
        assert dist["bulk"] == 2
        assert dist["budget"] == 2
        assert dist["mid"] == 2
        assert dist["premium"] == 2
        assert dist["chase"] == 2

    def test_lands_excluded_from_distribution(
        self, deck_with_price_spread: Deck
    ) -> None:
        result = budget_efficiency(deck_with_price_spread)
        # The $50 land should not appear in any bracket
        total_in_dist = sum(result.price_distribution.values())
        assert total_in_dist == 10  # 10 nonland mainboard cards

    def test_empty_distribution(self, empty_deck: Deck) -> None:
        result = budget_efficiency(empty_deck)
        assert result.price_distribution == {
            "bulk": 0,
            "budget": 0,
            "mid": 0,
            "premium": 0,
            "chase": 0,
        }


# -- most_expensive -----------------------------------------------------------


class TestMostExpensive:
    def test_top_five_sorted(self, deck_with_price_spread: Deck) -> None:
        result = budget_efficiency(deck_with_price_spread)
        assert len(result.most_expensive) == 5
        names = [name for name, _ in result.most_expensive]
        assert names[0] == "Chase Card B"
        assert names[1] == "Chase Card A"
        assert names[2] == "Premium Card B"

    def test_fewer_than_five_cards(self) -> None:
        deck = Deck(
            name="Small",
            cards=[
                _make_card("A", 10.0, category="creature"),
                _make_card("B", 5.0, category="creature"),
            ],
        )
        result = budget_efficiency(deck)
        assert len(result.most_expensive) == 2
        assert result.most_expensive[0] == ("A", 10.0)
        assert result.most_expensive[1] == ("B", 5.0)

    def test_excludes_commanders_lands(self, deck_with_price_spread: Deck) -> None:
        result = budget_efficiency(deck_with_price_spread)
        names = [name for name, _ in result.most_expensive]
        assert "Commander X" not in names
        assert "Fancy Land" not in names

    def test_empty_deck_most_expensive(self, empty_deck: Deck) -> None:
        result = budget_efficiency(empty_deck)
        assert result.most_expensive == []
