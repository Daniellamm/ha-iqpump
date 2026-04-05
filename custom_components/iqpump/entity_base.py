"""Shared base entity for all iQPUMP01 entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import IQPumpApiClient
from .const import DOMAIN, NAME


class IQPumpBaseEntity(CoordinatorEntity):
    """Base entity for all iQPUMP01 entities.

    Reads pump state from the shared DataUpdateCoordinator and exposes a
    common DeviceInfo so all entities appear under the same HA device.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: IQPumpApiClient,
        serial: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._serial = serial
        self._device_name = device_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=device_name,
            manufacturer="Jandy / Zodiac",
            model="iQPUMP01 (i2d)",
        )

    @property
    def _pump(self) -> dict:
        """Return the pump sub-dict from the latest coordinator data."""
        from .api import IQPumpApiClient  # local import to avoid circular
        return IQPumpApiClient.extract_pump_state(self.coordinator.data or {})
