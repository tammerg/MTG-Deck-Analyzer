"""Tests for the post-build synergy audit module."""

from __future__ import annotations

from mtg_deck_maker.engine.synergy_audit import SynergyAuditResult, audit_synergy
from mtg_deck_maker.models.card import Card


def _make_card(
    name: str,
    oracle_text: str = "",
    type_line: str = "Creature",
    keywords: list[str] | None = None,
) -> Card:
    return Card(
        oracle_id=f"oid-{name}",
        name=name,
        oracle_text=oracle_text,
        type_line=type_line,
        keywords=keywords or [],
        color_identity=[],
        colors=[],
        cmc=3.0,
        mana_cost="{3}",
        legal_commander=True,
    )


# ---------------------------------------------------------------------------
# Sacrifice / death-trigger themed cards (high internal synergy)
# ---------------------------------------------------------------------------
_SACRIFICE_CARDS = [
    _make_card("Viscera Seer", "Sacrifice a creature: Scry 1.", "Creature — Vampire Wizard"),
    _make_card("Blood Artist", "Whenever a creature dies, target player loses 1 life.", "Creature — Vampire"),
    _make_card("Zulaport Cutthroat", "Whenever a creature you control dies, each opponent loses 1 life.", "Creature — Human Rogue"),
    _make_card("Grave Pact", "Whenever a creature you control dies, each other player sacrifices a creature.", "Enchantment"),
    _make_card("Carrion Feeder", "Sacrifice a creature: Put a +1/+1 counter on Carrion Feeder.", "Creature — Zombie"),
]

# ---------------------------------------------------------------------------
# Random / low-synergy cards
# ---------------------------------------------------------------------------
_RANDOM_CARDS = [
    _make_card("Grizzly Bears", ""),
    _make_card("Hill Giant", ""),
    _make_card("Wind Drake", "", "Creature — Drake", ["flying"]),
    _make_card("Coral Merfolk", ""),
    _make_card("Forest Bear", ""),
]

# ---------------------------------------------------------------------------
# Pool cards — some synergistic, some not
# ---------------------------------------------------------------------------
_POOL_SYNERGISTIC = [
    _make_card("Dictate of Erebos", "Whenever a creature you control dies, each opponent sacrifices a creature.", "Enchantment"),
    _make_card("Midnight Reaper", "Whenever a nontoken creature you control dies, draw a card.", "Creature — Zombie Knight"),
]
_POOL_RANDOM = [
    _make_card("Runeclaw Bear", ""),
    _make_card("Grey Ogre", ""),
]


class TestAuditSynergyReturnType:
    def test_audit_synergy_returns_result(self) -> None:
        result = audit_synergy(_SACRIFICE_CARDS[:3], [])
        assert isinstance(result, SynergyAuditResult)
        assert isinstance(result.avg_synergy, float)
        assert isinstance(result.low_synergy_cards, list)
        assert isinstance(result.suggested_swaps, list)
        assert isinstance(result.card_synergy_scores, dict)


class TestAvgSynergy:
    def test_avg_synergy_for_synergistic_deck(self) -> None:
        synergy_result = audit_synergy(_SACRIFICE_CARDS, [])
        random_result = audit_synergy(_RANDOM_CARDS, [])
        assert synergy_result.avg_synergy > random_result.avg_synergy


class TestLowSynergyCards:
    def test_low_synergy_cards_sorted_ascending(self) -> None:
        # Mix synergistic and random cards so some are clearly worse
        mixed = _SACRIFICE_CARDS + _RANDOM_CARDS
        result = audit_synergy(mixed, [])
        scores = [s for _, s in result.low_synergy_cards]
        assert scores == sorted(scores), "low_synergy_cards should be sorted ascending by synergy"


class TestCardSynergyScores:
    def test_card_synergy_scores_populated(self) -> None:
        result = audit_synergy(_SACRIFICE_CARDS, [])
        for card in _SACRIFICE_CARDS:
            assert card.name in result.card_synergy_scores


class TestSuggestedSwaps:
    def test_suggested_swaps_improve_synergy(self) -> None:
        # Deck has sacrifice cards plus random cards; pool has synergistic replacements
        deck = _SACRIFICE_CARDS + _RANDOM_CARDS[:3]
        pool = _POOL_SYNERGISTIC + _POOL_RANDOM
        result = audit_synergy(deck, pool, top_swap_count=5)
        for removed, added, improvement in result.suggested_swaps:
            assert improvement > 0.0, (
                f"Swap {removed} -> {added} should have positive improvement, got {improvement}"
            )


class TestEdgeCases:
    def test_empty_selected_returns_zero(self) -> None:
        result = audit_synergy([], [])
        assert result.avg_synergy == 0.0
        assert result.low_synergy_cards == []
        assert result.suggested_swaps == []
        assert result.card_synergy_scores == {}

    def test_single_card_returns_zero(self) -> None:
        result = audit_synergy([_SACRIFICE_CARDS[0]], [])
        assert result.avg_synergy == 0.0
        assert result.card_synergy_scores[_SACRIFICE_CARDS[0].name] == 0.0

    def test_two_cards_synergy(self) -> None:
        from mtg_deck_maker.engine.synergy import compute_pairwise_synergy

        cards = _SACRIFICE_CARDS[:2]
        expected = compute_pairwise_synergy(cards[0], cards[1])
        result = audit_synergy(cards, [])
        assert abs(result.avg_synergy - expected) < 1e-9


class TestPoolConstraints:
    def test_pool_cards_not_in_selected(self) -> None:
        # Put a pool card that is also in selected — should not appear in swaps
        overlap_card = _SACRIFICE_CARDS[0]
        deck = _SACRIFICE_CARDS + _RANDOM_CARDS[:2]
        pool = [overlap_card] + _POOL_SYNERGISTIC
        result = audit_synergy(deck, pool, top_swap_count=5)
        added_names = {added for _, added, _ in result.suggested_swaps}
        assert overlap_card.name not in added_names

    def test_swap_count_limited(self) -> None:
        deck = _SACRIFICE_CARDS + _RANDOM_CARDS
        pool = _POOL_SYNERGISTIC + _POOL_RANDOM
        result = audit_synergy(deck, pool, top_swap_count=2)
        assert len(result.suggested_swaps) <= 2

    def test_no_swaps_when_pool_empty(self) -> None:
        result = audit_synergy(_SACRIFICE_CARDS + _RANDOM_CARDS, [], top_swap_count=5)
        assert result.suggested_swaps == []
