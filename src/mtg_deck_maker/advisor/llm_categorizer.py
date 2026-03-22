"""LLM-assisted card categorization for cards missed by regex patterns.

Batches uncategorized cards through an LLM provider for JSON categorization,
complementing the regex-based engine/categories.py.
"""

from __future__ import annotations

import json
import logging
import re

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.engine.categories import Category
from mtg_deck_maker.models.card import Card

logger = logging.getLogger(__name__)

# Functional categories that indicate a card has a meaningful role.
_FUNCTIONAL_CATEGORIES: frozenset[str] = frozenset({
    Category.RAMP.value,
    Category.CARD_DRAW.value,
    Category.REMOVAL.value,
    Category.BOARD_WIPE.value,
    Category.COUNTERSPELL.value,
    Category.PROTECTION.value,
    Category.RECURSION.value,
    Category.WIN_CONDITION.value,
    Category.TUTOR.value,
})

# Valid category names the LLM may return.
_VALID_LLM_CATEGORIES: frozenset[str] = _FUNCTIONAL_CATEGORIES

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")

_SYSTEM_PROMPT = """\
You are a Magic: The Gathering card categorization engine. Given a list of cards \
with their oracle text, classify each card into one or more functional categories.

Valid categories and their meanings:
- ramp: Produces mana or fetches lands (e.g. mana dorks, mana rocks, land ramp)
- card_draw: Draws cards or provides card selection/advantage
- removal: Destroys, exiles, or otherwise removes a single target permanent or creature
- board_wipe: Destroys or exiles all/multiple permanents at once
- counterspell: Counters spells or activated/triggered abilities
- protection: Grants hexproof, indestructible, shroud, ward, or other protection
- recursion: Returns cards from the graveyard to hand or battlefield
- win_condition: Directly wins the game, deals large damage, or enables a winning strategy
- tutor: Searches the library for specific non-land cards

Respond ONLY with a JSON object mapping each card name to a list of \
[category, confidence] pairs. Confidence is a float from 0.0 to 1.0. \
Only include categories that genuinely apply. If a card fits no category, \
return an empty list for it.

Example response:
{"Sol Ring": [["ramp", 0.95]], "Swords to Plowshares": [["removal", 0.95]]}
"""


def _is_uncategorized(categories: list[tuple[str, float]]) -> bool:
    """Check if a card has no functional category from regex.

    A card is "uncategorized" if its only categories are type-based
    (creature, artifact, enchantment, land) or utility.

    Args:
        categories: Existing regex-based categories for the card.

    Returns:
        True if the card has no functional category.
    """
    return not any(cat in _FUNCTIONAL_CATEGORIES for cat, _ in categories)


def _parse_llm_categories(raw: str) -> dict[str, list[tuple[str, float]]]:
    """Parse LLM JSON response into validated category mappings.

    Handles fenced code blocks, validates category names against the
    Category enum, and clamps confidence values to [0.0, 1.0].

    Args:
        raw: Raw text response from the LLM.

    Returns:
        Dict mapping card name to list of (category, confidence) tuples.
        Returns empty dict on any parse failure.
    """
    if not raw:
        return {}

    # Strip fenced code blocks if present.
    match = _FENCED_JSON_RE.search(raw)
    text = match.group(1).strip() if match else raw.strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM categorization response as JSON")
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[str, list[tuple[str, float]]] = {}
    for card_name, entries in data.items():
        if not isinstance(entries, list):
            continue
        validated: list[tuple[str, float]] = []
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            cat_name, confidence = entry[0], entry[1]
            if not isinstance(cat_name, str) or cat_name not in _VALID_LLM_CATEGORIES:
                continue
            if not isinstance(confidence, (int, float)):
                continue
            clamped = max(0.0, min(1.0, float(confidence)))
            validated.append((cat_name, clamped))
        result[str(card_name)] = validated

    return result


def _build_user_prompt(cards: list[Card]) -> str:
    """Build the user prompt listing cards for categorization.

    Args:
        cards: Cards to include in the prompt.

    Returns:
        Formatted user message with card names and oracle text.
    """
    lines: list[str] = ["Categorize these cards:\n"]
    for card in cards:
        oracle = card.oracle_text or "(no oracle text)"
        type_line = card.type_line or "(no type)"
        lines.append(f"- {card.name} [{type_line}]: {oracle}")
    return "\n".join(lines)


class LLMCategorizer:
    """Categorizes MTG cards using an LLM provider.

    Sends batches of cards to the LLM for JSON categorization, with
    results validated against the Category enum.
    """

    def __init__(
        self, provider: LLMProvider | None = None, batch_size: int = 25
    ) -> None:
        self._provider = provider
        self._batch_size = batch_size

    def categorize_batch(
        self, cards: list[Card]
    ) -> dict[str, list[tuple[str, float]]]:
        """Categorize a batch of cards using the LLM.

        Args:
            cards: Cards to categorize.

        Returns:
            Dict mapping card name to list of (category, confidence) tuples.
            Categories use Category enum values from engine/categories.py.

        Raises:
            RuntimeError: If no LLM provider is available.
        """
        if not cards:
            return {}

        if self._provider is None:
            raise RuntimeError("No LLM provider available for categorization")

        merged: dict[str, list[tuple[str, float]]] = {}

        for i in range(0, len(cards), self._batch_size):
            chunk = cards[i : i + self._batch_size]
            user_prompt = _build_user_prompt(chunk)
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            try:
                raw = self._provider.chat(
                    messages, max_tokens=2048, temperature=0.2
                )
            except Exception:
                logger.exception("LLM categorization call failed for batch")
                continue

            parsed = _parse_llm_categories(raw)
            merged.update(parsed)

        return merged

    def categorize_uncategorized(
        self,
        cards: list[Card],
        existing: dict[int, list[tuple[str, float]]],
    ) -> dict[str, list[tuple[str, float]]]:
        """Categorize only cards that have no functional category from regex.

        A card is "uncategorized" if its only categories from regex are
        type-based (creature, artifact, enchantment, land) or utility.

        Args:
            cards: All cards to check.
            existing: Existing regex-based categorization keyed by card ID.

        Returns:
            Dict mapping card name to LLM-assigned categories.
        """
        uncategorized: list[Card] = []
        for card in cards:
            key = card.id
            if key is None or key not in existing:
                uncategorized.append(card)
                continue
            if _is_uncategorized(existing[key]):
                uncategorized.append(card)

        if not uncategorized:
            return {}

        return self.categorize_batch(uncategorized)
