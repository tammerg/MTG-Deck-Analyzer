"""Card categorization engine using rule-based oracle text and keyword matching.

Categorizes MTG cards into functional roles (ramp, card draw, removal, etc.)
using regex pattern matching against oracle_text and type_line fields.
"""

from __future__ import annotations

import re
from enum import Enum

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.utils.text import REMINDER_TEXT_RE


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


def _strip_reminder_text(text: str) -> str:
    """Remove reminder text (parenthesized text) from oracle text.

    Args:
        text: Raw oracle text potentially containing reminder text.

    Returns:
        Oracle text with reminder text removed.
    """
    return REMINDER_TEXT_RE.sub("", text)


# Category detection rules: list of (pattern, confidence) tuples per category.
# Patterns are compiled regexes applied to oracle_text with reminder text stripped.
_RAMP_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"search your library for a.*land", re.IGNORECASE), 0.9),
    (re.compile(r"search your library for.*\bland card", re.IGNORECASE), 0.9),
    (re.compile(r"add \{[WUBRGC]", re.IGNORECASE), 0.8),
    (re.compile(r"add one mana of any", re.IGNORECASE), 0.8),
    (re.compile(r"add \w+ mana", re.IGNORECASE), 0.7),
    # Treasure token creation (mana generation)
    (re.compile(r"create.*\btreasure\b", re.IGNORECASE), 0.8),
    # Food token creation (pseudo-ramp, lower confidence)
    (re.compile(r"create.*\bfood\b", re.IGNORECASE), 0.6),
]

_CARD_DRAW_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"draw a card", re.IGNORECASE), 0.9),
    (re.compile(r"draw \w+ cards", re.IGNORECASE), 0.9),
    (re.compile(r"draw cards", re.IGNORECASE), 0.9),
    (re.compile(r"investigate", re.IGNORECASE), 0.8),
    (re.compile(r"create.*clue", re.IGNORECASE), 0.8),
    # Impulsive draw: exile top cards + may play/cast
    (re.compile(r"exile the top.*you may play", re.IGNORECASE), 0.8),
    (re.compile(r"exile the top.*you may cast", re.IGNORECASE), 0.8),
    # Look at top N, put into hand
    (re.compile(r"look at the top.*into your hand", re.IGNORECASE), 0.8),
    # Scry as card selection (lower confidence)
    (re.compile(r"\bscry\b", re.IGNORECASE), 0.5),
    # Surveil as card selection (lower confidence)
    (re.compile(r"\bsurveil\b", re.IGNORECASE), 0.5),
    # Connive as card selection (lower confidence)
    (re.compile(r"\bconnives?\b", re.IGNORECASE), 0.6),
]

_REMOVAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"destroy target", re.IGNORECASE), 0.9),
    (re.compile(r"exile target", re.IGNORECASE), 0.9),
    (re.compile(r"deals? \d+ damage to.*target", re.IGNORECASE), 0.8),
    (re.compile(r"-\d+/-\d+ until", re.IGNORECASE), 0.7),
    # Fight-based removal (word boundary to avoid false positives)
    (re.compile(r"\bfights?\b", re.IGNORECASE), 0.7),
    # Bounce as soft removal (lower confidence since temporary)
    (re.compile(r"return target.*to its owner's hand", re.IGNORECASE), 0.6),
    (re.compile(r"return target.*to their owner's hand", re.IGNORECASE), 0.6),
    # Sacrifice-based removal
    (re.compile(r"sacrifices? a creature", re.IGNORECASE), 0.7),
    (re.compile(r"sacrifices? an? \w+", re.IGNORECASE), 0.6),
    # Permanent -N/-N effects (without "until" already covered above)
    (re.compile(r"gets? -\d+/-\d+", re.IGNORECASE), 0.6),
]

_BOARD_WIPE_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"destroy all", re.IGNORECASE), 0.95),
    (re.compile(r"exile all", re.IGNORECASE), 0.95),
    (re.compile(r"each.*creature.*gets -", re.IGNORECASE), 0.85),
    (re.compile(r"all creatures get -", re.IGNORECASE), 0.85),
    # Each player sacrifices (pseudo-wipe)
    (re.compile(r"each player.*sacrifices", re.IGNORECASE), 0.8),
    # Mass bounce (return all ... to hands)
    (re.compile(r"return all.*to their owners'? hands", re.IGNORECASE), 0.85),
    # Damage-based wipes (deals N damage to each creature)
    (re.compile(r"deals? \d+ damage to each creature", re.IGNORECASE), 0.85),
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
    # Ward keyword
    (re.compile(r"\bward\b", re.IGNORECASE), 0.8),
    # Phase out as protection
    (re.compile(r"\bphase out\b", re.IGNORECASE), 0.8),
    # Regenerate as protection (lower confidence)
    (re.compile(r"\bregenerate\b", re.IGNORECASE), 0.6),
    # Totem armor for enchantment-based protection
    (re.compile(r"\btotem armor\b", re.IGNORECASE), 0.8),
]

_RECURSION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"return.*from.*graveyard", re.IGNORECASE), 0.9),
    (re.compile(r"put.*from.*graveyard", re.IGNORECASE), 0.85),
]

_WIN_CONDITION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    # Direct win / loss
    (re.compile(r"you win the game", re.IGNORECASE), 1.0),
    (re.compile(r"opponent.*loses the game", re.IGNORECASE), 0.95),
    (re.compile(r"each opponent loses", re.IGNORECASE), 0.9),
    # Damage-based
    (re.compile(r"deals? \d+ damage to each opponent", re.IGNORECASE), 0.85),
    (re.compile(r"each opponent loses \d+ life", re.IGNORECASE), 0.85),
    (re.compile(r"deals damage to each opponent equal to", re.IGNORECASE), 0.85),
    # Poison / Infect
    (re.compile(r"infect", re.IGNORECASE), 0.85),
    (re.compile(r"toxic", re.IGNORECASE), 0.8),
    (re.compile(r"poison counter", re.IGNORECASE), 0.8),
    # Extra combat
    (re.compile(r"additional combat phase", re.IGNORECASE), 0.8),
    (re.compile(r"extra combat", re.IGNORECASE), 0.8),
    (re.compile(r"additional combat step", re.IGNORECASE), 0.7),
    # Mill
    (re.compile(r"each opponent.*mills", re.IGNORECASE), 0.8),
    (re.compile(r"target opponent.*mills", re.IGNORECASE), 0.75),
    (re.compile(r"mills? \d+ cards", re.IGNORECASE), 0.7),
    (re.compile(r"put the top \d+ cards.*into.*graveyard", re.IGNORECASE), 0.7),
    # Commander damage enablers
    (re.compile(r"double strike", re.IGNORECASE), 0.7),
    (re.compile(r"commander damage", re.IGNORECASE), 0.6),
    (re.compile(r"double.*power", re.IGNORECASE), 0.6),
    (re.compile(r"deals? combat damage to a player", re.IGNORECASE), 0.6),
    # Large power boosts
    (re.compile(r"gets? \+\d+/\+\d+", re.IGNORECASE), 0.5),
    # Enablers
    (re.compile(r"can't lose the game", re.IGNORECASE), 0.5),
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
