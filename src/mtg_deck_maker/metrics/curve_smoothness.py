"""Mana curve smoothness metric.

Computes how closely a deck's actual CMC distribution matches an ideal curve.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mtg_deck_maker.models.deck import Deck

_MAX_BUCKET = 7


@dataclass(slots=True)
class CurveSmoothnessResult:
    """Result of a curve smoothness calculation."""

    smoothness: float
    rmse: float
    actual_distribution: dict[int, float]
    ideal_distribution: dict[int, float]
    total_nonland: int


def _bucket(cmc: float) -> int:
    """Map a CMC value to a bucket 0-7, capping at 7."""
    return min(int(cmc), _MAX_BUCKET)


def curve_smoothness(
    deck: Deck,
    ideal_curve: dict[int, float],
) -> CurveSmoothnessResult:
    """Compute how closely a deck's CMC distribution matches the ideal curve.

    Only counts non-land, non-commander, non-companion cards. Returns a
    CurveSmoothnessResult with smoothness in [0.0, 1.0] where 1.0 is a
    perfect match.

    Args:
        deck: The deck to evaluate.
        ideal_curve: Mapping of CMC bucket (0-7) to ideal percentage (0.0-1.0).

    Returns:
        CurveSmoothnessResult with smoothness score and distribution data.
    """
    # Count cards per CMC bucket, excluding lands, commanders, companions.
    counts: dict[int, int] = {b: 0 for b in range(_MAX_BUCKET + 1)}
    for card in deck.cards:
        if card.category == "land" or card.is_commander or card.is_companion:
            continue
        counts[_bucket(card.cmc)] += card.quantity

    total_nonland = sum(counts.values())

    # Build actual distribution as percentages.
    actual: dict[int, float] = {
        b: (counts[b] / total_nonland if total_nonland > 0 else 0.0)
        for b in range(_MAX_BUCKET + 1)
    }

    if total_nonland == 0:
        return CurveSmoothnessResult(
            smoothness=0.0,
            rmse=0.0,
            actual_distribution=actual,
            ideal_distribution=ideal_curve,
            total_nonland=0,
        )

    # RMSE between actual and ideal distributions across all buckets.
    n_buckets = _MAX_BUCKET + 1
    squared_sum = sum(
        (actual.get(b, 0.0) - ideal_curve.get(b, 0.0)) ** 2
        for b in range(n_buckets)
    )
    rmse = math.sqrt(squared_sum / n_buckets)

    # Normalize: max possible RMSE is when 100% is in one bucket and ideal
    # is spread out. The theoretical max RMSE for a distribution over 8
    # buckets is bounded by 1.0. We use 1.0 as the normalizer so smoothness
    # stays in [0, 1].
    smoothness = max(0.0, 1.0 - rmse)

    return CurveSmoothnessResult(
        smoothness=smoothness,
        rmse=rmse,
        actual_distribution=actual,
        ideal_distribution=ideal_curve,
        total_nonland=total_nonland,
    )
