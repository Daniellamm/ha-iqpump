"""Config flow for the Jandy iQPUMP01 integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IQPumpApiClient, IQPumpApiError, IQPumpAuthError, IQPumpNoDeviceError
from .const import (
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_and_discover(
    hass: HomeAssistant, email: str, password: str
) -> list[dict]:
    """Validate credentials and return list of i2d devices."""
    session = async_get_clientsession(hass)
    client = IQPumpApiClient(session)
    await client.login(email, password)
    return await client.get_devices()


class IQPumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for iQPUMP01."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._devices: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: collect credentials and discover devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]

            try:
                devices = await _validate_and_discover(self.hass, email, password)
            except IQPumpAuthError:
                errors["base"] = "invalid_auth"
            except IQPumpNoDeviceError:
                errors["base"] = "no_device"
            except IQPumpApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during iQPump setup")
                errors["base"] = "unknown"
            else:
                self._email = email
                self._password = password
                self._devices = devices

                if len(devices) == 1:
                    # Only one device — skip the picker
                    return await self._create_entry(devices[0])

                # Multiple i2d devices — let the user pick
                return await self.async_step_pick_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"name": NAME},
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 (optional): pick which i2d device to use."""
        if user_input is not None:
            serial = user_input[CONF_SERIAL]
            device = next(d for d in self._devices if d["serial_number"] == serial)
            return await self._create_entry(device)

        device_options = {
            d["serial_number"]: f"{d.get('name') or 'iQPUMP01'} ({d['serial_number']})"
            for d in self._devices
        }

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_SERIAL): vol.In(device_options)}
            ),
        )

    async def _create_entry(self, device: dict) -> config_entries.FlowResult:
        """Create the config entry for a chosen device."""
        serial = device["serial_number"]
        # name is null for devices that have never been named in the app
        device_name = device.get("name") or f"iQPUMP01 ({serial})"

        # Prevent duplicate entries for the same device
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device_name,
            data={
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_SERIAL: serial,
                CONF_DEVICE_NAME: device_name,
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return IQPumpOptionsFlow(config_entry)


class IQPumpOptionsFlow(config_entries.OptionsFlow):
    """Options flow — allows re-entering credentials after auth failure."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await _validate_and_discover(self.hass, email, password)
            except (IQPumpAuthError, IQPumpNoDeviceError, IQPumpApiError) as err:
                errors["base"] = "invalid_auth" if isinstance(err, IQPumpAuthError) else "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self.config_entry.data.get(CONF_EMAIL, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
