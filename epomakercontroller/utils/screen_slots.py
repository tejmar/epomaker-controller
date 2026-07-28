"""Local preset slots for the 60×9 screen designer.

Slots live under ``~/.epomaker-controller/screen_slots/`` as JSON. Each slot
stores column-major RGB frames (same layout as ScreenDesignerApp) plus delay.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageTk

from .bitmap_text import WIDTH, HEIGHT, render_text_animation

NUM_SLOTS = 8
SLOT_VERSION = 1


def slots_directory() -> Path:
    path = Path.home() / ".epomaker-controller" / "screen_slots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def slot_path(index: int) -> Path:
    if not 0 <= index < NUM_SLOTS:
        raise IndexError(f"slot index {index} out of range 0..{NUM_SLOTS - 1}")
    return slots_directory() / f"slot_{index}.json"


def _blank(n: int = WIDTH * HEIGHT) -> list[tuple[int, int, int]]:
    return [(0, 0, 0) for _ in range(n)]


def _pixel(frame: list[tuple[int, int, int]], c: int, r: int, color: tuple[int, int, int]) -> None:
    if 0 <= c < WIDTH and 0 <= r < HEIGHT:
        frame[c * HEIGHT + r] = color


# --- Built-in factory presets -------------------------------------------------


def _preset_rainbow_wipe() -> dict[str, Any]:
    frames = []
    for offset in range(12):
        frame = _blank()
        for c in range(WIDTH):
            hue = ((c + offset * 5) % 60) / 60.0
            # cheap HSV→RGB
            i = int(hue * 6)
            f = hue * 6 - i
            q = int(255 * (1 - f))
            t = int(255 * f)
            rgb = [
                (255, t, 0),
                (q, 255, 0),
                (0, 255, t),
                (0, q, 255),
                (t, 0, 255),
                (255, 0, q),
            ][i % 6]
            for r in range(HEIGHT):
                _pixel(frame, c, r, rgb)
        frames.append(frame)
    return {"name": "Rainbow", "delay_ms": 80, "frames": frames, "factory": True}


def _preset_pulse() -> dict[str, Any]:
    frames = []
    for i in range(10):
        # triangle brightness 0→1→0
        t = i / 9
        bri = int(255 * (1 - abs(2 * t - 1)))
        color = (bri, max(0, bri // 4), max(0, bri // 3))
        frames.append([color for _ in range(WIDTH * HEIGHT)])
    return {"name": "Pulse", "delay_ms": 90, "frames": frames, "factory": True}


def _preset_bounce() -> dict[str, Any]:
    frames = []
    for i in range(14):
        frame = _blank()
        # bounce col across width
        phase = i / 13 * math.pi
        c = int((math.sin(phase) * 0.5 + 0.5) * (WIDTH - 3))
        r = HEIGHT // 2
        for dc in range(3):
            for dr in range(-1, 2):
                _pixel(frame, c + dc, r + dr, (255, 200, 40))
        frames.append(frame)
    return {"name": "Bounce", "delay_ms": 70, "frames": frames, "factory": True}


def _preset_rain() -> dict[str, Any]:
    frames = []
    for i in range(12):
        frame = _blank()
        for c in range(0, WIDTH, 3):
            head = (c * 3 + i * 2) % (HEIGHT + 4)
            for r in range(HEIGHT):
                dist = (head - r) % (HEIGHT + 4)
                if dist < 4:
                    g = 40 + (3 - dist) * 60
                    _pixel(frame, c, r, (20, min(255, g), 40))
        frames.append(frame)
    return {"name": "Rain", "delay_ms": 90, "frames": frames, "factory": True}


def _preset_scanner() -> dict[str, Any]:
    frames = []
    for i in range(WIDTH):
        frame = _blank()
        for r in range(HEIGHT):
            _pixel(frame, i, r, (0, 180, 255))
            if i > 0:
                _pixel(frame, i - 1, r, (0, 60, 100))
        frames.append(frame)
        if len(frames) >= 15:
            break
    # step by 4 to stay under 15
    frames = frames[:: max(1, len(frames) // 15 or 1)][:15]
    return {"name": "Scanner", "delay_ms": 50, "frames": frames, "factory": True}


def _preset_checker() -> dict[str, Any]:
    frames = []
    for phase in range(8):
        frame = _blank()
        for c in range(WIDTH):
            for r in range(HEIGHT):
                if ((c // 2 + r + phase) % 2) == 0:
                    _pixel(frame, c, r, (90, 40, 200))
                else:
                    _pixel(frame, c, r, (20, 20, 40))
        frames.append(frame)
    return {"name": "Checker", "delay_ms": 120, "frames": frames, "factory": True}


def _preset_hello() -> dict[str, Any]:
    frames = render_text_animation("HELLO", color=(0, 220, 160), max_frames=1, scroll=False)
    return {"name": "Hello", "delay_ms": 200, "frames": frames, "factory": True}


def _preset_wave() -> dict[str, Any]:
    frames = []
    for i in range(12):
        frame = _blank()
        for c in range(WIDTH):
            r = int((math.sin((c + i * 2) * 0.35) * 0.5 + 0.5) * (HEIGHT - 1))
            _pixel(frame, c, r, (255, 80, 140))
            if r + 1 < HEIGHT:
                _pixel(frame, c, r + 1, (120, 30, 70))
        frames.append(frame)
    return {"name": "Wave", "delay_ms": 80, "frames": frames, "factory": True}


FACTORY_PRESETS: list[dict[str, Any]] = [
    _preset_rainbow_wipe(),
    _preset_pulse(),
    _preset_bounce(),
    _preset_rain(),
    _preset_scanner(),
    _preset_checker(),
    _preset_hello(),
    _preset_wave(),
]


def _serialize_frames(
    frames: list[list[tuple[int, int, int]]],
) -> list[list[list[int]]]:
    return [[[int(c) for c in px] for px in frame] for frame in frames]


def _deserialize_frames(
    raw: list[list[list[int]]],
) -> list[list[tuple[int, int, int]]]:
    out: list[list[tuple[int, int, int]]] = []
    for frame in raw:
        out.append([
            (int(px[0]), int(px[1]), int(px[2])) if len(px) >= 3 else (0, 0, 0)
            for px in frame
        ])
    return out


def save_slot(
    index: int,
    frames: list[list[tuple[int, int, int]]],
    delay_ms: int,
    name: str = "",
    *,
    factory: bool = False,
) -> Path:
    path = slot_path(index)
    payload = {
        "version": SLOT_VERSION,
        "name": name or f"Slot {index + 1}",
        "delay_ms": int(delay_ms),
        "frames": _serialize_frames(frames),
        "factory": factory,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def load_slot(index: int) -> dict[str, Any] | None:
    path = slot_path(index)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    frames = _deserialize_frames(data.get("frames") or [])
    if not frames:
        return None
    # pad / trim frame length to WIDTH*HEIGHT
    fixed = []
    for fr in frames:
        if len(fr) < WIDTH * HEIGHT:
            fr = fr + [(0, 0, 0)] * (WIDTH * HEIGHT - len(fr))
        fixed.append(fr[: WIDTH * HEIGHT])
    return {
        "name": data.get("name") or f"Slot {index + 1}",
        "delay_ms": int(data.get("delay_ms") or 100),
        "frames": fixed,
        "factory": bool(data.get("factory")),
    }


def ensure_factory_slots() -> None:
    """Write factory presets into empty slot files only."""
    for i, preset in enumerate(FACTORY_PRESETS[:NUM_SLOTS]):
        path = slot_path(i)
        if path.exists():
            continue
        save_slot(
            i,
            preset["frames"],
            preset["delay_ms"],
            name=preset["name"],
            factory=True,
        )


def reset_slot_to_factory(index: int) -> dict[str, Any]:
    preset = FACTORY_PRESETS[index % len(FACTORY_PRESETS)]
    save_slot(
        index,
        preset["frames"],
        preset["delay_ms"],
        name=preset["name"],
        factory=True,
    )
    return load_slot(index)  # type: ignore[return-value]


def clear_slot(index: int) -> None:
    path = slot_path(index)
    if path.exists():
        path.unlink()


def frame_to_thumbnail(
    frame: list[tuple[int, int, int]],
    *,
    scale: int = 3,
) -> Image.Image:
    """Column-major frame → small RGB image for Tk."""
    row_major = [frame[x * HEIGHT + y] for y in range(HEIGHT) for x in range(WIDTH)]
    img = Image.new("RGB", (WIDTH, HEIGHT))
    img.putdata(row_major)
    if scale != 1:
        img = img.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST)
    return img


def slot_photoimage(index: int, *, scale: int = 3) -> tuple[ImageTk.PhotoImage | None, str]:
    """Return (PhotoImage or None, label name) for a slot."""
    data = load_slot(index)
    if not data:
        # empty placeholder
        img = Image.new("RGB", (WIDTH * scale, HEIGHT * scale), (30, 34, 44))
        return ImageTk.PhotoImage(img), "Empty"
    thumb = frame_to_thumbnail(data["frames"][0], scale=scale)
    return ImageTk.PhotoImage(thumb), data["name"]
