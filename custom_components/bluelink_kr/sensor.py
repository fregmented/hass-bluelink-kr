from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE

from .const import DOMAIN, DRIVING_RANGE_UNIT_MAP, TIME_UNIT_MAP
from . import BluelinkCoordinator


def _device_info_from_coordinator(
    coordinator: BluelinkCoordinator,
) -> dict | None:
    car = coordinator.car or {}
    car_id = coordinator.selected_car_id
    if not car_id:
        return None
    name = car.get("carNickname") or car.get("carName") or car_id
    model = (
        car.get("carSellname")
        or car.get("carName")
        or car.get("carType")
    )
    sw = None
    return {
        "identifiers": {(DOMAIN, car_id)},
        "manufacturer": "Hyundai",
        "name": name,
        "model": model,
        "sw_version": sw,
    }


def _entity_base_name(coordinator: BluelinkCoordinator, entry_title: str) -> str:
    """Return the car's nickname/name or fall back to id/title."""
    car = coordinator.car or {}
    return (
        car.get("carNickname")
        or car.get("carName")
        or coordinator.selected_car_id
        or entry_title
    )


def _format_float(value) -> float | None:
    """Return a float rounded to 2 decimals, or 0.0 if missing/invalid."""
    if value is None:
        return 0.0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return float(f"{num:.2f}")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 현대 블루링크 sensors based on a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: BluelinkCoordinator = runtime["coordinator"]
    entities: list[SensorEntity] = [
        BluelinkDrivingRangeSensor(coordinator, entry.entry_id, entry.title),
        BluelinkOdometerSensor(coordinator, entry.entry_id, entry.title),
    ]
    if coordinator.is_ev_capable:
        entities.extend(
            [
                BluelinkChargingSocSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingPlugSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingStateSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingPlugTypeSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingTargetSocSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingRemainTimeSensor(
                    coordinator, entry.entry_id, entry.title
                ),
                BluelinkChargingEstimateTimeSensor(
                    coordinator, entry.entry_id, entry.title
                ),
            ]
        )

    warning_labels: list[tuple[str, str]] = [
        (
            "low_fuel",
            "HV Battery Low Warning"
            if coordinator.car_type == "EV"
            else "Low Fuel Warning",
        ),
        ("tire_pressure", "Tire Pressure Warning"),
        ("lamp_wire", "Lamp Warning"),
        ("smart_key_battery", "Smart Key Battery Warning"),
        ("washer_fluid", "Washer Fluid Warning"),
        ("brake_oil", "Brake Fluid Warning"),
    ]
    if coordinator.car_type != "EV":
        warning_labels.append(("engine_oil", "Engine Oil Warning"))

    for key, label in warning_labels:
        entities.append(
            BluelinkWarningSensor(
                coordinator,
                entry.entry_id,
                entry.title,
                warning_key=key,
                label=label,
            )
        )
    async_add_entities(entities)


class BluelinkDrivingRangeSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Sensor reporting the driving range of the selected vehicle."""

    _attr_icon = "mdi:car-connected"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Driving Range"
        self._attr_unique_id = f"{entry_id}_driving_range"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> float | None:
        driving_range = self.coordinator.data.get("driving_range") or {}
        value = (
            driving_range.get("phevTotalValue")
            if self.coordinator.car_type == "PHEV"
            else driving_range.get("value")
        )
        return _format_float(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        driving_range = self.coordinator.data.get("driving_range") or {}
        unit = (
            driving_range.get("phevTotalUnit")
            if self.coordinator.car_type == "PHEV"
            else driving_range.get("unit")
        )
        if unit is None:
            return None
        return DRIVING_RANGE_UNIT_MAP.get(unit, str(unit))

    @property
    def extra_state_attributes(self) -> dict:
        driving_range = self.coordinator.data.get("driving_range") or {}
        return {
            "timestamp": driving_range.get("timestamp"),
            "phev_total_value": _format_float(driving_range.get("phevTotalValue")),
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
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Odometer"
        self._attr_unique_id = f"{entry_id}_odometer"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> float | None:
        odometer = self._latest_odometer()
        value = odometer.get("value")
        return _format_float(value)

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
            sorted_odometers = sorted(
                odometers, key=lambda item: item.get("timestamp") or ""
            )
            return sorted_odometers[-1]
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


class _BluelinkChargingSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Base class for EV charging sensors."""

    def _charging(self) -> dict:
        return self.coordinator.data.get("charging_status") or {}

    def _battery(self) -> dict:
        return self.coordinator.data.get("battery_status") or {}

    def _is_charging(self) -> bool:
        charging = self._charging()
        return bool(
            charging.get("batteryCharge")
            if "batteryCharge" in charging
            else charging.get("batterCharge")
        )

    def _remain_time(self) -> dict:
        charging = self._charging()
        return charging.get("remainTime") or {}


class BluelinkChargingSocSensor(_BluelinkChargingSensor):
    """Sensor reporting EV SOC and charging status."""

    _attr_icon = "mdi:ev-station"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} EV SOC"
        self._attr_unique_id = f"{entry_id}_ev_soc"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> float | None:
        battery = self._battery()
        soc = battery.get("soc")
        return _format_float(soc)

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        battery = self._battery()
        remain = charging.get("remainTime") or {}
        target = charging.get("targetSOC") or {}
        return {
            "battery_charge": bool(
                charging.get("batteryCharge")
                if "batteryCharge" in charging
                else charging.get("batterCharge")
            ),
            "battery_plugin": charging.get("batteryPlugin"),
            "target_soc_plug_type": target.get("plugType"),
            "target_soc_level": _format_float(target.get("targetSOClevel")),
            "remain_time_value": remain.get("value"),
            "remain_time_unit": remain.get("unit"),
            "timestamp": battery.get("timestamp"),
            "msg_id": battery.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingPlugSensor(_BluelinkChargingSensor):
    """Sensor reporting charger connection state."""

    _attr_icon = "mdi:power-plug"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charger Connection"
        self._attr_unique_id = f"{entry_id}_charging_plugin"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> int | None:
        charging = self._charging()
        plugin = charging.get("batteryPlugin")
        return 0 if plugin is None else plugin

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        return {
            "timestamp": charging.get("timestamp"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingStateSensor(_BluelinkChargingSensor):
    """Sensor reporting whether the vehicle is charging."""

    _attr_icon = "mdi:battery-charging"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charging State"
        self._attr_unique_id = f"{entry_id}_charging_state"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> bool | None:
        charging = self._charging()
        if "batteryCharge" in charging:
            return bool(charging.get("batteryCharge", False))
        return bool(charging.get("batterCharge", False))

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        return {
            "timestamp": charging.get("timestamp"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingPlugTypeSensor(_BluelinkChargingSensor):
    """Sensor reporting target plug type."""

    _attr_icon = "mdi:ev-plug-type2"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charging Plug Type"
        self._attr_unique_id = f"{entry_id}_charging_plug_type"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> int | None:
        target = self._charging().get("targetSOC") or {}
        plug_type = target.get("plugType")
        return 0 if plug_type is None else plug_type

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        target = charging.get("targetSOC") or {}
        return {
            "timestamp": charging.get("timestamp"),
            "target_soc_level": _format_float(target.get("targetSOClevel")),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingTargetSocSensor(_BluelinkChargingSensor):
    """Sensor reporting target SOC level."""

    _attr_icon = "mdi:battery-charging-100"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charging Target SOC"
        self._attr_unique_id = f"{entry_id}_charging_target_soc"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> float | None:
        target = self._charging().get("targetSOC") or {}
        level = target.get("targetSOClevel")
        if level is None:
            return None
        return _format_float(level)

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        target = charging.get("targetSOC") or {}
        return {
            "timestamp": charging.get("timestamp"),
            "plug_type": target.get("plugType"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingRemainTimeSensor(_BluelinkChargingSensor):
    """Sensor reporting remaining charging time while charging."""

    _attr_icon = "mdi:timer-sand"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charging Time Remaining"
        self._attr_unique_id = f"{entry_id}_charging_remain_time"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> int | None:
        remain = self._remain_time()
        raw_value = remain.get("value")
        value = int(raw_value) if raw_value is not None else 0
        return value if self._is_charging() else 0

    @property
    def native_unit_of_measurement(self) -> str | None:
        remain = self._remain_time()
        unit = remain.get("unit")
        if unit is None:
            return None
        return TIME_UNIT_MAP.get(unit, str(unit))

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        remain = self._remain_time()
        return {
            "timestamp": charging.get("timestamp"),
            "raw_unit": remain.get("unit"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkWarningSensor(CoordinatorEntity[BluelinkCoordinator], SensorEntity):
    """Sensor reporting warning status."""

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: BluelinkCoordinator,
        entry_id: str,
        entry_title: str,
        *,
        warning_key: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._warning_key = warning_key
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} {label}"
        self._attr_unique_id = f"{entry_id}_{warning_key}_warning"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    def _warning_data(self) -> dict:
        warnings = self.coordinator.data.get("warnings") or {}
        return warnings.get(self._warning_key) or {}

    @property
    def native_value(self) -> bool | None:
        data = self._warning_data()
        status = data.get("status")
        if status is None:
            return False
        return bool(status)

    @property
    def extra_state_attributes(self) -> dict:
        data = self._warning_data()
        return {
            "timestamp": data.get("timestamp"),
            "msg_id": data.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }


class BluelinkChargingEstimateTimeSensor(_BluelinkChargingSensor):
    """Sensor reporting estimated charging time when not charging."""

    _attr_icon = "mdi:timer-outline"

    def __init__(
        self, coordinator: BluelinkCoordinator, entry_id: str, entry_title: str
    ) -> None:
        super().__init__(coordinator)
        base = _entity_base_name(coordinator, entry_title)
        self._attr_name = f"{base} Charging Time Estimate"
        self._attr_unique_id = f"{entry_id}_charging_estimate_time"
        self._attr_device_info = _device_info_from_coordinator(coordinator)

    @property
    def native_value(self) -> int | None:
        remain = self._remain_time()
        raw_value = remain.get("value")
        value = int(raw_value) if raw_value is not None else 0
        return 0 if self._is_charging() else value

    @property
    def native_unit_of_measurement(self) -> str | None:
        remain = self._remain_time()
        unit = remain.get("unit")
        if unit is None:
            return None
        return TIME_UNIT_MAP.get(unit, str(unit))

    @property
    def extra_state_attributes(self) -> dict:
        charging = self._charging()
        remain = self._remain_time()
        return {
            "timestamp": charging.get("timestamp"),
            "raw_unit": remain.get("unit"),
            "msg_id": charging.get("msgId"),
            "car_id": self.coordinator.selected_car_id,
        }
