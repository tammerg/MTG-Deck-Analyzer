"""LLM-assisted pairwise synergy scoring for card pairs.

Uses an LLM provider to evaluate synergy between pairs of cards in the
context of a specific commander, producing a synergy matrix that supplements
the regex-based synergy engine.
"""

from __future__ import annotations

import json
import logging
from itertools import combinations

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.advisor.parsing import extract_json_from_response
from mtg_deck_maker.models.card import Card

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a Magic: The Gathering synergy evaluation engine. Given a commander \
and pairs of cards with their oracle text, rate how well each pair of cards \
works together in a deck led by this commander.

Score each pair from 0.0 (no synergy) to 1.0 (extremely high synergy). \
Consider mechanical interactions, shared themes, enabler/payoff relationships, \
and how well the pair supports the commander's strategy.

Respond ONLY with a JSON object mapping "Card A | Card B" to a float score. \
Example: {"Sol Ring | Arcane Signet": 0.3, "Ashnod's Altar | Gravecrawler": 0.95}
"""


def _canonical_key(name_a: str, name_b: str) -> tuple[str, str]:
    """Return a canonical (sorted) key for a card pair.

    Ensures (A, B) and (B, A) map to the same key by sorting alphabetically.
    """
    if name_a <= name_b:
        return (name_a, name_b)
    return (name_b, name_a)


def _build_pair_prompt(
    commander_name: str,
    commander_text: str,
    pairs: list[tuple[Card, Card]],
) -> str:
    """Build a user prompt listing card pairs for synergy evaluation."""
    lines = [
        f"Commander: {commander_name}",
        f"Commander text: {commander_text}",
        "",
        "Rate synergy for these card pairs:",
        "",
    ]
    for card_a, card_b in pairs:
        text_a = card_a.oracle_text or "(no text)"
        text_b = card_b.oracle_text or "(no text)"
        lines.append(f"- {card_a.name} [{text_a}] | {card_b.name} [{text_b}]")
    return "\n".join(lines)


def _parse_synergy_response(raw: str) -> dict[tuple[str, str], float]:
    """Parse LLM JSON response into synergy scores with canonical keys.

    Handles fenced code blocks, validates scores are floats, clamps to [0.0, 1.0],
    and uses canonical key ordering.

    Returns empty dict on parse failure.
    """
    if not raw:
        return {}

    text = extract_json_from_response(raw)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM synergy response as JSON")
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[tuple[str, str], float] = {}
    for pair_key, score in data.items():
        if not isinstance(pair_key, str) or "|" not in pair_key:
            continue
        parts = pair_key.split("|", 1)
        if len(parts) != 2:
            continue
        name_a = parts[0].strip()
        name_b = parts[1].strip()
        if not name_a or not name_b:
            continue
        if not isinstance(score, (int, float)):
            continue
        clamped = max(0.0, min(1.0, float(score)))
        key = _canonical_key(name_a, name_b)
        result[key] = clamped

    return result


def generate_synergy_matrix(
    commander: Card,
    candidates: list[Card],
    provider: LLMProvider,
    top_n: int = 100,
    batch_size: int = 50,
) -> dict[tuple[str, str], float]:
    """Generate pairwise synergy scores for top candidates using an LLM.

    Takes the top N candidates by position in the list (assumed pre-sorted
    by base score), generates all unique pairs, batches them through the LLM,
    and returns a synergy matrix.

    Args:
        commander: The commander Card.
        candidates: List of candidate Cards (pre-sorted by score).
        provider: LLM provider for chat completions.
        top_n: Number of top candidates to consider. Default 100.
        batch_size: Number of pairs per LLM call. Default 50.

    Returns:
        Dict mapping (card_a_name, card_b_name) -> synergy score.
        Keys are canonically ordered (alphabetical). Returns empty
        dict on complete failure (graceful degradation).
    """
    subset = candidates[:top_n]
    if len(subset) < 2:
        return {}

    # Generate all unique pairs
    all_pairs = list(combinations(subset, 2))

    commander_text = commander.oracle_text or "(no text)"
    matrix: dict[tuple[str, str], float] = {}

    # Process in batches
    for i in range(0, len(all_pairs), batch_size):
        batch = all_pairs[i : i + batch_size]
        user_prompt = _build_pair_prompt(commander.name, commander_text, batch)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = provider.chat(messages, max_tokens=4096, temperature=0.2)
        except Exception:
            logger.exception(
                "LLM synergy call failed for batch %d", i // batch_size
            )
            continue

        parsed = _parse_synergy_response(raw)
        matrix.update(parsed)

    return matrix
