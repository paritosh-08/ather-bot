from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    runtime: Path
    secrets: Path
    database: Path
    token: Path
    owner: Path
    tailscale: Path

    @classmethod
    def from_env(cls) -> Paths:
        root = Path(os.environ.get("ATHER_BOT_ROOT", "/workspace/ather-bot")).resolve()
        runtime = root / "runtime"
        return cls(
            root=root,
            runtime=runtime,
            secrets=runtime / "secrets",
            database=runtime / "ather-bot.db",
            token=runtime / "secrets" / "ather_token",
            owner=runtime / "owner_user_id",
            tailscale=runtime / "tailscale",
        )


DEFAULT_SETTINGS = {
    "battery_threshold": "20",
    "front_min_threshold": "25",
    "front_max_threshold": "35",
    "rear_min_threshold": "27",
    "rear_max_threshold": "37",
    "email_recipients": "",
    "email_enabled": "1",
    "gmail_provider": "",
    "gmail_mailbox": "",
    "socks_url": "",
    "selected_scooter": "",
}
