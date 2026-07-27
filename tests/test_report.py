"""Unit tests for Report construction and checksum."""

import pytest

from epomakercontroller.commands.reports.Report import BUFF_LENGTH, Report
from epomakercontroller.commands.reports.ReportWithData import ReportWithData
from epomakercontroller.exceptions import ProtocolError


def test_buff_length_is_64() -> None:
    assert BUFF_LENGTH == 64


def test_report_padded_to_buff_length() -> None:
    report = Report("18000000000000e7", checksum_index=None, index=0)
    assert len(report) == BUFF_LENGTH
    assert report.get_all_bytes() is not None
    assert report.get_all_bytes()[:8] == bytes.fromhex("18000000000000e7")
    assert report.get_all_bytes()[8:] == bytes(BUFF_LENGTH - 8)


def test_checksum_calculation() -> None:
    # sum(0x19, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00) = 0x1a; checksum = 0xff - 0x1a = 0xe5
    header = bytes([0x19, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00])
    assert Report._calculate_checksum(header) == bytes([0xE5])


def test_report_with_checksum_appends_byte() -> None:
    report = Report(
        "19{this_frame_report_index:02x}{frame_index:02x}"
        "{total_frames:02x}{frame_time:02x}0000",
        checksum_index=7,
        index=1,
        pad_on_init=True,
        header_format_values={
            "this_frame_report_index": 0,
            "frame_index": 0,
            "total_frames": 1,
            "frame_time": 0,
        },
    )
    raw = report.get_all_bytes()
    assert raw is not None
    assert len(raw) == BUFF_LENGTH
    assert raw[0] == 0x19
    assert raw[7] == 0xE5  # checksum for the 7-byte header above


def test_report_too_long_raises() -> None:
    # 65 bytes of hex → more than BUFF_LENGTH after fromhex
    too_long = "00" * (BUFF_LENGTH + 1)
    with pytest.raises(ProtocolError, match="exceeds the maximum"):
        Report(too_long, checksum_index=None, index=0)


def test_report_with_data_rejects_double_add() -> None:
    report = ReportWithData(
        "19000001000000",
        checksum_index=7,
        index=1,
    )
    report.add_data(bytes(56))
    with pytest.raises(ProtocolError, match="already been set"):
        report.add_data(bytes(56))
