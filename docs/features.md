# Features and behavior

[Overview](../README.md) · [Dashboard guide](dashboard.md) · [Tuya setup](tuya-setup.md) · [Troubleshooting](troubleshooting.md)

Intex Pool supports three equipment roles in one integration entry. You can
configure any combination of them.

| Equipment | Connection | Main behavior |
| --- | --- | --- |
| Water Analyzer | Tuya developer cloud | pH, ORP, reference-only free chlorine, water temperature, battery, writable targets, measurement refresh, and read-only measurement schedules |
| Intex/AGP saltwater system | Local Tuya LAN, with optional cloud credentials for schedules | Power and chlorination controls, salinity, temperature, status, alarms, configuration controls, and editable schedules |
| Sand-filter pump | Local Tuya LAN or an existing Home Assistant switch | Local Tuya controls and editable schedules, or a linked switch with optional power/energy sensors and pump auto mode |

The built-in Home Assistant Tuya integration does not provide credentials or
devices to Intex Pool. Cloud features use a Tuya developer project's Access ID,
Access Secret, and exact data-center region.

## Schedules

The three schedule sources have different capabilities:

| Device | Cloud property | Home Assistant entities | Writable |
| --- | --- | --- | --- |
| Saltwater system | `skdl_salt` | Schedules sensor; seven slot switches and duration controls; start-time controls for slots 1-6 | Yes, through the entities or `intex_pool.set_schedule` |
| Water Analyzer | `skdl_orpph` | Measurement schedules sensor | No |
| Local Tuya pump | `skdl_filter` | Schedules sensor; seven slot switches, duration controls, and start-time controls | Yes, through the entities |
| Linked Home Assistant pump switch | None | No Intex schedule entities | No |

Saltwater slot `0` is the Boost cycle. It has a duration but no meaningful
start time. Turning Boost on temporarily clears active timed saltwater slots;
the integration remembers and restores them when Boost is turned off. A pump's
slot `0` is a normal timer slot and does have a start time.

Schedule data is cloud-only, even when the saltwater system or pump itself is
controlled locally. A manual local-only setup therefore has local controls but
no schedule entities. Cloud discovery retains the credentials for saltwater-only
and Tuya-pump-only entries so their schedule coordinators can recover after a
temporary cloud failure.

The slot format is a fixed seven-slot, 56-byte value. The integration preserves
that value across decode and encode. Labels for repeat-day semantics remain
best-effort because firmware and app behavior can differ.

## Linked pump auto mode

Pump auto mode is created only when the same integration entry contains:

1. a local saltwater system; and
2. a pump linked as an existing Home Assistant switch.

When enabled, it follows the saltwater system's chlorine-production state
(`DP103`). It turns the linked pump on while production is active, then keeps it
on for one hour after production stops. Turning Pump auto mode off leaves the
linked pump under manual control. If the production state is unavailable or
invalid, the integration pauses automatic switching until a valid state returns.

A relay selected only in the dashboard card does not create this interlock. The
pump must be linked in the integration setup or reconfiguration flow.

## Measurements and derived values

### Enter the required values

1. Open **Settings → Devices & services → Intex Pool**, then the relevant device page.
2. On the **Water Analyzer**, find the configuration numbers **Total alkalinity (test)**,
   **Calcium hardness (test)**, **Cyanuric acid (test)** and **TDS (test)**. Enter your
   measured values; zero means not provided. LSI needs alkalinity and calcium hardness
   together with the analyzer's current pH and temperature.
3. On the **saltwater device**, set **Pool volume**. Check **Volume unit** and
   **Target salinity** in the integration's **Configure/Options** before using the estimate.
   Enter the volume in the selected unit; use zero to disable the salt estimate.
4. Check the calculated **LSI / Water balance** or **Salt to add** entity after changing
   the inputs. Missing prerequisites can leave a calculated value unknown.

If a configuration entity is hidden or disabled, find it in **Settings → Devices &
services → Entities** filtered to Intex Pool. The **ORP calibration offset** entity
is intentionally disabled by default; a pH/free-chlorine test is not an ORP reference.

### What the values mean

- **Free chlorine** is a device-derived reference value. Software calibration
  changes pH or ORP only; it does not recalibrate free chlorine.
- **Refresh measurement** sends the supported refresh/re-test command and then
  polls again. Successful command delivery does not prove that the sleeping
  analyzer has produced a new sample; confirm the **Last measurement** value.
- **Cell wear** is an estimate that scales the device's 0-5000-hour runtime
  counter to a percentage. Treating that counter range as rated cell life is an
  integration assumption, not a manufacturer-provided remaining-life reading.
- **Cold water** is an advisory binary sensor below 15 °C. It does not block the
  chlorinator or switch equipment automatically.
- **LSI** uses the Water Analyzer's calibrated pH and temperature plus the
  manually entered total alkalinity and calcium hardness. Cyanuric acid and TDS
  are optional. If TDS is zero or unset and a saltwater system has a current
  salinity value, the integration uses that salinity as the TDS fallback;
  manually entered TDS takes precedence.
- **Salt to add** is advisory only. It requires a configured saltwater system,
  a current salinity value, and a non-zero pool volume. It never actuates pool
  equipment.

The Water Analyzer temperature-unit selector uses the saltwater system's
observed boolean polarity. The Water Analyzer polarity has not been verified on
physical hardware and may be inverted on some models.

## Actions

Home Assistant shows these under **Developer tools → Actions**.

Replace `config_entry_id` in these examples with the entry selected by HA's
**Configuration entry** field. It is not a device ID or entity ID. For one
matching entry you can omit the field; with several entries, select it explicitly.
The examples are action steps that can also be used in scripts/automations.

### `intex_pool.set_schedule`

Creates, changes, or clears a saltwater-system schedule slot. It does not target
the Water Analyzer or pump schedules.

```yaml
action: intex_pool.set_schedule
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  slot: 4
  enable: true
  hour: 22
  minute: 0
  duration: 2
  days: 255
```

`slot` is zero-based (`0`-`6`). The optional `enable` field controls the slot's
on/boost byte; it does not remove the slot. Use `clear: true` to empty a slot.
`days: 255` represents every day, while `days: 0` is used with `month` and
`date` for a one-time entry. Duration is in hours and accepts `0`-`72`.

`config_entry_id` is optional when only one matching integration entry exists.
Set it when more than one Intex Pool entry is configured so the action targets
the intended entry.

### `intex_pool.get_schedule`

Returns response data for every schedule coordinator in the selected entry:
`saltwater`, `analyzer`, and `pump`. A value is `null` when that schedule source
is not configured.

```yaml
action: intex_pool.get_schedule
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
response_variable: intex_schedules
```

`response_variable` stores the result when this is a script/automation step.
In Developer tools → Actions, omit that line and view the returned response in the UI.

### `intex_pool.calibrate`

Computes and stores a software offset from the current analyzer reading and a
reference value. Supported parameters are `ph` and `orp`.

```yaml
action: intex_pool.calibrate
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  parameter: ph
  reference_value: 7.4
```

The action rejects an offset larger than ±0.5 pH or ±100 mV. Values inside the
device-resolution deadband are stored as zero. When requested with response
data, it returns the device value, reference value, and resulting offset.

### `intex_pool.clear_calibration`

Removes both stored software offsets from the selected entry.

```yaml
action: intex_pool.clear_calibration
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
```
