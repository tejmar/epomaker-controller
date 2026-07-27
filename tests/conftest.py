"""Shared fixtures for Epomaker controller tests (no hardware required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from epomakercontroller.configs.configs import DEFAULT_MAIN_CONFIG, Config, ConfigType


@pytest.fixture
def isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point main-config load/save at a temporary directory."""
    monkeypatch.setattr(
        "epomakercontroller.configs.configs.get_main_config_directory",
        lambda: tmp_path,
    )
    return tmp_path


@pytest.fixture
def main_config(isolated_config_dir: Path) -> Config:
    """A verified main Config written under the isolated config directory."""
    from epomakercontroller.configs.configs import load_main_config

    return load_main_config()


@pytest.fixture
def dynatab_main_config(isolated_config_dir: Path) -> Config:
    """Main config forced to DynaTab layout/keymap + capabilities."""
    data = {
        **DEFAULT_MAIN_CONFIG,
        "CONF_LAYOUT_PATH": "EpomakerDynaTab75X.json",
        "CONF_KEYMAP_PATH": "EpomakerDynaTab75X.json",
        "CAPABILITIES": ["per_key_rgb", "dynatab_screen"],
    }
    config_file = isolated_config_dir / "config.json"
    config_file.write_text(json.dumps(data), encoding="utf-8")
    return Config(ConfigType.CONF_MAIN, config_file.as_posix(), data=data)
