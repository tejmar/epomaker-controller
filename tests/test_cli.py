"""CLI smoke tests using Click's CliRunner (no device required)."""

from click.testing import CliRunner

from epomakercontroller.cli import cli


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
