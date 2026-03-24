"""Strategy guide service orchestrating deck analysis and optional LLM narrative."""

from __future__ import annotations

import logging
import sqlite3

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.combo_repo import ComboRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.deck_repo import DeckRepository
from mtg_deck_maker.engine.strategy_guide import generate_strategy_guide
from mtg_deck_maker.models.strategy_guide import StrategyGuide

logger = logging.getLogger(__name__)


class StrategyGuideService:
    """Generates a strategy guide for a persisted deck."""

    def generate(
        self,
        deck_id: int,
        db: Database,
        llm_provider: LLMProvider | None = None,
        seed: int = 42,
        num_sims: int = 1000,
    ) -> StrategyGuide:
        """Build a strategy guide for the given deck.

        Args:
            deck_id: Database ID of the deck.
            db: Database connection.
            llm_provider: Optional LLM provider for narrative enrichment.
            seed: Random seed for hand simulation.
            num_sims: Number of hand simulations.

        Returns:
            StrategyGuide with analysis and optional LLM narrative.

        Raises:
            ValueError: If the deck is not found.
        """
        deck_repo = DeckRepository(db)
        card_repo = CardRepository(db)
        combo_repo = ComboRepository(db)

        deck = deck_repo.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found.")

        # Build card lookup — single batch query instead of N+1
        cards_by_id = card_repo.get_cards_by_ids(
            [dc.card_id for dc in deck.cards]
        )
        card_lookup = {}
        card_names: list[str] = []
        for card in cards_by_id.values():
            if card is not None:
                card_lookup[card.name] = card
                card_names.append(card.name)

        # Find commander
        commander_name = ""
        for dc in deck.cards:
            if dc.is_commander and dc.card_name:
                commander_name = dc.card_name
                break

        # Fetch combos (table may not exist if sync hasn't been run)
        try:
            combos = combo_repo.get_combos_for_cards(card_names)
        except sqlite3.OperationalError:
            logger.warning("Combos table unavailable; proceeding without combos")
            combos = []

        # Generate algorithmic guide
        guide = generate_strategy_guide(
            deck_cards=card_names,
            card_lookup=card_lookup,
            combos=combos,
            commander_name=commander_name,
            seed=seed,
            num_sims=num_sims,
        )

        # LLM narrative enrichment
        if llm_provider is not None:
            try:
                narrative = self._generate_narrative(guide, llm_provider)
                guide.llm_narrative = narrative
            except Exception as exc:
                logger.warning("LLM narrative generation failed: %s", exc)

        return guide

    def _generate_narrative(
        self,
        guide: StrategyGuide,
        provider: LLMProvider,
    ) -> str:
        """Generate a narrative summary using an LLM.

        Args:
            guide: The algorithmic strategy guide.
            provider: LLM provider to use.

        Returns:
            Narrative text (2-3 paragraphs).
        """
        win_path_names = [wp.name for wp in guide.win_paths[:5]]
        phase_summaries = [
            f"{p.phase_name} ({p.turn_range}): {', '.join(p.priorities[:2])}"
            for p in guide.game_phases
        ]
        keep_rate = guide.hand_simulation.keep_rate if guide.hand_simulation else 0.0

        context = (
            f"Archetype: {guide.archetype}\n"
            f"Themes: {', '.join(guide.themes) if guide.themes else 'none detected'}\n"
            f"Win Paths: {', '.join(win_path_names) if win_path_names else 'none'}\n"
            f"Game Plan: {'; '.join(phase_summaries)}\n"
            f"Opening Hand Keep Rate: {keep_rate:.0%}\n"
            f"Key Synergies: {len(guide.key_synergies)} pairs identified"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Magic: The Gathering Commander deck analyst. "
                    "Write clear, specific, and actionable strategy narratives that "
                    "help pilots understand their deck's game plan and key decisions."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Based on the following deck analysis data, write a 2-3 paragraph "
                    "strategy narrative that explains the deck's game plan, strengths, "
                    "and key decisions a pilot should make. Be specific and actionable.\n\n"
                    f"{context}"
                ),
            },
        ]

        return provider.chat(messages, max_tokens=512, temperature=0.7)
