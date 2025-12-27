from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, OAUTH_CALLBACK_PATH, TERMS_CALLBACK_PATH

_LOGGER = logging.getLogger(__name__)


class BluelinkUnifiedCallbackView(HomeAssistantView):
    """Handle OAuth and terms callbacks; choose flow based on available state stores."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant, url: str, name: str) -> None:
        self.hass = hass
        self.url = url
        self.name = name

    @callback
    async def get(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")
        user_id = request.query.get("userId")
        err_code = request.query.get("errCode")
        err_msg = request.query.get("errMsg")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        callback_states: dict[str, str] = domain_data.setdefault("callback_states", {})
        legacy_oauth: dict[str, str] = domain_data.setdefault("oauth_states", {})
        legacy_terms: dict[str, str] = domain_data.setdefault("terms_states", {})

        if not callback_states and (legacy_oauth or legacy_terms):
            # Migrate any legacy stored states from before the unified map.
            for legacy_state, flow_id in legacy_oauth.items():
                callback_states.setdefault(legacy_state, flow_id)
            for legacy_state, flow_id in legacy_terms.items():
                callback_states.setdefault(legacy_state, flow_id)

        _LOGGER.debug(
            "Callback received: state=%s path=%s code_present=%s callback_states=%d",
            state,
            self.url,
            bool(code),
            len(callback_states),
        )

        if not state or state not in callback_states:
            return web.Response(status=400, text="No active flow.")

        flow_id = callback_states.pop(state)

        if err_code:
            return web.Response(
                text=f"terms mode\nTerms agreement failed. You can close this window and return to Home Assistant.\ndomain_data: {domain_data}"
            )

        authorization = code or user_id
        if not authorization:
            return web.Response(
                status=400,
                text=f"missing authorization\nNo code or userId provided.\ndomain_data: {domain_data}",
            )

        try:
            await self.hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"authorization": authorization},
            )
        except ValueError as e:
            callback_states[state] = flow_id
            return web.Response(
                status=400,
                text=f"Flow not in expected state. Please restart the integration setup.\ndomain_data: {domain_data}\nerror: {e}",
            )

        return web.Response(
            text=f"Authorization received. You can close this window and return to Home Assistant.\ndomain_data: {domain_data}"
        )
