import base64
from email import message_from_bytes

import pytest

from ather_bot.config import Paths
from ather_bot.db import connect, set_settings
from ather_bot.gmail import integration_url, raw_message, send_test


def test_raw_message():
    encoded = raw_message(["a@example.com"], "Ather alert", "Battery: 10%")
    message = message_from_bytes(base64.urlsafe_b64decode(encoded))
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Ather alert"


def test_raw_message_requires_recipient():
    with pytest.raises(ValueError, match="recipient"):
        raw_message([], "Ather alert", "Battery: 10%")


def test_provider_id_cannot_change_integration_path(monkeypatch):
    monkeypatch.setenv("PROMPTQL_PLATFORM_API_URL", "https://example.test/platform")
    with pytest.raises(ValueError, match="provider"):
        integration_url("../other", "profile")


def test_send_test_does_not_drain_pending_alerts(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    paths = Paths(
        root=tmp_path,
        runtime=runtime,
        secrets=runtime / "secrets",
        database=runtime / "ather-bot.db",
        token=runtime / "secrets" / "ather_token",
        owner=runtime / "owner_user_id",
    )
    conn = connect(paths.database)
    set_settings(conn, {"gmail_provider": "__gmail-v2"})
    conn.execute(
        "INSERT INTO email_queue("
        "id,created_at,recipients_json,subject,body,state"
        ") VALUES('queued','now','[\"queued@example.com\"]','queued','body','pending')"
    )
    conn.commit()

    calls = []

    def fake_send(provider, recipients, subject, body):
        calls.append((provider, recipients, subject, body))
        return "message-1"

    monkeypatch.setattr("ather_bot.gmail.send", fake_send)

    result = send_test(paths, ["test@example.com"])

    assert result == {"message_id": "message-1"}
    assert calls[0][1] == ["test@example.com"]
    assert conn.execute(
        "SELECT COUNT(1) FROM email_queue WHERE state='pending'"
    ).fetchone()[0] == 1
