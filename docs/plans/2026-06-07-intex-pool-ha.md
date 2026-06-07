# Intex Pool HA — Implementation Plan

> **For agentic workers:** Execute task-by-task (TDD). Steps use checkbox (`- [ ]`) syntax. Spec: `docs/specs/2026-06-07-intex-pool-ha-design.md`.

**Goal:** Ship a polished, HACS-distributed Home Assistant integration `intex_pool` (+ adaptive dashboard card) that exposes any subset of {water sensor (cloud), saltwater chlorinator (local), sand-filter pump (Tuya local or linked entity)} as clean native entities, verified live against real hardware.

**Architecture:** Per-device `DataUpdateCoordinator`s (blocking tinytuya wrapped in executor) hung off `entry.runtime_data`; multi-step conditional config flow; declarative `EntityDescription` tables drive all platforms; the integration serves its own Lit card via `async_register_static_paths` + `add_extra_js_url`.

**Tech Stack:** Python 3.13 (HA 2025.12), tinytuya, voluptuous, pytest + pytest-homeassistant-custom-component; Lit + esbuild for the card; GitHub Actions (hassfest, hacs/action).

---

## Key shared interfaces (locked here, used by all tasks)

```python
# const.py
DOMAIN = "intex_pool"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH,
             Platform.NUMBER, Platform.BUTTON, Platform.SELECT]
# device-type config keys
CONF_HAS_SENSOR, CONF_HAS_SALT, CONF_HAS_PUMP = "has_sensor", "has_salt", "has_pump"
CONF_REGION, CONF_ACCESS_ID, CONF_ACCESS_SECRET = "region", "access_id", "access_secret"
CONF_DEVICE_ID, CONF_LOCAL_KEY, CONF_HOST, CONF_VERSION = "device_id", "local_key", "host", "version"
CONF_PUMP_MODE = "pump_mode"            # "tuya" | "entity"
CONF_PUMP_SWITCH = "pump_switch"        # entity_id (entity mode)
CONF_PUMP_POWER, CONF_PUMP_ENERGY, CONF_PUMP_TEMP = "pump_power", "pump_energy", "pump_temp"
DEFAULT_LOCAL_INTERVAL, DEFAULT_CLOUD_INTERVAL = 15, 120

# models.py
@dataclass
class IntexPoolData:
    salt: SaltCoordinator | None = None
    sensor: SensorCoordinator | None = None
    pump: PumpCoordinator | None = None
type IntexPoolConfigEntry = ConfigEntry[IntexPoolData]

# coordinator API (all three): .data is dict[str, Any] keyed by DP-string (salt/pump) or property code (sensor)
#   SaltCoordinator.async_set_dp(dp:int, value)         # local set, then request_refresh
#   SensorCoordinator.async_issue(code:str, value)      # cloud property issue
#   SensorCoordinator.async_refresh_measure()           # press refresh_switch
```

Descriptor tables (`const.py`) carry, per entity: `key`, `dp`/`code`, `name`/`translation_key`, `device_class`, `state_class`, `unit`, `entity_category`, `icon`, `scale`, `options` (select), `min/max/step` (number), `value_fn`/`decode_fn`. Ported verbatim from `01-drift/13-pool-kontrol/config.json` + `manuals/REFERENCE.md`.

---

## Phase 1 — Skeleton, constants, decoders (no HA runtime; pure unit tests)

### Task 1: Repo skeleton + dev tooling
**Files:** Create `pyproject.toml` (or `requirements_test.txt`), `tests/conftest.py`, `.gitignore`, `custom_components/intex_pool/__init__.py` (empty stub), `manifest.json`, `const.py`.
- [ ] Create a `.venv`, install `homeassistant`, `pytest-homeassistant-custom-component`, `tinytuya`.
- [ ] Write `manifest.json` with the 6 HACS-required keys + `version`, `config_flow: true`, `iot_class: local_polling`, `integration_type: hub`, `dependencies: ["frontend","http"]`, `requirements: ["tinytuya==1.18.1"]`.
- [ ] `const.py` with the locked constants above.
- [ ] Commit.

### Task 2: Decoders (`decode.py`) — pure functions, TDD
**Files:** Create `custom_components/intex_pool/decode.py`, `tests/test_decode.py`.
- [ ] Write failing tests: `decode_salt_error(0) == "ingen"`; known bitmap codes from REFERENCE.md → labels; `decode_status("working") == "Arbejder"` etc.; `decode_alarm("E90")`, `E91E92`, `normal`.
- [ ] Run → fail.
- [ ] Implement decoders from `manuals/REFERENCE.md §2/§3`.
- [ ] Run → pass. Commit.

### Task 3: Descriptor tables + selection logic
**Files:** Modify `const.py` (add `SALT_*`, `SENSOR_*`, `PUMP_*` descriptor tuples). Create `tests/test_descriptors.py`.
- [ ] Tests: every salt switch/select/sensor/binary DP from `config.json` is present with correct unit/device_class/scale; sensor properties present with ÷100 scaling on pH/fc; no duplicate `key`s; all `translation_key`s unique per platform.
- [ ] Implement tables. Run → pass. Commit.

## Phase 2 — Tuya transport + coordinators (mockable; unit tests with fakes)

### Task 4: `tuya.py` executor-wrapped helpers
**Files:** Create `custom_components/intex_pool/tuya.py`, `tests/test_tuya.py`.
- [ ] Tests with a fake tinytuya: `LocalClient.status()` returns dps dict; fresh non-persistent socket per call; `set_value(dp,val)`; version handling (configured vs auto-rotate candidates [3.4,3.5,3.3,3.1]); `CloudClient.properties()` parses `/shadow/properties`; `CloudClient.issue(code,val)`; `CloudClient` builds correct issue path/body.
- [ ] Implement thin wrappers (no HA import here; just tinytuya + plain callables). Run → pass. Commit.

### Task 5: Coordinators
**Files:** Create `coordinator.py`, `models.py`, `tests/test_coordinator.py`.
- [ ] Tests (pytest-homeassistant-custom-component, mocked `tuya.py`): each coordinator `_async_update_data` returns parsed dict; `UpdateFailed` on transport error; blocking calls go through `async_add_executor_job`; `async_set_dp`/`async_issue`/`async_refresh_measure` call transport then request refresh; scaling applied (pH 740→7.4).
- [ ] Implement coordinators + `IntexPoolData`/typed entry. Run → pass. Commit.

## Phase 3 — Entities (all platforms; HA test harness)

### Task 6: Base entity + sensor/binary_sensor
**Files:** Create `entity.py`, `sensor.py`, `binary_sensor.py`, `tests/test_sensor.py`.
- [ ] Tests: given a fake entry with each device active, the right sensor/binary entities are created with correct `unique_id`, `device_info`, `native_value` (decoded/scaled), `entity_category`, `available` follows coordinator.
- [ ] Implement base `IntexPoolEntity` (DeviceInfo, has_entity_name) + the two platforms driven by descriptor tables. Run → pass. Commit.

### Task 7: switch / number / button / select
**Files:** Create `switch.py`, `number.py`, `button.py`, `select.py`, `tests/test_controls.py`.
- [ ] Tests: toggling `switch.power` calls `SaltCoordinator.async_set_dp(104, True)`; `number.ph_target` set calls `SensorCoordinator.async_issue("ph_set", 750)` (scale); `button.refresh` calls `async_refresh_measure`; `select.self_clean` maps "4 h"→DP value; command error → `HomeAssistantError`.
- [ ] Implement. Run → pass. Commit.

## Phase 4 — Config flow + wiring

### Task 8: `__init__.py` setup/unload + card serving
**Files:** Modify `__init__.py`, `tests/test_init.py`.
- [ ] Tests: `async_setup_entry` builds only the coordinators for present devices, sets `runtime_data`, forwards platforms; `async_unload_entry` unloads; `async_setup` registers static path + extra js url once (mock http/frontend).
- [ ] Implement. Run → pass. Commit.

### Task 9: Config flow + options + reconfigure
**Files:** Create `config_flow.py`, `strings.json`, `translations/en.json`, `translations/da.json`, `tests/test_config_flow.py`.
- [ ] Tests: step `user` with each boolean subset routes through only the relevant steps and creates an entry with merged data; bad cloud creds → `errors{base: cannot_connect}` (mock validate); duplicate → abort; options flow changes intervals; `OptionsFlowWithReload`.
- [ ] Implement multi-step conditional flow + `validate_*` helpers (mockable) + translations. Run → pass; run `python -m script.hassfest`. Commit.

## Phase 5 — Card serving + live deploy + cutover-verify

### Task 10: Minimal card + build pipeline
**Files:** Create `card/package.json`, `card/src/intex-pool-card.ts`, `card/build` (esbuild) → `custom_components/intex_pool/frontend/intex-pool-card.js`, `.github/workflows/build-card.yaml`.
- [ ] Minimal Lit card: `setConfig`, `set hass` (per-entity diff), `getCardSize`, `getGridOptions`, `window.customCards`, renders one section. Build with esbuild (Lit bundled). Commit built file.

### Task 11: Deploy to HA + live verify (real hardware)
- [ ] cifs-mount `//192.168.1.190/config`; copy `custom_components/intex_pool`; `check_config`; restart HA.
- [ ] Add integration via config flow (sensor=cloud creds, salt=local id/key/v3.5, pump=entity `switch.sandfilter_pumpe`).
- [ ] Stop bridge salt poll to avoid contention; verify: salt entities populate + a chlorination toggle round-trips; cloud sensor pH/ORP/battery populate; pump toggle works; card renders. Capture screenshot.

## Phase 6 — Polished adaptive card

### Task 12: Full adaptive card + editor
**Files:** Expand `card/src/*` (chemistry/chlorinator/pump sections, gauges, pills, big toggles), `getConfigForm`, `getStubConfig` auto-detect.
- [ ] Build + redeploy; screenshot each combo (sensor-only, salt-only, pump-only, all) by temporarily configuring card; verify theme + responsiveness + a11y. Iterate until it looks good.

## Phase 7 — Cutover

### Task 13: Re-point automations + Pool-Vagt + dashboard
- [ ] Build old→new entity-id map; update `pool_kemi_vagt`, `pumpe_folger_anlaeg`, `pool_orp_auto_hold_700`, `filter_driftstimer_taeller`; update Pool-Vagt (`03-tools/16`); update dashboard card (wall-panel-4 #12). Verify each.
- [ ] Disable `pool-kontrol.service` (keep as fallback); remove stale MQTT discovery topics.

## Phase 8 — Publish (GitHub + HACS)

### Task 14: CI + docs + brand + release
**Files:** `.github/workflows/{hassfest.yaml,validate.yaml}`, `hacs.json`, `README.md`, `info.md`, `LICENSE`, `CHANGELOG.md`, `brand/icon.png`.
- [ ] Add CI workflows; `hacs.json`; README (My-link + install + screenshots); brand icon; LICENSE (MIT); CHANGELOG.
- [ ] Create GitHub repo `Hovborg/intex-pool` (public); push; verify Actions green; tag `v0.1.0` release.
- [ ] Verify a clean HACS custom-repo install path (validation action green).

## Phase 9 — Polish loop
- [ ] Iterate (look + robustness + edge cases) until the integration + card are "super good" and live-verified. Update CHANGELOG + release bumps.

---

## Self-review
- **Coverage:** every spec section (§3 architecture→Tasks 4–8; §4 flow→Task 9; §5 entities→Tasks 6–7; §6 card→Tasks 10,12; §7 errors→Tasks 5,7; §8 testing→all; §9 cutover→Tasks 11,13; §10 publish→Task 14) has a task.
- **No placeholders:** interfaces locked above; per-task tests named concretely.
- **Type consistency:** coordinator method names (`async_set_dp`/`async_issue`/`async_refresh_measure`) and `IntexPoolData` fields used consistently across Tasks 5–9.
