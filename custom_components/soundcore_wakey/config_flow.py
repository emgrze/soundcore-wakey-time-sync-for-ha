"""Config flow for Soundcore Wakey — UI setup."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_ADDRESS, CONF_FLAG, DEFAULT_FLAG, DEFAULT_NAME, DOMAIN

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}([0-9A-Fa-f]{2})$")


def _normalize_mac(raw: str) -> str:
    raw = raw.strip().replace("-", ":").upper()
    if not _MAC_RE.match(raw):
        raise ValueError("invalid_mac")
    return raw


class SoundcoreWakeyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Soundcore Wakey."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                address = _normalize_mac(user_input[CONF_ADDRESS])
            except ValueError:
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                flag = int(user_input.get(CONF_FLAG, DEFAULT_FLAG))
                name = user_input.get(CONF_NAME) or DEFAULT_NAME

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_FLAG: flag,
                        CONF_NAME: name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default="D3:B1:EE:26:14:B3"): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_FLAG, default=DEFAULT_FLAG): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=255,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
