# Ather Bot for PromptQL

Set up an always-on Ather scooter monitor in a PromptQL bot VM. It watches
battery and tyre pressure, provides a private App Artifact for configuration,
and sends transition/recovery alerts through the user's connected Gmail
integration.

> Unofficial community project. It uses Ather's private mobile APIs and is not
> affiliated with or supported by Ather Energy.

## Quick start

Create a PromptQL bot with a v2 VM and say:

```text
Use https://github.com/paritosh-08/ather-bot to set up Gmail alerts for my
Ather battery and tyre pressure.
```

PromptQL should:

1. Check that your Gmail integration is connected and can send mail.
2. Install this repository into its VM.
3. Publish a private **Ather Bot** App Artifact.
4. Ask you to enter an existing Ather API token inside the private app.
5. Verify the token with live Ather telemetry over the VM's direct connection.
6. Discover your scooter and show live battery and tyre-pressure readings.
7. Let you configure thresholds and email recipients.
8. Send a test email, activate the five-minute monitor, and show live status.

Never paste your Ather token into PromptQL chat.

## Prerequisites

- PromptQL project with a **v2 VM**
- Connected Gmail integration with send/compose permission
- Existing, unexpired Ather API token
- Permission to publish an App Artifact, install systemd units, and create a
  recurring PromptQL trigger

## Architecture

```text
Ather API ← direct HTTPS ← VM monitor + SQLite
                                  ↓ durable queue
PromptQL scheduled trigger → Gmail integration → recipients
                                  ↑
                           private App Artifact
```

## Defaults

| Setting | Default |
|---|---:|
| Battery alert | below 20% |
| Front tyre alert | below 25 PSI or above 35 PSI |
| Rear tyre alert | below 27 PSI or above 37 PSI |
| Telemetry check | every 5 minutes |
| Gmail queue drain | every 30 minutes |
| Repeat reminders | disabled |

All thresholds and recipients can be changed in the App Artifact.

## Alert behavior

An alert is queued only when a metric crosses from normal to alert. A recovery
message is queued when it returns to normal. Repeated checks in the same state
are suppressed. The first successful run establishes a baseline without
sending surprise alerts. Three consecutive telemetry failures create one
monitor-health event.

## Security

- The App Artifact is restricted to the PromptQL user who installed it.
- The Ather token is collected only in the private app.
- The token's expiry and live telemetry access are verified before storage.
- Secrets live under `runtime/secrets/` with mode `0600`; runtime directories
  use `0700`.
- Secrets are never printed, passed in command arguments, committed, or stored
  in artifacts.
- PromptQL/Gmail OAuth credentials never enter this repository.
- Gmail messages are queued locally. A recurring PromptQL interaction drains
  the queue with the acting user's fresh credentials; no PromptQL JWT is
  persisted.
- State-changing app requests require PromptQL visitor identity plus CSRF
  protection.

See [SECURITY.md](SECURITY.md).

## Operations

Assuming installation root `/workspace/ather-bot`:

```bash
cd /workspace/ather-bot
.venv/bin/ather-bot doctor
.venv/bin/ather-bot status
.venv/bin/ather-bot monitor
.venv/bin/ather-bot gmail-drain
journalctl -u ather-bot-monitor.service -n 100 --no-pager
systemctl list-timers ather-bot-monitor.timer --no-pager
```

### Updating

```bash
cd /workspace/ather-bot
git pull --ff-only
uv sync --all-extras
sudo systemctl restart ather-bot-app.service
sudo systemctl start ather-bot-monitor.service
```

Back up `runtime/ather-bot.db` and `runtime/secrets/ather_token` first.

### Uninstalling

```bash
sudo ./scripts/uninstall.sh /workspace/ather-bot
```

Then delete the PromptQL recurring trigger and App Artifact reference.

## Troubleshooting

### Token rejected or Ather returns 401/403

Confirm the token is current and works from another trusted client. The app
stores it only after authenticated scooter discovery and live telemetry both
succeed.

### Gmail is disconnected

Reconnect Gmail in PromptQL, verify `/gmail/v1/users/me/profile`, and rerun the
queue drain. Do not hardcode a Gmail provider version.

### Gmail is connected but sending fails

Confirm the mailbox, send/compose scope, PromptQL trigger ownership, and the
recurring trigger's latest run. Queued mail can be delayed by up to the trigger
interval.

### App says “upstream HTTP request failed”

Check:

```bash
systemctl status ather-bot-app.service --no-pager
curl -i http://127.0.0.1:8085/readyz
journalctl -u ather-bot-app.service -n 100 --no-pager
```

The App Artifact declaration does not start the web service.

### Telemetry fields are missing

Ather may have changed its private schema. Save a redacted response shape (keys
and types only), update the parser, and add a fixture-based regression test.

## Development

```bash
uv sync --all-extras
./scripts/check.sh
```

## Limitations

- Ather's private APIs can change without notice.
- Direct Ather access must be available from the bot VM.
- Tyre-pressure freshness depends on the scooter's latest telemetry.
- Gmail delivery can lag by the recurring-trigger interval.
- Version 0.1 supports one Ather account and one selected scooter per install.
