# Issue and dashboard verification — 2026-09-10

Baseline: `0a871a4205aee0d34def911d76eb96cd1f01fb65` (`origin/main`).
Prepared version: **0.21.3**. The original local checkout had unrelated changes
in `CONTRIBUTING.md` and `conftest.py`; this work used a separate worktree.

## Every reported issue

All nine issue bodies and their comments were inspected through the GitHub API.
The open issues at the start were #13, #24 and #25. Web search's cached issue
list was stale; the GitHub API supplied the current states.

| Issue | Finding and outcome | Evidence and remaining boundary |
| --- | --- | --- |
| [#25](https://github.com/Hovborg/intex-pool/issues/25) | The visual editor nested fields under named sections while the card read flat fields. Linked-pump discovery also ignored the pump selector's selected entity. Fixed both; migrate old nested overrides, preserve explicit clears, and resolve selector state on each update. | Regression tests and actual HA 2026.9.1 editor/save/reload/service tests. The reporter's physical pump is not accessible here. |
| [#24](https://github.com/Hovborg/intex-pool/issues/24) | Card power/chlorination selectors now accept any existing HA switch, including Shelly relays. | Actual HA switch service/state roundtrip. This is card-level manual relay control; it adds no Tuya salt-device setup mode, salt telemetry, device schedules or automatic pump interlock. |
| [#13](https://github.com/Hovborg/intex-pool/issues/13) | Fixed lost cloud subscription/permission errors, partial discovery and token-renewal recovery. Added explicit account-recovery messages and readable region names. Expanded developer-cloud guide and distinction from the official HA Tuya login. | Regression tests run the actual pinned TinyTuya client against synthetic HTTP responses. The reporter confirmed IoT Core renewal eventually restored their access. Pairing and vendor automation migration remain unverified on physical equipment. |
| [#22](https://github.com/Hovborg/intex-pool/issues/22) | Two-temperature header fix was already in main but unreleased. Included in 0.21.3. | Existing dual/single/deduplicated-temperature tests pass. |
| [#20](https://github.com/Hovborg/intex-pool/issues/20) | Device-aware measurement refresh/repair fix was already in main but unreleased. Included in 0.21.3. | Local DP107, separate-analyzer command and repair-error regressions pass. A successful command is not proof of a fresh physical measurement. |
| [#18](https://github.com/Hovborg/intex-pool/issues/18) | Reporter confirmed explicit protocol 3.5. Auto detection already tries all supported versions and retains the successful one. | Authentication/version tests pass; guide specifies LAN IP and current local key. |
| [#10](https://github.com/Hovborg/intex-pool/issues/10) | Reporter recognized the existing WA510 compatibility entry and closed the question. | Compatibility documentation retained; no new hardware certification is implied. |
| [#8](https://github.com/Hovborg/intex-pool/issues/8) | Reporter confirmed browser refresh fixed card availability. | Actual automatic module registration works in the isolated HA instance. Added duplicate-registration regression for installations also using a manual resource URL. |
| [#7](https://github.com/Hovborg/intex-pool/issues/7) | SX2100 power DP recovery and cloud schedule credentials were already fixed in 0.20.1. | Complete backend regression suite passes. No new physical SX2100 write was made. |

## Additional dashboard findings

- Visual review at 320 pixels found clipped status badges in side-by-side cards
  despite the outer card reporting no overflow. The header now wraps, and the
  browser matrix asserts that individual header children also fit.
- Sections previously reserved three rows regardless of schedule length. With a
  seven-row schedule the first card ended at y466.19 and the next started at
  y272: 194.19 pixels of overlap. Content-based row sizing now places the next
  card at y474.19, leaving an 8-pixel gap.
- Masonry now reports the rendered height rather than a constant size of 3.
- Legacy nested user selections override old auto-detected flat stub values.
  The editor converts its input/output to one flat shape. Clearing a field
  persists an empty override instead of restoring either the old nested value
  or an auto-detected entity.
- Automatic and manually added JavaScript resources register one picker entry.

## Expanded setup and runtime audit

- Calibration and pool-volume/unit changes now refresh the actual HA states for
  Action required and Salt to add immediately. Regression tests read `hass.states`
  after the change; checking only the Python properties missed the stale UI.
- Pump auto mode distinguishes unknown status from stopped chlorination, pauses
  pending stop timers during unknown status, and resumes the full one-hour
  after-run when a known stopped state returns. Generation checks prevent stale
  timers from stopping a newly active pump; disabled/self-targeting automations
  cannot send pump service calls. Synthetic HA timer/service regressions cover it.
- Explicit removal overrides preselected editing in manual reconfigure.
- Discovery preserves model labels when refreshing the same physical device.
- Reconfigure updates the entry identity from the final merged device set and
  rejects a collision before saving data. Replacing hardware creates new entity
  identities; README now explains that dashboards/automations need adjustment.
- The actual TinyTuya 1.20 client is tested with synthetic HTTP responses for
  expired subscriptions, API permissions, token failures, retry/recovery and
  malformed replies. Error metadata is checked before the library can discard
  it in token handling, pagination or per-account device discovery.
- Cloud calls use per-request connect/read timeouts without globally modifying
  Python requests or other clients. Returned error messages contain numeric
  codes rather than potentially private upstream payloads.
- Integration debug no longer activates TinyTuya's raw credential-bearing
  logger. Explicit global/vendor debug settings remain the user's separate
  responsibility; existing logs are neither inspected nor removed here.
- Region selectors show data-center names in English and Danish. Empty device
  lists no longer suggest that manual analyzer setup bypasses cloud access.
- The relay guide now states that the integration must be configured and loaded
  to register its card. HACS download alone does not load the JavaScript.

## Tested Home Assistant and browser matrix

The official latest-release API reported **Home Assistant 2026.9.1** and
frontend **20260826.6**. The actual browser test used the official
`ghcr.io/home-assistant/home-assistant:2026.9.1` image, digest
`sha256:612d76760b544cb40b7ba01387fdac964c59a6a550a50a4d30b4773c822d2918`.
The integration was loaded with an entity-linked pump backed by a template
switch and input_boolean. No pool hardware, cloud credentials or production
Home Assistant instance was used.

| Configuration | Tested |
| --- | --- |
| YAML dashboards | Masonry, Sections, Panel, Sidebar |
| UI/storage dashboards | Masonry, Sections, Panel, Sidebar |
| Container cards | Vertical stack, horizontal stack, grid, conditional |
| Navigation | Subview |
| Browser widths | 1280, 390 and 320 CSS pixels |
| Native editor | Legacy configuration, edit, canonical save, reload, actual test-switch toggle, clear, save/reload |
| Long content | Sections schedule content followed by a second card; no overlap |

This is 30 dashboard/width cases. It covers Home Assistant's native customizable
Lovelace views. Built-in pages that do not host arbitrary cards (for example,
Energy) and every third-party custom view are not a blanket compatibility
claim. Native mobile app WebViews and physical devices need their own checks.

The first minimal fixture omitted Recorder, which intermittently produced a
frontend `recorder/info` / `unknown_command` error. The reusable fixture includes
Recorder. The final clean-instance matrix, editor and stress commands all passed. This is a test-fixture correction, not an Intex Pool backend change.

## Verification commands

- `npm --prefix card test` → 19 passed, 0 failed, including tests observed failing
  before their fixes.
- `npm --prefix card run build` → `Built intex-pool-card v0.21.3`.
- `python scripts/verify_release.py` → metadata and artifacts agree on v0.21.3.
- `docker exec intex-pool-test-20260910 python -m pytest -o addopts='' -p no:cacheprovider -q`
  → 303 passed in 22.82s. This is the existing CI stack: Python 3.13,
  Home Assistant 2026.2.3, pytest-homeassistant-custom-component 0.13.316,
  TinyTuya 1.20.0. The newer actual HA browser/runtime test above is separate.
- `ruff check custom_components tests` → `All checks passed!`.
- Browser regression commands and isolated setup are under
  [scripts/browser](../scripts/browser/README.md).
- Independent Astra reviews reproduced and checked the editor/reconfigure fixes.
  Astra/max reviewed the cloud adapter and pump timer changes; all resulting
  findings were fixed and retested. The final pump-specific review ran 30 tests.
- Current HA imports report `UnitOfRatio ppm`; older-HA entity tests retain ppm
  compatibility without importing the deprecated constant on current HA.

## Device names in the reporter's screenshot

All five screenshots in #25 were visually inspected. The original switch
`switch.pool_pump` is the correct external switch to choose: the integration's
additional `Pump switch` entity is a selector, not a duplicate hardware switch.
The actual failures were missing linked-selector discovery and nested editor
configuration. Both automatic discovery and explicit editor selection are tested.

`Water sensor`, `Water analyzer (WA510)`, `Sand filter pump` and `Linked pump`
are integration-wide default names/model strings in `const.py` and `entity.py`.
They are not copied from the author's Home Assistant registry. `Garden` is not
set by this integration. These names alone provide no evidence of shared
private device data.
