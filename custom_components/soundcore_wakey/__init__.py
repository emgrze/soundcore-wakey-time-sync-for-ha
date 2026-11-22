"""Soundcore Wakey — sync display time over BLE from Home Assistant host."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .ble import async_sync_time
from .const import CONF_ADDRESS, CONF_FLAG, DEFAULT_FLAG, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON]

SERVICE_SYNC_TIME = "sync_time"

SERVICE_SYNC_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional(CONF_ADDRESS): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from YAML is not used; config entries only."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Soundcore Wakey from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_sync(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        address_override = call.data.get(CONF_ADDRESS)

        target_entry: ConfigEntry | None = None
        if entry_id:
            target_entry = hass.data[DOMAIN].get(entry_id)
        elif address_override:
            for e in hass.data[DOMAIN].values():
                if e.data.get(CONF_ADDRESS, "").upper() == address_override.upper():
                    target_entry = e
                    break
        elif len(hass.data[DOMAIN]) == 1:
            target_entry = next(iter(hass.data[DOMAIN].values()))
        else:
            raise HomeAssistantError(
                "Podaj entry_id albo address (masz więcej niż jeden Wakey)."
            )

        if target_entry is None:
            raise HomeAssistantError("Nie znaleziono konfiguracji Soundcore Wakey.")

        address = target_entry.data[CONF_ADDRESS]
        flag = int(target_entry.data.get(CONF_FLAG, DEFAULT_FLAG))

        try:
            await async_sync_time(hass, address, dt=datetime.now(), flag=flag)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Wakey sync failed")
            raise HomeAssistantError(f"Sync nieudany: {err}") from err

    if not hass.services.has_service(DOMAIN, SERVICE_SYNC_TIME):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SYNC_TIME,
            _handle_sync,
            schema=SERVICE_SYNC_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SYNC_TIME)
    return unload_ok
