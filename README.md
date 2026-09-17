# Ather Bot for PromptQL

Set up an always-on Ather scooter monitor in a PromptQL bot VM. It watches battery
and tyre pressure, provides a private App Artifact for configuration, and sends
transition/recovery alerts through the user's connected Gmail integration.

> Unofficial community project. It uses Ather's private mobile APIs and is not
> affiliated with or supported by Ather Energy.

## Quick start

Create a PromptQL bot with a v2 VM and say:

```text
Use https://github.com/paritosh-08/ather-bot to set up Gmail alerts for my
Ather battery and tyre pressure.
```

PromptQL should then:

1. Check whether your Gmail integration is connected and can send mail.
2. Install this repository into its VM.
3. Publish a private **Ather Bot** App Artifact.
4. Ask you to enter an existing Ather API token inside the app.
5. Verify the token with a live Ather telemetry request.
6. If Ather is unreachable, offer an isolated Tailscale login and retry.
7. Discover your scooter and read live telemetry.
8. Let you set battery/front/rear thresholds and recipient emails.
9. Send a test email, activate a five-minute monitor, and show live status.

Your Ather token must never be pasted into PromptQL chat.

## Prerequisites

- PromptQL project with a **v2 VM**
- Connected Gmail integration with send/compose permission
- An existing, unexpired Ather API token
- Permission to publish an App Artifact, install user-owned `systemd` units, and
  create a recurring PromptQL trigger
- If direct Ather access is blocked: Tailscale and an exit-node-capable device in
  a region from which Ather works

## Architecture

```text
Ather API ← direct requests OR local SOCKS ← userspace Tailscale
                       ↑
              VM monitor + SQLite
                       ↓ durable queue
PromptQL scheduled trigger → Gmail integration → recipients
                       ↑
                private App Artifact
```

Only Ather HTTP calls may use the SOCKS proxy. Gmail, PromptQL, and all other VM
traffic remain on the VM's normal network path.

## Defaults

| Setting | Default |
|---|---:|
| Battery alert | below 20% |
| Front tyre alert | below 25 PSI or above 35 PSI |
| Rear tyre alert | below 27 PSI or above 37 PSI |
| Telemetry check | every 5 minutes |
| Gmail queue drain | every 30 minutes |
| Repeat reminders | disabled |

Lower/upper tyre bounds, the battery threshold, and recipients can be changed in the App Artifact.

## Alert behavior

A notification is created only when a metric crosses from normal to alert. A
recovery message is created when it returns to normal. Repeated checks in the
same state are suppressed. The first successful run establishes a baseline and
does not send surprise alerts. Three consecutive telemetry failures create one
monitor-health event.

## Security

- The App Artifact is restricted to the PromptQL user who installed it.
- The Ather token is collected only in the private app and verified before storage.
- Secrets live under `runtime/secrets/` with mode `0600`; runtime directories use
  `0700`.
- Secrets are never printed, included in command arguments, committed, or stored
  in artifacts.
- PromptQL/Gmail OAuth credentials never enter this repository.
- Tailscale uses userspace networking and a loopback-only SOCKS listener. It must
  not change the VM route, DNS, or install/enable a machine-wide VPN.
- Gmail messages are queued locally. A recurring PromptQL interaction drains the
  queue with the acting user's fresh credentials; no PromptQL JWT is persisted.
- State-changing app requests require PromptQL visitor identity plus CSRF
  protection.

See [SECURITY.md](SECURITY.md) for reporting, revocation, and threat boundaries.

## Operations

Assuming installation root `/workspace/ather-bot`:

```bash
cd /workspace/ather-bot
.venv/bin/ather-bot doctor --json
.venv/bin/ather-bot status --json
.venv/bin/ather-bot monitor --once --json
.venv/bin/ather-bot gmail-drain --json
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

Back up `runtime/ather-bot.db` and `runtime/secrets/ather_token` before an upgrade.

### Uninstalling

```bash
sudo ./scripts/uninstall.sh /workspace/ather-bot
```

Then delete the PromptQL recurring trigger and the App Artifact reference. The
uninstaller stops/disables services and removes runtime data only after explicit
confirmation.

## Tailscale fallback

The installer first performs the real Ather request directly. Tailscale should
be offered only for timeout, connection failure, or a confirmed geographic/bot
block. An unauthenticated `403` alone does **not** prove the source IP is blocked.

The fallback uses standalone, checksum-verified Tailscale binaries:

- `tailscaled --tun=userspace-networking`
- state and socket under `runtime/tailscale/`
- SOCKS5 on `127.0.0.1`
- no accepted routes or DNS
- no machine-wide exit-node configuration

PromptQL shows the Tailscale login URL, then asks you to select from advertised
exit nodes. It must verify that the host default route and direct egress remain
unchanged; its SOCKS test must target Ather, not route unrelated traffic.

By default Tailscale state is ephemeral. VM/daemon replacement may require
authorization again.

## Troubleshooting

### Ather returns 403

Confirm that the token is current. If the same token works from another machine,
retry through the isolated Tailscale fallback. Do not change the VM's default
route or infer that the token is invalid from an unauthenticated endpoint.

### No Tailscale exit node

Enable exit-node advertising on a trusted tailnet device, approve it in
Tailscale, then refresh the app. Never silently choose an arbitrary device.

### Gmail is disconnected

Reconnect Gmail in PromptQL, verify `/gmail/v1/users/me/profile`, and rerun the
queue drain. The repository must not hardcode a Gmail provider version.

### Gmail is connected but sending fails

Confirm the chosen mailbox, send/compose scope, PromptQL trigger ownership, and
the recurring trigger's latest run. Queued mail can be delayed by up to the
trigger interval.

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

## Limitations

- Ather's private APIs can change without notice.
- Tyre-pressure freshness depends on the scooter's latest telemetry.
- Gmail delivery can lag by the recurring-trigger interval.
- Ephemeral Tailscale may require reauthorization.
- Version 0.1 supports one Ather account and one selected scooter per install.
