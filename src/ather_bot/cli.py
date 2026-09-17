from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, get_status
from .gmail import configure, drain, profile, send_test
from .monitor import record_failure, run
from .web import serve


def doctor(paths: Paths) -> dict[str, Any]:
    settings = get_settings(connect(paths.database), DEFAULT_SETTINGS)
    checks = {
        "owner_configured": paths.owner.is_file(),
        "ather_token_configured": paths.token.is_file(),
        "gmail_provider_configured": bool(settings["gmail_provider"]),
        "email_recipients_configured": bool(settings["email_recipients"]),
    }
    return {"ok": all(checks.values()), "root": str(paths.root), **checks}


def status(paths: Paths) -> dict[str, Any]:
    conn = connect(paths.database)
    result = get_status(conn)
    result["pending_emails"] = conn.execute(
        "SELECT COUNT(1) FROM email_queue WHERE state='pending'"
    ).fetchone()[0]
    result["ok"] = bool(result.get("last_success_at")) and not result.get(
        "last_error"
    )
    return result


def output(result: dict[str, Any]) -> None:
    print(json.dumps(result, separators=(",", ":")))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="ather-bot")
    sub = command.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check installation prerequisites")
    sub.add_parser("status", help="Show monitor and queue status")

    monitor = sub.add_parser("monitor", help="Run one telemetry check")
    monitor.add_argument(
        "--bootstrap",
        action="store_true",
        help="Establish state without sending threshold alerts",
    )

    gmail_check = sub.add_parser("gmail-check", help="Verify a Gmail provider")
    gmail_check.add_argument("--provider", required=True)

    gmail_configure = sub.add_parser(
        "gmail-configure",
        help="Verify and save the Gmail provider",
    )
    gmail_configure.add_argument("--provider", required=True)
    gmail_configure.add_argument("--mailbox", required=True)

    gmail_test = sub.add_parser("gmail-test", help="Send a test alert")
    gmail_test.add_argument("--recipient", action="append", required=True)

    sub.add_parser("gmail-drain", help="Deliver queued email alerts")
    sub.add_parser("serve", help="Run the private setup application")
    return command


def dispatch(args: argparse.Namespace, paths: Paths) -> dict[str, Any] | None:
    if args.command == "doctor":
        return doctor(paths)
    if args.command == "status":
        return status(paths)
    if args.command == "gmail-check":
        return profile(args.provider)
    if args.command == "gmail-configure":
        return configure(paths, args.provider, args.mailbox)
    if args.command == "gmail-test":
        return send_test(paths, args.recipient)
    if args.command == "gmail-drain":
        return drain(paths)
    if args.command == "serve":
        serve(paths)
        return None

    try:
        return run(paths, bootstrap=args.bootstrap)
    except Exception as exc:
        result = record_failure(paths, exc)
        output(result)
        raise


def main() -> None:
    args = parser().parse_args()
    try:
        result = dispatch(args, Paths.from_env())
        if result is not None:
            output(result)
    except Exception as exc:  # noqa: BLE001
        if args.command != "monitor":
            output(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            )
        sys.exit(1)
