from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import network

from .api import (
    BluelinkAuthError,
    async_get_profile,
    async_get_car_list,
    async_request_terms_agreement,
    async_request_token,
)
from .const import (
    DEFAULT_NAME,
    DOMAIN,
    OAUTH_CALLBACK_PATH,
    TERMS_CALLBACK_PATH,
    build_authorize_url,
    build_terms_agreement_url,
)
from .device import async_sync_selected_vehicle
from .views import BluelinkOAuthCallbackView, BluelinkTermsCallbackView

class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Hyundai Bluelink (KR)."""

    VERSION = 1
    _options_flow_class = None

    def __init__(self) -> None:
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._redirect_uri: str | None = None
        self._state: str | None = None
        self._auth_url: str | None = None
        self._reauth_entry = None
        self._terms_state: str | None = None
        self._terms_url: str | None = None
        self._pending_auth_data: dict[str, Any] | None = None
        self._car_list: list[dict[str, Any]] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect OAuth client credentials and start external login."""
        errors: dict[str, str] = {}
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        if not domain_data.get("views_registered"):
            self.hass.http.register_view(BluelinkOAuthCallbackView(self.hass))
            self.hass.http.register_view(BluelinkTermsCallbackView(self.hass))
            domain_data["views_registered"] = True

        secret_client_id = None
        secret_client_secret = None
        if hasattr(self.hass, "secrets"):
            secret_client_id = self.hass.secrets.get("bluelink_client_id")
            secret_client_secret = self.hass.secrets.get("bluelink_client_secret")

        base_url: str | None = None
        try:
            base_url = network.get_url(
                self.hass,
                allow_internal=False,
                prefer_external=True,
                require_ssl=False,
            )
        except HomeAssistantError:
            base_url = None

        oauth_callback_url = (
            f"{base_url.rstrip('/')}{OAUTH_CALLBACK_PATH}" if base_url else ""
        )
        terms_callback_url = (
            f"{base_url.rstrip('/')}{TERMS_CALLBACK_PATH}" if base_url else ""
        )

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            if not self._reauth_entry:
                self._abort_if_unique_id_configured()

            self._client_id = user_input["client_id"]
            self._client_secret = user_input["client_secret"]

            if not base_url:
                errors["base"] = "external_url_required"
            else:
                self._redirect_uri = oauth_callback_url
                self._state = secrets.token_urlsafe(16)
                self._auth_url = build_authorize_url(
                    self._client_id, self._redirect_uri, self._state
                )

                domain_data = self.hass.data.setdefault(DOMAIN, {})
                oauth_states: dict[str, str] = domain_data.setdefault(
                    "oauth_states", {}
                )
                oauth_states[self._state] = self.flow_id

                # Trigger browser/webview to open the authorize URL; callback is handled automatically.
                return self.async_external_step(step_id="auth", url=self._auth_url)

        schema = vol.Schema(
            {
                vol.Required(
                    "client_id",
                    default=secret_client_id if secret_client_id else vol.UNDEFINED,
                ): str,
                vol.Required(
                    "client_secret",
                    default=secret_client_secret
                    if secret_client_secret
                    else vol.UNDEFINED,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "oauth_callback_url": oauth_callback_url,
                "terms_callback_url": terms_callback_url,
            },
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle redirect callback and create the entry."""
        if user_input is None:
            return self.async_abort(reason="authorization_pending")

        if user_input.get("state") != self._state:
            return self.async_abort(reason="invalid_auth")

        try:
            token_result = await async_request_token(
                self.hass,
                client_id=self._client_id,
                client_secret=self._client_secret,
                grant_type="authorization_code",
                code=user_input["authorization_code"],
                redirect_uri=self._redirect_uri,
            )
            profile = await async_get_profile(
                self.hass, access_token=token_result.access_token
            )
            user_id = profile.get("id")
            if not user_id:
                raise BluelinkAuthError("Profile missing id")

            self._pending_auth_data = {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "access_token": token_result.access_token,
                "refresh_token": token_result.refresh_token,
                "token_type": token_result.token_type or "Bearer",
                "access_token_expires_at": token_result.access_token_expires_at,
                "refresh_token_expires_at": token_result.refresh_token_expires_at,
                "user_id": user_id,
            }

            self._terms_state = secrets.token_urlsafe(16)
            domain_data = self.hass.data.setdefault(DOMAIN, {})
            terms_states: dict[str, str] = domain_data.setdefault("terms_states", {})
            terms_states[self._terms_state] = self.flow_id
            self._terms_url = build_terms_agreement_url(
                access_token=token_result.access_token, state=self._terms_state
            )
            await async_request_terms_agreement(
                self.hass,
                access_token=token_result.access_token,
                state=self._terms_state,
            )

            return self.async_external_step(step_id="terms", url=self._terms_url)
        except BluelinkAuthError:
            return self.async_abort(reason="invalid_auth")

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauthentication trigger."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._client_id = entry_data.get("client_id")
        self._client_secret = entry_data.get("client_secret")
        return await self.async_step_user(
            {"client_id": self._client_id, "client_secret": self._client_secret}
        )

    async def async_step_terms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle terms agreement callback."""
        if user_input is None:
            return self.async_abort(reason="authorization_pending")

        if user_input.get("state") != self._terms_state or not self._pending_auth_data:
            return self.async_abort(reason="invalid_auth")

        if user_input.get("err_code"):
            return self.async_abort(reason="invalid_auth")

        terms_user_id = user_input.get("user_id")
        if not terms_user_id:
            return self.async_abort(reason="invalid_auth")

        self._pending_auth_data["terms_user_id"] = terms_user_id

        try:
            car_list = await async_get_car_list(
                self.hass, access_token=self._pending_auth_data["access_token"]
            )
        except BluelinkAuthError:
            return self.async_abort(reason="invalid_auth")

        if not car_list:
            return self.async_abort(reason="no_cars")

        self._car_list = car_list
        return self.async_external_step_done(next_step_id="vehicle")

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle vehicle selection after terms agreement."""
        if not self._car_list:
            return self.async_abort(reason="no_cars")
        if not self._pending_auth_data:
            return self.async_abort(reason="invalid_auth")

        choices = {
            car["carId"]: f"{car.get('carNickname') or car.get('carName') or car['carId']}"
            for car in self._car_list
            if "carId" in car
        }
        if user_input is None:
            return self.async_show_form(
                step_id="vehicle",
                data_schema=vol.Schema(
                    {vol.Required("selected_car_id"): vol.In(choices)}
                ),
            )

        selected_id = user_input.get("selected_car_id")
        selected_car = next(
            (car for car in self._car_list if car.get("carId") == selected_id), None
        )
        if not selected_car:
            return self.async_abort(reason="invalid_auth")

        auth_data = dict(self._pending_auth_data or {})
        vehicle_data = {
            "cars": self._car_list,
            "car": selected_car,
            "selected_car_id": selected_id,
        }

        if self._reauth_entry:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={**self._reauth_entry.data, **auth_data},
                options={**self._reauth_entry.options, **vehicle_data},
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=DEFAULT_NAME, data=auth_data, options=vehicle_data
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return BluelinkOptionsFlow(config_entry)


class BluelinkOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Hyundai Bluelink (KR)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initial step with a rescan button."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({vol.Required("rescan", default=True): bool}),
            )

        if not user_input.get("rescan"):
            return self.async_create_entry(title="", data=self.config_entry.options)

        access_token = self.config_entry.data.get("access_token")
        selected_car_id = self.config_entry.options.get(
            "selected_car_id",
            self.config_entry.data.get("selected_car_id"),
        )
        if not access_token:
            return self.async_abort(reason="invalid_auth")

        try:
            car_list = await async_get_car_list(
                self.hass,
                access_token=access_token,
            )
        except BluelinkAuthError:
            return self.async_abort(reason="invalid_auth")

        selected_car = next(
            (car for car in car_list if car.get("carId") == selected_car_id), None
        )

        new_options = {
            **self.config_entry.options,
            "cars": car_list,
            "car": selected_car,
            "selected_car_id": selected_car_id,
        }
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=new_options
        )
        await async_sync_selected_vehicle(
            self.hass,
            self.config_entry,
            selected_car=selected_car,
            selected_car_id=selected_car_id,
        )

        runtime = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if runtime and runtime.get("coordinator"):
            coordinator = runtime["coordinator"]
            coordinator.car = selected_car
            coordinator.selected_car_id = selected_car_id
            await coordinator.async_request_refresh()

        return self.async_create_entry(title="", data=self.config_entry.options)
