"""Number entity — Set custom speed RPM — for the Jandy iQPUMP01 integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALLDATA_CUSTOM_RPM,
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DOMAIN,
    PUMP_RPM_MAX,
    PUMP_RPM_MIN,
)
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
            IQPumpSpeedNumber(
                coordinator=data["coordinator"],
                client=data["client"],
                serial=data["serial"],
                device_name=entry.data[CONF_DEVICE_NAME],
            )
        ]
    )


class IQPumpSpeedNumber(IQPumpBaseEntity, NumberEntity):
    """Set the pump custom speed RPM.

    This value is used when the pump switch is turned on (opmode=1 / custom
    speed). The pump runs at this RPM until stopped or until the schedule
    resumes.
    """

    _attr_name = "Custom Speed RPM"
    _attr_icon = "mdi:gauge"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = float(PUMP_RPM_MIN)
    _attr_native_max_value = float(PUMP_RPM_MAX)
    _attr_native_step = 50.0
    _attr_native_unit_of_measurement = "RPM"

    def __init__(self, coordinator, client, serial, device_name) -> None:
        super().__init__(coordinator, client, serial, device_name)
        self._attr_unique_id = f"{serial}_custom_rpm"

    @property
    def native_value(self) -> float | None:
        value = self._pump.get(ALLDATA_CUSTOM_RPM)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        rpm = int(round(value / 50) * 50)  # snap to 50-RPM increments
        rpm = max(PUMP_RPM_MIN, min(PUMP_RPM_MAX, rpm))
        _LOGGER.debug("Setting pump custom RPM to %d (serial=%s)", rpm, self._serial)
        await self._client.set_custom_rpm(self._serial, rpm)
        await self.coordinator.async_request_refresh()
