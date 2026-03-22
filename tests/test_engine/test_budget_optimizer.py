"""Tests for the budget optimizer engine module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.engine.budget_optimizer import (
    compute_curve_penalty,
    compute_diminishing_penalty,
    compute_duplicate_penalty,
    compute_functional_similarity,
    optimize_for_budget,
    score_card,
)
from mtg_deck_maker.models.card import Card


# ---------------------------------------------------------------------------
# Helper: build a minimal candidate dict for budget optimizer
# ---------------------------------------------------------------------------

def _make_candidate(
    card_id: int,
    name: str,
    score: float,
    price: float,
    category: str,
) -> dict:
    """Create a candidate dict matching the optimize_for_budget contract."""
    card = Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line="Instant",
        oracle_text="",
        mana_cost="{1}",
        cmc=1.0,
        colors=[],
        color_identity=[],
        keywords=[],
        legal_commander=True,
        id=card_id,
    )
    return {
        "card": card,
        "card_id": card_id,
        "score": score,
        "price": price,
        "category": category,
    }


# ===========================================================================
# score_card tests
# ===========================================================================


class TestScoreCard:
    """Tests for the score_card function."""

    @pytest.mark.parametrize(
        "synergy, power, price, expected",
        [
            (0.0, 0.8, 1.0, 0.0),
            (0.8, 0.0, 1.0, 0.0),
            (-0.5, 0.8, 1.0, 0.0),
            (0.8, -0.5, 1.0, 0.0),
        ],
        ids=["zero_synergy", "zero_power", "negative_synergy", "negative_power"],
    )
    def test_zero_or_negative_returns_zero(self, synergy, power, price, expected):
        assert score_card(synergy, power, price) == expected

    def test_positive_score_for_good_card(self):
        """A card with good synergy and power should have a positive score."""
        assert score_card(0.8, 0.9, 1.0) > 0.0

    def test_cheaper_card_scores_higher(self):
        """A cheaper card should score higher than an expensive one with same stats."""
        assert score_card(0.8, 0.8, 0.50) > score_card(0.8, 0.8, 10.0)

    def test_higher_synergy_scores_higher(self):
        assert score_card(1.0, 0.8, 2.0) > score_card(0.3, 0.8, 2.0)

    def test_very_cheap_card_floor(self):
        """Cards priced below $0.25 should use $0.25 as the floor."""
        assert score_card(0.5, 0.5, 0.01) == score_card(0.5, 0.5, 0.25)


# ===========================================================================
# optimize_for_budget tests
# ===========================================================================


class TestOptimizeForBudget:
    """Tests for the optimize_for_budget function."""

    def test_empty_candidates_returns_empty(self):
        result = optimize_for_budget([], 100.0, {"ramp": (3, 5)})
        assert result == []

    def test_fills_category_minimums(self):
        candidates = [
            _make_candidate(i, f"Card {i}", score=10.0 - i, price=1.0, category="ramp")
            for i in range(1, 11)
        ]
        targets = {"ramp": (5, 8)}
        result = optimize_for_budget(candidates, 100.0, targets)
        ramp_count = sum(1 for c in result if c["category"] == "ramp")
        assert ramp_count >= 5

    def test_budget_compliance(self):
        candidates = [
            _make_candidate(i, f"Card {i}", score=5.0, price=2.0, category="ramp")
            for i in range(1, 51)
        ]
        result = optimize_for_budget(candidates, 20.0, {"ramp": (3, 10)})
        assert sum(c["price"] for c in result) <= 20.0

    def test_multiple_categories_filled(self):
        candidates = []
        idx = 1
        for cat in ["ramp", "card_draw", "removal"]:
            for j in range(8):
                candidates.append(
                    _make_candidate(idx, f"{cat}_{j}", score=5.0 - j * 0.1, price=1.0, category=cat)
                )
                idx += 1

        targets = {
            "ramp": (3, 5),
            "card_draw": (3, 5),
            "removal": (2, 4),
        }
        result = optimize_for_budget(candidates, 100.0, targets)

        cat_counts: dict[str, int] = {}
        for c in result:
            cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1

        assert cat_counts.get("ramp", 0) >= 3
        assert cat_counts.get("card_draw", 0) >= 3
        assert cat_counts.get("removal", 0) >= 2

    def test_preserves_singleton(self):
        candidates = [
            _make_candidate(i, f"Card {i}", score=5.0, price=1.0, category="ramp")
            for i in range(1, 21)
        ]
        result = optimize_for_budget(candidates, 100.0, {"ramp": (5, 10)})
        card_ids = [c["card_id"] for c in result]
        assert len(card_ids) == len(set(card_ids)), "Duplicate card IDs found"


# ===========================================================================
# compute_curve_penalty tests
# ===========================================================================


def _make_candidate_with_cmc(
    card_id: int,
    name: str,
    score: float,
    price: float,
    category: str,
    cmc: float,
) -> dict:
    """Create a candidate dict with a specific CMC for curve shaping tests."""
    card = Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line="Instant",
        oracle_text="",
        mana_cost="{1}",
        cmc=cmc,
        colors=[],
        color_identity=[],
        keywords=[],
        legal_commander=True,
        id=card_id,
    )
    return {
        "card": card,
        "card_id": card_id,
        "score": score,
        "price": price,
        "category": category,
    }


class TestCurvePenalty:
    """Tests for the compute_curve_penalty function."""

    _IDEAL = {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05}

    @pytest.mark.parametrize(
        "current_count, expected_op, expected_val",
        [
            (5, "eq", 1.0),       # underfull: ideal ~14.3, count=5
            (16, "lt", 1.0),      # overfull: above 14.3 but below 21.45
            (25, "eq", 0.3),      # very overfull: above 1.5x ideal
        ],
        ids=["underfull", "overfull", "very_overfull"],
    )
    def test_curve_penalty_levels(self, current_count, expected_op, expected_val):
        current_curve = {3: current_count}
        result = compute_curve_penalty(
            cmc=3.0,
            current_curve=current_curve,
            ideal_curve=self._IDEAL,
            total_nonland_target=65,
        )
        if expected_op == "eq":
            assert result == expected_val
        elif expected_op == "lt":
            assert result < expected_val
            assert result > 0.3

    def test_curve_penalty_cmc_clamped_to_7(self):
        """CMC 9 should go into bucket 7."""
        result = compute_curve_penalty(
            cmc=9.0,
            current_curve={},
            ideal_curve=self._IDEAL,
            total_nonland_target=65,
        )
        assert result == 1.0


# ===========================================================================
# compute_diminishing_penalty tests
# ===========================================================================


class TestDiminishingReturns:
    """Tests for the compute_diminishing_penalty function."""

    @pytest.mark.parametrize(
        "count, expected",
        [
            (5, 1.0),
            (8, 0.5),
        ],
        ids=["under_max", "at_max"],
    )
    def test_penalty_relative_to_max(self, count, expected):
        result = compute_diminishing_penalty(
            "ramp", {"ramp": count}, {"ramp": (3, 8)}
        )
        assert result == expected

    def test_penalty_over_max_decays(self):
        targets = {"ramp": (3, 8)}
        result_1_over = compute_diminishing_penalty("ramp", {"ramp": 9}, targets)
        result_2_over = compute_diminishing_penalty("ramp", {"ramp": 10}, targets)
        assert result_1_over == pytest.approx(0.25)
        assert result_2_over == pytest.approx(0.125)
        assert result_2_over < result_1_over

    def test_penalty_no_target(self):
        result = compute_diminishing_penalty("flex", {"flex": 15}, {"ramp": (3, 8)})
        assert result == 1.0


# ===========================================================================
# compute_functional_similarity tests
# ===========================================================================


class TestFunctionalSimilarity:
    """Tests for the compute_functional_similarity function."""

    def test_identical_text_high_similarity(self):
        text = "Draw two cards. You lose 2 life."
        assert compute_functional_similarity(text, text) == pytest.approx(1.0)

    def test_different_text_low_similarity(self):
        result = compute_functional_similarity(
            "Destroy all creatures. They can't be regenerated.",
            "Search your library for a basic land card and put it onto the battlefield tapped.",
        )
        assert result < 0.3

    def test_empty_text(self):
        assert compute_functional_similarity("", "Draw two cards.") == 0.0
        assert compute_functional_similarity("", "") == 0.0

    def test_reminder_text_stripped(self):
        result = compute_functional_similarity(
            "Flying (This creature can only be blocked by creatures with flying.)",
            "Flying",
        )
        assert result == pytest.approx(1.0)


# ===========================================================================
# compute_duplicate_penalty tests
# ===========================================================================


class TestDuplicatePenalty:
    """Tests for the compute_duplicate_penalty function."""

    @pytest.mark.parametrize(
        "candidate, selected, expected",
        [
            (
                "Destroy target creature.",
                ["Draw two cards.", "Search your library for a basic land card."],
                1.0,
            ),
            (
                "Draw two cards.",
                ["Draw three cards.", "Destroy target creature."],
                0.7,
            ),
            (
                "Draw two cards. Scry 1.",
                ["Draw two cards.", "Draw three cards.", "Draw two cards and lose 2 life."],
                0.2,
            ),
            (
                "Draw two cards.",
                [],
                1.0,
            ),
        ],
        ids=["no_duplicates", "one_duplicate", "multiple_duplicates", "empty_selected"],
    )
    def test_duplicate_penalty(self, candidate, selected, expected):
        assert compute_duplicate_penalty(candidate, selected) == expected
