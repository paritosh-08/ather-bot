import base64
import json
import time

from ather_bot.ather import jwt_expiry


def test_jwt_expiry():
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(time.time()) + 3600}).encode()
    ).decode().rstrip("=")
    token = "x." + payload + ".signature" + ("z" * 100)
    assert jwt_expiry(token) > time.time()
