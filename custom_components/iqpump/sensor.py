"""Sensor entities for the Jandy iQPUMP01 integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfElectricCurrent, REVOLUTIONS_PER_MINUTE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DOMAIN,
    SHADOW_PUMP_RPM,
    SHADOW_PUMP_SPEED,
    SHADOW_PUMP_WATTS,
)
from .entity_base import IQPumpBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IQPumpSensorDescription(SensorEntityDescription):
    """Describes an iQPUMP sensor, including the shadow field key."""

    shadow_key: str = ""


SENSORS: tuple[IQPumpSensorDescription, ...] = (
    IQPumpSensorDescription(
        key="rpm",
        shadow_key=SHADOW_PUMP_RPM,
        name="Pump RPM",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:rotate-right",
    ),
    IQPumpSensorDescription(
        key="watts",
        shadow_key=SHADOW_PUMP_WATTS,
        name="Power Draw",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    IQPumpSensorDescription(
        key="speed",
        shadow_key=SHADOW_PUMP_SPEED,
        name="Speed Preset",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            IQPumpSensor(
                coordinator=data["coordinator"],
                client=data["client"],
                serial=data["serial"],
                device_name=entry.data[CONF_DEVICE_NAME],
                description=desc,
            )
            for desc in SENSORS
        ]
    )


class IQPumpSensor(IQPumpBaseEntity, SensorEntity):
    """A read-only sensor reading a single field from the pump shadow."""

    entity_description: IQPumpSensorDescription

    def __init__(self, coordinator, client, serial, device_name, description: IQPumpSensorDescription) -> None:
        super().__init__(coordinator, client, serial, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        value = self._pump.get(self.entity_description.shadow_key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
