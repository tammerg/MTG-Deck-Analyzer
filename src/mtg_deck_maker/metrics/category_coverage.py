"""Category coverage metric for Commander decklists.

Computes what percentage of minimum category targets are met by a given deck.
"""

from __future__ import annotations

from dataclasses import dataclass

from mtg_deck_maker.models.deck import Deck


@dataclass(slots=True)
class CategoryStatus:
    """Per-category breakdown of target fulfillment."""

    count: int
    min_target: int
    max_target: int
    met: bool
    surplus: int


@dataclass(slots=True)
class CategoryCoverageResult:
    """Aggregate result of category coverage analysis."""

    overall_pct: float
    per_category: dict[str, CategoryStatus]
    total_deficit: int


def category_coverage(
    deck: Deck,
    category_targets: dict[str, tuple[int, int]],
) -> CategoryCoverageResult:
    """Compute category coverage for a deck against target thresholds.

    Args:
        deck: The deck to analyze.
        category_targets: Mapping of category name to (min, max) targets.

    Returns:
        A CategoryCoverageResult with overall percentage, per-category
        breakdown, and total deficit across underfilled categories.
    """
    if not category_targets:
        return CategoryCoverageResult(
            overall_pct=1.0,
            per_category={},
            total_deficit=0,
        )

    # Count cards per category, excluding commanders and companions.
    counts: dict[str, int] = {}
    for card in deck.cards:
        if card.is_commander or card.is_companion:
            continue
        if card.category in category_targets:
            counts[card.category] = counts.get(card.category, 0) + card.quantity

    per_category: dict[str, CategoryStatus] = {}
    met_count = 0
    total_deficit = 0

    for category, (min_target, max_target) in category_targets.items():
        count = counts.get(category, 0)
        surplus = count - min_target
        met = count >= min_target
        if met:
            met_count += 1
        else:
            total_deficit += min_target - count

        per_category[category] = CategoryStatus(
            count=count,
            min_target=min_target,
            max_target=max_target,
            met=met,
            surplus=surplus,
        )

    overall_pct = met_count / len(category_targets)

    return CategoryCoverageResult(
        overall_pct=overall_pct,
        per_category=per_category,
        total_deficit=total_deficit,
    )
