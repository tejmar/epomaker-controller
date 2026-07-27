"""Golden-structure tests for command builders (no HID device)."""

from datetime import datetime
from pathlib import Path

import pytest

from epomakercontroller.commands.EpomakerCpuCommand import EpomakerCpuCommand
from epomakercontroller.commands.EpomakerDynaTabScreenCommand import (
    EpomakerDynaTabScreenCommand,
)
from epomakercontroller.commands.EpomakerImageCommand import EpomakerImageCommand
from epomakercontroller.commands.EpomakerKeyRGBCommand import (
    EpomakerKeyRGBCommand,
    KeyboardRGBFrame,
    KeyMap,
)
from epomakercontroller.commands.EpomakerTempCommand import EpomakerTempCommand
from epomakercontroller.commands.EpomakerTimeCommand import EpomakerTimeCommand
from epomakercontroller.commands.data.constants import BUFF_LENGTH
from epomakercontroller.commands.reports.Report import BUFF_LENGTH as REPORT_BUFF
from epomakercontroller.configs.configs import Config, ConfigType
from epomakercontroller.exceptions import UnsupportedImageError
from epomakercontroller.utils.keyboard_keys import KeyboardKeys


def test_constants_buff_length_matches_report() -> None:
    assert BUFF_LENGTH == REPORT_BUFF == 64


def test_time_command_format() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    cmd = EpomakerTimeCommand(dt)
    assert cmd.report_data_prepared
    reports = list(cmd)
    assert len(reports) == 1
    raw = reports[0].get_all_bytes()
    assert raw is not None
    assert len(raw) == BUFF_LENGTH
    # header 28000000000000d7 + year month day hour minute second
    expected_prefix = bytes.fromhex("28000000000000d7" + "07e80102030405")
    assert raw[: len(expected_prefix)] == expected_prefix


def test_temp_and_cpu_commands() -> None:
    temp = EpomakerTempCommand(42)
    t_raw = list(temp)[0].get_all_bytes()
    assert t_raw is not None
    assert t_raw[:9] == bytes.fromhex("2a000000000000d52a")

    cpu = EpomakerCpuCommand(75)
    c_raw = list(cpu)[0].get_all_bytes()
    assert c_raw is not None
    assert c_raw[0] == 0x22
    assert c_raw[16] == 75  # cpu byte after fixed prefix


def test_key_rgb_command_structure_and_packing() -> None:
    keymap = Config(ConfigType.CONF_KEYMAP, "EpomakerDynaTab75X.json")
    keys = KeyboardKeys(keymap)
    mapping = KeyMap(keys)

    # Paint a single known key solid red so index math is checkable.
    target = keys.get_key_by_name("A")
    assert target is not None
    mapping[target] = (0xAA, 0xBB, 0xCC)

    cmd = EpomakerKeyRGBCommand([KeyboardRGBFrame(key_map=mapping)])
    assert cmd.report_data_prepared
    reports = list(cmd)
    # 1 init + 7 data reports per frame
    assert len(reports) == 8
    for report in reports:
        assert len(report) == BUFF_LENGTH

    init = reports[0].get_all_bytes()
    assert init is not None
    assert init[:8] == bytes.fromhex("18000000000000e7")

    data_reports = cmd.get_data_reports()
    assert len(data_reports) == 7
    for i, report in enumerate(data_reports):
        raw = report.get_all_bytes()
        assert raw is not None
        assert raw[0] == 0x19
        assert raw[1] == i  # this_frame_report_index

    # Locate R/G/B for key.value in the concatenated data buffers (header len 8)
    header_len = 8
    data_len = BUFF_LENGTH - header_len
    flat = bytearray()
    for report in data_reports:
        raw = report.get_all_bytes()
        assert raw is not None
        flat.extend(raw[header_len : header_len + data_len])

    base = target.value * 3
    assert flat[base : base + 3] == bytes([0xAA, 0xBB, 0xCC])


def test_dynatab_screen_command_frame_count() -> None:
    black = [(0, 0, 0)] * 540
    cmd = EpomakerDynaTabScreenCommand([black], delay_ms=100)
    assert cmd.report_data_prepared
    reports = list(cmd)
    # 1 init + 29 data reports per frame
    assert len(reports) == 30
    for report in reports:
        assert len(report) == BUFF_LENGTH

    init = reports[0].get_all_bytes()
    assert init is not None
    assert init[0] == 0xA9
    assert init[2] == 1  # frame_count
    assert init[3] == 100  # delay_ms

    assert reports[1].get_all_bytes()[0] == 0x29


def test_dynatab_truncates_over_15_frames() -> None:
    frames = [[(0, 0, 0)] * 540 for _ in range(20)]
    cmd = EpomakerDynaTabScreenCommand(frames, delay_ms=50)
    # 1 + 15 * 29
    assert len(list(cmd)) == 1 + 15 * 29


def test_image_command_rejects_bad_extension(tmp_path: Path) -> None:
    bad = tmp_path / "x.xyz"
    bad.write_bytes(b"not an image")
    cmd = EpomakerImageCommand()
    with pytest.raises(UnsupportedImageError, match="Unsupported format"):
        cmd.encode_image(str(bad))


def test_dynatab_from_image_rejects_bad_extension(tmp_path: Path) -> None:
    bad = tmp_path / "x.xyz"
    bad.write_bytes(b"nope")
    with pytest.raises(UnsupportedImageError, match="Unsupported format"):
        EpomakerDynaTabScreenCommand.from_image(str(bad))
