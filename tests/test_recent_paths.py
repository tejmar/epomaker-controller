"""Tests for recent text/folder memory."""

from epomakercontroller.utils.recent_paths import load_recent, remember, save_recent


def test_remember_dedupes_and_orders(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "epomakercontroller.utils.recent_paths._config_path",
        lambda: tmp_path / "recent.json",
    )
    remember("text", "hello")
    remember("folder", "/tmp/proj", label="proj")
    remember("text", "hello")  # move to front
    items = load_recent()
    assert items[0]["value"] == "hello"
    assert items[0]["kind"] == "text"
    assert any(i["value"] == "/tmp/proj" for i in items)
    assert len([i for i in items if i["value"] == "hello"]) == 1
