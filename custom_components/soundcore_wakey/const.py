"""Constants for Soundcore Wakey time sync."""

DOMAIN = "soundcore_wakey"

# BLE (from wakeysync / PacketLogger)
SERVICE_UUID = "0109f5da-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "00007777-0000-1000-8000-00805f9b34fb"

# Display flag: 0x01 = 24h + sun/moon (verified on device)
DEFAULT_FLAG = 0x01

CONF_ADDRESS = "address"
CONF_FLAG = "flag"

DEFAULT_NAME = "Soundcore Wakey"
