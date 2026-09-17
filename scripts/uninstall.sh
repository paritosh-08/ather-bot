#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/workspace/ather-bot}"
read -r -p "Stop services and permanently delete $ROOT/runtime? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || exit 1
systemctl disable --now ather-bot-monitor.timer ather-bot-app.service 2>/dev/null || true
rm -f /etc/systemd/system/ather-bot-app.service
rm -f /etc/systemd/system/ather-bot-monitor.service
rm -f /etc/systemd/system/ather-bot-monitor.timer
systemctl daemon-reload
rm -rf "$ROOT/runtime"
echo "Runtime data removed. Delete the PromptQL trigger separately."
