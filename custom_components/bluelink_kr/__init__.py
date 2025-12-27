from __future__ import annotations

import logging
from datetime import timedelta
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
    async_request_token,
)
from .const import (
    DOMAIN,
    PLATFORMS,
    CHARGING_INTERVAL,
    ODOMETER_INTERVAL,
    REFRESH_TOKEN_DEFAULT_EXPIRES_IN,
    REFRESH_TOKEN_REAUTH_THRESHOLD_DAYS,
    SCAN_INTERVAL,
)
from .views import BluelinkOAuthCallbackView, BluelinkTermsCallbackView
from .device import async_sync_selected_vehicle

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bluelink KR component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault("oauth_states", {})
    domain_data.setdefault("reauth_notified", set())
    domain_data.setdefault("terms_states", {})
    if not domain_data.get("views_registered"):
        hass.http.register_view(BluelinkOAuthCallbackView(hass))
        hass.http.register_view(BluelinkTermsCallbackView(hass))
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
        self._odometer: dict[str, Any] | None = None
        self._last_odometer: dt_util.dt | None = None
        self._charging_status: dict[str, Any] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Bluelink service."""
        try:
            if not self.access_token or not self.selected_car_id:
                raise UpdateFailed("Missing access token or selected car")

            driving_range = await async_get_driving_range(
                self.hass,
                access_token=self.access_token,
                car_id=self.selected_car_id,
            )

            charging_status = await async_get_ev_charging_status(
                self.hass,
                access_token=self.access_token,
                car_id=self.selected_car_id,
            )
            self._charging_status = charging_status
            is_charging = bool(charging_status.get("batteryCharge"))
            self.update_interval = CHARGING_INTERVAL if is_charging else SCAN_INTERVAL

            # Fetch odometer every ODOMETER_INTERVAL.
            now = dt_util.utcnow()
            if not self._last_odometer or (
                now - self._last_odometer
            ) >= ODOMETER_INTERVAL:
                self._odometer = await async_get_odometer(
                    self.hass,
                    access_token=self.access_token,
                    car_id=self.selected_car_id,
                )
                self._last_odometer = now

            return {
                "driving_range": driving_range,
                "charging_status": charging_status,
                "odometer": self._odometer,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluelink KR from a config entry."""
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
        raise ConfigEntryNotReady from err

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
            "Hyundai Bluelink (KR) 로그인 후 364일이 지나 재인증이 필요합니다. 통합을 다시 설정하세요.",
            title="Bluelink KR 재인증 필요",
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
