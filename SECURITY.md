# Security Policy

This integration stores Tuya **cloud credentials** (access ID / secret) and device
**local keys** in the Home Assistant config entry. Treat them like passwords.

## Reporting a vulnerability

Please report security issues **privately** rather than in a public issue:

- Use GitHub's **Report a vulnerability** (Security → Advisories) on this repository, or
- Open a minimal issue asking to be contacted privately (do **not** include secrets).

When sharing logs, diagnostics, or data-point dumps, **redact** any `local_key`,
`access_id`, `access_secret`, and `device_id`.

## Supported versions

Only the latest released version receives fixes.
