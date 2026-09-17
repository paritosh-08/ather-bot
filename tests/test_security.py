from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


def test_no_legacy_authentication_or_network_fallback():
    root = Path(__file__).parents[1]
    forbidden = (
        "tele" + "gram",
        "tail" + "scale",
        "generate-login-" + "otp",
        "verify-login-" + "otp",
    )
    for path in root.rglob("*"):
        if not path.is_file() or EXCLUDED_DIRS.intersection(path.parts):
            continue
        if path == Path(__file__):
            continue
        text = path.read_text(errors="ignore").casefold()
        for value in forbidden:
            assert value not in text, f"legacy feature remains in {path}"


def test_no_runtime_secrets_or_generated_state():
    root = Path(__file__).parents[1]
    forbidden_names = {"ather_token", "ather-bot.db", ".env", "platform.json"}
    forbidden_fragments = ("Bearer " + "eyJ", "PROMPTQL_USER_" + "JWT=")

    for path in root.rglob("*"):
        if not path.is_file() or EXCLUDED_DIRS.intersection(path.parts):
            continue
        if path == Path(__file__):
            continue
        assert path.name not in forbidden_names, f"runtime file committed: {path}"
        text = path.read_text(errors="ignore")
        for value in forbidden_fragments:
            assert value not in text, f"sensitive value leaked into {path}"
