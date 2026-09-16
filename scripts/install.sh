#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/workspace/ather-bot}"
OWNER_USER_ID="${2:-}"
if [[ -z "$OWNER_USER_ID" ]]; then
  echo "Usage: sudo ./scripts/install.sh ROOT PROMPTQL_OWNER_USER_ID" >&2
  exit 2
fi

cd "$ROOT"
install -d -m 0700 "$ROOT/runtime" "$ROOT/runtime/secrets" "$ROOT/runtime/tailscale"
printf '%s' "$OWNER_USER_ID" > "$ROOT/runtime/owner_user_id"
chmod 0600 "$ROOT/runtime/owner_user_id"
chown -R promptql:promptql "$ROOT/runtime"

uv venv --quiet "$ROOT/.venv"
uv pip install --quiet --python "$ROOT/.venv/bin/python" -e "$ROOT"
chown -R promptql:promptql "$ROOT/.venv"

sed "s|@@ROOT@@|$ROOT|g" systemd/ather-bot-app.service.in \
  | install -m 0644 /dev/stdin /etc/systemd/system/ather-bot-app.service
sed "s|@@ROOT@@|$ROOT|g" systemd/ather-bot-monitor.service.in \
  | install -m 0644 /dev/stdin /etc/systemd/system/ather-bot-monitor.service
install -m 0644 systemd/ather-bot-monitor.timer.in \
  /etc/systemd/system/ather-bot-monitor.timer

systemctl daemon-reload
systemctl enable --now ather-bot-app.service
echo "Installed. Complete Ather login and Gmail configuration before enabling the monitor."
