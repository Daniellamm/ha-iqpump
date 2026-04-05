"""Switch entity — Pump on/off — for the Jandy iQPUMP01 integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, CONF_SERIAL, DOMAIN, SHADOW_PUMP_STATE
from .entity_base import IQPumpBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            IQPumpSwitch(
                coordinator=data["coordinator"],
                client=data["client"],
                serial=data["serial"],
                device_name=entry.data[CONF_DEVICE_NAME],
            )
        ]
    )


class IQPumpSwitch(IQPumpBaseEntity, SwitchEntity):
    """Controls pump power (on / off)."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:pump"
    _attr_name = "Pump Power"

    def __init__(self, coordinator, client, serial, device_name) -> None:
        super().__init__(coordinator, client, serial, device_name)
        self._attr_unique_id = f"{serial}_pump_power"

    @property
    def is_on(self) -> bool | None:
        state = self._pump.get(SHADOW_PUMP_STATE)
        if state is None:
            return None
        return bool(int(state))

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug("Turning pump ON (serial=%s)", self._serial)
        await self._client.set_state(self._serial, {SHADOW_PUMP_STATE: 1})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.debug("Turning pump OFF (serial=%s)", self._serial)
        await self._client.set_state(self._serial, {SHADOW_PUMP_STATE: 0})
        await self.coordinator.async_request_refresh()
