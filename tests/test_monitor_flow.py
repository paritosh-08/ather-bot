import json
from pathlib import Path

from ather_bot.ather import Telemetry
from ather_bot.config import Paths
from ather_bot.db import connect, set_settings
from ather_bot.monitor import run


def paths(tmp_path: Path) -> Paths:
    runtime = tmp_path / "runtime"
    secrets = runtime / "secrets"
    secrets.mkdir(parents=True)
    token = secrets / "ather_token"
    token.write_text("test-token")
    return Paths(
        root=tmp_path,
        runtime=runtime,
        secrets=secrets,
        database=runtime / "ather-bot.db",
        token=token,
        owner=runtime / "owner_user_id",
    )


def test_baseline_then_alert_and_recovery(monkeypatch, tmp_path):
    installation = paths(tmp_path)
    conn = connect(installation.database)
    set_settings(
        conn,
        {
            "email_recipients": "owner@example.com",
            "email_enabled": "1",
        },
    )

    readings = iter(
        [
            Telemetry("scooter-1", 30, 29, 31),
            Telemetry("scooter-1", 19, 24, 38),
            Telemetry("scooter-1", 30, 29, 31),
        ]
    )

    class FakeClient:
        def __init__(self, token):
            assert token == "test-token"

        def telemetry(self, scooter_id=None):
            assert scooter_id in (None, "scooter-1")
            return next(readings)

    monkeypatch.setattr("ather_bot.monitor.Client", FakeClient)

    assert run(installation, bootstrap=True)["queued_messages"] == 0
    assert run(installation)["queued_messages"] == 1
    assert run(installation)["queued_messages"] == 1

    rows = conn.execute(
        "SELECT subject, recipients_json FROM email_queue ORDER BY created_at"
    ).fetchall()
    assert [row["subject"] for row in rows] == [
        "Ather alert",
        "Ather recovered",
    ]
    assert json.loads(rows[0]["recipients_json"]) == ["owner@example.com"]