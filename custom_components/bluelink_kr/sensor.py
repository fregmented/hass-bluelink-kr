from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from . import BluelinkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bluelink KR sensors based on a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: BluelinkCoordinator = runtime["coordinator"]
    async_add_entities(
        [BluelinkVehicleCountSensor(coordinator, entry.entry_id, entry.title)]
    )


class BluelinkVehicleCountSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Example sensor reporting the number of vehicles in the account."""

    _attr_icon = "mdi:car-connected"
    _attr_native_unit_of_measurement = "vehicles"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{entry_title} Vehicle Count"
        self._attr_unique_id = f"{entry_id}_vehicle_count"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("vehicle_count", 0)
