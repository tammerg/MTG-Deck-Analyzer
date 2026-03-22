"""Deck comparison — runs all metrics on two decks and produces a side-by-side."""

from __future__ import annotations

from dataclasses import dataclass

from mtg_deck_maker.metrics.budget_efficiency import (
    BudgetEfficiencyResult,
    budget_efficiency,
)
from mtg_deck_maker.metrics.category_coverage import (
    CategoryCoverageResult,
    category_coverage,
)
from mtg_deck_maker.metrics.curve_smoothness import (
    CurveSmoothnessResult,
    curve_smoothness,
)
from mtg_deck_maker.metrics.edhrec_overlap import (
    EDHRECOverlapResult,
    edhrec_overlap,
)
from mtg_deck_maker.models.deck import Deck

_TOLERANCE = 0.01


@dataclass(slots=True)
class DeckMetrics:
    """All metrics for a single deck."""

    deck_name: str
    total_cards: int
    total_price: float
    average_cmc: float
    category_coverage: CategoryCoverageResult | None
    curve_smoothness: CurveSmoothnessResult | None
    edhrec_overlap: EDHRECOverlapResult | None
    budget_efficiency: BudgetEfficiencyResult | None


@dataclass(slots=True)
class ComparisonResult:
    """Side-by-side comparison of two decks."""

    deck_a: DeckMetrics
    deck_b: DeckMetrics
    summary: dict[str, str]


def _compare_floats(
    val_a: float | None,
    val_b: float | None,
) -> str:
    """Return 'A', 'B', or 'tie' for two float values within tolerance."""
    if val_a is None or val_b is None:
        return "tie"
    diff = val_a - val_b
    if abs(diff) <= _TOLERANCE:
        return "tie"
    return "A" if diff > 0 else "B"


def _compare_metric(
    metric_a: object | None,
    metric_b: object | None,
    field: str,
) -> str:
    """Compare a specific field from two metric results."""
    if metric_a is None or metric_b is None:
        return "tie"
    val_a = getattr(metric_a, field, None)
    val_b = getattr(metric_b, field, None)
    return _compare_floats(val_a, val_b)


def _budget_winner(
    be_a: BudgetEfficiencyResult | None,
    be_b: BudgetEfficiencyResult | None,
) -> str:
    """Compare budget efficiency: prefer quality_per_dollar, fallback to lower total_spent."""
    if be_a is None or be_b is None:
        return "tie"
    if be_a.quality_per_dollar is not None and be_b.quality_per_dollar is not None:
        return _compare_floats(be_a.quality_per_dollar, be_b.quality_per_dollar)
    # Fallback: lower total_spent wins (invert comparison)
    result = _compare_floats(be_a.total_spent, be_b.total_spent)
    if result == "A":
        return "B"
    if result == "B":
        return "A"
    return "tie"


def compute_metrics(
    deck: Deck,
    category_targets: dict[str, tuple[int, int]] | None = None,
    ideal_curve: dict[int, float] | None = None,
    edhrec_inclusion: dict[str, float] | None = None,
) -> DeckMetrics:
    """Compute all available metrics for a single deck."""
    cc = category_coverage(deck, category_targets) if category_targets is not None else None
    cs = curve_smoothness(deck, ideal_curve) if ideal_curve is not None else None
    eo = edhrec_overlap(deck, edhrec_inclusion) if edhrec_inclusion is not None else None
    be = budget_efficiency(deck, edhrec_inclusion)

    return DeckMetrics(
        deck_name=deck.name,
        total_cards=deck.total_cards(),
        total_price=deck.total_price(),
        average_cmc=deck.average_cmc(),
        category_coverage=cc,
        curve_smoothness=cs,
        edhrec_overlap=eo,
        budget_efficiency=be,
    )


def compare_decks(
    deck_a: Deck,
    deck_b: Deck,
    category_targets: dict[str, tuple[int, int]] | None = None,
    ideal_curve: dict[int, float] | None = None,
    edhrec_inclusion: dict[str, float] | None = None,
) -> ComparisonResult:
    """Compare two decks across all metrics."""
    metrics_a = compute_metrics(deck_a, category_targets, ideal_curve, edhrec_inclusion)
    metrics_b = compute_metrics(deck_b, category_targets, ideal_curve, edhrec_inclusion)

    summary: dict[str, str] = {}

    summary["category_coverage"] = _compare_metric(
        metrics_a.category_coverage, metrics_b.category_coverage, "overall_pct",
    )
    summary["curve_smoothness"] = _compare_metric(
        metrics_a.curve_smoothness, metrics_b.curve_smoothness, "smoothness",
    )
    summary["edhrec_overlap"] = _compare_metric(
        metrics_a.edhrec_overlap, metrics_b.edhrec_overlap, "overlap_pct",
    )
    summary["budget_efficiency"] = _budget_winner(
        metrics_a.budget_efficiency, metrics_b.budget_efficiency,
    )

    # Overall: count A vs B wins across the four metrics
    a_wins = sum(1 for k, v in summary.items() if v == "A")
    b_wins = sum(1 for k, v in summary.items() if v == "B")
    if a_wins > b_wins:
        summary["overall"] = "A"
    elif b_wins > a_wins:
        summary["overall"] = "B"
    else:
        summary["overall"] = "tie"

    return ComparisonResult(deck_a=metrics_a, deck_b=metrics_b, summary=summary)


def _fmt_pct(value: float | None) -> str:
    """Format a float as a percentage string."""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _fmt_float(value: float | None) -> str:
    """Format a float to 2 decimal places."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _fmt_dollar(value: float | None) -> str:
    """Format a float as a dollar amount."""
    if value is None:
        return "N/A"
    return f"${value:.2f}"


def format_comparison(result: ComparisonResult) -> str:
    """Format a comparison result as a human-readable table string."""
    ma = result.deck_a
    mb = result.deck_b

    col_w = 24
    val_w = 16

    header = (
        f"{'Metric':<{col_w}}| {ma.deck_name:<{val_w}}| {mb.deck_name:<{val_w}}| Winner"
    )
    sep = f"{'-' * col_w}|{'-' * (val_w + 1)}|{'-' * (val_w + 1)}|{'-' * 7}"

    rows: list[str] = []

    # Category Coverage
    cc_a = _fmt_pct(ma.category_coverage.overall_pct if ma.category_coverage else None)
    cc_b = _fmt_pct(mb.category_coverage.overall_pct if mb.category_coverage else None)
    cc_w = result.summary["category_coverage"]
    rows.append(
        f"{'Category Coverage':<{col_w}}| {cc_a:<{val_w}}| {cc_b:<{val_w}}| {cc_w}"
    )

    # Curve Smoothness
    cs_a = _fmt_float(ma.curve_smoothness.smoothness if ma.curve_smoothness else None)
    cs_b = _fmt_float(mb.curve_smoothness.smoothness if mb.curve_smoothness else None)
    cs_w = result.summary["curve_smoothness"]
    rows.append(
        f"{'Curve Smoothness':<{col_w}}| {cs_a:<{val_w}}| {cs_b:<{val_w}}| {cs_w}"
    )

    # EDHREC Overlap
    eo_a = _fmt_pct(ma.edhrec_overlap.overlap_pct if ma.edhrec_overlap else None)
    eo_b = _fmt_pct(mb.edhrec_overlap.overlap_pct if mb.edhrec_overlap else None)
    eo_w = result.summary["edhrec_overlap"]
    rows.append(
        f"{'EDHREC Overlap':<{col_w}}| {eo_a:<{val_w}}| {eo_b:<{val_w}}| {eo_w}"
    )

    # Budget Efficiency
    be_a = _fmt_dollar(ma.budget_efficiency.total_spent if ma.budget_efficiency else None)
    be_b = _fmt_dollar(mb.budget_efficiency.total_spent if mb.budget_efficiency else None)
    be_w = result.summary["budget_efficiency"]
    rows.append(
        f"{'Budget Efficiency':<{col_w}}| {be_a:<{val_w}}| {be_b:<{val_w}}| {be_w}"
    )

    # Informational rows (no winner)
    rows.append(
        f"{'Average CMC':<{col_w}}| {_fmt_float(ma.average_cmc):<{val_w}}"
        f"| {_fmt_float(mb.average_cmc):<{val_w}}| -"
    )
    rows.append(
        f"{'Total Price':<{col_w}}| {_fmt_dollar(ma.total_price):<{val_w}}"
        f"| {_fmt_dollar(mb.total_price):<{val_w}}| -"
    )

    return "\n".join([header, sep, *rows])
