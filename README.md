# Soundcore Wakey for Home Assistant

Sync the clock on an **Anker Soundcore Wakey (A3300)** over BLE from the Home Assistant host — no phone and no official app required.

After install you get a **Sync time** button and the `soundcore_wakey.sync_time` service.

## Credits

The BLE time-sync protocol used here was reverse-engineered by **[mthnmhn](https://github.com/mthnmhn)** for the macOS app **[wakeysync](https://github.com/mthnmhn/wakeysync)**. This Home Assistant integration reuses that work so the Wakey can be kept in sync without the official Soundcore app or a phone.

## Requirements

- Home Assistant **2026.11+** with a working **Bluetooth** integration (BLE adapter on the HA host)
- On Docker: the HA container typically needs host networking and access to the system D-Bus (`/var/run/dbus`) so BlueZ is reachable
- Soundcore Wakey within BLE range
- The Soundcore app should **not** hold an active BLE connection to the radio while syncing

## Install via Marketplace

Home Assistant 2026.11+ includes the community store as **Settings → Marketplace** (formerly HACS).

1. **Settings → Marketplace**
2. **Add from link** → paste the GitHub repo URL:  
   `https://github.com/emgrze/soundcore-wakey-time-sync-for-ha`
3. Confirm category **Integration** (if asked)
4. **Install**
5. Complete the setup flow (BLE address, e.g. `AA:BB:CC:DD:EE:FF`, flag `1`)

Custom repositories need a one-time GitHub device sign-in in Marketplace. Browsing the default catalog does not.

On a first install, HA often opens the integration setup immediately (no separate restart). Updates may still require a restart.

## Manual install

Copy `custom_components/soundcore_wakey` into `/config/custom_components/`, restart HA, then:

**Settings → Devices & services → Add integration → Soundcore Wakey**

## Usage

| Action | How |
|--------|-----|
| Manual sync | **Sync time** button on the device |
| Service | `soundcore_wakey.sync_time` |
| Daily | Automation: `time` trigger → `button.press` / `soundcore_wakey.sync_time` |

The time sent is the HA host **local wall-clock** (HA timezone).

Writes use **GATT write-with-response** and a short settle delay after connect (more reliable on some BlueZ hosts than write-without-response).

## Display flag

| Value | Effect |
|-------|--------|
| `0` | 12-hour (AM/PM) |
| `1` | **24-hour + sun/moon** (recommended) |
| `24` (`0x18`) | 24-hour without icon |

With flag `1`, the sun/moon icon is chosen by firmware:

- **sun** 06:00–21:59  
- **moon** 22:00–05:59  

## Protocol (summary)

- Write GATT characteristic: `00007777-0000-1000-8000-00805f9b34fb`
- Time packet (cmd `0x8101`):  
  `08 ee 00 00 00 01 81 10 00` + `YY MM DD HH MM SS FLAG`  
  (`YY = year − 2000`)

See [wakeysync](https://github.com/mthnmhn/wakeysync) for the original reverse-engineering notes and macOS client.
  
## Finding the BLE address / CLI test

On Linux (host with BlueZ and [bleak](https://github.com/hbldh/bleak)):

```bash
python3 -m venv /tmp/wakey-venv
/tmp/wakey-venv/bin/pip install bleak

/tmp/wakey-venv/bin/python tools/wakey_sync_time.py --scan-only
/tmp/wakey-venv/bin/python tools/wakey_sync_time.py --address AA:BB:CC:DD:EE:FF --time 10:00 --flag 0x01
/tmp/wakey-venv/bin/python tools/wakey_sync_time.py --address AA:BB:CC:DD:EE:FF --now --flag 0x01
```

Or use `bluetoothctl scan on` and look for nearby devices / manufacturer data.

## Troubleshooting

- **Connect failed** — check range, `bluetoothctl power on`, disconnect the phone from the Wakey  
- **Log says write completed but display does not change** — disconnect the Soundcore app; retry; try setting a clearly different time (e.g. `10:00` via CLI); confirm flag `1` for 24h  
- **No notification after write** — normal on many Linux/BlueZ setups; the device may still accept the write  
- **HAOS / Docker / Bluetooth** — the adapter must be visible to Core (Bluetooth integration works)

## License

MIT
