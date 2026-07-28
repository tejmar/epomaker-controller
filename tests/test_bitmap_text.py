"""Tests for 60×9 bitmap text and git helper (no device)."""

from epomakercontroller.utils.bitmap_text import (
    WIDTH,
    HEIGHT,
    measure_text,
    render_text_animation,
    render_text_frame,
    detect_git_repo_name,
)
from epomakercontroller.utils.screen_slots import (
    NUM_SLOTS,
    FACTORY_PRESETS,
    frame_to_thumbnail,
    save_slot,
    load_slot,
    ensure_factory_slots,
    slots_directory,
)


def test_render_text_frame_size():
    frame = render_text_frame("HI", color=(255, 0, 0))
    assert len(frame) == WIDTH * HEIGHT
    assert any(px != (0, 0, 0) for px in frame)


def test_long_text_scrolls_multiple_frames():
    frames = render_text_animation(
        "VERY-LONG-REPO-NAME-HERE",
        max_frames=15,
        scroll=True,
    )
    assert 1 < len(frames) <= 15
    assert measure_text("VERY-LONG-REPO-NAME-HERE") > WIDTH


def test_short_text_single_frame():
    frames = render_text_animation("OK", max_frames=15, scroll=True)
    assert len(frames) == 1


def test_detect_git_repo_in_this_project():
    # This worktree is a git checkout
    name, top = detect_git_repo_name()
    assert name is not None
    assert top is not None
    assert top.exists()


def test_factory_presets_and_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "epomakercontroller.utils.screen_slots.slots_directory",
        lambda: tmp_path,
    )
    assert len(FACTORY_PRESETS) >= NUM_SLOTS
    ensure_factory_slots()
    for i in range(NUM_SLOTS):
        data = load_slot(i)
        assert data is not None
        assert len(data["frames"]) >= 1
        assert len(data["frames"][0]) == WIDTH * HEIGHT
        thumb = frame_to_thumbnail(data["frames"][0], scale=2)
        assert thumb.size == (WIDTH * 2, HEIGHT * 2)

    # overwrite slot 0
    blank = [[(1, 2, 3) for _ in range(WIDTH * HEIGHT)]]
    save_slot(0, blank, 50, name="Mine", factory=False)
    data = load_slot(0)
    assert data["name"] == "Mine"
    assert data["frames"][0][0] == (1, 2, 3)
