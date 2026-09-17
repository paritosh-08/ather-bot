from __future__ import annotations

import json
import sqlite3
import uuid

from .ather import Client
from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, get_status, now, set_status

LABELS = {"battery": "Battery", "front": "Front tyre", "rear": "Rear tyre"}
UNITS = {"battery": "%", "front": " PSI", "rear": " PSI"}


def queue_email(
    conn: sqlite3.Connection,
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    conn.execute(
        "INSERT INTO email_queue(id,created_at,recipients_json,subject,body,state) "
        "VALUES(?,?,?,?,?,'pending')",
        (str(uuid.uuid4()), now(), json.dumps(recipients), subject, body),
    )
    conn.commit()


def is_active(key: str, value: float, limits: dict[str, tuple[float, float | None]]) -> bool:
    low, high = limits[key]
    return value < low or (high is not None and value > high)


def limit_text(key: str, limits: dict[str, tuple[float, float | None]]) -> str:
    low, high = limits[key]
    if high is None:
        return f"below {low:g}{UNITS[key]}"
    return f"outside {low:g}–{high:g}{UNITS[key]}"


def message(
    title: str,
    keys: list[str],
    values: dict[str, float],
    limits: dict[str, tuple[float, float | None]],
) -> str:
    lines = [title]
    for key in keys:
        lines.append(
            f"{LABELS[key]}: {values[key]:g}{UNITS[key]} "
            f"(alert {limit_text(key, limits)})"
        )
    return "\n".join(lines)


def recipients(settings: dict[str, str]) -> list[str]:
    return [item.strip() for item in settings["email_recipients"].split(",") if item.strip()]


def maybe_queue(
    conn: sqlite3.Connection,
    settings: dict[str, str],
    subject: str,
    body: str,
) -> bool:
    targets = recipients(settings)
    if settings["email_enabled"] != "1" or not targets:
        return False
    queue_email(conn, targets, subject, body)
    return True


def run(paths: Paths, bootstrap: bool = False) -> dict:
    conn = connect(paths.database)
    settings = get_settings(conn, DEFAULT_SETTINGS)
    prior_status = get_status(conn)
    token = paths.token.read_text(encoding="utf-8").strip()
    client = Client(token=token)
    reading = client.telemetry(settings["selected_scooter"] or None)
    values = {"battery": reading.battery, "front": reading.front, "rear": reading.rear}
    limits = {
        "battery": (float(settings["battery_threshold"]), None),
        "front": (
            float(settings["front_min_threshold"]),
            float(settings["front_max_threshold"]),
        ),
        "rear": (
            float(settings["rear_min_threshold"]),
            float(settings["rear_max_threshold"]),
        ),
    }
    timestamp = now()
    alerts: list[str] = []
    recoveries: list[str] = []
    old = {row["metric"]: row for row in conn.execute("SELECT * FROM metric_state")}

    for key, value in values.items():
        active = is_active(key, value, limits)
        previous = old.get(key)
        if not bootstrap and previous is not None:
            if not bool(previous["active"]) and active:
                alerts.append(key)
            elif bool(previous["active"]) and not active:
                recoveries.append(key)
        conn.execute(
            "INSERT INTO metric_state(metric,value,threshold,active,checked_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(metric) DO UPDATE SET value=excluded.value,threshold=excluded.threshold,"
            "active=excluded.active,checked_at=excluded.checked_at",
            (key, value, limits[key][0], int(active), timestamp),
        )
    conn.commit()

    queued = 0
    if alerts and maybe_queue(
        conn,
        settings,
        "Ather alert",
        message("Ather alert", alerts, values, limits),
    ):
        queued += 1
    if recoveries and maybe_queue(
        conn,
        settings,
        "Ather recovered",
        message("Ather recovered", recoveries, values, limits),
    ):
        queued += 1
    if (
        not bootstrap
        and int(prior_status.get("consecutive_failures", 0)) >= 3
        and maybe_queue(
            conn,
            settings,
            "Ather monitor recovered",
            "Ather monitor is checking telemetry normally again.",
        )
    ):
        queued += 1

    set_status(conn, "last_success_at", timestamp)
    set_status(conn, "last_values", values)
    set_status(conn, "last_error", None)
    set_status(conn, "consecutive_failures", 0)
    set_status(conn, "failure_alert_queued", False)
    set_status(conn, "scooter_id", reading.scooter_id)
    return {
        "ok": True,
        "bootstrap": bootstrap,
        "values": values,
        "queued_messages": queued,
    }


def record_failure(paths: Paths, exc: Exception) -> dict:
    conn = connect(paths.database)
    settings = get_settings(conn, DEFAULT_SETTINGS)
    status = get_status(conn)
    count = int(status.get("consecutive_failures", 0)) + 1
    set_status(conn, "consecutive_failures", count)
    set_status(conn, "last_failure_at", now())
    set_status(conn, "last_error", f"{type(exc).__name__}: {str(exc)[:200]}")
    queued = False
    if count == 3 and not bool(status.get("failure_alert_queued")):
        queued = maybe_queue(
            conn,
            settings,
            "Ather monitor failure",
            "Ather monitor failed three consecutive telemetry checks. It will keep retrying.",
        )
        set_status(conn, "failure_alert_queued", queued)
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "failure_count": count,
        "failure_email_queued": queued,
    }
