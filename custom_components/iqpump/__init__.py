"""Jandy iQPUMP01 Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IQPumpApiClient, IQPumpApiError, IQPumpAuthError
from .const import (
    CONF_EMAIL,
    CONF_ID_TOKEN,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_AUTH_TOKEN,
    CONF_USER_ID,
    CONF_SERIAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iQPUMP from a config entry."""
    session = async_get_clientsession(hass)
    client = IQPumpApiClient(session)

    # Restore persisted tokens if available, then verify / refresh them
    client.load_tokens(entry.options)

    try:
        if not entry.options.get(CONF_ID_TOKEN):
            await client.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        else:
            await client.ensure_authenticated()
    except IQPumpAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except IQPumpApiError as err:
        raise ConfigEntryNotReady(f"Cannot connect to iAqualink cloud: {err}") from err

    # Persist refreshed tokens back to the entry
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, **client.dump_tokens()}
    )

    serial = entry.data[CONF_SERIAL]

    async def _async_update_data() -> dict:
        """Fetch latest pump alldata — called by the coordinator."""
        try:
            alldata = await client.get_alldata(serial)
        except IQPumpAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except IQPumpApiError as err:
            raise UpdateFailed(f"Error fetching pump data: {err}") from err

        # Persist updated tokens after every successful poll
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, **client.dump_tokens()}
        )
        return alldata

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{serial}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Initial data fetch — raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "serial": serial,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
