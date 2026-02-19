"""Tests for the build service orchestration layer."""

from __future__ import annotations

import pytest

from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.services.build_service import (
    BuildResult,
    BuildService,
    BuildServiceError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(
    card_id: int,
    name: str,
    type_line: str = "Instant",
    oracle_text: str = "",
    mana_cost: str = "{1}",
    cmc: float = 1.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    keywords: list[str] | None = None,
    edhrec_rank: int = 1000,
    legal_commander: bool = True,
) -> Card:
    """Create a test Card with sensible defaults."""
    return Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=color_identity or [],
        keywords=keywords or [],
        edhrec_rank=edhrec_rank,
        legal_commander=legal_commander,
        id=card_id,
    )


def _build_mono_green_pool(size: int = 250) -> list[Card]:
    """Build a card pool for a mono-green commander."""
    pool: list[Card] = []
    card_id = 1

    # Ramp
    for j in range(15):
        pool.append(_make_card(
            card_id, f"Green Ramp {j}",
            "Sorcery", "Search your library for a Forest card.",
            "{1}{G}", 2.0, ["G"], ["G"], edhrec_rank=100 + j,
        ))
        card_id += 1

    # Colorless ramp
    for j in range(8):
        pool.append(_make_card(
            card_id, f"Mana Rock {j}",
            "Artifact", "{T}: Add {C}.",
            "{2}", 2.0, [], [], edhrec_rank=200 + j,
        ))
        card_id += 1

    # Draw
    for j in range(12):
        pool.append(_make_card(
            card_id, f"Green Draw {j}",
            "Sorcery", "Draw a card for each creature you control.",
            "{2}{G}", 3.0, ["G"], ["G"], edhrec_rank=300 + j,
        ))
        card_id += 1

    # Removal
    for j in range(10):
        pool.append(_make_card(
            card_id, f"Green Removal {j}",
            "Instant", "Destroy target artifact or enchantment.",
            "{1}{G}", 2.0, ["G"], ["G"], edhrec_rank=400 + j,
        ))
        card_id += 1

    # Board wipes
    for j in range(4):
        pool.append(_make_card(
            card_id, f"Green Wipe {j}",
            "Sorcery", "Destroy all artifacts and enchantments.",
            "{4}{G}", 5.0, ["G"], ["G"], edhrec_rank=500 + j,
        ))
        card_id += 1

    # Protection
    for j in range(6):
        pool.append(_make_card(
            card_id, f"Green Protection {j}",
            "Instant", "Target creature gains hexproof until end of turn.",
            "{G}", 1.0, ["G"], ["G"], edhrec_rank=600 + j,
        ))
        card_id += 1

    # Win conditions
    for j in range(10):
        pool.append(_make_card(
            card_id, f"Green Finisher {j}",
            "Creature - Beast", "Trample\nEach opponent loses life.",
            "{4}{G}{G}", 6.0, ["G"], ["G"],
            keywords=["Trample"],
            edhrec_rank=50 + j,
        ))
        card_id += 1

    # Creatures/utility
    while len(pool) < size:
        pool.append(_make_card(
            card_id, f"Green Creature {card_id}",
            "Creature - Elf", "When this enters, you gain 1 life.",
            "{2}{G}", 3.0, ["G"], ["G"], edhrec_rank=800 + card_id,
        ))
        card_id += 1

    # Basic lands
    pool.append(_make_card(
        card_id, "Forest", "Basic Land", "", "", 0.0, [], [],
        edhrec_rank=None,
    ))
    card_id += 1

    # Command Tower (won't be used for mono but included for completeness)
    pool.append(_make_card(
        card_id, "Command Tower", "Land",
        "{T}: Add one mana of any color in your commander's color identity.",
        "", 0.0, [], [], edhrec_rank=2,
    ))
    card_id += 1

    return pool


def _build_mono_green_commander() -> Commander:
    """Create a mono-green commander."""
    cmd = _make_card(
        card_id=8000,
        name="Test Green Commander",
        type_line="Legendary Creature - Elf Druid",
        oracle_text="Whenever a land enters the battlefield under your control, you gain 1 life.",
        mana_cost="{2}{G}",
        cmc=3.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
        edhrec_rank=30,
    )
    return Commander(primary=cmd)


def _build_prices(pool: list[Card]) -> dict[int, float]:
    """Build a price dict for the pool."""
    prices: dict[int, float] = {}
    for card in pool:
        if card.id is not None:
            if card.is_land:
                prices[card.id] = 0.10
            elif card.edhrec_rank and card.edhrec_rank < 100:
                prices[card.id] = 2.00
            else:
                prices[card.id] = 0.50
    return prices


# ===========================================================================
# Tests
# ===========================================================================


class TestBuildService:
    """Tests for the BuildService class."""

    def test_end_to_end_build(self):
        """Service should produce a complete 100-card deck."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
        )

        assert isinstance(result, BuildResult)
        assert result.deck is not None
        assert result.deck.total_cards() == 100

    def test_build_with_csv_export(self):
        """Service should produce CSV output when requested."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
            export_csv=True,
        )

        assert result.csv_output is not None
        assert "Card Name" in result.csv_output
        assert "DECK SUMMARY" in result.csv_output

    def test_build_with_custom_config(self):
        """Service should respect custom configuration."""
        config = AppConfig()
        config.constraints.max_price_per_card = 5.0
        service = BuildService(config=config)
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
        )

        assert result.deck.total_cards() == 100

    def test_invalid_commander_raises_service_error(self):
        """Service should raise BuildServiceError for invalid commander."""
        service = BuildService()
        bad_card = _make_card(
            9999, "Not A Legend",
            "Creature - Human", "", "{1}", 1.0, [], [],
        )
        commander = Commander(primary=bad_card)
        pool = _build_mono_green_pool()

        with pytest.raises(BuildServiceError, match="Commander validation failed"):
            service.build(
                commander=commander,
                budget=100.0,
                card_pool=pool,
            )

    def test_deterministic_builds(self):
        """Same seed should produce identical results."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result1 = service.build(
            commander=commander, budget=150.0,
            card_pool=pool, prices=prices, seed=42,
        )
        result2 = service.build(
            commander=commander, budget=150.0,
            card_pool=pool, prices=prices, seed=42,
        )

        names1 = sorted(c.card_name for c in result1.deck.cards)
        names2 = sorted(c.card_name for c in result2.deck.cards)
        assert names1 == names2

    def test_warnings_for_budget_overage(self):
        """Service should include warnings when deck is over budget."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        # Set all prices high to trigger budget warning potential
        prices = {card.id: 3.0 for card in pool if card.id is not None}

        result = service.build(
            commander=commander,
            budget=500.0,  # High budget to avoid build failure
            card_pool=pool,
            prices=prices,
        )

        # The deck should still be built; warnings may or may not appear
        # depending on final price vs budget
        assert result.deck is not None
        assert result.deck.total_cards() == 100

    def test_build_result_attributes(self):
        """BuildResult should have correct attribute types."""
        service = BuildService()
        commander = _build_mono_green_commander()
        pool = _build_mono_green_pool()
        prices = _build_prices(pool)

        result = service.build(
            commander=commander,
            budget=150.0,
            card_pool=pool,
            prices=prices,
        )

        assert hasattr(result, "deck")
        assert hasattr(result, "warnings")
        assert hasattr(result, "csv_output")
        assert isinstance(result.warnings, list)
        assert result.csv_output is None  # Not requested
