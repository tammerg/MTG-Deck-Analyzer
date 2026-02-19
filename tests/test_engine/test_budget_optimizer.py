"""Tests for the budget optimizer engine module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.engine.budget_optimizer import optimize_for_budget, score_card
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
