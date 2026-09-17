# PromptQL installation contract

This file is for the PromptQL bot operating this repository.

## Non-negotiable safety rules

1. Never ask for or echo the Ather token, Gmail token, or Tailscale credential
   in chat.
2. Collect the Ather token only through the owner-restricted app.
3. Ask before sending a test email.
4. Try authenticated Ather telemetry directly before offering Tailscale.
5. Route only Ather requests through Tailscale's local SOCKS proxy.
6. Never install/enable machine-wide Tailscale, accept DNS/routes, or change the
   VM default route.
7. Do not persist `$PROMPTQL_USER_JWT`.
8. Do not claim success until app readiness, telemetry, timer, Gmail profile,
   and test delivery have all been verified.
9. Never commit generated runtime files or downloaded binaries.

## Installation flow

### 1. Preconditions

- Confirm VM v2 is available.
- Read `promptql.manifest.json`.
- Resolve the acting user's connected Gmail provider. Prefer the verified
  provider, but do not hardcode `__gmail-v2`.
- Validate the provider with:
  `GET https://www.googleapis.com/gmail/v1/users/me/profile`.
- If no Gmail provider is connected, emit the appropriate PromptQL
  `<connect_integration ... />` card and stop. Resume after connection.

### 2. Install

Clone into `/workspace/ather-bot`, then run:

```bash
sudo ./scripts/install.sh /workspace/ather-bot "$PROMPTQL_USER_ID"
```

If `PROMPTQL_USER_ID` is not present in the VM environment, obtain the triggering
user's PromptQL ID from context and pass it explicitly. The script is idempotent.

### 3. Publish the app

Ensure `ather-bot-app.service` is active and `/readyz` returns 204. Store an App
Artifact named `ather-bot` using:

```json
{
  "version": 2,
  "host": "vm",
  "sandbox_id": "<PROMPTQL_SANDBOX_ID>",
  "kind": "web",
  "port": 8085,
  "protocol": "http",
  "readiness": {"path": "/readyz"}
}
```

The app identifies the visitor through `X-PromptQL-Visitor-Token` and permits
configuration only for the installer user ID.

### 4. Ather authentication

Ask the user to open the app and paste an existing Ather API token there. Never
ask them to put it in chat. The app strips an optional `Bearer` prefix, checks
the token's expiry, discovers the scooter, and verifies live telemetry before
atomically storing it under `runtime/secrets/ather_token`.

Try authenticated telemetry directly first. If that fails with a classified
network/blocking error:

1. Ask whether the user wants the isolated Tailscale fallback.
2. Download the pinned Tailscale release through
   `scripts/download-tailscale.sh`; verify its SHA-256.
3. Start userspace `tailscaled` with local socket/state and loopback SOCKS.
4. Show the login URL returned by `tailscale up`.
5. Wait for the user to authorize it.
6. List only exit-node-capable devices and ask the user to select one.
7. Configure the exit node for the userspace daemon.
8. Verify direct egress/default route remain unchanged and SOCKS works.
9. Ask the user to resubmit the token in the private app so telemetry can be
   verified and the token stored.

### 5. Configure and activate

The user selects a scooter, battery threshold, tyre safe ranges, recipients, and whether email is
enabled. Resolve and store only the Gmail provider ID and mailbox address—never
OAuth credentials.

Run a baseline without alerts:

```bash
.venv/bin/ather-bot monitor --once --bootstrap --json
```

After explicit approval, send one test email through the connected Gmail
integration using `POST /gmail/v1/users/me/messages/send`.

Enable/start `ather-bot-monitor.timer`.

### 6. Durable Gmail delivery

Create one recurring PromptQL trigger, every 30 minutes, owned by the installing
user. Its interaction must run:

```bash
cd /workspace/ather-bot
.venv/bin/ather-bot gmail-drain --json
```

The command reads `$PROMPTQL_PLATFORM_API_URL` and `$PROMPTQL_USER_JWT` from the
fresh interaction environment. It must not write the JWT to disk. Tell the user
email delivery may lag by up to 30 minutes.

### 7. Verification

Check all of:

```bash
curl -fsS http://127.0.0.1:8085/readyz
.venv/bin/ather-bot doctor --json
.venv/bin/ather-bot status --json
systemctl is-enabled ather-bot-monitor.timer
systemctl is-active ather-bot-monitor.timer
ip route show default
```

Verify the Gmail profile and confirm the test message API response has an ID.
If Tailscale is active, verify the host route/direct egress are unchanged and
that an Ather request succeeds through SOCKS. Do not proxy unrelated probes.

## Upgrade, rollback, uninstall

- Back up `runtime/ather-bot.db` and `runtime/secrets/`.
- Pull a tagged release, run tests, restart the app, and perform one monitor run.
- Roll back to the prior tag if either check fails.
- For uninstall, delete the PromptQL trigger, disable services, run
  `scripts/uninstall.sh`, and revoke Tailscale authorization if used.
