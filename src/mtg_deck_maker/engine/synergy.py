"""Synergy scoring engine for evaluating card-commander compatibility.

Computes synergy scores based on keyword overlap, theme detection,
theme matching, and color efficiency.
"""

from __future__ import annotations

import re

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.utils.colors import is_within_identity

# Theme detection patterns: map theme name -> list of (regex, weight) for oracle text
_THEME_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
    "tokens": [
        (re.compile(r"create.*token", re.IGNORECASE), 1.0),
        (re.compile(r"token.*creature", re.IGNORECASE), 0.8),
        (re.compile(r"populate", re.IGNORECASE), 0.9),
    ],
    "counters": [
        (re.compile(r"\+1/\+1 counter", re.IGNORECASE), 1.0),
        (re.compile(r"proliferate", re.IGNORECASE), 1.0),
        (re.compile(r"-1/-1 counter", re.IGNORECASE), 0.8),
        (re.compile(r"counter on", re.IGNORECASE), 0.7),
    ],
    "graveyard": [
        (re.compile(r"graveyard", re.IGNORECASE), 0.9),
        (re.compile(r"mill", re.IGNORECASE), 0.7),
        (re.compile(r"dredge", re.IGNORECASE), 0.9),
        (re.compile(r"from your graveyard", re.IGNORECASE), 1.0),
        (re.compile(r"into your graveyard", re.IGNORECASE), 0.8),
    ],
    "combat": [
        (re.compile(r"attack", re.IGNORECASE), 0.7),
        (re.compile(r"combat damage", re.IGNORECASE), 0.9),
        (re.compile(r"blocks?", re.IGNORECASE), 0.5),
        (re.compile(r"double strike", re.IGNORECASE), 0.9),
        (re.compile(r"first strike", re.IGNORECASE), 0.6),
    ],
    "spells-matter": [
        (re.compile(r"whenever you cast a(n)? (instant|sorcery|noncreature)", re.IGNORECASE), 1.0),
        (re.compile(r"instant and sorcery", re.IGNORECASE), 0.9),
        (re.compile(r"magecraft", re.IGNORECASE), 1.0),
        (re.compile(r"storm", re.IGNORECASE), 0.8),
        (re.compile(r"prowess", re.IGNORECASE), 0.7),
    ],
    "artifacts-matter": [
        (re.compile(r"whenever.*artifact.*enters", re.IGNORECASE), 1.0),
        (re.compile(r"for each artifact", re.IGNORECASE), 0.9),
        (re.compile(r"artifact you control", re.IGNORECASE), 0.8),
        (re.compile(r"affinity for artifacts", re.IGNORECASE), 1.0),
    ],
    "enchantments-matter": [
        (re.compile(r"whenever.*enchantment.*enters", re.IGNORECASE), 1.0),
        (re.compile(r"for each enchantment", re.IGNORECASE), 0.9),
        (re.compile(r"enchantment you control", re.IGNORECASE), 0.8),
        (re.compile(r"constellation", re.IGNORECASE), 1.0),
    ],
    "tribal": [
        (re.compile(r"other .+ you control get", re.IGNORECASE), 0.8),
        (re.compile(r"each other .+ you control", re.IGNORECASE), 0.8),
        (re.compile(r"lord", re.IGNORECASE), 0.5),
    ],
    "landfall": [
        (re.compile(r"landfall", re.IGNORECASE), 1.0),
        (re.compile(r"whenever a land enters", re.IGNORECASE), 1.0),
        (re.compile(r"land enters the battlefield under your control", re.IGNORECASE), 0.9),
    ],
    "sacrifice": [
        (re.compile(r"sacrifice a", re.IGNORECASE), 0.8),
        (re.compile(r"whenever.*you sacrifice", re.IGNORECASE), 1.0),
        (re.compile(r"sacrifice.*creature", re.IGNORECASE), 0.7),
        (re.compile(r"whenever.*dies", re.IGNORECASE), 0.8),
    ],
    "infect": [
        (re.compile(r"infect", re.IGNORECASE), 1.0),
        (re.compile(r"poison counter", re.IGNORECASE), 0.9),
        (re.compile(r"toxic", re.IGNORECASE), 0.9),
        (re.compile(r"proliferate", re.IGNORECASE), 0.7),
    ],
}

# Shared keyword groups for overlap detection
_KEYWORD_GROUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\+1/\+1 counter", re.IGNORECASE), "+1/+1 counter"),
    (re.compile(r"-1/-1 counter", re.IGNORECASE), "-1/-1 counter"),
    (re.compile(r"token", re.IGNORECASE), "token"),
    (re.compile(r"graveyard", re.IGNORECASE), "graveyard"),
    (re.compile(r"sacrifice", re.IGNORECASE), "sacrifice"),
    (re.compile(r"draw", re.IGNORECASE), "draw"),
    (re.compile(r"counter target", re.IGNORECASE), "counter"),
    (re.compile(r"exile", re.IGNORECASE), "exile"),
    (re.compile(r"lifelink", re.IGNORECASE), "lifelink"),
    (re.compile(r"flying", re.IGNORECASE), "flying"),
    (re.compile(r"trample", re.IGNORECASE), "trample"),
    (re.compile(r"deathtouch", re.IGNORECASE), "deathtouch"),
    (re.compile(r"proliferate", re.IGNORECASE), "proliferate"),
    (re.compile(r"mill", re.IGNORECASE), "mill"),
    (re.compile(r"treasure", re.IGNORECASE), "treasure"),
    (re.compile(r"equip", re.IGNORECASE), "equip"),
    (re.compile(r"aura", re.IGNORECASE), "aura"),
    (re.compile(r"enchant", re.IGNORECASE), "enchant"),
    (re.compile(r"flash", re.IGNORECASE), "flash"),
]


def _extract_keyword_set(card: Card) -> set[str]:
    """Extract a set of keyword group labels from a card's text and keywords.

    Args:
        card: Card to extract keywords from.

    Returns:
        Set of keyword group labels found in the card.
    """
    keywords: set[str] = set()
    text = card.oracle_text or ""

    for pattern, label in _KEYWORD_GROUPS:
        if pattern.search(text):
            keywords.add(label)

    # Also include the card's formal keywords (lowercased)
    for kw in card.keywords:
        keywords.add(kw.lower())

    return keywords


def extract_themes(card: Card) -> list[str]:
    """Detect deck themes from a commander's oracle text and keywords.

    Analyzes the card's oracle text against known theme patterns to
    determine what strategies the commander supports.

    Args:
        card: The commander card to analyze.

    Returns:
        List of theme names detected, sorted by relevance (highest first).
    """
    text = card.oracle_text or ""
    if not text:
        return []

    theme_scores: dict[str, float] = {}

    for theme_name, patterns in _THEME_PATTERNS.items():
        max_score = 0.0
        for pattern, weight in patterns:
            if pattern.search(text):
                max_score = max(max_score, weight)
        if max_score > 0:
            theme_scores[theme_name] = max_score

    # Also check keywords for theme hints
    kw_text = " ".join(card.keywords).lower()
    if "proliferate" in kw_text and "counters" not in theme_scores:
        theme_scores["counters"] = 0.8
    if "landfall" in kw_text and "landfall" not in theme_scores:
        theme_scores["landfall"] = 0.9

    # Sort by score descending
    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
    return [theme for theme, _ in sorted_themes]


def score_theme_match(themes: list[str], candidate: Card) -> float:
    """Score how well a candidate card supports the given themes.

    Args:
        themes: List of theme names from the commander.
        candidate: The candidate card to evaluate.

    Returns:
        Score from 0.0 to 1.0 indicating theme compatibility.
    """
    if not themes:
        return 0.0

    text = candidate.oracle_text or ""
    if not text:
        return 0.0

    total_score = 0.0
    matched_themes = 0

    for theme in themes:
        patterns = _THEME_PATTERNS.get(theme, [])
        theme_max = 0.0
        for pattern, weight in patterns:
            if pattern.search(text):
                theme_max = max(theme_max, weight)
        if theme_max > 0:
            total_score += theme_max
            matched_themes += 1

    if matched_themes == 0:
        return 0.0

    # Normalize: average match score weighted by coverage
    # More themes matched = better, but cap at 1.0
    coverage = matched_themes / len(themes)
    avg_score = total_score / matched_themes
    return min(1.0, avg_score * (0.5 + 0.5 * coverage))


def _compute_keyword_overlap(commander: Card, candidate: Card) -> float:
    """Compute keyword overlap score between commander and candidate.

    Args:
        commander: The commander card.
        candidate: The candidate card.

    Returns:
        Score from 0.0 to 1.0 based on shared keyword groups.
    """
    cmd_keywords = _extract_keyword_set(commander)
    cand_keywords = _extract_keyword_set(candidate)

    if not cmd_keywords or not cand_keywords:
        return 0.0

    overlap = cmd_keywords.intersection(cand_keywords)
    if not overlap:
        return 0.0

    # Score based on proportion of commander's keywords found in candidate
    return min(1.0, len(overlap) / max(len(cmd_keywords), 1))


def _compute_color_synergy(commander: Card, candidate: Card) -> float:
    """Compute color synergy bonus.

    Cards that use the commander's colors efficiently get a bonus.
    Cards must be within the commander's color identity.

    Args:
        commander: The commander card.
        candidate: The candidate card.

    Returns:
        Score from 0.0 to 1.0 for color synergy.
    """
    cmd_identity = set(commander.color_identity)
    cand_identity = set(candidate.color_identity)

    # Must be within identity
    if not is_within_identity(candidate.color_identity, commander.color_identity):
        return 0.0

    if not cmd_identity:
        # Colorless commander: colorless cards get full bonus
        return 1.0 if not cand_identity else 0.0

    if not cand_identity:
        # Colorless candidate: moderate synergy (fits but does not leverage colors)
        return 0.5

    # Bonus for using more of the commander's colors
    overlap = cmd_identity.intersection(cand_identity)
    return len(overlap) / len(cmd_identity)


def _extract_creature_types(card: Card) -> set[str]:
    """Extract creature types from a card's type_line.

    The type_line format uses an em-dash (\u2014) to separate supertypes/types
    from subtypes, e.g. "Legendary Creature \u2014 Zombie Wizard".
    Everything after the em-dash is split into individual creature types.

    Args:
        card: Card to extract creature types from.

    Returns:
        Set of creature type strings. Empty if the card has no subtypes.
    """
    type_line = card.type_line or ""
    if "\u2014" not in type_line:
        return set()

    _, subtypes_part = type_line.split("\u2014", 1)
    types = {t.strip() for t in subtypes_part.strip().split() if t.strip()}
    return types


def _compute_tribal_synergy(commander: Card, candidate: Card) -> float:
    """Compute tribal synergy based on shared creature types.

    Args:
        commander: The commander card.
        candidate: The candidate card.

    Returns:
        Score from 0.0 to 1.0:
        - 1.0 if the candidate shares the commander's primary (first) creature type
        - 0.5 if the candidate shares a secondary creature type
        - 0.0 if no shared types, or either card is not a creature
    """
    cmd_types = _extract_creature_types(commander)
    if not cmd_types:
        return 0.0

    cand_types = _extract_creature_types(candidate)
    if not cand_types:
        return 0.0

    shared = cmd_types.intersection(cand_types)
    if not shared:
        return 0.0

    # Determine primary type: first type after the em-dash in commander's type_line
    type_line = commander.type_line or ""
    _, subtypes_part = type_line.split("\u2014", 1)
    ordered_types = [t.strip() for t in subtypes_part.strip().split() if t.strip()]

    if ordered_types and ordered_types[0] in shared:
        return 1.0

    return 0.5


def compute_synergy(commander: Card, candidate: Card) -> float:
    """Compute overall synergy score between a commander and a candidate card.

    Combines keyword overlap, theme matching, and color synergy into
    a single score on a 0.0 to 1.0 scale.

    Args:
        commander: The commander card.
        candidate: The candidate card.

    Returns:
        Float score from 0.0 to 1.0 representing overall synergy.
    """
    # Weight factors for each component
    keyword_weight = 0.25
    theme_weight = 0.35
    color_weight = 0.20
    tribal_weight = 0.20

    keyword_score = _compute_keyword_overlap(commander, candidate)

    themes = extract_themes(commander)
    theme_score = score_theme_match(themes, candidate)

    color_score = _compute_color_synergy(commander, candidate)

    tribal_score = _compute_tribal_synergy(commander, candidate)

    raw_score = (
        keyword_score * keyword_weight
        + theme_score * theme_weight
        + color_score * color_weight
        + tribal_score * tribal_weight
    )

    return min(1.0, max(0.0, raw_score))


def compute_combo_synergy(
    card_name: str,
    deck_card_names: set[str],
    combo_partners: dict[str, list[str]],
) -> float:
    """Compute combo synergy bonus for a candidate card.

    Checks whether the candidate card has known combo partners and whether
    any of those partners are already in the deck.

    Args:
        card_name: Name of the candidate card.
        deck_card_names: Set of card names already selected for the deck.
        combo_partners: Mapping of card name to list of known combo
            partner card names.

    Returns:
        Float score:
        - 0.0 if the card has no known combo partners.
        - 0.3 to 0.5 if the card has combo partners but none are in the deck.
        - 0.8 to 1.0 if at least one combo partner is already in the deck.
    """
    partners = combo_partners.get(card_name)
    if not partners:
        return 0.0

    partners_in_deck = [p for p in partners if p in deck_card_names]

    if partners_in_deck:
        # At least one partner is in the deck -- high bonus
        # Scale slightly by how many partners are present
        ratio = min(len(partners_in_deck) / len(partners), 1.0)
        return 0.8 + 0.2 * ratio

    # Partners exist but are not yet in the deck -- moderate bonus
    return 0.4


# Enabler/payoff pattern pairs for pairwise synergy detection.
# Each tuple is (enabler_pattern, payoff_pattern); if card A matches the
# enabler and card B matches the payoff (or vice-versa), the pair scores.
_ENABLER_PAYOFF_PAIRS: list[tuple[re.Pattern[str], re.Pattern[str]]] = [
    (re.compile(r"sacrifice a", re.I), re.compile(r"whenever.*dies", re.I)),
    (
        re.compile(r"create.*token", re.I),
        re.compile(r"for each.*creature|whenever.*creature.*enters", re.I),
    ),
    (
        re.compile(r"draw.*card|cards", re.I),
        re.compile(r"whenever you draw|no maximum hand size", re.I),
    ),
    (
        re.compile(r"graveyard", re.I),
        re.compile(r"from.*graveyard|whenever.*put into.*graveyard", re.I),
    ),
    (
        re.compile(r"\+1/\+1 counter", re.I),
        re.compile(r"proliferate|for each.*counter", re.I),
    ),
]


def _compute_enabler_payoff(card_a: Card, card_b: Card) -> float:
    """Score enabler/payoff relationship between two cards.

    Checks whether one card provides an enabler effect and the other
    provides a corresponding payoff effect. The relationship is checked
    in both directions (A enables B, or B enables A).

    Args:
        card_a: First card.
        card_b: Second card.

    Returns:
        1.0 if at least one enabler/payoff pair matches, 0.0 otherwise.
    """
    text_a = card_a.oracle_text or ""
    text_b = card_b.oracle_text or ""
    if not text_a or not text_b:
        return 0.0

    for enabler_pat, payoff_pat in _ENABLER_PAYOFF_PAIRS:
        # A is enabler, B is payoff
        if enabler_pat.search(text_a) and payoff_pat.search(text_b):
            return 1.0
        # B is enabler, A is payoff
        if enabler_pat.search(text_b) and payoff_pat.search(text_a):
            return 1.0

    return 0.0


def _compute_pairwise_theme_co_support(card_a: Card, card_b: Card) -> float:
    """Score how many themes both cards co-support.

    Checks each theme in ``_THEME_PATTERNS`` and counts how many themes
    both cards match. Returns a normalized score (0.0-1.0).

    Args:
        card_a: First card.
        card_b: Second card.

    Returns:
        Proportion of themes both cards match out of total themes.
    """
    text_a = card_a.oracle_text or ""
    text_b = card_b.oracle_text or ""
    if not text_a or not text_b:
        return 0.0

    shared_themes = 0
    total_themes = len(_THEME_PATTERNS)

    for _theme_name, patterns in _THEME_PATTERNS.items():
        a_matches = any(pat.search(text_a) for pat, _w in patterns)
        b_matches = any(pat.search(text_b) for pat, _w in patterns)
        if a_matches and b_matches:
            shared_themes += 1

    if shared_themes == 0:
        return 0.0

    # Normalize: 1 shared theme out of ~11 is still meaningful, so scale up
    return min(1.0, shared_themes / max(total_themes * 0.3, 1.0))


def _compute_pairwise_tribal(card_a: Card, card_b: Card) -> float:
    """Score tribal overlap between two cards.

    Args:
        card_a: First card.
        card_b: Second card.

    Returns:
        1.0 if any creature types are shared, 0.0 otherwise.
    """
    types_a = _extract_creature_types(card_a)
    types_b = _extract_creature_types(card_b)
    if not types_a or not types_b:
        return 0.0
    return 1.0 if types_a.intersection(types_b) else 0.0


def compute_pairwise_synergy(card_a: Card, card_b: Card) -> float:
    """Compute pairwise synergy score between two cards.

    Evaluates how well two cards work together independent of any
    commander, based on keyword overlap, shared theme support,
    tribal overlap, and enabler/payoff relationships.

    Args:
        card_a: First card.
        card_b: Second card.

    Returns:
        Float score from 0.0 to 1.0 representing card-to-card synergy.
    """
    keyword_weight = 0.30
    theme_weight = 0.40
    tribal_weight = 0.15
    enabler_weight = 0.15

    # Keyword overlap
    kw_a = _extract_keyword_set(card_a)
    kw_b = _extract_keyword_set(card_b)
    if kw_a and kw_b:
        overlap = kw_a.intersection(kw_b)
        keyword_score = min(1.0, len(overlap) / max(len(kw_a.union(kw_b)) * 0.3, 1.0))
    else:
        keyword_score = 0.0

    # Theme co-support
    theme_score = _compute_pairwise_theme_co_support(card_a, card_b)

    # Tribal match
    tribal_score = _compute_pairwise_tribal(card_a, card_b)

    # Enabler/payoff
    enabler_score = _compute_enabler_payoff(card_a, card_b)

    raw = (
        keyword_score * keyword_weight
        + theme_score * theme_weight
        + tribal_score * tribal_weight
        + enabler_score * enabler_weight
    )
    return min(1.0, max(0.0, raw))


def compute_package_score(cards: list[Card]) -> float:
    """Compute the average pairwise synergy for a small group of cards.

    Args:
        cards: List of 0-5 cards to evaluate as a package.

    Returns:
        Mean of all pairwise synergy scores, or 0.0 if fewer than 2 cards.
    """
    if len(cards) < 2:
        return 0.0

    total = 0.0
    pair_count = 0
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            total += compute_pairwise_synergy(cards[i], cards[j])
            pair_count += 1

    return total / pair_count


def find_synergy_packages(
    candidates: list[Card],
    top_n: int = 50,
    min_synergy: float = 0.3,
) -> list[tuple[str, str, float]]:
    """Find pairs of cards with high pairwise synergy.

    Evaluates all pairs among the first ``top_n`` candidates and returns
    those whose pairwise synergy meets the minimum threshold.

    Args:
        candidates: List of candidate cards (order matters for top_n cutoff).
        top_n: Number of candidates to consider from the front of the list.
        min_synergy: Minimum pairwise synergy score to include in results.

    Returns:
        List of (card_a_name, card_b_name, score) tuples sorted by score
        descending.
    """
    subset = candidates[:top_n]
    if len(subset) < 2:
        return []

    results: list[tuple[str, str, float]] = []
    for i in range(len(subset)):
        for j in range(i + 1, len(subset)):
            score = compute_pairwise_synergy(subset[i], subset[j])
            if score >= min_synergy:
                results.append((subset[i].name, subset[j].name, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results
