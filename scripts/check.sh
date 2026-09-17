#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
uv run ruff check .
uv run mypy
uv run pytest -q
bash -n scripts/*.sh
git diff --check
