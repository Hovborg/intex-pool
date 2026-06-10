# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.14.0] - 2026-06-10

Calibration against your own reference tests + user-adjustable pool volume.

### Added
- **Calibrate against a reference test** (`intex_pool.calibrate`): aligns the pH (or ORP)
  reading with your own drop-test/strip result by storing a software offset
  (offset = reference − current reading). Research-grounded guardrails: deadband below the
  device's 0.1 pH resolution, hard clamp at ±0.5 pH / ±100 mV (beyond that the probe needs
  cleaning + a buffer calibration in the Intex app — an offset would hide a real problem),
  and the corrected value is what the Action-required roll-up judges. The raw reading stays
  visible as the `raw_value` attribute. `clear_calibration` removes the offsets.
- **pH / ORP calibration offset number entities** (config category; ORP is advanced and
  disabled by default — home tests measure chlorine, not ORP, and a low ORP is usually
  chemistry or fouling).
- **Auto-reset on app recalibration**: the integration watches the device's own (read-only)
  calibration coefficients; when the Intex app recalibrates the probes, the now-obsolete
  software offsets are reset to 0 and a repair issue explains why. A repair also warns when
  software offsets are older than the manual's 4-month calibration cadence.
- **Pool volume entity** (`number`) + **Volume unit** select (litres / US gallons) right on
  the saltwater device — no need to open Configure. The salt advisor reads them live; the
  unit choice never converts the stored figure.

### Changed
- The salt advisor entity now always exists; without a pool volume it stays empty with a
  `set_pool_volume` status hint.
- FC remains uncalibrated by design: it is computed device-side from the *uncorrected*
  pH/ORP and labeled "reference only" by Intex; ground truth for chlorine is a FAS-DPD
  drop test.

## [0.13.0] - 2026-06-10

Advisory features grounded in the device manuals + deep online research (iopool/poolchem
patterns, TFP community practice, Tuya thing-model verification).

### Added
- **Salt dose advisor** (`Salt to add`, kg): set your pool volume under ⋮ → Configure and the
  sensor computes how much salt reaches the target salinity (default 950 ppm — the QS-series
  optimum; formula kg = L × Δppm ÷ 10⁶, matching the manual's own examples). Above 1800 ppm it
  flips to the manual's E92 dilution advice (drain/refill %). Advisory only.
- **Action required** binary sensor — one PROBLEM flag rolling up: active salt alarm, probe
  maintenance, pH outside 7.2–7.8, ORP below the 650 mV sanitation floor, salinity outside
  800–1800 ppm, stale analyzer data. The `reasons` attribute lists what triggered for
  notifications/automations.
- **Cold water** binary sensor — flags electrolysis-hostile water below 15 °C (the unit itself
  errors with E03 under 10 °C); protects the cell in shoulder season.
- **Cell wear** sensor — electrolysis-cell runtime as % of the 5000 h counter range (assumed
  rated life).
- **Analyzer measurement schedules** (read-only): the water analyzer's own `skdl_orpph` schedule
  blob is now decoded — same 7-slot format as the saltwater schedule (byte-format live-verified).
  Per the manual these windows drive hourly measurements and group-mode authority.
- **`intex_pool.get_schedule` service** with response data — returns the decoded slot tables for
  both devices. `set_schedule` now optionally returns the resulting table too.
- **Fixable stale-data repair**: the "stale sensor data" issue now has a Fix button that forces a
  fresh measurement (wakes the sleeping sensor).
- Card: **ORP trend marker** on the ORP tile (from the trend entity) and a **stale badge** with
  relative age next to the battery when the newest measurement is older than 3 h.
- Setup polish: contextual help texts (`data_description`) on all config/options fields.

### Changed
- Options now include pool volume + target salinity (advisor), alongside polling intervals.

## [0.12.1] - 2026-06-10

Follow-up fixes found by a re-audit of the v0.12.0 release.

### Fixed
- **Event entities: no more spurious event after restart.** When a cloud property (e.g.
  `error_code`) was absent from the first poll — the cloud only reports properties the device has
  ever emitted — its first appearance later fired a false transition event. The first observed
  value now seeds the baseline silently.
- **Card: `saltwater_abnormal` no longer masked.** The ORP indicator's fourth state now colors the
  ORP tile as a problem instead of silently falling back to the numeric range (which could show
  green while the device reported a fault).
- **Repairs survive connectivity loss.** An active alarm/maintenance/stale repair issue is no
  longer deleted just because the device went offline — only a confirmed clear removes it.
- **Repairs are purged when the integration is removed** (`async_remove_entry`), so no orphaned
  issues linger in the Repairs dashboard.
- **Pump auto mode** no longer stacks concurrent sync service calls on rapid coordinator updates.

### Changed
- `hacs.json`: added `hide_default_branch` (the `main` branch is no longer offered as a
  downloadable "version" in HACS) and dropped the legacy `render_readme` flag (dead in HACS 2.x).

## [0.12.0] - 2026-06-10

Hardening + feature release after a full multi-agent audit of the integration and card.

### Fixed
- **Tuya pump: configured on/off data point was ignored.** The switch looked the DP up under the
  wrong config key and always fell back to DP 1 — a custom `pump_on_dp` now actually applies.
- **Schedule writes commit state only on success.** Slot toggles / Boost no longer update their
  remembered/suspended bookkeeping (or UI state) when the cloud write fails; all schedule editors
  (toggle, duration, start time) now surface write failures as proper Home Assistant errors.
- **Rotated local key is detected in auto-version mode.** When every protocol-version candidate is
  rejected as bad auth, the coordinator now escalates to the re-authentication flow instead of
  cycling versions forever.
- **Local writes can no longer silently fail.** tinytuya doesn't raise on a rejected/undelivered
  command — the response is now checked, so an offline device surfaces as an error instead of a
  switch that looks like it worked.
- **Pump auto mode** defers its initial sync until Home Assistant has fully started (the linked
  switch's integration may not be loaded yet during boot) and logs a warning when the pump switch
  can't be reached (the service call is now blocking).
- Card: a water-sensor-only setup is no longer misclassified as a saltwater system (shared
  `water_temp` key no longer drives detection); the configured free-chlorine entity now actually
  renders as a tile; failed service calls from the card are caught and shown as a notification
  (with a busy state preventing double-taps); light-variant status colors now meet WCAG AA
  contrast; toggle pills expose `aria-pressed`.
- Config flow: a rejected key fails immediately instead of being retried through the full
  transport-retry budget.
- `manifest.json` `iot_class` corrected to `cloud_polling` (the water sensor + schedules poll the
  Tuya cloud).

### Added
- **Diagnostics** (Settings → Devices & Services → ⋮ → Download diagnostics) with local keys and
  cloud credentials redacted — raw coordinator data included for bug reports.
- **Repairs**: saltwater alarms (E90 flow, E91/E92 salt, E01–E04 electrode/temperature, E97/E99
  hardware) with the manual's fix steps, a probe-maintenance reminder, and a **stale sensor data**
  warning (newest measurement older than 3 h).
- **Last measurement** timestamp sensor — per-property report times from the cloud are now kept
  instead of thrown away.
- **Alarm / Error event entities** that fire on every transition (logbook + automation triggers).
- New entities: **ORP trend** (`ORP_dif_Number`), sensor-side **link status** (`mesh_indicator`),
  **stabilizer (CYA) flag** switch (`fc_sta_flg`), **Chlorine production 2** switch (DP 102,
  disabled by default — effect unverified on hardware), and read-only pH/ORP
  calibration-coefficient diagnostics (disabled by default; writing them corrupts calibration).
- `intex_pool.set_schedule` gained a **config entry selector** for multi-entry installs, and the
  service is registered at component setup (a call without a loaded entry now gives a clear
  validation error).
- Card: pH/ORP tiles are colored by the device's own **indicator** verdicts when available;
  free-chlorine tile; source maps for debugging; deterministic cross-platform card build
  (`build.mjs`).
- Quality-scale polish: `SensorDeviceClass.PH` on the pH sensor, `DURATION` on runtime sensors,
  `suggested_display_precision` everywhere, all icons moved to `icons.json` (state-dependent alarm
  icon), exception translations, `data_description` help texts in setup, and stale device-registry
  entries can now be deleted from the UI after a reconfigure.

### Changed
- The `set_schedule` service caps `duration` at 72 h (matching the duration entities and the
  longest boost cycle in the manual).
- Tuya error messages no longer quote raw response bodies (only code/msg fields).

## [0.11.0] - 2026-06-09

### Added
- **Reporting cadence** select on the water sensor (`report_number`) — choose whether the analyzer
  reports ORP / pH / free-chlorine by week or by month.
- **Temperature unit** select on the water sensor (°C / °F). Note: the sensor-side polarity reuses
  the verified saltwater-system polarity and should be live-verified — it may be inverted.
- **Re-test now** button on the saltwater system (`retest_switch`, DP 107) — forces a fresh
  salt/temperature measurement, mirroring the sensor's existing Refresh button.

### Fixed
- Cloud-side selects (water sensor) now write via the cloud property path instead of the local-only
  path, so the new sensor selects actually apply. (Internal: the select/button write path is now
  device-aware — local devices write over the LAN, cloud devices issue a property.)

## [0.10.2] - 2026-06-09

### Fixed
- Setup no longer shows a dead/empty device picker when cloud discovery returns no devices — it
  now shows a clear "no devices found — set up manually instead" message so you're never stuck on
  a blank dropdown. The reconfigure flow now does the same (re-prompts for credentials instead of
  showing an empty picker).

### Changed
- The discovery device dropdowns accept a typed/pasted device id (`custom_value`), so a finicky or
  incomplete list can't block setup.
- `hacs.json` now sets `render_readme` so the full README (with screenshots + install button) shows
  on the HACS page.

## [0.10.1] - 2026-06-09

### Added
- **Reconfigure flow.** Integration entry → **⋮ → Reconfigure** re-runs cloud discovery (reusing
  your stored credentials) so you can repoint to a **replaced device** that got a new Tuya id —
  without removing the integration. The current devices are pre-selected; unchanged devices keep
  their stored IP/key (no rescan needed), so a swap keeps all your entity ids and history.

## [0.10.0] - 2026-06-09

### Added
- **Reauthentication flow.** When the Tuya `local_key` rotates (e.g. after re-pairing the
  device in the app) or a cloud secret is rejected, the integration now raises
  `ConfigEntryAuthFailed` and Home Assistant prompts you to enter the new key/secret instead of
  the device going silently unavailable forever.
- Config/CI hygiene: `ruff` lint job, Dependabot (actions + npm), issue templates, PR template,
  `CONTRIBUTING.md`, `SECURITY.md`.

### Changed
- Setup now reports `ConfigEntryNotReady` when **every** configured device fails its first poll,
  so Home Assistant retries with backoff instead of loading with all entities unavailable.
- The bundled card is served with a `?v={version}` cache-buster, so a HACS update loads the new
  card without a manual browser hard-refresh.
- The card version is now injected from `package.json` at build time (no more hard-coded drift).
- Setup errors now distinguish **invalid credentials** from **cannot connect**.

### Fixed
- `schedule.py` no longer raises on a corrupt/truncated cloud schedule blob (decodes to empty).
- `validate_local` re-raises the real connection error (preserving its type/traceback) after
  exhausting retries, so the config flow can tell auth from transport failures.

## [0.9.4] - 2026-06-09

### Added
- Turning **Boost** on now suspends your timed schedules (they're remembered and restored when
  Boost is turned off), mirroring how the unit reverts to its normal schedule after a boost. A
  second Boost turn-on can't wipe the remembered schedules, and the suspended set survives a
  Home Assistant restart.

### Changed
- `schedule.py` documents the now-verified `skdl_salt` field semantics from the device's Tuya
  thing-model (`worktime` = duration, `week` bitmask with bit7 = weekly repeat, `control` = on;
  `control = 0` + long duration is the Boost cycle, reported back as `working_indicator = boost`).

## [0.9.3] - 2026-06-09

### Changed
- Schedule slot 0 is now presented as **Boost**: a toggle + **Boost duration** (hours) only, with
  no start-time entity (boost runs for a duration, not at a clock time).

### Fixed
- Upgrade migration (config-entry v1 → v2) removes the orphaned `time.…_schedule_1_start` entity
  left by earlier versions so it no longer lingers as "unavailable".

## [0.9.2] - 2026-06-09

### Fixed
- Temperature-unit select was inverted: on the real hardware DP124 is True for °C / False for °F
  (opposite of the thing-model doc). Now matches the device.

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
