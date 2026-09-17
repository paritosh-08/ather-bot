from __future__ import annotations

import base64
import html
import json
import os
import re
from email.message import EmailMessage
from typing import Any

import requests

from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, now, set_settings

GMAIL_HOST = "www.googleapis.com"
PROFILE_PATH = "gmail/v1/users/me/profile"
SEND_PATH = "gmail/v1/users/me/messages/send"
PROVIDER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def platform_url() -> str:
    try:
        return os.environ["PROMPTQL_PLATFORM_API_URL"].rstrip("/")
    except KeyError as exc:
        raise RuntimeError("PROMPTQL_PLATFORM_API_URL is unavailable.") from exc


def user_jwt() -> str:
    try:
        return os.environ["PROMPTQL_USER_JWT"]
    except KeyError as exc:
        raise RuntimeError("PROMPTQL_USER_JWT is unavailable.") from exc


def integration_url(provider: str, path: str) -> str:
    if not PROVIDER_RE.fullmatch(provider):
        raise ValueError("Invalid Gmail provider ID.")
    return f"{platform_url()}/v1/integration/{provider}/{GMAIL_HOST}/{path}"


def headers(description: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {user_jwt()}",
        "X-PromptQL-Description": description,
    }


def profile(provider: str) -> dict[str, str]:
    response = requests.get(
        integration_url(provider, PROFILE_PATH),
        headers=headers("Verify Gmail for Ather alert delivery"),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    mailbox = payload.get("emailAddress")
    if not isinstance(mailbox, str) or not mailbox:
        raise RuntimeError("Gmail returned an invalid profile.")
    return {"provider": provider, "mailbox": mailbox}


def configure(paths: Paths, provider: str, mailbox: str) -> dict[str, str]:
    verified = profile(provider)
    if verified["mailbox"].casefold() != mailbox.strip().casefold():
        raise ValueError(
            "The requested mailbox does not match the connected Gmail account."
        )
    set_settings(
        connect(paths.database),
        {
            "gmail_provider": provider,
            "gmail_mailbox": verified["mailbox"],
        },
    )
    return verified


def raw_message(recipients: list[str], subject: str, body: str) -> str:
    if not recipients:
        raise ValueError("At least one recipient is required.")
    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(
        "<html><body><p>"
        + html.escape(body).replace("\n", "<br>")
        + "</p></body></html>",
        subtype="html",
    )
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def send_test(paths: Paths, recipients: list[str]) -> dict[str, str]:
    with connect(paths.database) as conn:
        provider = get_settings(conn, DEFAULT_SETTINGS)["gmail_provider"]
    if not provider:
        raise RuntimeError("Gmail has not been configured.")
    message_id = send(
        provider,
        recipients,
        "Ather Bot email alerts enabled",
        "Ather Bot is configured to send telemetry alerts to this address.",
    )
    return {"message_id": message_id}


def send(provider: str, recipients: list[str], subject: str, body: str) -> str:
    response = requests.post(
        integration_url(provider, SEND_PATH),
        headers={
            **headers("Send an authorized Ather telemetry alert"),
            "Content-Type": "application/json",
        },
        json={"raw": raw_message(recipients, subject, body)},
        timeout=45,
    )
    response.raise_for_status()
    message_id = response.json().get("id")
    if not isinstance(message_id, str) or not message_id:
        raise RuntimeError("Gmail did not return a message ID.")
    return message_id


def drain(paths: Paths) -> dict[str, int]:
    conn = connect(paths.database)
    provider = get_settings(conn, DEFAULT_SETTINGS)["gmail_provider"]
    if not provider:
        raise RuntimeError("Gmail has not been configured.")

    sent_count = 0
    rows = conn.execute(
        "SELECT * FROM email_queue "
        "WHERE state='pending' ORDER BY created_at LIMIT 25"
    ).fetchall()
    for item in rows:
        recipients: Any = json.loads(item["recipients_json"])
        if not isinstance(recipients, list) or not all(
            isinstance(value, str) for value in recipients
        ):
            raise RuntimeError("A queued email has invalid recipients.")
        message_id = send(
            provider,
            recipients,
            item["subject"],
            item["body"],
        )
        conn.execute(
            "UPDATE email_queue "
            "SET state='sent',gmail_message_id=?,sent_at=? "
            "WHERE id=? AND state='pending'",
            (message_id, now(), item["id"]),
        )
        conn.commit()
        sent_count += 1

    pending = conn.execute(
        "SELECT COUNT(1) FROM email_queue WHERE state='pending'"
    ).fetchone()[0]
    return {"sent": sent_count, "pending": pending}
