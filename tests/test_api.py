from __future__ import annotations

import pytest

from custom_components.bluelink_kr.api import (
    BluelinkAuthError,
    async_get_profile,
    async_get_car_list,
    async_request_terms_agreement,
    async_request_token,
)


class DummyResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return str(self._payload)


class DummySession:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self._status = status

    async def post(self, *_args, **_kwargs):
        return DummyResponse(self._payload, self._status)

    async def get(self, *_args, **_kwargs):
        return DummyResponse(self._payload, self._status)


def _patch_session(monkeypatch, session: DummySession):
    monkeypatch.setattr(
        "custom_components.bluelink_kr.api.async_get_clientsession",
        lambda hass: session,
    )


@pytest.mark.asyncio
async def test_async_request_token_authorization_code_success(monkeypatch):
    payload = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    _patch_session(monkeypatch, DummySession(payload))

    result = await async_request_token(
        hass=None,
        client_id="id",
        client_secret="secret",
        grant_type="authorization_code",
        code="authcode",
        redirect_uri="http://example.com/callback",
    )

    assert result.access_token == "access"
    assert result.refresh_token == "refresh"
    assert result.token_type == "Bearer"
    assert result.access_token_expires_at
    assert result.refresh_token_expires_at


@pytest.mark.asyncio
async def test_async_request_token_error_from_api(monkeypatch):
    payload = {"errCode": "E123", "errMsg": "bad request"}
    _patch_session(monkeypatch, DummySession(payload, status=400))

    with pytest.raises(BluelinkAuthError):
        await async_request_token(
            hass=None,
            client_id="id",
            client_secret="secret",
            grant_type="authorization_code",
            code="authcode",
            redirect_uri="http://example.com/callback",
        )


@pytest.mark.asyncio
async def test_async_request_token_refresh_requires_token(monkeypatch):
    _patch_session(
        monkeypatch,
        DummySession({"access_token": "new", "refresh_token": "still"}),
    )

    with pytest.raises(BluelinkAuthError):
        await async_request_token(
            hass=None,
            client_id="id",
            client_secret="secret",
            grant_type="refresh_token",
        )


@pytest.mark.asyncio
async def test_async_request_token_delete_requires_access_token(monkeypatch):
    _patch_session(
        monkeypatch,
        DummySession({"access_token": "deleted"}),
    )

    with pytest.raises(BluelinkAuthError):
        await async_request_token(
            hass=None,
            client_id="id",
            client_secret="secret",
            grant_type="delete",
        )


@pytest.mark.asyncio
async def test_async_get_profile_success(monkeypatch):
    payload = {"id": "user-id", "email": "user@example.com"}
    _patch_session(monkeypatch, DummySession(payload))

    result = await async_get_profile(hass=None, access_token="token")
    assert result["id"] == "user-id"


@pytest.mark.asyncio
async def test_async_get_profile_error(monkeypatch):
    payload = {"errCode": "E1", "errMsg": "nope"}
    _patch_session(monkeypatch, DummySession(payload, status=401))

    with pytest.raises(BluelinkAuthError):
        await async_get_profile(hass=None, access_token="token")


@pytest.mark.asyncio
async def test_async_request_terms_agreement_success(monkeypatch):
    _patch_session(monkeypatch, DummySession({}, status=200))

    await async_request_terms_agreement(
        hass=None, access_token="token", state="state-value"
    )


@pytest.mark.asyncio
async def test_async_request_terms_agreement_error(monkeypatch):
    _patch_session(monkeypatch, DummySession({"err": "x"}, status=500))

    with pytest.raises(BluelinkAuthError):
        await async_request_terms_agreement(
            hass=None, access_token="token", state="state-value"
        )


@pytest.mark.asyncio
async def test_async_get_car_list_success(monkeypatch):
    payload = {
        "cars": [{"carId": "c1", "carNickname": "My Car", "carType": "EV"}],
        "msgId": "msg",
    }
    _patch_session(monkeypatch, DummySession(payload))

    cars = await async_get_car_list(hass=None, access_token="token")
    assert cars[0]["carId"] == "c1"


@pytest.mark.asyncio
async def test_async_get_car_list_error(monkeypatch):
    payload = {"errCode": "E2", "errMsg": "fail"}
    _patch_session(monkeypatch, DummySession(payload, status=500))

    with pytest.raises(BluelinkAuthError):
        await async_get_car_list(hass=None, access_token="token")
