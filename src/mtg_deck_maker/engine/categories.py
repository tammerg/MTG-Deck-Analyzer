"""Card categorization engine using rule-based oracle text and keyword matching.

Categorizes MTG cards into functional roles (ramp, card draw, removal, etc.)
using regex pattern matching against oracle_text and type_line fields.
"""

from __future__ import annotations

import re
from enum import Enum

from mtg_deck_maker.models.card import Card


class Category(str, Enum):
    """Functional categories for MTG card classification."""

    RAMP = "ramp"
    CARD_DRAW = "card_draw"
    REMOVAL = "removal"
    BOARD_WIPE = "board_wipe"
    COUNTERSPELL = "counterspell"
    PROTECTION = "protection"
    RECURSION = "recursion"
    WIN_CONDITION = "win_condition"
    TUTOR = "tutor"
    LAND = "land"
    CREATURE = "creature"
    ARTIFACT = "artifact"
    ENCHANTMENT = "enchantment"
    UTILITY = "utility"


# Regex for reminder text: text enclosed in parentheses
_REMINDER_TEXT_RE = re.compile(r"\([^)]*\)")


def _strip_reminder_text(text: str) -> str:
    """Remove reminder text (parenthesized text) from oracle text.

    Args:
        text: Raw oracle text potentially containing reminder text.

    Returns:
        Oracle text with reminder text removed.
    """
    return _REMINDER_TEXT_RE.sub("", text)


# Category detection rules: list of (pattern, confidence) tuples per category.
# Patterns are compiled regexes applied to oracle_text with reminder text stripped.
_RAMP_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"search your library for a.*land", re.IGNORECASE), 0.9),
    (re.compile(r"search your library for.*\bland card", re.IGNORECASE), 0.9),
    (re.compile(r"add \{[WUBRGC]", re.IGNORECASE), 0.8),
    (re.compile(r"add one mana of any", re.IGNORECASE), 0.8),
    (re.compile(r"add \w+ mana", re.IGNORECASE), 0.7),
]

_CARD_DRAW_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"draw a card", re.IGNORECASE), 0.9),
    (re.compile(r"draw \w+ cards", re.IGNORECASE), 0.9),
    (re.compile(r"draw cards", re.IGNORECASE), 0.9),
    (re.compile(r"investigate", re.IGNORECASE), 0.8),
    (re.compile(r"create.*clue", re.IGNORECASE), 0.8),
]

_REMOVAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"destroy target", re.IGNORECASE), 0.9),
    (re.compile(r"exile target", re.IGNORECASE), 0.9),
    (re.compile(r"deals? \d+ damage to.*target", re.IGNORECASE), 0.8),
    (re.compile(r"-\d+/-\d+ until", re.IGNORECASE), 0.7),
]

_BOARD_WIPE_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"destroy all", re.IGNORECASE), 0.95),
    (re.compile(r"exile all", re.IGNORECASE), 0.95),
    (re.compile(r"each.*creature.*gets -", re.IGNORECASE), 0.85),
    (re.compile(r"all creatures get -", re.IGNORECASE), 0.85),
]

_COUNTERSPELL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"counter target spell", re.IGNORECASE), 0.95),
    (re.compile(r"counter target.*spell", re.IGNORECASE), 0.9),
    (re.compile(r"counter target.*ability", re.IGNORECASE), 0.85),
]

_PROTECTION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"hexproof", re.IGNORECASE), 0.85),
    (re.compile(r"indestructible", re.IGNORECASE), 0.85),
    (re.compile(r"shroud", re.IGNORECASE), 0.8),
    (re.compile(r"protection from", re.IGNORECASE), 0.8),
]

_RECURSION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"return.*from.*graveyard", re.IGNORECASE), 0.9),
    (re.compile(r"put.*from.*graveyard", re.IGNORECASE), 0.85),
]

_WIN_CONDITION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"you win the game", re.IGNORECASE), 1.0),
    (re.compile(r"each opponent loses", re.IGNORECASE), 0.9),
    (re.compile(r"commander damage", re.IGNORECASE), 0.6),
]

_TUTOR_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"search your library for a card", re.IGNORECASE), 0.9),
    (re.compile(r"search your library for an?\b", re.IGNORECASE), 0.8),
]

# Tutor negative filter: if the search is specifically for lands, it is RAMP not TUTOR
_TUTOR_LAND_FILTER = re.compile(
    r"search your library for.*\bland\b", re.IGNORECASE
)


def _match_patterns(
    text: str, patterns: list[tuple[re.Pattern[str], float]]
) -> float:
    """Match text against a list of patterns, returning the highest confidence.

    Args:
        text: Oracle text to match against (reminder text already stripped).
        patterns: List of (compiled_regex, confidence) tuples.

    Returns:
        Highest confidence score among matched patterns, or 0.0 if no match.
    """
    max_confidence = 0.0
    for pattern, confidence in patterns:
        if pattern.search(text):
            max_confidence = max(max_confidence, confidence)
    return max_confidence


def categorize_card(card: Card) -> list[tuple[str, float]]:
    """Categorize a card into functional roles with confidence scores.

    A card can belong to multiple categories. For example, a creature that
    draws cards will be categorized as both CREATURE and CARD_DRAW.

    Args:
        card: The Card to categorize.

    Returns:
        List of (category_value, confidence) tuples sorted by confidence
        descending. Each category_value is the string value of a Category enum.
    """
    categories: list[tuple[str, float]] = []
    oracle_text = _strip_reminder_text(card.oracle_text) if card.oracle_text else ""
    type_line = card.type_line or ""

    # Type-based categories (always high confidence from type_line)
    if "Land" in type_line:
        categories.append((Category.LAND.value, 1.0))
    if "Creature" in type_line:
        categories.append((Category.CREATURE.value, 1.0))
    if "Artifact" in type_line:
        categories.append((Category.ARTIFACT.value, 1.0))
    if "Enchantment" in type_line:
        categories.append((Category.ENCHANTMENT.value, 1.0))

    # Ramp detection
    ramp_conf = _match_patterns(oracle_text, _RAMP_PATTERNS)
    # Artifact mana rocks: artifact with low CMC and mana ability
    if (
        "Artifact" in type_line
        and card.cmc <= 3.0
        and ramp_conf > 0
    ):
        ramp_conf = max(ramp_conf, 0.85)
    if ramp_conf > 0:
        categories.append((Category.RAMP.value, ramp_conf))

    # Card draw detection
    draw_conf = _match_patterns(oracle_text, _CARD_DRAW_PATTERNS)
    if draw_conf > 0:
        categories.append((Category.CARD_DRAW.value, draw_conf))

    # Removal detection (targeted)
    removal_conf = _match_patterns(oracle_text, _REMOVAL_PATTERNS)
    if removal_conf > 0:
        categories.append((Category.REMOVAL.value, removal_conf))

    # Board wipe detection
    wipe_conf = _match_patterns(oracle_text, _BOARD_WIPE_PATTERNS)
    if wipe_conf > 0:
        categories.append((Category.BOARD_WIPE.value, wipe_conf))

    # Counterspell detection
    counter_conf = _match_patterns(oracle_text, _COUNTERSPELL_PATTERNS)
    if counter_conf > 0:
        categories.append((Category.COUNTERSPELL.value, counter_conf))

    # Protection detection
    prot_conf = _match_patterns(oracle_text, _PROTECTION_PATTERNS)
    if prot_conf > 0:
        categories.append((Category.PROTECTION.value, prot_conf))

    # Recursion detection
    recur_conf = _match_patterns(oracle_text, _RECURSION_PATTERNS)
    if recur_conf > 0:
        categories.append((Category.RECURSION.value, recur_conf))

    # Win condition detection
    win_conf = _match_patterns(oracle_text, _WIN_CONDITION_PATTERNS)
    if win_conf > 0:
        categories.append((Category.WIN_CONDITION.value, win_conf))

    # Tutor detection (non-land searches)
    tutor_conf = _match_patterns(oracle_text, _TUTOR_PATTERNS)
    if tutor_conf > 0:
        # Filter out land-specific searches (those are ramp, not tutors)
        if _TUTOR_LAND_FILTER.search(oracle_text):
            # If the only search text is for lands, skip tutor category
            # But if there is also a non-land search, keep it
            non_land_search = re.search(
                r"search your library for a(?!.*\bland\b).*card",
                oracle_text,
                re.IGNORECASE,
            )
            if not non_land_search:
                tutor_conf = 0.0
        if tutor_conf > 0:
            categories.append((Category.TUTOR.value, tutor_conf))

    # If no functional category was assigned beyond type, mark as utility
    functional_cats = {
        Category.RAMP.value,
        Category.CARD_DRAW.value,
        Category.REMOVAL.value,
        Category.BOARD_WIPE.value,
        Category.COUNTERSPELL.value,
        Category.PROTECTION.value,
        Category.RECURSION.value,
        Category.WIN_CONDITION.value,
        Category.TUTOR.value,
    }
    assigned_cats = {cat for cat, _ in categories}
    if not assigned_cats.intersection(functional_cats):
        categories.append((Category.UTILITY.value, 0.5))

    # Sort by confidence descending
    categories.sort(key=lambda x: x[1], reverse=True)
    return categories


def bulk_categorize(cards: list[Card]) -> dict[int, list[tuple[str, float]]]:
    """Categorize multiple cards in batch.

    Args:
        cards: List of Card objects to categorize.

    Returns:
        Dict mapping card ID to list of (category, confidence) tuples.
        Cards without an ID are keyed by their index in the input list
        as a negative number (-1, -2, etc.) to distinguish from real IDs.
    """
    results: dict[int, list[tuple[str, float]]] = {}
    for idx, card in enumerate(cards):
        key = card.id if card.id is not None else -(idx + 1)
        results[key] = categorize_card(card)
    return results
