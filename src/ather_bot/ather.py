from __future__ import annotations

import base64
import binascii
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
    """A safe-to-display Ather API error."""


class AtherNetworkError(AtherError):
    """Ather could not be reached."""


@dataclass(frozen=True)
class Telemetry:
    scooter_id: str
    battery: float
    front: float
    rear: float


def normalize_token(value: str) -> tuple[str, int]:
    token = value.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    parts = token.split(".")
    if len(parts) != 3 or len(token) < 100:
        raise ValueError("Enter a valid Ather API token.")

    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        expiry = int(claims["exp"])
    except (
        binascii.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise ValueError("Enter a valid Ather API token.") from exc

    if expiry <= int(time.time()):
        raise ValueError("That Ather API token has expired.")
    return token, expiry


def jwt_expiry(token: str) -> int:
    return normalize_token(token)[1]


class Client:
    def __init__(self, token: str, timeout: int = 30):
        normalized, _ = normalize_token(token)
        self.session = requests.Session()
        self.session.headers.update(
            {**APP_HEADERS, "Authorization": f"Bearer {normalized}"}
        )
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(
                method,
                BASE_URL + path,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise AtherNetworkError(
                f"Ather request failed: {type(exc).__name__}"
            ) from exc

        if response.status_code >= 400:
            raise AtherError(f"Ather returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AtherError("Ather returned an invalid response.") from exc
        if not isinstance(payload, dict):
            raise AtherError("Ather returned an invalid response.")
        return payload

    def scooters(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/api/v1/auth/user/scooters/firebase-dbs",
        )
        scooters = payload.get("scooterDatabases")
        if not isinstance(scooters, list):
            raise AtherError("Ather's scooter response is unsupported.")
        return [item for item in scooters if isinstance(item, dict)]

    def telemetry(self, scooter_id: str | None = None) -> Telemetry:
        scooters = self.scooters()
        available = [
            str(item["scooter"])
            for item in scooters
            if item.get("scooter") is not None
        ]
        if not available:
            raise AtherError("No Ather scooter was found for this account.")
        if scooter_id and scooter_id not in available:
            raise AtherError("The selected scooter is unavailable.")
        selected = scooter_id or available[0]

        payload = self._request(
            "GET",
            "/api/v1/devices/shadows/telemetry",
            params={"uuid": selected},
        )
        try:
            reported = payload["data"]["state"]["reported"]
            return Telemetry(
                scooter_id=selected,
                battery=float(reported["bike"]["battery_soc"]),
                front=float(reported["tpms"]["front_tyre_pressure"]),
                rear=float(reported["tpms"]["rear_tyre_pressure"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AtherError("Ather's telemetry response is unsupported.") from exc
