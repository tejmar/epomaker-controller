"""Config load, verify, and DynaTab capability migration tests."""

import json
from pathlib import Path

import pytest

from epomakercontroller.configs.configs import (
    DEFAULT_MAIN_CONFIG,
    Config,
    ConfigType,
    _migrate_dynatab_capabilities,
    load_main_config,
    verify_main_config,
)
from epomakercontroller.exceptions import ConfigError


def test_default_main_config_has_capabilities() -> None:
    assert "CAPABILITIES" in DEFAULT_MAIN_CONFIG
    assert "per_key_rgb" in DEFAULT_MAIN_CONFIG["CAPABILITIES"]


def test_load_main_config_creates_and_merges(isolated_config_dir: Path) -> None:
    assert not (isolated_config_dir / "config.json").exists()
    cfg = load_main_config()
    assert cfg.type == ConfigType.CONF_MAIN
    assert cfg["CAPABILITIES"] == DEFAULT_MAIN_CONFIG["CAPABILITIES"]
    assert (isolated_config_dir / "config.json").exists()


def test_verify_rejects_unknown_keys(isolated_config_dir: Path) -> None:
    bad = Config(
        ConfigType.CONF_MAIN,
        "virtual",
        data={**DEFAULT_MAIN_CONFIG, "NOT_A_REAL_KEY": 1},
    )
    with pytest.raises(ConfigError, match="Unsupported config entries"):
        verify_main_config(bad)


def test_migrate_dynatab_capabilities() -> None:
    data = {
        **DEFAULT_MAIN_CONFIG,
        "CONF_LAYOUT_PATH": "EpomakerDynaTab75X.json",
        # Start from RT100 defaults (no dynatab_screen)
        "CAPABILITIES": ["per_key_rgb", "rt100_screen"],
    }
    _migrate_dynatab_capabilities(data)
    assert "dynatab_screen" in data["CAPABILITIES"]
    assert "rt100_screen" not in data["CAPABILITIES"]
    assert "per_key_rgb" in data["CAPABILITIES"]


def test_migrate_leaves_non_dynatab_alone() -> None:
    data = {
        **DEFAULT_MAIN_CONFIG,
        "CONF_LAYOUT_PATH": "EpomakerRT100-UK-ISO.json",
        "CAPABILITIES": ["per_key_rgb", "rt100_screen"],
    }
    _migrate_dynatab_capabilities(data)
    assert data["CAPABILITIES"] == ["per_key_rgb", "rt100_screen"]


def test_verify_migrates_dynatab_layout_file(isolated_config_dir: Path) -> None:
    # Simulate an older user config that only swapped layout/keymap paths.
    raw = {
        "VENDOR_ID": 0x3151,
        "PRODUCT_IDS_WIRED": [0x4010],
        "PRODUCT_IDS_24G": [0x4011],
        "USE_WIRELESS": False,
        "DEVICE_DESCRIPTION_REGEX": "ROYUAN .* System Control",
        "CONF_LAYOUT_PATH": "EpomakerDynaTab75X.json",
        "CONF_KEYMAP_PATH": "EpomakerDynaTab75X.json",
    }
    path = isolated_config_dir / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = Config(ConfigType.CONF_MAIN, path.as_posix())
    out = verify_main_config(loaded)
    assert "dynatab_screen" in out["CAPABILITIES"]
    assert "rt100_screen" not in out["CAPABILITIES"]


def test_config_getitem_missing_key_raises() -> None:
    cfg = Config(ConfigType.CONF_MAIN, "virtual", data=dict(DEFAULT_MAIN_CONFIG))
    with pytest.raises(ConfigError, match="not found"):
        _ = cfg["DOES_NOT_EXIST"]
