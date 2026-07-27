"""
Font resolution helper for Tkinter GUIs.
Picks the best available sans-serif font on the current system,
falling back gracefully through a priority list.
"""
import tkinter as tk
from tkinter import font as tkfont

# Priority list: best modern sans-serif fonts first, ending with guaranteed fallbacks
_FONT_PRIORITY = [
    "Ubuntu Sans",
    "Ubuntu",
    "Lato",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "FreeSans",
    "Helvetica",
    "Arial",
    "TkDefaultFont",
]

_resolved: str | None = None


def get_ui_font() -> str:
    """Return the best available sans-serif font family name."""
    global _resolved
    if _resolved is not None:
        return _resolved

    # We need a Tk root to query available fonts.
    # If one already exists, use it; otherwise create a temporary hidden one.
    try:
        root = tk._default_root  # type: ignore[attr-defined]
        if root is None:
            raise RuntimeError("no root")
        available = set(tkfont.families())
    except Exception:
        tmp = tk.Tk()
        tmp.withdraw()
        available = set(tkfont.families())
        tmp.destroy()

    for candidate in _FONT_PRIORITY:
        if candidate in available:
            _resolved = candidate
            return _resolved

    _resolved = "TkDefaultFont"
    return _resolved


def F(size: int, weight: str = "normal") -> tuple:
    """Shorthand: return a (family, size, weight) font tuple."""
    return (get_ui_font(), size, weight)
