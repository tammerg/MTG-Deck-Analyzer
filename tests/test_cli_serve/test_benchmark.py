"""Tests for the ``mtg-deck benchmark`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtg_deck_maker.cli import cli
from mtg_deck_maker.metrics.benchmark import get_benchmark_commanders
from mtg_deck_maker.models.deck import Deck, DeckCard

# Patch targets use the source module paths because the benchmark command
# imports them locally inside the function body.
_DB_PATH = "mtg_deck_maker.db.database.Database"
_BUILD_SVC_PATH = "mtg_deck_maker.services.build_service.BuildService"
_COMPUTE_METRICS_PATH = "mtg_deck_maker.metrics.comparison.compute_metrics"
_VALIDATE_PATH = "mtg_deck_maker.metrics.benchmark.validate_benchmark_result"


def _make_mock_deck(name: str = "Test Deck", card_count: int = 100) -> Deck:
    """Create a mock deck with the given number of cards."""
    cards = [
        DeckCard(
            card_id=i,
            quantity=1,
            category="creature" if i % 3 == 0 else "spell",
            card_name=f"Card {i}",
            cmc=float(i % 6),
            price=0.50,
        )
        for i in range(card_count)
    ]
    return Deck(name=name, cards=cards)


def _make_mock_build_result(deck: Deck | None = None) -> MagicMock:
    """Create a mock BuildResult."""
    result = MagicMock()
    result.deck = deck or _make_mock_deck()
    result.warnings = []
    result.csv_output = None
    return result


def _make_mock_metrics() -> MagicMock:
    """Create a mock DeckMetrics with all metric sub-results."""
    metrics = MagicMock()
    metrics.deck_name = "Test Deck"
    metrics.total_cards = 100
    metrics.total_price = 45.00
    metrics.average_cmc = 2.8

    # Category coverage
    metrics.category_coverage = MagicMock()
    metrics.category_coverage.overall_pct = 0.85

    # Curve smoothness
    metrics.curve_smoothness = MagicMock()
    metrics.curve_smoothness.smoothness = 0.78

    # EDHREC overlap
    metrics.edhrec_overlap = MagicMock()
    metrics.edhrec_overlap.overlap_pct = 0.42

    # Budget efficiency
    metrics.budget_efficiency = MagicMock()
    metrics.budget_efficiency.total_spent = 45.00
    metrics.budget_efficiency.quality_per_dollar = 1.5

    return metrics


def _patch_db_exists(exists: bool = True):
    """Return a patch that controls whether the DB path exists."""
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = exists
    return patch("mtg_deck_maker.cli._get_db_path", return_value=mock_path)


class TestBenchmarkCommand:
    """Tests for the benchmark CLI command."""

    def test_benchmark_command_exists(self) -> None:
        """The benchmark command is registered and callable."""
        runner = CliRunner()
        result = runner.invoke(cli, ["benchmark", "--help"])
        assert result.exit_code == 0
        assert "Run benchmark suite" in result.output

    def test_benchmark_successful_run(self) -> None:
        """All commanders build and pass validation."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        assert "passed" in result.output
        assert "0 failed" in result.output

    def test_benchmark_commander_build_failure(self) -> None:
        """One commander fails to build; others continue."""
        from mtg_deck_maker.services.build_service import BuildServiceError

        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()

        call_count = 0
        commanders = get_benchmark_commanders()

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BuildServiceError("Commander not found")
            return mock_result

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.side_effect = side_effect
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        assert "failed to build" in result.output
        # Other commanders should still be processed
        assert f"{len(commanders) - 1} passed" in result.output
        assert "1 failed" in result.output

    def test_benchmark_save_writes_json(self, tmp_path: Path) -> None:
        """--save flag writes valid JSON to the specified path."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        save_file = tmp_path / "results.json"

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark", "--save", str(save_file)])

        assert result.exit_code == 0
        assert save_file.exists()
        data = json.loads(save_file.read_text())
        assert "timestamp" in data
        assert "commanders" in data

    def test_benchmark_budget_override(self) -> None:
        """--budget flag overrides each commander's default budget."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark", "--budget", "75.0"])

        assert result.exit_code == 0
        # Verify all calls used the overridden budget
        for call in mock_svc_cls.return_value.build_from_db.call_args_list:
            assert call.kwargs["budget"] == 75.0

    def test_benchmark_output_contains_all_commanders(self) -> None:
        """Output references every benchmark commander via build calls."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        commanders = get_benchmark_commanders()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        # Verify each commander was passed to build_from_db
        called_names = [
            call.kwargs["commander_name"]
            for call in mock_svc_cls.return_value.build_from_db.call_args_list
        ]
        for cmd in commanders:
            assert cmd.name in called_names

    def test_benchmark_warnings_displayed(self) -> None:
        """Warnings from validation are shown in output."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        warning_msg = "category coverage 0.50 is below threshold"

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[warning_msg]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        assert warning_msg in result.output

    def test_benchmark_no_database_shows_error(self) -> None:
        """Missing database exits with an error message."""
        with _patch_db_exists(False):
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code != 0
        assert "No card database found" in result.output

    def test_benchmark_json_structure(self, tmp_path: Path) -> None:
        """JSON output has the correct structure with all expected fields."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        save_file = tmp_path / "bench.json"
        commanders = get_benchmark_commanders()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark", "--save", str(save_file)])

        assert result.exit_code == 0
        data = json.loads(save_file.read_text())

        assert "timestamp" in data
        assert "commanders" in data
        assert len(data["commanders"]) == len(commanders)

        for cmd in commanders:
            entry = data["commanders"][cmd.name]
            assert "archetype" in entry
            assert "card_count" in entry
            assert "total_price" in entry
            assert "category_coverage" in entry
            assert "curve_smoothness" in entry
            assert "edhrec_overlap" in entry
            assert "warnings" in entry
            assert isinstance(entry["warnings"], list)

    def test_benchmark_iterates_all_commanders(self) -> None:
        """build_from_db is called once per benchmark commander."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        commanders = get_benchmark_commanders()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        assert mock_svc_cls.return_value.build_from_db.call_count == len(commanders)

    def test_benchmark_uses_commander_default_budget(self) -> None:
        """Without --budget, each commander uses its own configured budget."""
        mock_deck = _make_mock_deck()
        mock_result = _make_mock_build_result(mock_deck)
        mock_metrics = _make_mock_metrics()
        commanders = get_benchmark_commanders()

        with (
            _patch_db_exists(True),
            patch(_DB_PATH),
            patch(_BUILD_SVC_PATH) as mock_svc_cls,
            patch(_COMPUTE_METRICS_PATH, return_value=mock_metrics),
            patch(_VALIDATE_PATH, return_value=[]),
        ):
            mock_svc_cls.return_value.build_from_db.return_value = mock_result
            runner = CliRunner()
            result = runner.invoke(cli, ["benchmark"])

        assert result.exit_code == 0
        calls = mock_svc_cls.return_value.build_from_db.call_args_list
        for i, call in enumerate(calls):
            assert call.kwargs["budget"] == commanders[i].budget
