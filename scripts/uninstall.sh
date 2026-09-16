#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/workspace/ather-bot}"
read -r -p "Stop services and permanently delete $ROOT/runtime? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || exit 1
systemctl disable --now ather-bot-monitor.timer ather-bot-app.service 2>/dev/null || true
if [[ -x "$ROOT/.venv/bin/ather-bot" ]]; then
  sudo -u promptql env ATHER_BOT_ROOT="$ROOT" "$ROOT/.venv/bin/ather-bot" tailscale-stop >/dev/null 2>&1 || true
fi
rm -f /etc/systemd/system/ather-bot-app.service
rm -f /etc/systemd/system/ather-bot-monitor.service
rm -f /etc/systemd/system/ather-bot-monitor.timer
systemctl daemon-reload
rm -rf "$ROOT/runtime"
echo "Runtime data removed. Delete the PromptQL trigger and revoke Tailscale separately."
