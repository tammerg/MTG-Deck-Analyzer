"""Tests for benchmark commander suite and validation logic."""

from __future__ import annotations

from mtg_deck_maker.metrics.benchmark import (
    BenchmarkCommander,
    BenchmarkResult,
    get_benchmark_commanders,
    validate_benchmark_result,
)

VALID_COLORS = {"W", "U", "B", "R", "G"}

REQUIRED_ARCHETYPES = {"aggro", "control", "combo", "midrange", "spellslinger"}


class TestGetBenchmarkCommanders:
    """Verify the benchmark commander list meets structural requirements."""

    def test_returns_at_least_eight_commanders(self) -> None:
        commanders = get_benchmark_commanders()
        assert len(commanders) >= 8

    def test_all_archetypes_covered(self) -> None:
        commanders = get_benchmark_commanders()
        archetypes_present = {c.archetype for c in commanders}
        assert REQUIRED_ARCHETYPES.issubset(archetypes_present)

    def test_color_identity_uses_only_wubrg(self) -> None:
        commanders = get_benchmark_commanders()
        for commander in commanders:
            assert len(commander.color_identity) > 0, (
                f"{commander.name} has empty color identity"
            )
            for color in commander.color_identity:
                assert color in VALID_COLORS, (
                    f"{commander.name} has invalid color '{color}'"
                )

    def test_each_commander_has_expected_themes(self) -> None:
        commanders = get_benchmark_commanders()
        for commander in commanders:
            assert len(commander.expected_themes) > 0, (
                f"{commander.name} has no expected themes"
            )

    def test_each_commander_has_positive_budget(self) -> None:
        commanders = get_benchmark_commanders()
        for commander in commanders:
            assert commander.budget > 0, (
                f"{commander.name} has non-positive budget"
            )

    def test_commander_names_are_unique(self) -> None:
        commanders = get_benchmark_commanders()
        names = [c.name for c in commanders]
        assert len(names) == len(set(names))

    def test_returns_list_of_benchmark_commanders(self) -> None:
        commanders = get_benchmark_commanders()
        assert isinstance(commanders, list)
        for c in commanders:
            assert isinstance(c, BenchmarkCommander)


class TestBenchmarkCommanderDataclass:
    """Verify BenchmarkCommander uses slots and has expected defaults."""

    def test_slots_enabled(self) -> None:
        assert hasattr(BenchmarkCommander, "__slots__")

    def test_notes_default_empty(self) -> None:
        commander = BenchmarkCommander(
            name="Test Commander",
            archetype="aggro",
            color_identity=["R"],
            expected_themes=["tokens"],
            budget=50.0,
        )
        assert commander.notes == ""

    def test_fields_stored_correctly(self) -> None:
        commander = BenchmarkCommander(
            name="Krenko, Mob Boss",
            archetype="aggro",
            color_identity=["R"],
            expected_themes=["goblins", "tokens"],
            budget=50.0,
            notes="Mono-red goblin tribal",
        )
        assert commander.name == "Krenko, Mob Boss"
        assert commander.archetype == "aggro"
        assert commander.color_identity == ["R"]
        assert commander.expected_themes == ["goblins", "tokens"]
        assert commander.budget == 50.0
        assert commander.notes == "Mono-red goblin tribal"


class TestBenchmarkResultDataclass:
    """Verify BenchmarkResult dataclass basics."""

    def test_slots_enabled(self) -> None:
        assert hasattr(BenchmarkResult, "__slots__")

    def test_construction_with_none_metrics(self) -> None:
        result = BenchmarkResult(
            commander_name="Test",
            metrics=None,
            deck_card_count=100,
            warnings=[],
        )
        assert result.metrics is None
        assert result.deck_card_count == 100
        assert result.warnings == []


class TestValidateBenchmarkResult:
    """Verify validation catches threshold violations."""

    def _make_commander(self, budget: float = 50.0) -> BenchmarkCommander:
        return BenchmarkCommander(
            name="Test Commander",
            archetype="aggro",
            color_identity=["R"],
            expected_themes=["tokens"],
            budget=budget,
        )

    def test_clean_result_returns_no_warnings(self) -> None:
        """A result that meets all thresholds produces no warnings."""
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.90, curve_smoothness=0.80, total_price=45.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert warnings == []

    def test_catches_low_category_coverage(self) -> None:
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.70, curve_smoothness=0.80, total_price=45.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert any("category coverage" in w.lower() for w in warnings)

    def test_catches_low_curve_smoothness(self) -> None:
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.90, curve_smoothness=0.50, total_price=45.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert any("curve smoothness" in w.lower() for w in warnings)

    def test_catches_wrong_card_count(self) -> None:
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.90, curve_smoothness=0.80, total_price=45.0),
            deck_card_count=95,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert any("card count" in w.lower() for w in warnings)

    def test_catches_over_budget(self) -> None:
        commander = self._make_commander(budget=50.0)
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.90, curve_smoothness=0.80, total_price=60.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert any("budget" in w.lower() for w in warnings)

    def test_budget_within_ten_percent_is_ok(self) -> None:
        """Budget exceeded by exactly 10% should not trigger a warning."""
        commander = self._make_commander(budget=50.0)
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.90, curve_smoothness=0.80, total_price=55.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert not any("budget" in w.lower() for w in warnings)

    def test_none_metrics_returns_warning(self) -> None:
        """If metrics are None, validation should warn about missing metrics."""
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=None,
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert any("metrics" in w.lower() for w in warnings)

    def test_multiple_violations_return_multiple_warnings(self) -> None:
        commander = self._make_commander(budget=50.0)
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.50, curve_smoothness=0.30, total_price=70.0),
            deck_card_count=85,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert len(warnings) >= 4

    def test_boundary_coverage_exactly_at_threshold(self) -> None:
        """Coverage of exactly 0.80 should not trigger a warning."""
        commander = self._make_commander()
        result = BenchmarkResult(
            commander_name="Test Commander",
            metrics=_FakeMetrics(category_coverage=0.80, curve_smoothness=0.70, total_price=50.0),
            deck_card_count=100,
            warnings=[],
        )
        warnings = validate_benchmark_result(result, commander)
        assert warnings == []


class _FakeMetrics:
    """Stand-in for DeckMetrics to avoid importing from comparison.py."""

    def __init__(
        self,
        category_coverage: float,
        curve_smoothness: float,
        total_price: float,
    ) -> None:
        self.category_coverage = category_coverage
        self.curve_smoothness = curve_smoothness
        self.total_price = total_price
