"""BLE connect + write time packet to Soundcore Wakey."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import WRITE_CHAR_UUID
from .protocol import build_time_packet

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 20.0
# Empirically more reliable on some BlueZ hosts than 1.0s
SETTLE_SECONDS = 2.0


async def async_sync_time(
    hass: HomeAssistant,
    address: str,
    dt: datetime | None = None,
    flag: int = 0x01,
) -> None:
    """Connect over BLE and write local wall-clock time to the Wakey."""
    if dt is None:
        dt = datetime.now().replace(microsecond=0)

    packet = build_time_packet(dt, flag=flag)
    _LOGGER.info(
        "Wakey sync %s → %s (flag=0x%02x) packet=%s",
        address,
        dt.isoformat(sep=" "),
        flag,
        packet.hex(" "),
    )

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    if ble_device is None:
        target: str | object = address
        _LOGGER.debug("No BLEDevice from HA scanner for %s, using address string", address)
    else:
        target = ble_device

    try:
        from bleak_retry_connector import (
            BleakClientWithServiceCache,
            establish_connection,
        )
    except ImportError:
        from bleak import BleakClient

        BleakClientWithServiceCache = BleakClient  # type: ignore[misc, assignment]
        establish_connection = None  # type: ignore[assignment]

    client = None
    try:
        if establish_connection is not None:
            client = await establish_connection(
                BleakClientWithServiceCache,
                target,
                name=f"soundcore_wakey_{address}",
                max_attempts=3,
                timeout=CONNECT_TIMEOUT,
            )
        else:
            client = BleakClientWithServiceCache(target, timeout=CONNECT_TIMEOUT)
            await client.connect()

        await asyncio.sleep(SETTLE_SECONDS)

        # Always use write-with-response: write-without-response can report
        # success on BlueZ while the Wakey ignores the payload (seen on HA host).
        _LOGGER.debug("Writing GATT char %s response=True", WRITE_CHAR_UUID)
        await client.write_gatt_char(WRITE_CHAR_UUID, packet, response=True)
        _LOGGER.info("Wakey time write completed for %s (write-with-response)", address)
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
