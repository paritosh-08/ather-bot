# PromptQL installation contract

This file is for the PromptQL bot operating this repository.

## Non-negotiable rules

1. Never ask for or echo the Ather token or Gmail token in chat.
2. Collect the Ather token only through the owner-restricted app.
3. Use the VM's direct network path for Ather.
4. Do not persist `$PROMPTQL_USER_JWT`.
5. Ask before sending a test email.
6. Do not claim success until app readiness, live telemetry, timer, Gmail
   profile, and test delivery have all been verified.
7. Never commit generated runtime files or downloaded binaries.

## Installation flow

### 1. Preconditions

- Confirm VM v2 is available.
- Read `promptql.manifest.json`.
- Resolve the acting user's connected Gmail provider; do not hardcode a version.
- Validate it with
  `GET https://www.googleapis.com/gmail/v1/users/me/profile`.
- If Gmail is disconnected, emit its PromptQL connection card and stop.

### 2. Install

```bash
git clone https://github.com/paritosh-08/ather-bot /workspace/ather-bot
cd /workspace/ather-bot
sudo ./scripts/install.sh /workspace/ather-bot "$PROMPTQL_USER_ID"
```

If `PROMPTQL_USER_ID` is absent, obtain the triggering user's ID from context
and pass it explicitly. Installation is idempotent.

### 3. Publish the app

Ensure `ather-bot-app.service` is active and `/readyz` returns 204. Store an App
Artifact named `ather-bot`:

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

The app authorizes the installer through `X-PromptQL-Visitor-Token`.

### 4. Ather authentication

Ask the user to open the app and paste an existing Ather API token there. Never
ask for it in chat. The app strips an optional `Bearer` prefix, checks token
expiry, discovers the scooter, and verifies live telemetry over direct HTTPS
before atomically storing `runtime/secrets/ather_token`.

If direct authenticated telemetry fails, report the status without exposing the
token. Do not improvise alternate routing or weaken token validation.

### 5. Configure and activate

The user configures battery threshold, tyre safe ranges, recipients, and email
enablement in the app. Resolve and store only the Gmail provider ID and mailbox,
never OAuth credentials.

Run the alert-free baseline:

```bash
.venv/bin/ather-bot monitor --bootstrap
```

After explicit approval, send one Gmail test and enable/start
`ather-bot-monitor.timer`.

### 6. Durable Gmail delivery

Create a recurring PromptQL trigger every 30 minutes, owned by the installer.
It runs:

```bash
cd /workspace/ather-bot
.venv/bin/ather-bot gmail-drain
```

The command consumes the fresh interaction's platform URL and user JWT from the
environment and never writes the JWT to disk.

### 7. Verification

```bash
curl -fsS http://127.0.0.1:8085/readyz
.venv/bin/ather-bot doctor
.venv/bin/ather-bot status
systemctl is-enabled ather-bot-monitor.timer
systemctl is-active ather-bot-monitor.timer
```

Also verify the Gmail profile and test-send response ID.

## Upgrade, rollback, uninstall

- Back up `runtime/ather-bot.db` and `runtime/secrets/`.
- Pull a tagged release, run tests, restart the app, and perform one monitor run.
- Roll back if either check fails.
- For uninstall, delete the PromptQL trigger, disable services, and run
  `scripts/uninstall.sh`.
