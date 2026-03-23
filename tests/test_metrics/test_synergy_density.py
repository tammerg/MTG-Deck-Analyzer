"""Tests for the synergy density metric module."""

from __future__ import annotations

from mtg_deck_maker.metrics.comparison import (
    compare_decks,
    compute_metrics,
    format_comparison,
)
from mtg_deck_maker.metrics.synergy_density import (
    SynergyDensityResult,
    synergy_density,
)
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck, DeckCard


# ---------------------------------------------------------------------------
# Card fixtures
# ---------------------------------------------------------------------------

def _token_creator() -> Card:
    """Card that creates tokens (sacrifice enabler / token theme)."""
    return Card(
        oracle_id="tok-1",
        name="Token Maker",
        type_line="Creature \u2014 Human Soldier",
        oracle_text="When Token Maker enters the battlefield, create two 1/1 white Soldier creature tokens.",
        cmc=3.0,
        colors=["W"],
        color_identity=["W"],
        keywords=[],
    )


def _sacrifice_payoff() -> Card:
    """Card that triggers whenever a creature dies (sacrifice payoff)."""
    return Card(
        oracle_id="sac-1",
        name="Death Profiteer",
        type_line="Creature \u2014 Human Cleric",
        oracle_text="Whenever a creature you control dies, you gain 1 life and draw a card.",
        cmc=3.0,
        colors=["B"],
        color_identity=["B"],
        keywords=[],
    )


def _counter_card() -> Card:
    """Card that uses +1/+1 counters."""
    return Card(
        oracle_id="cnt-1",
        name="Counter Smith",
        type_line="Creature \u2014 Human Artificer",
        oracle_text="When Counter Smith enters the battlefield, put a +1/+1 counter on each creature you control.",
        cmc=4.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
    )


def _unrelated_card() -> Card:
    """Card with no synergy keywords."""
    return Card(
        oracle_id="unr-1",
        name="Vanilla Bear",
        type_line="Creature \u2014 Bear",
        oracle_text="",
        cmc=2.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
    )


def _land_card() -> Card:
    """A basic land card."""
    return Card(
        oracle_id="land-1",
        name="Plains",
        type_line="Basic Land \u2014 Plains",
        oracle_text="",
        cmc=0.0,
        colors=[],
        color_identity=["W"],
        keywords=[],
    )


def _make_lookup(*cards: Card) -> dict[str, Card]:
    return {c.name: c for c in cards}


def _make_deck(
    deck_cards: list[DeckCard],
    name: str = "Test Deck",
) -> Deck:
    return Deck(name=name, cards=deck_cards)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSynergyDensityEdgeCases:
    """Edge cases returning zeroed results."""

    def test_empty_deck(self) -> None:
        deck = _make_deck([])
        result = synergy_density(deck, {})
        assert result.pair_count == 0
        assert result.card_count == 0
        assert result.avg_synergy == 0.0
        assert result.min_synergy == 0.0
        assert result.max_synergy == 0.0
        assert result.low_synergy_count == 0

    def test_single_card_deck(self) -> None:
        tok = _token_creator()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
        ])
        result = synergy_density(deck, _make_lookup(tok))
        assert result.pair_count == 0
        assert result.card_count == 1
        assert result.avg_synergy == 0.0

    def test_cards_not_in_lookup_are_skipped(self) -> None:
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Missing Card A", cmc=2.0, category="creature"),
            DeckCard(card_id=2, card_name="Missing Card B", cmc=3.0, category="creature"),
        ])
        result = synergy_density(deck, {})
        assert result.pair_count == 0
        assert result.card_count == 0


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestSynergyDensityFiltering:
    """Cards excluded by category or role."""

    def test_land_cards_excluded(self) -> None:
        tok = _token_creator()
        land = _land_card()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Plains", cmc=0.0, category="land"),
        ])
        result = synergy_density(deck, _make_lookup(tok, land))
        # Only 1 nonland card, so no pairs
        assert result.card_count == 1
        assert result.pair_count == 0

    def test_commander_cards_excluded(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature", is_commander=True),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
        ])
        result = synergy_density(deck, _make_lookup(tok, sac))
        assert result.card_count == 1
        assert result.pair_count == 0

    def test_companion_cards_excluded(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature", is_companion=True),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
        ])
        result = synergy_density(deck, _make_lookup(tok, sac))
        assert result.card_count == 1
        assert result.pair_count == 0


# ---------------------------------------------------------------------------
# Pair computation
# ---------------------------------------------------------------------------

class TestSynergyDensityPairComputation:
    """Correct pair counts and score tracking."""

    def test_two_cards_one_pair(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
        ])
        result = synergy_density(deck, _make_lookup(tok, sac))
        assert result.pair_count == 1
        assert result.card_count == 2

    def test_three_cards_three_pairs(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        cnt = _counter_card()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
            DeckCard(card_id=3, card_name="Counter Smith", cmc=4.0, category="creature"),
        ])
        result = synergy_density(deck, _make_lookup(tok, sac, cnt))
        assert result.pair_count == 3
        assert result.card_count == 3

    def test_avg_synergy_is_mean(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        cnt = _counter_card()
        lookup = _make_lookup(tok, sac, cnt)
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
            DeckCard(card_id=3, card_name="Counter Smith", cmc=4.0, category="creature"),
        ])
        result = synergy_density(deck, lookup)

        # Manually compute expected average
        from mtg_deck_maker.engine.synergy import compute_pairwise_synergy

        scores = [
            compute_pairwise_synergy(tok, sac),
            compute_pairwise_synergy(tok, cnt),
            compute_pairwise_synergy(sac, cnt),
        ]
        expected_avg = sum(scores) / len(scores)
        assert abs(result.avg_synergy - expected_avg) < 1e-9

    def test_min_max_correctly_identified(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        unr = _unrelated_card()
        lookup = _make_lookup(tok, sac, unr)
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, category="creature"),
            DeckCard(card_id=3, card_name="Vanilla Bear", cmc=2.0, category="creature"),
        ])
        result = synergy_density(deck, lookup)

        from mtg_deck_maker.engine.synergy import compute_pairwise_synergy

        scores = [
            compute_pairwise_synergy(tok, sac),
            compute_pairwise_synergy(tok, unr),
            compute_pairwise_synergy(sac, unr),
        ]
        assert abs(result.min_synergy - min(scores)) < 1e-9
        assert abs(result.max_synergy - max(scores)) < 1e-9

    def test_low_synergy_count(self) -> None:
        tok = _token_creator()
        unr = _unrelated_card()
        lookup = _make_lookup(tok, unr)
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, category="creature"),
            DeckCard(card_id=2, card_name="Vanilla Bear", cmc=2.0, category="creature"),
        ])
        result = synergy_density(deck, lookup)

        from mtg_deck_maker.engine.synergy import compute_pairwise_synergy

        score = compute_pairwise_synergy(tok, unr)
        expected_low = 1 if score < 0.1 else 0
        assert result.low_synergy_count == expected_low


# ---------------------------------------------------------------------------
# Integration with comparison module
# ---------------------------------------------------------------------------

class TestSynergyDensityComparison:
    """Integration with compute_metrics, compare_decks, format_comparison."""

    def _deck_and_lookup(self) -> tuple[Deck, dict[str, Card]]:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        deck = _make_deck([
            DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, price=1.0, category="creature"),
            DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, price=2.0, category="creature"),
        ])
        return deck, _make_lookup(tok, sac)

    def test_compute_metrics_with_card_lookup(self) -> None:
        deck, lookup = self._deck_and_lookup()
        result = compute_metrics(deck, card_lookup=lookup)
        assert result.synergy_density is not None
        assert isinstance(result.synergy_density, SynergyDensityResult)
        assert result.synergy_density.pair_count == 1

    def test_compute_metrics_without_card_lookup(self) -> None:
        deck, _ = self._deck_and_lookup()
        result = compute_metrics(deck)
        assert result.synergy_density is None

    def test_compare_decks_includes_synergy_density(self) -> None:
        tok = _token_creator()
        sac = _sacrifice_payoff()
        unr = _unrelated_card()
        lookup = _make_lookup(tok, sac, unr)

        deck_a = _make_deck(
            [
                DeckCard(card_id=1, card_name="Token Maker", cmc=3.0, price=1.0, category="creature"),
                DeckCard(card_id=2, card_name="Death Profiteer", cmc=3.0, price=2.0, category="creature"),
            ],
            name="Deck A",
        )
        deck_b = _make_deck(
            [
                DeckCard(card_id=3, card_name="Token Maker", cmc=3.0, price=1.0, category="creature"),
                DeckCard(card_id=4, card_name="Vanilla Bear", cmc=2.0, price=0.5, category="creature"),
            ],
            name="Deck B",
        )
        result = compare_decks(deck_a, deck_b, card_lookup=lookup)
        assert "synergy_density" in result.summary
        assert result.summary["synergy_density"] in {"A", "B", "tie"}

    def test_format_comparison_includes_synergy_density_row(self) -> None:
        deck, lookup = self._deck_and_lookup()
        result = compare_decks(deck, deck, card_lookup=lookup)
        output = format_comparison(result)
        assert "Synergy Density" in output
