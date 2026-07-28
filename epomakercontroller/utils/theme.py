"""Shared dark UI theme for Epomaker controller GUIs.

Centralizes colors and small widget factories so the key backlight and screen
designer apps stay visually consistent without depending on a third-party theme pack.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from .fonts import F

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = "#12141a"  # app background
SURFACE = "#1c1f28"  # panels / cards
SURFACE_2 = "#252a36"  # nested controls
SURFACE_3 = "#2f3545"  # hover / secondary buttons
BORDER = "#3a4154"

TEXT = "#eef0f5"
TEXT_MUTED = "#9aa3b5"
TEXT_DIM = "#6b7385"

ACCENT = "#5b8cff"  # primary actions / selection ring
ACCENT_HOVER = "#7aa2ff"
ACCENT_SOFT = "#2a3a5c"

SUCCESS = "#3ecf8e"
SUCCESS_HOVER = "#56dca0"
DANGER = "#f04f6e"
DANGER_HOVER = "#ff6b86"
WARN = "#f0b429"

KEY_IDLE = "#2a2f3c"
KEY_DISABLED = "#161922"
KEY_BORDER = "#3d4456"
KEY_TEXT = "#eef0f5"
KEY_TEXT_DIM = "#5a6275"

SWATCH_OFF = "#0d0f14"
CANVAS_BG = "#0a0b10"
GRID_LINE = "#2a3040"

# Legacy aliases used while migrating call sites
BG_LEGACY = BG
PANEL = SURFACE
BTN = SURFACE_3
BTN_HOVER = ACCENT_HOVER


def hex_rgb(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def contrast_fg(bg_hex: str) -> str:
    """Pick light or dark text for readability on *bg_hex*."""
    h = bg_hex.lstrip("#")
    if len(h) != 6:
        return TEXT
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # Perceived luminance
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111318" if lum > 0.55 else TEXT


def style_root(root: tk.Tk | tk.Toplevel, title: str | None = None) -> None:
    if title is not None:
        root.title(title)
    root.configure(bg=BG)


def panel(parent: tk.Misc, **kwargs: Any) -> tk.Frame:
    opts = {"bg": SURFACE, "highlightthickness": 0, "bd": 0}
    opts.update(kwargs)
    return tk.Frame(parent, **opts)


def section_label(parent: tk.Misc, text: str, **pack_kwargs: Any) -> tk.Label:
    lbl = tk.Label(
        parent,
        text=text.upper(),
        font=F(8, "bold"),
        bg=parent.cget("bg") if "bg" not in pack_kwargs else pack_kwargs.get("bg", SURFACE),
        fg=TEXT_DIM,
        anchor="w",
    )
    # allow caller to pack/grid themselves
    return lbl


def muted_label(parent: tk.Misc, text: str = "", **kwargs: Any) -> tk.Label:
    opts = {
        "text": text,
        "font": F(9),
        "bg": parent.cget("bg"),
        "fg": TEXT_MUTED,
        "anchor": "w",
    }
    opts.update(kwargs)
    return tk.Label(parent, **opts)


def body_label(parent: tk.Misc, text: str = "", **kwargs: Any) -> tk.Label:
    opts = {
        "text": text,
        "font": F(10),
        "bg": parent.cget("bg"),
        "fg": TEXT,
        "anchor": "w",
    }
    opts.update(kwargs)
    return tk.Label(parent, **opts)


def title_label(parent: tk.Misc, text: str, **kwargs: Any) -> tk.Label:
    opts = {
        "text": text,
        "font": F(15, "bold"),
        "bg": parent.cget("bg") if hasattr(parent, "cget") else BG,
        "fg": TEXT,
        "pady": 12,
    }
    opts.update(kwargs)
    return tk.Label(parent, **opts)


def status_bar(parent: tk.Misc, textvariable: tk.StringVar) -> tk.Label:
    return tk.Label(
        parent,
        textvariable=textvariable,
        bg=SURFACE,
        fg=TEXT_MUTED,
        font=F(8),
        anchor="w",
        padx=12,
        pady=6,
    )


def _btn_base(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None,
    *,
    bg: str,
    fg: str,
    activebackground: str,
    font: Any = None,
    **kwargs: Any,
) -> tk.Button:
    opts = {
        "text": text,
        "command": command,
        "bg": bg,
        "fg": fg,
        "activebackground": activebackground,
        "activeforeground": fg,
        "font": font or F(9, "bold"),
        "relief": tk.FLAT,
        "bd": 0,
        "highlightthickness": 0,
        "cursor": "hand2",
        "padx": 10,
        "pady": 6,
    }
    opts.update(kwargs)
    return tk.Button(parent, **opts)


def button_secondary(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    **kwargs: Any,
) -> tk.Button:
    return _btn_base(
        parent,
        text,
        command,
        bg=SURFACE_3,
        fg=TEXT,
        activebackground=BORDER,
        **kwargs,
    )


def button_primary(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    **kwargs: Any,
) -> tk.Button:
    return _btn_base(
        parent,
        text,
        command,
        bg=ACCENT,
        fg="#ffffff",
        activebackground=ACCENT_HOVER,
        **kwargs,
    )


def button_success(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    **kwargs: Any,
) -> tk.Button:
    return _btn_base(
        parent,
        text,
        command,
        bg=SUCCESS,
        fg="#0b1a12",
        activebackground=SUCCESS_HOVER,
        **kwargs,
    )


def button_danger(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    **kwargs: Any,
) -> tk.Button:
    return _btn_base(
        parent,
        text,
        command,
        bg=DANGER,
        fg="#ffffff",
        activebackground=DANGER_HOVER,
        **kwargs,
    )


def button_tool(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    active: bool = False,
    **kwargs: Any,
) -> tk.Button:
    if active:
        return _btn_base(
            parent,
            text,
            command,
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_HOVER,
            font=F(9, "bold"),
            **kwargs,
        )
    return _btn_base(
        parent,
        text,
        command,
        bg=SURFACE_3,
        fg=TEXT,
        activebackground=BORDER,
        font=F(9),
        **kwargs,
    )


def set_tool_active(btn: tk.Button, active: bool) -> None:
    if active:
        btn.configure(
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_HOVER,
            activeforeground="#ffffff",
            font=F(9, "bold"),
        )
    else:
        btn.configure(
            bg=SURFACE_3,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            font=F(9),
        )


def card(parent: tk.Misc, title: str | None = None) -> tuple[tk.Frame, tk.Frame]:
    """Return (outer card, inner content frame)."""
    outer = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, bd=0)
    if title:
        tk.Label(
            outer,
            text=title,
            font=F(9, "bold"),
            bg=SURFACE,
            fg=TEXT_MUTED,
            anchor="w",
            padx=12,
            pady=8,
        ).pack(fill=tk.X)
        # subtle separator
        tk.Frame(outer, bg=BORDER, height=1).pack(fill=tk.X)
    inner = tk.Frame(outer, bg=SURFACE, padx=10, pady=8)
    inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


def scale(
    parent: tk.Misc,
    **kwargs: Any,
) -> tk.Scale:
    opts = {
        "bg": SURFACE,
        "fg": TEXT,
        "troughcolor": SURFACE_2,
        "highlightthickness": 0,
        "bd": 0,
        "activebackground": ACCENT,
        "font": F(8),
    }
    opts.update(kwargs)
    return tk.Scale(parent, **opts)


def entry(parent: tk.Misc, **kwargs: Any) -> tk.Entry:
    opts = {
        "bg": SURFACE_2,
        "fg": TEXT,
        "insertbackground": TEXT,
        "relief": tk.FLAT,
        "bd": 0,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT,
        "font": F(9),
    }
    opts.update(kwargs)
    return tk.Entry(parent, **opts)


def checkbox(
    parent: tk.Misc,
    text: str,
    variable: tk.Variable,
    **kwargs: Any,
) -> tk.Checkbutton:
    opts = {
        "text": text,
        "variable": variable,
        "bg": SURFACE,
        "fg": TEXT,
        "selectcolor": SURFACE_2,
        "activebackground": SURFACE,
        "activeforeground": TEXT,
        "highlightthickness": 0,
        "font": F(9),
        "anchor": "w",
    }
    opts.update(kwargs)
    return tk.Checkbutton(parent, **opts)


def option_menu(
    parent: tk.Misc,
    variable: tk.StringVar,
    *values: str,
) -> tk.OptionMenu:
    menu = tk.OptionMenu(parent, variable, *values)
    menu.config(
        bg=SURFACE_3,
        fg=TEXT,
        activebackground=BORDER,
        activeforeground=TEXT,
        highlightthickness=0,
        relief=tk.FLAT,
        bd=0,
        font=F(9),
    )
    menu["menu"].config(bg=SURFACE_2, fg=TEXT, activebackground=ACCENT, activeforeground="#ffffff")
    return menu


def color_swatch_button(
    parent: tk.Misc,
    rgb: tuple[int, int, int],
    command: Callable[[], None],
    *,
    text: str | None = None,
    width: int = 3,
    height: int = 1,
) -> tk.Button:
    hx = hex_rgb(rgb) if rgb != (0, 0, 0) else SWATCH_OFF
    fg = contrast_fg(hx) if text else TEXT
    return tk.Button(
        parent,
        text=text or "",
        bg=hx,
        fg=fg,
        activebackground=hx,
        activeforeground=fg,
        font=F(7, "bold"),
        width=width,
        height=height,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        cursor="hand2",
        command=command,
    )
