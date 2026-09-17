from __future__ import annotations

import argparse
import json
import sys

from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, get_status
from .gmail import configure, drain, profile, queue_test
from .monitor import record_failure, run
from .web import serve


def doctor(paths: Paths) -> dict:
    conn = connect(paths.database)
    settings = get_settings(conn, DEFAULT_SETTINGS)
    return {
        "ok": True,
        "root": str(paths.root),
        "owner_configured": paths.owner.exists(),
        "ather_token_configured": paths.token.exists(),
        "gmail_provider_configured": bool(settings["gmail_provider"]),
        "email_recipients_configured": bool(settings["email_recipients"]),
    }


def status(paths: Paths) -> dict:
    conn = connect(paths.database)
    result = get_status(conn)
    result["pending_emails"] = conn.execute(
        "SELECT COUNT(1) FROM email_queue WHERE state='pending'"
    ).fetchone()[0]
    result["ok"] = result.get("last_error") is None
    return result


def print_result(result: dict) -> None:
    print(json.dumps(result, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(prog="ather-bot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")
    sub.add_parser("status")

    monitor = sub.add_parser("monitor")
    monitor.add_argument("--once", action="store_true")
    monitor.add_argument("--bootstrap", action="store_true")

    gmail_check = sub.add_parser("gmail-check")
    gmail_check.add_argument("--provider", required=True)

    gmail_configure = sub.add_parser("gmail-configure")
    gmail_configure.add_argument("--provider", required=True)
    gmail_configure.add_argument("--mailbox", required=True)

    gmail_test = sub.add_parser("gmail-test")
    gmail_test.add_argument("--recipient", action="append", required=True)

    sub.add_parser("gmail-drain")

    sub.add_parser("serve")

    args = parser.parse_args()
    paths = Paths.from_env()
    try:
        if args.command == "doctor":
            result = doctor(paths)
        elif args.command == "status":
            result = status(paths)
        elif args.command == "gmail-check":
            result = profile(args.provider)
        elif args.command == "gmail-configure":
            result = configure(paths, args.provider, args.mailbox)
        elif args.command == "gmail-test":
            result = queue_test(paths, args.recipient)
        elif args.command == "gmail-drain":
            result = drain(paths)
        elif args.command == "serve":
            serve(paths)
            return
        else:
            try:
                result = run(paths, bootstrap=args.bootstrap)
            except Exception as exc:
                result = record_failure(paths, exc)
                print_result(result)
                raise
        print_result(result)
    except Exception as exc:  # noqa: BLE001
        if args.command != "monitor":
            print_result(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            )
        sys.exit(1)
