"""Budget-aware card selection optimizer for Commander deck construction.

Handles soft budget caps per category, backfill from overflow categories,
and over-budget swap optimization to produce decks within total budget.
"""

from __future__ import annotations

import math


def score_card(synergy: float, power: float, price: float) -> float:
    """Compute a final selection score for a candidate card.

    The formula balances synergy, power, and cost-efficiency:
        final_score = synergy * power / price_weight

    price_weight grows logarithmically so expensive cards are penalized
    but not completely excluded.

    Args:
        synergy: Synergy score (0.0 to 1.0) from the synergy engine.
        power: Power/quality score (0.0 to 1.0), often derived from
            EDHREC rank normalization or category confidence.
        price: Card price in USD. Must be >= 0.

    Returns:
        A float score where higher is better. Returns 0.0 for zero
        synergy or zero power.
    """
    if synergy <= 0.0 or power <= 0.0:
        return 0.0

    # Price weight: log-scaled so that a $0.25 card has weight ~1.0
    # and a $20 card has weight ~4.4
    effective_price = max(price, 0.25)
    price_weight = 1.0 + math.log(effective_price / 0.25)

    return (synergy * power) / price_weight


def optimize_for_budget(
    candidates: list[dict],
    budget: float,
    category_targets: dict[str, tuple[int, int]],
) -> list[dict]:
    """Select cards from candidates to fill category targets within budget.

    Each candidate dict must have keys:
        - "card": the Card object
        - "card_id": int identifier
        - "score": float final score (from score_card)
        - "price": float price in USD
        - "category": str primary category assignment

    Category targets map category name to (min_count, max_count) tuples.
    Soft budget caps mean individual categories can exceed their max if
    the total budget allows it.

    Algorithm:
        1. Sort candidates by score descending within each category.
        2. Fill each category up to its minimum target.
        3. Backfill underfilled categories from overflow of other categories.
        4. Fill remaining slots from highest-scored unused candidates.
        5. If over budget, swap lowest-scored selected cards for cheaper
           alternatives until within budget.

    Args:
        candidates: List of candidate dicts with card info and scores.
        budget: Total budget in USD.
        category_targets: Dict mapping category -> (min, max) counts.

    Returns:
        List of selected candidate dicts within (or near) budget.
    """
    if not candidates:
        return []

    # Group candidates by category, sorted by score descending
    by_category: dict[str, list[dict]] = {}
    for cand in candidates:
        cat = cand["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(cand)

    for cat in by_category:
        by_category[cat].sort(key=lambda c: c["score"], reverse=True)

    selected: list[dict] = []
    selected_ids: set[int] = set()
    total_cost = 0.0

    # Phase 1: Fill category minimums
    for cat, (min_count, _max_count) in category_targets.items():
        cat_candidates = by_category.get(cat, [])
        filled = 0
        for cand in cat_candidates:
            if filled >= min_count:
                break
            cid = cand["card_id"]
            if cid in selected_ids:
                continue
            selected.append(cand)
            selected_ids.add(cid)
            total_cost += cand["price"]
            filled += 1

    # Phase 2: Fill up to max targets where budget allows
    for cat, (_min_count, max_count) in category_targets.items():
        cat_candidates = by_category.get(cat, [])
        cat_selected = sum(1 for s in selected if s["category"] == cat)
        for cand in cat_candidates:
            if cat_selected >= max_count:
                break
            cid = cand["card_id"]
            if cid in selected_ids:
                continue
            # Soft cap: allow if total stays within budget
            if total_cost + cand["price"] <= budget:
                selected.append(cand)
                selected_ids.add(cid)
                total_cost += cand["price"]
                cat_selected += 1

    # Phase 3: Backfill underfilled categories from unselected candidates
    for cat, (min_count, _max_count) in category_targets.items():
        cat_selected = sum(1 for s in selected if s["category"] == cat)
        deficit = min_count - cat_selected
        if deficit <= 0:
            continue
        # Try to find cards from any category that could fill this gap
        # Look through all unselected candidates sorted by score
        all_unselected = [
            c for c in candidates
            if c["card_id"] not in selected_ids
        ]
        all_unselected.sort(key=lambda c: c["score"], reverse=True)
        for cand in all_unselected:
            if deficit <= 0:
                break
            cid = cand["card_id"]
            if cid in selected_ids:
                continue
            # Re-assign to the deficit category
            reassigned = dict(cand)
            reassigned["category"] = cat
            selected.append(reassigned)
            selected_ids.add(cid)
            total_cost += cand["price"]
            deficit -= 1

    # Phase 4: If over budget, swap lowest-scored cards for cheaper alternatives
    if total_cost > budget:
        _swap_for_cheaper(selected, selected_ids, candidates, budget)

    return selected


def _swap_for_cheaper(
    selected: list[dict],
    selected_ids: set[int],
    all_candidates: list[dict],
    budget: float,
) -> None:
    """Swap expensive low-scored cards for cheaper alternatives in-place.

    Iteratively replaces the lowest-scored selected card with the
    highest-scored unselected card that costs less, until budget is met
    or no more swaps are possible.

    Args:
        selected: List of selected candidate dicts (modified in-place).
        selected_ids: Set of selected card IDs (modified in-place).
        all_candidates: Full list of candidate dicts to draw replacements from.
        budget: Target budget in USD.
    """
    max_iterations = len(selected) * 2
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        total_cost = sum(c["price"] for c in selected)
        if total_cost <= budget:
            break

        overage = total_cost - budget

        # Find the lowest-scored selected card
        selected.sort(key=lambda c: c["score"])
        swapped = False

        for i, worst in enumerate(selected):
            # Find a cheaper unselected alternative
            alternatives = [
                c for c in all_candidates
                if c["card_id"] not in selected_ids
                and c["price"] < worst["price"]
                and c["price"] <= worst["price"] - (overage * 0.1)
            ]
            if not alternatives:
                # Try any cheaper card
                alternatives = [
                    c for c in all_candidates
                    if c["card_id"] not in selected_ids
                    and c["price"] < worst["price"]
                ]
            if not alternatives:
                continue

            # Pick the highest scored cheap alternative
            alternatives.sort(key=lambda c: c["score"], reverse=True)
            replacement = alternatives[0]

            # Perform swap
            selected_ids.discard(worst["card_id"])
            selected_ids.add(replacement["card_id"])
            # Preserve category assignment
            new_entry = dict(replacement)
            new_entry["category"] = worst["category"]
            selected[i] = new_entry
            swapped = True
            break

        if not swapped:
            # No beneficial swaps possible; remove the cheapest low-scored card
            if selected:
                removed = selected.pop(0)
                selected_ids.discard(removed["card_id"])
            break
