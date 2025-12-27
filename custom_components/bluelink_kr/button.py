from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BluelinkCoordinator
from .const import DOMAIN
from .sensor import _car_unique_id, _device_info_from_coordinator, _entity_base_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 현대 블루링크 buttons based on a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: BluelinkCoordinator = runtime["coordinator"]
    async_add_entities(
        [BluelinkForceRefreshButton(coordinator, entry.entry_id, entry.title)]
    )


class BluelinkForceRefreshButton(
    CoordinatorEntity[BluelinkCoordinator], ButtonEntity
):
    """Button to force a data refresh."""

    _attr_icon = "mdi:refresh"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Force Refresh"
        car_uid = _car_unique_id(coordinator, entry_id)
        self._attr_unique_id = f"{car_uid}_force_refresh"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_force_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Force refresh failed: %s", err)
            await self.coordinator.async_request_refresh()
