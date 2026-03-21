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
    def test_version(self, runner):
        """--version should print the version string."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "mtg-deck" in result.output
        assert "0.1.0" in result.output

    def test_help(self, runner):
        """--help should print usage information."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "MTG Commander Deck Creator" in result.output

    def test_help_lists_commands(self, runner):
        """--help should list all available commands."""
        result = runner.invoke(cli, ["--help"])
        for cmd in ["build", "analyze", "upgrade", "advise",
                     "validate", "sync", "search", "config"]:
            assert cmd in result.output


# === Command Existence and Help ===


class TestCommandHelp:
    def test_build_help(self, runner):
        """build --help should show build command usage."""
        result = runner.invoke(cli, ["build", "--help"])
        assert result.exit_code == 0
        assert "commander" in result.output.lower()

    def test_analyze_help(self, runner):
        """analyze --help should show analyze command usage."""
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "deck_file" in result.output.lower()

    def test_upgrade_help(self, runner):
        """upgrade --help should show upgrade command usage."""
        result = runner.invoke(cli, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "budget" in result.output.lower()

    def test_advise_help(self, runner):
        """advise --help should show advise command usage."""
        result = runner.invoke(cli, ["advise", "--help"])
        assert result.exit_code == 0
        assert "problem" in result.output.lower()

    def test_validate_help(self, runner):
        """validate --help should show validate command usage."""
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "deck_file" in result.output.lower()

    def test_sync_help(self, runner):
        """sync --help should show sync command usage."""
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "full" in result.output.lower()

    def test_search_help(self, runner):
        """search --help should show search command usage."""
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_config_help(self, runner):
        """config --help should show config command usage."""
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output.lower()


# === Command Execution ===


class TestBuildCommand:
    @patch("mtg_deck_maker.services.build_service.BuildService")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_build_runs(
        self, mock_db_path, mock_db_cls, mock_build_svc_cls, runner,
    ):
        """build should execute without crashing."""
        from mtg_deck_maker.services.build_service import BuildResult

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_build_svc_cls.return_value.build_from_db.return_value = BuildResult(
            deck=_make_deck("Atraxa Deck"),
        )

        result = runner.invoke(cli, ["build", "Atraxa, Praetors' Voice"])
        assert result.exit_code == 0

    @patch("mtg_deck_maker.services.build_service.BuildService")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_build_with_options(
        self, mock_db_path, mock_db_cls, mock_build_svc_cls, runner,
    ):
        """build should accept all options."""
        from mtg_deck_maker.services.build_service import BuildResult

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_build_svc_cls.return_value.build_from_db.return_value = BuildResult(
            deck=_make_deck("Atraxa Deck"),
        )

        result = runner.invoke(cli, [
            "build", "Atraxa",
            "--budget", "200",
            "--seed", "123",
        ])
        assert result.exit_code == 0


class TestAnalyzeCommand:
    def test_analyze_runs(self, runner, sample_csv):
        """analyze should execute on a valid CSV file."""
        result = runner.invoke(cli, ["analyze", sample_csv])
        assert result.exit_code == 0

    def test_analyze_missing_file(self, runner):
        """analyze should fail on missing file."""
        result = runner.invoke(cli, ["analyze", "/nonexistent/file.csv"])
        assert result.exit_code != 0


class TestUpgradeCommand:
    @patch("mtg_deck_maker.services.upgrade_service.UpgradeService")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_upgrade_runs(
        self, mock_db_path, mock_db_cls, mock_card_repo_cls,
        mock_price_repo_cls, mock_upgrade_svc_cls, runner, sample_csv,
    ):
        """upgrade should execute on a valid CSV file."""
        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        sol_ring = _make_card("Sol Ring", 1, [], 1.0, "Artifact")
        swords = _make_card("Swords to Plowshares", 2, ["W"], 1.0, "Instant")
        counterspell = _make_card("Counterspell", 3, ["U"], 2.0, "Instant")

        mock_card_repo_cls.return_value.get_card_by_name.side_effect = lambda name: {
            "Sol Ring": sol_ring,
            "Swords to Plowshares": swords,
            "Counterspell": counterspell,
        }.get(name)
        mock_card_repo_cls.return_value.get_commander_legal_cards.return_value = [
            sol_ring, swords, counterspell,
        ]
        mock_price_repo_cls.return_value.get_cheapest_prices.return_value = {
            1: 2.0, 2: 2.0, 3: 2.0,
        }

        mock_upgrade_svc_cls.return_value.recommend_from_cards.return_value = (
            MagicMock(), [],
        )

        result = runner.invoke(cli, ["upgrade", sample_csv])
        assert result.exit_code == 0

    @patch("mtg_deck_maker.services.upgrade_service.UpgradeService")
    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_upgrade_with_options(
        self, mock_db_path, mock_db_cls, mock_card_repo_cls,
        mock_price_repo_cls, mock_upgrade_svc_cls, runner, sample_csv,
    ):
        """upgrade should accept budget and focus options."""
        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        sol_ring = _make_card("Sol Ring", 1, [], 1.0, "Artifact")

        mock_card_repo_cls.return_value.get_card_by_name.return_value = sol_ring
        mock_card_repo_cls.return_value.get_commander_legal_cards.return_value = [sol_ring]
        mock_price_repo_cls.return_value.get_cheapest_prices.return_value = {1: 3.0}

        mock_upgrade_svc_cls.return_value.recommend_from_cards.return_value = (
            MagicMock(), [],
        )

        result = runner.invoke(cli, [
            "upgrade", sample_csv,
            "--budget", "25",
            "--focus", "card_draw",
        ])
        assert result.exit_code == 0


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

    def test_advise_missing_file(self, runner):
        """advise should fail on missing file."""
        result = runner.invoke(cli, ["advise", "/nonexistent/file.csv"])
        assert result.exit_code != 0


class TestValidateCommand:
    def test_validate_runs(self, runner, sample_csv):
        """validate should execute on a valid CSV file."""
        result = runner.invoke(cli, ["validate", sample_csv])
        assert result.exit_code == 0

    def test_validate_missing_file(self, runner):
        """validate should fail on missing file."""
        result = runner.invoke(cli, ["validate", "/nonexistent/file.csv"])
        assert result.exit_code != 0


class TestSyncCommand:
    @patch("mtg_deck_maker.services.sync_service.SyncService")
    def test_sync_runs(self, mock_svc_cls, runner):
        """sync should execute and show sync status."""
        from mtg_deck_maker.services.sync_service import SyncResult

        mock_svc_cls.return_value.sync.return_value = SyncResult(
            errors=["No cards in database. Run full sync first: mtg-deck sync --full"]
        )
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "sync" in result.output.lower()

    @patch("mtg_deck_maker.services.sync_service.SyncService")
    def test_sync_full(self, mock_svc_cls, runner):
        """sync --full should execute."""
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
        """search should execute with a query."""
        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        sol_ring = _make_card("Sol Ring", 1, [], 1.0, "Artifact")
        mock_card_repo_cls.return_value.search_cards.return_value = [sol_ring]
        mock_price_repo_cls.return_value.get_cheapest_price.return_value = 3.0

        result = runner.invoke(cli, ["search", "Sol Ring"])
        assert result.exit_code == 0
        assert "Sol Ring" in result.output

    @patch("mtg_deck_maker.db.price_repo.PriceRepository")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_search_with_filters(
        self, mock_db_path, mock_db_cls, mock_card_repo_cls,
        mock_price_repo_cls, runner,
    ):
        """search should accept filter options."""
        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        bolt = _make_card("Lightning Bolt", 1, ["R"], 1.0, "Instant")
        mock_card_repo_cls.return_value.search_cards.return_value = [bolt]
        mock_price_repo_cls.return_value.get_cheapest_price.return_value = 1.0

        result = runner.invoke(cli, [
            "search", "Lightning",
            "--color", "R",
            "--type", "Instant",
        ])
        assert result.exit_code == 0


class TestConfigCommand:
    def test_config_no_show(self, runner):
        """config without --show should print guidance."""
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0

    def test_config_show(self, runner):
        """config --show should display configuration."""
        result = runner.invoke(cli, ["config", "--show"])
        assert result.exit_code == 0


# === Research Command ===


class TestResearchCommand:
    def test_research_help(self, runner):
        """research --help should show research command usage."""
        result = runner.invoke(cli, ["research", "--help"])
        assert result.exit_code == 0
        assert "commander" in result.output.lower()
        assert "--provider" in result.output
        assert "--model" in result.output
        assert "--format" in result.output

    @patch("mtg_deck_maker.services.research_service.ResearchService")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    @patch("mtg_deck_maker.advisor.llm_provider.get_provider")
    def test_research_rich_format(
        self, mock_get_provider, mock_db_path, mock_db_cls,
        mock_card_repo_cls, mock_research_svc_cls, runner,
    ):
        """research should display rich output by default."""
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
        """research --format json should output JSON."""
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

    @patch("mtg_deck_maker.services.research_service.ResearchService")
    @patch("mtg_deck_maker.db.card_repo.CardRepository")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    @patch("mtg_deck_maker.advisor.llm_provider.get_provider")
    def test_research_md_format(
        self, mock_get_provider, mock_db_path, mock_db_cls,
        mock_card_repo_cls, mock_research_svc_cls, runner,
    ):
        """research --format md should output markdown."""
        from mtg_deck_maker.services.research_service import ResearchResult

        mock_provider = MagicMock()
        mock_provider.name = "Fake Provider"
        mock_get_provider.return_value = mock_provider

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_card_repo_cls.return_value.get_card_by_name.return_value = None

        mock_research_svc_cls.return_value.research_commander.return_value = ResearchResult(
            commander_name="Atraxa",
            strategy_overview="Go wide.",
            key_cards=["Sol Ring"],
            parse_success=True,
        )

        result = runner.invoke(cli, ["research", "Atraxa", "--format", "md"])
        assert result.exit_code == 0
        assert "# Atraxa Research" in result.output

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
        """build --smart should delegate to build_from_db with smart=True."""
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
        # Verify smart=True was passed
        call_kwargs = mock_build_svc_cls.return_value.build_from_db.call_args
        assert call_kwargs.kwargs.get("smart") is True

    @patch("mtg_deck_maker.services.build_service.BuildService")
    @patch("mtg_deck_maker.db.database.Database")
    @patch("mtg_deck_maker.cli._get_db_path")
    def test_smart_with_provider(
        self, mock_db_path, mock_db_cls, mock_build_svc_cls, runner,
    ):
        """build --smart --provider should pass provider flag to build_from_db."""
        from mtg_deck_maker.services.build_service import BuildResult

        mock_db_path.return_value = _mock_db_path()
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_build_svc_cls.return_value.build_from_db.return_value = BuildResult(
            deck=_make_deck("Atraxa Deck"),
        )

        result = runner.invoke(cli, ["build", "Atraxa", "--smart", "--provider", "openai"])
        assert result.exit_code == 0
        call_kwargs = mock_build_svc_cls.return_value.build_from_db.call_args
        assert call_kwargs.kwargs.get("smart") is True
        assert call_kwargs.kwargs.get("provider") == "openai"


# === Provider and Model Flags ===


class TestProviderAndModelFlags:
    def test_build_accepts_provider_flag(self, runner):
        """build --provider should be accepted without error."""
        result = runner.invoke(cli, ["build", "--help"])
        assert "--provider" in result.output
        assert "openai" in result.output
        assert "anthropic" in result.output

    def test_build_accepts_model_flag(self, runner):
        """build --model should be accepted without error."""
        result = runner.invoke(cli, ["build", "--help"])
        assert "--model" in result.output

    def test_advise_accepts_provider_flag(self, runner):
        """advise --provider should be accepted without error."""
        result = runner.invoke(cli, ["advise", "--help"])
        assert "--provider" in result.output

    def test_advise_accepts_model_flag(self, runner):
        """advise --model should be accepted without error."""
        result = runner.invoke(cli, ["advise", "--help"])
        assert "--model" in result.output

    def test_research_accepts_provider_flag(self, runner):
        """research --provider should be accepted without error."""
        result = runner.invoke(cli, ["research", "--help"])
        assert "--provider" in result.output

    def test_research_accepts_model_flag(self, runner):
        """research --model should be accepted without error."""
        result = runner.invoke(cli, ["research", "--help"])
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
        """research --model should pass the model override to get_provider."""
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
