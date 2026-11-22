"""Button entity — press to sync Wakey time now."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble import async_sync_time
from .const import CONF_ADDRESS, CONF_FLAG, DEFAULT_FLAG, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WakeySyncButton(entry)])


class WakeySyncButton(ButtonEntity):
    """Press to send current local time to the Wakey over BLE."""

    _attr_has_entity_name = True
    _attr_name = "Sync time"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_sync_time"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, address)},
            "name": entry.data.get(CONF_NAME) or "Soundcore Wakey",
            "manufacturer": "Anker / Soundcore",
            "model": "Wakey A3300",
            "connections": {("bluetooth", address)},
        }

    async def async_press(self) -> None:
        address = self._entry.data[CONF_ADDRESS]
        flag = int(self._entry.data.get(CONF_FLAG, DEFAULT_FLAG))
        try:
            await async_sync_time(
                self.hass,
                address,
                dt=datetime.now().replace(microsecond=0),
                flag=flag,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Wakey button sync failed")
            raise HomeAssistantError(f"Sync nieudany: {err}") from err
