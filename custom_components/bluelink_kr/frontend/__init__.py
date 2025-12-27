from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BUNDLED_CARD_URL = f"/{DOMAIN}/bluelink-kr-card.js"


def _card_path() -> Path:
    return Path(__file__).with_name("bluelink-kr-card.js")


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Expose the bundled Lovelace card and auto-load it."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("frontend_registered"):
        return

    card_path = _card_path()
    if not card_path.is_file():
        _LOGGER.debug("Frontend bundle not found: %s", card_path)
        return

    try:
        hass.http.register_static_path(
            BUNDLED_CARD_URL, str(card_path), cache_headers=True
        )
    except Exception as err:  # register_static_path is idempotent in most HA versions
        _LOGGER.debug("Static path already registered or failed: %s", err)

    add_extra_js = getattr(frontend, "async_add_extra_js_url", None)
    if callable(add_extra_js):
        add_extra_js(hass, BUNDLED_CARD_URL)
        domain_data["frontend_registered"] = True
    else:
        _LOGGER.debug(
            "frontend.async_add_extra_js_url unavailable; add %s as a Lovelace resource manually",
            BUNDLED_CARD_URL,
        )


async def async_unload_frontend(hass: HomeAssistant) -> None:
    """Undo frontend registration when all entries are removed."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    remove_extra_js = getattr(frontend, "async_remove_extra_js_url", None)
    if callable(remove_extra_js):
        remove_extra_js(hass, BUNDLED_CARD_URL)
    domain_data.pop("frontend_registered", None)
