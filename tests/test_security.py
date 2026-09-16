from pathlib import Path


def test_no_runtime_secrets_or_generated_state():
    root = Path(__file__).parents[1]
    forbidden_names = {"ather_token", "platform.json", "ather-bot.db", ".env"}
    forbidden_fragments = (
        "Bearer " + "eyJ",
        "PROMPTQL_USER_" + "JWT=",
    )
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or ".venv" in path.parts
            or "__pycache__" in path.parts
            or path == Path(__file__)
        ):
            continue
        assert path.name not in forbidden_names, f"runtime file committed: {path}"
        text = path.read_text(errors="ignore")
        for value in forbidden_fragments:
            assert value not in text, f"sensitive value leaked into {path}"
