#!/usr/bin/env python3
"""
Sync time on a Soundcore Wakey (A3300) over BLE from Linux.

Protocol reverse-engineered from https://github.com/mthnmhn/wakeysync

Usage examples:
  python3 wakey_sync_time.py --time 10:00
  python3 wakey_sync_time.py --time 14:30:00
  python3 wakey_sync_time.py --time 2026-11-04T10:00:00
  python3 wakey_sync_time.py --scan-only
  python3 wakey_sync_time.py --address AA:BB:CC:DD:EE:FF --time 10:00
  python3 wakey_sync_time.py --address AA:BB:CC:DD:EE:FF --time 10:00 --flag 0x01
  python3 wakey_sync_time.py --address AA:BB:CC:DD:EE:FF --time 10:00 --dump-gatt

Trailing body byte (flag) — verified on device:
  0x00  12-hour (AM/PM)
  0x01  24-hour + sun icon (best default)
  0x18  24-hour without sun icon
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.characteristic import BleakGATTCharacteristic
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("Missing dependency: bleak", file=sys.stderr)
    print("Install with:  pip install --user bleak", file=sys.stderr)
    print("Or in a venv:   python3 -m venv .venv && . .venv/bin/activate && pip install bleak", file=sys.stderr)
    sys.exit(1)

SERVICE_UUID = "0109f5da-0000-1000-8000-00805f9b34fb"
# Vendor short IDs as seen in PacketLogger / wakeysync (not Bluetooth SIG base UUIDs)
WRITE_SHORT = "7777"
NOTIFY_SHORT = "8888"
DEVICE_NAME_HINTS = ("soundcore wakey", "wakey")


def build_time_packet(dt: datetime, flag: int = 0x01) -> bytes:
    """Build Soundcore Wakey time-sync frame (command 0x8101).

    Body: year_since_2000, month, day, hour, minute, second, flag
    flag (verified):
      0x00 → 12h AM/PM
      0x01 → 24h + sun icon (recommended default)
      0x18 → 24h without sun icon
    """
    if dt.year < 2000 or dt.year > 2255:
        raise ValueError(f"Year out of range for year_since_2000 encoding: {dt.year}")
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


def parse_time_arg(raw: str) -> datetime:
    """Parse HH:MM, HH:MM:SS or ISO-like datetime. Date defaults to today."""
    raw = raw.strip()
    today = datetime.now().replace(microsecond=0)

    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%H:%M:%S",
        "%H:%M",
    ):
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt in ("%H:%M", "%H:%M:%S"):
                return today.replace(
                    hour=parsed.hour,
                    minute=parsed.minute,
                    second=getattr(parsed, "second", 0) or 0,
                )
            return parsed
        except ValueError:
            continue

    raise argparse.ArgumentTypeError(
        f"Cannot parse time '{raw}'. Use HH:MM, HH:MM:SS or YYYY-MM-DDTHH:MM:SS"
    )


def normalize_uuid(u: str) -> str:
    return u.lower().replace("-", "")


def is_short_uuid(actual: str, short4: str) -> bool:
    """
    Match vendor 16-bit style UUID 7777 / 8888 without confusing them with
    standard SIG characteristics that share the Bluetooth base UUID suffix.
    Accepts:
      - "7777"
      - "00007777-0000-1000-8000-00805f9b34fb"
      - any UUID whose 16-bit code field (bytes 2-3 of 128-bit form) is 7777
        when using the Bluetooth base, OR whose compact form equals/ends with 7777
        in the vendor-service sense used by Soundcore traces.
    """
    short4 = short4.lower()
    a = normalize_uuid(actual)

    if a == short4:
        return True

    # Standard expansion of 16-bit UUID: 0000XXXX-0000-1000-8000-00805f9b34fb
    if len(a) == 32 and a.startswith("0000") and a.endswith("00001000800000805f9b34fb"):
        return a[4:8] == short4

    # Some stacks expose bare 16-bit as 4 hex chars already handled above.
    # Also accept if the only non-zero identity is the short code in vendor form.
    if a.endswith(short4) and len(a) in (4, 8):
        return True

    return False


def device_looks_like_wakey(device: BLEDevice, adv: AdvertisementData) -> bool:
    names = []
    if device.name:
        names.append(device.name.lower())
    if adv.local_name:
        names.append(adv.local_name.lower())
    for name in names:
        for hint in DEVICE_NAME_HINTS:
            if hint in name:
                return True

    if adv.service_uuids:
        target = normalize_uuid(SERVICE_UUID)
        for su in adv.service_uuids:
            if normalize_uuid(su) == target:
                return True

    # Classic MAC embedded little-endian in manufacturer payload is a strong hint.
    # Full LE MAC is 6 bytes; bleak splits company_id (2) + rest.
    if adv.manufacturer_data:
        for company_id, payload in adv.manufacturer_data.items():
            blob = company_id.to_bytes(2, "little") + bytes(payload)
            if len(blob) >= 6:
                # Any 6-byte sequence is possible; accept Anker-ish OUI prefixes.
                # Anker/Soundcore often AC:B1:EE / similar in captures.
                oui = blob[3:6]  # last 3 of LE MAC = first 3 of classic
                if oui in (bytes.fromhex("acb1ee"), bytes.fromhex("acb1ef")):
                    return True
                # Fallback: if payload length looks like MAC remainder, still candidate
                if len(blob) == 6:
                    return True

    return False


async def scan_devices(scan_seconds: float) -> list[tuple[BLEDevice, AdvertisementData]]:
    print(f"Scanning BLE for {scan_seconds:.0f}s ...")
    found: dict[str, tuple[BLEDevice, AdvertisementData]] = {}

    def callback(device: BLEDevice, adv: AdvertisementData) -> None:
        if device_looks_like_wakey(device, adv):
            found[device.address] = (device, adv)

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    await asyncio.sleep(scan_seconds)
    await scanner.stop()

    results = list(found.values())
    if not results:
        print("No device matched name/service/manufacturer filter. Showing all discovered devices:")
        devices = await BleakScanner.discover(timeout=scan_seconds)
        for d in devices:
            print(f"  {d.address}  rssi={getattr(d, 'rssi', '?')}  name={d.name!r}")
    return results


def dump_gatt(client: BleakClient) -> None:
    print("GATT map:")
    for service in client.services:
        print(f"  Service {service.uuid}")
        for char in service.characteristics:
            props = ",".join(char.properties)
            print(f"    Char {char.uuid}  handle={char.handle}  props=[{props}]")
            for desc in char.descriptors:
                print(f"      Desc {desc.uuid}  handle={desc.handle}")


def find_char_by_short(client: BleakClient, short4: str) -> Optional[BleakGATTCharacteristic]:
    for service in client.services:
        for char in service.characteristics:
            if is_short_uuid(char.uuid, short4):
                return char
    return None


def find_writable_vendor_char(client: BleakClient) -> Optional[BleakGATTCharacteristic]:
    """Prefer 7777; else any writable char under the known vendor service."""
    write_char = find_char_by_short(client, WRITE_SHORT)
    if write_char is not None:
        return write_char

    target_svc = normalize_uuid(SERVICE_UUID)
    for service in client.services:
        if normalize_uuid(service.uuid) != target_svc:
            continue
        for char in service.characteristics:
            props = set(char.properties)
            if "write" in props or "write-without-response" in props:
                return char
    return None


async def sync_time(
    address: Optional[str],
    dt: datetime,
    scan_seconds: float,
    listen_seconds: float,
    write_with_response: bool,
    dump_gatt_flag: bool,
    settle_seconds: float,
    flag: int = 0x01,
) -> int:
    target_address = address

    if not target_address:
        matches = await scan_devices(scan_seconds)
        if not matches:
            print("Wakey not found. Power it on, stay nearby, retry with --scan-only.", file=sys.stderr)
            return 2
        if len(matches) > 1:
            print("Multiple candidates:")
            for d, adv in matches:
                print(f"  {d.address}  name={d.name or adv.local_name!r}")
            print("Pass --address explicitly.", file=sys.stderr)
            return 3
        device, adv = matches[0]
        target_address = device.address
        print(f"Found: {target_address}  name={device.name or adv.local_name!r}")
    else:
        print(f"Using address: {target_address}")

    packet = build_time_packet(dt, flag=flag)
    print(f"Target wall-clock time: {dt.isoformat(sep=' ')}")
    print(f"Flag byte: 0x{flag:02x}")
    print(f"Packet ({len(packet)} B): {packet.hex(' ')}")

    notification_event = asyncio.Event()
    notifications: list[bytes] = []

    def on_notify(_handle: int, data: bytearray) -> None:
        b = bytes(data)
        notifications.append(b)
        print(f"Notify: {b.hex(' ')}")
        notification_event.set()

    print(f"Connecting to {target_address} ...")
    async with BleakClient(target_address, timeout=30.0) as client:
        if not client.is_connected:
            print("Failed to connect.", file=sys.stderr)
            return 4

        print("Connected.")
        if settle_seconds > 0:
            print(f"Waiting {settle_seconds:.1f}s for services to settle ...")
            await asyncio.sleep(settle_seconds)

        if dump_gatt_flag or True:
            # Always dump when 7777 missing; optional always via flag handled below
            pass

        write_char = find_writable_vendor_char(client)
        notify_char = find_char_by_short(client, NOTIFY_SHORT)

        if write_char is None or dump_gatt_flag:
            dump_gatt(client)

        if write_char is None:
            print(
                "Write characteristic 7777 (or writable char on vendor service) not found.\n"
                "If GATT only shows generic services, try:\n"
                "  - closer range, Wakey plugged in\n"
                "  - disconnect phone Soundcore app\n"
                "  - --settle-seconds 2\n"
                "  - reboot BT: bluetoothctl power off && bluetoothctl power on",
                file=sys.stderr,
            )
            return 5

        print(
            f"Write char: {write_char.uuid} handle={write_char.handle} "
            f"props={write_char.properties}"
        )

        if notify_char is not None:
            print(f"Notify char: {notify_char.uuid} handle={notify_char.handle}")
            try:
                await client.start_notify(notify_char, on_notify)
            except Exception as exc:
                print(f"Could not enable notifications (continuing): {exc}")

        props = set(write_char.properties)
        response = write_with_response
        if not response:
            if "write-without-response" in props:
                response = False
            elif "write" in props:
                response = True
                print("No write-without-response; using write-with-response")
            else:
                print(f"Characteristic not writable: {write_char.properties}", file=sys.stderr)
                return 6

        print(f"Writing packet (response={response}) ...")
        await client.write_gatt_char(write_char, packet, response=response)
        print("Write completed.")

        if listen_seconds > 0:
            print(f"Listening for notifications up to {listen_seconds:.1f}s ...")
            try:
                await asyncio.wait_for(notification_event.wait(), timeout=listen_seconds)
            except asyncio.TimeoutError:
                if not notifications:
                    print("No notification received (device may still have accepted the write).")

        if notify_char is not None:
            try:
                await client.stop_notify(notify_char)
            except Exception:
                pass

    print("Done. Check the Wakey display.")
    return 0


async def scan_only(scan_seconds: float) -> int:
    matches = await scan_devices(scan_seconds)
    if matches:
        print(f"Matched {len(matches)} device(s):")
        for d, adv in matches:
            print(f"  {d.address}  name={d.name or adv.local_name!r}  rssi={adv.rssi}")
            if adv.manufacturer_data:
                for k, v in adv.manufacturer_data.items():
                    blob = k.to_bytes(2, "little") + bytes(v)
                    print(f"    manufacturer company=0x{k:04x} payload={bytes(v).hex(' ')}")
                    print(f"    raw LE bytes: {blob.hex(' ')}")
            if adv.service_uuids:
                print(f"    service_uuids: {adv.service_uuids}")
    return 0 if matches else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set Soundcore Wakey display time over BLE (no official app)."
    )
    parser.add_argument(
        "--time",
        type=parse_time_arg,
        help="Time to set, e.g. 10:00 or 14:30:00 or 2026-11-04T10:00:00 (local wall-clock)",
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Use current local wall-clock time (for HA daily automation)",
    )
    parser.add_argument(
        "--address",
        default=os.environ.get("WAKEY_ADDRESS"),
        help="BLE MAC address (or env WAKEY_ADDRESS)",
    )
    parser.add_argument("--scan-only", action="store_true", help="Only scan and list devices")
    parser.add_argument("--scan-seconds", type=float, default=8.0, help="Scan duration (default 8)")
    parser.add_argument(
        "--listen-seconds",
        type=float,
        default=2.0,
        help="Wait for notify after write (default 2)",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=1.0,
        help="Delay after connect before using GATT (default 1)",
    )
    parser.add_argument(
        "--write-with-response",
        action="store_true",
        help="Force GATT write-with-response instead of write command",
    )
    parser.add_argument(
        "--dump-gatt",
        action="store_true",
        help="Always print full GATT service/characteristic map",
    )
    parser.add_argument(
        "--flag",
        type=lambda s: int(s, 0),
        default=int(os.environ.get("WAKEY_FLAG", "0x01"), 0),
        help=(
            "Trailing body flag byte (default 0x01 = 24h + sun). "
            "0x00=12h AM/PM, 0x01=24h+sun, 0x18=24h no sun. "
            "Also env WAKEY_FLAG."
        ),
    )
    args = parser.parse_args()

    if args.scan_only:
        return asyncio.run(scan_only(args.scan_seconds))

    if args.now and args.time is not None:
        parser.error("Use either --now or --time, not both")

    if args.now:
        dt = datetime.now().replace(microsecond=0)
    elif args.time is not None:
        dt = args.time
    else:
        parser.error("Provide --now or --time HH:MM (or --scan-only)")

    if not args.address:
        parser.error("Provide --address or set WAKEY_ADDRESS")

    return asyncio.run(
        sync_time(
            address=args.address,
            dt=dt,
            scan_seconds=args.scan_seconds,
            listen_seconds=args.listen_seconds,
            write_with_response=args.write_with_response,
            dump_gatt_flag=args.dump_gatt,
            settle_seconds=args.settle_seconds,
            flag=args.flag,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
