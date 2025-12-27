from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from homeassistant.const import Platform, UnitOfLength, UnitOfTime

DOMAIN = "bluelink_kr"
DEFAULT_NAME = "현대 블루링크"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]
SCAN_INTERVAL = timedelta(minutes=5)
BATTERY_INTERVAL = timedelta(minutes=5)
CHARGING_INTERVAL = timedelta(minutes=10)
DRIVING_RANGE_INTERVAL = timedelta(hours=1)
WARNING_INTERVAL = timedelta(hours=1)
ODOMETER_INTERVAL = timedelta(hours=1)

# 현대 블루링크(대한민국) OAuth 엔드포인트 및 기본값.
AUTH_URL = (
    "https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/authorize?"
    "client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}"
)
TOKEN_URL = "https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/token"
TERMS_AGREEMENT_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car-service/terms/agreement"
TERMS_CALLBACK_PATH = "/api/bluelink_kr/terms/callback"
PROFILE_URL = "https://prd.kr-ccapi.hyundai.com/api/v1/user/profile"
CAR_LIST_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car/profile/carlist"
DRIVING_RANGE_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/{carId}/dte"
ODOMETER_URL = "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/{carId}/odometer"
EV_CHARGING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/{carId}/ev/charging"
)
EV_BATTERY_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/{carId}/ev/battery"
)
LOW_FUEL_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/lowFuel"
)
TIRE_PRESSURE_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/tirePressure"
)
LAMP_WIRE_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/lampWire"
)
SMART_KEY_BATTERY_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/smartKeyBattery"
)
WASHER_FLUID_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/washerFluid"
)
BRAKE_OIL_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/breakOil"
)
ENGINE_OIL_WARNING_URL = (
    "https://dev.kr-ccapi.hyundai.com/api/v1/car/status/warning/{carId}/engineOil"
)
OAUTH_CALLBACK_PATH = "/api/bluelink_kr/oauth/callback"
ACCESS_TOKEN_DEFAULT_EXPIRES_IN = 60 * 60 * 24  # 24 hours
REFRESH_TOKEN_DEFAULT_EXPIRES_IN = 60 * 60 * 24 * 365  # 1 year
REFRESH_TOKEN_REAUTH_THRESHOLD_DAYS = 364

# Car type codes from the car list API (immutable per vehicle).
CAR_TYPE_LABELS: dict[str, str] = {
    "GN": "Internal combustion",
    "EV": "Electric",
    "HEV": "Hybrid",
    "PHEV": "Plug-in hybrid",
    "FCEV": "Fuel cell electric",
}

# EV-capable types for charging/SOC endpoints.
EV_CAPABLE_CAR_TYPES: set[str] = {"EV", "PHEV", "FCEV"}

# Unit enum mapping from API
DRIVING_RANGE_UNIT_MAP: dict[int, str] = {
    0: UnitOfLength.FEET,
    1: UnitOfLength.KILOMETERS,
    2: UnitOfLength.METERS,
    3: UnitOfLength.MILES,
}

TIME_UNIT_MAP: dict[int, str] = {
    0: UnitOfTime.HOURS,
    1: UnitOfTime.MINUTES,
    2: "ms",
    3: UnitOfTime.SECONDS,
}


def normalize_car_type(car_type: str | None) -> str | None:
    """Normalize carType values from the car list."""
    if not car_type:
        return None
    return str(car_type).strip().upper()


def is_ev_capable_car_type(car_type: str | None) -> bool:
    """Return True if the carType supports EV charging endpoints."""
    normalized = normalize_car_type(car_type)
    if normalized is None:
        return True
    return normalized in EV_CAPABLE_CAR_TYPES


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
