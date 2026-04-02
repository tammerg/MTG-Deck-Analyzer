"""Data-driven commander research service (no LLM required).

Assembles a ResearchResult from EDHREC per-commander data,
CommanderSpellbook combos, archetype/theme detection, and the
category engine.  Provides the same output shape as the LLM-based
ResearchService so callers can use either interchangeably.
"""

from __future__ import annotations

import asyncio
import logging

from mtg_deck_maker.api.edhrec import fetch_commander_data
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.combo_repo import ComboRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.engine.deck_builder import (
    ARCHETYPE_CATEGORY_TARGETS,
    DEFAULT_CATEGORY_TARGETS,
    detect_archetype,
)
from mtg_deck_maker.engine.synergy import extract_themes
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.services.research_service import ResearchResult

logger = logging.getLogger(__name__)

_COLOR_NAMES: dict[str, str] = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}

_BUDGET_THRESHOLD = 5.0
_KEY_CARDS_LIMIT = 15
_BUDGET_STAPLES_LIMIT = 10
_COMBOS_LIMIT = 5
_WIN_CONDITIONS_LIMIT = 10


def _color_identity_label(colors: list[str]) -> str:
    """Convert color identity letters to a readable string."""
    if not colors:
        return "colorless"
    return "/".join(_COLOR_NAMES.get(c, c) for c in sorted(colors))


def _build_strategy_overview(
    commander: Card,
    archetype: str,
    themes: list[str],
) -> str:
    """Generate a template-based strategy overview."""
    color_label = _color_identity_label(commander.color_identity)
    identity_letters = "".join(sorted(commander.color_identity)) or "C"

    theme_str = ""
    if themes:
        if len(themes) == 1:
            theme_str = f" focusing on {themes[0]} themes"
        else:
            theme_str = f" focusing on {', '.join(themes[:-1])} and {themes[-1]} themes"

    overview = (
        f"{commander.name} is a {archetype} commander"
        f"{theme_str} in {identity_letters} ({color_label})."
    )

    # Add archetype-specific advice
    advice: dict[str, str] = {
        "aggro": " Prioritize low-curve threats, combat enhancers, and haste enablers.",
        "control": " Prioritize answers, card advantage, and finishers that close the game.",
        "combo": " Prioritize tutors, card draw, and combo protection pieces.",
        "midrange": " Prioritize a balanced mix of threats, interaction, and card advantage.",
        "tribal": " Prioritize tribal synergies, lords, and tribal payoff cards.",
        "spellslinger": " Prioritize instants/sorceries, spell copying, and storm enablers.",
    }
    overview += advice.get(archetype, "")

    return overview


def data_research_commander(
    db: Database,
    commander_name: str,
    budget: float | None = None,
) -> ResearchResult:
    """Research a commander using only data sources (no LLM).

    Assembles a ResearchResult from EDHREC per-commander data,
    CommanderSpellbook combos, archetype detection, theme extraction,
    and the category engine.

    Args:
        db: Database connection for local data lookups.
        commander_name: Name of the commander card.
        budget: Optional budget constraint (reserved for future use).

    Returns:
        ResearchResult populated from data sources.
    """
    card_repo = CardRepository(db)
    price_repo = PriceRepository(db)
    combo_repo = ComboRepository(db)

    # Look up the commander card in local DB
    commander = card_repo.get_card_by_name(commander_name)

    # Detect archetype and themes
    archetype = "midrange"
    themes: list[str] = []
    color_identity: list[str] = []

    if commander:
        archetype = detect_archetype(commander)
        themes = extract_themes(commander)
        color_identity = commander.color_identity

    # Build strategy overview
    strategy_overview = ""
    if commander:
        strategy_overview = _build_strategy_overview(commander, archetype, themes)
    else:
        strategy_overview = (
            f"Research for {commander_name}. "
            "Commander not found in local database — showing EDHREC data only."
        )

    # Fetch EDHREC per-commander data
    try:
        edhrec_data = asyncio.run(fetch_commander_data(commander_name))
        edhrec_data.sort(key=lambda d: d.inclusion_rate, reverse=True)
    except Exception:
        logger.exception("EDHREC fetch failed for commander '%s'", commander_name)
        edhrec_data = []

    # Key cards: top N by inclusion rate
    key_cards = [d.card_name for d in edhrec_data[:_KEY_CARDS_LIMIT]]

    # Build card name -> Card map once for reuse
    card_map: dict[str, Card] = {}
    for entry in edhrec_data:
        if entry.card_name not in card_map:
            card = card_repo.get_card_by_name(entry.card_name)
            if card:
                card_map[entry.card_name] = card

    # Budget staples: resolve prices, filter to cheap cards
    budget_staples: list[str] = []
    for entry in edhrec_data:
        if len(budget_staples) >= _BUDGET_STAPLES_LIMIT:
            break
        card = card_map.get(entry.card_name)
        if card and card.id is not None:
            price = price_repo.get_cheapest_price(card.id)
            if price is not None and price < _BUDGET_THRESHOLD:
                budget_staples.append(entry.card_name)

    # Combos from CommanderSpellbook
    combos: list[str] = []
    raw_combos = combo_repo.get_combos_for_card(commander_name)

    # Filter combos by color identity
    ci_set = set(color_identity)
    if ci_set:
        for combo in raw_combos:
            if len(combos) >= _COMBOS_LIMIT:
                break
            combo_ci = set(combo.color_identity)
            if combo_ci.issubset(ci_set):
                cards_str = " + ".join(combo.card_names)
                combos.append(f"{combo.result} ({cards_str})")

    # Win conditions: from EDHREC top cards, categorize and filter
    win_conditions: list[str] = []
    for entry in edhrec_data:
        if len(win_conditions) >= _WIN_CONDITIONS_LIMIT:
            break
        card = card_map.get(entry.card_name)
        if card:
            cats = categorize_card(card)
            cat_names = {c for c, _ in cats}
            if Category.WIN_CONDITION.value in cat_names:
                win_conditions.append(entry.card_name)

    # Category targets from archetype detection
    category_targets = ARCHETYPE_CATEGORY_TARGETS.get(
        archetype, DEFAULT_CATEGORY_TARGETS
    )

    return ResearchResult(
        commander_name=commander_name,
        strategy_overview=strategy_overview,
        key_cards=key_cards,
        budget_staples=budget_staples,
        combos=combos,
        win_conditions=win_conditions,
        cards_to_avoid=[],
        category_targets=category_targets,
        parse_success=True,
    )
