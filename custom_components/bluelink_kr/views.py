from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BluelinkUnifiedCallbackView(HomeAssistantView):
    """Handle OAuth callbacks for 현대 블루링크."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant, url: str, name: str) -> None:
        self.hass = hass
        self.url = url
        self.name = name

    @callback
    async def get(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        callback_states: dict[str, str] = domain_data.setdefault("callback_states", {})
        legacy_oauth: dict[str, str] = domain_data.setdefault("oauth_states", {})

        if not callback_states and legacy_oauth:
            # Migrate any legacy stored states from before the unified map.
            for legacy_state, flow_id in legacy_oauth.items():
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

        if not code:
            return web.Response(
                status=400,
                text="Missing authorization code. You can close this window and restart setup in Home Assistant.",
            )

        try:
            await self.hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"authorization": code},
            )
        except ValueError as e:
            callback_states[state] = flow_id
            return web.Response(
                status=400,
                text=(
                    "Flow not in expected state. Please restart the integration setup."
                    f"\nerror: {e}"
                ),
            )

        return web.Response(
            text="Authorization received. You can close this window and return to Home Assistant."
        )
