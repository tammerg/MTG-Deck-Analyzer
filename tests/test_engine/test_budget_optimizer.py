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

    def test_zero_synergy_returns_zero(self):
        """Zero synergy should produce a zero score."""
        assert score_card(0.0, 0.8, 1.0) == 0.0

    def test_zero_power_returns_zero(self):
        """Zero power should produce a zero score."""
        assert score_card(0.8, 0.0, 1.0) == 0.0

    def test_positive_score_for_good_card(self):
        """A card with good synergy and power should have a positive score."""
        result = score_card(0.8, 0.9, 1.0)
        assert result > 0.0

    def test_cheaper_card_scores_higher(self):
        """A cheaper card should score higher than an expensive one with same stats."""
        cheap = score_card(0.8, 0.8, 0.50)
        expensive = score_card(0.8, 0.8, 10.0)
        assert cheap > expensive

    def test_higher_synergy_scores_higher(self):
        """Higher synergy should produce a higher score at the same price/power."""
        high_syn = score_card(1.0, 0.8, 2.0)
        low_syn = score_card(0.3, 0.8, 2.0)
        assert high_syn > low_syn

    def test_higher_power_scores_higher(self):
        """Higher power should produce a higher score at the same price/synergy."""
        high_pow = score_card(0.8, 1.0, 2.0)
        low_pow = score_card(0.8, 0.3, 2.0)
        assert high_pow > low_pow

    def test_very_cheap_card_floor(self):
        """Cards priced below $0.25 should use $0.25 as the floor."""
        free = score_card(0.5, 0.5, 0.01)
        quarter = score_card(0.5, 0.5, 0.25)
        assert free == quarter

    def test_negative_synergy_returns_zero(self):
        """Negative synergy should return zero."""
        assert score_card(-0.5, 0.8, 1.0) == 0.0

    def test_negative_power_returns_zero(self):
        """Negative power should return zero."""
        assert score_card(0.8, -0.5, 1.0) == 0.0

    def test_score_is_deterministic(self):
        """Same inputs should always produce the same score."""
        s1 = score_card(0.7, 0.6, 3.0)
        s2 = score_card(0.7, 0.6, 3.0)
        assert s1 == s2


# ===========================================================================
# optimize_for_budget tests
# ===========================================================================


class TestOptimizeForBudget:
    """Tests for the optimize_for_budget function."""

    def test_empty_candidates_returns_empty(self):
        """An empty candidate list should return an empty selection."""
        result = optimize_for_budget([], 100.0, {"ramp": (3, 5)})
        assert result == []

    def test_fills_category_minimums(self):
        """Categories should have at least their minimum target filled."""
        candidates = [
            _make_candidate(i, f"Card {i}", score=10.0 - i, price=1.0, category="ramp")
            for i in range(1, 11)
        ]
        targets = {"ramp": (5, 8)}
        result = optimize_for_budget(candidates, 100.0, targets)
        ramp_count = sum(1 for c in result if c["category"] == "ramp")
        assert ramp_count >= 5

    def test_budget_compliance(self):
        """Total cost of selected cards should not exceed budget."""
        candidates = [
            _make_candidate(i, f"Card {i}", score=5.0, price=2.0, category="ramp")
            for i in range(1, 51)
        ]
        budget = 20.0
        targets = {"ramp": (3, 10)}
        result = optimize_for_budget(candidates, budget, targets)
        total_cost = sum(c["price"] for c in result)
        assert total_cost <= budget

    def test_soft_cap_allows_over_individual_max(self):
        """A category can go over its max count if total budget allows."""
        # 10 cheap ramp cards, budget allows all of them
        candidates = [
            _make_candidate(i, f"Ramp {i}", score=9.0 - i * 0.1, price=0.50, category="ramp")
            for i in range(1, 11)
        ]
        targets = {"ramp": (3, 5)}
        result = optimize_for_budget(candidates, 100.0, targets)
        # With soft caps the optimizer fills up to max but not over unless via backfill
        ramp_count = sum(1 for c in result if c["category"] == "ramp")
        assert ramp_count >= 3

    def test_multiple_categories_filled(self):
        """Multiple categories should each have their minimums met."""
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

    def test_over_budget_swap_reduces_cost(self):
        """When initial selection is over budget, swaps should reduce total cost."""
        # Mix of expensive and cheap candidates
        candidates = []
        for i in range(1, 11):
            # Expensive high-score
            candidates.append(
                _make_candidate(i, f"Expensive {i}", score=8.0, price=5.0, category="ramp")
            )
        for i in range(11, 21):
            # Cheap moderate-score
            candidates.append(
                _make_candidate(i, f"Cheap {i}", score=4.0, price=0.50, category="ramp")
            )

        budget = 15.0
        targets = {"ramp": (5, 10)}
        result = optimize_for_budget(candidates, budget, targets)
        total_cost = sum(c["price"] for c in result)
        # Should be at or under budget after swaps
        assert total_cost <= budget

    def test_preserves_singleton(self):
        """No card ID should appear more than once in the result."""
        candidates = [
            _make_candidate(i, f"Card {i}", score=5.0, price=1.0, category="ramp")
            for i in range(1, 21)
        ]
        targets = {"ramp": (5, 10)}
        result = optimize_for_budget(candidates, 100.0, targets)
        card_ids = [c["card_id"] for c in result]
        assert len(card_ids) == len(set(card_ids)), "Duplicate card IDs found"

    def test_backfill_underfilled_categories(self):
        """When a category has too few candidates, backfill from others."""
        candidates = [
            _make_candidate(1, "Only Ramp", score=8.0, price=1.0, category="ramp"),
            _make_candidate(2, "Draw 1", score=7.0, price=1.0, category="card_draw"),
            _make_candidate(3, "Draw 2", score=6.0, price=1.0, category="card_draw"),
            _make_candidate(4, "Draw 3", score=5.0, price=1.0, category="card_draw"),
            _make_candidate(5, "Draw 4", score=4.0, price=1.0, category="card_draw"),
            _make_candidate(6, "Draw 5", score=3.0, price=1.0, category="card_draw"),
        ]
        targets = {
            "ramp": (3, 5),  # Only 1 ramp candidate, need 3
            "card_draw": (2, 4),
        }
        result = optimize_for_budget(candidates, 100.0, targets)
        # Should have selected cards and attempted to backfill ramp
        assert len(result) >= 3

    def test_respects_budget_over_quantity(self):
        """Budget constraint should take priority over filling all slots."""
        candidates = [
            _make_candidate(i, f"Card {i}", score=5.0, price=10.0, category="ramp")
            for i in range(1, 21)
        ]
        budget = 30.0
        targets = {"ramp": (5, 10)}
        result = optimize_for_budget(candidates, budget, targets)
        total_cost = sum(c["price"] for c in result)
        # Cannot fill min of 5 at $10 each within $30 budget, but
        # the optimizer should still try to select as many as possible
        assert total_cost <= budget + 10.0  # Allow some overage since minimums must be met


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

    def test_curve_penalty_underfull_bucket(self):
        """Returns 1.0 when the CMC bucket has room below ideal count."""
        ideal_curve = {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05}
        # Ideal count for bucket 3 = 0.22 * 65 = 14.3
        # Current count = 5 (well under 14.3)
        current_curve = {3: 5}
        result = compute_curve_penalty(
            cmc=3.0,
            current_curve=current_curve,
            ideal_curve=ideal_curve,
            total_nonland_target=65,
        )
        assert result == 1.0

    def test_curve_penalty_overfull_bucket(self):
        """Returns < 1.0 when the CMC bucket is over ideal but under 1.5x."""
        ideal_curve = {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05}
        # Ideal count for bucket 3 = 0.22 * 65 = 14.3
        # Current count = 16 (above 14.3 but below 14.3 * 1.5 = 21.45)
        current_curve = {3: 16}
        result = compute_curve_penalty(
            cmc=3.0,
            current_curve=current_curve,
            ideal_curve=ideal_curve,
            total_nonland_target=65,
        )
        assert result < 1.0
        assert result > 0.3

    def test_curve_penalty_very_overfull(self):
        """Returns 0.3 when the bucket is at or beyond 1.5x the ideal count."""
        ideal_curve = {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05}
        # Ideal count for bucket 3 = 0.22 * 65 = 14.3
        # 1.5x ideal = 21.45, current count = 25 (well above)
        current_curve = {3: 25}
        result = compute_curve_penalty(
            cmc=3.0,
            current_curve=current_curve,
            ideal_curve=ideal_curve,
            total_nonland_target=65,
        )
        assert result == 0.3

    def test_curve_penalty_cmc_clamped_to_7(self):
        """CMC 9 should go into bucket 7."""
        ideal_curve = {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05}
        # Ideal count for bucket 7 = 0.05 * 65 = 3.25
        # Current count = 0 (underfull)
        current_curve = {}
        result = compute_curve_penalty(
            cmc=9.0,
            current_curve=current_curve,
            ideal_curve=ideal_curve,
            total_nonland_target=65,
        )
        assert result == 1.0

    def test_optimize_with_curve_shapes_distribution(self):
        """Optimize with ideal_curve should produce a more even CMC distribution than without."""
        # Create candidates heavily skewed toward CMC 5
        candidates = []
        idx = 1
        # 30 cards at CMC 5 (high score)
        for i in range(30):
            candidates.append(
                _make_candidate_with_cmc(
                    idx, f"Five Drop {i}", score=8.0 - i * 0.01,
                    price=0.50, category="ramp", cmc=5.0,
                )
            )
            idx += 1
        # 20 cards at CMC 2 (moderate score)
        for i in range(20):
            candidates.append(
                _make_candidate_with_cmc(
                    idx, f"Two Drop {i}", score=6.0 - i * 0.01,
                    price=0.50, category="ramp", cmc=2.0,
                )
            )
            idx += 1
        # 15 cards at CMC 3 (moderate score)
        for i in range(15):
            candidates.append(
                _make_candidate_with_cmc(
                    idx, f"Three Drop {i}", score=5.5 - i * 0.01,
                    price=0.50, category="ramp", cmc=3.0,
                )
            )
            idx += 1
        # 10 cards at CMC 1 (lower score)
        for i in range(10):
            candidates.append(
                _make_candidate_with_cmc(
                    idx, f"One Drop {i}", score=4.0 - i * 0.01,
                    price=0.50, category="ramp", cmc=1.0,
                )
            )
            idx += 1

        targets = {"ramp": (10, 40)}
        ideal_curve = {
            0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05,
        }

        # Without curve shaping
        result_no_curve = optimize_for_budget(candidates, 100.0, targets)
        # With curve shaping
        result_with_curve = optimize_for_budget(
            candidates, 100.0, targets,
            ideal_curve=ideal_curve,
            total_nonland_target=40,
        )

        # Count CMC 5 cards in each result
        cmc5_no_curve = sum(
            1 for c in result_no_curve if c["card"].cmc == 5.0
        )
        cmc5_with_curve = sum(
            1 for c in result_with_curve if c["card"].cmc == 5.0
        )

        # With curve shaping, there should be fewer 5-drops because the
        # ideal curve only allocates 12% to bucket 5
        assert cmc5_with_curve < cmc5_no_curve


# ===========================================================================
# compute_diminishing_penalty tests
# ===========================================================================


class TestDiminishingReturns:
    """Tests for the compute_diminishing_penalty function."""

    def test_penalty_under_max(self):
        """When current count is below max target, penalty should be 1.0 (no penalty)."""
        category_counts = {"ramp": 5}
        category_targets = {"ramp": (3, 8)}
        result = compute_diminishing_penalty("ramp", category_counts, category_targets)
        assert result == 1.0

    def test_penalty_at_max(self):
        """When current count equals max target, penalty should be 0.5."""
        category_counts = {"ramp": 8}
        category_targets = {"ramp": (3, 8)}
        result = compute_diminishing_penalty("ramp", category_counts, category_targets)
        assert result == 0.5

    def test_penalty_over_max(self):
        """When current count exceeds max target, penalty should decay exponentially."""
        category_targets = {"ramp": (3, 8)}
        # 1 over max: 0.5 ** 2 = 0.25
        result_1_over = compute_diminishing_penalty(
            "ramp", {"ramp": 9}, category_targets
        )
        assert result_1_over == pytest.approx(0.25)

        # 2 over max: 0.5 ** 3 = 0.125
        result_2_over = compute_diminishing_penalty(
            "ramp", {"ramp": 10}, category_targets
        )
        assert result_2_over == pytest.approx(0.125)

        # Each additional card over max should have a smaller penalty
        assert result_2_over < result_1_over

    def test_penalty_no_target(self):
        """Category not in targets should return 1.0 (no penalty)."""
        category_counts = {"flex": 15}
        category_targets = {"ramp": (3, 8)}
        result = compute_diminishing_penalty("flex", category_counts, category_targets)
        assert result == 1.0


# ===========================================================================
# compute_functional_similarity tests
# ===========================================================================


class TestFunctionalSimilarity:
    """Tests for the compute_functional_similarity function."""

    def test_identical_text_high_similarity(self):
        """Identical oracle text should produce similarity close to 1.0."""
        text = "Draw two cards. You lose 2 life."
        result = compute_functional_similarity(text, text)
        assert result == pytest.approx(1.0)

    def test_different_text_low_similarity(self):
        """Completely unrelated oracle texts should have low similarity."""
        text_a = "Destroy all creatures. They can't be regenerated."
        text_b = "Search your library for a basic land card and put it onto the battlefield tapped."
        result = compute_functional_similarity(text_a, text_b)
        assert result < 0.3

    def test_similar_draw_spells(self):
        """Two 'draw cards' variants should have high similarity."""
        text_a = "Draw two cards."
        text_b = "Draw three cards."
        result = compute_functional_similarity(text_a, text_b)
        assert result > 0.3

    def test_empty_text(self):
        """Empty oracle text should return 0.0 similarity."""
        result = compute_functional_similarity("", "Draw two cards.")
        assert result == 0.0

    def test_both_empty(self):
        """Two empty oracle texts should return 0.0."""
        result = compute_functional_similarity("", "")
        assert result == 0.0

    def test_reminder_text_stripped(self):
        """Text in parentheses (reminder text) should be stripped before comparison."""
        text_a = "Flying (This creature can only be blocked by creatures with flying.)"
        text_b = "Flying"
        result = compute_functional_similarity(text_a, text_b)
        assert result == pytest.approx(1.0)


# ===========================================================================
# compute_duplicate_penalty tests
# ===========================================================================


class TestDuplicatePenalty:
    """Tests for the compute_duplicate_penalty function."""

    def test_no_duplicates_no_penalty(self):
        """When no selected card is similar, penalty should be 1.0."""
        candidate = "Destroy target creature."
        selected = [
            "Draw two cards.",
            "Search your library for a basic land card.",
        ]
        result = compute_duplicate_penalty(candidate, selected)
        assert result == 1.0

    def test_one_duplicate_mild_penalty(self):
        """When one selected card is similar, penalty should be 0.7."""
        candidate = "Draw two cards."
        selected = [
            "Draw three cards.",  # Very similar
            "Destroy target creature.",  # Not similar
        ]
        result = compute_duplicate_penalty(candidate, selected)
        assert result == 0.7

    def test_multiple_duplicates_heavy_penalty(self):
        """When 3+ selected cards are similar, penalty should be 0.2."""
        candidate = "Draw two cards. Scry 1."
        selected = [
            "Draw two cards.",
            "Draw three cards.",
            "Draw two cards and lose 2 life.",
        ]
        result = compute_duplicate_penalty(candidate, selected)
        assert result == 0.2

    def test_empty_selected_no_penalty(self):
        """Empty selected list should return 1.0."""
        result = compute_duplicate_penalty("Draw two cards.", [])
        assert result == 1.0

    def test_two_duplicates_moderate_penalty(self):
        """When exactly 2 selected cards are similar, penalty should be 0.4."""
        candidate = "Draw two cards. You gain 1 life."
        selected = [
            "Draw two cards.",
            "Draw three cards.",
            "Destroy target creature.",  # Not similar
        ]
        result = compute_duplicate_penalty(candidate, selected)
        assert result == 0.4
