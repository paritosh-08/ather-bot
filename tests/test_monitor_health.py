from pathlib import Path

from ather_bot.config import Paths
from ather_bot.db import connect, get_status, set_settings
from ather_bot.monitor import record_failure


def paths(tmp_path: Path) -> Paths:
    runtime = tmp_path / "runtime"
    return Paths(
        root=tmp_path,
        runtime=runtime,
        secrets=runtime / "secrets",
        database=runtime / "ather-bot.db",
        token=runtime / "secrets" / "ather_token",
        owner=runtime / "owner_user_id",
        tailscale=runtime / "tailscale",
    )


def test_failure_email_queued_once_on_third_failure(tmp_path):
    p = paths(tmp_path)
    conn = connect(p.database)
    set_settings(conn, {"email_recipients": "owner@example.com", "email_enabled": "1"})
    record_failure(p, RuntimeError("one"))
    record_failure(p, RuntimeError("two"))
    third = record_failure(p, RuntimeError("three"))
    fourth = record_failure(p, RuntimeError("four"))
    assert third["failure_email_queued"] is True
    assert fourth["failure_email_queued"] is False
    assert conn.execute("SELECT COUNT(1) FROM email_queue").fetchone()[0] == 1
    assert get_status(conn)["consecutive_failures"] == 4
