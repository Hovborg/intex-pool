# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

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
