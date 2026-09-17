from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://cerberus.ather.io"
APP_HEADERS = {
    "Source": "ATHER_APP/11.3.0",
    "User-Agent": "Ktor client",
    "Accept": "application/json",
}


class AtherError(RuntimeError):
    pass


class AtherNetworkError(AtherError):
    pass


@dataclass(frozen=True)
class Telemetry:
    scooter_id: str
    battery: float
    front: float
    rear: float


def jwt_expiry(token: str) -> int:
    token = token.removeprefix("Bearer ").strip()
    parts = token.split(".")
    if len(parts) != 3 or len(token) < 100:
        raise ValueError("Ather returned an invalid token.")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    expiry = int(claims.get("exp", 0))
    if expiry <= int(time.time()):
        raise ValueError("Ather returned an expired token.")
    return expiry


class Client:
    def __init__(self, token: str | None = None, socks_url: str = "", timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update(APP_HEADERS)
        if token:
            self.session.headers["Authorization"] = f"Bearer {token.strip()}"
        if socks_url:
            self.session.proxies.update({"http": socks_url, "https": socks_url})
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(method, BASE_URL + path, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise AtherNetworkError(type(exc).__name__) from exc
        if response.status_code >= 400:
            raise AtherError(f"Ather returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise AtherError("Ather returned a non-JSON response") from exc

    def scooters(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/auth/user/scooters/firebase-dbs")
        return list(data.get("scooterDatabases") or [])

    def telemetry(self, scooter_id: str | None = None) -> Telemetry:
        scooters = self.scooters()
        if not scooters:
            raise AtherError("No Ather scooter found.")
        selected = scooter_id or str(scooters[0]["scooter"])
        payload = self._request("GET", f"/api/v1/devices/shadows/telemetry?uuid={selected}")
        try:
            reported = payload["data"]["state"]["reported"]
            return Telemetry(
                scooter_id=selected,
                battery=float(reported["bike"]["battery_soc"]),
                front=float(reported["tpms"]["front_tyre_pressure"]),
                rear=float(reported["tpms"]["rear_tyre_pressure"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AtherError("Ather telemetry schema is unsupported.") from exc
