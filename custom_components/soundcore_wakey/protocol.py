"""Build Soundcore Wakey time-sync BLE frame (command 0x8101)."""

from __future__ import annotations

from datetime import datetime


def build_time_packet(dt: datetime, flag: int = 0x01) -> bytes:
    """Body: year_since_2000, month, day, hour, minute, second, flag."""
    if dt.year < 2000 or dt.year > 2255:
        raise ValueError(f"Year out of range: {dt.year}")
    if not 0 <= flag <= 0xFF:
        raise ValueError(f"flag must be 0..255, got {flag}")

    header = bytes([0x08, 0xEE, 0x00, 0x00, 0x00])
    command = bytes([0x01, 0x81])  # 0x8101 little-endian
    body = bytes(
        [
            dt.year - 2000,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            flag & 0xFF,
        ]
    )
    length = (5 + 2 + 2 + len(body)).to_bytes(2, "little")
    return header + command + length + body
