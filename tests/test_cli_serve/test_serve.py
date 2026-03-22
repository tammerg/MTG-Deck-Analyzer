"""Tests for the ``mtg-deck serve`` CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtg_deck_maker.cli import cli


class TestServeCommand:
    """Tests for the serve command."""

    def test_serve_calls_uvicorn_run(self) -> None:
        mock_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            # uvicorn.run will be called and block, so mock it
            mock_uvicorn.run = MagicMock()
            result = runner.invoke(cli, ["serve"])

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "mtg_deck_maker.api.web.app:create_app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            factory=True,
        )

    def test_serve_custom_host_and_port(self) -> None:
        mock_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            mock_uvicorn.run = MagicMock()
            result = runner.invoke(cli, ["serve", "--host", "0.0.0.0", "--port", "3000"])

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "mtg_deck_maker.api.web.app:create_app",
            host="0.0.0.0",
            port=3000,
            reload=False,
            factory=True,
        )

    def test_serve_reload_flag(self) -> None:
        mock_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            mock_uvicorn.run = MagicMock()
            result = runner.invoke(cli, ["serve", "--reload"])

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "mtg_deck_maker.api.web.app:create_app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            factory=True,
        )

    def test_serve_prints_startup_message(self) -> None:
        mock_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            mock_uvicorn.run = MagicMock()
            result = runner.invoke(cli, ["serve", "--port", "9000"])

        assert "http://127.0.0.1:9000" in result.output

    def test_serve_missing_uvicorn_exits_with_error(self) -> None:
        runner = CliRunner()
        with patch.dict("sys.modules", {"uvicorn": None}):
            result = runner.invoke(cli, ["serve"])

        assert result.exit_code != 0
