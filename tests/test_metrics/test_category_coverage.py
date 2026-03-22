"""Tests for category coverage metric."""

from __future__ import annotations

from mtg_deck_maker.metrics.category_coverage import (
    CategoryCoverageResult,
    CategoryStatus,
    category_coverage,
)
from mtg_deck_maker.models.deck import Deck, DeckCard


def _make_deck(cards: list[DeckCard]) -> Deck:
    """Helper to build a Deck with the given cards."""
    return Deck(name="Test Deck", cards=cards)


def _make_card(
    category: str,
    quantity: int = 1,
    *,
    is_commander: bool = False,
    is_companion: bool = False,
) -> DeckCard:
    """Helper to build a DeckCard with minimal fields."""
    return DeckCard(
        card_id=0,
        quantity=quantity,
        category=category,
        is_commander=is_commander,
        is_companion=is_companion,
    )


class TestCategoryStatus:
    """Verify CategoryStatus dataclass basics."""

    def test_met_when_count_meets_min(self) -> None:
        status = CategoryStatus(count=8, min_target=8, max_target=12, met=True, surplus=0)
        assert status.met is True
        assert status.surplus == 0

    def test_deficit_is_negative_surplus(self) -> None:
        status = CategoryStatus(count=3, min_target=8, max_target=12, met=False, surplus=-5)
        assert status.met is False
        assert status.surplus == -5


class TestEmptyDeck:
    """An empty deck should report 0% coverage and full deficit."""

    def test_empty_deck_all_targets_missed(self) -> None:
        deck = _make_deck([])
        targets = {"ramp": (8, 12), "card_draw": (8, 10)}
        result = category_coverage(deck, targets)

        assert result.overall_pct == 0.0
        assert result.total_deficit == 16  # 8 + 8
        assert len(result.per_category) == 2
        for status in result.per_category.values():
            assert status.met is False
            assert status.count == 0


class TestAllTargetsMet:
    """When every category meets its minimum, coverage is 100%."""

    def test_exact_minimum(self) -> None:
        cards = [
            _make_card("ramp", quantity=8),
            _make_card("card_draw", quantity=8),
            _make_card("removal", quantity=5),
        ]
        targets = {"ramp": (8, 12), "card_draw": (8, 10), "removal": (5, 7)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.overall_pct == 1.0
        assert result.total_deficit == 0
        for cat, status in result.per_category.items():
            assert status.met is True
            assert status.surplus == 0

    def test_above_minimum(self) -> None:
        cards = [
            _make_card("ramp", quantity=10),
            _make_card("card_draw", quantity=9),
        ]
        targets = {"ramp": (8, 12), "card_draw": (8, 10)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.overall_pct == 1.0
        assert result.total_deficit == 0
        assert result.per_category["ramp"].surplus == 2
        assert result.per_category["card_draw"].surplus == 1


class TestSomeTargetsMissed:
    """Partial coverage when some categories are short."""

    def test_one_of_two_met(self) -> None:
        cards = [
            _make_card("ramp", quantity=10),
            _make_card("card_draw", quantity=3),
        ]
        targets = {"ramp": (8, 12), "card_draw": (8, 10)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.overall_pct == 0.5
        assert result.total_deficit == 5  # card_draw short by 5
        assert result.per_category["ramp"].met is True
        assert result.per_category["card_draw"].met is False
        assert result.per_category["card_draw"].surplus == -5

    def test_two_of_three_met(self) -> None:
        cards = [
            _make_card("ramp", quantity=8),
            _make_card("card_draw", quantity=8),
            _make_card("removal", quantity=2),
        ]
        targets = {"ramp": (8, 12), "card_draw": (8, 10), "removal": (5, 7)}
        result = category_coverage(_make_deck(cards), targets)

        assert abs(result.overall_pct - 2 / 3) < 1e-9
        assert result.total_deficit == 3  # removal short by 3


class TestNoTargetsProvided:
    """When targets dict is empty, coverage is trivially 100%."""

    def test_empty_targets(self) -> None:
        cards = [_make_card("ramp", quantity=10)]
        result = category_coverage(_make_deck(cards), {})

        assert result.overall_pct == 1.0
        assert result.total_deficit == 0
        assert result.per_category == {}


class TestCategoriesInDeckNotInTargets:
    """Cards whose category is not in targets should be ignored."""

    def test_extra_categories_ignored(self) -> None:
        cards = [
            _make_card("ramp", quantity=8),
            _make_card("lands", quantity=36),
            _make_card("flavor", quantity=5),
        ]
        targets = {"ramp": (8, 12)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.overall_pct == 1.0
        assert "lands" not in result.per_category
        assert "flavor" not in result.per_category
        assert result.per_category["ramp"].met is True


class TestCommanderCompanionExcluded:
    """Commander and companion cards should not count toward category totals."""

    def test_commander_excluded(self) -> None:
        cards = [
            _make_card("ramp", quantity=7),
            _make_card("ramp", quantity=1, is_commander=True),
        ]
        targets = {"ramp": (8, 12)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.per_category["ramp"].count == 7
        assert result.per_category["ramp"].met is False
        assert result.total_deficit == 1

    def test_companion_excluded(self) -> None:
        cards = [
            _make_card("card_draw", quantity=7),
            _make_card("card_draw", quantity=1, is_companion=True),
        ]
        targets = {"card_draw": (8, 10)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.per_category["card_draw"].count == 7
        assert result.per_category["card_draw"].met is False

    def test_both_excluded(self) -> None:
        cards = [
            _make_card("removal", quantity=4),
            _make_card("removal", quantity=1, is_commander=True),
            _make_card("removal", quantity=1, is_companion=True),
        ]
        targets = {"removal": (5, 7)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.per_category["removal"].count == 4
        assert result.per_category["removal"].met is False
        assert result.total_deficit == 1


class TestMultipleCardsPerCategory:
    """Multiple DeckCard entries for the same category should be summed."""

    def test_aggregation(self) -> None:
        cards = [
            _make_card("ramp", quantity=3),
            _make_card("ramp", quantity=5),
            _make_card("card_draw", quantity=4),
            _make_card("card_draw", quantity=4),
        ]
        targets = {"ramp": (8, 12), "card_draw": (8, 10)}
        result = category_coverage(_make_deck(cards), targets)

        assert result.per_category["ramp"].count == 8
        assert result.per_category["card_draw"].count == 8
        assert result.overall_pct == 1.0


class TestReturnTypes:
    """Verify that the function returns correct types."""

    def test_result_type(self) -> None:
        result = category_coverage(_make_deck([]), {"ramp": (8, 12)})
        assert isinstance(result, CategoryCoverageResult)
        assert isinstance(result.per_category["ramp"], CategoryStatus)
        assert isinstance(result.overall_pct, float)
        assert isinstance(result.total_deficit, int)
