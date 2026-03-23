"""Budget-aware card selection optimizer for Commander deck construction.

Handles soft budget caps per category, backfill from overflow categories,
and over-budget swap optimization to produce decks within total budget.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace

from mtg_deck_maker.models.scored_candidate import ScoredCandidate


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


def compute_curve_penalty(
    cmc: float,
    current_curve: dict[int, int],
    ideal_curve: dict[int, float],
    total_nonland_target: int,
) -> float:
    """Compute a penalty multiplier based on how overfull a CMC bucket is.

    Used during card selection to discourage picking cards in CMC buckets
    that are already at or above the ideal count for the deck's archetype.

    Args:
        cmc: The card's converted mana cost.
        current_curve: Dict mapping CMC bucket -> count of cards already
            selected in that bucket.
        ideal_curve: Dict mapping CMC bucket -> ideal percentage of
            non-land cards that should fall in that bucket.
        total_nonland_target: Target number of non-land cards in the deck.

    Returns:
        A float multiplier between 0.3 and 1.0:
        - 1.0 when the bucket is underfull (no penalty)
        - 0.3 when the bucket is at or beyond 1.5x the ideal count
        - Linear interpolation between 1.0 and 0.3 otherwise
    """
    cmc_bucket = min(7, int(cmc))
    ideal_count = ideal_curve.get(cmc_bucket, 0.0) * total_nonland_target
    current_count = current_curve.get(cmc_bucket, 0)

    if ideal_count <= 0:
        # No ideal allocation for this bucket; apply heavy penalty if any exist
        return 0.3 if current_count > 0 else 1.0

    if current_count < ideal_count:
        return 1.0

    if current_count >= ideal_count * 1.5:
        return 0.3

    # Linear interpolation between 1.0 and 0.3
    # At ideal_count -> 1.0, at ideal_count * 1.5 -> 0.3
    overshoot = (current_count - ideal_count) / (ideal_count * 0.5)
    return 1.0 - overshoot * 0.7


def compute_diminishing_penalty(
    category: str,
    category_counts: dict[str, int],
    category_targets: dict[str, tuple[int, int]],
) -> float:
    """Compute a diminishing returns penalty for cards in an overfull category.

    Once a category reaches its max target, additional cards in that
    category receive exponentially decaying value.

    Args:
        category: The category to check.
        category_counts: Dict mapping category name -> current count
            of selected cards in that category.
        category_targets: Dict mapping category name -> (min, max) count
            targets.

    Returns:
        A float penalty multiplier between 0.0 and 1.0.
        1.0 means no penalty (under max target or no target defined).
        0.5 means first card at max target.
        Exponential decay for cards beyond max target.
    """
    if category not in category_targets:
        return 1.0

    _min_target, max_target = category_targets[category]
    current_count = category_counts.get(category, 0)

    if current_count < max_target:
        return 1.0

    if current_count == max_target:
        return 0.5

    # Exponential decay: 0.5 ** (current_count - max_target + 1)
    return 0.5 ** (current_count - max_target + 1)


# Regex to strip reminder text (text in parentheses)
_REMINDER_TEXT_RE = re.compile(r"\([^)]*\)")

# Common MTG words to exclude from functional keyword extraction
_COMMON_MTG_WORDS = frozenset({
    "target", "creature", "you", "the", "your", "this", "that",
    "card", "each", "its", "all", "and", "for", "with", "from",
    "into", "one", "may", "can", "are", "has", "have", "any",
    "end", "turn", "until", "when", "whenever", "put", "get",
    "gets", "other", "they", "than", "not", "also", "then",
    "those", "where", "control", "spell", "mana", "pay",
    "player", "opponent", "opponents", "permanent", "ability",
})


def _extract_functional_tokens(oracle_text: str) -> set[str]:
    """Extract functional keyword tokens from oracle text.

    Strips reminder text (parenthesized), lowercases, filters to
    words with 3+ characters, and removes common MTG stop words.

    Args:
        oracle_text: The card's oracle text.

    Returns:
        Set of functional keyword strings.
    """
    if not oracle_text:
        return set()

    # Strip reminder text
    cleaned = _REMINDER_TEXT_RE.sub("", oracle_text)

    # Tokenize: lowercase, extract word tokens of 3+ characters
    words = re.findall(r"[a-z]{3,}", cleaned.lower())

    # Filter out common MTG words
    return {w for w in words if w not in _COMMON_MTG_WORDS}


def compute_functional_similarity(card_a_text: str, card_b_text: str) -> float:
    """Compute functional similarity between two cards using Jaccard index.

    Extracts functional keywords from oracle text (stripping reminder text
    and common MTG words) and computes the Jaccard similarity coefficient
    of the resulting token sets.

    Args:
        card_a_text: Oracle text of the first card.
        card_b_text: Oracle text of the second card.

    Returns:
        A float between 0.0 and 1.0 where 1.0 means identical
        functional keywords. Returns 0.0 if either card has no
        meaningful tokens.
    """
    tokens_a = _extract_functional_tokens(card_a_text)
    tokens_b = _extract_functional_tokens(card_b_text)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    if not union:
        return 0.0

    return len(intersection) / len(union)


def compute_duplicate_penalty(
    candidate_text: str,
    selected_texts: list[str],
    threshold: float = 0.3,
) -> float:
    """Compute a penalty for a candidate card based on similarity to selected cards.

    Penalizes cards that are functionally similar to cards already selected
    for the deck to encourage diversity.

    Args:
        candidate_text: Oracle text of the candidate card.
        selected_texts: List of oracle texts of already-selected cards.
        threshold: Similarity threshold above which cards are considered
            functional duplicates. Defaults to 0.3.

    Returns:
        A float penalty multiplier:
        1.0 if no selected card is similar.
        0.7 if exactly 1 selected card is similar.
        0.4 if exactly 2 selected cards are similar.
        0.2 if 3 or more selected cards are similar.
    """
    if not selected_texts:
        return 1.0

    similar_count = 0
    for selected_text in selected_texts:
        similarity = compute_functional_similarity(candidate_text, selected_text)
        if similarity >= threshold:
            similar_count += 1

    if similar_count >= 3:
        return 0.2
    if similar_count >= 2:
        return 0.4
    if similar_count >= 1:
        return 0.7

    return 1.0


def _get_cmc_bucket(card: object) -> int:
    """Extract the CMC bucket (0-7) from a candidate's card.

    Args:
        card: A Card object with a ``cmc`` attribute.

    Returns:
        Integer CMC bucket clamped to range 0-7.
    """
    return min(7, int(getattr(card, "cmc", 0)))


def _compute_llm_synergy_bonus(
    candidate_name: str,
    selected_names: list[str],
    matrix: dict[tuple[str, str], float],
) -> float:
    """Compute average LLM synergy between candidate and already-selected cards.

    Args:
        candidate_name: Name of the candidate card.
        selected_names: Names of already-selected cards.
        matrix: LLM synergy matrix with canonical keys.

    Returns:
        Average synergy score with selected cards, or 0.0 if no matches.
    """
    if not selected_names or not matrix:
        return 0.0

    total = 0.0
    count = 0
    for sel_name in selected_names:
        key = (min(candidate_name, sel_name), max(candidate_name, sel_name))
        if key in matrix:
            total += matrix[key]
            count += 1

    return total / count if count > 0 else 0.0


def optimize_for_budget(
    candidates: list[ScoredCandidate],
    budget: float,
    category_targets: dict[str, tuple[int, int]],
    ideal_curve: dict[int, float] | None = None,
    total_nonland_target: int = 0,
    card_texts: dict[int, str] | None = None,
    llm_synergy_matrix: dict[tuple[str, str], float] | None = None,
) -> list[ScoredCandidate]:
    """Select cards from candidates to fill category targets within budget.

    Category targets map category name to (min_count, max_count) tuples.
    Soft budget caps mean individual categories can exceed their max if
    the total budget allows it.

    When ``ideal_curve`` is provided, card scores are penalized based on
    how overfull the card's CMC bucket already is, encouraging a more
    balanced mana curve.

    Algorithm:
        1. Sort candidates by score descending within each category.
        2. Fill each category up to its minimum target.
        3. Backfill underfilled categories from overflow of other categories.
        4. Fill remaining slots from highest-scored unused candidates.
        5. If over budget, swap lowest-scored selected cards for cheaper
           alternatives until within budget.

    Penalties applied during Phases 2 and 3:
        - Curve penalty: penalizes cards in overfull CMC buckets.
        - Diminishing returns: penalizes categories that exceed max target.
        - Duplicate penalty: penalizes cards functionally similar to
          already-selected cards.

    Args:
        candidates: List of ScoredCandidate objects.
        budget: Total budget in USD.
        category_targets: Dict mapping category -> (min, max) counts.
        ideal_curve: Optional dict mapping CMC bucket -> ideal percentage
            of non-land cards. When provided, enables mana curve shaping.
        total_nonland_target: Target number of non-land cards. Required
            when ideal_curve is provided for accurate curve penalty
            computation.
        card_texts: Optional dict mapping card_id -> oracle text for
            functional duplicate detection.

    Returns:
        List of selected ScoredCandidate objects within (or near) budget.
    """
    if not candidates:
        return []

    use_curve = ideal_curve is not None and total_nonland_target > 0
    current_curve: dict[int, int] = {}
    # Track category counts for diminishing returns
    category_counts: dict[str, int] = {}
    # Track oracle texts of selected cards for duplicate detection
    selected_texts: list[str] = []
    # Track names of selected cards for LLM synergy bonus
    selected_names: list[str] = []

    def _track_selected(cand: ScoredCandidate) -> None:
        """Update tracking state after selecting a card."""
        category_counts[cand.category] = category_counts.get(cand.category, 0) + 1
        selected_names.append(cand.card.name)
        if card_texts is not None:
            text = card_texts.get(cand.card_id, "")
            if text:
                selected_texts.append(text)

    def _compute_adjusted_score(cand: ScoredCandidate) -> float:
        """Compute a candidate's score with all applicable penalties."""
        adjusted = cand.score

        # Apply curve penalty
        if use_curve and ideal_curve is not None:
            curve_pen = compute_curve_penalty(
                cand.card.cmc, current_curve, ideal_curve,
                total_nonland_target,
            )
            adjusted *= curve_pen

        # Apply diminishing returns penalty
        dim_pen = compute_diminishing_penalty(
            cand.category, category_counts, category_targets,
        )
        adjusted *= dim_pen

        # Apply duplicate penalty
        if card_texts is not None and selected_texts:
            cand_text = card_texts.get(cand.card_id, "")
            if cand_text:
                dup_pen = compute_duplicate_penalty(
                    cand_text, selected_texts,
                )
                adjusted *= dup_pen

        # Apply LLM synergy bonus
        if llm_synergy_matrix is not None and selected_names:
            llm_bonus = _compute_llm_synergy_bonus(
                cand.card.name, selected_names, llm_synergy_matrix,
            )
            adjusted *= (1.0 + llm_bonus * 0.15)

        return adjusted

    # Group candidates by category, sorted by score descending
    by_category: dict[str, list[ScoredCandidate]] = {}
    for cand in candidates:
        if cand.category not in by_category:
            by_category[cand.category] = []
        by_category[cand.category].append(cand)

    for cat in by_category:
        by_category[cat].sort(key=lambda c: c.score, reverse=True)

    selected: list[ScoredCandidate] = []
    selected_ids: set[int] = set()
    total_cost = 0.0

    # Phase 1: Fill category minimums (softer curve penalty, floor 0.5)
    for cat, (min_count, _max_count) in category_targets.items():
        cat_candidates = by_category.get(cat, [])
        # When using curve shaping, re-sort by curve-adjusted score
        if use_curve and ideal_curve is not None:
            scored_cands = []
            for cand in cat_candidates:
                penalty = compute_curve_penalty(
                    cand.card.cmc, current_curve, ideal_curve, total_nonland_target
                )
                # Softer penalty in Phase 1: floor at 0.5
                soft_penalty = max(penalty, 0.5)
                scored_cands.append((cand.score * soft_penalty, cand))
            scored_cands.sort(key=lambda x: x[0], reverse=True)
            ordered = [c for _, c in scored_cands]
        else:
            ordered = cat_candidates

        filled = 0
        for cand in ordered:
            if filled >= min_count:
                break
            if cand.card_id in selected_ids:
                continue
            selected.append(cand)
            selected_ids.add(cand.card_id)
            total_cost += cand.price
            _track_selected(cand)
            filled += 1
            if use_curve:
                bucket = _get_cmc_bucket(cand.card)
                current_curve[bucket] = current_curve.get(bucket, 0) + 1

    # Phase 2: Fill up to max targets where budget allows
    for cat, (_min_count, max_count) in category_targets.items():
        cat_candidates = by_category.get(cat, [])
        cat_selected = sum(1 for s in selected if s.category == cat)

        # Build available list of unselected candidates
        available = [
            c for c in cat_candidates if c.card_id not in selected_ids
        ]

        while cat_selected < max_count and available:
            # Re-score with all penalties and pick the best
            scored = [
                (c, _compute_adjusted_score(c)) for c in available
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            best_cand, _best_score = scored[0]

            # Soft cap: allow if total stays within budget
            if total_cost + best_cand.price > budget:
                available.remove(best_cand)
                continue

            selected.append(best_cand)
            selected_ids.add(best_cand.card_id)
            total_cost += best_cand.price
            _track_selected(best_cand)
            cat_selected += 1
            available.remove(best_cand)
            if use_curve:
                bucket = _get_cmc_bucket(best_cand.card)
                current_curve[bucket] = current_curve.get(bucket, 0) + 1

    # Phase 3: Backfill underfilled categories from unselected candidates
    for cat, (min_count, _max_count) in category_targets.items():
        cat_selected = sum(1 for s in selected if s.category == cat)
        deficit = min_count - cat_selected
        if deficit <= 0:
            continue
        # Try to find cards from any category that could fill this gap
        # Look through all unselected candidates sorted by adjusted score
        all_unselected = [
            c for c in candidates
            if c.card_id not in selected_ids
        ]
        # Score with penalties
        scored_unselected = [
            (c, _compute_adjusted_score(c)) for c in all_unselected
        ]
        scored_unselected.sort(key=lambda x: x[1], reverse=True)

        for cand, _adj_score in scored_unselected:
            if deficit <= 0:
                break
            if cand.card_id in selected_ids:
                continue
            # Re-assign to the deficit category
            reassigned = replace(cand, category=cat)
            selected.append(reassigned)
            selected_ids.add(cand.card_id)
            total_cost += cand.price
            _track_selected(reassigned)
            deficit -= 1

    # Phase 4: If over budget, swap lowest-scored cards for cheaper alternatives
    if total_cost > budget:
        _swap_for_cheaper(selected, selected_ids, candidates, budget)

    return selected


def _swap_for_cheaper(
    selected: list[ScoredCandidate],
    selected_ids: set[int],
    all_candidates: list[ScoredCandidate],
    budget: float,
) -> None:
    """Swap expensive low-scored cards for cheaper alternatives in-place.

    Iteratively replaces the lowest-scored selected card with the
    highest-scored unselected card that costs less, until budget is met
    or no more swaps are possible.

    Args:
        selected: List of selected ScoredCandidates (modified in-place).
        selected_ids: Set of selected card IDs (modified in-place).
        all_candidates: Full list of ScoredCandidates to draw replacements from.
        budget: Target budget in USD.
    """
    max_iterations = len(selected) * 2
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        total_cost = sum(c.price for c in selected)
        if total_cost <= budget:
            break

        overage = total_cost - budget

        # Find the lowest-scored selected card
        selected.sort(key=lambda c: c.score)
        swapped = False

        for i, worst in enumerate(selected):
            # Find a cheaper unselected alternative
            alternatives = [
                c for c in all_candidates
                if c.card_id not in selected_ids
                and c.price < worst.price
                and c.price <= worst.price - (overage * 0.1)
            ]
            if not alternatives:
                # Try any cheaper card
                alternatives = [
                    c for c in all_candidates
                    if c.card_id not in selected_ids
                    and c.price < worst.price
                ]
            if not alternatives:
                continue

            # Pick the highest scored cheap alternative
            alternatives.sort(key=lambda c: c.score, reverse=True)
            replacement = alternatives[0]

            # Perform swap
            selected_ids.discard(worst.card_id)
            selected_ids.add(replacement.card_id)
            # Preserve category assignment
            selected[i] = replace(replacement, category=worst.category)
            swapped = True
            break

        if not swapped:
            # No beneficial swaps possible; remove the cheapest low-scored card
            if selected:
                removed = selected.pop(0)
                selected_ids.discard(removed.card_id)
            break
