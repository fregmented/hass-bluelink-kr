from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from homeassistant.const import Platform

DOMAIN = "bluelink_kr"
DEFAULT_NAME = "Hyundai Bluelink (KR)"
PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=5)

# OAuth endpoints and defaults for Hyundai Bluelink (South Korea).
AUTH_URL = (
    "https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/authorize?"
    "client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}"
)
TOKEN_URL = "https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/token"
TERMS_AGREEMENT_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car-service/terms/agreement"
TERMS_CALLBACK_PATH = "/api/bluelink_kr/terms/callback"
PROFILE_URL = "https://prd.kr-ccapi.hyundai.com/api/v1/user/profile"
CAR_LIST_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car/profile/carlist"
OAUTH_CALLBACK_PATH = "/api/bluelink_kr/oauth/callback"
ACCESS_TOKEN_DEFAULT_EXPIRES_IN = 60 * 60 * 24  # 24 hours
REFRESH_TOKEN_DEFAULT_EXPIRES_IN = 60 * 60 * 24 * 365  # 1 year
REFRESH_TOKEN_REAUTH_THRESHOLD_DAYS = 364


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the authorize URL for the KR Bluelink API."""
    return AUTH_URL.format(
        client_id=quote(client_id),
        redirect_uri=quote(redirect_uri),
        state=quote(state),
    )


def build_terms_agreement_url(access_token: str, state: str) -> str:
    """Build the terms agreement URL for user data sharing."""
    token_param = quote(f"Bearer {access_token}")
    return f"{TERMS_AGREEMENT_URL}?token={token_param}&state={quote(state)}"
