# Post-v0.20.1 hardening design

## Goal

Ship one coherent maintenance and robustness update that clears the known
dependency debt, makes optional cloud schedules recover automatically, exposes
pump schedules in the bundled card, and prevents release artefact drift.

## Scope and constraints

- Local pump and salt controls must keep loading when the optional Tuya cloud
  endpoint or credentials are unavailable.
- Schedule entities must exist immediately and recover without an integration
  reload after a transient standalone-cloud failure.
- A standalone cloud authentication failure must start reauthentication without
  taking local controls offline.
- Sensor-backed cloud remains required for the analyzer: its existing
  `ConfigEntryNotReady` and `ConfigEntryAuthFailed` semantics stay unchanged.
- No DP102 or schedule-byte semantics may change without physical-device
  evidence.
- The dashboard card must auto-detect and render both salt and pump schedules,
  and only suggest itself for entities owned by this integration.
- All release versions and the committed card bundle must be checked by CI.

## Architecture

### Recovering optional cloud schedules

A small `CloudClientProvider` owns the standalone cloud credentials, an async
lock, and a cached `CloudClient`. Schedule coordinators created from standalone
credentials ask this provider for a client on every update until construction
succeeds. Construction runs in Home Assistant's executor.

`ScheduleCoordinator` continues to accept the existing eager client used by the
water sensor. It additionally accepts an optional provider and an
`optional_cloud` flag. For optional schedules, authentication errors start a
single reauthentication flow and are reported as coordinator update failures;
they never fail the complete config entry. Successful polls reset the normal
auth-failure counter. Writes obtain the same recovered client and remain
serialized by the existing write lock.

This design is preferred over periodically reloading the complete entry: it
keeps local coordinators stable, creates the entities on the first platform
setup, and uses Home Assistant's existing coordinator interval as the retry
mechanism.

### Dashboard card

Entity-role detection moves to a pure `entity-detection.js` module so Node's
built-in test runner can exercise it without a browser. The pump role gains a
`schedules` mapping to `pump_schedules_sensor`. The card editor exposes that
field and renders separate labelled schedule groups for saltwater and pump
programs.

The `window.customCards` registration implements Home Assistant 2026.6's
`getEntitySuggestion(hass, entityId)` contract. It returns a populated card
configuration only when `hass.entities[entityId].platform === "intex_pool"`.

### Release and CI hygiene

The maintenance update adopts `actions/checkout@v7`, `setup-python@v6`,
`setup-node@v6`, Ruff action v4.1.0, and esbuild 0.28.1. A Python verifier checks
that `manifest.json`, `pyproject.toml`, `card/package.json`, both lockfile root
versions, and the compiled card version agree. It also builds the card and
fails on either bundle or source-map drift.

Push workflows run on branches and ignore tags, eliminating duplicate release
tag runs. Pull requests and manual dispatch remain unchanged; scheduled HACS
and hassfest validation remain enabled.

`tinytuya` 1.20.0 is upgraded only if the full offline suite and API-compatibility
checks pass. Physical SX/QS behaviour remains explicitly documented as needing
live verification after dependency changes.

## Error handling and security

- Cloud credentials remain only in config-entry data and are never logged.
- Authentication logs contain the exception message but no submitted fields.
- The provider serializes client construction so simultaneous schedule polls do
  not perform duplicate token requests.
- Network and protocol exceptions become `UpdateFailed`; local device
  coordinators continue independently.
- Card suggestions trust the entity registry platform field, not an entity-id
  naming convention.

## Verification

- Red/green Python regression tests for initial cloud failure, later recovery,
  shared client construction, authentication reauth, and recovered writes.
- Red/green Node tests for pump schedule detection and card suggestions.
- A red/green version-verifier test or direct failure reproduction against the
  current stale lockfile.
- Full `pytest`, Ruff, `npm test`, `npm run build`, `npm audit`, version check,
  bundle diff, YAML parse, and repository diff review.

## Non-goals

- Inferring or changing unverified DP102 behaviour.
- Reinterpreting the schedule byte format without hardware evidence.
- Adding a general-purpose retry framework or refactoring unrelated platforms.
