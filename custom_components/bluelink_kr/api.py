from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    ACCESS_TOKEN_DEFAULT_EXPIRES_IN,
    CAR_LIST_URL,
    PROFILE_URL,
    DRIVING_RANGE_URL,
    ODOMETER_URL,
    EV_CHARGING_URL,
    REFRESH_TOKEN_DEFAULT_EXPIRES_IN,
    TERMS_AGREEMENT_URL,
    TOKEN_URL,
)


class BluelinkAuthError(Exception):
    """Raised when the Bluelink auth server returns an error."""


@dataclass
class TokenResult:
    """Container for OAuth token data and expiration times."""

    access_token: str
    refresh_token: str | None
    token_type: str | None
    access_token_expires_at: str
    refresh_token_expires_at: str | None


def _build_auth_header(client_id: str, client_secret: str) -> str:
    creds = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(creds).decode()


async def async_request_token(
    hass: HomeAssistant,
    *,
    client_id: str,
    client_secret: str,
    grant_type: str,
    code: str | None = None,
    refresh_token: str | None = None,
    access_token: str | None = None,
    redirect_uri: str | None = None,
) -> TokenResult:
    """Call the Hyundai Bluelink token endpoint."""
    session = async_get_clientsession(hass)

    data: dict[str, Any] = {"grant_type": grant_type}
    if grant_type == "authorization_code":
        if not code:
            raise BluelinkAuthError("Missing authorization code")
        data["code"] = code
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
    elif grant_type == "refresh_token":
        if not refresh_token:
            raise BluelinkAuthError("Missing refresh_token")
        data["refresh_token"] = refresh_token
    elif grant_type == "delete":
        if not access_token:
            raise BluelinkAuthError("Missing access_token for deletion")
        data["access_token"] = access_token
    else:
        raise BluelinkAuthError(f"Unsupported grant_type: {grant_type}")

    headers = {
        "Authorization": _build_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        resp = await session.post(TOKEN_URL, headers=headers, data=data)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Token request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Token request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"Token response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(f"Token request failed ({err_code}): {err_msg}")

    access_token_value: str | None = payload.get("access_token")
    if not access_token_value:
        raise BluelinkAuthError("Token response missing access_token")

    refresh_token_value: str | None = payload.get("refresh_token", refresh_token)
    expires_in = payload.get("expires_in", ACCESS_TOKEN_DEFAULT_EXPIRES_IN)
    access_expires_at = dt_util.utcnow() + timedelta(seconds=expires_in)

    refresh_expires_at: str | None = None
    if refresh_token_value:
        refresh_expires_at_dt = dt_util.utcnow() + timedelta(
            seconds=REFRESH_TOKEN_DEFAULT_EXPIRES_IN
        )
        refresh_expires_at = refresh_expires_at_dt.isoformat()

    return TokenResult(
        access_token=access_token_value,
        refresh_token=refresh_token_value,
        token_type=payload.get("token_type"),
        access_token_expires_at=access_expires_at.isoformat(),
        refresh_token_expires_at=refresh_expires_at,
    )


async def async_get_profile(hass: HomeAssistant, *, access_token: str) -> dict[str, Any]:
    """Fetch user profile using an access token."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        resp = await session.get(PROFILE_URL, headers=headers)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Profile request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Profile request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"Profile response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(f"Profile request failed ({err_code}): {err_msg}")

    return payload


async def async_request_terms_agreement(
    hass: HomeAssistant, *, access_token: str, state: str
) -> None:
    """Initiate the terms agreement call."""
    session = async_get_clientsession(hass)
    params = {"token": f"Bearer {access_token}", "state": state}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = await session.post(TERMS_AGREEMENT_URL, params=params, headers=headers)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Terms request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Terms request failed: {err}") from err

    if resp.status not in (200, 302):
        text = await resp.text()
        raise BluelinkAuthError(
            f"Terms request failed ({resp.status}): {text}"
        )


async def async_get_car_list(hass: HomeAssistant, *, access_token: str) -> list[dict]:
    """Fetch the user's registered cars."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        resp = await session.get(CAR_LIST_URL, headers=headers)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Car list request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Car list request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"Car list response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(f"Car list request failed ({err_code}): {err_msg}")

    cars = payload.get("cars", [])
    if not isinstance(cars, list):
        raise BluelinkAuthError("Car list response missing cars array")

    return cars


async def async_get_driving_range(
    hass: HomeAssistant, *, access_token: str, car_id: str
) -> dict[str, Any]:
    """Fetch driving range for a vehicle."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = DRIVING_RANGE_URL.format(carId=car_id)
    params = {"carId": car_id}

    try:
        resp = await session.get(url, headers=headers, params=params)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Driving range request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Driving range request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"Driving range response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(f"Driving range request failed ({err_code}): {err_msg}")

    return payload


async def async_get_odometer(
    hass: HomeAssistant, *, access_token: str, car_id: str
) -> dict[str, Any]:
    """Fetch odometer information for a vehicle."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = ODOMETER_URL.format(carId=car_id)
    params = {"carId": car_id}

    try:
        resp = await session.get(url, headers=headers, params=params)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"Odometer request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"Odometer request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"Odometer response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(f"Odometer request failed ({err_code}): {err_msg}")

    return payload


async def async_get_ev_charging_status(
    hass: HomeAssistant, *, access_token: str, car_id: str
) -> dict[str, Any]:
    """Fetch EV charging status for a vehicle."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = EV_CHARGING_URL.format(carId=car_id)
    params = {"carId": car_id}

    try:
        resp = await session.get(url, headers=headers, params=params)
    except ClientResponseError as err:
        raise BluelinkAuthError(f"EV charging request failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise BluelinkAuthError(f"EV charging request failed: {err}") from err

    try:
        payload: dict[str, Any] = await resp.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        text = await resp.text()
        raise BluelinkAuthError(
            f"EV charging response parse failed: {err}; body={text}"
        ) from err

    if resp.status != 200 or "errCode" in payload:
        err_code = payload.get("errCode") or resp.status
        err_msg = payload.get("errMsg") or payload
        raise BluelinkAuthError(
            f"EV charging request failed ({err_code}): {err_msg}"
        )

    return payload
