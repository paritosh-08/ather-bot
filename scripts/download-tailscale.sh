#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/workspace/ather-bot}"
VERSION="${TAILSCALE_VERSION:-1.88.3}"
ARCH="${TAILSCALE_ARCH:-amd64}"
BASE="https://pkgs.tailscale.com/stable"
ARCHIVE="tailscale_${VERSION}_${ARCH}.tgz"
mkdir -p "$ROOT/bin"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSLo "$tmp/$ARCHIVE" "$BASE/$ARCHIVE"
curl -fsSLo "$tmp/SHA256SUMS.txt" "$BASE/SHA256SUMS.txt"
(cd "$tmp" && grep "  $ARCHIVE$" SHA256SUMS.txt | sha256sum -c -)
tar -xzf "$tmp/$ARCHIVE" -C "$tmp"
install -m 0755 "$tmp/tailscale_${VERSION}_${ARCH}/tailscale" "$ROOT/bin/tailscale"
install -m 0755 "$tmp/tailscale_${VERSION}_${ARCH}/tailscaled" "$ROOT/bin/tailscaled"
echo "Installed Tailscale $VERSION ($ARCH); no system service was created."
