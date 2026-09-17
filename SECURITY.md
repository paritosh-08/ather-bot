# Security policy

## Secrets

Never commit or paste Ather API tokens, Gmail credentials, or PromptQL JWTs.
Runtime secrets belong under `runtime/secrets/` with mode `0600`.

## Network boundary

Ather telemetry uses direct HTTPS from the bot VM. This project does not install
or manage VPN software and does not alter VM routing or DNS.

## App authorization

The setup app listens on the VM guest interface and is published only through
PromptQL's authenticated App Artifact proxy. It accepts configuration only from
the installer identified by the platform visitor token. State-changing requests
require CSRF validation.

## Revocation

- Ather: renew/revoke the session in the Ather account.
- Gmail: disconnect the integration in PromptQL/Google Account permissions.
- PromptQL: delete the recurring trigger and bot/VM.

## Reporting

Open a GitHub security advisory rather than a public issue. Do not include live
credentials, complete telemetry payloads, or personal data.
