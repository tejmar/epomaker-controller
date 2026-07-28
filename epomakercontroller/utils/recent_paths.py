"""Persist a short list of recent folders / text snippets for the screen designer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_RECENT = 12
_FILE = "recent_screen_text.json"


def _config_path() -> Path:
    d = Path.home() / ".epomaker-controller"
    d.mkdir(parents=True, exist_ok=True)
    return d / _FILE


def load_recent() -> list[dict[str, str]]:
    """Return list of {kind, label, value} dicts (newest first)."""
    path = _config_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = str(it.get("kind") or "text")
        value = str(it.get("value") or "").strip()
        label = str(it.get("label") or value).strip()
        if not value:
            continue
        out.append({"kind": kind, "label": label, "value": value})
    return out


def save_recent(items: list[dict[str, str]]) -> None:
    path = _config_path()
    path.write_text(
        json.dumps({"items": items[:MAX_RECENT]}, indent=2),
        encoding="utf-8",
    )


def remember(kind: str, value: str, label: str | None = None) -> list[dict[str, str]]:
    """Push *value* to the front of the recent list (deduped)."""
    value = value.strip()
    if not value:
        return load_recent()
    label = (label or value).strip()
    items = load_recent()
    items = [it for it in items if it.get("value") != value]
    items.insert(0, {"kind": kind, "label": label, "value": value})
    items = items[:MAX_RECENT]
    save_recent(items)
    return items
