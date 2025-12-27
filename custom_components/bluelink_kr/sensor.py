from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE

from .const import DEFAULT_NAME, DOMAIN, DRIVING_RANGE_UNIT_MAP
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
        [
            BluelinkDrivingRangeSensor(coordinator, entry.entry_id, entry.title),
            BluelinkOdometerSensor(coordinator, entry.entry_id, entry.title),
            BluelinkChargingSocSensor(coordinator, entry.entry_id, entry.title),
        ]
    )


class BluelinkDrivingRangeSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Sensor reporting the driving range of the selected vehicle."""

    _attr_icon = "mdi:car-connected"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{entry_title} Driving Range"
        self._attr_unique_id = f"{entry_id}_driving_range"

    @property
    def native_value(self) -> float | None:
        driving_range = self.coordinator.data.get("driving_range") or {}
        value = driving_range.get("value")
        return float(value) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        driving_range = self.coordinator.data.get("driving_range") or {}
        unit = driving_range.get("unit")
        if unit is None:
            return None
        return DRIVING_RANGE_UNIT_MAP.get(unit, str(unit))

    @property
    def extra_state_attributes(self) -> dict:
        driving_range = self.coordinator.data.get("driving_range") or {}
        return {
            "timestamp": driving_range.get("timestamp"),
            "phev_total_value": driving_range.get("phevTotalValue"),
            "phev_total_unit": driving_range.get("phevTotalUnit"),
            "msg_id": driving_range.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
            "raw_unit": driving_range.get("unit"),
        }


class BluelinkOdometerSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Sensor reporting the odometer of the selected vehicle."""

    _attr_icon = "mdi:counter"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{entry_title} Odometer"
        self._attr_unique_id = f"{entry_id}_odometer"

    @property
    def native_value(self) -> int | None:
        odometer = self._latest_odometer()
        value = odometer.get("value")
        return int(value) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        odometer = self._latest_odometer()
        unit = odometer.get("unit")
        if unit is None:
            return None
        return DRIVING_RANGE_UNIT_MAP.get(unit, str(unit))

    def _latest_odometer(self) -> dict:
        odometer = self.coordinator.data.get("odometer") or {}
        odometers = odometer.get("odometers") or []
        if odometers:
            return odometers[0]
        return {}

    @property
    def extra_state_attributes(self) -> dict:
        odometer_entry = self._latest_odometer()
        odometer = self.coordinator.data.get("odometer") or {}
        return {
            "msg_id": odometer.get("msgId"),
            "timestamp": odometer_entry.get("timestamp"),
            "date": odometer_entry.get("date"),
            "raw_unit": odometer_entry.get("unit"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingSocSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Sensor reporting EV SOC and charging status."""

    _attr_icon = "mdi:ev-station"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{entry_title} EV SOC"
        self._attr_unique_id = f"{entry_id}_ev_soc"

    @property
    def native_value(self) -> float | None:
        charging = self.coordinator.data.get("charging_status") or {}
        soc = charging.get("soc")
        return float(soc) if soc is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        charging = self.coordinator.data.get("charging_status") or {}
        remain = charging.get("remainTime") or {}
        target = charging.get("targetSOC") or {}
        return {
            "battery_charge": charging.get("batteryCharge"),
            "battery_plugin": charging.get("batteryPlugin"),
            "target_soc_plug_type": target.get("plugType"),
            "target_soc_level": target.get("targetSOClevel"),
            "remain_time_value": remain.get("value"),
            "remain_time_unit": remain.get("unit"),
            "timestamp": charging.get("timestamp"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }
