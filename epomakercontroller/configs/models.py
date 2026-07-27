"""Built-in keyboard model registry and helpers to apply a model to main config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..exceptions import ConfigError
from .configs import Config, ConfigType, save_main_config


@dataclass(frozen=True)
class KeyboardModel:
    """A packaged keyboard profile (layout + keymap + capabilities)."""

    id: str
    name: str
    layout: str
    keymap: str
    capabilities: tuple[str, ...]
    description: str = ""


# Shared Royuan VID/PID family uses DEFAULT_MAIN_CONFIG product IDs.
# Models here only switch layout, keymap, and feature flags.
MODELS: dict[str, KeyboardModel] = {
    "rt100": KeyboardModel(
        id="rt100",
        name="Epomaker RT100 (UK ISO)",
        layout="EpomakerRT100-UK-ISO.json",
        keymap="EpomakerRT100.json",
        capabilities=("per_key_rgb", "rt100_screen"),
        description="Full-size RT100 with 162×173 status-screen image upload.",
    ),
    "dynatab75x": KeyboardModel(
        id="dynatab75x",
        name="Epomaker DynaTab 75X",
        layout="EpomakerDynaTab75X.json",
        keymap="EpomakerDynaTab75X.json",
        capabilities=("per_key_rgb", "dynatab_screen"),
        description="75% board with 60×9 dot-matrix screen designer.",
    ),
    "ep64": KeyboardModel(
        id="ep64",
        name="Epomaker EP64",
        layout="EpomakerEP64.json",
        keymap="EpomakerEP64.json",
        capabilities=("per_key_rgb",),
        description="60%/64-layout board; per-key RGB only.",
    ),
    "gamakay-tk68-he": KeyboardModel(
        id="gamakay-tk68-he",
        name="Gamakay TK68-HE",
        layout="GamakayTK68-HE.json",
        keymap="GamakayTK68-HE.json",
        capabilities=("per_key_rgb",),
        description="TK68 HE; per-key RGB only.",
    ),
}


def list_models() -> list[KeyboardModel]:
    """Return registered models in stable id order."""
    return [MODELS[key] for key in sorted(MODELS.keys())]


def get_model(model_id: str) -> KeyboardModel:
    """Look up a model by id (case-insensitive).

    Raises:
        ConfigError: If the id is unknown.
    """
    key = model_id.strip().lower()
    if key not in MODELS:
        known = ", ".join(sorted(MODELS.keys()))
        raise ConfigError(
            f"Unknown model {model_id!r}. Known models: {known}"
        )
    return MODELS[key]


def match_model(config: Config) -> KeyboardModel | None:
    """Return the registry model matching layout+keymap paths, if any."""
    if config.data is None:
        return None
    layout = config.data.get("CONF_LAYOUT_PATH")
    keymap = config.data.get("CONF_KEYMAP_PATH")
    for model in MODELS.values():
        if model.layout == layout and model.keymap == keymap:
            return model
    return None


def apply_model(config: Config, model_id: str, *, save: bool = True) -> Config:
    """Apply a registry model to a main Config and optionally persist it.

    Updates CONF_LAYOUT_PATH, CONF_KEYMAP_PATH, and CAPABILITIES. Leaves VID/PID
    and other fields unchanged.

    Args:
        config: Existing main config (type CONF_MAIN).
        model_id: Registry id (e.g. ``dynatab75x``).
        save: Write to ``~/.epomaker-controller/config.json`` when True.

    Returns:
        A new Config instance with the model applied.
    """
    if config.type != ConfigType.CONF_MAIN:
        raise ConfigError("apply_model only works on CONF_MAIN configs")
    if config.data is None:
        raise ConfigError("Config has no data")

    model = get_model(model_id)
    data = dict(config.data)
    data["CONF_LAYOUT_PATH"] = model.layout
    data["CONF_KEYMAP_PATH"] = model.keymap
    data["CAPABILITIES"] = list(model.capabilities)

    out = Config(
        type=ConfigType.CONF_MAIN,
        filename=config.filename,
        data=data,
    )
    if save:
        save_main_config(out)
    return out


def format_models_table(
    models: Iterable[KeyboardModel],
    current: KeyboardModel | None = None,
) -> str:
    """Human-readable multi-line listing for CLI output."""
    lines = [
        f"{'ID':<18} {'NAME':<28} CAPABILITIES",
        f"{'-' * 18} {'-' * 28} {'-' * 32}",
    ]
    for model in models:
        marker = "*" if current is not None and model.id == current.id else " "
        caps = ", ".join(model.capabilities)
        lines.append(
            f"{marker}{model.id:<17} {model.name:<28} {caps}"
        )
    lines.append("")
    lines.append("* = currently selected (layout + keymap match)")
    return "\n".join(lines)
