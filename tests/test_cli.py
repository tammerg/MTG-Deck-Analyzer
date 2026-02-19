"""Tests for the CLI module using Click's CliRunner."""

from __future__ import annotations

import os
import tempfile

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
        assert "build" in result.output
        assert "analyze" in result.output
        assert "upgrade" in result.output
        assert "advise" in result.output
        assert "validate" in result.output
        assert "sync" in result.output
        assert "search" in result.output
        assert "config" in result.output


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
    def test_build_runs(self, runner):
        """build should execute without crashing."""
        result = runner.invoke(cli, ["build", "Atraxa, Praetors' Voice"])
        assert result.exit_code == 0

    def test_build_with_options(self, runner):
        """build should accept all options."""
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
    def test_upgrade_runs(self, runner, sample_csv):
        """upgrade should execute on a valid CSV file."""
        result = runner.invoke(cli, ["upgrade", sample_csv])
        assert result.exit_code == 0

    def test_upgrade_with_options(self, runner, sample_csv):
        """upgrade should accept budget and focus options."""
        result = runner.invoke(cli, [
            "upgrade", sample_csv,
            "--budget", "25",
            "--focus", "card_draw",
        ])
        assert result.exit_code == 0


class TestAdviseCommand:
    def test_advise_runs(self, runner, sample_csv):
        """advise should execute and fall back gracefully without API key."""
        # Ensure no API key is set
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
    def test_sync_runs(self, runner):
        """sync should execute and show sync status."""
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "sync" in result.output.lower()

    def test_sync_full(self, runner):
        """sync --full should execute."""
        result = runner.invoke(cli, ["sync", "--full"])
        assert result.exit_code == 0


class TestSearchCommand:
    def test_search_runs(self, runner):
        """search should execute with a query."""
        result = runner.invoke(cli, ["search", "Sol Ring"])
        assert result.exit_code == 0

    def test_search_with_filters(self, runner):
        """search should accept filter options."""
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
