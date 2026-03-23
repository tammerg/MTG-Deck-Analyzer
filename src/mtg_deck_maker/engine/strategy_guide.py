"""Strategy guide engine for post-build deck analysis.

Pure algorithmic analysis — no LLM dependency. Provides opening hand
simulation, win condition analysis, game phase planning, and synergy
identification.
"""

from __future__ import annotations

import random
import re

from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.engine.synergy import (
    compute_pairwise_synergy,
    extract_themes,
)
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.combo import Combo
from mtg_deck_maker.models.strategy_guide import (
    GamePhase,
    HandSample,
    HandSimulationResult,
    KeySynergy,
    StrategyGuide,
    WinPath,
)

# ---------------------------------------------------------------------------
# Win-condition sub-type regex patterns
# ---------------------------------------------------------------------------
_WIN_SUBTYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Direct Win", re.compile(r"you win the game", re.I)),
    ("Drain/Life Loss", re.compile(r"(each opponent loses|deals? \d+ damage to each opponent|opponent.*loses the game)", re.I)),
    ("Mill", re.compile(r"(mills?|put the top \d+ cards.*into.*graveyard)", re.I)),
    ("Infect/Poison", re.compile(r"(infect|toxic|poison counter)", re.I)),
    ("Extra Combat", re.compile(r"(additional combat|extra combat)", re.I)),
    ("Combat/Commander Damage", re.compile(r"(double strike|commander damage|double.*power|combat damage to a player)", re.I)),
]


def _card_categories(card: Card) -> set[str]:
    """Return the set of category names for a card."""
    return {cat for cat, _conf in categorize_card(card)}


def _is_land(card: Card) -> bool:
    return "Land" in (card.type_line or "")


def _is_ramp(card: Card) -> bool:
    return Category.RAMP.value in _card_categories(card)


def _is_win_condition(card: Card) -> bool:
    return Category.WIN_CONDITION.value in _card_categories(card)


def _is_tutor(card: Card) -> bool:
    return Category.TUTOR.value in _card_categories(card)


# ---------------------------------------------------------------------------
# Opening hand simulation
# ---------------------------------------------------------------------------


def _score_hand(
    hand_cards: list[str],
    card_lookup: dict[str, Card],
) -> tuple[int, str]:
    """Score an opening hand on a 0-10 scale.

    Returns (score, reason_string).
    """
    lands = [c for c in hand_cards if c in card_lookup and _is_land(card_lookup[c])]
    ramps = [c for c in hand_cards if c in card_lookup and _is_ramp(card_lookup[c]) and not _is_land(card_lookup[c])]
    non_lands = [c for c in hand_cards if c in card_lookup and not _is_land(card_lookup[c])]
    win_enablers = [
        c for c in hand_cards
        if c in card_lookup and (_is_win_condition(card_lookup[c]) or _is_tutor(card_lookup[c]))
    ]

    land_count = len(lands)
    score = 0
    reasons: list[str] = []

    # Land scoring
    if land_count <= 1:
        score += 2
        reasons.append(f"only {land_count} land(s)")
    elif land_count == 2:
        score += 5
        reasons.append("2 lands (tight)")
    elif land_count in (3, 4):
        score += 8
        reasons.append(f"{land_count} lands (ideal)")
    elif land_count == 5:
        score += 5
        reasons.append("5 lands (land-heavy)")
    else:
        score += 2
        reasons.append(f"{land_count} lands (flood)")

    # Ramp bonus
    if ramps:
        score += 1
        reasons.append(f"{len(ramps)} ramp card(s)")

    # Curve penalty
    if non_lands:
        avg_cmc = sum(card_lookup[c].cmc for c in non_lands) / len(non_lands)
        if avg_cmc > 4.0:
            score -= 1
            reasons.append(f"high avg CMC ({avg_cmc:.1f})")
    else:
        avg_cmc = 0.0

    # Win enabler bonus
    if win_enablers:
        score += 1
        reasons.append("has win enabler/tutor")

    score = max(0, min(10, score))
    return score, "; ".join(reasons)


def simulate_opening_hands(
    deck_cards: list[str],
    card_lookup: dict[str, Card],
    num_simulations: int = 1000,
    seed: int = 42,
) -> HandSimulationResult:
    """Run Monte Carlo opening hand simulation.

    Args:
        deck_cards: List of card names in the deck (excluding commander).
        card_lookup: Mapping of card name to Card object.
        num_simulations: Number of simulations to run.
        seed: Random seed for reproducibility.

    Returns:
        HandSimulationResult with statistics and sample hands.
    """
    if len(deck_cards) < 7:
        return HandSimulationResult(
            total_simulations=0,
            keep_rate=0.0,
            avg_land_count=0.0,
            avg_ramp_count=0.0,
            avg_cmc_in_hand=0.0,
            mulligan_advice="Deck has fewer than 7 cards; cannot simulate.",
        )

    rng = random.Random(seed)
    scored_hands: list[tuple[int, HandSample]] = []
    total_lands = 0.0
    total_ramps = 0.0
    total_cmc = 0.0
    keeps = 0

    for _ in range(num_simulations):
        hand = rng.sample(deck_cards, 7)
        score, reason = _score_hand(hand, card_lookup)

        lands = [c for c in hand if c in card_lookup and _is_land(card_lookup[c])]
        ramps = [c for c in hand if c in card_lookup and _is_ramp(card_lookup[c]) and not _is_land(card_lookup[c])]
        non_lands = [c for c in hand if c in card_lookup and not _is_land(card_lookup[c])]
        win_enablers = any(
            c in card_lookup and (_is_win_condition(card_lookup[c]) or _is_tutor(card_lookup[c]))
            for c in hand
        )

        avg_cmc = (
            sum(card_lookup[c].cmc for c in non_lands) / len(non_lands)
            if non_lands else 0.0
        )

        keep = score >= 5
        if keep:
            keeps += 1

        total_lands += len(lands)
        total_ramps += len(ramps)
        total_cmc += avg_cmc

        sample = HandSample(
            cards=sorted(hand),
            land_count=len(lands),
            ramp_count=len(ramps),
            avg_cmc=round(avg_cmc, 2),
            has_win_enabler=win_enablers,
            keep_recommendation=keep,
            reason=reason,
        )
        scored_hands.append((score, sample))

    keep_rate = keeps / num_simulations
    avg_land = total_lands / num_simulations
    avg_ramp = total_ramps / num_simulations
    avg_cmc_overall = total_cmc / num_simulations

    # Pick 5 representative sample hands
    scored_hands.sort(key=lambda x: x[0])
    samples: list[HandSample] = []

    # Worst
    samples.append(scored_hands[0][1])
    # Best
    samples.append(scored_hands[-1][1])
    # Median
    mid = len(scored_hands) // 2
    samples.append(scored_hands[mid][1])
    # Borderline keep (score == 5)
    borderline_keep = next((s for sc, s in scored_hands if sc == 5), None)
    if borderline_keep:
        samples.append(borderline_keep)
    # Borderline mulligan (score == 4)
    borderline_mull = next((s for sc, s in scored_hands if sc == 4), None)
    if borderline_mull:
        samples.append(borderline_mull)

    # Mulligan advice
    if keep_rate >= 0.75:
        advice = "Excellent mana base. Most opening hands are keepable."
    elif keep_rate >= 0.6:
        advice = "Solid mana base. Occasionally mulligan land-light hands."
    elif keep_rate >= 0.45:
        advice = "Consider adding more lands or low-cost ramp to improve consistency."
    else:
        advice = "Mana base needs work. Frequent mulligans expected. Add more lands and ramp."

    return HandSimulationResult(
        total_simulations=num_simulations,
        keep_rate=round(keep_rate, 3),
        avg_land_count=round(avg_land, 2),
        avg_ramp_count=round(avg_ramp, 2),
        avg_cmc_in_hand=round(avg_cmc_overall, 2),
        sample_hands=samples,
        mulligan_advice=advice,
    )


# ---------------------------------------------------------------------------
# Win condition analysis
# ---------------------------------------------------------------------------


def _classify_win_subtype(card: Card) -> str:
    """Classify a win-condition card into a sub-type."""
    text = card.oracle_text or ""
    for subtype_name, pattern in _WIN_SUBTYPE_PATTERNS:
        if pattern.search(text):
            return subtype_name
    return "General Win Condition"


def analyze_win_conditions(
    deck_cards: list[str],
    card_lookup: dict[str, Card],
    combos: list[Combo],
    archetype: str,
    commander_name: str,
) -> list[WinPath]:
    """Identify win condition paths available in the deck.

    Args:
        deck_cards: Card names in the deck.
        card_lookup: Card name to Card mapping.
        combos: Known combos from the database.
        archetype: Detected deck archetype.
        commander_name: Name of the commander.

    Returns:
        Sorted list of WinPath objects.
    """
    deck_set = set(deck_cards)
    win_paths: list[WinPath] = []

    # 1. Complete combos (all cards present in deck)
    for combo in combos:
        if all(cn in deck_set for cn in combo.card_names):
            win_paths.append(WinPath(
                name=f"Combo: {combo.result[:60]}",
                cards=combo.card_names,
                description=combo.description or combo.result,
                combo_id=combo.combo_id,
            ))

    # 2. Win-condition cards grouped by sub-type
    win_cards_by_type: dict[str, list[str]] = {}
    for name in deck_cards:
        card = card_lookup.get(name)
        if card and _is_win_condition(card):
            subtype = _classify_win_subtype(card)
            win_cards_by_type.setdefault(subtype, []).append(name)

    for subtype, cards in win_cards_by_type.items():
        win_paths.append(WinPath(
            name=subtype,
            cards=sorted(cards),
            description=f"{subtype} via {', '.join(cards[:3])}{'...' if len(cards) > 3 else ''}",
        ))

    # Sort: complete combos first, then by card count descending
    win_paths.sort(key=lambda wp: (0 if wp.combo_id else 1, -len(wp.cards)))
    return win_paths


# ---------------------------------------------------------------------------
# Game phase planning
# ---------------------------------------------------------------------------

_ARCHETYPE_EARLY_PRIORITIES: dict[str, list[str]] = {
    "aggro": ["Deploy cheap creatures", "Establish early board presence", "Play ramp"],
    "combo": ["Find combo pieces with tutors/draw", "Ramp into combo turns", "Set up card selection"],
    "control": ["Hold up interaction", "Deploy low-cost card draw", "Establish mana base"],
    "spellslinger": ["Cantrip and filter", "Build mana base", "Deploy cost reducers"],
    "tribal": ["Play tribal lord setup", "Deploy cheap tribe members", "Ramp"],
    "midrange": ["Ramp", "Deploy early card draw", "Fix mana"],
}

_ARCHETYPE_MID_PRIORITIES: dict[str, list[str]] = {
    "aggro": ["Deploy commander and key threats", "Push damage", "Remove blockers"],
    "combo": ["Assemble combo pieces", "Protect key permanents", "Tutor for missing pieces"],
    "control": ["Deploy removal and board wipes", "Counter key threats", "Establish card advantage"],
    "spellslinger": ["Chain spells for value", "Deploy payoff permanents", "Control the board"],
    "tribal": ["Deploy tribal lords and anthem effects", "Build critical mass", "Remove threats"],
    "midrange": ["Deploy key threats", "Establish board presence", "Use targeted removal"],
}

_ARCHETYPE_LATE_PRIORITIES: dict[str, list[str]] = {
    "aggro": ["Close out the game", "Deploy extra combat/pump effects", "Rebuild after wipes"],
    "combo": ["Execute combo", "Protect the win", "Find backup win conditions"],
    "control": ["Deploy finisher", "Lock out opponents", "Protect your board"],
    "spellslinger": ["Storm off or burn out opponents", "Recur key spells", "Protect the win"],
    "tribal": ["Overwhelm with tribal synergy", "Recover from board wipes", "Alpha strike"],
    "midrange": ["Execute win conditions", "Grind out remaining opponents", "Protect board state"],
}


def plan_game_phases(
    deck_cards: list[str],
    card_lookup: dict[str, Card],
    archetype: str,
    themes: list[str],
    avg_cmc: float,
) -> list[GamePhase]:
    """Plan the game into three phases with archetype-aware priorities.

    Args:
        deck_cards: Card names in the deck.
        card_lookup: Card name to Card mapping.
        archetype: Detected archetype.
        themes: Detected themes.
        avg_cmc: Average CMC of the deck.

    Returns:
        List of 3 GamePhase objects (Early, Mid, Late).
    """
    arch_key = archetype.lower()

    # Categorize cards by CMC bucket
    early_cards: list[str] = []
    mid_cards: list[str] = []
    late_cards: list[str] = []

    for name in deck_cards:
        card = card_lookup.get(name)
        if not card or _is_land(card):
            continue
        cats = _card_categories(card)
        if card.cmc <= 2:
            if cats & {Category.RAMP.value, Category.CARD_DRAW.value, Category.TUTOR.value}:
                early_cards.append(name)
        if 3 <= card.cmc <= 5:
            if cats & {Category.REMOVAL.value, Category.WIN_CONDITION.value, Category.CARD_DRAW.value,
                       Category.BOARD_WIPE.value, Category.TUTOR.value, Category.PROTECTION.value}:
                mid_cards.append(name)
        if card.cmc >= 6 or cats & {Category.WIN_CONDITION.value, Category.PROTECTION.value, Category.COUNTERSPELL.value}:
            late_cards.append(name)

    early_priorities = _ARCHETYPE_EARLY_PRIORITIES.get(arch_key, _ARCHETYPE_EARLY_PRIORITIES["midrange"])
    mid_priorities = _ARCHETYPE_MID_PRIORITIES.get(arch_key, _ARCHETYPE_MID_PRIORITIES["midrange"])
    late_priorities = _ARCHETYPE_LATE_PRIORITIES.get(arch_key, _ARCHETYPE_LATE_PRIORITIES["midrange"])

    return [
        GamePhase(
            phase_name="Early Game",
            turn_range="Turns 1-3",
            priorities=early_priorities,
            key_cards=sorted(set(early_cards))[:8],
            description=f"Focus on establishing your mana base and early setup. Avg deck CMC is {avg_cmc:.1f}.",
        ),
        GamePhase(
            phase_name="Mid Game",
            turn_range="Turns 4-7",
            priorities=mid_priorities,
            key_cards=sorted(set(mid_cards))[:8],
            description="Deploy key pieces and establish your game plan. React to opponents as needed.",
        ),
        GamePhase(
            phase_name="Late Game",
            turn_range="Turns 8+",
            priorities=late_priorities,
            key_cards=sorted(set(late_cards))[:8],
            description="Execute your win conditions and close out the game.",
        ),
    ]


# ---------------------------------------------------------------------------
# Key synergy identification
# ---------------------------------------------------------------------------


def identify_key_synergies(
    deck_cards: list[str],
    card_lookup: dict[str, Card],
    max_results: int = 10,
) -> list[KeySynergy]:
    """Find the most synergistic card pairs in the deck.

    Args:
        deck_cards: Card names in the deck.
        card_lookup: Card name to Card mapping.
        max_results: Maximum pairs to return.

    Returns:
        List of KeySynergy objects sorted by synergy score descending.
    """
    non_land_names = [
        n for n in deck_cards
        if n in card_lookup and not _is_land(card_lookup[n])
    ]

    if len(non_land_names) < 2:
        return []

    # Limit to top 50 cards to keep O(n^2) manageable
    subset = non_land_names[:50]
    pairs: list[tuple[float, str, str]] = []

    for i in range(len(subset)):
        card_a = card_lookup[subset[i]]
        for j in range(i + 1, len(subset)):
            card_b = card_lookup[subset[j]]
            score = compute_pairwise_synergy(card_a, card_b)
            if score > 0.1:
                pairs.append((score, subset[i], subset[j]))

    pairs.sort(key=lambda x: x[0], reverse=True)

    results: list[KeySynergy] = []
    for score, name_a, name_b in pairs[:max_results]:
        reason = _build_synergy_reason(card_lookup[name_a], card_lookup[name_b])
        results.append(KeySynergy(card_a=name_a, card_b=name_b, reason=reason))

    return results


def _build_synergy_reason(card_a: Card, card_b: Card) -> str:
    """Build a human-readable reason for why two cards synergize."""
    reasons: list[str] = []

    # Check shared themes
    from mtg_deck_maker.engine.synergy import _THEME_PATTERNS

    text_a = card_a.oracle_text or ""
    text_b = card_b.oracle_text or ""

    for theme_name, patterns in _THEME_PATTERNS.items():
        a_match = any(pat.search(text_a) for pat, _w in patterns)
        b_match = any(pat.search(text_b) for pat, _w in patterns)
        if a_match and b_match:
            reasons.append(f"shared {theme_name} theme")

    # Check shared keywords
    from mtg_deck_maker.engine.synergy import _extract_keyword_set

    kw_a = _extract_keyword_set(card_a)
    kw_b = _extract_keyword_set(card_b)
    shared_kw = kw_a & kw_b
    if shared_kw:
        reasons.append(f"shared keywords: {', '.join(sorted(shared_kw)[:3])}")

    # Check tribal overlap
    from mtg_deck_maker.engine.synergy import _extract_creature_types

    types_a = _extract_creature_types(card_a)
    types_b = _extract_creature_types(card_b)
    shared_types = types_a & types_b
    if shared_types:
        reasons.append(f"shared creature type(s): {', '.join(sorted(shared_types))}")

    if not reasons:
        reasons.append("complementary effects")

    return "; ".join(reasons)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def generate_strategy_guide(
    deck_cards: list[str],
    card_lookup: dict[str, Card],
    combos: list[Combo],
    commander_name: str,
    archetype: str | None = None,
    seed: int = 42,
    num_sims: int = 1000,
) -> StrategyGuide:
    """Generate a complete strategy guide for a deck.

    Args:
        deck_cards: All card names in the deck (including commander).
        card_lookup: Card name to Card mapping.
        combos: Known combos from the database.
        commander_name: Name of the commander card.
        archetype: Detected archetype (auto-detected if None).
        seed: Random seed for hand simulation.
        num_sims: Number of hand simulations.

    Returns:
        Complete StrategyGuide.
    """
    from mtg_deck_maker.engine.deck_builder import detect_archetype

    commander_card = card_lookup.get(commander_name)

    # Auto-detect archetype and themes
    if archetype is None and commander_card:
        archetype = detect_archetype(commander_card)
    archetype = archetype or "midrange"

    themes: list[str] = []
    if commander_card:
        themes = extract_themes(commander_card)

    # Exclude commander from the 99 for hand simulation
    deck_99 = [c for c in deck_cards if c != commander_name]

    # Compute avg CMC
    non_land_cmcs = [
        card_lookup[c].cmc for c in deck_99
        if c in card_lookup and not _is_land(card_lookup[c])
    ]
    avg_cmc = sum(non_land_cmcs) / len(non_land_cmcs) if non_land_cmcs else 0.0

    hand_sim = simulate_opening_hands(deck_99, card_lookup, num_sims, seed)
    win_paths = analyze_win_conditions(deck_99, card_lookup, combos, archetype, commander_name)
    phases = plan_game_phases(deck_99, card_lookup, archetype, themes, avg_cmc)
    synergies = identify_key_synergies(deck_99, card_lookup)

    return StrategyGuide(
        archetype=archetype,
        themes=themes,
        win_paths=win_paths,
        game_phases=phases,
        hand_simulation=hand_sim,
        key_synergies=synergies,
    )
