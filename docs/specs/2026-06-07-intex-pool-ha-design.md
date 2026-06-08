# Intex Pool — Home Assistant integration + dashboard card

**Status:** design · **Date:** 2026-06-07 · **Domain:** `intex_pool` · **Repo:** `intex-pool`

A polished, open-source (HACS) Home Assistant integration that brings **Intex / AGP (Tuya-based) pool equipment** into HA as clean native entities, plus a **dedicated dashboard card** that adapts to whichever equipment the user owns. Works with any subset of:

1. **Water quality sensor** (AGP Smart Sensor / Intex Water Analyzer) — pH, ORP, temperature, free chlorine, battery; writable pH/ORP targets; force-refresh. **Cloud-only** (Tuya developer API).
2. **Saltwater chlorinator** (Intex/AGP QS-series, e.g. QS1600 Plus) — power, chlorine production, salinity, water temp, self-clean cycle, runtime, error/status. **Local** (Tuya LAN, tinytuya).
3. **Sand-filter pump** — on/off + optional power/energy/water-temp. Two modes: a **Tuya pump** (local) *or* **linking an existing HA switch** (e.g. a Shelly plug) for non-Tuya pumps.

Each is independent: the user can have one, two, or all three, in any combination.

---

## 1. Goals & non-goals

**Goals**
- One UI-driven install (config flow), no MQTT broker, no separate service.
- Native entities with correct `device_class`/`state_class`, clean entity-ids, per-device device cards.
- A single adaptive **Pool dashboard card** served by the integration (no separate HACS plugin).
- Robust against device sleep, DHCP roaming, and HA restarts/upgrades.
- Published on GitHub, installable + auto-updating via HACS, with CI (hassfest + HACS validation).
- Continuously verified against real hardware (read + control) and visually (card screenshots).

**Non-goals (YAGNI)**
- No Tuya OAuth account-linking wizard — the user supplies device id/key/cloud creds directly (single-household reality; cloud creds come from a Tuya IoT developer project).
- No automatic Tuya-cloud device discovery in the config flow (manual entry; local LAN discovery is used only to resolve IPs at runtime).
- No attempt to support non-Intex pool brands beyond what the generic Tuya DP-map / entity-link already enables.

## 2. Source of truth (ported knowledge)

The DP maps, property maps, scaling, error-code decoding, salt/chemistry tables, and the **non-persistent-socket** fix come from the proven `01-drift/13-pool-kontrol` bridge (`bridge.py`, `config.json`, `manuals/REFERENCE.md`), live-verified 2026-06-07. This project ports that knowledge into a native integration; it does **not** depend on the bridge at runtime.

Verified device facts (the developer's live testbed):
- Saltwater `<salt-device-id>` @ `<salt-ip>`, Tuya **v3.5**, local key present. DPs per `REFERENCE.md §2`.
- Smart Sensor `<sensor-device-id>`, **cloud-only** (no local port). Tuya developer project region `eu`. Properties per `REFERENCE.md §3`.
- Pump = a **Shelly Plus 2PM** (`switch.sandfilter_pumpe` + power/energy + `sensor.pool_vandtemperatur`) → exercises the **entity-link** pump mode.

## 3. Architecture

```
custom_components/intex_pool/
  __init__.py        # async_setup (serve card + register frontend module),
                     # async_setup_entry (build coordinators -> runtime_data, forward platforms),
                     # async_unload_entry
  const.py           # DOMAIN, platforms, defaults, DEVICE-TYPE keys, DP/property descriptor tables
  config_flow.py     # multi-step conditional flow + OptionsFlowWithReload
  coordinator.py     # SaltCoordinator (local), SensorCoordinator (cloud), PumpCoordinator (local Tuya)
  tuya.py            # thin executor-wrapped tinytuya helpers (local Device + Cloud); socket/version logic
  models.py          # typed runtime_data container (which coordinators are active)
  entity.py          # IntexPoolEntity base (DeviceInfo, has_entity_name)
  sensor.py binary_sensor.py switch.py number.py button.py select.py
  decode.py          # error-code / status decoders (pure functions, ported from REFERENCE.md)
  manifest.json hacs.json
  translations/{en,da}.json   strings.json
  frontend/intex-pool-card.js (built from /card; committed so HACS ships it)
  brand/icon.png brand/icon@2x.png
card/                # Lit + esbuild source for the card (dev), builds into frontend/
.github/workflows/{hassfest.yaml,validate.yaml,build-card.yaml}
hacs.json README.md info.md LICENSE CHANGELOG.md
```

**Runtime model.** `entry.runtime_data` (typed `IntexPoolConfigEntry = ConfigEntry[IntexPoolData]`) holds whichever of the three coordinators are active for that entry. Platforms read `runtime_data` and create entities only for present devices (`exists_fn`-style filtering via `EntityDescription`).

**Coordinators** (all `DataUpdateCoordinator`, blocking tinytuya wrapped in `hass.async_add_executor_job`):
- `SaltCoordinator` — local poll of the chlorinator every 15 s; **fresh non-persistent socket per poll** (ported fix against stale DPs / swallowed commands); runtime LAN discovery + version handling for IP/version resilience.
- `SensorCoordinator` — Tuya cloud `/v2.0/cloud/thing/{id}/shadow/properties` every 120 s (battery sensor sleeps; only wakes ~hourly unless force-refreshed).
- `PumpCoordinator` — local poll of a Tuya pump every 15 s (only when pump is in Tuya mode).

**Commands.** switch/number/button/select entities call coordinator methods → executor `tinytuya.set_value()` (local) or cloud `/shadow/properties/issue` (cloud) → `async_request_refresh()`. Command failures raise `HomeAssistantError` (visible in UI) and are logged.

**Card serving.** `async_setup` registers the static path for `frontend/intex-pool-card.js` via `await hass.http.async_register_static_paths([StaticPathConfig(...)])` and calls `add_extra_js_url(hass, ...)` so the card auto-loads (storage-mode dashboards). Registered once per integration, guarded against reload double-registration.

## 4. Config flow

Step `user`: three booleans — *Water sensor*, *Saltwater system*, *Sand filter pump* (at least one required, else `errors`).
Conditional follow-up steps (only for chosen devices), each validated by a live test connection before advancing:
- `water_sensor`: cloud region + access_id + access_secret + sensor device id. Validate via a cloud properties fetch.
- `saltwater`: device id + local key + (optional IP, optional protocol version — auto-detect if blank). Validate via a local `status()`.
- `sand_filter`: mode select → **Tuya** (id/key/ip/version + on-DP) or **Existing entity** (switch entity_id + optional power/energy/temp entity_ids). Validate accordingly.

`async_set_unique_id` from the first device id (or a composed id); `_abort_if_unique_id_configured`. **Options flow** (`OptionsFlowWithReload`): poll intervals for local + cloud, and add/remove device types later. `reconfigure` step to change creds.

## 5. Entities (per device, ported + native upgrades)

**Saltwater chlorinator** (local device card):
- switch: `power` (DP104, main feature), `chlorination` (DP103)
- select: `self_clean` (DP108 → 2/4/6/10 h), `temp_unit` (DP124 → °C/°F) — *native upgrade over raw bridge sensors*
- sensor: `salinity` (DP109 ppm), `water_temp` (DP111 °C, temperature), `cell_runtime` (DP105 h, diagnostic), `time_remaining` (DP110 h), `status` (DP125 decoded), `alarm` (DP127 decoded), `error_code` (DP114 → readable text, diagnostic)
- binary_sensor: `connectivity`, `mesh` (DP119, diagnostic), `pump_mesh` (DP126, diagnostic)

**Water sensor** (cloud device card):
- sensor: `ph` (PH_Number ÷100), `orp` (mV), `free_chlorine` (fc_number ÷100, "reference only"), `water_temp` (°C, temperature), `battery` (%, battery, diagnostic), `ph_indicator`, `orp_indicator`, `chlorine_indicator`, `maintenance`, `error_code` (diagnostic)
- number: `ph_target` (ph_set 7.2–7.8, config), `orp_target` (orp_set 650–750 mV, config)
- button: `refresh` (refresh_switch — force a fresh measurement)
- binary_sensor: `connectivity`

**Sand-filter pump** (local device card, Tuya mode):
- switch: `pump` (on/off DP, main feature)
- sensor: `power` (W), `energy` (kWh) where DPs exist
- binary_sensor: `connectivity`
*(Entity-link mode creates no entities — the linked entities are referenced directly by the card and any provided blueprints.)*

All entities: `_attr_has_entity_name = True`, `translation_key`, stable `unique_id = f"{device_id}_{key}"`, grouped via `DeviceInfo`. Diagnostic/config entities use `entity_category`.

## 6. Dashboard card (`intex-pool-card`)

Lit + esbuild (Lit bundled), single ESM file. Renders inside `<ha-card>`, uses native `ha-gauge`/`ha-control-button`/`ha-icon` and HA CSS variables for theming. **Adaptive**: detects which device groups are present (from config + runtime entity existence) and renders only those sections, with per-tile "unavailable" placeholders when a present device is offline.

Sections:
- **Chemistry** — gauges for pH (target band 7.2–7.6), ORP (650–750 mV), free chlorine; water temp; battery + refresh button; status pills (pH/ORP/maintenance indicators).
- **Chlorinator** — big power toggle, chlorination toggle, salinity readout + salt-level pill, self-clean selector, runtime/time-remaining, decoded status/alarm.
- **Pump** — big on/off toggle, power/energy, runtime if present (works with Tuya pump entities or a linked Shelly switch).
- **Empty state** when nothing configured.

Editor via `getConfigForm()` (entity selectors per section, expandable panels). Auto-config: `getStubConfig()` + auto-detect of `intex_pool` entities so a freshly added card is pre-populated. Registered in `window.customCards` (`preview: true`). `getGridOptions()` (12-col sections) + `getCardSize()`. Tap → `hass-action` (`more-info`) and `callService` for toggles/number/button. Accessibility: real buttons, `aria-label`, color paired with text, `prefers-reduced-motion`.

## 7. Error handling & resilience

- Local poll fail → `UpdateFailed` → entities `unavailable`; reconnect next cycle; version auto-detect rotates candidates when unknown.
- Cloud fail → sensor `unavailable`; transient errors tolerated (sensor sleeps).
- Command fail → `HomeAssistantError` + log.
- Decoders map raw E-codes/status to readable text (ported from `REFERENCE.md`).
- Two pollers must not fight the chlorinator: during cutover the bridge's salt poll is stopped (see §9).

## 8. Testing & verification

- **Unit** (pytest, no HA): decoders (`decode.py`), scaling, descriptor tables, command-payload building, config-flow routing logic (pure parts).
- **Integration** (`pytest-homeassistant-custom-component`): config flow (each device subset + conditional routing), coordinator update with mocked tinytuya/cloud, entity creation per subset, options/reconfigure.
- **CI**: hassfest + HACS validation actions; pytest; card build (esbuild) + lint.
- **Live verification** (real testbed): read all DPs/properties; one safe control toggle (chlorination on→off); cloud write (ph_target) + refresh button; pump toggle via linked Shelly. Card rendered + screenshotted (playwright) in each present-device combination; checked it "looks good" (layout, theme, no overflow).

## 9. Cutover from the MQTT bridge (developer's instance)

1. Build + unit/integration tests green.
2. Deploy `custom_components/intex_pool/` to HA `/config/` via cifs mount; restart HA; add via config flow (sensor=cloud, salt=local, pump=link `switch.sandfilter_pumpe`).
3. **Clean live verify:** stop the bridge's salt poll (or whole `pool-kontrol.service`) so two clients don't contend on `.87`; verify integration reads + controls salt, reads/writes cloud sensor, toggles pump.
4. Re-point dashboard card + automations (`pool_kemi_vagt`, `pumpe_folger_anlaeg`, `pool_orp_auto_hold_700`, `filter_driftstimer_taeller`) + Pool-Vagt (`03-tools/16`) from old MQTT entity-ids to new native ids (mechanical old→new map, verified per item).
5. Once stable, **disable** `pool-kontrol.service` but keep it as a fallback (do not delete). Remove stale MQTT discovery configs.

## 10. Publish

Single GitHub repo `intex-pool`. `hacs.json` (name + min HA version), `manifest.json` with the 6 HACS-required keys + `version` (SemVer). CI: `home-assistant/actions/hassfest@master`, `hacs/action@main` (`category: integration`). Ship `brand/icon.png` in-repo (HA 2026.3+ — no brands PR needed for custom-repo installs). README with My-link + install steps + screenshots; `info.md`; `CHANGELOG.md`; tagged GitHub Releases drive HACS updates. Default-store submission to `hacs/default` optional/later.

## 11. Build order (phases)

1. **Skeleton + manifest + const/decoders + unit tests** (no HA needed) → green.
2. **tuya.py + coordinators** (mockable) + coordinator tests.
3. **Entities (all platforms)** + entity tests.
4. **Config flow + options/reconfigure** + flow tests.
5. **Card serving + minimal card** → deploy to HA, verify entities live (cutover §9 step 2–3).
6. **Polished adaptive card** + editor → screenshot-verify each combo.
7. **Cutover** (§9 step 4–5) + re-point automations/Pool-Vagt/dashboard.
8. **CI + docs + brand + release** → push to GitHub, verify HACS install in a clean check.
9. **Polish pass**: iterate on look/robustness until "super good".
