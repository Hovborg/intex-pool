# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.9.1] - 2026-06-09

### Changed
- The **Pump switch** selector now shows in the device's main controls (not the Configuration
  section), so it's easy to find on the Sand filter pump device.

## [0.9.0] - 2026-06-09

### Changed
- Cleaner schedule device page: empty slots' Start time / Duration editors are now hidden
  (unavailable) so only active schedules show; toggling an empty slot on creates an editable
  daily default you can adjust.
- The linked pump's controls (Auto mode + a new **Pump switch** selector) are grouped under
  their own **Sand filter pump** device — and you can change the pump switch right there.

### Fixed
- Removed duplicate/orphaned per-slot schedule sensors left over from an earlier version.

## [0.8.0] - 2026-06-09

### Added
- **Edit schedules under the device:** each slot now has an editable **Start time** and
  **Duration** entity (in Configuration), alongside the on/off toggle — full per-schedule
  editing without the action.
- **Change the linked pump after setup:** the integration's **Configure** (options) now lets
  you pick the pump switch (and optional power/energy sensors) for an entity-linked pump.

## [0.7.0] - 2026-06-09

### Added
- **Pump auto mode** switch: when on, a linked (any-brand) pump runs only while the saltwater
  system is on.
- **Per-slot schedule switches** (`Schedule 1`…`Schedule 7`): turn each schedule on/off; turning
  one off remembers it so it can be turned back on.

### Fixed
- Editing a schedule now reflects in HA right away (the Tuya cloud needs a few seconds to apply
  a write; the read-back was happening too soon).
- `E93` is shown as **Standby**, not an alarm, on the card and in the alarm sensor.
- The dashboard card is now fully English.

## [0.6.0] - 2026-06-09

### Added
- Schedules are now **visible without digging into attributes**: one sensor per schedule slot
  (`Schedule 1`…`Schedule 7`) under the saltwater device, each showing its summary, plus a
  **schedules list on the dashboard card**.

## [0.5.0] - 2026-06-09

### Added
- **Saltwater schedules** are now visible in HA: a read-only `Schedules` sensor (state = number
  of active schedules; attributes list each one — daily/one-time, time, duration, on/boost).
  The schedule blob (`skdl_salt`) is cloud-only and was previously unexposed; it's now decoded.
- **`intex_pool.set_schedule` service** to create / change / clear a schedule slot from HA
  (writes back via the Tuya cloud). The codec round-trips byte-exact and the cloud write path
  is verified; field meanings (duration unit, days mask, boost) are best-effort.

### Notes
- Schedules require a configured water sensor (its Tuya cloud credentials) + a saltwater system.

## [0.4.0] - 2026-06-09

### Added
- **Selectable card appearance** via a `variant` option: `auto` (follows your HA theme),
  `light`, `dark`, and two designed dark looks — **ocean** (teal gradient) and **midnight**
  (deep indigo). Choose it in the card editor.

## [0.3.0] - 2026-06-08

### Added
- **Cloud auto-discovery setup (much easier):** enter your Tuya IoT cloud credentials once and
  the integration lists your devices (with their local keys) and LAN-scans for IPs — just pick
  which devices are the pool gear. No manual local-key extraction, no IP typing.
- Manual entry is kept as a fallback (tick "set up manually").

## [0.2.0] - 2026-06-08

### Changed
- Redesigned the dashboard card to be compact: a tight header with status, a single row of
  core metric tiles (pH / ORP / temp / salt) with at-a-glance in-range bars, and compact
  control pills (power / chlorine / pump) — instead of three tall stacked sections.
- Dropped the "free chlorine" tile from the card by default (device value is calculated /
  reference-only and misleads when the ORP probe is faulty).

## [0.1.0] - 2026-06-08

### Added
- Initial release: config-flow setup for any combination of water sensor (cloud),
  saltwater system (local), and sand-filter pump (local Tuya **or** linked HA switch — any brand).
- Native entities: sensors, binary sensors, switches, numbers, button, selects, with
  decoded status/alarm/error and per-device connectivity.
- Self-loading adaptive Lovelace card `custom:intex-pool-card`.
- English + Danish translations.
- HACS + hassfest CI validation; pytest suite.
