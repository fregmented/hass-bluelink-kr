from __future__ import annotations

from custom_components.bluelink_kr.const import (
    build_authorize_url,
    is_ev_capable_car_type,
    normalize_car_type,
)


def test_build_authorize_url_encodes_params():
    url = build_authorize_url(
        client_id="client id",
        redirect_uri="https://example.com/callback?x=1&y=2",
        state="my state",
    )
    assert "client_id=client%20id" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback%3Fx%3D1%26y%3D2" in url
    assert "state=my%20state" in url


def test_normalize_car_type_handles_whitespace_and_case():
    assert normalize_car_type(" ev ") == "EV"
    assert normalize_car_type(None) is None


def test_is_ev_capable_car_type():
    assert is_ev_capable_car_type("EV") is True
    assert is_ev_capable_car_type("PHEV") is True
    assert is_ev_capable_car_type("FCEV") is True
    assert is_ev_capable_car_type("HEV") is False
    assert is_ev_capable_car_type("GN") is False
    assert is_ev_capable_car_type(None) is True
