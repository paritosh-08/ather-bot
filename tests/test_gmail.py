import base64
from email import message_from_bytes

from ather_bot.gmail import raw_message


def test_raw_message():
    encoded = raw_message(["a@example.com"], "Ather alert", "Battery: 10%")
    message = message_from_bytes(base64.urlsafe_b64decode(encoded))
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Ather alert"
