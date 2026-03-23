"""Tests for LLM synergy matrix integration in budget_optimizer and deck_builder."""

from __future__ import annotations

import pytest

from mtg_deck_maker.engine.budget_optimizer import (
    _compute_llm_synergy_bonus,
    optimize_for_budget,
)
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.scored_candidate import ScoredCandidate


def _card(name: str, cmc: float = 3.0) -> Card:
    return Card(oracle_id=f"oid-{name}", name=name, cmc=cmc, type_line="Creature")


def _candidate(
    name: str,
    score: float = 1.0,
    price: float = 1.0,
    category: str = "ramp",
    cmc: float = 3.0,
) -> ScoredCandidate:
    card = _card(name, cmc)
    return ScoredCandidate(
        card=card,
        card_id=hash(name),
        score=score,
        price=price,
        category=category,
    )


class TestComputeLLMSynergyBonus:
    def test_empty_selected_returns_zero(self) -> None:
        matrix = {("A", "B"): 0.8}
        assert _compute_llm_synergy_bonus("A", [], matrix) == 0.0

    def test_empty_matrix_returns_zero(self) -> None:
        assert _compute_llm_synergy_bonus("A", ["B"], {}) == 0.0

    def test_computes_correct_average(self) -> None:
        matrix = {
            ("A", "B"): 0.8,
            ("A", "C"): 0.4,
        }
        result = _compute_llm_synergy_bonus("A", ["B", "C"], matrix)
        assert result == pytest.approx(0.6)

    def test_canonical_key_ordering(self) -> None:
        # "Z" > "A", so canonical key is ("A", "Z")
        matrix = {("A", "Z"): 0.9}
        result = _compute_llm_synergy_bonus("Z", ["A"], matrix)
        assert result == pytest.approx(0.9)

    def test_skips_pairs_not_in_matrix(self) -> None:
        matrix = {("A", "B"): 0.8}
        # "C" is not in any pair with "A"
        result = _compute_llm_synergy_bonus("A", ["B", "C"], matrix)
        # Only 1 match (A,B) out of 1 found
        assert result == pytest.approx(0.8)

    def test_no_matching_pairs_returns_zero(self) -> None:
        matrix = {("X", "Y"): 0.8}
        result = _compute_llm_synergy_bonus("A", ["B"], matrix)
        assert result == 0.0


class TestOptimizeWithLLMSynergy:
    def test_none_matrix_works_as_before(self) -> None:
        candidates = [
            _candidate("A", score=2.0, price=1.0),
            _candidate("B", score=1.5, price=1.0),
        ]
        targets = {"ramp": (1, 2)}
        result = optimize_for_budget(
            candidates, 10.0, targets, llm_synergy_matrix=None,
        )
        assert len(result) >= 1

    def test_matrix_boosts_synergistic_cards(self) -> None:
        # Card C has lower base score but high synergy with A
        candidates = [
            _candidate("A", score=2.0, price=1.0, category="ramp"),
            _candidate("B", score=1.8, price=1.0, category="ramp"),
            _candidate("C", score=1.7, price=1.0, category="ramp"),
        ]
        matrix = {
            ("A", "C"): 1.0,  # Very high synergy
            ("A", "B"): 0.0,  # No synergy
        }
        targets = {"ramp": (2, 3)}
        result = optimize_for_budget(
            candidates, 10.0, targets, llm_synergy_matrix=matrix,
        )
        names = {c.card.name for c in result}
        # C should be boosted by synergy with A
        assert "A" in names
        assert "C" in names

    def test_bonus_magnitude_is_bounded(self) -> None:
        # Even with max synergy (1.0), bonus multiplier is 1.15
        matrix = {("A", "B"): 1.0}
        bonus = _compute_llm_synergy_bonus("B", ["A"], matrix)
        multiplier = 1.0 + bonus * 0.15
        assert multiplier == pytest.approx(1.15)
