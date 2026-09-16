from ather_bot.monitor import is_active, message

LIMITS = {
    "battery": (20.0, None),
    "front": (25.0, 35.0),
    "rear": (27.0, 37.0),
}


def test_message_ranges():
    body = message(
        "Ather alert",
        ["battery", "front", "rear"],
        {"battery": 10, "front": 24, "rear": 38},
        LIMITS,
    )
    assert "Battery: 10%" in body
    assert "below 20%" in body
    assert "outside 25–35 PSI" in body
    assert "outside 27–37 PSI" in body


def test_threshold_boundaries_are_safe():
    assert is_active("battery", 19.9, LIMITS)
    assert not is_active("battery", 20.0, LIMITS)
    assert is_active("front", 24.9, LIMITS)
    assert not is_active("front", 25.0, LIMITS)
    assert not is_active("front", 35.0, LIMITS)
    assert is_active("front", 35.1, LIMITS)
    assert is_active("rear", 26.9, LIMITS)
    assert not is_active("rear", 27.0, LIMITS)
    assert not is_active("rear", 37.0, LIMITS)
    assert is_active("rear", 37.1, LIMITS)
