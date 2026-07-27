"""Controller dry-run and capability routing tests (no real HID traffic)."""

from unittest.mock import patch

import pytest

from epomakercontroller.commands.EpomakerKeyRGBCommand import (
    KeyboardRGBFrame,
    KeyMap,
)
from epomakercontroller.commands.data.constants import (
    CAPABILITY_DYNATAB_SCREEN,
    CAPABILITY_RT100_SCREEN,
    ERASE_DELAY_S,
    PACKET_DELAY_S,
)
from epomakercontroller.epomakercontroller import EpomakerController
from epomakercontroller.exceptions import ProtocolError, UnsupportedImageError
from epomakercontroller.utils.keyboard_keys import KeyboardKeys


def test_has_capability(main_config) -> None:
    ctl = EpomakerController(main_config, dry_run=True)
    # Default package config is RT100 capabilities
    assert ctl.has_capability("per_key_rgb")
    assert ctl.has_capability(CAPABILITY_RT100_SCREEN)
    assert not ctl.has_capability(CAPABILITY_DYNATAB_SCREEN)


def test_dynatab_config_capabilities(dynatab_main_config) -> None:
    ctl = EpomakerController(dynatab_main_config, dry_run=True)
    assert ctl.has_capability(CAPABILITY_DYNATAB_SCREEN)
    assert not ctl.has_capability(CAPABILITY_RT100_SCREEN)


def test_send_keys_applies_pacing(main_config) -> None:
    ctl = EpomakerController(main_config, dry_run=True)
    keys = KeyboardKeys(ctl.config_keymap)
    mapping = KeyMap(keys)
    for key in keys:
        mapping[key] = (1, 2, 3)
    frame = KeyboardRGBFrame(key_map=mapping)

    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with patch("epomakercontroller.epomakercontroller.time.sleep", fake_sleep):
        ctl.send_keys([frame])

    # 1 erase delay after first report + 7 packet delays after data reports
    assert sleeps[0] == ERASE_DELAY_S
    assert sleeps[1:] == [PACKET_DELAY_S] * 7
    assert len(sleeps) == 8


def test_send_dynatab_frames_dry_run(dynatab_main_config) -> None:
    ctl = EpomakerController(dynatab_main_config, dry_run=True)
    ctl.send_dynatab_frames([[(0, 0, 0)] * 540], delay_ms=80)


def test_send_image_no_capability_raises(main_config) -> None:
    data = dict(main_config.data)
    data["CAPABILITIES"] = ["per_key_rgb"]  # no screen
    main_config.data = data
    ctl = EpomakerController(main_config, dry_run=True)
    # Re-apply after constructor (constructor already read CAPABILITIES)
    ctl.capabilities = {"per_key_rgb"}
    with pytest.raises(ProtocolError, match="No screen upload capability"):
        ctl.send_image("/tmp/anything.png")


def test_send_image_rt100_bad_extension(main_config, tmp_path) -> None:
    ctl = EpomakerController(main_config, dry_run=True)
    assert ctl.has_capability(CAPABILITY_RT100_SCREEN)
    bad = tmp_path / "x.xyz"
    bad.write_bytes(b"nope")
    with pytest.raises(UnsupportedImageError):
        ctl.send_image(str(bad))


def test_context_manager_closes_device(main_config) -> None:
    ctl = EpomakerController(main_config, dry_run=True)
    with ctl:
        assert ctl.open_device()
        # dry_run leaves a placeholder hid.device object
        assert ctl.device is not None
    # __exit__ always calls close_device
    assert ctl.device is None


def test_context_manager_closes_on_exception(main_config) -> None:
    ctl = EpomakerController(main_config, dry_run=True)
    with pytest.raises(RuntimeError, match="boom"):
        with ctl:
            assert ctl.open_device()
            raise RuntimeError("boom")
    assert ctl.device is None


def test_signal_handlers_opt_in(main_config, monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_signal(sig, handler):
        calls.append((sig, handler))

    monkeypatch.setattr(
        "epomakercontroller.epomakercontroller.signal.signal", fake_signal
    )
    EpomakerController(main_config, dry_run=True)
    assert calls == []

    EpomakerController(
        main_config, dry_run=True, install_signal_handlers=True
    )
    assert len(calls) == 2  # SIGINT + SIGTERM
