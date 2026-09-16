from __future__ import annotations

import base64
import html
import json
import os
import uuid
from email.message import EmailMessage

import requests

from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, now, set_settings

GMAIL_HOST = "www.googleapis.com"
PROFILE_PATH = "gmail/v1/users/me/profile"
SEND_PATH = "gmail/v1/users/me/messages/send"


def _base() -> str:
    return os.environ["PROMPTQL_PLATFORM_API_URL"].rstrip("/")


def _jwt() -> str:
    return os.environ["PROMPTQL_USER_JWT"]


def _url(provider: str, path: str) -> str:
    return f"{_base()}/v1/integration/{provider}/{GMAIL_HOST}/{path}"


def profile(provider: str) -> dict:
    response = requests.get(
        _url(provider, PROFILE_PATH),
        headers={
            "Authorization": f"Bearer {_jwt()}",
            "X-PromptQL-Description": "Verify Gmail for Ather alert delivery",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return {"provider": provider, "mailbox": payload["emailAddress"]}


def configure(paths: Paths, provider: str, mailbox: str) -> dict:
    verified = profile(provider)
    if verified["mailbox"].casefold() != mailbox.casefold():
        raise ValueError("Requested mailbox does not match the connected Gmail account.")
    conn = connect(paths.database)
    set_settings(
        conn,
        {"gmail_provider": provider, "gmail_mailbox": verified["mailbox"]},
    )
    return verified


def raw_message(recipients: list[str], subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(
        "<html><body><p>" + html.escape(body).replace("\n", "<br>") + "</p></body></html>",
        subtype="html",
    )
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def queue_test(paths: Paths, recipients: list[str]) -> dict:
    conn = connect(paths.database)
    conn.execute(
        "INSERT INTO email_queue(id,created_at,recipients_json,subject,body,state) "
        "VALUES(?,?,?,?,?,'pending')",
        (
            str(uuid.uuid4()),
            now(),
            json.dumps(recipients),
            "Ather Bot email alerts enabled",
            "Ather Bot is configured to send telemetry alerts to this address.",
        ),
    )
    conn.commit()
    return drain(paths)


def drain(paths: Paths) -> dict:
    conn = connect(paths.database)
    settings = get_settings(conn, DEFAULT_SETTINGS)
    provider = settings["gmail_provider"]
    if not provider:
        raise RuntimeError("Gmail provider has not been configured.")
    sent = 0
    rows = conn.execute(
        "SELECT * FROM email_queue WHERE state='pending' ORDER BY created_at LIMIT 25"
    ).fetchall()
    for item in rows:
        recipients = json.loads(item["recipients_json"])
        response = requests.post(
            _url(provider, SEND_PATH),
            headers={
                "Authorization": f"Bearer {_jwt()}",
                "X-PromptQL-Description": "Send an authorized Ather telemetry alert",
                "Content-Type": "application/json",
            },
            json={"raw": raw_message(recipients, item["subject"], item["body"])},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        conn.execute(
            "UPDATE email_queue SET state='sent',gmail_message_id=?,sent_at=? "
            "WHERE id=? AND state='pending'",
            (payload.get("id"), now(), item["id"]),
        )
        conn.commit()
        sent += 1
    pending = conn.execute(
        "SELECT COUNT(1) FROM email_queue WHERE state='pending'"
    ).fetchone()[0]
    return {"sent": sent, "pending": pending}
