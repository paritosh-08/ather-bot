from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metric_state (
  metric TEXT PRIMARY KEY,
  value REAL NOT NULL,
  threshold REAL NOT NULL,
  active INTEGER NOT NULL,
  checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS status (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_queue (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  recipients_json TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending',
  gmail_message_id TEXT,
  sent_at TEXT
);
CREATE INDEX IF NOT EXISTS email_queue_state_idx ON email_queue(state, created_at);
'''


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_settings(conn: sqlite3.Connection, defaults: dict[str, str]) -> dict[str, str]:
    values = defaults.copy()
    values.update({row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM settings")})
    return values


def set_settings(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.executemany(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        values.items(),
    )
    conn.commit()


def set_status(conn: sqlite3.Connection, key: str, value: Any) -> None:
    encoded = json.dumps(value, separators=(",", ":"))
    conn.execute(
        "INSERT INTO status(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, encoded),
    )
    conn.commit()


def get_status(conn: sqlite3.Connection) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in conn.execute("SELECT key,value FROM status"):
        try:
            result[row["key"]] = json.loads(row["value"])
        except ValueError:
            result[row["key"]] = row["value"]
    return result


def now() -> str:
    return datetime.now(UTC).isoformat()
