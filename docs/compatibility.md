# Device and protocol compatibility

This matrix separates behaviour verified on physical equipment from mappings
derived from a Tuya thing model or from protocol captures. Please keep that
distinction when reporting or adding a device.

| Device / model | Connection | Verified behaviour | Remaining caveats |
|---|---|---|---|
| AGP / Intex QS1600 Plus | Local Tuya + optional cloud schedules | Local status and controls; `skdl_salt` decode/encode round-trip; schedule writes and readback | The second chlorine-production datapoint (DP102) is not hardware-verified and stays disabled by default. Duration/day labels are best-effort even though the raw 56-byte blob round-trips exactly. |
| AGP Smart Sensor / Water Analyzer WA510 and T3U | Tuya cloud | pH, ORP, free chlorine reference, temperature, battery, refresh, targets and measurement-window schedule | Tuya's free-tier log API does not provide datapoint history for backfill. |
| Intex SX2100 sand-filter pump | Local Tuya + optional cloud schedule | Master power DP104; DP106 filtration OFF→ON physically started the motor from `sleep`/E93 on 2026-07-14 (about 1.2 W to 207 W); status/alarm/runtime mappings; `skdl_filter` schedule read/write path and per-slot editors | The tested unit briefly made its local entities unavailable during the DP106 restart before read-back recovered. Other firmware may behave differently; verify after dependency or firmware changes. |
| Any-brand linked pump | Existing Home Assistant switch | Linked on/off control, optional power/energy entities and pump-auto interlock | Safety and electrical suitability remain the responsibility of the linked switch/relay installation. |

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
