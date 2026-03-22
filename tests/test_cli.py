"""Tests for the CLI module using Click's CliRunner."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mtg_deck_maker.cli import cli


@pytest.fixture
def runner():
    """Create a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV deck file for testing."""
    content = (
        "Quantity,Card Name,Category,Mana Cost,CMC,Type,Price (USD),Set,Set Code,Notes\n"
        "1,Sol Ring,ramp,{1},1,Artifact,3.00,,,\n"
        "1,Swords to Plowshares,removal,{W},1,Instant,2.00,,,\n"
        "1,Counterspell,counterspell,{U}{U},2,Instant,1.50,,,\n"
    )
    csv_file = tmp_path / "test_deck.csv"
    csv_file.write_text(content)
    return str(csv_file)


def _make_card(name="Test Card", card_id=1, color_identity=None, cmc=2.0, type_line="Creature"):
    """Create a Card object for testing."""
    from mtg_deck_maker.models.card import Card

    return Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line=type_line,
        cmc=cmc,
        color_identity=color_identity or ["W"],
        legal_commander=True,
        id=card_id,
    )


def _make_deck(name="Test Deck"):
    """Create a Deck object for testing."""
    from mtg_deck_maker.models.deck import Deck, DeckCard

    return Deck(
        name=name,
        cards=[
            DeckCard(
                card_id=1, quantity=1, category="commander",
                card_name="Test Commander", cmc=4.0, price=5.0,
            ),
            DeckCard(
                card_id=2, quantity=1, category="ramp",
                card_name="Sol Ring", cmc=1.0, price=3.0,
            ),
        ],
    )


def _mock_db_path():
    """Return a MagicMock Path that reports as existing."""
    path = MagicMock()
    path.exists.return_value = True
    return path


# === Version and Help ===


class TestVersionAndHelp:
    def test_version_and_help(self, runner):
        """--version and --help should work correctly."""
        version_result = runner.invoke(cli, ["--version"])
        assert version_result.exit_code == 0
        assert "mtg-deck" in version_result.output
        assert "0.1.0" in version_result.output

        help_result = runner.invoke(cli, ["--help"])
        assert help_result.exit_code == 0
        assert "MTG Commander Deck Creator" in help_result.output
        for cmd in ["build", "analyze", "upgrade", "advise",
                     "validate", "sync", "search", "config"]:
            assert cmd in help_result.output


# === Command Help ===


class TestCommandHelp:
    @pytest.mark.parametrize(
        "command, expected_text",
        [
            ("build", "commander"),
            ("analyze", "deck_file"),
            ("upgrade", "budget"),
            ("advise", "problem"),
            ("validate", "deck_file"),
            ("sync", "full"),
            ("search", "query"),
            ("config", "show"),
        ],
        ids=["build", "analyze", "upgrade", "advise", "validate", "sync", "search", "config"],
    )
    def test_command_help(self, runner, command, expected_text):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0
        assert expected_text in result.output.lower()


# === Command Execution ===


class TestBuildCommand:
    @patch("mtg_deck_maker.services.build_service.BuildService")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_build_runs_with_options(
        self, mock_db_path, mock_db_cls, mock_build_svc_cls, runner,
    ):
        """build should execute with and without options."""
        from mtg_deck_maker.services.build_service import BuildResult

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_build_svc_cls.return_value.build_from_db.return_value = BuildResult(
            deck=_make_deck("Atraxa Deck"),
        )

        result = runner.invoke(cli, ["build", "Atraxa, Praetors' Voice"])
        assert result.exit_code == 0

        result = runner.invoke(cli, [
            "build", "Atraxa",
            "--budget", "200",
            "--seed", "123",
        ])
        assert result.exit_code == 0


class TestAnalyzeCommand:
    def test_analyze_runs(self, runner, sample_csv):
        result = runner.invoke(cli, ["analyze", sample_csv])
        assert result.exit_code == 0

    def test_analyze_missing_file(self, runner):
        result = runner.invoke(cli, ["analyze", "/nonexistent/file.csv"])
        assert result.exit_code != 0


class TestAdviseCommand:
    def test_advise_runs(self, runner, sample_csv):
        """advise should execute and fall back gracefully without API key."""
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        result = runner.invoke(
            cli,
            ["advise", sample_csv, "--problem", "My deck is too slow"],
            env=env,
        )
        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output


class TestValidateCommand:
    def test_validate_runs(self, runner, sample_csv):
        result = runner.invoke(cli, ["validate", sample_csv])
        assert result.exit_code == 0

    def test_validate_missing_file(self, runner):
        result = runner.invoke(cli, ["validate", "/nonexistent/file.csv"])
        assert result.exit_code != 0


class TestSyncCommand:
    @patch("mtg_deck_maker.services.sync_service.SyncService")
    def test_sync_runs(self, mock_svc_cls, runner):
        from mtg_deck_maker.services.sync_service import SyncResult

        mock_svc_cls.return_value.sync.return_value = SyncResult(
            errors=["No cards in database. Run full sync first: mtg-deck sync --full"]
        )
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "sync" in result.output.lower()

    @patch("mtg_deck_maker.services.sync_service.SyncService")
    def test_sync_full(self, mock_svc_cls, runner):
        from mtg_deck_maker.services.sync_service import SyncResult

        mock_svc_cls.return_value.sync.return_value = SyncResult(
            cards_added=100, printings_added=100, prices_added=300,
            duration_seconds=5.0,
        )
        result = runner.invoke(cli, ["sync", "--full"])
        assert result.exit_code == 0
        assert "complete" in result.output.lower()


class TestSearchCommand:
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_search_runs(
        self, mock_db_path, mock_db_cls, mock_card_repo_cls,
        mock_price_repo_cls, runner,
    ):
        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        sol_ring = _make_card("Sol Ring", 1, [], 1.0, "Artifact")
        mock_card_repo_cls.return_value.search_cards.return_value = [sol_ring]
        mock_price_repo_cls.return_value.get_cheapest_price.return_value = 3.0

        result = runner.invoke(cli, ["search", "Sol Ring"])
        assert result.exit_code == 0
        assert "Sol Ring" in result.output


class TestConfigCommand:
    @pytest.mark.parametrize(
        "args",
        [[], ["--show"]],
        ids=["no_show", "with_show"],
    )
    def test_config(self, runner, args):
        result = runner.invoke(cli, ["config"] + args)
        assert result.exit_code == 0


# === Research Command ===


class TestResearchCommand:
    @patch("mtg_deck_maker.services.research_service.ResearchService")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    @patch("mtg_deck_maker.advisor.llm_provider.get_provider")
    def test_research_rich_format(
        self, mock_get_provider, mock_db_path, mock_db_cls,
        mock_card_repo_cls, mock_research_svc_cls, runner,
    ):
        from mtg_deck_maker.services.research_service import ResearchResult

        mock_provider = MagicMock()
        mock_provider.name = "Fake Provider"
        mock_get_provider.return_value = mock_provider

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        cmd_card = _make_card(
            "Atraxa, Praetors' Voice", 1, ["W", "U", "B", "G"], 4.0,
        )
        mock_card_repo_cls.return_value.get_card_by_name.return_value = cmd_card

        mock_research_svc_cls.return_value.research_commander.return_value = ResearchResult(
            commander_name="Atraxa, Praetors' Voice",
            strategy_overview="Proliferate strategy.",
            key_cards=["Doubling Season", "Deepglow Skate"],
            parse_success=True,
        )

        result = runner.invoke(cli, ["research", "Atraxa, Praetors' Voice"])
        assert result.exit_code == 0
        assert "Strategy Overview" in result.output

    @patch("mtg_deck_maker.services.research_service.ResearchService")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    @patch("mtg_deck_maker.advisor.llm_provider.get_provider")
    def test_research_json_format(
        self, mock_get_provider, mock_db_path, mock_db_cls,
        mock_card_repo_cls, mock_research_svc_cls, runner,
    ):
        from mtg_deck_maker.services.research_service import ResearchResult

        mock_provider = MagicMock()
        mock_provider.name = "Fake Provider"
        mock_get_provider.return_value = mock_provider

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_card_repo_cls.return_value.get_card_by_name.return_value = None

        mock_research_svc_cls.return_value.research_commander.return_value = ResearchResult(
            commander_name="Atraxa",
            strategy_overview="Proliferate.",
            key_cards=["Sol Ring"],
            parse_success=True,
        )

        result = runner.invoke(cli, ["research", "Atraxa", "--format", "json"])
        assert result.exit_code == 0
        assert '"commander"' in result.output
        assert '"strategy_overview"' in result.output

    def test_research_no_provider(self, runner):
        """research should fail gracefully without an API key."""
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
        result = runner.invoke(cli, ["research", "Atraxa"], env=env)
        assert result.exit_code != 0


# === Smart Build Flag ===


class TestBuildSmartFlag:
    @patch("mtg_deck_maker.services.build_service.BuildService")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_smart_no_provider_degrades_gracefully(
        self, mock_db_path, mock_db_cls, mock_build_svc_cls, runner,
    ):
        from mtg_deck_maker.services.build_service import BuildResult

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_build_svc_cls.return_value.build_from_db.return_value = BuildResult(
            deck=_make_deck("Atraxa Deck"),
        )

        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
        result = runner.invoke(cli, ["build", "Atraxa", "--smart"], env=env)
        assert result.exit_code == 0
        call_kwargs = mock_build_svc_cls.return_value.build_from_db.call_args
        assert call_kwargs.kwargs.get("smart") is True


# === Provider and Model Flags ===


class TestProviderAndModelFlags:
    @pytest.mark.parametrize(
        "command",
        ["build", "advise", "research"],
    )
    def test_accepts_provider_and_model_flags(self, runner, command):
        result = runner.invoke(cli, [command, "--help"])
        assert "--provider" in result.output
        assert "--model" in result.output

    @patch("mtg_deck_maker.services.research_service.ResearchService")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    @patch("mtg_deck_maker.advisor.llm_provider.get_provider")
    def test_research_passes_model_to_provider(
        self, mock_get_provider, mock_db_path, mock_db_cls,
        mock_card_repo_cls, mock_research_svc_cls, runner,
    ):
        from mtg_deck_maker.services.research_service import ResearchResult

        mock_provider = MagicMock()
        mock_provider.name = "Fake Provider"
        mock_get_provider.return_value = mock_provider

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_card_repo_cls.return_value.get_card_by_name.return_value = None

        mock_research_svc_cls.return_value.research_commander.return_value = ResearchResult(
            commander_name="Atraxa",
            parse_success=True,
        )

        runner.invoke(cli, [
            "research", "Atraxa",
            "--provider", "anthropic",
            "--model", "claude-opus-4-20250514",
        ])
        mock_get_provider.assert_called_once_with(
            "anthropic", model="claude-opus-4-20250514"
        )
