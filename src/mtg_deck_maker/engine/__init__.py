"""Deck building engine: categorization, synergy, mana base, power level, deck builder, budget optimizer."""

from mtg_deck_maker.engine.categories import (
    Category,
    categorize_card,
    bulk_categorize,
)
from mtg_deck_maker.engine.synergy import (
    compute_combo_synergy,
    compute_synergy,
    extract_themes,
    score_theme_match,
)
from mtg_deck_maker.engine.mana_base import (
    build_mana_base,
    calculate_land_count,
    calculate_basic_land_distribution,
    count_color_pips,
)
from mtg_deck_maker.engine.power_level import (
    estimate_power_level,
    analyze_deck_composition,
    FAST_MANA_CARDS,
)
from mtg_deck_maker.engine.budget_optimizer import (
    optimize_for_budget,
    score_card,
)
from mtg_deck_maker.engine.deck_builder import (
    build_deck,
    DeckBuildError,
    DEFAULT_CATEGORY_TARGETS,
)

__all__ = [
    "Category",
    "categorize_card",
    "bulk_categorize",
    "compute_combo_synergy",
    "compute_synergy",
    "extract_themes",
    "score_theme_match",
    "build_mana_base",
    "calculate_land_count",
    "calculate_basic_land_distribution",
    "count_color_pips",
    "estimate_power_level",
    "analyze_deck_composition",
    "FAST_MANA_CARDS",
    "optimize_for_budget",
    "score_card",
    "build_deck",
    "DeckBuildError",
    "DEFAULT_CATEGORY_TARGETS",
]
