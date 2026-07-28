"""Tiny bitmap font helpers for the 60×9 DynaTab screen.

Frames are column-major: index = col * HEIGHT + row, matching ScreenDesignerApp.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

WIDTH = 60
HEIGHT = 9

# 5×7 glyphs (rows top→bottom). Bit 4 = leftmost pixel.
_FONT_5X7: dict[str, tuple[int, ...]] = {
    " ": (0, 0, 0, 0, 0, 0, 0),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0E),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x01, 0x01, 0x01, 0x01, 0x11, 0x11, 0x0E),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F),
    "3": (0x1F, 0x01, 0x02, 0x06, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    "/": (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
}


def _blank_frame() -> list[tuple[int, int, int]]:
    return [(0, 0, 0) for _ in range(WIDTH * HEIGHT)]


def _set_pixel(
    frame: list[tuple[int, int, int]],
    col: int,
    row: int,
    color: tuple[int, int, int],
) -> None:
    if 0 <= col < WIDTH and 0 <= row < HEIGHT:
        frame[col * HEIGHT + row] = color


def _draw_char(
    frame: list[tuple[int, int, int]],
    ch: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> int:
    """Draw one character; return advance width (5 + 1 gap)."""
    glyph = _FONT_5X7.get(ch.upper(), _FONT_5X7[" "])
    for row, bits in enumerate(glyph):
        for col in range(5):
            if bits & (0x10 >> col):
                _set_pixel(frame, x + col, y + row, color)
    return 6


def measure_text(text: str) -> int:
    """Pixel width of *text* with 1px gaps (no trailing gap)."""
    if not text:
        return 0
    return max(0, len(text) * 6 - 1)


def render_text_frame(
    text: str,
    *,
    color: tuple[int, int, int] = (0, 220, 120),
    x: int = 0,
    y: int = 1,
    bg: tuple[int, int, int] = (0, 0, 0),
) -> list[tuple[int, int, int]]:
    """Single frame with *text* drawn at (x, y)."""
    frame = [bg for _ in range(WIDTH * HEIGHT)]
    cursor = x
    for ch in text:
        if cursor >= WIDTH:
            break
        cursor += _draw_char(frame, ch, cursor, y, color)
    return frame


def render_text_animation(
    text: str,
    *,
    color: tuple[int, int, int] = (0, 220, 120),
    max_frames: int = 15,
    scroll: bool = True,
) -> list[list[tuple[int, int, int]]]:
    """Render text as one or more frames; scroll if wider than the screen."""
    text = (text or "").strip() or "?"
    # Prefer readable casing for repo names (keep as given but font is uppercase glyphs)
    display = text
    width_px = measure_text(display)
    y = 1  # 7-row glyph + 1px top margin fits in 9

    if width_px <= WIDTH and not scroll:
        return [render_text_frame(display, color=color, x=(WIDTH - width_px) // 2, y=y)]

    if width_px <= WIDTH:
        # Centered static single frame
        return [render_text_frame(display, color=color, x=(WIDTH - width_px) // 2, y=y)]

    # Scrolling marquee
    frames: list[list[tuple[int, int, int]]] = []
    # Start fully right, scroll left until fully off
    start_x = WIDTH
    end_x = -width_px
    total_travel = start_x - end_x
    steps = min(max_frames, max(1, total_travel))
    for i in range(steps):
        x = start_x - int(i * total_travel / max(1, steps - 1))
        frames.append(render_text_frame(display, color=color, x=x, y=y))
    return frames


def detect_git_repo_name(start: Path | None = None) -> tuple[str | None, Path | None]:
    """Return (repo_directory_name, toplevel_path) or (None, None)."""
    cwd = (start or Path.cwd()).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if result.returncode != 0:
        return None, None
    top = Path(result.stdout.strip())
    if not top.exists():
        return None, None
    return top.name, top


def truncate_for_screen(name: str, max_chars: int = 12) -> str:
    """Shorten a name so it is likely to fit; scroll still works if longer."""
    name = name.strip()
    if len(name) <= max_chars:
        return name
    return name[: max_chars - 1] + "."
