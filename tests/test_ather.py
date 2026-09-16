import base64
import json
import time

import pytest

from ather_bot.ather import jwt_expiry, normalize_phone


def test_normalize_phone():
    assert normalize_phone("+91 98765 43210") == "9876543210"


def test_reject_phone():
    with pytest.raises(ValueError):
        normalize_phone("123")


def test_jwt_expiry():
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(time.time()) + 3600}).encode()
    ).decode().rstrip("=")
    token = "x." + payload + ".signature" + ("z" * 100)
    assert jwt_expiry(token) > time.time()
