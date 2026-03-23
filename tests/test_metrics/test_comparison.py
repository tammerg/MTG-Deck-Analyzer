"""Tests for the deck comparison module."""

from __future__ import annotations

from mtg_deck_maker.metrics.comparison import (
    ComparisonResult,
    DeckMetrics,
    compare_decks,
    compute_metrics,
    format_comparison,
)
from mtg_deck_maker.metrics.budget_efficiency import BudgetEfficiencyResult
from mtg_deck_maker.metrics.category_coverage import CategoryCoverageResult
from mtg_deck_maker.metrics.curve_smoothness import CurveSmoothnessResult
from mtg_deck_maker.metrics.edhrec_overlap import EDHRECOverlapResult
from mtg_deck_maker.models.deck import Deck, DeckCard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deck(
    name: str = "Test Deck",
    budget_target: float | None = 50.0,
    cards: list[DeckCard] | None = None,
) -> Deck:
    """Build a minimal Deck for testing."""
    if cards is None:
        cards = [
            DeckCard(card_id=1, card_name="Sol Ring", cmc=1.0, price=3.0, category="ramp"),
            DeckCard(card_id=2, card_name="Swords to Plowshares", cmc=1.0, price=2.0, category="removal"),
            DeckCard(card_id=3, card_name="Brainstorm", cmc=1.0, price=1.0, category="draw"),
            DeckCard(card_id=4, card_name="Command Tower", cmc=0.0, price=0.5, category="land"),
            DeckCard(card_id=5, card_name="Counterspell", cmc=2.0, price=1.5, category="counter"),
        ]
    return Deck(name=name, cards=cards, budget_target=budget_target)


def _category_targets() -> dict[str, tuple[int, int]]:
    return {
        "ramp": (1, 3),
        "removal": (1, 3),
        "draw": (1, 3),
        "counter": (1, 2),
    }


def _ideal_curve() -> dict[int, float]:
    return {
        0: 0.0,
        1: 0.30,
        2: 0.25,
        3: 0.20,
        4: 0.12,
        5: 0.07,
        6: 0.04,
        7: 0.02,
    }


def _edhrec_inclusion() -> dict[str, float]:
    return {
        "Sol Ring": 0.95,
        "Swords to Plowshares": 0.80,
        "Brainstorm": 0.60,
        "Counterspell": 0.70,
    }


# ---------------------------------------------------------------------------
# compute_metrics — all data provided
# ---------------------------------------------------------------------------

class TestComputeMetricsAllData:
    """compute_metrics with all optional data supplied."""

    def test_returns_deck_metrics(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        assert isinstance(result, DeckMetrics)

    def test_basic_fields(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        assert result.deck_name == "Test Deck"
        assert result.total_cards == deck.total_cards()
        assert result.total_price == deck.total_price()
        assert abs(result.average_cmc - deck.average_cmc()) < 1e-9

    def test_all_metrics_populated(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        assert result.category_coverage is not None
        assert isinstance(result.category_coverage, CategoryCoverageResult)
        assert result.curve_smoothness is not None
        assert isinstance(result.curve_smoothness, CurveSmoothnessResult)
        assert result.edhrec_overlap is not None
        assert isinstance(result.edhrec_overlap, EDHRECOverlapResult)
        assert result.budget_efficiency is not None
        assert isinstance(result.budget_efficiency, BudgetEfficiencyResult)


# ---------------------------------------------------------------------------
# compute_metrics — partial data
# ---------------------------------------------------------------------------

class TestComputeMetricsPartialData:
    """compute_metrics with some optional data omitted."""

    def test_no_category_targets(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        assert result.category_coverage is None
        assert result.curve_smoothness is not None
        assert result.edhrec_overlap is not None
        assert result.budget_efficiency is not None

    def test_no_ideal_curve(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            category_targets=_category_targets(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        assert result.category_coverage is not None
        assert result.curve_smoothness is None
        assert result.edhrec_overlap is not None

    def test_no_edhrec_inclusion(self) -> None:
        deck = _make_deck()
        result = compute_metrics(
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
        )
        assert result.edhrec_overlap is None
        # budget_efficiency should still be computed (just no quality_per_dollar)
        assert result.budget_efficiency is not None
        assert result.budget_efficiency.quality_per_dollar is None

    def test_no_optional_data(self) -> None:
        deck = _make_deck()
        result = compute_metrics(deck)
        assert result.category_coverage is None
        assert result.curve_smoothness is None
        assert result.edhrec_overlap is None
        # budget_efficiency is always computed (no required external data)
        assert result.budget_efficiency is not None


# ---------------------------------------------------------------------------
# compare_decks — A wins
# ---------------------------------------------------------------------------

class TestCompareDecksAWins:
    """Scenarios where deck A wins most metrics."""

    def test_a_wins_overall(self) -> None:
        # Deck A: all categories met, good curve, high EDHREC overlap
        cards_a = [
            DeckCard(card_id=1, card_name="Sol Ring", cmc=1.0, price=3.0, category="ramp"),
            DeckCard(card_id=2, card_name="Swords to Plowshares", cmc=1.0, price=2.0, category="removal"),
            DeckCard(card_id=3, card_name="Brainstorm", cmc=1.0, price=1.0, category="draw"),
            DeckCard(card_id=4, card_name="Counterspell", cmc=2.0, price=1.5, category="counter"),
            DeckCard(card_id=5, card_name="Command Tower", cmc=0.0, price=0.5, category="land"),
        ]
        # Deck B: missing categories, worse prices
        cards_b = [
            DeckCard(card_id=10, card_name="Unknown Card A", cmc=5.0, price=10.0, category="other"),
            DeckCard(card_id=11, card_name="Unknown Card B", cmc=6.0, price=8.0, category="other"),
            DeckCard(card_id=12, card_name="Unknown Card C", cmc=4.0, price=5.0, category="other"),
            DeckCard(card_id=13, card_name="Command Tower", cmc=0.0, price=0.5, category="land"),
        ]
        deck_a = _make_deck(name="Deck A", cards=cards_a, budget_target=50.0)
        deck_b = _make_deck(name="Deck B", cards=cards_b, budget_target=50.0)

        result = compare_decks(
            deck_a,
            deck_b,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )

        assert isinstance(result, ComparisonResult)
        assert result.summary["category_coverage"] == "A"
        assert result.summary["edhrec_overlap"] == "A"
        assert result.summary["overall"] == "A"


# ---------------------------------------------------------------------------
# compare_decks — B wins
# ---------------------------------------------------------------------------

class TestCompareDecksBWins:
    """Scenarios where deck B wins."""

    def test_b_wins_overall(self) -> None:
        # Deck A: bad coverage, bad overlap
        cards_a = [
            DeckCard(card_id=10, card_name="Unknown Card A", cmc=5.0, price=10.0, category="other"),
            DeckCard(card_id=11, card_name="Unknown Card B", cmc=6.0, price=8.0, category="other"),
        ]
        # Deck B: good everything
        cards_b = [
            DeckCard(card_id=1, card_name="Sol Ring", cmc=1.0, price=3.0, category="ramp"),
            DeckCard(card_id=2, card_name="Swords to Plowshares", cmc=1.0, price=2.0, category="removal"),
            DeckCard(card_id=3, card_name="Brainstorm", cmc=1.0, price=1.0, category="draw"),
            DeckCard(card_id=4, card_name="Counterspell", cmc=2.0, price=1.5, category="counter"),
        ]
        deck_a = _make_deck(name="Deck A", cards=cards_a, budget_target=50.0)
        deck_b = _make_deck(name="Deck B", cards=cards_b, budget_target=50.0)

        result = compare_decks(
            deck_a,
            deck_b,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )

        assert result.summary["category_coverage"] == "B"
        assert result.summary["edhrec_overlap"] == "B"
        assert result.summary["overall"] == "B"


# ---------------------------------------------------------------------------
# compare_decks — tie
# ---------------------------------------------------------------------------

class TestCompareDecksTie:
    """Identical decks should tie on all metrics."""

    def test_identical_decks_tie(self) -> None:
        deck = _make_deck()
        result = compare_decks(
            deck,
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )

        assert result.summary["category_coverage"] == "tie"
        assert result.summary["curve_smoothness"] == "tie"
        assert result.summary["edhrec_overlap"] == "tie"
        assert result.summary["budget_efficiency"] == "tie"
        assert result.summary["overall"] == "tie"

    def test_tie_when_no_metrics_available(self) -> None:
        deck_a = _make_deck(name="A")
        deck_b = _make_deck(name="B")
        result = compare_decks(deck_a, deck_b)
        # No category_targets, no ideal_curve, no edhrec_inclusion
        # Those metrics are None, but budget_efficiency is always computed
        assert result.summary["category_coverage"] == "tie"
        assert result.summary["curve_smoothness"] == "tie"
        assert result.summary["edhrec_overlap"] == "tie"
        # budget_efficiency still runs; identical decks => tie
        assert result.summary["budget_efficiency"] == "tie"
        assert result.summary["overall"] == "tie"


# ---------------------------------------------------------------------------
# compare_decks — summary values
# ---------------------------------------------------------------------------

class TestComparisonSummaryValues:
    """Verify summary only contains 'A', 'B', or 'tie'."""

    def test_summary_values_are_valid(self) -> None:
        deck_a = _make_deck(name="A")
        deck_b = _make_deck(name="B")
        result = compare_decks(
            deck_a,
            deck_b,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        valid = {"A", "B", "tie"}
        for key, value in result.summary.items():
            assert value in valid, f"summary[{key!r}] = {value!r} not in {valid}"

    def test_summary_has_expected_keys(self) -> None:
        deck_a = _make_deck(name="A")
        deck_b = _make_deck(name="B")
        result = compare_decks(deck_a, deck_b)
        expected_keys = {
            "category_coverage",
            "curve_smoothness",
            "edhrec_overlap",
            "budget_efficiency",
            "synergy_density",
            "overall",
        }
        assert set(result.summary.keys()) == expected_keys


# ---------------------------------------------------------------------------
# format_comparison — output structure
# ---------------------------------------------------------------------------

class TestFormatComparison:
    """Verify the formatted table string."""

    def test_contains_header_row(self) -> None:
        deck = _make_deck()
        result = compare_decks(
            deck,
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        output = format_comparison(result)
        assert "Metric" in output
        assert "Deck A" in output or result.deck_a.deck_name in output
        assert "Winner" in output

    def test_contains_separator(self) -> None:
        deck = _make_deck()
        result = compare_decks(deck, deck)
        output = format_comparison(result)
        assert "---" in output

    def test_contains_metric_rows(self) -> None:
        deck = _make_deck()
        result = compare_decks(
            deck,
            deck,
            category_targets=_category_targets(),
            ideal_curve=_ideal_curve(),
            edhrec_inclusion=_edhrec_inclusion(),
        )
        output = format_comparison(result)
        assert "Category Coverage" in output
        assert "Curve Smoothness" in output
        assert "EDHREC Overlap" in output
        assert "Budget Efficiency" in output
        assert "Average CMC" in output
        assert "Total Price" in output

    def test_returns_string(self) -> None:
        deck = _make_deck()
        result = compare_decks(deck, deck)
        output = format_comparison(result)
        assert isinstance(output, str)

    def test_multiline_output(self) -> None:
        deck = _make_deck()
        result = compare_decks(deck, deck)
        output = format_comparison(result)
        lines = output.strip().split("\n")
        # header + separator + at least 6 data rows
        assert len(lines) >= 8

    def test_winner_column_shows_dash_for_info_rows(self) -> None:
        """Average CMC and Total Price are informational, not compared."""
        deck = _make_deck()
        result = compare_decks(deck, deck)
        output = format_comparison(result)
        for line in output.strip().split("\n"):
            if "Average CMC" in line or "Total Price" in line:
                # The winner column should show '-'
                assert line.rstrip().endswith("-")
