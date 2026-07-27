"""Tests for the keyboard model registry and CLI."""

from click.testing import CliRunner

from epomakercontroller.cli import cli
from epomakercontroller.configs.configs import DEFAULT_MAIN_CONFIG, Config, ConfigType
from epomakercontroller.configs.models import (
    apply_model,
    get_model,
    list_models,
    match_model,
)
from epomakercontroller.exceptions import ConfigError
import pytest


def test_list_models_includes_known_ids() -> None:
    ids = {m.id for m in list_models()}
    assert ids == {"rt100", "dynatab75x", "ep64", "gamakay-tk68-he"}


def test_get_model_case_insensitive() -> None:
    assert get_model("DynaTab75X").id == "dynatab75x"


def test_get_model_unknown_raises() -> None:
    with pytest.raises(ConfigError, match="Unknown model"):
        get_model("not-a-keyboard")


def test_apply_model_updates_paths_and_caps(isolated_config_dir, main_config) -> None:
    out = apply_model(main_config, "dynatab75x", save=True)
    assert out["CONF_LAYOUT_PATH"] == "EpomakerDynaTab75X.json"
    assert out["CONF_KEYMAP_PATH"] == "EpomakerDynaTab75X.json"
    assert out["CAPABILITIES"] == ["per_key_rgb", "dynatab_screen"]
    # VID and other fields preserved
    assert out["VENDOR_ID"] == DEFAULT_MAIN_CONFIG["VENDOR_ID"]
    saved = (isolated_config_dir / "config.json").read_text(encoding="utf-8")
    assert "dynatab_screen" in saved


def test_match_model_after_apply(main_config) -> None:
    applied = apply_model(main_config, "ep64", save=False)
    matched = match_model(applied)
    assert matched is not None
    assert matched.id == "ep64"


def test_match_model_custom_paths() -> None:
    cfg = Config(
        ConfigType.CONF_MAIN,
        "virtual",
        data={
            **DEFAULT_MAIN_CONFIG,
            "CONF_LAYOUT_PATH": "CustomLayout.json",
            "CONF_KEYMAP_PATH": "CustomKeymap.json",
        },
    )
    assert match_model(cfg) is None


def test_cli_models_list(isolated_config_dir, main_config, monkeypatch) -> None:
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["models", "list"])
    assert result.exit_code == 0
    assert "dynatab75x" in result.output
    assert "rt100" in result.output


def test_cli_models_set_and_show(isolated_config_dir, main_config, monkeypatch) -> None:
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["models", "set", "dynatab75x"])
    assert result.exit_code == 0
    assert "dynatab75x" in result.output

    result = runner.invoke(cli, ["models", "show"])
    assert result.exit_code == 0
    assert "dynatab75x" in result.output
    assert "dynatab_screen" in result.output


def test_cli_models_set_unknown(isolated_config_dir, main_config, monkeypatch) -> None:
    monkeypatch.setattr("epomakercontroller.cli.CONFIG_MAIN", main_config)
    runner = CliRunner()
    result = runner.invoke(cli, ["models", "set", "nope"])
    assert result.exit_code != 0
