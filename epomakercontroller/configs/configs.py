from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any

from importlib.resources import files

from ..exceptions import ConfigError


class ConfigType(Enum):
    CONF_MAIN = 0
    CONF_LAYOUT = 1
    CONF_KEYMAP = 2


DEFAULT_MAIN_CONFIG = {
    "VENDOR_ID": 0x3151,
    "PRODUCT_IDS_WIRED": [0x4010, 0x4015],
    "PRODUCT_IDS_24G": [0x4011, 0x4016],
    "USE_WIRELESS": False,
    "DEVICE_DESCRIPTION_REGEX": "ROYUAN .* System Control",
    # The file will be looked for in the install location first, otherwise use a full filepath
    "CONF_LAYOUT_PATH": "EpomakerRT100-UK-ISO.json",
    "CONF_KEYMAP_PATH": "EpomakerRT100.json",
    # Model feature flags: per_key_rgb, rt100_screen, dynatab_screen
    "CAPABILITIES": ["per_key_rgb", "rt100_screen"],
}


@dataclass
class Config:
    type: ConfigType
    filename: str
    data: dict[Any, Any] | None = None

    def __post_init__(self) -> None:
        # If data not set manually, load it from the filename
        if not self.data:
            with open(self._find_config_path(self.filename, self.type), "r", encoding="utf-8") as f:
                self.data = json.load(f)
                return

        if self.data is None:
            raise ConfigError("Config has no data")

    @staticmethod
    def _find_config_path(filename: str, type: ConfigType) -> str:
        # If the filename exists, use that
        if os.path.exists(filename):
            return os.path.realpath(filename)

        # Otherwise resolve the file from the installed package data.
        # importlib.resources.files() is the 3.9+ replacement for the
        # deprecated/removed importlib.resources.path().
        if type == ConfigType.CONF_LAYOUT:
            return str(files("epomakercontroller.configs.layouts").joinpath(filename))
        if type == ConfigType.CONF_KEYMAP:
            return str(files("epomakercontroller.configs.keymaps").joinpath(filename))

        raise ConfigError(f"Unsupported ConfigType: {type.name}")

    def __getitem__(self, key: str) -> Any:
        if self.data is None:
            raise ConfigError("Config has no data")
        if key not in self.data:
            raise ConfigError(f"Key {key!r} not found in {self.type.name}")
        return self.data[key]


def get_main_config_directory() -> Path:
    home_dir = Path.home()
    config_dir = home_dir / ".epomaker-controller"
    return config_dir


def create_default_main_config(config_file: Path) -> None:
    with open(config_file, 'w', encoding="utf-8") as f:
        json.dump(DEFAULT_MAIN_CONFIG, f, indent=4)


def save_main_config(config: Config) -> None:
    config_dir = get_main_config_directory()
    config_file = config_dir / "config.json"
    with open(config_file, 'w', encoding="utf-8") as f:
        json.dump(config.data, f, indent=4)


def setup_main_config() -> Path:
    config_dir = get_main_config_directory()
    config_file = config_dir / "config.json"

    # Create the config directory if it doesn't exist
    if not config_dir.exists():
        print(f"Creating config directory at {config_dir}")
        config_dir.mkdir(parents=True)

    # Create the default config file if it doesn't exist
    if not config_file.exists():
        print(f"Creating default config file at {config_file}")
        create_default_main_config(config_file)

    return config_file


def _migrate_dynatab_capabilities(data: dict[Any, Any]) -> None:
    """Upgrade older configs that set DynaTab layout without CAPABILITIES."""
    layout = str(data.get("CONF_LAYOUT_PATH", ""))
    caps = list(data.get("CAPABILITIES", DEFAULT_MAIN_CONFIG["CAPABILITIES"]))
    if "DynaTab" in layout and "dynatab_screen" not in caps:
        caps = [c for c in caps if c != "rt100_screen"]
        if "per_key_rgb" not in caps:
            caps.insert(0, "per_key_rgb")
        caps.append("dynatab_screen")
        data["CAPABILITIES"] = caps


def verify_main_config(in_config: Config) -> Config:
    if in_config.type != ConfigType.CONF_MAIN:
        raise ConfigError("verify_main_config only for Configs of type CONF_MAIN")
    if in_config.data is None:
        raise ConfigError("Config has no data")

    # Ensure no unsupported entries are present
    extra_keys = set(in_config.data.keys()) - set(DEFAULT_MAIN_CONFIG.keys())
    if extra_keys:
        raise ConfigError(f"Unsupported config entries found: {extra_keys}")

    # Merge the default values with the provided config, ensuring no missing keys
    merged = {**DEFAULT_MAIN_CONFIG, **in_config.data}
    _migrate_dynatab_capabilities(merged)

    out_config = Config(
        type=in_config.type,
        filename=in_config.filename,
        data=merged,
    )

    # Write config back
    save_main_config(out_config)

    return out_config


def load_main_config() -> Config:
    config_file = setup_main_config()

    config = Config(ConfigType.CONF_MAIN, config_file.as_posix())

    return verify_main_config(config)


def get_all_configs() -> dict[ConfigType, Config]:
    # First load the main config file
    main_config = load_main_config()
    if main_config.data is None:
        raise ConfigError("Config has no data")

    # Use keyboard and layout configs as per main config
    conf_layout_path = main_config.data["CONF_LAYOUT_PATH"]
    conf_keymap_path = main_config.data["CONF_KEYMAP_PATH"]

    all_configs = {
        ConfigType.CONF_MAIN: main_config,
        ConfigType.CONF_LAYOUT: Config(ConfigType.CONF_LAYOUT, conf_layout_path),
        ConfigType.CONF_KEYMAP: Config(ConfigType.CONF_KEYMAP, conf_keymap_path),
    }

    return all_configs
