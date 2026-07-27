"""CLI smoke tests using Click's CliRunner (no device required)."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from epomakercontroller.cli import cli, open_controller


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "set-keys" in result.output
    assert "upload-image" in result.output


def test_show_keymap_filter(main_config, monkeypatch) -> None:
    # Ensure CLI uses isolated/default package config already loaded at import
    # is fine; show-keymap only needs dry_run controller + keymap JSON.
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["show-keymap", "--filter", "enter"])
    assert result.exit_code == 0
    assert "ENTER" in result.output.upper() or "enter" in result.output.lower()


def test_open_controller_dry_run_context(main_config, monkeypatch) -> None:
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    with open_controller(dry_run=True) as ctl:
        assert ctl.dry_run is True
    assert ctl.device is None


def test_send_time_uses_open_controller(main_config, monkeypatch) -> None:
    """CLI path should open/close via helper without leaking try/finally noise."""
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    mock_ctl = MagicMock()
    mock_ctl.open_device.return_value = True
    # Make ``with controller:`` behave like EpomakerController context manager.
    mock_ctl.__enter__.return_value = mock_ctl
    mock_ctl.__exit__.side_effect = lambda *a: mock_ctl.close_device()

    with patch("epomakercontroller.cli.EpomakerController", return_value=mock_ctl):
        runner = CliRunner()
        result = runner.invoke(cli, ["send-time"])

    assert result.exit_code == 0, result.output
    mock_ctl.open_device.assert_called_once()
    mock_ctl.send_time.assert_called_once()
    mock_ctl.close_device.assert_called()
    assert "Time sent successfully" in result.output
