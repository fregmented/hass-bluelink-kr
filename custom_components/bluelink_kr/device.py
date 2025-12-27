from __future__ import annotations

from typing import Any

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def _extract_car_id(device: dr.DeviceEntry) -> str | None:
    for domain, value in device.identifiers:
        if domain == DOMAIN:
            return value
    return None


async def async_sync_selected_vehicle(
    hass,
    entry,
    *,
    selected_car: dict[str, Any] | None,
    selected_car_id: str | None,
) -> None:
    """Create or update the selected vehicle device, disable missing ones."""
    registry = dr.async_get(hass)
    active_ids: set[str] = set()

    if selected_car and selected_car_id:
        name = (
            selected_car.get("carNickname")
            or selected_car.get("carName")
            or selected_car_id
        )
        model = selected_car.get("carType")
        sw = selected_car.get("carSellname")

        device = registry.async_get_device({(DOMAIN, selected_car_id)})
        if device is None:
            device = registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, selected_car_id)},
                manufacturer="Hyundai",
                model=model,
                name=name,
                sw_version=sw,
            )
        updates: dict[str, Any] = {}
        if device.name != name:
            updates["name"] = name
        if device.model != model:
            updates["model"] = model
        if device.sw_version != sw:
            updates["sw_version"] = sw
        if device.disabled_by == dr.DeviceEntryDisabler.INTEGRATION:
            updates["disabled_by"] = None
        if updates:
            registry.async_update_device(device.id, **updates)
        active_ids.add(selected_car_id)

    # Disable devices not present anymore
    for device in registry.async_entries_for_config_entry(entry.entry_id):
        car_id = _extract_car_id(device)
        if not car_id or car_id in active_ids:
            continue
        if device.disabled_by in (None, dr.DeviceEntryDisabler.INTEGRATION):
            registry.async_update_device(
                device.id, disabled_by=dr.DeviceEntryDisabler.INTEGRATION
            )
