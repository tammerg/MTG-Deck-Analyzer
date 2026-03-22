"""Tests for mana curve smoothness metric."""

from __future__ import annotations

import pytest

from mtg_deck_maker.metrics.curve_smoothness import (
    CurveSmoothnessResult,
    curve_smoothness,
)
from mtg_deck_maker.models.deck import Deck, DeckCard


IDEAL_CURVE: dict[int, float] = {
    0: 0.02,
    1: 0.12,
    2: 0.22,
    3: 0.22,
    4: 0.18,
    5: 0.12,
    6: 0.07,
    7: 0.05,
}


def _make_deck(
    cards: list[DeckCard],
    name: str = "Test Deck",
) -> Deck:
    return Deck(name=name, cards=cards)


def _nonland_card(
    cmc: float,
    quantity: int = 1,
    category: str = "creature",
    card_id: int = 0,
) -> DeckCard:
    return DeckCard(
        card_id=card_id,
        cmc=cmc,
        quantity=quantity,
        category=category,
    )


class TestCurveSmoothnessResult:
    """Verify CurveSmoothnessResult is a proper dataclass."""

    def test_fields(self) -> None:
        result = CurveSmoothnessResult(
            smoothness=0.85,
            rmse=0.03,
            actual_distribution={0: 0.0, 1: 0.1},
            ideal_distribution={0: 0.02, 1: 0.12},
            total_nonland=50,
        )
        assert result.smoothness == 0.85
        assert result.rmse == 0.03
        assert result.total_nonland == 50

    def test_has_slots(self) -> None:
        assert hasattr(CurveSmoothnessResult, "__slots__")


class TestPerfectCurve:
    """When the actual distribution exactly matches the ideal curve."""

    def test_smoothness_is_one(self) -> None:
        # Build a deck whose nonland distribution exactly matches IDEAL_CURVE.
        # Use 100 nonland cards for easy percentage math.
        cards: list[DeckCard] = []
        card_id = 1
        for cmc_bucket, pct in IDEAL_CURVE.items():
            count = round(pct * 100)
            cards.append(
                _nonland_card(cmc=float(cmc_bucket), quantity=count, card_id=card_id)
            )
            card_id += 1

        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == pytest.approx(1.0, abs=1e-9)
        assert result.rmse == pytest.approx(0.0, abs=1e-9)
        assert result.total_nonland == 100

    def test_actual_matches_ideal(self) -> None:
        cards: list[DeckCard] = []
        card_id = 1
        for cmc_bucket, pct in IDEAL_CURVE.items():
            count = round(pct * 100)
            cards.append(
                _nonland_card(cmc=float(cmc_bucket), quantity=count, card_id=card_id)
            )
            card_id += 1

        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        for bucket, pct in IDEAL_CURVE.items():
            assert result.actual_distribution[bucket] == pytest.approx(pct, abs=0.01)


class TestAllCardsAtOneCmc:
    """All nonland cards at a single CMC should produce poor smoothness."""

    def test_all_at_cmc_3(self) -> None:
        cards = [_nonland_card(cmc=3.0, quantity=60)]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness < 0.75
        assert result.rmse > 0.2
        assert result.actual_distribution[3] == pytest.approx(1.0)
        for bucket in range(8):
            if bucket != 3:
                assert result.actual_distribution[bucket] == pytest.approx(0.0)

    def test_all_at_cmc_0(self) -> None:
        cards = [_nonland_card(cmc=0.0, quantity=40, category="artifact")]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness < 0.75
        assert result.actual_distribution[0] == pytest.approx(1.0)


class TestEmptyDeck:
    """An empty deck or a deck with zero nonland cards."""

    def test_empty_cards_list(self) -> None:
        deck = _make_deck([])
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == 0.0
        assert result.rmse == 0.0
        assert result.total_nonland == 0
        for bucket in range(8):
            assert result.actual_distribution[bucket] == 0.0

    def test_only_lands(self) -> None:
        cards = [
            DeckCard(card_id=1, category="land", quantity=36, cmc=0.0),
            DeckCard(card_id=2, category="land", quantity=2, cmc=0.0),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == 0.0
        assert result.total_nonland == 0

    def test_only_commanders(self) -> None:
        cards = [
            DeckCard(card_id=1, is_commander=True, cmc=4.0, quantity=1),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == 0.0
        assert result.total_nonland == 0

    def test_only_companions(self) -> None:
        cards = [
            DeckCard(card_id=1, is_companion=True, cmc=3.0, quantity=1),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == 0.0
        assert result.total_nonland == 0

    def test_only_lands_and_commanders(self) -> None:
        cards = [
            DeckCard(card_id=1, category="land", quantity=36, cmc=0.0),
            DeckCard(card_id=2, is_commander=True, cmc=5.0, quantity=1),
            DeckCard(card_id=3, is_companion=True, cmc=3.0, quantity=1),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.smoothness == 0.0
        assert result.total_nonland == 0


class TestHighCmcBucketing:
    """CMC >= 7 should all go into bucket 7."""

    def test_cmc_9_goes_to_bucket_7(self) -> None:
        cards = [
            _nonland_card(cmc=9.0, quantity=5, card_id=1),
            _nonland_card(cmc=7.0, quantity=5, card_id=2),
            _nonland_card(cmc=2.0, quantity=40, card_id=3),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.actual_distribution[7] == pytest.approx(10 / 50)
        assert result.total_nonland == 50

    def test_cmc_15_goes_to_bucket_7(self) -> None:
        cards = [
            _nonland_card(cmc=15.0, quantity=3, card_id=1),
            _nonland_card(cmc=1.0, quantity=7, card_id=2),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.actual_distribution[7] == pytest.approx(0.3)


class TestRealisticDistribution:
    """A realistic-ish Commander deck distribution."""

    def test_reasonable_smoothness(self) -> None:
        # A deck that's close but not perfect to the ideal curve.
        cards = [
            _nonland_card(cmc=0.0, quantity=1, card_id=1),
            _nonland_card(cmc=1.0, quantity=8, card_id=2),
            _nonland_card(cmc=2.0, quantity=14, card_id=3),
            _nonland_card(cmc=3.0, quantity=12, card_id=4),
            _nonland_card(cmc=4.0, quantity=9, card_id=5),
            _nonland_card(cmc=5.0, quantity=6, card_id=6),
            _nonland_card(cmc=6.0, quantity=4, card_id=7),
            _nonland_card(cmc=7.0, quantity=2, card_id=8),
            _nonland_card(cmc=8.0, quantity=1, card_id=9),
            # Also include some lands and a commander (excluded from metric).
            DeckCard(card_id=100, category="land", quantity=36, cmc=0.0),
            DeckCard(card_id=101, is_commander=True, cmc=4.0, quantity=1),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        # Should be reasonably good but not perfect.
        assert 0.5 < result.smoothness < 1.0
        assert result.rmse > 0.0
        # Bucket 7 should include cmc=7 and cmc=8 cards.
        assert result.actual_distribution[7] == pytest.approx(3 / 57, abs=0.001)
        assert result.total_nonland == 57

    def test_smoothness_between_0_and_1(self) -> None:
        cards = [
            _nonland_card(cmc=1.0, quantity=20, card_id=1),
            _nonland_card(cmc=3.0, quantity=20, card_id=2),
            _nonland_card(cmc=5.0, quantity=20, card_id=3),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert 0.0 <= result.smoothness <= 1.0


class TestIdealDistributionPassthrough:
    """The ideal_distribution field should match the input."""

    def test_ideal_is_returned(self) -> None:
        cards = [_nonland_card(cmc=2.0, quantity=10)]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.ideal_distribution == IDEAL_CURVE


class TestQuantityRespected:
    """Card quantity should be respected in distribution counts."""

    def test_quantity_counted(self) -> None:
        cards = [
            _nonland_card(cmc=1.0, quantity=4, card_id=1),
            _nonland_card(cmc=2.0, quantity=6, card_id=2),
        ]
        deck = _make_deck(cards)
        result = curve_smoothness(deck, IDEAL_CURVE)

        assert result.total_nonland == 10
        assert result.actual_distribution[1] == pytest.approx(0.4)
        assert result.actual_distribution[2] == pytest.approx(0.6)
