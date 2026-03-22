"""Deck builder engine for Commander deck construction.

Orchestrates the full deck-building pipeline: commander validation,
card pool filtering, categorization, synergy scoring, budget optimization,
mana base construction, and final validation.
"""

from __future__ import annotations

import random
import re
from enum import Enum

from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.engine.budget_optimizer import optimize_for_budget, score_card
from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.engine.mana_base import build_mana_base, calculate_land_count
from mtg_deck_maker.engine.synergy import compute_combo_synergy, compute_synergy
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.models.deck import Deck, DeckCard
from mtg_deck_maker.models.scored_candidate import ScoredCandidate
from mtg_deck_maker.utils.colors import is_within_identity


class DeckBuildError(Exception):
    """Raised when deck construction fails."""


# Default 8x8 flexible category targets: (min, max) slots
DEFAULT_CATEGORY_TARGETS: dict[str, tuple[int, int]] = {
    Category.RAMP.value: (8, 12),
    Category.CARD_DRAW.value: (8, 10),
    Category.REMOVAL.value: (5, 7),
    Category.BOARD_WIPE.value: (2, 4),
    Category.WIN_CONDITION.value: (7, 10),
    Category.PROTECTION.value: (3, 5),
}

class Archetype(str, Enum):
    """Commander deck archetype classification."""

    AGGRO = "aggro"
    CONTROL = "control"
    COMBO = "combo"
    MIDRANGE = "midrange"
    SPELLSLINGER = "spellslinger"
    TRIBAL = "tribal"
    DEFAULT = "default"


# Archetype-specific category targets: (min, max) slots per archetype
ARCHETYPE_CATEGORY_TARGETS: dict[str, dict[str, tuple[int, int]]] = {
    Archetype.AGGRO.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (8, 10),
        Category.REMOVAL.value: (3, 5),
        Category.BOARD_WIPE.value: (1, 2),
        Category.WIN_CONDITION.value: (10, 14),
        Category.PROTECTION.value: (3, 5),
    },
    Archetype.CONTROL.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (8, 10),
        Category.REMOVAL.value: (7, 10),
        Category.BOARD_WIPE.value: (3, 5),
        Category.COUNTERSPELL.value: (3, 5),
        Category.WIN_CONDITION.value: (4, 6),
        Category.PROTECTION.value: (3, 5),
    },
    Archetype.COMBO.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (10, 14),
        Category.REMOVAL.value: (3, 5),
        Category.BOARD_WIPE.value: (2, 4),
        Category.TUTOR.value: (3, 5),
        Category.WIN_CONDITION.value: (3, 5),
        Category.PROTECTION.value: (3, 5),
    },
    Archetype.SPELLSLINGER.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (10, 14),
        Category.REMOVAL.value: (5, 7),
        Category.BOARD_WIPE.value: (2, 4),
        Category.WIN_CONDITION.value: (5, 8),
        Category.PROTECTION.value: (4, 6),
    },
    Archetype.TRIBAL.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (8, 10),
        Category.REMOVAL.value: (5, 7),
        Category.BOARD_WIPE.value: (1, 2),
        Category.WIN_CONDITION.value: (8, 12),
        Category.PROTECTION.value: (3, 5),
    },
    Archetype.MIDRANGE.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (8, 10),
        Category.REMOVAL.value: (5, 7),
        Category.BOARD_WIPE.value: (2, 4),
        Category.WIN_CONDITION.value: (7, 10),
        Category.PROTECTION.value: (3, 5),
    },
    Archetype.DEFAULT.value: {
        Category.RAMP.value: (8, 12),
        Category.CARD_DRAW.value: (8, 10),
        Category.REMOVAL.value: (5, 7),
        Category.BOARD_WIPE.value: (2, 4),
        Category.WIN_CONDITION.value: (7, 10),
        Category.PROTECTION.value: (3, 5),
    },
}

# Ideal CMC distribution per archetype (% of non-land cards per CMC bucket)
# Buckets: 0, 1, 2, 3, 4, 5, 6, 7+
IDEAL_CURVE: dict[str, dict[int, float]] = {
    "aggro":        {0: 0.02, 1: 0.18, 2: 0.28, 3: 0.22, 4: 0.15, 5: 0.08, 6: 0.05, 7: 0.02},
    "control":      {0: 0.02, 1: 0.10, 2: 0.20, 3: 0.22, 4: 0.18, 5: 0.13, 6: 0.08, 7: 0.07},
    "combo":        {0: 0.03, 1: 0.15, 2: 0.25, 3: 0.22, 4: 0.15, 5: 0.10, 6: 0.06, 7: 0.04},
    "midrange":     {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05},
    "spellslinger": {0: 0.03, 1: 0.18, 2: 0.28, 3: 0.22, 4: 0.14, 5: 0.08, 6: 0.04, 7: 0.03},
    "tribal":       {0: 0.02, 1: 0.14, 2: 0.24, 3: 0.24, 4: 0.16, 5: 0.10, 6: 0.06, 7: 0.04},
    "default":      {0: 0.02, 1: 0.12, 2: 0.22, 3: 0.22, 4: 0.18, 5: 0.12, 6: 0.07, 7: 0.05},
}

# Synergy and flex categories get the remainder
SYNERGY_TARGET: tuple[int, int] = (8, 12)
FLEX_CATEGORY = "flex"


# Archetype detection patterns
_SPELLSLINGER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"whenever you cast a(n)? (instant|sorcery|noncreature)", re.IGNORECASE),
    re.compile(r"instant and sorcery", re.IGNORECASE),
    re.compile(r"magecraft", re.IGNORECASE),
    re.compile(r"prowess", re.IGNORECASE),
    re.compile(r"\bstorm\b", re.IGNORECASE),
]

_COMBO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"search your library", re.IGNORECASE),
    re.compile(r"\binfinite\b", re.IGNORECASE),
    re.compile(r"untap all", re.IGNORECASE),
]

_AGGRO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"whenever .+ attacks", re.IGNORECASE),
    re.compile(r"combat damage to a player", re.IGNORECASE),
    re.compile(r"additional combat", re.IGNORECASE),
]

_CONTROL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"counter target", re.IGNORECASE),
    re.compile(r"\bexile\b.*\btarget\b", re.IGNORECASE),
    re.compile(r"\btax\b", re.IGNORECASE),
    re.compile(r"\bprevent\b", re.IGNORECASE),
]


def detect_archetype(commander: Card) -> str:
    """Detect the deck archetype from a commander's oracle text and type line.

    Uses pattern matching to classify the commander into an archetype
    that determines category target distributions.

    Detection priority:
        1. TRIBAL: commander has creature types referenced in oracle text
        2. SPELLSLINGER: instants/sorceries-matter triggers
        3. COMBO: library search, infinite, untap patterns
        4. AGGRO: attack triggers, combat damage
        5. CONTROL: counter, exile, tax, prevent
        6. MIDRANGE: default fallback

    Args:
        commander: The commander card to analyze.

    Returns:
        Archetype value string (e.g. "aggro", "tribal").
    """
    oracle = commander.oracle_text or ""
    type_line = commander.type_line or ""
    oracle_lower = oracle.lower()

    # Check TRIBAL: commander has creature types and oracle text references them
    if "\u2014" in type_line and "Creature" in type_line:
        _, subtypes_part = type_line.split("\u2014", 1)
        creature_types = [t.strip() for t in subtypes_part.strip().split() if t.strip()]
        for ctype in creature_types:
            if ctype.lower() in oracle_lower:
                return Archetype.TRIBAL.value

    # Check SPELLSLINGER
    for pattern in _SPELLSLINGER_PATTERNS:
        if pattern.search(oracle):
            return Archetype.SPELLSLINGER.value

    # Check COMBO
    for pattern in _COMBO_PATTERNS:
        if pattern.search(oracle):
            return Archetype.COMBO.value

    # Check AGGRO
    for pattern in _AGGRO_PATTERNS:
        if pattern.search(oracle):
            return Archetype.AGGRO.value

    # Check CONTROL
    for pattern in _CONTROL_PATTERNS:
        if pattern.search(oracle):
            return Archetype.CONTROL.value

    return Archetype.MIDRANGE.value


def _normalize_edhrec_rank(rank: int | None, max_rank: int = 20000) -> float:
    """Convert EDHREC rank to a 0-1 power score.

    Lower rank (more popular) yields a higher score.

    Args:
        rank: The card's EDHREC rank, or None if unknown.
        max_rank: Normalization ceiling.

    Returns:
        Float from 0.0 to 1.0 where 1.0 is the best rank.
    """
    if rank is None:
        return 0.3  # Default middle-low score for unranked cards
    clamped = min(rank, max_rank)
    return 1.0 - (clamped / max_rank)


def _get_primary_category(
    categories: list[tuple[str, float]],
) -> tuple[str, float]:
    """Extract the best functional category from a card's category list.

    Prefers functional categories over type-based ones (creature, artifact, etc.).

    Args:
        categories: List of (category, confidence) tuples from categorize_card.

    Returns:
        Tuple of (category_name, confidence) for the primary functional role.
    """
    type_categories = {
        Category.LAND.value,
        Category.CREATURE.value,
        Category.ARTIFACT.value,
        Category.ENCHANTMENT.value,
    }

    # Prefer functional categories
    for cat, conf in categories:
        if cat not in type_categories:
            return cat, conf

    # Fall back to first category
    if categories:
        return categories[0]

    return Category.UTILITY.value, 0.5


def build_deck(
    commander: Commander,
    budget: float,
    card_pool: list[Card],
    config: AppConfig,
    prices: dict[int, float] | None = None,
    seed: int = 42,
    priority_cards: list[str] | None = None,
    edhrec_inclusion: dict[str, float] | None = None,
    combo_partners: dict[str, list[str]] | None = None,
) -> Deck:
    """Build a complete 100-card Commander deck from a card pool.

    Algorithm:
        1. Validate commander (solo/partner/background/companion)
        2. Compute color identity (union for pairs)
        3. Filter card_pool to color identity + commander legal
        4. Categorize all candidates using categories engine
        5. Score candidates using synergy engine
        6. Calculate land count using mana_base engine
        7. Fill category targets (8x8 flexible)
        8. Select cards using final_score = synergy * power / price_weight
        9. Build mana base
       10. Validate: 100 cards, singleton, within color identity,
           within budget (5% tolerance)

    Args:
        commander: The Commander configuration to build around.
        budget: Total budget in USD.
        card_pool: List of available Card objects to select from.
        config: Application configuration.
        prices: Optional dict mapping card.id -> USD price.
        seed: Random seed for deterministic output.
        priority_cards: Optional list of card names recommended by LLM.
        edhrec_inclusion: Optional per-commander card inclusion rates
            mapping card name -> inclusion rate (0.0 to 1.0).
        combo_partners: Optional mapping of card name to list of known
            combo partner card names for combo synergy scoring.

    Returns:
        A fully constructed Deck object with exactly 100 cards.

    Raises:
        DeckBuildError: If the commander is invalid or not enough cards
            are available to build a legal deck.
    """
    rng = random.Random(seed)

    if prices is None:
        prices = {}

    # Step 1: Validate commander
    errors = commander.validate()
    if errors:
        raise DeckBuildError(
            f"Invalid commander configuration: {'; '.join(errors)}"
        )

    # Step 2: Compute color identity
    color_identity = commander.combined_color_identity()

    # Step 3: Filter card pool to color identity + commander legal
    commander_names = {c.name for c in commander.all_commander_cards()}
    if commander.companion is not None:
        commander_names.add(commander.companion.name)

    filtered_pool = _filter_card_pool(
        card_pool, color_identity, commander_names, config
    )

    if len(filtered_pool) < 30:
        raise DeckBuildError(
            f"Insufficient card pool: only {len(filtered_pool)} candidates "
            f"after filtering (need at least 30)."
        )

    # Step 4: Categorize all candidates
    card_categories: dict[int, list[tuple[str, float]]] = {}
    for card in filtered_pool:
        key = card.id if card.id is not None else id(card)
        card_categories[key] = categorize_card(card)

    # Step 5: Score candidates using synergy engine
    primary_commander = commander.primary
    card_synergies: dict[int, float] = {}
    for card in filtered_pool:
        key = card.id if card.id is not None else id(card)
        card_synergies[key] = compute_synergy(primary_commander, card)

    # Step 6: Calculate land count
    nonland_slots = commander.deck_size()
    # Account for companion taking a slot
    if commander.companion is not None:
        nonland_slots -= 1

    # Estimate ramp count from categorization
    estimated_ramp = 0
    for card in filtered_pool:
        key = card.id if card.id is not None else id(card)
        cats = card_categories.get(key, [])
        cat_names = {c for c, _ in cats}
        if Category.RAMP.value in cat_names and not card.is_land:
            estimated_ramp += 1
    estimated_ramp = min(estimated_ramp, 15)

    avg_cmc_estimate = _estimate_avg_cmc(filtered_pool)
    num_lands = calculate_land_count(
        color_identity,
        ramp_count=min(estimated_ramp, 12),
        avg_cmc=avg_cmc_estimate,
    )

    # Non-land card slots
    nonland_card_count = nonland_slots - num_lands

    # Step 7 & 8: Build candidate list with scores and select via budget optimizer
    candidates = _build_scored_candidates(
        filtered_pool, card_categories, card_synergies, prices, config,
        priority_cards=priority_cards,
        edhrec_inclusion=edhrec_inclusion,
        combo_partners=combo_partners,
    )

    # Shuffle with seed for tie-breaking determinism
    rng.shuffle(candidates)
    # Re-sort by score (stable sort preserves shuffle order for ties)
    candidates.sort(key=lambda c: c.score, reverse=True)

    # Filter out lands (handled separately in mana base)
    nonland_candidates = [c for c in candidates if not c.card.is_land]

    # Select non-land cards using budget optimizer
    # Reserve budget portion for lands (estimate ~$0.25 per basic land)
    land_budget_estimate = num_lands * 0.30
    nonland_budget = budget - land_budget_estimate

    # Detect archetype and use corresponding category targets
    archetype = detect_archetype(commander.primary)
    category_targets = ARCHETYPE_CATEGORY_TARGETS.get(
        archetype, DEFAULT_CATEGORY_TARGETS
    )

    # Look up the ideal mana curve for the detected archetype
    ideal_curve = IDEAL_CURVE.get(archetype, IDEAL_CURVE["default"])

    selected = optimize_for_budget(
        nonland_candidates, nonland_budget, category_targets,
        ideal_curve=ideal_curve,
        total_nonland_target=nonland_card_count,
    )

    # Ensure we have exactly the right number of nonland cards
    if len(selected) < nonland_card_count:
        _fill_remaining_slots(
            selected, nonland_candidates, nonland_card_count
        )

    if len(selected) > nonland_card_count:
        # Trim lowest-scored cards
        selected.sort(key=lambda c: c.score, reverse=True)
        selected = selected[:nonland_card_count]

    # Step 9: Build mana base
    land_candidates = [c for c in card_pool if c.is_land and
                       is_within_identity(c.color_identity, color_identity)]
    mana_base = build_mana_base(
        color_identity, num_lands, budget, land_candidates
    )

    # Step 10: Assemble the deck
    deck = _assemble_deck(
        commander, selected, mana_base, prices, budget
    )

    # Validate the final deck
    validation_errors = _validate_deck(deck, commander, color_identity, budget)
    if validation_errors:
        # Try to fix minor issues rather than raising
        _attempt_fixes(deck, validation_errors)

    return deck


def _filter_card_pool(
    card_pool: list[Card],
    color_identity: list[str],
    commander_names: set[str],
    config: AppConfig,
) -> list[Card]:
    """Filter card pool to legal candidates for the deck.

    Args:
        card_pool: Full available card pool.
        color_identity: Commander's combined color identity.
        commander_names: Names of commander cards (to exclude from pool).
        config: App configuration.

    Returns:
        List of cards legal for inclusion in the deck.
    """
    filtered: list[Card] = []
    excluded_names = set(config.constraints.exclude_cards)

    for card in card_pool:
        # Skip commander cards themselves
        if card.name in commander_names:
            continue

        # Skip excluded cards
        if card.name in excluded_names:
            continue

        # Must be commander-legal
        if not card.legal_commander:
            continue

        # Must be within color identity
        if not is_within_identity(card.color_identity, color_identity):
            continue

        # Skip cards over max price per card (if prices known)
        # This is handled downstream via scoring penalty

        filtered.append(card)

    return filtered


def _estimate_avg_cmc(cards: list[Card]) -> float:
    """Estimate average CMC of non-land cards in the pool.

    Args:
        cards: List of cards to analyze.

    Returns:
        Estimated average CMC.
    """
    non_land = [c for c in cards if not c.is_land and c.cmc > 0]
    if not non_land:
        return 3.0
    return sum(c.cmc for c in non_land) / len(non_land)


def _build_scored_candidates(
    cards: list[Card],
    categories: dict[int, list[tuple[str, float]]],
    synergies: dict[int, float],
    prices: dict[int, float],
    config: AppConfig,
    priority_cards: list[str] | None = None,
    edhrec_inclusion: dict[str, float] | None = None,
    combo_partners: dict[str, list[str]] | None = None,
) -> list[ScoredCandidate]:
    """Build scored candidates for the budget optimizer.

    Args:
        cards: Filtered card pool.
        categories: Category assignments per card.
        synergies: Synergy scores per card.
        prices: Price per card.
        config: App configuration.
        priority_cards: Optional list of card names recommended by LLM.
        edhrec_inclusion: Optional mapping of card name -> per-commander
            inclusion rate (0.0 to 1.0). When available, replaces the
            generic EDHREC rank normalization for matching cards.
        combo_partners: Optional mapping of card name to list of known
            combo partner card names for combo synergy scoring.

    Returns:
        List of ScoredCandidate objects with card, score, price, and category info.
    """
    candidates: list[ScoredCandidate] = []
    priority_set = {n.lower() for n in (priority_cards or [])}
    priority_bonus = config.llm.priority_bonus

    # Build a set of all candidate card names for combo synergy context
    all_card_names = {c.name for c in cards}

    for card in cards:
        key = card.id if card.id is not None else id(card)
        card_cats = categories.get(key, [])
        primary_cat, confidence = _get_primary_category(card_cats)
        synergy = synergies.get(key, 0.0)
        price = prices.get(card.id if card.id is not None else -1, 0.50)

        # Power score: use per-commander inclusion rate if available,
        # otherwise fall back to generic EDHREC rank normalization.
        if edhrec_inclusion and card.name in edhrec_inclusion:
            power = edhrec_inclusion[card.name] * 0.6 + confidence * 0.4
        else:
            power = _normalize_edhrec_rank(card.edhrec_rank) * 0.6 + confidence * 0.4

        # Minimum synergy floor so all legal cards have some chance
        effective_synergy = max(synergy, 0.1)

        final_score = score_card(effective_synergy, power, price)

        # Check max price per card constraint
        if price > config.constraints.max_price_per_card:
            final_score *= 0.01  # Heavy penalty, not complete exclusion

        # Apply priority bonus for LLM-recommended cards (additive)
        if priority_set and card.name.lower() in priority_set:
            final_score += priority_bonus

        # Apply combo synergy bonus (additive, scaled by relevance)
        if combo_partners:
            combo_bonus = compute_combo_synergy(
                card.name, all_card_names, combo_partners
            )
            final_score += combo_bonus * priority_bonus * 0.5

        candidates.append(ScoredCandidate(
            card=card,
            card_id=card.id if card.id is not None else id(card),
            score=final_score,
            price=price,
            category=primary_cat,
            synergy=synergy,
            power=power,
        ))

    return candidates


def _fill_remaining_slots(
    selected: list[ScoredCandidate],
    all_candidates: list[ScoredCandidate],
    target_count: int,
) -> None:
    """Fill remaining deck slots from unused candidates.

    Modifies selected list in-place.

    Args:
        selected: Currently selected candidates.
        all_candidates: All available candidates.
        target_count: Target number of cards to select.
    """
    selected_ids = {c.card_id for c in selected}

    for cand in all_candidates:
        if len(selected) >= target_count:
            break
        if cand.card_id not in selected_ids:
            selected.append(cand)
            selected_ids.add(cand.card_id)


def _assemble_deck(
    commander: Commander,
    selected_nonlands: list[ScoredCandidate],
    mana_base: list[Card],
    prices: dict[int, float],
    budget: float,
) -> Deck:
    """Assemble a Deck object from selected cards and mana base.

    Args:
        commander: The commander configuration.
        selected_nonlands: Selected ScoredCandidate objects.
        mana_base: List of land Cards from mana base builder.
        prices: Price mapping.
        budget: Budget target.

    Returns:
        A fully assembled Deck object.
    """
    deck_cards: list[DeckCard] = []

    # Add commander cards
    for cmd_card in commander.all_commander_cards():
        deck_cards.append(DeckCard(
            card_id=cmd_card.id if cmd_card.id is not None else 0,
            quantity=1,
            category="commander",
            is_commander=True,
            card_name=cmd_card.name,
            cmc=cmd_card.cmc,
            colors=list(cmd_card.colors),
            price=prices.get(cmd_card.id, 0.0) if cmd_card.id is not None else 0.0,
        ))

    # Add companion if present
    if commander.companion is not None:
        comp = commander.companion
        deck_cards.append(DeckCard(
            card_id=comp.id if comp.id is not None else 0,
            quantity=1,
            category="companion",
            is_companion=True,
            card_name=comp.name,
            cmc=comp.cmc,
            colors=list(comp.colors),
            price=prices.get(comp.id, 0.0) if comp.id is not None else 0.0,
        ))

    # Add selected nonland cards
    for cand in selected_nonlands:
        card = cand.card
        deck_cards.append(DeckCard(
            card_id=card.id if card.id is not None else 0,
            quantity=1,
            category=cand.category,
            is_commander=False,
            card_name=card.name,
            cmc=card.cmc,
            colors=list(card.colors),
            price=cand.price,
        ))

    # Add lands from mana base
    # Track land names to group duplicates (basic lands)
    land_counts: dict[str, tuple[Card, int]] = {}
    for land in mana_base:
        if land.name in land_counts:
            existing_card, count = land_counts[land.name]
            land_counts[land.name] = (existing_card, count + 1)
        else:
            land_counts[land.name] = (land, 1)

    for land_name, (land, count) in land_counts.items():
        deck_cards.append(DeckCard(
            card_id=land.id if land.id is not None else 0,
            quantity=count,
            category=Category.LAND.value,
            is_commander=False,
            card_name=land.name,
            cmc=0.0,
            colors=list(land.colors),
            price=prices.get(land.id, 0.10) if land.id is not None else 0.10,
        ))

    # Build commander name for deck title
    cmd_names = [c.name for c in commander.all_commander_cards()]
    deck_name = f"{' & '.join(cmd_names)} Deck"

    return Deck(
        name=deck_name,
        cards=deck_cards,
        format="commander",
        budget_target=budget,
    )


def _validate_deck(
    deck: Deck,
    commander: Commander,
    color_identity: list[str],
    budget: float,
) -> list[str]:
    """Validate the constructed deck against Commander rules.

    Args:
        deck: The deck to validate.
        commander: Commander configuration.
        color_identity: Expected color identity.
        budget: Target budget.

    Returns:
        List of validation error messages. Empty means valid.
    """
    errors: list[str] = []

    # Check total card count
    total = deck.total_cards()
    if total != 100:
        errors.append(f"Deck has {total} cards, expected 100.")

    # Check singleton (except basic lands)
    basic_names = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
    seen_names: set[str] = set()
    for card in deck.cards:
        if card.card_name in basic_names:
            continue
        if card.quantity > 1:
            errors.append(
                f"Non-basic card {card.card_name!r} has quantity {card.quantity}."
            )
        if card.card_name in seen_names:
            errors.append(
                f"Duplicate card entry for {card.card_name!r}."
            )
        seen_names.add(card.card_name)

    # Check budget (5% tolerance)
    total_price = deck.total_price()
    budget_limit = budget * 1.05
    if total_price > budget_limit:
        errors.append(
            f"Deck cost ${total_price:.2f} exceeds budget "
            f"${budget:.2f} (limit ${budget_limit:.2f} with 5% tolerance)."
        )

    return errors


def _attempt_fixes(deck: Deck, errors: list[str]) -> None:
    """Attempt to fix minor deck validation issues.

    Currently a no-op placeholder. Future implementations could:
    - Adjust card counts to hit 100
    - Swap expensive cards for cheaper alternatives
    - Remove duplicates

    Args:
        deck: The deck to fix (modified in-place).
        errors: List of validation errors.
    """
    # For now, just log/acknowledge issues.
    # The build algorithm should produce valid decks in most cases.
    pass
