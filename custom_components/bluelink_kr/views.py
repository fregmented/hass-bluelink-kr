from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, OAUTH_CALLBACK_PATH, TERMS_CALLBACK_PATH


class BluelinkOAuthCallbackView(HomeAssistantView):
    """Handle OAuth redirect from Hyundai Bluelink (KR)."""

    url = OAUTH_CALLBACK_PATH
    name = "api:bluelink_kr:oauth_callback"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @callback
    async def get(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")

        if not code or not state:
            return web.Response(status=400, text="Missing code or state.")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        oauth_states: dict[str, str] = domain_data.setdefault("oauth_states", {})
        flow_id = oauth_states.pop(state, None)

        if not flow_id:
            return web.Response(status=400, text="Unknown or expired state.")

        # Resume the config flow with the received authorization code.
        await self.hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"authorization_code": code, "state": state},
        )

        return web.Response(
            text="Authorization received. You can close this window and return to Home Assistant."
        )


class BluelinkTermsCallbackView(HomeAssistantView):
    """Handle terms agreement redirect from Hyundai Bluelink (KR)."""

    url = TERMS_CALLBACK_PATH
    name = "api:bluelink_kr:terms_callback"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @callback
    async def get(self, request: web.Request) -> web.Response:
        state = request.query.get("state")
        user_id = request.query.get("userId")
        err_code = request.query.get("errCode")
        err_msg = request.query.get("errMsg")

        if not state:
            return web.Response(status=400, text="Missing state.")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        terms_states: dict[str, str] = domain_data.setdefault("terms_states", {})
        flow_id = terms_states.pop(state, None)

        if not flow_id:
            return web.Response(status=400, text="Unknown or expired state.")

        await self.hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                "state": state,
                "user_id": user_id,
                "err_code": err_code,
                "err_msg": err_msg,
            },
        )

        if err_code:
            return web.Response(
                text="Terms agreement failed. You can close this window and return to Home Assistant."
            )

        return web.Response(
            text="Terms agreement received. You can close this window and return to Home Assistant."
        )
