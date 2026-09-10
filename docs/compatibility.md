# Device and protocol compatibility

[Overview](../README.md) · [Installation](installation.md) · [Tuya setup](tuya-setup.md) · [Features](features.md)

This matrix separates behaviour verified on physical equipment from mappings
derived from a Tuya thing model or from protocol captures. Please keep that
distinction when reporting or adding a device.

| Device / model | Connection | Verified behaviour | Remaining caveats |
|---|---|---|---|
| AGP / Intex QS1600 Plus | Local Tuya + optional cloud schedules | Local status and controls; `skdl_salt` decode/encode round-trip; schedule writes and readback | The second chlorine-production datapoint (DP102) is not hardware-verified and stays disabled by default. Duration/day labels are best-effort even though the raw 56-byte blob round-trips exactly. |
| AGP Smart Sensor / Water Analyzer WA510 | Tuya cloud | Project-reported hardware support for pH, ORP, free-chlorine reference, temperature, battery, refresh, targets and measurement-window schedule | The analyzer temperature-unit selector's boolean polarity is not physically verified. The integration does not backfill measurements recorded while HA was offline. |
| Intex SX2100 sand-filter pump | Local Tuya + optional cloud schedule | Master power DP104; DP106 filtration OFF→ON physically started the motor from `sleep`/E93 on 2026-07-14 (about 1.2 W to 207 W); status/alarm/runtime mappings; `skdl_filter` schedule read/write path and per-slot editors | The tested unit briefly made its local entities unavailable during the DP106 restart before read-back recovered. Other firmware may behave differently; verify after dependency or firmware changes. |
| Any-brand linked pump | Existing Home Assistant switch | Linked on/off control and optional power/energy entities; switch service/state behavior checked in an isolated HA instance | Pump auto mode requires a local saltwater coordinator in the same entry. A linked switch's state alone does not prove water circulation. |
| Non-Wi-Fi saltwater system on an HA relay | Existing Home Assistant switch selected in the card | Manual relay control through the v0.21.3 card; selector and service/state roundtrip checked with a test switch | No separate saltwater relay setup mode, telemetry, device schedules or automatic pump interlock. Intex Pool must already be configured and loaded. |

Earlier documentation also named **T3U**, but this repository does not retain
model-specific evidence sufficient to place it in the physically verified list.
Treat it as unconfirmed until a model/firmware report and observed data points are available.
The WA510 compatibility discussion is recorded in [issue #10](https://github.com/Hovborg/intex-pool/issues/10).

The physical observations above are historical project evidence, not a fresh
hardware test of v0.21.3. The current [verification report](github-issues-2026-09-10.md)
separately records the complete offline suite and actual HA 2026.9.1 browser checks.

## Dependency verification status

`tinytuya` 1.20.0 passes the complete offline integration test suite on Python
3.13. That proves API compatibility with the wrappers and simulated protocol
responses; it is not a physical-device verification. Before changing a mapping
because of a library upgrade, confirm it against a real device and record the
model, firmware, protocol version and observed datapoints.

Cloud setup exposes TinyTuya 1.20's distinct project regions: `eu`, `eu-w`,
`us`, `us-e`, `cn`, `in`, and `sg`. Local protocol auto-detection tries 3.4,
3.5, 3.3, and 3.1 once each and persists the version that responds. An offline
test proves candidate selection, persistence, entry startup and error
classification, but it does not replace a physical LAN read from the target
device and firmware.

## Reporting another device

Attach Home Assistant diagnostics or a redacted TinyTuya status/thing-model
capture to a GitHub issue. Include:

- exact model and firmware shown in the Tuya/Intex app;
- local protocol version and which connection path works;
- raw datapoint names/ids and values before and after one controlled action;
- expected versus observed behaviour;
- whether the evidence came from physical readback, a thing model, or inference.

Remove local keys, access IDs, access secrets, device IDs, IP addresses and any
request signatures. Home Assistant diagnostics already redact the integration's
stored credentials, but review the file before publishing it.
