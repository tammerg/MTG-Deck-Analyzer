"""Benchmark commander suite for regression testing the deck building algorithm.

Defines reference commanders covering all major archetypes, along with
validation logic for benchmark results.  This module is pure data and
validation -- it performs no I/O, database access, or deck building.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BenchmarkCommander:
    """A reference commander for regression testing."""

    name: str
    archetype: str  # "aggro", "control", "combo", "midrange", "spellslinger"
    color_identity: list[str]  # e.g. ["B", "R", "G"]
    expected_themes: list[str]  # e.g. ["sacrifice", "aristocrats", "tokens"]
    budget: float  # default budget to test at
    notes: str = ""  # optional notes about what makes this a good benchmark


@dataclass(slots=True)
class BenchmarkResult:
    """Result of running the benchmark suite.

    The ``metrics`` field expects a ``DeckMetrics`` object from
    ``mtg_deck_maker.metrics.comparison`` once that module is available.
    It should expose at least ``category_coverage``, ``curve_smoothness``,
    and ``total_price`` as float attributes.
    """

    commander_name: str
    metrics: Any  # DeckMetrics from comparison.py (not imported to avoid circular deps)
    deck_card_count: int
    warnings: list[str] = field(default_factory=list)


_BENCHMARK_COMMANDERS: list[BenchmarkCommander] = [
    BenchmarkCommander(
        name="Krenko, Mob Boss",
        archetype="aggro",
        color_identity=["R"],
        expected_themes=["goblins", "tokens", "tribal"],
        budget=50.0,
        notes="Mono-red goblin tribal; explosive token generation.",
    ),
    BenchmarkCommander(
        name="Atraxa, Praetors' Voice",
        archetype="midrange",
        color_identity=["W", "U", "B", "G"],
        expected_themes=["proliferate", "counters", "superfriends"],
        budget=50.0,
        notes="Four-color midrange; proliferate and +1/+1 counter synergies.",
    ),
    BenchmarkCommander(
        name="Korvold, Fae-Cursed King",
        archetype="combo",
        color_identity=["B", "R", "G"],
        expected_themes=["sacrifice", "aristocrats", "tokens"],
        budget=50.0,
        notes="Jund sacrifice engine; card draw on permanent sacrifice.",
    ),
    BenchmarkCommander(
        name="Muldrotha, the Gravetide",
        archetype="control",
        color_identity=["B", "U", "G"],
        expected_themes=["graveyard", "self-mill", "recursion"],
        budget=50.0,
        notes="Sultai graveyard value; replays permanents from the graveyard.",
    ),
    BenchmarkCommander(
        name="Talrand, Sky Summoner",
        archetype="spellslinger",
        color_identity=["U"],
        expected_themes=["instants", "sorceries", "tokens"],
        budget=50.0,
        notes="Mono-blue spellslinger; creates drakes on instant/sorcery cast.",
    ),
    BenchmarkCommander(
        name="Teysa Karlov",
        archetype="combo",
        color_identity=["W", "B"],
        expected_themes=["death triggers", "aristocrats", "tokens"],
        budget=50.0,
        notes="Orzhov death-trigger doubler; aristocrats combo enabler.",
    ),
    BenchmarkCommander(
        name="Omnath, Locus of Creation",
        archetype="midrange",
        color_identity=["W", "U", "R", "G"],
        expected_themes=["landfall", "ramp", "elementals"],
        budget=50.0,
        notes="Four-color landfall; triggers on each land entering the battlefield.",
    ),
    BenchmarkCommander(
        name="Kess, Dissident Mage",
        archetype="spellslinger",
        color_identity=["U", "B", "R"],
        expected_themes=["graveyard", "instants", "sorceries"],
        budget=50.0,
        notes="Grixis spellslinger; casts instants/sorceries from graveyard.",
    ),
]

# Thresholds used by validate_benchmark_result.
_MIN_CATEGORY_COVERAGE = 0.80
_MIN_CURVE_SMOOTHNESS = 0.70
_EXPECTED_CARD_COUNT = 100
_BUDGET_TOLERANCE_PCT = 0.10  # 10%


def get_benchmark_commanders() -> list[BenchmarkCommander]:
    """Return the list of benchmark commanders."""
    return list(_BENCHMARK_COMMANDERS)


def validate_benchmark_result(
    result: BenchmarkResult,
    commander: BenchmarkCommander,
) -> list[str]:
    """Validate a benchmark result against expected thresholds.

    Returns a list of warning strings for any issues detected:
    - Missing metrics (None)
    - Category coverage below 80%
    - Curve smoothness below 0.7
    - Total card count != 100
    - Budget exceeded by > 10%
    """
    warnings: list[str] = []

    if result.metrics is None:
        warnings.append(
            f"{commander.name}: metrics are None; benchmark may not have run."
        )
        return warnings

    metrics = result.metrics

    if metrics.category_coverage < _MIN_CATEGORY_COVERAGE:
        warnings.append(
            f"{commander.name}: category coverage {metrics.category_coverage:.2f} "
            f"is below threshold {_MIN_CATEGORY_COVERAGE:.2f}."
        )

    if metrics.curve_smoothness < _MIN_CURVE_SMOOTHNESS:
        warnings.append(
            f"{commander.name}: curve smoothness {metrics.curve_smoothness:.2f} "
            f"is below threshold {_MIN_CURVE_SMOOTHNESS:.2f}."
        )

    if result.deck_card_count != _EXPECTED_CARD_COUNT:
        warnings.append(
            f"{commander.name}: card count is {result.deck_card_count}, "
            f"expected {_EXPECTED_CARD_COUNT}."
        )

    budget_limit = commander.budget * (1 + _BUDGET_TOLERANCE_PCT)
    if metrics.total_price > budget_limit:
        warnings.append(
            f"{commander.name}: total price ${metrics.total_price:.2f} "
            f"exceeds budget ${commander.budget:.2f} by more than "
            f"{_BUDGET_TOLERANCE_PCT:.0%}."
        )

    return warnings
