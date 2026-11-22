# Soundcore Wakey for Home Assistant

Synchronizacja czasu na **Anker Soundcore Wakey (A3300)** przez BLE z hosta Home Assistant — bez telefonu i bez oficjalnej aplikacji.

Po instalacji pojawia się przycisk **Sync time** oraz usługa `soundcore_wakey.sync_time`.

## Wymagania

- Home Assistant z działającą integracją **Bluetooth** (adapter BLE na serwerze HA)
- Soundcore Wakey w zasięgu radia BLE
- Apka Soundcore **nie** powinna trzymać aktywnego połączenia BLE z radiem w momencie syncu

## Instalacja przez HACS

1. HACS → **Integrations** → menu (⋮) → **Custom repositories**
2. Repository URL: `https://github.com/TWOJ_USER/soundcore-wakey`
3. Category: **Integration**
4. Add → wyszukaj **Soundcore Wakey** → Download
5. **Restart** Home Assistant
6. **Ustawienia → Urządzenia i usługi → Dodaj integrację → Soundcore Wakey**
7. Podaj adres BLE (np. `D3:B1:EE:26:14:B3`) i flagę `1`

## Instalacja ręczna

Skopiuj katalog `custom_components/soundcore_wakey` do `/config/custom_components/`, zrestartuj HA, dodaj integrację z UI.

## Użycie

| Akcja | Jak |
|--------|-----|
| Ręczny sync | Przycisk **Sync time** na urządzeniu |
| Usługa | `soundcore_wakey.sync_time` |
| Codziennie | Automation: trigger `time` → `button.press` / `soundcore_wakey.sync_time` |

Czas wysyłany to **lokalny wall-clock** hosta HA (strefa z HA).

## Flaga wyświetlacza

| Wartość | Efekt |
|---------|--------|
| `0` | 12h (AM/PM) |
| `1` | **24h + sun/moon** (zalecane) |
| `24` (`0x18`) | 24h bez ikony |

Ikona sun/moon (przy fladze `1`) jest ustawiana przez firmware:

- **słońce** 06:00–21:59  
- **księżyc** 22:00–05:59  

## Protokół (skrót)

- Write GATT: `00007777-0000-1000-8000-00805f9b34fb`
- Pakiet czasu (cmd `0x8101`):  
  `08 ee 00 00 00 01 81 10 00` + `YY MM DD HH MM SS FLAG`  
  (`YY = year − 2000`)

Oparte na reverse-engineerze projektu [mthnmhn/wakeysync](https://github.com/mthnmhn/wakeysync) (aplikacja macOS).

## Znajdowanie adresu BLE

Na Linuxie (host z BlueZ):

```bash
python3 wakey_sync_time.py --scan-only
```

albo `bluetoothctl scan on` i szukaj urządzenia w pobliżu / manufacturer data.

## Troubleshooting

- **Connect failed** — zasięg, `bluetoothctl power on`, odłącz telefon od Wakeya  
- **Brak zmiany na wyświetlaczu** — flaga `1`, sprawdź logi HA (`soundcore_wakey`)  
- **HAOS** — adapter Bluetooth musi być widoczny dla Core (integracja Bluetooth w HA działa)

## Licencja

MIT
