# Security policy

## Secrets

Never commit or paste Ather phone numbers, OTPs, JWTs, Gmail credentials,
PromptQL JWTs, or Tailscale credentials. Runtime secrets belong under
`runtime/secrets/` with mode `0600`.

## Network boundary

Tailscale is optional and must operate only as a userspace SOCKS proxy for Ather
traffic. A change to the VM's default route or DNS is a security failure.

## App authorization

The setup app listens on the VM guest interface and is published only through PromptQL's authenticated App Artifact proxy. It accepts
configuration only from the installer user identified by the platform-provided
visitor token. State-changing requests require CSRF validation.

## Revocation

- Ather: renew/revoke the session in the Ather account.
- Gmail: disconnect the integration in PromptQL/Google Account permissions.
- Tailscale: remove the VM device from the tailnet.
- PromptQL: delete the recurring trigger and bot/VM.

## Reporting

Open a GitHub security advisory rather than a public issue for vulnerabilities.
Do not include live credentials, complete telemetry payloads, or personal data.
