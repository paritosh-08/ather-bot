import base64
import json

import pytest

from ather_bot.config import DEFAULT_SETTINGS
from ather_bot.web import page, parse_settings_form, visitor_id


def form(**overrides):
    values = {
        "battery_threshold": ["20"],
        "front_min_threshold": ["25"],
        "front_max_threshold": ["35"],
        "rear_min_threshold": ["27"],
        "rear_max_threshold": ["37"],
        "email_recipients": ["A@example.com, a@example.com; b@example.com"],
        "email_enabled": ["on"],
    }
    values.update(overrides)
    return values


def test_settings_are_normalized_and_deduplicated():
    values = parse_settings_form(form())
    assert values["email_recipients"] == "a@example.com,b@example.com"
    assert values["battery_threshold"] == "20"


def test_email_can_be_disabled_without_recipients():
    values = parse_settings_form(
        form(email_recipients=[""], email_enabled=[])
    )
    assert values["email_recipients"] == ""
    assert values["email_enabled"] == "0"


def test_rejects_invalid_ranges_and_email():
    with pytest.raises(ValueError, match="Front"):
        parse_settings_form(form(front_min_threshold=["35"]))
    with pytest.raises(ValueError, match="valid"):
        parse_settings_form(form(email_recipients=["not-an-email"]))


def test_visitor_subject_and_output_escaping():
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "owner-1"}).encode()
    ).decode().rstrip("=")
    assert visitor_id(f"x.{payload}.x") == "owner-1"

    settings = DEFAULT_SETTINGS | {"email_recipients": "<script>"}
    rendered = page(
        "<p>safe</p>",
        settings,
        {"last_values": {"battery": "<script>"}},
        "csrf",
    ).decode()
    assert "&lt;script&gt;" in rendered
    assert "<textarea name=\"email_recipients\"><script>" not in rendered