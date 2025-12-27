from __future__ import annotations

import logging
from datetime import timedelta
import asyncio
from typing import Any, Callable

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    BluelinkAuthError,
    async_get_driving_range,
    async_get_odometer,
    async_get_ev_charging_status,
    async_get_ev_battery_status,
    async_get_low_fuel_warning,
    async_get_tire_pressure_warning,
    async_get_lamp_wire_warning,
    async_get_smart_key_battery_warning,
    async_get_washer_fluid_warning,
    async_get_brake_oil_warning,
    async_get_engine_oil_warning,
    async_request_token,
)
from .const import (
    DOMAIN,
    PLATFORMS,
    CHARGING_INTERVAL,
    DRIVING_RANGE_INTERVAL,
    ODOMETER_INTERVAL,
    OAUTH_CALLBACK_PATH,
    REFRESH_TOKEN_DEFAULT_EXPIRES_IN,
    REFRESH_TOKEN_REAUTH_THRESHOLD_DAYS,
    SCAN_INTERVAL,
    TERMS_CALLBACK_PATH,
    WARNING_INTERVAL,
    BATTERY_INTERVAL,
    CHARGING_INTERVAL,
    is_ev_capable_car_type,
    normalize_car_type,
)
from .views import BluelinkUnifiedCallbackView
from .device import async_sync_selected_vehicle

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the 현대 블루링크 component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault("callback_states", {})
    domain_data.setdefault("oauth_states", {})
    domain_data.setdefault("reauth_notified", set())
    domain_data.setdefault("terms_states", {})
    if not domain_data.get("views_registered"):
        hass.http.register_view(
            BluelinkUnifiedCallbackView(
                hass, url=OAUTH_CALLBACK_PATH, name="api:bluelink_kr:oauth_callback"
            )
        )
        hass.http.register_view(
            BluelinkUnifiedCallbackView(
                hass, url=TERMS_CALLBACK_PATH, name="api:bluelink_kr:terms_callback"
            )
        )
        domain_data["views_registered"] = True
    return True


_AUTH_KEYS = {
    "client_id",
    "client_secret",
    "redirect_uri",
    "access_token",
    "refresh_token",
    "token_type",
    "access_token_expires_at",
    "refresh_token_expires_at",
    "user_id",
    "terms_user_id",
}
_VEHICLE_KEYS = {"cars", "car", "selected_car_id"}


class BluelinkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Placeholder coordinator for Bluelink data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: str | None,
        refresh_token: str | None,
        access_token_expires_at: str | None,
        refresh_token_expires_at: str | None,
        selected_car_id: str | None,
        car: dict[str, Any] | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_token_expires_at = access_token_expires_at
        self.refresh_token_expires_at = refresh_token_expires_at
        self.selected_car_id = selected_car_id
        self.car = car
        self.car_type = normalize_car_type(car.get("carType") if car else None)
        self.is_ev_capable = is_ev_capable_car_type(self.car_type)
        self._odometer: dict[str, Any] | None = None
        self._last_odometer: dt_util.dt | None = None
        self._driving_range: dict[str, Any] | None = None
        self._last_driving_range: dt_util.dt | None = None
        self._warnings: dict[str, Any] | None = None
        self._last_warnings: dt_util.dt | None = None
        self._charging_status: dict[str, Any] | None = None
        self._battery_status: dict[str, Any] | None = None
        self._last_battery_status: dt_util.dt | None = None
        self._last_charging_status: dt_util.dt | None = None

    def _should_fetch(self, last: dt_util.dt | None, interval: timedelta, now) -> bool:
        """Return True if data should be refreshed."""
        if last is None:
            return True
        return (now - last) >= interval

    async def _async_fetch_warnings(self, access_token: str) -> dict[str, Any]:
        """Fetch all warning endpoints."""
        if not self.selected_car_id:
            return {}

        warnings: dict[str, Any] = {}
        car_id = self.selected_car_id
        warnings["low_fuel"] = await async_get_low_fuel_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        warnings["tire_pressure"] = await async_get_tire_pressure_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        warnings["lamp_wire"] = await async_get_lamp_wire_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        warnings["smart_key_battery"] = await async_get_smart_key_battery_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        warnings["washer_fluid"] = await async_get_washer_fluid_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        warnings["brake_oil"] = await async_get_brake_oil_warning(
            self.hass,
            access_token=access_token,
            car_id=car_id,
        )
        if self.car_type != "EV":
            warnings["engine_oil"] = await async_get_engine_oil_warning(
                self.hass,
                access_token=access_token,
                car_id=car_id,
            )
        else:
            warnings["engine_oil"] = None

        return warnings

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Bluelink service."""
        try:
            if not self.access_token or not self.selected_car_id:
                raise UpdateFailed("Missing access token or selected car")

            now = dt_util.utcnow()

            if self._should_fetch(self._last_driving_range, DRIVING_RANGE_INTERVAL, now):
                self._driving_range = await async_get_driving_range(
                    self.hass,
                    access_token=self.access_token,
                    car_id=self.selected_car_id,
                )
                self._last_driving_range = now

            if self.is_ev_capable and self._should_fetch(
                self._last_battery_status, BATTERY_INTERVAL, now
            ):
                self._battery_status = await async_get_ev_battery_status(
                    self.hass,
                    access_token=self.access_token,
                    car_id=self.selected_car_id,
                )
                self._last_battery_status = now

            if self.is_ev_capable and self._should_fetch(
                self._last_charging_status, CHARGING_INTERVAL, now
            ):
                charging_status = await async_get_ev_charging_status(
                    self.hass,
                    access_token=self.access_token,
                    car_id=self.selected_car_id,
                )
                self._charging_status = charging_status
                self._last_charging_status = now
            elif not self.is_ev_capable:
                _LOGGER.debug(
                    "Skipping EV charging poll; car_type=%s", self.car_type or "unknown"
                )
                self._charging_status = None
                self._last_charging_status = None
                self._battery_status = None
                self._last_battery_status = None

            # Fetch odometer every ODOMETER_INTERVAL.
            if self._should_fetch(self._last_odometer, ODOMETER_INTERVAL, now):
                self._odometer = await async_get_odometer(
                    self.hass,
                    access_token=self.access_token,
                    car_id=self.selected_car_id,
                )
                self._last_odometer = now

            if self._should_fetch(self._last_warnings, WARNING_INTERVAL, now):
                self._warnings = await self._async_fetch_warnings(self.access_token)
                self._last_warnings = now

            return {
                "driving_range": self._driving_range,
                "charging_status": self._charging_status,
                "battery_status": self._battery_status,
                "odometer": self._odometer,
                "warnings": self._warnings,
                "car": self.car,
                "selected_car_id": self.selected_car_id,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "access_token": self.access_token,
            }
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    @callback
    def update_tokens(self, *, access_token: str, refresh_token: str | None) -> None:
        """Update tokens stored on the coordinator."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        # If tokens were refreshed, keep car selection unchanged.

    async def async_force_refresh(self) -> None:
        """Force refresh all endpoints sequentially with small delays."""
        if not self.access_token or not self.selected_car_id:
            raise UpdateFailed("Missing access token or selected car")

        now = dt_util.utcnow()
        car_id = self.selected_car_id

        self._driving_range = await async_get_driving_range(
            self.hass,
            access_token=self.access_token,
            car_id=car_id,
        )
        await asyncio.sleep(0.1)

        if self.is_ev_capable:
            self._battery_status = await async_get_ev_battery_status(
                self.hass,
                access_token=self.access_token,
                car_id=car_id,
            )
            self._last_battery_status = now
            await asyncio.sleep(0.1)

            self._charging_status = await async_get_ev_charging_status(
                self.hass,
                access_token=self.access_token,
                car_id=car_id,
            )
            self._last_charging_status = now
            await asyncio.sleep(0.1)
        else:
            self._charging_status = None
            self._battery_status = None
            self._last_battery_status = None
            self._last_charging_status = None

        self._odometer = await async_get_odometer(
            self.hass,
            access_token=self.access_token,
            car_id=car_id,
        )
        self._last_odometer = now
        await asyncio.sleep(0.1)

        self._warnings = await self._async_fetch_warnings(self.access_token)
        self._last_warnings = now
        self._last_driving_range = now

        self.async_set_updated_data(
            {
                "driving_range": self._driving_range,
                "charging_status": self._charging_status,
                "battery_status": self._battery_status,
                "odometer": self._odometer,
                "warnings": self._warnings,
                "car": self.car,
                "selected_car_id": self.selected_car_id,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "access_token": self.access_token,
            }
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 현대 블루링크 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = dict(entry.data)
    options = dict(entry.options)
    if _VEHICLE_KEYS & data.keys() and not (_VEHICLE_KEYS & options.keys()):
        for key in _VEHICLE_KEYS:
            if key in data:
                options[key] = data[key]

    trimmed_data = {key: data[key] for key in _AUTH_KEYS if key in data}
    if trimmed_data != data or options != dict(entry.options):
        hass.config_entries.async_update_entry(
            entry, data=trimmed_data, options=options
        )
        data = trimmed_data

    coordinator = BluelinkCoordinator(
        hass,
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        redirect_uri=data.get("redirect_uri", ""),
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        access_token_expires_at=data.get("access_token_expires_at"),
        refresh_token_expires_at=data.get("refresh_token_expires_at"),
        selected_car_id=options.get("selected_car_id"),
        car=options.get("car"),
    )

    runtime: dict[str, Any] = {"coordinator": coordinator, "refresh_unsub": None}
    hass.data[DOMAIN][entry.entry_id] = runtime

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.warning(
            "Initial refresh failed; proceeding with coordinator setup anyway: %s", err
        )
        coordinator.last_update_success = False

    runtime["refresh_unsub"] = _setup_token_refresh(hass, entry, coordinator)

    await async_sync_selected_vehicle(
        hass,
        entry,
        selected_car=options.get("car"),
        selected_car_id=options.get("selected_car_id"),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            runtime = hass.data[DOMAIN].pop(entry.entry_id)
            refresh_unsub: Callable | None = runtime.get("refresh_unsub")
            if refresh_unsub:
                refresh_unsub()
    return unload_ok


def _setup_token_refresh(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BluelinkCoordinator
) -> Callable | None:
    """Register a 24h refresh task for access_token."""

    async def _async_refresh_tokens(now) -> None:
        refresh_token = coordinator.refresh_token
        if not refresh_token:
            _LOGGER.debug("No refresh token available; skipping refresh")
            return

        try:
            token_result = await async_request_token(
                hass,
                client_id=coordinator.client_id,
                client_secret=coordinator.client_secret,
                grant_type="refresh_token",
                refresh_token=refresh_token,
            )
        except BluelinkAuthError as err:
            _LOGGER.warning("Token refresh failed: %s", err)
            return

        new_data = {
            **entry.data,
            "access_token": token_result.access_token,
            "refresh_token": token_result.refresh_token or refresh_token,
            "token_type": token_result.token_type or entry.data.get("token_type", "Bearer"),
            "access_token_expires_at": token_result.access_token_expires_at,
            "refresh_token_expires_at": token_result.refresh_token_expires_at
            or entry.data.get("refresh_token_expires_at"),
        }

        _LOGGER.debug(
            "Access token refreshed (len=%d): %s",
            len(token_result.access_token),
            token_result.access_token,
        )

        hass.config_entries.async_update_entry(entry, data=new_data)
        coordinator.update_tokens(
            access_token=new_data["access_token"],
            refresh_token=new_data.get("refresh_token"),
        )

        _maybe_request_reauth(hass, entry, coordinator)

    _maybe_request_reauth(hass, entry, coordinator)
    return async_track_time_interval(hass, _async_refresh_tokens, timedelta(hours=24))


def _maybe_request_reauth(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BluelinkCoordinator
) -> None:
    """Prompt reauth if refresh token is near expiry (after ~364 days)."""
    refresh_expires_at = entry.data.get("refresh_token_expires_at")
    if not refresh_expires_at:
        return

    parsed = dt_util.parse_datetime(refresh_expires_at)
    if not parsed:
        return

    issued_at = parsed - timedelta(seconds=REFRESH_TOKEN_DEFAULT_EXPIRES_IN)
    threshold = issued_at + timedelta(days=REFRESH_TOKEN_REAUTH_THRESHOLD_DAYS)
    if dt_util.utcnow() >= threshold:
        domain_data = hass.data.setdefault(DOMAIN, {})
        notified: set[str] = domain_data.setdefault("reauth_notified", set())
        if entry.entry_id in notified:
            return

        persistent_notification.async_create(
            hass,
            "현대 블루링크 로그인 후 364일이 지나 재인증이 필요합니다. 통합을 다시 설정하세요.",
            title="현대 블루링크 재인증 필요",
            notification_id=f"{DOMAIN}_reauth_{entry.entry_id}",
        )
        notified.add(entry.entry_id)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "reauth", "entry_id": entry.entry_id},
                data=entry.data,
            )
        )
