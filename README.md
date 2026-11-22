# Soundcore Wakey for Home Assistant

Sync the clock on an **Anker Soundcore Wakey (A3300)** over BLE from the Home Assistant host — no phone and no official app required.

After install you get a **Sync time** button and the `soundcore_wakey.sync_time` service.

## Requirements

- Home Assistant **2026.11+** with a working **Bluetooth** integration (BLE adapter on the HA host)
- Soundcore Wakey within BLE range
- The Soundcore app should **not** hold an active BLE connection to the radio while syncing

## Install via Marketplace

Home Assistant 2026.11+ includes the community store as **Settings → Marketplace** (formerly HACS).

1. **Settings → Marketplace**
2. **Add from link** → paste the GitHub repo URL, e.g.  
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

Based on reverse engineering of [mthnmhn/wakeysync](https://github.com/mthnmhn/wakeysync) (macOS app).

## Finding the BLE address

On Linux (host with BlueZ):

```bash
python3 tools/wakey_sync_time.py --scan-only
```

Or use `bluetoothctl scan on` and look for nearby devices / manufacturer data.

## Troubleshooting

- **Connect failed** — check range, `bluetoothctl power on`, disconnect the phone from the Wakey  
- **Display does not change** — use flag `1`, check HA logs (`soundcore_wakey`)  
- **HAOS / Bluetooth** — the adapter must be visible to Core (Bluetooth integration works)

## License

MIT
