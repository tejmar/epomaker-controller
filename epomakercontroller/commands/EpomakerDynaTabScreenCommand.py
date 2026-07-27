"""Command for sending images and animations to the DynaTab 75X dot-matrix screen."""

import os
import cv2
import numpy as np

from ..exceptions import UnsupportedImageError
from .EpomakerCommand import EpomakerCommand, CommandStructure
from .reports.Report import Report
from .reports.ReportWithData import ReportWithData

SUPPORTED_FORMATS = [".gif", ".png", ".jpg", ".jpeg", ".bmp", ".webp"]

class EpomakerDynaTabScreenCommand(EpomakerCommand):
    """A command for sending custom images or animations to the DynaTab 75X screen."""

    def __init__(self, frames_rgb: list[list[tuple[int, int, int]]], delay_ms: int = 100) -> None:
        """Initializes the command with frame pixel data.

        Args:
            frames_rgb (list): A list of frames.
            delay_ms (int): The animation frame delay in milliseconds.
        """
        if len(frames_rgb) > 15:
            print("Warning: Animation truncated to 15 frames (maximum supported by DynaTab 75X).")
            frames_rgb = frames_rgb[:15]
        frame_count = len(frames_rgb)
        
        # Buffer size of one frame: 540 pixels * 3 bytes/pixel = 1620 bytes (0x0654)
        frame_bytes_len = 1620
        buffer_size_bytes = frame_bytes_len.to_bytes(2, "little")
        
        # 1. Build the initialization command report (0xa9)
        # Byte 0: a9
        # Byte 1: 00
        # Byte 2: frame_count
        # Byte 3: delay_ms (clamped to 0-255)
        # Byte 4, 5: buffer_size_bytes (low, high)
        # Byte 6: 00
        # Byte 7: Checksum
        # Byte 10: Width (60 = 0x3c)
        # Byte 11: Height (9 = 0x09)
        init_header_format = (
            "a900{frame_count:02x}{delay_ms:02x}"
            "{buf_size_low:02x}{buf_size_high:02x}00"
        )
        initial_report = ReportWithData(
            header_format_string=init_header_format,
            index=0,
            header_format_values={
                "frame_count": frame_count,
                "delay_ms": min(255, max(1, delay_ms)),
                "buf_size_low": buffer_size_bytes[0],
                "buf_size_high": buffer_size_bytes[1],
            },
            checksum_index=7,
        )
        
        # Pad payload to 56 bytes, adding width/height at offset 10 and 11
        init_data = bytearray(56)
        init_data[2] = 60  # byte 10 (offset 2 in payload)
        init_data[3] = 9   # byte 11 (offset 3 in payload)
        initial_report.add_data(bytes(init_data))

        # There are 29 reports per frame
        reports_per_frame = 29
        structure = CommandStructure(
            number_of_starter_reports=1,
            number_of_data_reports=frame_count * reports_per_frame,
            number_of_footer_reports=0,
        )
        super().__init__(initial_report, structure)
        
        # 2. Build the data reports (0x29) for each frame
        data_buff_length = 56
        
        for f_idx, frame in enumerate(frames_rgb):
            # Flatten the frame to bytes
            frame_bytes = bytearray()
            for r, g, b in frame:
                frame_bytes.append(r)
                frame_bytes.append(g)
                frame_bytes.append(b)
                
            for r_idx in range(reports_per_frame):
                # The last report carries 52 bytes of payload, others carry 56
                is_last_report = (r_idx == reports_per_frame - 1)
                payload_len = 52 if is_last_report else 56
                payload_len_hex = f"{payload_len:02x}"
                
                header_fmt = "29{frame_index:02x}{frame_count:02x}{delay_ms:02x}{report_index:02x}00" + payload_len_hex
                
                report = ReportWithData(
                    header_format_string=header_fmt,
                    index=1 + (f_idx * reports_per_frame) + r_idx,
                    header_format_values={
                        "frame_index": f_idx,
                        "frame_count": frame_count,
                        "delay_ms": min(255, max(1, delay_ms)),
                        "report_index": r_idx,
                    },
                    checksum_index=7,
                )
                payload_slice = frame_bytes[r_idx * 56 : r_idx * 56 + payload_len]
                report.add_data(bytes(payload_slice))
                self._insert_report(report)
                
        self.report_data_prepared = True

    @classmethod
    def from_image(cls, image_path: str, delay_ms: int = 100) -> "EpomakerDynaTabScreenCommand":
        """Loads and encodes an image or GIF file using Pillow.

        Args:
            image_path (str): The path to the image or GIF file.
            delay_ms (int): The animation frame delay in milliseconds (default: 100).
        """
        from PIL import Image
        
        _, extension = os.path.splitext(image_path)
        ext = extension.lower()
        if ext not in SUPPORTED_FORMATS:
            raise UnsupportedImageError(
                f"Unsupported format {ext!r}. Supported: {SUPPORTED_FORMATS}"
            )

        frames_rgb = []

        try:
            img = Image.open(image_path)
            try:
                while True:
                    frame_img = img.copy().convert("RGB").resize((60, 9), Image.Resampling.LANCZOS)
                    # Column-major format conversion: col-by-col, row-by-row
                    pixels = []
                    for x in range(60):
                        for y in range(9):
                            pixels.append(frame_img.getpixel((x, y)))
                    frames_rgb.append(pixels)

                    if ext == ".gif":
                        img.seek(img.tell() + 1)
                    else:
                        break
            except EOFError:
                pass
        except UnsupportedImageError:
            raise
        except Exception as e:
            raise UnsupportedImageError(
                f"Error loading image/GIF with Pillow: {e}"
            ) from e

        if not frames_rgb:
            raise UnsupportedImageError(
                f"No frames found in image/GIF: {image_path}"
            )
        return cls(frames_rgb, delay_ms)
