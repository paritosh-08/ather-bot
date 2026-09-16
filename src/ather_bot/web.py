from __future__ import annotations

import base64
import html
import json
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from .ather import Client
from .config import DEFAULT_SETTINGS, Paths
from .db import connect, get_settings, get_status, set_settings
from .util import save_secret

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def visitor_id(header: str) -> str | None:
    try:
        payload = header.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))["sub"]
    except Exception:  # noqa: BLE001
        return None


def page(message: str, settings: dict[str, str], status: dict, csrf: str) -> bytes:
    metric_rows = ""
    values = status.get("last_values", {})
    for key, label, unit in (
        ("battery", "Battery", "%"),
        ("front", "Front tyre", " PSI"),
        ("rear", "Rear tyre", " PSI"),
    ):
        value = values.get(key)
        metric_rows += f"<li><b>{label}</b>: {'—' if value is None else html.escape(str(value)) + unit}</li>"
    checked = "checked" if settings["email_enabled"] == "1" else ""
    body = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Ather Bot</title>
<style>body{{font:15px system-ui;max-width:760px;margin:36px auto;padding:0 18px;background:#f6f8fc;color:#172033}}
.card{{background:white;border:1px solid #e1e6ee;border-radius:14px;padding:20px;margin:16px 0}}
label{{display:block;font-weight:650;margin:11px 0}}input,textarea{{display:block;width:100%;box-sizing:border-box;padding:10px;margin-top:5px}}
button{{background:#1769e0;color:white;border:0;border-radius:8px;padding:11px 15px;font-weight:700}}.msg{{padding:10px;background:#eef6ff;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}</style></head><body>
<h1>Ather Bot</h1><p>Private setup and live telemetry status.</p>{message}
<div class="card"><h2>Status</h2><ul>{metric_rows}</ul><p>Last check: {html.escape(str(status.get("last_success_at", "Not yet")))}</p></div>
<div class="card"><h2>Alert settings</h2><form method="post" action="/settings">
<input type="hidden" name="csrf" value="{csrf}">
<label>Battery below (%)<input name="battery_threshold" type="number" min="1" max="100" step=".1" value="{html.escape(settings['battery_threshold'])}"></label>
<div class="grid">
<label>Front tyre below (PSI)<input name="front_min_threshold" type="number" min="1" max="100" step=".1" value="{html.escape(settings['front_min_threshold'])}"></label>
<label>Front tyre above (PSI)<input name="front_max_threshold" type="number" min="1" max="100" step=".1" value="{html.escape(settings['front_max_threshold'])}"></label>
<label>Rear tyre below (PSI)<input name="rear_min_threshold" type="number" min="1" max="100" step=".1" value="{html.escape(settings['rear_min_threshold'])}"></label>
<label>Rear tyre above (PSI)<input name="rear_max_threshold" type="number" min="1" max="100" step=".1" value="{html.escape(settings['rear_max_threshold'])}"></label></div>
<label>Email recipients<textarea name="email_recipients">{html.escape(settings['email_recipients'])}</textarea></label>
<label><input style="display:inline;width:auto" type="checkbox" name="email_enabled" {checked}> Email alerts enabled</label>
<button>Save settings</button></form></div>
<div class="card"><h2>Ather login</h2><form method="post" action="/otp/request">
<input type="hidden" name="csrf" value="{csrf}"><label>Registered mobile number<input name="phone" inputmode="numeric" autocomplete="tel"></label>
<button>Send OTP</button></form>
<form method="post" action="/otp/verify"><input type="hidden" name="csrf" value="{csrf}">
<label>Registered mobile number<input name="phone" inputmode="numeric" autocomplete="tel"></label>
<label>OTP<input name="otp" inputmode="numeric" autocomplete="one-time-code"></label>
<button>Verify OTP</button></form></div></body></html>"""
    return body.encode()


class App:
    def __init__(self, paths: Paths):
        self.paths = paths
        self.csrf = secrets.token_urlsafe(32)

    def handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def authorized(self) -> bool:
                try:
                    owner = app.paths.owner.read_text(encoding="utf-8").strip()
                except OSError:
                    return False
                return visitor_id(self.headers.get("X-PromptQL-Visitor-Token", "")) == owner

            def form(self) -> dict[str, list[str]]:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 30000:
                    raise ValueError("Request too large.")
                return parse_qs(self.rfile.read(length).decode())

            def send_html(self, code: int = 200, message: str = "") -> None:
                conn = connect(app.paths.database)
                body = page(message, get_settings(conn, DEFAULT_SETTINGS), get_status(conn), app.csrf)
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/readyz":
                    self.send_response(204)
                    self.end_headers()
                    return
                if self.path != "/":
                    self.send_error(404)
                    return
                if not self.authorized():
                    self.send_html(403, '<p class="msg">Not authorized.</p>')
                    return
                self.send_html()

            def do_POST(self) -> None:
                if self.path not in ("/settings", "/otp/request", "/otp/verify"):
                    self.send_error(404)
                    return
                if not self.authorized():
                    self.send_html(403, '<p class="msg">Not authorized.</p>')
                    return
                try:
                    form = self.form()
                    if not secrets.compare_digest(form.get("csrf", [""])[0], app.csrf):
                        raise ValueError("Invalid form session; refresh the page.")
                    conn = connect(app.paths.database)
                    settings = get_settings(conn, DEFAULT_SETTINGS)
                    if self.path == "/settings":
                        emails = [x.strip().lower() for x in re.split(r"[,;\n]+", form.get("email_recipients", [""])[0]) if x.strip()]
                        if not emails or any(not EMAIL_RE.match(x) for x in emails):
                            raise ValueError("Enter at least one valid email.")
                        values = {}
                        threshold_names = (
                            "battery_threshold",
                            "front_min_threshold",
                            "front_max_threshold",
                            "rear_min_threshold",
                            "rear_max_threshold",
                        )
                        for name in threshold_names:
                            value = float(form.get(name, [""])[0])
                            if not 1 <= value <= 100:
                                raise ValueError("Thresholds must be between 1 and 100.")
                            values[name] = str(value)
                        if float(values["front_min_threshold"]) >= float(
                            values["front_max_threshold"]
                        ):
                            raise ValueError("Front minimum must be below its maximum.")
                        if float(values["rear_min_threshold"]) >= float(
                            values["rear_max_threshold"]
                        ):
                            raise ValueError("Rear minimum must be below its maximum.")
                        values["email_recipients"] = ",".join(emails)
                        values["email_enabled"] = "1" if form.get("email_enabled") else "0"
                        set_settings(conn, values)
                        message = '<p class="msg">Settings saved.</p>'
                    else:
                        client = Client(socks_url=settings["socks_url"])
                        phone = form.get("phone", [""])[0]
                        if self.path == "/otp/request":
                            client.request_otp(phone)
                            message = '<p class="msg">OTP sent by Ather.</p>'
                        else:
                            token, expiry = client.verify_otp(phone, form.get("otp", [""])[0])
                            authenticated = Client(token=token, socks_url=settings["socks_url"])
                            reading = authenticated.telemetry(settings["selected_scooter"] or None)
                            save_secret(app.paths.token, token)
                            set_settings(conn, {"selected_scooter": reading.scooter_id})
                            message = (
                                '<p class="msg">Ather login saved and telemetry verified. '
                                f'Token expires {time.strftime("%Y-%m-%d", time.gmtime(expiry))}.</p>'
                            )
                    self.send_html(message=message)
                except Exception as exc:  # noqa: BLE001
                    self.send_html(400, f'<p class="msg">{html.escape(str(exc))}</p>')

            def log_message(self, fmt: str, *args) -> None:
                pass

        return Handler


def serve(paths: Paths, port: int = 8085) -> None:
    ThreadingHTTPServer(("0.0.0.0", port), App(paths).handler()).serve_forever()
