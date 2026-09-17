import base64
import json
import time

import pytest

from ather_bot.ather import Client, jwt_expiry, normalize_token


def token(expiry: int) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": expiry}).encode()
    ).decode().rstrip("=")
    return "x." + payload + ".signature" + ("z" * 100)


def test_normalize_token_strips_bearer_prefix():
    value = token(int(time.time()) + 3600)
    assert normalize_token(f"Bearer {value}")[0] == value


def test_rejects_invalid_and_expired_tokens():
    with pytest.raises(ValueError, match="valid"):
        jwt_expiry("not-a-token")
    with pytest.raises(ValueError, match="expired"):
        jwt_expiry(token(int(time.time()) - 1))


def test_telemetry_uses_first_scooter(monkeypatch):
    client = Client(token(int(time.time()) + 3600))
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("firebase-dbs"):
            return {"scooterDatabases": [{"scooter": "scooter-1"}]}
        return {
            "data": {
                "state": {
                    "reported": {
                        "bike": {"battery_soc": "42.5"},
                        "tpms": {
                            "front_tyre_pressure": 29,
                            "rear_tyre_pressure": 31,
                        },
                    }
                }
            }
        }

    monkeypatch.setattr(client, "_request", fake_request)
    reading = client.telemetry()

    assert reading.scooter_id == "scooter-1"
    assert reading.battery == 42.5
    assert calls[-1][2]["params"] == {"uuid": "scooter-1"}
