"""Feature engineering for card-commander ML model.

Extracts a flat feature vector from a (card, commander) pair for use
in training and inference of the power prediction model.
"""

from __future__ import annotations

from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.models.card import Card

# Feature names for interpretability and column labeling
FEATURE_NAMES: list[str] = [
    # Card features (10)
    "cmc",
    "color_count",
    "is_creature",
    "is_instant",
    "is_sorcery",
    "is_artifact",
    "is_enchantment",
    "is_planeswalker",
    "keyword_count",
    "oracle_length",
    # Commander features (2)
    "commander_cmc",
    "commander_color_count",
    # Interaction features (4)
    "color_overlap",
    "keyword_overlap",
    "theme_overlap",
    "tribal_match",
    # Category features (6)
    "is_ramp",
    "is_card_draw",
    "is_removal",
    "is_board_wipe",
    "is_win_condition",
    "is_protection",
]


def _count_shared_keywords(card: Card, commander: Card) -> int:
    """Count keywords shared between card and commander."""
    if not card.keywords or not commander.keywords:
        return 0
    card_kw = {k.lower() for k in card.keywords}
    cmd_kw = {k.lower() for k in commander.keywords}
    return len(card_kw & cmd_kw)


def _color_overlap_ratio(card: Card, commander: Card) -> float:
    """Compute ratio of card colors that overlap with commander identity."""
    if not card.color_identity or not commander.color_identity:
        return 0.0
    card_colors = set(card.color_identity)
    cmd_colors = set(commander.color_identity)
    overlap = card_colors & cmd_colors
    return len(overlap) / max(len(card_colors), 1)


def _theme_overlap(card: Card, commander: Card) -> float:
    """Compute theme overlap score between card and commander.

    Uses the synergy engine's extract_themes to find common themes.
    """
    from mtg_deck_maker.engine.synergy import extract_themes, score_theme_match

    themes = extract_themes(commander)
    if not themes:
        return 0.0
    return score_theme_match(themes, card)


def _tribal_match(card: Card, commander: Card) -> float:
    """Check if card shares creature types with commander."""
    from mtg_deck_maker.engine.synergy import _extract_creature_types

    cmd_types = _extract_creature_types(commander)
    if not cmd_types:
        return 0.0
    card_types = _extract_creature_types(card)
    if not card_types:
        return 0.0
    return 1.0 if cmd_types & card_types else 0.0


def _has_type(card: Card, type_name: str) -> float:
    """Check if card's type_line contains a specific type."""
    return 1.0 if type_name in (card.type_line or "") else 0.0


def _has_category(categories: list[tuple[str, float]], target: str) -> float:
    """Check if a card has a specific category."""
    return 1.0 if any(cat == target for cat, _ in categories) else 0.0


def extract_features(card: Card, commander: Card) -> list[float]:
    """Extract a flat feature vector from a card-commander pair.

    Returns a list of floats with length == len(FEATURE_NAMES).

    Args:
        card: The candidate card.
        commander: The commander card.

    Returns:
        List of float feature values.
    """
    categories = categorize_card(card)

    features = [
        # Card features (10)
        float(card.cmc),
        float(len(card.color_identity)),
        _has_type(card, "Creature"),
        _has_type(card, "Instant"),
        _has_type(card, "Sorcery"),
        _has_type(card, "Artifact"),
        _has_type(card, "Enchantment"),
        _has_type(card, "Planeswalker"),
        float(len(card.keywords)),
        float(len(card.oracle_text or "")),
        # Commander features (2)
        float(commander.cmc),
        float(len(commander.color_identity)),
        # Interaction features (4)
        _color_overlap_ratio(card, commander),
        float(_count_shared_keywords(card, commander)),
        _theme_overlap(card, commander),
        _tribal_match(card, commander),
        # Category features (6)
        _has_category(categories, Category.RAMP.value),
        _has_category(categories, Category.CARD_DRAW.value),
        _has_category(categories, Category.REMOVAL.value),
        _has_category(categories, Category.BOARD_WIPE.value),
        _has_category(categories, Category.WIN_CONDITION.value),
        _has_category(categories, Category.PROTECTION.value),
    ]

    return features
